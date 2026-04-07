from __future__ import annotations

import json
import os
from typing import Any

import requests


DEFAULT_DYNAMIQUOTE_API_URL = "http://127.0.0.1:8000"
DEFAULT_PLAYBOOK_NAME = "General"


class DynamiQuoteError(RuntimeError):
    """Error controlado para integración con DynamiQuote."""


def get_dynamiquote_api_url(configured_url: str | None = None) -> str:
    api_url = configured_url or os.getenv("DYNAMIQUOTE_API_URL") or DEFAULT_DYNAMIQUOTE_API_URL
    return api_url.rstrip("/")


def parse_dynamiquote_items(raw_items_json: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Valida y normaliza líneas de cotización capturadas como JSON."""
    if not raw_items_json or not raw_items_json.strip():
        raise ValueError("Debes proporcionar el JSON de items para DynamiQuote.")

    try:
        raw_items = json.loads(raw_items_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON de items inválido: {exc.msg}") from exc

    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("El JSON debe ser una lista no vacía de items.")

    api_items: list[dict[str, Any]] = []
    audit_items: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"El item #{index} debe ser un objeto JSON.")

        if "quantity" not in item or "cost_unit" not in item:
            raise ValueError(f"El item #{index} debe incluir quantity y cost_unit.")

        quantity = float(item["quantity"])
        cost_unit = float(item["cost_unit"])
        price_unit = item.get("price_unit")
        if price_unit is not None:
            price_unit = float(price_unit)

        if quantity <= 0:
            raise ValueError(f"El item #{index} debe tener quantity > 0.")
        if cost_unit < 0:
            raise ValueError(f"El item #{index} debe tener cost_unit >= 0.")
        if price_unit is not None and price_unit < 0:
            raise ValueError(f"El item #{index} debe tener price_unit >= 0.")

        item_number = item.get("item_number", index)
        api_item = {
            "item_id": item.get("item_id") or item.get("sku"),
            "item_number": item_number,
            "quantity": quantity,
            "cost_unit": cost_unit,
            "price_unit": price_unit,
        }
        audit_item = {
            "item_number": item_number,
            "sku": item.get("sku"),
            "description": item.get("description"),
            **api_item,
        }
        api_items.append(api_item)
        audit_items.append(audit_item)

    return api_items, audit_items


def _resolve_response_payload(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise DynamiQuoteError("DynamiQuote respondió un payload no JSON.") from exc

    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else None
        raise DynamiQuoteError(f"DynamiQuote devolvió error HTTP {response.status_code}: {detail or payload}")

    if not isinstance(payload, dict):
        raise DynamiQuoteError("DynamiQuote respondió una estructura inesperada.")
    return payload


def _summarize_health(nodes: list[dict[str, Any]]) -> str:
    health_counts: dict[str, int] = {}
    for node in nodes:
        health = str(node.get("health") or "undefined")
        health_counts[health] = health_counts.get(health, 0) + 1
    return ", ".join(f"{key}:{value}" for key, value in sorted(health_counts.items())) or "sin-health"


def importar_cotizacion_desde_dynamiquote(
    raw_items_json: str,
    playbook_name: str = DEFAULT_PLAYBOOK_NAME,
    api_url: str | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    """Calcula una cotización externa en DynamiQuote y devuelve un resumen listo para persistir."""
    api_items, audit_items = parse_dynamiquote_items(raw_items_json)
    resolved_api_url = get_dynamiquote_api_url(api_url)
    api_payload = {
        "playbook_name": playbook_name,
        "items": api_items,
    }
    response = requests.post(
        f"{resolved_api_url}/calculate/batch",
        json=api_payload,
        timeout=timeout,
    )
    response_payload = _resolve_response_payload(response)
    nodes = response_payload.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise DynamiQuoteError("DynamiQuote no devolvió líneas calculadas.")

    total_revenue = round(sum(float(node.get("subtotal_price") or 0.0) for node in nodes), 2)
    total_cost = round(sum(float(node.get("subtotal_cost") or 0.0) for node in nodes), 2)
    gross_profit = round(sum(float(node.get("gross_profit") or 0.0) for node in nodes), 2)
    margin_pct = round((gross_profit / total_revenue) * 100, 2) if total_revenue > 0 else 0.0
    external_quote_id = response_payload.get("quote_id") or response_payload.get("proposal_id")

    if total_revenue <= 0:
        raise DynamiQuoteError("DynamiQuote devolvió un total de cotización inválido.")

    return {
        "api_url": resolved_api_url,
        "playbook_name": playbook_name,
        "api_payload": api_payload,
        "audit_payload": {
            "playbook_name": playbook_name,
            "items_enviados": api_items,
            "items_originales": audit_items,
        },
        "response_payload": response_payload,
        "external_quote_id": external_quote_id,
        "line_count": len(nodes),
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "gross_profit": gross_profit,
        "margin_pct": margin_pct,
        "health_summary": _summarize_health(nodes),
    }