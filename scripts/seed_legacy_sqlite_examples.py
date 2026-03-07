from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crm_exo_v2.core.db_runtime import get_sqlite_db_path

DB_PATH = get_sqlite_db_path(ROOT)


EXAMPLES = [
    {
        "empresa": {
            "nombre": "DEMO ThreatDown Norte",
            "rfc": "DTN250307A11",
            "sector": "Ciberseguridad",
            "telefono": "5551001001",
            "correo": "compras@norte.demo.mx",
        },
        "contacto": {
            "nombre": "Ana Lucero",
            "correo": "ana.lucero@norte.demo.mx",
            "telefono": "5551002001",
            "puesto": "Directora de TI",
        },
        "prospecto": {"origen": "Referido", "estado": "Activo", "es_cliente": 1},
        "oportunidad": {
            "nombre": "Licenciamiento MDR anual",
            "etapa": "Ganada",
            "probabilidad": 100,
            "monto_estimado": 185000.0,
            "oc_recibida": 1,
            "dias_cierre": 10,
        },
        "cotizacion": {"modo": "generico", "monto_total": 185000.0, "moneda": "MXN", "estado": "Aceptada"},
        "oc": {"numero_oc": "DEMO-OC-001", "monto_oc": 185000.0, "moneda": "MXN"},
        "factura": {"uuid": "11111111-1111-4111-8111-111111111111", "serie": "A", "folio": "1001", "monto_total": 185000.0, "moneda": "MXN"},
    },
    {
        "empresa": {
            "nombre": "DEMO FinOps Bajio",
            "rfc": "DFB250307B22",
            "sector": "Finanzas",
            "telefono": "5551001002",
            "correo": "direccion@bajio.demo.mx",
        },
        "contacto": {
            "nombre": "Marco Ibarra",
            "correo": "marco.ibarra@bajio.demo.mx",
            "telefono": "5551002002",
            "puesto": "CFO",
        },
        "prospecto": {"origen": "Campana", "estado": "Activo", "es_cliente": 0},
        "oportunidad": {
            "nombre": "Conciliacion CFDI automatizada",
            "etapa": "Negociación",
            "probabilidad": 70,
            "monto_estimado": 92000.0,
            "oc_recibida": 0,
            "dias_cierre": 18,
        },
        "cotizacion": {"modo": "externo", "monto_total": 92000.0, "moneda": "MXN", "estado": "Enviada"},
    },
    {
        "empresa": {
            "nombre": "DEMO Retail Centro",
            "rfc": "DRC250307C33",
            "sector": "Retail",
            "telefono": "5551001003",
            "correo": "sistemas@retailcentro.demo.mx",
        },
        "contacto": {
            "nombre": "Luisa Vera",
            "correo": "luisa.vera@retailcentro.demo.mx",
            "telefono": "5551002003",
            "puesto": "Gerente de Sistemas",
        },
        "prospecto": {"origen": "LinkedIn", "estado": "Activo", "es_cliente": 0},
        "oportunidad": {
            "nombre": "Monitoreo de sucursales",
            "etapa": "Propuesta",
            "probabilidad": 55,
            "monto_estimado": 64000.0,
            "oc_recibida": 0,
            "dias_cierre": 24,
        },
        "cotizacion": {"modo": "minimo", "monto_total": 64000.0, "moneda": "USD", "estado": "Borrador"},
    },
    {
        "empresa": {
            "nombre": "DEMO Logistica Sur",
            "rfc": "DLS250307D44",
            "sector": "Logistica",
            "telefono": "5551001004",
            "correo": "operaciones@logsur.demo.mx",
        },
        "contacto": {
            "nombre": "Paola Medina",
            "correo": "paola.medina@logsur.demo.mx",
            "telefono": "5551002004",
            "puesto": "Directora Operativa",
        },
        "prospecto": {"origen": "Webinar", "estado": "Activo", "es_cliente": 1},
        "oportunidad": {
            "nombre": "Hardening de endpoints",
            "etapa": "Ganada",
            "probabilidad": 100,
            "monto_estimado": 128500.0,
            "oc_recibida": 1,
            "dias_cierre": 7,
        },
        "cotizacion": {"modo": "generico", "monto_total": 128500.0, "moneda": "MXN", "estado": "Aceptada"},
        "oc": {"numero_oc": "DEMO-OC-002", "monto_oc": 128500.0, "moneda": "MXN"},
    },
    {
        "empresa": {
            "nombre": "DEMO Manufactura Este",
            "rfc": "DME250307E55",
            "sector": "Manufactura",
            "telefono": "5551001005",
            "correo": "it@manuest.demo.mx",
        },
        "contacto": {
            "nombre": "Raul Pineda",
            "correo": "raul.pineda@manuest.demo.mx",
            "telefono": "5551002005",
            "puesto": "Arquitecto de Infraestructura",
        },
        "prospecto": {"origen": "Outbound", "estado": "Activo", "es_cliente": 0},
    },
]


def registrar_evento(con: sqlite3.Connection, entidad: str, id_entidad: int, accion: str, valor_nuevo: str, usuario: str = "seed") -> None:
    timestamp = date.today().isoformat()
    raw = f"{entidad}|{accion}|{valor_nuevo}|{timestamp}"
    hash_evento = hashlib.sha256(raw.encode()).hexdigest()
    con.execute(
        """
        INSERT INTO historial_general
        (entidad, id_entidad, accion, valor_nuevo, usuario, timestamp, hash_evento)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (entidad, id_entidad, accion, valor_nuevo, usuario, timestamp, hash_evento),
    )


def registrar_hash(con: sqlite3.Connection, tabla_origen: str, id_registro: int, payload: dict) -> None:
    hash_sha256 = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    con.execute(
        "INSERT INTO hash_registros (tabla_origen, id_registro, hash_sha256) VALUES (?, ?, ?)",
        (tabla_origen, id_registro, hash_sha256),
    )


def fetch_one(cur: sqlite3.Cursor, query: str, params: tuple) -> sqlite3.Row | None:
    cur.execute(query, params)
    return cur.fetchone()


def main() -> int:
    if not DB_PATH.exists():
        raise RuntimeError(f"SQLite no encontrada: {DB_PATH}")

    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    summary = {
        "empresas": 0,
        "contactos": 0,
        "prospectos": 0,
        "oportunidades": 0,
        "cotizaciones": 0,
        "ocs": 0,
        "facturas": 0,
    }

    try:
        for index, example in enumerate(EXAMPLES, start=1):
            empresa = example["empresa"]
            row = fetch_one(cur, "SELECT id_empresa FROM empresas WHERE rfc = ? OR nombre = ?", (empresa["rfc"], empresa["nombre"]))
            if row:
                id_empresa = row["id_empresa"]
            else:
                cur.execute(
                    "INSERT INTO empresas (nombre, rfc, sector, telefono, correo) VALUES (?, ?, ?, ?, ?)",
                    (empresa["nombre"], empresa["rfc"], empresa["sector"], empresa["telefono"], empresa["correo"]),
                )
                id_empresa = cur.lastrowid
                registrar_evento(con, "empresa", id_empresa, "CREAR", f"Empresa seed: {empresa['nombre']}")
                summary["empresas"] += 1

            contacto = example["contacto"]
            row = fetch_one(cur, "SELECT id_contacto FROM contactos WHERE id_empresa = ? AND correo = ?", (id_empresa, contacto["correo"]))
            if row:
                id_contacto = row["id_contacto"]
            else:
                cur.execute(
                    "INSERT INTO contactos (id_empresa, nombre, correo, telefono, puesto) VALUES (?, ?, ?, ?, ?)",
                    (id_empresa, contacto["nombre"], contacto["correo"], contacto["telefono"], contacto["puesto"]),
                )
                id_contacto = cur.lastrowid
                registrar_evento(con, "contacto", id_contacto, "CREAR", f"Contacto seed: {contacto['nombre']}")
                summary["contactos"] += 1

            prospecto = example["prospecto"]
            row = fetch_one(cur, "SELECT id_prospecto FROM prospectos WHERE id_empresa = ?", (id_empresa,))
            if row:
                id_prospecto = row["id_prospecto"]
            else:
                fecha_conversion = date.today().isoformat() if prospecto["es_cliente"] else None
                cur.execute(
                    """
                    INSERT INTO prospectos (id_empresa, id_contacto, estado, origen, es_cliente, fecha_conversion_cliente)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (id_empresa, id_contacto, prospecto["estado"], prospecto["origen"], prospecto["es_cliente"], fecha_conversion),
                )
                id_prospecto = cur.lastrowid
                registrar_evento(con, "prospecto", id_prospecto, "CREAR", f"Prospecto seed: {empresa['nombre']}")
                summary["prospectos"] += 1

            oportunidad = example.get("oportunidad")
            if oportunidad:
                row = fetch_one(cur, "SELECT id_oportunidad FROM oportunidades WHERE id_prospecto = ? AND nombre = ?", (id_prospecto, oportunidad["nombre"]))
                if row:
                    id_oportunidad = row["id_oportunidad"]
                else:
                    fecha_estimada = (date.today() + timedelta(days=oportunidad["dias_cierre"])).isoformat()
                    cur.execute(
                        """
                        INSERT INTO oportunidades
                        (id_prospecto, nombre, etapa, probabilidad, monto_estimado, oc_recibida, fecha_estimada_cierre)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            id_prospecto,
                            oportunidad["nombre"],
                            oportunidad["etapa"],
                            oportunidad["probabilidad"],
                            oportunidad["monto_estimado"],
                            oportunidad["oc_recibida"],
                            fecha_estimada,
                        ),
                    )
                    id_oportunidad = cur.lastrowid
                    if oportunidad["etapa"] == "Ganada" and prospecto["es_cliente"]:
                        cur.execute(
                            "UPDATE prospectos SET es_cliente = 1, fecha_conversion_cliente = COALESCE(fecha_conversion_cliente, ?) WHERE id_prospecto = ?",
                            (date.today().isoformat(), id_prospecto),
                        )
                    registrar_evento(con, "oportunidad", id_oportunidad, "CREAR", f"Oportunidad seed: {oportunidad['nombre']}")
                    summary["oportunidades"] += 1

                cotizacion = example.get("cotizacion")
                if cotizacion:
                    row = fetch_one(cur, "SELECT id_cotizacion FROM cotizaciones WHERE id_oportunidad = ?", (id_oportunidad,))
                    if not row:
                        payload = {
                            "id_oportunidad": id_oportunidad,
                            "modo": cotizacion["modo"],
                            "monto_total": cotizacion["monto_total"],
                            "moneda": cotizacion["moneda"],
                        }
                        hash_integridad = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                        cur.execute(
                            """
                            INSERT INTO cotizaciones
                            (id_oportunidad, modo, fuente, monto_total, moneda, estado, hash_integridad, notas)
                            VALUES (?, ?, 'manual', ?, ?, ?, ?, ?)
                            """,
                            (
                                id_oportunidad,
                                cotizacion["modo"],
                                cotizacion["monto_total"],
                                cotizacion["moneda"],
                                cotizacion["estado"],
                                hash_integridad,
                                f"Seed example {index}",
                            ),
                        )
                        id_cotizacion = cur.lastrowid
                        registrar_hash(con, "cotizaciones", id_cotizacion, payload)
                        registrar_evento(con, "cotizacion", id_cotizacion, "CREAR", f"Cotizacion seed: {oportunidad['nombre']}")
                        summary["cotizaciones"] += 1

                oc = example.get("oc")
                if oc:
                    row = fetch_one(cur, "SELECT id_oc FROM ordenes_compra WHERE numero_oc = ?", (oc["numero_oc"],))
                    if row:
                        id_oc = row["id_oc"]
                    else:
                        cur.execute(
                            "INSERT INTO ordenes_compra (id_oportunidad, numero_oc, fecha_oc, monto_oc, moneda) VALUES (?, ?, ?, ?, ?)",
                            (id_oportunidad, oc["numero_oc"], date.today().isoformat(), oc["monto_oc"], oc["moneda"]),
                        )
                        id_oc = cur.lastrowid
                        registrar_evento(con, "orden_compra", id_oc, "CREAR", f"OC seed: {oc['numero_oc']}")
                        summary["ocs"] += 1

                    factura = example.get("factura")
                    if factura:
                        row = fetch_one(cur, "SELECT id_factura FROM facturas WHERE uuid = ?", (factura["uuid"],))
                        if not row:
                            cur.execute(
                                """
                                INSERT INTO facturas (id_oc, uuid, serie, folio, fecha_emision, monto_total, moneda)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    id_oc,
                                    factura["uuid"],
                                    factura["serie"],
                                    factura["folio"],
                                    date.today().isoformat(),
                                    factura["monto_total"],
                                    factura["moneda"],
                                ),
                            )
                            id_factura = cur.lastrowid
                            registrar_hash(con, "facturas", id_factura, factura)
                            registrar_evento(con, "factura", id_factura, "CREAR", f"Factura seed: {factura['uuid']}")
                            summary["facturas"] += 1

        con.commit()
    finally:
        con.close()

    print("SEED_OK")
    for key, value in summary.items():
        print(key, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())