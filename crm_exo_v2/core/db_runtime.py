from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    import streamlit as st
except Exception:
    st = None

try:
    import psycopg
except Exception:
    psycopg = None


LEGACY_APP_TABLES = (
    "empresas",
    "contactos",
    "prospectos",
    "oportunidades",
    "cotizaciones",
    "ordenes_compra",
    "facturas",
    "historial_general",
    "hash_registros",
)


def get_sqlite_db_path(base_dir: Path) -> Path:
    return base_dir / "crm_exo_v2" / "data" / "crm_exo_v2.sqlite"


@lru_cache(maxsize=1)
def get_database_url() -> Optional[str]:
    env_value = os.getenv("DATABASE_URL")
    if env_value:
        return env_value

    if st is None:
        return None

    try:
        secret_value = st.secrets.get("DATABASE_URL")
        return str(secret_value) if secret_value else None
    except Exception:
        return None


@lru_cache(maxsize=1)
def legacy_postgres_schema_available() -> bool:
    database_url = get_database_url()
    if not database_url or psycopg is None:
        return False

    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = ANY(%s)
                    """,
                    (list(LEGACY_APP_TABLES),),
                )
                return cur.fetchone()[0] == len(LEGACY_APP_TABLES)
    except Exception:
        return False


def get_legacy_app_backend() -> str:
    if get_database_url() and legacy_postgres_schema_available():
        return "postgres"
    return "sqlite"


def get_legacy_app_backend_status() -> str:
    if not get_database_url():
        return "sqlite-default"
    if psycopg is None:
        return "postgres-configured-client-missing"
    if legacy_postgres_schema_available():
        return "postgres-ready"
    return "postgres-configured-schema-incompatible"