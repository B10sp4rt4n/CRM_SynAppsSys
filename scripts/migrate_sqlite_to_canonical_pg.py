from __future__ import annotations

import sqlite3
import sys
import tomllib
from pathlib import Path
from typing import Any, Optional

import psycopg


ROOT = Path(__file__).resolve().parent.parent
SQLITE_PATH = ROOT / "crm_exo_v2" / "data" / "crm_exo_v2.sqlite"
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"


def load_database_url() -> str:
    env_value = __import__("os").getenv("DATABASE_URL")
    if env_value:
        return env_value

    if SECRETS_PATH.exists():
        raw = SECRETS_PATH.read_text(encoding="utf-8")
        data = tomllib.loads(raw)
        if data.get("DATABASE_URL"):
            return str(data["DATABASE_URL"])

    raise RuntimeError("DATABASE_URL no disponible en entorno ni en .streamlit/secrets.toml")


def normalize_rfc(raw_value: Optional[str], prefix: str, legacy_id: int) -> str:
    if raw_value and raw_value.strip():
        return raw_value.strip().upper()
    return f"{prefix}{legacy_id:08d}"


def map_prospecto_estado(estado: Optional[str], es_cliente: int) -> str:
    if es_cliente:
        return "convertido"
    mapping = {
        None: "nuevo",
        "": "nuevo",
        "Activo": "contactado",
        "nuevo": "nuevo",
        "contactado": "contactado",
        "calificado": "calificado",
        "perdido": "perdido",
        "convertido": "convertido",
    }
    return mapping.get(estado, "contactado")


def map_oportunidad(etapa: Optional[str]) -> tuple[str, str]:
    if etapa == "Ganada":
        return "postventa", "ganada"
    if etapa == "Perdida":
        return "cierre", "perdida"

    mapping = {
        "Calificación": "calificacion",
        "Propuesta": "propuesta",
        "Negociación": "negociacion",
        "Cierre": "cierre",
    }
    return mapping.get(etapa, "calificacion"), "abierta"


def map_cotizacion_estado(estado: Optional[str]) -> str:
    mapping = {
        None: "borrador",
        "": "borrador",
        "Borrador": "borrador",
        "Enviada": "enviada",
        "Aceptada": "aceptada",
        "Rechazada": "rechazada",
        "Vencida": "vencida",
    }
    return mapping.get(estado, "borrador")


def map_oc_estado(has_invoice: bool) -> str:
    return "facturada" if has_invoice else "pendiente"


def ensure_entity(cur: psycopg.Cursor, *, rfc: str, razon_social: str, nombre_comercial: Optional[str], regimen_fiscal: Optional[str] = None,
                  codigo_postal_fiscal: str = "00000", correo_comercial: Optional[str] = None,
                  tipo_entidad: str = "empresa", telefono: Optional[str] = None, sector: Optional[str] = None) -> int:
    cur.execute(
        """
        INSERT INTO entidades_fiscales (
            tipo_entidad, rfc, razon_social, nombre_comercial, regimen_fiscal,
            codigo_postal_fiscal, correo_comercial, telefono, sector, creado_en
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (rfc) DO UPDATE SET
            tipo_entidad = EXCLUDED.tipo_entidad,
            razon_social = EXCLUDED.razon_social,
            nombre_comercial = EXCLUDED.nombre_comercial,
            regimen_fiscal = COALESCE(EXCLUDED.regimen_fiscal, entidades_fiscales.regimen_fiscal),
            correo_comercial = COALESCE(EXCLUDED.correo_comercial, entidades_fiscales.correo_comercial),
            telefono = COALESCE(EXCLUDED.telefono, entidades_fiscales.telefono),
            sector = COALESCE(EXCLUDED.sector, entidades_fiscales.sector),
            actualizado_en = NOW()
        RETURNING id_entidad
        """,
        (tipo_entidad, rfc, razon_social, nombre_comercial, regimen_fiscal, codigo_postal_fiscal, correo_comercial, telefono, sector),
    )
    return cur.fetchone()[0]


def ensure_contact(cur: psycopg.Cursor, id_entidad: int, nombre: str, correo: Optional[str], telefono: Optional[str], puesto: Optional[str]) -> int:
    cur.execute(
        """
        SELECT id_contacto
        FROM contactos
        WHERE id_entidad = %s AND nombre = %s AND COALESCE(correo, '') = COALESCE(%s, '')
        LIMIT 1
        """,
        (id_entidad, nombre, correo),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO contactos (id_entidad, nombre, correo, telefono, puesto, creado_en)
        VALUES (%s, %s, %s, %s, %s, NOW())
        RETURNING id_contacto
        """,
        (id_entidad, nombre, correo, telefono, puesto),
    )
    return cur.fetchone()[0]


def ensure_relation(cur: psycopg.Cursor, origen_tipo: str, origen_id: int, tipo_relacion: str, destino_tipo: str, destino_id: int):
    cur.execute(
        """
        SELECT id_relacion
        FROM relaciones_grafo
        WHERE nodo_origen_tipo = %s AND nodo_origen_id = %s AND tipo_relacion = %s
          AND nodo_destino_tipo = %s AND nodo_destino_id = %s
        LIMIT 1
        """,
        (origen_tipo, origen_id, tipo_relacion, destino_tipo, destino_id),
    )
    if cur.fetchone():
        return

    cur.execute(
        """
        INSERT INTO relaciones_grafo (
            nodo_origen_tipo, nodo_origen_id, tipo_relacion, nodo_destino_tipo, nodo_destino_id, creado_en
        ) VALUES (%s, %s, %s, %s, %s, NOW())
        """,
        (origen_tipo, origen_id, tipo_relacion, destino_tipo, destino_id),
    )


def main() -> int:
    if not SQLITE_PATH.exists():
        raise RuntimeError(f"SQLite origen no encontrada: {SQLITE_PATH}")

    database_url = load_database_url()

    src = sqlite3.connect(str(SQLITE_PATH))
    src.row_factory = sqlite3.Row
    pg = psycopg.connect(database_url)

    entity_map: dict[int, int] = {}
    contact_map: dict[int, int] = {}
    prospect_map: dict[int, int] = {}
    opportunity_map: dict[int, int] = {}
    oc_map: dict[int, int] = {}

    summary: dict[str, int] = {
        "entidades": 0,
        "contactos": 0,
        "prospectos": 0,
        "oportunidades": 0,
        "cotizaciones": 0,
        "ocs": 0,
        "cfdis": 0,
        "eventos": 0,
        "hashes": 0,
    }

    try:
        with pg.cursor() as cur:
            # Emisores CFDI primero, si existen
            for row in src.execute("SELECT * FROM config_cfdi_emisor ORDER BY id"):
                ensure_entity(
                    cur,
                    rfc=normalize_rfc(row["rfc_emisor"], "EMISOR", row["id"]),
                    razon_social=row["razon_social"] or row["rfc_emisor"],
                    nombre_comercial=row["razon_social"] or row["rfc_emisor"],
                    regimen_fiscal=row["regimen_fiscal"],
                    tipo_entidad="emisor",
                )

            for row in src.execute("SELECT * FROM empresas ORDER BY id_empresa"):
                entity_id = ensure_entity(
                    cur,
                    rfc=normalize_rfc(row["rfc"], "PENDRFC", row["id_empresa"]),
                    razon_social=row["nombre"],
                    nombre_comercial=row["nombre"],
                    correo_comercial=row["correo"],
                    telefono=row["telefono"],
                    sector=row["sector"],
                    tipo_entidad="empresa",
                )
                entity_map[row["id_empresa"]] = entity_id
                summary["entidades"] += 1

            for row in src.execute("SELECT * FROM contactos ORDER BY id_contacto"):
                if row["id_empresa"] not in entity_map:
                    continue
                contact_id = ensure_contact(
                    cur,
                    entity_map[row["id_empresa"]],
                    row["nombre"],
                    row["correo"],
                    row["telefono"],
                    row["puesto"],
                )
                contact_map[row["id_contacto"]] = contact_id
                ensure_relation(cur, "entidades_fiscales", entity_map[row["id_empresa"]], "tiene_contacto", "contactos", contact_id)
                summary["contactos"] += 1

            for row in src.execute("SELECT * FROM prospectos ORDER BY id_prospecto"):
                entity_id = entity_map.get(row["id_empresa"])
                if not entity_id:
                    continue
                cur.execute(
                    """
                    INSERT INTO prospectos (
                        id_entidad, id_contacto, origen, fuente, estado, es_cliente,
                        fecha_conversion_cliente, creado_en
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, NOW()))
                    ON CONFLICT (id_entidad) DO UPDATE SET
                        id_contacto = EXCLUDED.id_contacto,
                        origen = EXCLUDED.origen,
                        fuente = EXCLUDED.fuente,
                        estado = EXCLUDED.estado,
                        es_cliente = EXCLUDED.es_cliente,
                        fecha_conversion_cliente = EXCLUDED.fecha_conversion_cliente,
                        actualizado_en = NOW()
                    RETURNING id_prospecto
                    """,
                    (
                        entity_id,
                        contact_map.get(row["id_contacto"]),
                        row["origen"],
                        None,
                        map_prospecto_estado(row["estado"], row["es_cliente"] or 0),
                        1 if row["es_cliente"] else 0,
                        row["fecha_conversion_cliente"],
                        row["fecha_creacion"],
                    ),
                )
                prospect_id = cur.fetchone()[0]
                prospect_map[row["id_prospecto"]] = prospect_id
                ensure_relation(cur, "entidades_fiscales", entity_id, "tiene_prospecto", "prospectos", prospect_id)
                summary["prospectos"] += 1

            for row in src.execute("SELECT * FROM oportunidades ORDER BY id_oportunidad"):
                prospect_id = prospect_map.get(row["id_prospecto"])
                legacy_entity = None
                if row["id_prospecto"] in prospect_map:
                    src_prospect = src.execute("SELECT id_empresa FROM prospectos WHERE id_prospecto = ?", (row["id_prospecto"],)).fetchone()
                    if src_prospect:
                        legacy_entity = entity_map.get(src_prospect["id_empresa"])
                if not legacy_entity:
                    continue
                etapa, estado = map_oportunidad(row["etapa"])
                cur.execute(
                    """
                    INSERT INTO oportunidades (
                        id_entidad, id_prospecto, folio_oportunidad, nombre, etapa, estado,
                        probabilidad, monto_estimado, moneda_estimacion, fecha_estimada_cierre,
                        oc_recibida, creado_en
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'MXN', %s, %s, COALESCE(%s::timestamptz, NOW()))
                    ON CONFLICT (folio_oportunidad) DO UPDATE SET
                        nombre = EXCLUDED.nombre,
                        etapa = EXCLUDED.etapa,
                        estado = EXCLUDED.estado,
                        probabilidad = EXCLUDED.probabilidad,
                        monto_estimado = EXCLUDED.monto_estimado,
                        fecha_estimada_cierre = EXCLUDED.fecha_estimada_cierre,
                        oc_recibida = EXCLUDED.oc_recibida,
                        actualizado_en = NOW()
                    RETURNING id_oportunidad
                    """,
                    (
                        legacy_entity,
                        prospect_id,
                        f"LEGACY-OP-{row['id_oportunidad']}",
                        row["nombre"] or f"Oportunidad {row['id_oportunidad']}",
                        etapa,
                        estado,
                        row["probabilidad"] or 0,
                        row["monto_estimado"] or 0,
                        row["fecha_estimada_cierre"],
                        1 if row["oc_recibida"] else 0,
                        row["fecha_creacion"],
                    ),
                )
                op_id = cur.fetchone()[0]
                opportunity_map[row["id_oportunidad"]] = op_id
                if prospect_id:
                    ensure_relation(cur, "prospectos", prospect_id, "evoluciona_a", "oportunidades", op_id)
                summary["oportunidades"] += 1

            for row in src.execute("SELECT * FROM cotizaciones ORDER BY id_cotizacion"):
                op_id = opportunity_map.get(row["id_oportunidad"])
                if not op_id:
                    continue
                cur.execute(
                    """
                    INSERT INTO cotizaciones (
                        id_oportunidad, folio_cotizacion, version, modo, fuente, moneda,
                        subtotal, total, estado, notas, fecha_emision, hash_integridad, creado_en
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, NOW()), %s, NOW())
                    ON CONFLICT (folio_cotizacion) DO UPDATE SET
                        version = EXCLUDED.version,
                        modo = EXCLUDED.modo,
                        fuente = EXCLUDED.fuente,
                        moneda = EXCLUDED.moneda,
                        subtotal = EXCLUDED.subtotal,
                        total = EXCLUDED.total,
                        estado = EXCLUDED.estado,
                        notas = EXCLUDED.notas,
                        fecha_emision = EXCLUDED.fecha_emision,
                        hash_integridad = EXCLUDED.hash_integridad,
                        actualizado_en = NOW()
                    RETURNING id_cotizacion
                    """,
                    (
                        op_id,
                        f"LEGACY-COT-{row['id_cotizacion']}",
                        row["version"] or 1,
                        row["modo"] or "minimo",
                        row["fuente"],
                        row["moneda"] or "MXN",
                        row["monto_total"] or 0,
                        row["monto_total"] or 0,
                        map_cotizacion_estado(row["estado"]),
                        row["notas"],
                        row["fecha_creacion"],
                        row["hash_integridad"],
                    ),
                )
                cot_id = cur.fetchone()[0]
                ensure_relation(cur, "oportunidades", op_id, "genera", "cotizaciones", cot_id)
                summary["cotizaciones"] += 1

            facturas_src = {row["id_oc"]: row for row in src.execute("SELECT * FROM facturas")}

            for row in src.execute("SELECT * FROM ordenes_compra ORDER BY id_oc"):
                op_id = opportunity_map.get(row["id_oportunidad"])
                if not op_id:
                    continue
                src_op = src.execute("SELECT id_prospecto FROM oportunidades WHERE id_oportunidad = ?", (row["id_oportunidad"],)).fetchone()
                src_pr = src.execute("SELECT id_empresa FROM prospectos WHERE id_prospecto = ?", (src_op["id_prospecto"],)).fetchone() if src_op else None
                entity_id = entity_map.get(src_pr["id_empresa"]) if src_pr else None
                if not entity_id:
                    continue
                cur.execute(
                    """
                    INSERT INTO ordenes_compra (
                        id_entidad, id_oportunidad, numero_oc, fecha_oc, moneda,
                        subtotal, total, archivo_pdf, estado, hash_integridad, creado_en
                    ) VALUES (%s, %s, %s, COALESCE(%s::timestamptz, NOW()), %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (numero_oc) DO UPDATE SET
                        fecha_oc = EXCLUDED.fecha_oc,
                        moneda = EXCLUDED.moneda,
                        subtotal = EXCLUDED.subtotal,
                        total = EXCLUDED.total,
                        archivo_pdf = EXCLUDED.archivo_pdf,
                        estado = EXCLUDED.estado,
                        hash_integridad = EXCLUDED.hash_integridad,
                        actualizado_en = NOW()
                    RETURNING id_oc
                    """,
                    (
                        entity_id,
                        op_id,
                        row["numero_oc"] or f"LEGACY-OC-{row['id_oc']}",
                        row["fecha_oc"],
                        row["moneda"] or "MXN",
                        row["monto_oc"] or 0,
                        row["monto_oc"] or 0,
                        row["archivo_pdf"],
                        map_oc_estado(row["id_oc"] in facturas_src),
                        None,
                    ),
                )
                oc_id = cur.fetchone()[0]
                oc_map[row["id_oc"]] = oc_id
                ensure_relation(cur, "oportunidades", op_id, "recibe", "ordenes_compra", oc_id)
                summary["ocs"] += 1

            cur.execute(
                "SELECT id_entidad FROM entidades_fiscales WHERE tipo_entidad IN ('emisor', 'mixta') ORDER BY id_entidad LIMIT 1"
            )
            emisor_row = cur.fetchone()
            default_emisor_id = emisor_row[0] if emisor_row else ensure_entity(
                cur,
                rfc="EMISOR00000001",
                razon_social="EMISOR PENDIENTE",
                nombre_comercial="EMISOR PENDIENTE",
                tipo_entidad="emisor",
            )

            for row in src.execute("SELECT * FROM facturas ORDER BY id_factura"):
                oc_id = oc_map.get(row["id_oc"])
                if not oc_id:
                    continue
                src_oc = src.execute("SELECT id_oportunidad FROM ordenes_compra WHERE id_oc = ?", (row["id_oc"],)).fetchone()
                src_op = src.execute("SELECT id_prospecto FROM oportunidades WHERE id_oportunidad = ?", (src_oc["id_oportunidad"],)).fetchone() if src_oc else None
                src_pr = src.execute("SELECT id_empresa FROM prospectos WHERE id_prospecto = ?", (src_op["id_prospecto"],)).fetchone() if src_op else None
                receptor_id = entity_map.get(src_pr["id_empresa"]) if src_pr else None
                if not receptor_id:
                    continue
                cur.execute(
                    """
                    INSERT INTO comprobantes_cfdi (
                        uuid, id_emisor, id_receptor, id_oc, serie, folio, fecha_emision,
                        moneda, subtotal, total, estado, xml_path, pdf_path, creado_en,
                        tipo_comprobante
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, NOW()),
                        %s, %s, %s, %s, %s, %s, NOW(), 'I'
                    )
                    ON CONFLICT (uuid) DO UPDATE SET
                        id_oc = EXCLUDED.id_oc,
                        serie = EXCLUDED.serie,
                        folio = EXCLUDED.folio,
                        fecha_emision = EXCLUDED.fecha_emision,
                        moneda = EXCLUDED.moneda,
                        subtotal = EXCLUDED.subtotal,
                        total = EXCLUDED.total,
                        estado = EXCLUDED.estado,
                        xml_path = EXCLUDED.xml_path,
                        pdf_path = EXCLUDED.pdf_path,
                        actualizado_en = NOW()
                    RETURNING id_cfdi
                    """,
                    (
                        row["uuid"] or f"LEGACY-UUID-{row['id_factura']}",
                        default_emisor_id,
                        receptor_id,
                        oc_id,
                        row["serie"],
                        row["folio"],
                        row["fecha_emision"],
                        row["moneda"] or "MXN",
                        row["monto_total"] or 0,
                        row["monto_total"] or 0,
                        "timbrado",
                        row["archivo_xml"],
                        row["archivo_pdf"],
                    ),
                )
                cfdi_id = cur.fetchone()[0]
                ensure_relation(cur, "ordenes_compra", oc_id, "sustenta", "comprobantes_cfdi", cfdi_id)
                ensure_relation(cur, "entidades_fiscales", default_emisor_id, "actua_como_emisor", "comprobantes_cfdi", cfdi_id)
                ensure_relation(cur, "entidades_fiscales", receptor_id, "actua_como_receptor", "comprobantes_cfdi", cfdi_id)
                summary["cfdis"] += 1

            for row in src.execute("SELECT * FROM historial_general ORDER BY id_evento"):
                cur.execute(
                    """
                    INSERT INTO eventos_auditoria (
                        entidad_tipo, entidad_id, accion, valor_anterior, valor_nuevo,
                        usuario, timestamp_evento, hash_evento
                    ) VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, NOW()), %s)
                    ON CONFLICT (hash_evento) DO NOTHING
                    """,
                    (
                        row["entidad"],
                        row["id_entidad"],
                        row["accion"],
                        row["valor_anterior"],
                        row["valor_nuevo"],
                        row["usuario"],
                        row["timestamp"],
                        row["hash_evento"],
                    ),
                )
                summary["eventos"] += 1

            for row in src.execute("SELECT * FROM hash_registros ORDER BY id_hash"):
                cur.execute(
                    """
                    INSERT INTO hashes_integridad (
                        tabla_origen, id_registro, hash_sha256, timestamp_hash
                    ) VALUES (%s, %s, %s, COALESCE(%s::timestamptz, NOW()))
                    """,
                    (row["tabla_origen"], row["id_registro"], row["hash_sha256"], row["timestamp"]),
                )
                summary["hashes"] += 1

        pg.commit()
    except Exception:
        pg.rollback()
        raise
    finally:
        src.close()
        pg.close()

    print("ETL_OK")
    for key, value in summary.items():
        print(key, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())