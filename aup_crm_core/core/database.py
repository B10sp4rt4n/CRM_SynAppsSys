import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "aup_crm.sqlite"

def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error en conexión SQLite: {e}")
        return None

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # crea /data si no existe
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS aup_agentes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT,
        nombre TEXT,
        atributos TEXT,
        password_hash TEXT,
        activo INTEGER DEFAULT 1,
        fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS aup_relaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agente_origen INTEGER,
        agente_destino INTEGER,
        tipo_relacion TEXT,
        fecha TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS aup_eventos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agente_id INTEGER,
        accion TEXT,
        descripcion TEXT,
        fecha TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS aup_config_global (
        clave TEXT PRIMARY KEY,
        valor TEXT,
        fecha TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()
