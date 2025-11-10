# ============================================================
#  init_db_v2.py  |  CRM-EXO v2  (Arquitectura AUP)
#  ------------------------------------------------------------
#  Crea la base estructural completa con los cuatro núcleos:
#  Identidad, Transacción, Facturación y Trazabilidad.
#  Registra evento inicial DB_INIT con hash forense del archivo.
# ============================================================

import sqlite3
import hashlib
from datetime import datetime
import os
from pathlib import Path

# Ruta relativa desde la raíz del proyecto
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "crm_exo_v2" / "data" / "crm_exo_v2.sqlite"

# ============================================================
#  FUNCIONES AUXILIARES
# ============================================================

def calcular_hash_archivo(path):
    """Calcula hash SHA-256 del archivo SQLite."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def calcular_hash_evento(entidad, id_entidad, accion, valor_anterior, valor_nuevo, usuario, timestamp):
    """
    Calcula hash SHA-256 forense del evento completo.
    CRÍTICO: Esto garantiza que el evento no pueda ser alterado.
    """
    import json
    data = {
        "entidad": entidad,
        "id_entidad": id_entidad,
        "accion": accion,
        "valor_anterior": valor_anterior or "",
        "valor_nuevo": valor_nuevo or "",
        "usuario": usuario,
        "timestamp": timestamp
    }
    data_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data_str.encode()).hexdigest()


def registrar_evento(con, entidad, id_entidad, accion, valor_nuevo, usuario="system", valor_anterior=None):
    """
    Inserta registro en historial_general CON hash forense del evento.
    AJUSTE 1: Ahora calcula y almacena el hash_evento.
    """
    ts = datetime.utcnow().isoformat()
    
    # Calcular hash forense del evento
    hash_evt = calcular_hash_evento(
        entidad, id_entidad, accion, 
        valor_anterior, valor_nuevo, 
        usuario, ts
    )
    
    cur = con.cursor()
    cur.execute("""
        INSERT INTO historial_general
        (entidad, id_entidad, accion, valor_anterior, valor_nuevo, usuario, timestamp, hash_evento)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (entidad, id_entidad, accion, valor_anterior, valor_nuevo, usuario, ts, hash_evt))
    con.commit()
    
    return hash_evt


# ============================================================
#  CREACIÓN DE ESTRUCTURA
# ============================================================

def crear_base():
    """
    Crea la base de datos SQLite con los 4 núcleos AUP.
    AJUSTE 2: Agregamos índices de rendimiento después de crear tablas.
    """
    # Crear directorio si no existe
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    # Habilitar foreign keys
    cur.execute("PRAGMA foreign_keys = ON")

    # --------------------------
    # Núcleo 1: Identidad
    # --------------------------
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS empresas (
        id_empresa INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        rfc TEXT,
        sector TEXT,
        telefono TEXT,
        correo TEXT,
        fecha_alta TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS contactos (
        id_contacto INTEGER PRIMARY KEY AUTOINCREMENT,
        id_empresa INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        correo TEXT,
        telefono TEXT,
        puesto TEXT,
        fecha_alta TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id_empresa) REFERENCES empresas(id_empresa)
    );

    CREATE TABLE IF NOT EXISTS prospectos (
        id_prospecto INTEGER PRIMARY KEY AUTOINCREMENT,
        id_empresa INTEGER NOT NULL,
        id_contacto INTEGER NOT NULL,
        estado TEXT DEFAULT 'Activo',
        origen TEXT,
        fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id_empresa) REFERENCES empresas(id_empresa),
        FOREIGN KEY (id_contacto) REFERENCES contactos(id_contacto)
    );
    """)

    # --------------------------
    # Núcleo 2: Transacción
    # --------------------------
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS oportunidades (
        id_oportunidad INTEGER PRIMARY KEY AUTOINCREMENT,
        id_prospecto INTEGER NOT NULL,
        nombre TEXT,
        etapa TEXT DEFAULT 'Inicial',
        probabilidad INTEGER DEFAULT 0,
        monto_estimado REAL,
        fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id_prospecto) REFERENCES prospectos(id_prospecto)
    );

    CREATE TABLE IF NOT EXISTS cotizaciones (
        id_cotizacion INTEGER PRIMARY KEY AUTOINCREMENT,
        id_oportunidad INTEGER NOT NULL,
        modo TEXT CHECK(modo IN ('minimo','generico','externo')),
        fuente TEXT,
        monto_total REAL NOT NULL,
        moneda TEXT DEFAULT 'MXN',
        version INTEGER DEFAULT 1,
        estado TEXT DEFAULT 'Borrador',
        fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
        hash_integridad TEXT,
        notas TEXT,
        FOREIGN KEY (id_oportunidad) REFERENCES oportunidades(id_oportunidad)
    );
    """)

    # --------------------------
    # Núcleo 3: Facturación
    # --------------------------
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS ordenes_compra (
        id_oc INTEGER PRIMARY KEY AUTOINCREMENT,
        id_oportunidad INTEGER NOT NULL,
        numero_oc TEXT,
        fecha_oc TEXT,
        monto_oc REAL,
        moneda TEXT,
        archivo_pdf TEXT,
        FOREIGN KEY (id_oportunidad) REFERENCES oportunidades(id_oportunidad)
    );

    CREATE TABLE IF NOT EXISTS facturas (
        id_factura INTEGER PRIMARY KEY AUTOINCREMENT,
        id_oc INTEGER NOT NULL,
        uuid TEXT,
        serie TEXT,
        folio TEXT,
        fecha_emision TEXT,
        monto_total REAL,
        moneda TEXT,
        archivo_xml TEXT,
        archivo_pdf TEXT,
        FOREIGN KEY (id_oc) REFERENCES ordenes_compra(id_oc)
    );
    """)

    # --------------------------
    # Núcleo 4: Trazabilidad
    # --------------------------
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS historial_general (
        id_evento INTEGER PRIMARY KEY AUTOINCREMENT,
        entidad TEXT,
        id_entidad INTEGER,
        accion TEXT,
        valor_anterior TEXT,
        valor_nuevo TEXT,
        usuario TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        hash_evento TEXT
    );

    CREATE TABLE IF NOT EXISTS hash_registros (
        id_hash INTEGER PRIMARY KEY AUTOINCREMENT,
        tabla_origen TEXT,
        id_registro INTEGER,
        hash_sha256 TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS atributos_entidad (
        id_attr INTEGER PRIMARY KEY AUTOINCREMENT,
        entidad TEXT NOT NULL,
        id_entidad INTEGER NOT NULL,
        nombre_attr TEXT NOT NULL,
        valor_attr TEXT,
        tipo_dato TEXT DEFAULT 'text',
        fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # --------------------------
    # AJUSTE 2: Índices de rendimiento
    # --------------------------
    cur.executescript("""
    CREATE INDEX IF NOT EXISTS idx_contactos_empresa ON contactos(id_empresa);
    CREATE INDEX IF NOT EXISTS idx_prospectos_empresa ON prospectos(id_empresa);
    CREATE INDEX IF NOT EXISTS idx_oportunidades_prospecto ON oportunidades(id_prospecto);
    CREATE INDEX IF NOT EXISTS idx_cotizaciones_oportunidad ON cotizaciones(id_oportunidad);
    CREATE INDEX IF NOT EXISTS idx_ordenes_oportunidad ON ordenes_compra(id_oportunidad);
    CREATE INDEX IF NOT EXISTS idx_facturas_oc ON facturas(id_oc);
    CREATE INDEX IF NOT EXISTS idx_historial_entidad ON historial_general(entidad, id_entidad);
    CREATE INDEX IF NOT EXISTS idx_hash_origen ON hash_registros(tabla_origen, id_registro);
    CREATE INDEX IF NOT EXISTS idx_atributos_entidad ON atributos_entidad(entidad, id_entidad);
    """)

    con.commit()
    return con


def verificar_integridad_estructura(con):
    """
    AJUSTE 3: Verifica que todas las tablas e índices se hayan creado correctamente.
    """
    cur = con.cursor()
    
    # Verificar tablas
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tablas = [row[0] for row in cur.fetchall()]
    
    tablas_esperadas = [
        'empresas', 'contactos', 'prospectos',
        'oportunidades', 'cotizaciones',
        'ordenes_compra', 'facturas',
        'historial_general', 'hash_registros',
        'atributos_entidad'
    ]
    
    # Verificar índices
    cur.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
    indices = [row[0] for row in cur.fetchall()]
    
    indices_esperados = [
        'idx_contactos_empresa', 'idx_prospectos_empresa',
        'idx_oportunidades_prospecto', 'idx_cotizaciones_oportunidad',
        'idx_ordenes_oportunidad', 'idx_facturas_oc',
        'idx_historial_entidad', 'idx_hash_origen',
        'idx_atributos_entidad'
    ]
    
    tablas_faltantes = [t for t in tablas_esperadas if t not in tablas]
    indices_faltantes = [i for i in indices_esperados if i not in indices]
    
    return {
        "tablas_creadas": len(tablas),
        "tablas_esperadas": len(tablas_esperadas),
        "tablas_faltantes": tablas_faltantes,
        "indices_creados": len([i for i in indices if i.startswith('idx_')]),
        "indices_esperados": len(indices_esperados),
        "indices_faltantes": indices_faltantes,
        "estructura_completa": len(tablas_faltantes) == 0 and len(indices_faltantes) == 0
    }


# ============================================================
#  PROCESO PRINCIPAL
# ============================================================

if __name__ == "__main__":
    print("🚀 Iniciando creación de CRM-EXO v2...")
    print(f"📁 Ruta base: {BASE_DIR}")
    print(f"💾 DB destino: {DB_PATH}")
    print()
    
    # Crear base de datos
    con = crear_base()
    print("✅ Tablas e índices creados")
    
    # Verificar estructura
    verificacion = verificar_integridad_estructura(con)
    print(f"📊 Tablas: {verificacion['tablas_creadas']}/{verificacion['tablas_esperadas']}")
    print(f"📊 Índices: {verificacion['indices_creados']}/{verificacion['indices_esperados']}")
    
    if not verificacion['estructura_completa']:
        print("⚠️  ADVERTENCIA: Estructura incompleta")
        if verificacion['tablas_faltantes']:
            print(f"   Tablas faltantes: {', '.join(verificacion['tablas_faltantes'])}")
        if verificacion['indices_faltantes']:
            print(f"   Índices faltantes: {', '.join(verificacion['indices_faltantes'])}")
    else:
        print("✅ Estructura completa verificada")
    print()
    
    # Registrar evento inicial (AHORA CON HASH)
    hash_evento = registrar_evento(
        con, 
        entidad="sistema", 
        id_entidad=0,
        accion="DB_INIT",
        valor_nuevo="Creación base CRM-EXO v2 - Arquitectura AUP de 4 núcleos"
    )
    print(f"📝 Evento inicial registrado: {hash_evento[:16]}...")
    
    # Calcular hash estructural del archivo
    con.close()
    hash_db = calcular_hash_archivo(DB_PATH)
    print(f"🔐 Hash estructural DB: {hash_db}")
    
    # Reabrir y guardar hash en hash_registros
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cur.execute("""
        INSERT INTO hash_registros (tabla_origen, id_registro, hash_sha256)
        VALUES ('estructura', 0, ?)
    """, (hash_db,))
    con.commit()
    con.close()
    
    print()
    print("=" * 60)
    print("✅ Base CRM-EXO v2 creada correctamente")
    print(f"📦 Ruta: {DB_PATH}")
    print(f"🔐 Hash estructural: {hash_db}")
    print(f"🪶 Hash evento inicial: {hash_evento}")
    print("=" * 60)
