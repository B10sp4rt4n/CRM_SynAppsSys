import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "aup_crm.sqlite"

def get_connection():
    """Retorna conexión activa a la base de datos."""
    try:
        if not DB_PATH.exists():
            init_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"❌ Error al conectar con la base de datos: {e}")
        return None

def init_db():
    """Inicializa la base de datos si no existe."""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # === Tabla principal de agentes (personas, usuarios, prospectos, clientes) ===
    cur.execute("""
        CREATE TABLE IF NOT EXISTS aup_agentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT,
            nombre TEXT,
            atributos TEXT,
            password TEXT,
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # === Tabla de relaciones (grafo AUP) ===
    cur.execute("""
        CREATE TABLE IF NOT EXISTS aup_relaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agente_origen INTEGER,
            agente_destino INTEGER,
            tipo_relacion TEXT,
            fecha TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # === Tabla de eventos estructurales ===
    cur.execute("""
        CREATE TABLE IF NOT EXISTS aup_eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agente_id INTEGER,
            accion TEXT,
            descripcion TEXT,
            fecha TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # === Tabla de historial ===
    cur.execute("""
        CREATE TABLE IF NOT EXISTS aup_historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entidad TEXT,
            valor_anterior TEXT,
            valor_nuevo TEXT,
            responsable TEXT,
            fecha TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # === Tabla de configuración global ===
    cur.execute("""
        CREATE TABLE IF NOT EXISTS aup_config_global (
            clave TEXT PRIMARY KEY,
            valor TEXT,
            fecha TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada correctamente.")

def borrar_db():
    """Elimina la base de datos (solo para pruebas)."""
    if DB_PATH.exists():
        DB_PATH.unlink()
        print("🗑️ Base de datos eliminada.")
