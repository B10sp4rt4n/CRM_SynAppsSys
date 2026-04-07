import pytest
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crm_exo_v2.core.dynamiquote_bridge import (
    DEFAULT_PLAYBOOK_NAME,
    DynamiQuoteError,
    importar_cotizacion_desde_dynamiquote,
    parse_dynamiquote_items,
)


def test_parse_dynamiquote_items_normaliza_campos():
    api_items, audit_items = parse_dynamiquote_items(
        """
        [
          {"sku": "LIC-001", "description": "Licencia", "quantity": 2, "cost_unit": 10, "price_unit": 15}
        ]
        """
    )

    assert api_items == [
        {
            "item_id": "LIC-001",
            "item_number": 1,
            "quantity": 2.0,
            "cost_unit": 10.0,
            "price_unit": 15.0,
        }
    ]
    assert audit_items[0]["description"] == "Licencia"


def test_parse_dynamiquote_items_falla_si_json_es_invalido():
    with pytest.raises(ValueError):
        parse_dynamiquote_items("{bad json}")


def test_importar_cotizacion_desde_dynamiquote_resume_respuesta(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "playbook_used": DEFAULT_PLAYBOOK_NAME,
                "total_items": 2,
                "nodes": [
                    {
                        "item_number": 1,
                        "subtotal_cost": 100.0,
                        "subtotal_price": 150.0,
                        "gross_profit": 50.0,
                        "health": "yellow",
                    },
                    {
                        "item_number": 2,
                        "subtotal_cost": 50.0,
                        "subtotal_price": 90.0,
                        "gross_profit": 40.0,
                        "health": "green",
                    },
                ],
            }

    def fake_post(url, json, timeout):
        assert url.endswith("/calculate/batch")
        assert json["playbook_name"] == DEFAULT_PLAYBOOK_NAME
        assert timeout == 20
        return FakeResponse()

    monkeypatch.setattr("crm_exo_v2.core.dynamiquote_bridge.requests.post", fake_post)

    resultado = importar_cotizacion_desde_dynamiquote(
        raw_items_json='[{"sku": "LIC-001", "quantity": 1, "cost_unit": 100, "price_unit": 150}, {"sku": "SERV", "quantity": 1, "cost_unit": 50, "price_unit": 90}]'
    )

    assert resultado["line_count"] == 2
    assert resultado["total_revenue"] == 240.0
    assert resultado["total_cost"] == 150.0
    assert resultado["gross_profit"] == 90.0
    assert resultado["margin_pct"] == 37.5
    assert resultado["health_summary"] == "green:1, yellow:1"


def test_importar_cotizacion_desde_dynamiquote_propagates_error(monkeypatch):
    class FakeResponse:
        status_code = 400

        def json(self):
            return {"detail": "playbook inválido"}

    monkeypatch.setattr(
        "crm_exo_v2.core.dynamiquote_bridge.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(DynamiQuoteError):
        importar_cotizacion_desde_dynamiquote(
            raw_items_json='[{"quantity": 1, "cost_unit": 10, "price_unit": 20}]'
        )