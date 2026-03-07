# ================================================================
#  app_crm_exo_v2.py  |  CRM-EXO v2  (Aplicación Principal)
#  ---------------------------------------------------------------
#  Interfaz Streamlit unificada con flujo comercial completo:
#  Empresa → Contacto → Prospecto → Oportunidad → Cotización → 
#  Cliente → OC → Factura → Trazabilidad
# ================================================================

import streamlit as st
import sqlite3
import hashlib
from datetime import datetime, date
import pandas as pd
from pathlib import Path
from decimal import Decimal
import sys

# Ruta relativa desde raíz del proyecto
BASE_DIR = Path(__file__).parent

# Agregar rutas para imports de módulos internos
sys.path.insert(0, str(BASE_DIR / "crm_exo_v2" / "core"))
sys.path.insert(0, str(BASE_DIR / "crm_exo_v2" / "ui"))

from db_runtime import get_legacy_app_backend, get_legacy_app_backend_status, get_sqlite_db_path

DB_PATH = get_sqlite_db_path(BASE_DIR)

# Importar módulos de facturación CFDI
try:
    from ui_cfdi_emisor import ui_registro_emisor, widget_estado_cfdi
    from facturacion.cfdi_emisor import validar_configuracion_cfdi, obtener_configuracion_emisor
    CFDI_DISPONIBLE = True
except ImportError as e:
    CFDI_DISPONIBLE = False
    print(f"⚠️ Módulo CFDI no disponible: {e}")


APP_DB_BACKEND = get_legacy_app_backend()
APP_DB_BACKEND_STATUS = get_legacy_app_backend_status()

# Futuro helper interno entre etapas:
# - Deterministico y auditable, sin depender de LLM.
# - Debe evaluar completitud, tiempo transcurrido y bloqueos por etapa.
# - Debe emitir siguiente paso recomendado, riesgo y accion sugerida.
# - La fuente base deben ser estados, timestamps y validaciones del flujo.
ROI_BASELINE_HOURS = {
    "Prospecto a oportunidad": 48.0,
    "Oportunidad a OC": 120.0,
    "OC a factura": 24.0,
    "Prospecto a cliente": 168.0,
}


def obtener_metricas_helper(con):
    metricas = {}
    metricas["empresas_sin_contacto"] = int(pd.read_sql("""
        SELECT COUNT(*) AS total
        FROM empresas e
        LEFT JOIN contactos c ON c.id_empresa = e.id_empresa
        WHERE c.id_contacto IS NULL
    """, con).iloc[0]["total"])
    metricas["prospectos_sin_oportunidad"] = int(pd.read_sql("""
        SELECT COUNT(*) AS total
        FROM prospectos p
        LEFT JOIN oportunidades o ON o.id_prospecto = p.id_prospecto
        WHERE p.es_cliente = 0 AND o.id_oportunidad IS NULL
    """, con).iloc[0]["total"])
    metricas["oportunidades_sin_cotizacion"] = int(pd.read_sql("""
        SELECT COUNT(*) AS total
        FROM oportunidades o
        LEFT JOIN cotizaciones c ON c.id_oportunidad = o.id_oportunidad
        WHERE o.etapa NOT IN ('Ganada', 'Perdida') AND c.id_cotizacion IS NULL
    """, con).iloc[0]["total"])
    metricas["ganadas_sin_oc"] = int(pd.read_sql("""
        SELECT COUNT(*) AS total
        FROM oportunidades o
        LEFT JOIN ordenes_compra oc ON oc.id_oportunidad = o.id_oportunidad
        WHERE o.etapa = 'Ganada' AND o.oc_recibida = 1 AND oc.id_oc IS NULL
    """, con).iloc[0]["total"])
    metricas["ocs_sin_factura"] = int(pd.read_sql("""
        SELECT COUNT(*) AS total
        FROM ordenes_compra oc
        LEFT JOIN facturas f ON f.id_oc = oc.id_oc
        WHERE f.id_factura IS NULL
    """, con).iloc[0]["total"])
    metricas["oportunidades_estancadas"] = int(pd.read_sql("""
        SELECT COUNT(*) AS total
        FROM oportunidades o
        WHERE o.etapa NOT IN ('Ganada', 'Perdida')
          AND julianday('now') - julianday(o.fecha_creacion) >= 14
    """, con).iloc[0]["total"])
    return metricas


def construir_recomendaciones_helper(metricas, cfdi_valido):
    recomendaciones = []

    if metricas["empresas_sin_contacto"] > 0:
        recomendaciones.append({
            "prioridad": "Alta",
            "mensaje": f"Hay {metricas['empresas_sin_contacto']} empresa(s) sin contacto. Sin contacto no deberian entrar al flujo comercial.",
            "riesgo": "Bloqueo en identidad",
            "menu": "🏗️ N1: Identidad",
            "accion": "Completar contactos",
        })

    if metricas["prospectos_sin_oportunidad"] > 0:
        recomendaciones.append({
            "prioridad": "Alta",
            "mensaje": f"Hay {metricas['prospectos_sin_oportunidad']} prospecto(s) sin oportunidad. El pipeline se queda sin siguiente paso comercial.",
            "riesgo": "Estancamiento comercial",
            "menu": "💼 N2: Transacción",
            "accion": "Abrir oportunidades",
        })

    if metricas["oportunidades_sin_cotizacion"] > 0:
        recomendaciones.append({
            "prioridad": "Media",
            "mensaje": f"Hay {metricas['oportunidades_sin_cotizacion']} oportunidad(es) activas sin cotización.",
            "riesgo": "Baja trazabilidad de propuesta",
            "menu": "💼 N2: Transacción",
            "accion": "Generar cotizaciones",
        })

    if metricas["ganadas_sin_oc"] > 0:
        recomendaciones.append({
            "prioridad": "Alta",
            "mensaje": f"Hay {metricas['ganadas_sin_oc']} oportunidad(es) ganadas con OC marcada pero sin registro de orden de compra.",
            "riesgo": "No se puede facturar",
            "menu": "💰 N3: Facturación",
            "accion": "Registrar OCs",
        })

    if metricas["ocs_sin_factura"] > 0:
        recomendaciones.append({
            "prioridad": "Alta",
            "mensaje": f"Hay {metricas['ocs_sin_factura']} OC(s) sin factura. Existe valor cerrado sin salida fiscal completa.",
            "riesgo": "Retraso de ingreso y trazabilidad",
            "menu": "💰 N3: Facturación",
            "accion": "Emitir o registrar facturas",
        })

    if metricas["oportunidades_estancadas"] > 0:
        recomendaciones.append({
            "prioridad": "Media",
            "mensaje": f"Hay {metricas['oportunidades_estancadas']} oportunidad(es) activas con 14 o más días sin cierre.",
            "riesgo": "Desgaste comercial",
            "menu": "💼 N2: Transacción",
            "accion": "Revisar estancamiento",
        })

    if CFDI_DISPONIBLE and not cfdi_valido:
        recomendaciones.append({
            "prioridad": "Alta",
            "mensaje": "La configuración CFDI no está completa. Aunque el flujo comercial avance, la facturación queda limitada.",
            "riesgo": "Bloqueo fiscal",
            "menu": "⚙️ Configuración CFDI",
            "accion": "Configurar CFDI",
        })

    if not recomendaciones:
        recomendaciones.append({
            "prioridad": "OK",
            "mensaje": "El flujo no muestra bloqueos estructurales inmediatos. El siguiente paso es sostener velocidad y trazabilidad.",
            "riesgo": "Operación sana",
            "menu": "📊 Pipeline Visual",
            "accion": "Monitorear",
        })

    return recomendaciones


def obtener_scores_oportunidad(con):
    oportunidades = pd.read_sql("""
        SELECT
            o.id_oportunidad,
            e.nombre AS empresa,
            o.nombre AS oportunidad,
            o.etapa,
            o.probabilidad,
            ROUND(COALESCE(o.monto_estimado, 0), 2) AS monto_estimado,
            COALESCE(o.oc_recibida, 0) AS oc_recibida,
            ROUND(julianday('now') - julianday(o.fecha_creacion), 1) AS dias_abierta,
            COUNT(DISTINCT c.id_cotizacion) AS cotizaciones,
            COUNT(DISTINCT oc.id_oc) AS ocs,
            COUNT(DISTINCT f.id_factura) AS facturas
        FROM oportunidades o
        JOIN prospectos p ON p.id_prospecto = o.id_prospecto
        JOIN empresas e ON e.id_empresa = p.id_empresa
        LEFT JOIN cotizaciones c ON c.id_oportunidad = o.id_oportunidad
        LEFT JOIN ordenes_compra oc ON oc.id_oportunidad = o.id_oportunidad
        LEFT JOIN facturas f ON f.id_oc = oc.id_oc
        GROUP BY o.id_oportunidad, e.nombre, o.nombre, o.etapa, o.probabilidad, o.monto_estimado, o.oc_recibida, o.fecha_creacion
        ORDER BY o.fecha_creacion DESC
    """, con)

    if len(oportunidades) == 0:
        return oportunidades

    def evaluar(row):
        score = 100
        hallazgos = []
        menu = "💼 N2: Transacción"
        accion = "Revisar oportunidad"

        if row["cotizaciones"] == 0 and row["etapa"] not in ("Ganada", "Perdida"):
            score -= 25
            hallazgos.append("sin cotización")
            accion = "Generar cotización"

        if row["probabilidad"] >= 70 and row["cotizaciones"] == 0 and row["etapa"] not in ("Ganada", "Perdida"):
            score -= 10
            hallazgos.append("alta probabilidad sin propuesta formal")

        if row["dias_abierta"] >= 14 and row["etapa"] not in ("Ganada", "Perdida"):
            score -= 20
            hallazgos.append("estancada")
            accion = "Revisar seguimiento"

        if row["etapa"] == "Ganada" and row["oc_recibida"] == 0:
            score -= 25
            hallazgos.append("ganada sin OC recibida")
            accion = "Marcar OC recibida"

        if row["etapa"] == "Ganada" and row["oc_recibida"] == 1 and row["ocs"] == 0:
            score -= 35
            hallazgos.append("sin OC registrada")
            menu = "💰 N3: Facturación"
            accion = "Registrar OC"

        if row["ocs"] > 0 and row["facturas"] == 0:
            score -= 25
            hallazgos.append("sin factura")
            menu = "💰 N3: Facturación"
            accion = "Registrar factura"

        if row["facturas"] > 0:
            score = min(100, score + 5)
            hallazgos.append("salida fiscal completada")
            menu = "💰 N3: Facturación"
            accion = "Monitorear cierre"

        score = max(score, 0)

        if score >= 85:
            salud = "Sana"
            prioridad = "Baja"
        elif score >= 60:
            salud = "Atencion"
            prioridad = "Media"
        else:
            salud = "Critica"
            prioridad = "Alta"

        return pd.Series({
            "score_flujo": score,
            "salud_flujo": salud,
            "prioridad": prioridad,
            "hallazgos": ", ".join(hallazgos) if hallazgos else "sin bloqueos relevantes",
            "accion_sugerida": accion,
            "menu_sugerido": menu,
        })

    evaluacion = oportunidades.apply(evaluar, axis=1)
    oportunidades = pd.concat([oportunidades, evaluacion], axis=1)
    return oportunidades.sort_values(["score_flujo", "dias_abierta", "probabilidad"], ascending=[True, False, False])

def enriquecer_scores_con_historial(con, score_df):
    if len(score_df) == 0:
        return score_df

    historico = pd.read_sql("""
        SELECT s.id_oportunidad, s.score_flujo AS score_anterior, s.fecha_snapshot
        FROM pipeline_helper_oportunidad_snapshots s
        INNER JOIN (
            SELECT id_oportunidad, MAX(fecha_snapshot) AS fecha_snapshot
            FROM pipeline_helper_oportunidad_snapshots
            WHERE fecha_snapshot < date('now')
            GROUP BY id_oportunidad
        ) prev
            ON prev.id_oportunidad = s.id_oportunidad
           AND prev.fecha_snapshot = s.fecha_snapshot
    """, con)

    if len(historico) == 0:
        score_df["score_anterior"] = None
        score_df["delta_score"] = None
        return score_df

    score_df = score_df.merge(historico[["id_oportunidad", "score_anterior"]], on="id_oportunidad", how="left")
    score_df["delta_score"] = score_df["score_flujo"] - score_df["score_anterior"]
    return score_df


def persistir_scores_oportunidad(con, score_df):
    if len(score_df) == 0:
        return

    snapshot_date = date.today().isoformat()
    payload = [
        (
            int(row["id_oportunidad"]),
            snapshot_date,
            int(row["score_flujo"]),
            str(row["salud_flujo"]),
            str(row["prioridad"]),
            str(row["accion_sugerida"]),
            str(row["hallazgos"]),
        )
        for _, row in score_df.iterrows()
    ]

    con.executemany(
        """
        INSERT INTO pipeline_helper_oportunidad_snapshots (
            id_oportunidad, fecha_snapshot, score_flujo, salud_flujo,
            prioridad, accion_sugerida, hallazgos
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id_oportunidad, fecha_snapshot) DO UPDATE SET
            score_flujo = excluded.score_flujo,
            salud_flujo = excluded.salud_flujo,
            prioridad = excluded.prioridad,
            accion_sugerida = excluded.accion_sugerida,
            hallazgos = excluded.hallazgos,
            actualizado_en = CURRENT_TIMESTAMP
        """,
        payload,
    )
    con.commit()


# ================================================================
#  INICIALIZACIÓN Y CONEXIÓN
# ================================================================

def inicializar_db():
    """Crea la base de datos si no existe"""
    if APP_DB_BACKEND != "sqlite":
        return

    if DB_PATH.exists():
        return
    
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    
    # Ejecutar schema completo
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
        es_cliente INTEGER DEFAULT 0,
        fecha_conversion_cliente TEXT,
        fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id_empresa) REFERENCES empresas(id_empresa),
        FOREIGN KEY (id_contacto) REFERENCES contactos(id_contacto)
    );

    CREATE TABLE IF NOT EXISTS oportunidades (
        id_oportunidad INTEGER PRIMARY KEY AUTOINCREMENT,
        id_prospecto INTEGER NOT NULL,
        nombre TEXT,
        etapa TEXT DEFAULT 'Calificación',
        probabilidad INTEGER DEFAULT 0,
        monto_estimado REAL,
        oc_recibida INTEGER DEFAULT 0,
        fecha_estimada_cierre TEXT,
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

    CREATE TABLE IF NOT EXISTS pipeline_helper_oportunidad_snapshots (
        id_snapshot INTEGER PRIMARY KEY AUTOINCREMENT,
        id_oportunidad INTEGER NOT NULL,
        fecha_snapshot TEXT NOT NULL,
        score_flujo INTEGER NOT NULL,
        salud_flujo TEXT NOT NULL,
        prioridad TEXT NOT NULL,
        accion_sugerida TEXT,
        hallazgos TEXT,
        creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
        actualizado_en TEXT,
        UNIQUE(id_oportunidad, fecha_snapshot),
        FOREIGN KEY (id_oportunidad) REFERENCES oportunidades(id_oportunidad)
    );

    CREATE INDEX IF NOT EXISTS idx_contactos_empresa ON contactos(id_empresa);
    CREATE INDEX IF NOT EXISTS idx_prospectos_empresa ON prospectos(id_empresa);
    CREATE INDEX IF NOT EXISTS idx_oportunidades_prospecto ON oportunidades(id_prospecto);
    CREATE INDEX IF NOT EXISTS idx_cotizaciones_oportunidad ON cotizaciones(id_oportunidad);
    CREATE INDEX IF NOT EXISTS idx_ordenes_oportunidad ON ordenes_compra(id_oportunidad);
    CREATE INDEX IF NOT EXISTS idx_facturas_oc ON facturas(id_oc);
    CREATE INDEX IF NOT EXISTS idx_historial_entidad ON historial_general(entidad, id_entidad);
    CREATE INDEX IF NOT EXISTS idx_hash_origen ON hash_registros(tabla_origen, id_registro);
    CREATE INDEX IF NOT EXISTS idx_helper_snapshot_oportunidad ON pipeline_helper_oportunidad_snapshots(id_oportunidad, fecha_snapshot);
    """)
    
    con.commit()
    con.close()


def conectar():
    if APP_DB_BACKEND != "sqlite":
        raise RuntimeError(
            "La app actual solo puede usar PostgreSQL cuando exista el esquema legado. "
            "Hoy se debe ejecutar en SQLite hasta completar la migracion de app/repositorios."
        )

    inicializar_db()
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def registrar_evento(con, entidad, id_entidad, accion, valor_nuevo, usuario="ui"):
    """Registra evento con hash forense"""
    ts = datetime.now().isoformat()
    raw = f"{entidad}|{accion}|{valor_nuevo}|{ts}"
    h = hashlib.sha256(raw.encode()).hexdigest()
    con.execute("""
        INSERT INTO historial_general
        (entidad, id_entidad, accion, valor_nuevo, usuario, timestamp, hash_evento)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (entidad, id_entidad, accion, valor_nuevo, usuario, ts, h))
    con.commit()
    return h


# ================================================================
#  CONFIGURACIÓN DE LA APLICACIÓN
# ================================================================

st.set_page_config(
    page_title="CRM-EXO v2 - Sistema Completo",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar base de datos al arrancar la aplicación
inicializar_db()
# Aplicar migraciones pendientes en bases existentes (columnas nuevas, etc.)
def aplicar_migraciones():
    """Revisa y aplica pequeñas migraciones necesarias en bases existentes.
    Mantener aquí los ALTER TABLE seguros que agregan columnas con DEFAULT.
    """
    if APP_DB_BACKEND != "sqlite":
        return

    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()

    def _column_exists(table: str, column: str) -> bool:
        cur.execute(f"PRAGMA table_info({table})")
        rows = cur.fetchall()
        cols = [r[1] for r in rows]
        return column in cols

    # Asegurar columna es_cliente en prospectos (agregada en versiones recientes)
    try:
        if not _column_exists('prospectos', 'es_cliente'):
            cur.execute("ALTER TABLE prospectos ADD COLUMN es_cliente INTEGER DEFAULT 0")
            con.commit()
        
        if not _column_exists('prospectos', 'fecha_conversion_cliente'):
            cur.execute("ALTER TABLE prospectos ADD COLUMN fecha_conversion_cliente TEXT")
            con.commit()
        
        # Asegurar columna oc_recibida en oportunidades
        if not _column_exists('oportunidades', 'oc_recibida'):
            cur.execute("ALTER TABLE oportunidades ADD COLUMN oc_recibida INTEGER DEFAULT 0")
            con.commit()
        
        if not _column_exists('oportunidades', 'fecha_estimada_cierre'):
            cur.execute("ALTER TABLE oportunidades ADD COLUMN fecha_estimada_cierre TEXT")
            con.commit()
        
        # ========== MIGRACIÓN: Tablas de Configuración CFDI (Nov 2025) ==========
        # Crear tablas para configuración de facturación electrónica si no existen
        cur.execute("""
            CREATE TABLE IF NOT EXISTS config_cfdi_emisor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfc_emisor TEXT NOT NULL UNIQUE,
                razon_social TEXT,
                regimen_fiscal TEXT,
                token_api TEXT NOT NULL,
                modo TEXT NOT NULL CHECK(modo IN ('pruebas', 'produccion')),
                fecha_registro TEXT NOT NULL,
                fecha_actualizacion TEXT,
                activo INTEGER DEFAULT 1
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS config_cfdi_certificados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_emisor INTEGER NOT NULL,
                cer_base64 TEXT NOT NULL,
                key_base64 TEXT NOT NULL,
                numero_certificado TEXT,
                fecha_inicio_vigencia TEXT,
                fecha_fin_vigencia TEXT,
                fecha_carga TEXT NOT NULL,
                activo INTEGER DEFAULT 1,
                FOREIGN KEY (id_emisor) REFERENCES config_cfdi_emisor(id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_helper_oportunidad_snapshots (
                id_snapshot INTEGER PRIMARY KEY AUTOINCREMENT,
                id_oportunidad INTEGER NOT NULL,
                fecha_snapshot TEXT NOT NULL,
                score_flujo INTEGER NOT NULL,
                salud_flujo TEXT NOT NULL,
                prioridad TEXT NOT NULL,
                accion_sugerida TEXT,
                hallazgos TEXT,
                creado_en TEXT DEFAULT CURRENT_TIMESTAMP,
                actualizado_en TEXT,
                UNIQUE(id_oportunidad, fecha_snapshot)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_helper_snapshot_oportunidad ON pipeline_helper_oportunidad_snapshots(id_oportunidad, fecha_snapshot)")
        con.commit()
            
    except Exception:
        # No hacemos fail-hard: registramos y seguimos (Streamlit ocultará detalles en producción)
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
    finally:
        con.close()

aplicar_migraciones()

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .flow-step {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        text-align: center;
        font-weight: bold;
    }
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)


# ================================================================
#  SIDEBAR - NAVEGACIÓN
# ================================================================

with st.sidebar:
    st.markdown("### 🚀 CRM-EXO v2")
    st.markdown("**Arquitectura AUP de 4 núcleos**")
    if APP_DB_BACKEND == "sqlite":
        if APP_DB_BACKEND_STATUS == "postgres-configured-schema-incompatible":
            st.caption("DB runtime: SQLite (DATABASE_URL detectado, esquema legado no compatible)")
        else:
            st.caption("DB runtime: SQLite")
    else:
        st.caption("DB runtime: PostgreSQL")
    st.divider()
    
    if 'menu_redireccion_pendiente' in st.session_state:
        st.session_state.menu_seleccionado = st.session_state.pop('menu_redireccion_pendiente')

    # Inicializar menu en session_state si no existe
    if 'menu_seleccionado' not in st.session_state:
        st.session_state.menu_seleccionado = "🏠 Dashboard"
    
    menu = st.radio(
        "Navegación:",
        [
            "🏠 Dashboard",
            "🏗️ N1: Identidad",
            "💼 N2: Transacción",
            "💰 N3: Facturación",
            "🪶 N4: Trazabilidad",
            "📊 Pipeline Visual",
            "⚙️ Configuración CFDI"
        ],
        key='menu_seleccionado'
    )
    
    st.divider()
    
    # Mostrar estado CFDI en sidebar
    if CFDI_DISPONIBLE:
        try:
            valido_cfdi, _ = validar_configuracion_cfdi()
            if valido_cfdi:
                config_emisor = obtener_configuracion_emisor()
                st.success(f"🔐 CFDI: {config_emisor['rfc'][:6]}...")
            else:
                st.warning("⚠️ CFDI no configurado")
        except Exception:
            pass
        st.divider()
    
    # Mostrar flujo estructural
    st.markdown("**Flujo Comercial:**")
    st.markdown("""
    1. 🏢 Empresa
    2. 👤 Contacto
    3. 📈 Prospecto
    4. 🎯 Oportunidad
    5. 💰 Cotización
    6. ✅ Cliente (ganada)
    7. 🧾 OC
    8. 📄 Factura
    9. 🪶 Trazabilidad
    """)


# ================================================================
#  DASHBOARD PRINCIPAL
# ================================================================

if menu == "🏠 Dashboard":
    st.markdown('<div class="main-header">🏠 Dashboard CRM-EXO v2</div>', unsafe_allow_html=True)
    
    con = conectar()
    
    # Métricas principales con manejo de errores
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        with col1:
            total_empresas = pd.read_sql("SELECT COUNT(*) as total FROM empresas", con).iloc[0]["total"]
            st.metric("🏢 Empresas", total_empresas)
        
        with col2:
            total_prospectos = pd.read_sql("SELECT COUNT(*) as total FROM prospectos WHERE es_cliente=0", con).iloc[0]["total"]
            st.metric("📈 Prospectos", total_prospectos)
        
        with col3:
            total_oportunidades = pd.read_sql("SELECT COUNT(*) as total FROM oportunidades WHERE etapa NOT IN ('Ganada','Perdida')", con).iloc[0]["total"]
            st.metric("🎯 Oportunidades", total_oportunidades)
        
        with col4:
            total_clientes = pd.read_sql("SELECT COUNT(*) as total FROM prospectos WHERE es_cliente=1", con).iloc[0]["total"]
            st.metric("✅ Clientes", total_clientes)
    
    except Exception as e:
        st.error(f"❌ Error al cargar métricas del dashboard. Por favor contacta al administrador.")
        # Log completo para debugging (se guarda en logs de Streamlit Cloud)
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        st.stop()
    
    st.divider()
    
    # Widget de estado CFDI
    if CFDI_DISPONIBLE:
        try:
            widget_estado_cfdi()
            st.divider()
        except Exception:
            pass  # Si falla el widget, no romper el dashboard
    
    # Pipeline por etapa
    st.subheader("📊 Pipeline de Oportunidades")
    
    pipeline = pd.read_sql("""
        SELECT 
            o.etapa,
            COUNT(*) as cantidad,
            ROUND(SUM(o.monto_estimado), 2) as monto_total,
            ROUND(AVG(o.probabilidad), 1) as prob_promedio
        FROM oportunidades o
        WHERE o.etapa NOT IN ('Perdida')
        GROUP BY o.etapa
        ORDER BY 
            CASE o.etapa
                WHEN 'Calificación' THEN 1
                WHEN 'Propuesta' THEN 2
                WHEN 'Negociación' THEN 3
                WHEN 'Cierre' THEN 4
                WHEN 'Ganada' THEN 5
            END
    """, con)
    
    if len(pipeline) > 0:
        col_pipe1, col_pipe2 = st.columns(2)
        
        with col_pipe1:
            st.dataframe(
                pipeline,
                width="stretch",
                column_config={
                    "etapa": "Etapa",
                    "cantidad": st.column_config.NumberColumn("Cantidad", format="%d"),
                    "monto_total": st.column_config.NumberColumn("Monto Total", format="$%.2f"),
                    "prob_promedio": st.column_config.NumberColumn("Prob. Promedio", format="%.1f%%")
                }
            )
        
        with col_pipe2:
            # Gráfico simple de barras con st.bar_chart
            chart_data = pipeline.set_index('etapa')['monto_total']
            st.bar_chart(chart_data)
    else:
        st.info("No hay oportunidades activas. Crea la primera en N2: Transacción")
    
    st.divider()
    
    # Últimas actividades
    col_act1, col_act2 = st.columns(2)
    
    with col_act1:
        st.subheader("📋 Últimos Prospectos")
        prospectos_recientes = pd.read_sql("""
            SELECT p.id_prospecto, e.nombre as empresa, c.nombre as contacto,
                   p.estado, p.fecha_creacion
            FROM prospectos p
            JOIN empresas e ON e.id_empresa = p.id_empresa
            JOIN contactos c ON c.id_contacto = p.id_contacto
            WHERE p.es_cliente = 0
            ORDER BY p.fecha_creacion DESC
            LIMIT 5
        """, con)
        
        if len(prospectos_recientes) > 0:
            st.dataframe(prospectos_recientes, width="stretch", hide_index=True)
        else:
            st.info("No hay prospectos registrados")
    
    with col_act2:
        st.subheader("🎯 Oportunidades Activas")
        opor_activas = pd.read_sql("""
            SELECT o.id_oportunidad, o.nombre, o.etapa, o.probabilidad,
                   ROUND(o.monto_estimado, 2) as monto
            FROM oportunidades o
            WHERE o.etapa NOT IN ('Ganada', 'Perdida')
            ORDER BY o.probabilidad DESC, o.monto_estimado DESC
            LIMIT 5
        """, con)
        
        if len(opor_activas) > 0:
            st.dataframe(opor_activas, width="stretch", hide_index=True)
        else:
            st.info("No hay oportunidades activas")
    
    con.close()


# ================================================================
#  N1: IDENTIDAD (Empresas → Contactos → Prospectos)
# ================================================================

elif menu == "🏗️ N1: Identidad":
    st.markdown('<div class="main-header">🏗️ Núcleo 1: Identidad</div>', unsafe_allow_html=True)
    st.markdown("**Flujo:** Empresa → Contacto → Prospecto")
    
    tab1, tab2, tab3 = st.tabs(["🏢 Empresas", "👤 Contactos", "📈 Prospectos"])
    
    # TAB: Empresas
    with tab1:
        st.subheader("Gestión de Empresas")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            with st.form("form_empresa"):
                nombre = st.text_input("Nombre *", placeholder="Ej: ACME Corp")
                rfc = st.text_input("RFC", placeholder="ACM123456ABC")
                sector = st.text_input("Sector", placeholder="Tecnología")
                telefono = st.text_input("Teléfono")
                correo = st.text_input("Correo")
                submit = st.form_submit_button("✅ Registrar Empresa")
            
            if submit and nombre:
                con = conectar()
                cur = con.cursor()
                cur.execute("SELECT COUNT(*) as total FROM empresas WHERE LOWER(nombre) = LOWER(?)", (nombre,))
                if cur.fetchone()["total"] > 0:
                    st.error(f"❌ Ya existe '{nombre}'")
                else:
                    cur.execute("INSERT INTO empresas (nombre, rfc, sector, telefono, correo) VALUES (?, ?, ?, ?, ?)",
                               (nombre, rfc, sector, telefono, correo))
                    con.commit()
                    registrar_evento(con, "empresa", cur.lastrowid, "CREAR", f"Empresa: {nombre}")
                    st.success(f"✅ Empresa '{nombre}' creada")
                    st.rerun()
                con.close()
        
        with col2:
            con = conectar()
            empresas = pd.read_sql("""
                SELECT e.id_empresa, e.nombre, e.rfc, e.sector,
                       COUNT(c.id_contacto) as contactos
                FROM empresas e
                LEFT JOIN contactos c ON c.id_empresa = e.id_empresa
                GROUP BY e.id_empresa
                ORDER BY e.fecha_alta DESC
            """, con)
            con.close()
            
            if len(empresas) > 0:
                st.dataframe(empresas, width="stretch", hide_index=True)
            else:
                st.info("No hay empresas registradas")
    
    # TAB: Contactos
    with tab2:
        st.subheader("Gestión de Contactos")
        
        con = conectar()
        empresas_list = pd.read_sql("SELECT id_empresa, nombre FROM empresas ORDER BY nombre", con)
        con.close()
        
        if len(empresas_list) == 0:
            st.warning("⚠️ Primero registra una empresa")
        else:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                with st.form("form_contacto"):
                    empresa_sel = st.selectbox("Empresa *", empresas_list["nombre"].tolist())
                    id_empresa = int(empresas_list[empresas_list["nombre"]==empresa_sel]["id_empresa"].iloc[0])
                    nombre_c = st.text_input("Nombre *", placeholder="Juan Pérez")
                    correo_c = st.text_input("Correo *", placeholder="juan@empresa.com")
                    telefono_c = st.text_input("Teléfono")
                    puesto_c = st.text_input("Puesto")
                    submit_c = st.form_submit_button("✅ Registrar Contacto")
                
                if submit_c and nombre_c and correo_c:
                    con = conectar()
                    cur = con.cursor()
                    cur.execute("INSERT INTO contactos (id_empresa, nombre, correo, telefono, puesto) VALUES (?, ?, ?, ?, ?)",
                               (id_empresa, nombre_c, correo_c, telefono_c, puesto_c))
                    con.commit()
                    registrar_evento(con, "contacto", cur.lastrowid, "CREAR", f"Contacto: {nombre_c}")
                    st.success(f"✅ Contacto '{nombre_c}' creado")
                    st.rerun()
                    con.close()
            
            with col2:
                con = conectar()
                contactos = pd.read_sql("""
                    SELECT c.id_contacto, e.nombre as empresa, c.nombre, c.correo, c.puesto
                    FROM contactos c
                    JOIN empresas e ON e.id_empresa = c.id_empresa
                    ORDER BY c.fecha_alta DESC
                    LIMIT 10
                """, con)
                con.close()
                
                if len(contactos) > 0:
                    st.dataframe(contactos, width="stretch", hide_index=True)
                else:
                    st.info("No hay contactos registrados")
    
    # TAB: Prospectos (REGLA R1)
    with tab3:
        st.subheader("Generación de Prospectos")
        st.info("🔒 **REGLA R1:** Solo se generan prospectos desde empresas con contactos")
        
        con = conectar()
        empresas_validas = pd.read_sql("""
            SELECT e.id_empresa, e.nombre, COUNT(c.id_contacto) as total_contactos
            FROM empresas e
            INNER JOIN contactos c ON c.id_empresa = e.id_empresa
            GROUP BY e.id_empresa
            HAVING COUNT(c.id_contacto) > 0
            ORDER BY e.nombre
        """, con)
        con.close()
        
        if len(empresas_validas) == 0:
            st.warning("⚠️ No hay empresas con contactos válidos")
        else:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                with st.form("form_prospecto"):
                    emp_sel = st.selectbox("Empresa *", empresas_validas["nombre"].tolist())
                    id_emp = int(empresas_validas[empresas_validas["nombre"]==emp_sel]["id_empresa"].iloc[0])
                    
                    con = conectar()
                    contactos_emp = pd.read_sql("SELECT id_contacto, nombre, puesto FROM contactos WHERE id_empresa = ?", 
                                               con, params=(id_emp,))
                    con.close()
                    
                    if len(contactos_emp) > 0:
                        cont_display = [f"{row['nombre']} ({row['puesto']})" if row['puesto'] else row['nombre'] 
                                       for _, row in contactos_emp.iterrows()]
                        cont_sel = st.selectbox("Contacto *", cont_display)
                        id_cont = int(contactos_emp.iloc[cont_display.index(cont_sel)]["id_contacto"])
                        origen = st.text_input("Origen", placeholder="Campaña, Referencia, etc.")
                        submit_p = st.form_submit_button("✅ Generar Prospecto")
                        
                        if submit_p:
                            con = conectar()
                            cur = con.cursor()
                            cur.execute("INSERT INTO prospectos (id_empresa, id_contacto, origen, estado) VALUES (?, ?, ?, 'Activo')",
                                       (id_emp, id_cont, origen))
                            con.commit()
                            registrar_evento(con, "prospecto", cur.lastrowid, "CREAR", f"Prospecto: {emp_sel}")
                            st.success(f"✅ Prospecto generado (ID: {cur.lastrowid})")
                            st.rerun()
                            con.close()
            
            with col2:
                con = conectar()
                prospectos = pd.read_sql("""
                    SELECT p.id_prospecto, e.nombre as empresa, c.nombre as contacto,
                           p.estado, p.origen, p.fecha_creacion
                    FROM prospectos p
                    JOIN empresas e ON e.id_empresa = p.id_empresa
                    JOIN contactos c ON c.id_contacto = p.id_contacto
                    WHERE p.es_cliente = 0
                    ORDER BY p.fecha_creacion DESC
                    LIMIT 10
                """, con)
                con.close()
                
                if len(prospectos) > 0:
                    st.dataframe(prospectos, width="stretch", hide_index=True)
                else:
                    st.info("No hay prospectos activos")


# ================================================================
#  N2: TRANSACCIÓN (Oportunidades → Cotizaciones)
# ================================================================

elif menu == "💼 N2: Transacción":
    st.markdown('<div class="main-header">💼 Núcleo 2: Transacción</div>', unsafe_allow_html=True)
    st.markdown("**Flujo:** Prospecto → Oportunidad → Cotización → Cliente")
    
    tab1, tab2 = st.tabs(["🎯 Oportunidades", "💰 Cotizaciones"])
    
    # TAB: Oportunidades (REGLAS R2, R3, R4)
    with tab1:
        st.subheader("Gestión de Oportunidades")
        st.info("🔒 **REGLAS:** R2 (solo desde prospectos) | R3 (conversión automática) | R4 (OC requerida)")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            con = conectar()
            prospectos_disp = pd.read_sql("""
                SELECT p.id_prospecto, e.nombre as empresa, c.nombre as contacto
                FROM prospectos p
                JOIN empresas e ON e.id_empresa = p.id_empresa
                JOIN contactos c ON c.id_contacto = p.id_contacto
                WHERE p.es_cliente = 0 AND p.estado = 'Activo'
                ORDER BY p.fecha_creacion DESC
            """, con)
            con.close()
            
            if len(prospectos_disp) == 0:
                st.warning("⚠️ No hay prospectos activos. Crea uno en N1: Identidad")
            else:
                with st.form("form_oportunidad"):
                    pros_display = [f"{row['empresa']} - {row['contacto']}" for _, row in prospectos_disp.iterrows()]
                    pros_sel = st.selectbox("Prospecto *", pros_display)
                    id_pros = int(prospectos_disp.iloc[pros_display.index(pros_sel)]["id_prospecto"])
                    
                    nombre_op = st.text_input("Nombre de oportunidad *", placeholder="Venta de software CRM")
                    monto = st.number_input("Monto estimado *", min_value=0.0, step=1000.0)
                    etapa = st.selectbox("Etapa", ["Calificación", "Propuesta", "Negociación", "Cierre"])
                    probabilidad = st.slider("Probabilidad (%)", 0, 100, 25, 5)
                    fecha_cierre = st.date_input("Fecha estimada cierre")
                    submit_op = st.form_submit_button("✅ Crear Oportunidad")
                    
                    if submit_op and nombre_op and monto > 0:
                        con = conectar()
                        cur = con.cursor()
                        cur.execute("""
                            INSERT INTO oportunidades 
                            (id_prospecto, nombre, etapa, probabilidad, monto_estimado, fecha_estimada_cierre)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (id_pros, nombre_op, etapa, probabilidad, monto, fecha_cierre.isoformat()))
                        con.commit()
                        registrar_evento(con, "oportunidad", cur.lastrowid, "CREAR", f"Oportunidad: {nombre_op}")
                        st.success(f"✅ Oportunidad '{nombre_op}' creada")
                        st.rerun()
                        con.close()
        
        with col2:
            con = conectar()
            oportunidades = pd.read_sql("""
                SELECT o.id_oportunidad, o.nombre, o.etapa, o.probabilidad,
                       ROUND(o.monto_estimado, 2) as monto, o.oc_recibida,
                       e.nombre as empresa
                FROM oportunidades o
                JOIN prospectos p ON p.id_prospecto = o.id_prospecto
                JOIN empresas e ON e.id_empresa = p.id_empresa
                ORDER BY o.fecha_creacion DESC
                LIMIT 10
            """, con)
            con.close()
            
            if len(oportunidades) > 0:
                st.dataframe(oportunidades, width="stretch", hide_index=True)
                
                # Acciones sobre oportunidades
                st.divider()
                st.markdown("**Acciones:**")
                
                opor_sel_id = st.number_input("ID Oportunidad", min_value=1, step=1)
                
                col_a1, col_a2 = st.columns(2)
                
                with col_a1:
                    if st.button("🎉 Marcar como Ganada (REGLA R3)", width="stretch"):
                        con = conectar()
                        cur = con.cursor()
                        # Actualizar oportunidad
                        cur.execute("UPDATE oportunidades SET etapa='Ganada', probabilidad=100 WHERE id_oportunidad=?", 
                                   (opor_sel_id,))
                        # REGLA R3: Convertir prospecto a cliente
                        cur.execute("""
                            UPDATE prospectos SET es_cliente=1, fecha_conversion_cliente=? 
                            WHERE id_prospecto = (SELECT id_prospecto FROM oportunidades WHERE id_oportunidad=?)
                        """, (date.today().isoformat(), opor_sel_id))
                        con.commit()
                        registrar_evento(con, "oportunidad", opor_sel_id, "GANAR", "Oportunidad ganada → Cliente convertido")
                        st.success("✅ Oportunidad ganada y prospecto convertido a cliente")
                        st.rerun()
                        con.close()
                
                with col_a2:
                    if st.button("📋 Marcar OC Recibida (REGLA R4)", width="stretch"):
                        try:
                            con = conectar()
                            cur = con.cursor()
                            # Actualizar estado OC
                            cur.execute("UPDATE oportunidades SET oc_recibida=1 WHERE id_oportunidad=?", (opor_sel_id,))
                            con.commit()
                            
                            # Registrar evento en historial
                            registrar_evento(con, "oportunidad", opor_sel_id, "OC_RECIBIDA", "OC marcada como recibida")
                            
                            st.success("✅ OC recibida marcada y evento registrado en historial")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al marcar OC: {str(e)}")
                            import traceback
                            traceback.print_exc(file=sys.stderr)
                        finally:
                            if 'con' in locals():
                                con.close()
            else:
                st.info("No hay oportunidades registradas")
    
    # TAB: Cotizaciones
    with tab2:
        st.subheader("Gestión de Cotizaciones")
        st.info("🔒 **Modos:** Mínimo (solo monto) | Genérico (catálogo) | Externo (importación)")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            con = conectar()
            opor_para_cot = pd.read_sql("""
                SELECT o.id_oportunidad, o.nombre, o.etapa, ROUND(o.monto_estimado, 2) as monto
                FROM oportunidades o
                WHERE o.etapa NOT IN ('Perdida')
                ORDER BY o.fecha_creacion DESC
            """, con)
            con.close()
            
            if len(opor_para_cot) == 0:
                st.warning("⚠️ No hay oportunidades disponibles")
            else:
                with st.form("form_cotizacion"):
                    opor_display = [f"#{row['id_oportunidad']} - {row['nombre']} (${row['monto']})" 
                                   for _, row in opor_para_cot.iterrows()]
                    opor_sel = st.selectbox("Oportunidad *", opor_display)
                    id_opor = int(opor_para_cot.iloc[opor_display.index(opor_sel)]["id_oportunidad"])
                    
                    modo = st.selectbox("Modo *", ["minimo", "generico", "externo"])
                    monto_cot = st.number_input("Monto total *", min_value=0.0, step=100.0)
                    moneda = st.selectbox("Moneda", ["MXN", "USD", "EUR"])
                    notas = st.text_area("Notas", placeholder="Descripción de la cotización")
                    submit_cot = st.form_submit_button("✅ Crear Cotización")
                    
                    if submit_cot and monto_cot > 0:
                        import json
                        # Generar hash de integridad
                        data = {"id_oportunidad": id_opor, "modo": modo, "monto": monto_cot, "moneda": moneda}
                        hash_int = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
                        
                        con = conectar()
                        cur = con.cursor()
                        cur.execute("""
                            INSERT INTO cotizaciones 
                            (id_oportunidad, modo, fuente, monto_total, moneda, estado, hash_integridad, notas)
                            VALUES (?, ?, 'manual', ?, ?, 'Borrador', ?, ?)
                        """, (id_opor, modo, monto_cot, moneda, hash_int, notas))
                        con.commit()
                        cot_id = cur.lastrowid
                        # Registrar hash en tabla de trazabilidad
                        cur.execute("INSERT INTO hash_registros (tabla_origen, id_registro, hash_sha256) VALUES ('cotizaciones', ?, ?)",
                                   (cot_id, hash_int))
                        con.commit()
                        registrar_evento(con, "cotizacion", cot_id, "CREAR", f"Cotización modo {modo} - ${monto_cot} {moneda}")
                        st.success(f"✅ Cotización creada con hash: {hash_int[:16]}...")
                        st.rerun()
                        con.close()
        
        with col2:
            con = conectar()
            cotizaciones = pd.read_sql("""
                SELECT c.id_cotizacion, o.nombre as oportunidad, c.modo, 
                       ROUND(c.monto_total, 2) as monto, c.moneda, c.estado, c.version,
                       substr(c.hash_integridad, 1, 16) as hash
                FROM cotizaciones c
                JOIN oportunidades o ON o.id_oportunidad = c.id_oportunidad
                ORDER BY c.fecha_creacion DESC
                LIMIT 10
            """, con)
            con.close()
            
            if len(cotizaciones) > 0:
                st.dataframe(cotizaciones, width="stretch", hide_index=True)
            else:
                st.info("No hay cotizaciones registradas")


# ================================================================
#  N3: FACTURACIÓN (OC → Facturas)
# ================================================================

elif menu == "💰 N3: Facturación":
    st.markdown('<div class="main-header">💰 Núcleo 3: Facturación</div>', unsafe_allow_html=True)
    st.markdown("**Flujo:** Oportunidad Ganada → OC → Factura CFDI")
    
    # Widget de estado CFDI al inicio
    if CFDI_DISPONIBLE:
        try:
            st.divider()
            widget_estado_cfdi()
            st.divider()
        except Exception:
            pass
    
    tab1, tab2 = st.tabs(["🧾 Órdenes de Compra", "📄 Facturas"])
    
    # TAB: Órdenes de Compra
    with tab1:
        st.subheader("Gestión de Órdenes de Compra")
        st.info("🔒 **REGLA R4:** OC es requisito para facturar")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            con = conectar()
            opor_ganadas = pd.read_sql("""
                SELECT o.id_oportunidad, o.nombre, ROUND(o.monto_estimado, 2) as monto,
                       e.nombre as empresa
                FROM oportunidades o
                JOIN prospectos p ON p.id_prospecto = o.id_prospecto
                JOIN empresas e ON e.id_empresa = p.id_empresa
                WHERE o.etapa = 'Ganada' AND o.oc_recibida = 1
                AND o.id_oportunidad NOT IN (SELECT id_oportunidad FROM ordenes_compra)
                ORDER BY o.fecha_creacion DESC
            """, con)
            con.close()
            
            if len(opor_ganadas) == 0:
                st.warning("⚠️ No hay oportunidades ganadas con OC pendientes de registrar")
            else:
                with st.form("form_oc"):
                    opor_display = [f"#{row['id_oportunidad']} - {row['nombre']} (${row['monto']}) - {row['empresa']}" 
                                   for _, row in opor_ganadas.iterrows()]
                    opor_sel = st.selectbox("Oportunidad *", opor_display)
                    id_opor = int(opor_ganadas.iloc[opor_display.index(opor_sel)]["id_oportunidad"])
                    
                    numero_oc = st.text_input("Número de OC *", placeholder="OC-2025-001")
                    fecha_oc = st.date_input("Fecha OC *")
                    monto_oc = st.number_input("Monto OC *", min_value=0.0, step=100.0)
                    moneda_oc = st.selectbox("Moneda", ["MXN", "USD", "EUR"])
                    submit_oc = st.form_submit_button("✅ Registrar OC")
                    
                    if submit_oc and numero_oc and monto_oc > 0:
                        con = conectar()
                        cur = con.cursor()
                        cur.execute("""
                            INSERT INTO ordenes_compra (id_oportunidad, numero_oc, fecha_oc, monto_oc, moneda)
                            VALUES (?, ?, ?, ?, ?)
                        """, (id_opor, numero_oc, fecha_oc.isoformat(), monto_oc, moneda_oc))
                        con.commit()
                        registrar_evento(con, "orden_compra", cur.lastrowid, "CREAR", f"OC {numero_oc} - ${monto_oc} {moneda_oc}")
                        st.success(f"✅ OC '{numero_oc}' registrada")
                        st.rerun()
                        con.close()
        
        with col2:
            con = conectar()
            ocs = pd.read_sql("""
                SELECT oc.id_oc, oc.numero_oc, oc.fecha_oc, ROUND(oc.monto_oc, 2) as monto,
                       oc.moneda, o.nombre as oportunidad
                FROM ordenes_compra oc
                JOIN oportunidades o ON o.id_oportunidad = oc.id_oportunidad
                ORDER BY oc.fecha_oc DESC
                LIMIT 10
            """, con)
            con.close()
            
            if len(ocs) > 0:
                st.dataframe(ocs, width="stretch", hide_index=True)
            else:
                st.info("No hay OCs registradas")
    
    # TAB: Facturas
    with tab2:
        st.subheader("Gestión de Facturas CFDI")
        
        # Validar configuración CFDI antes de permitir facturar
        if CFDI_DISPONIBLE:
            valido_cfdi, mensaje_cfdi = validar_configuracion_cfdi()
            
            if not valido_cfdi:
                st.warning(f"⚠️ {mensaje_cfdi}")
                st.info("""
                **Para timbrar facturas CFDI necesitas:**
                1. Configurar tu emisor en **⚙️ Configuración CFDI**
                2. Registrar certificados CSD del SAT
                3. Configurar token de TimbrarCFDI33.mx
                
                👉 Ve al menú **⚙️ Configuración CFDI** para completar el registro.
                """)
                
                if st.button("⚙️ Ir a Configuración CFDI", type="primary"):
                    st.session_state.menu_redireccion_pendiente = "⚙️ Configuración CFDI"
                    st.rerun()
                
                st.divider()
                st.caption("💡 Mientras tanto, puedes registrar facturas manualmente ingresando el UUID.")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            con = conectar()
            ocs_sin_factura = pd.read_sql("""
                SELECT oc.id_oc, oc.numero_oc, ROUND(oc.monto_oc, 2) as monto, oc.moneda
                FROM ordenes_compra oc
                WHERE oc.id_oc NOT IN (SELECT id_oc FROM facturas)
                ORDER BY oc.fecha_oc DESC
            """, con)
            con.close()
            
            if len(ocs_sin_factura) == 0:
                st.warning("⚠️ No hay OCs pendientes de facturar")
            else:
                # Mostrar opción de timbrado automático si CFDI está configurado
                if CFDI_DISPONIBLE:
                    valido_cfdi, _ = validar_configuracion_cfdi()
                    if valido_cfdi:
                        st.success("✅ Emisor CFDI configurado - Timbrado disponible")
                        st.info("🚧 **Próximamente:** Timbrado automático CFDI 4.0")
                        st.caption("Por ahora, registra facturas manualmente con el UUID del PAC")
                
                with st.form("form_factura"):
                    st.markdown("### 📝 Registro Manual de Factura")
                    st.caption("Ingresa los datos de la factura ya timbrada en tu PAC")
                    
                    oc_display = [f"OC #{row['id_oc']} - {row['numero_oc']} (${row['monto']} {row['moneda']})" 
                                 for _, row in ocs_sin_factura.iterrows()]
                    oc_sel = st.selectbox("Orden de Compra *", oc_display)
                    id_oc = int(ocs_sin_factura.iloc[oc_display.index(oc_sel)]["id_oc"])
                    
                    uuid = st.text_input("UUID CFDI *", placeholder="A1B2C3D4-...")
                    serie = st.text_input("Serie", placeholder="A")
                    folio = st.text_input("Folio", placeholder="12345")
                    fecha_emision = st.date_input("Fecha emisión *")
                    monto_fact = st.number_input("Monto total *", min_value=0.0, step=100.0)
                    moneda_fact = st.selectbox("Moneda", ["MXN", "USD", "EUR"])
                    submit_fact = st.form_submit_button("✅ Registrar Factura")
                    
                    if submit_fact and uuid and monto_fact > 0:
                        import json
                        # Hash forense de la factura
                        data_fact = {"uuid": uuid, "serie": serie, "folio": folio, 
                                    "fecha": fecha_emision.isoformat(), "monto": monto_fact}
                        hash_fact = hashlib.sha256(json.dumps(data_fact, sort_keys=True).encode()).hexdigest()
                        
                        con = conectar()
                        cur = con.cursor()
                        cur.execute("""
                            INSERT INTO facturas (id_oc, uuid, serie, folio, fecha_emision, monto_total, moneda)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (id_oc, uuid, serie, folio, fecha_emision.isoformat(), monto_fact, moneda_fact))
                        con.commit()
                        fact_id = cur.lastrowid
                        # Registrar hash forense
                        cur.execute("INSERT INTO hash_registros (tabla_origen, id_registro, hash_sha256) VALUES ('facturas', ?, ?)",
                                   (fact_id, hash_fact))
                        con.commit()
                        registrar_evento(con, "factura", fact_id, "CREAR", f"Factura {serie}-{folio} UUID:{uuid[:16]}...")
                        st.success(f"✅ Factura creada con hash: {hash_fact[:16]}...")
                        st.rerun()
                        con.close()
        
        with col2:
            con = conectar()
            facturas = pd.read_sql("""
                SELECT f.id_factura, f.uuid, f.serie, f.folio, f.fecha_emision,
                       ROUND(f.monto_total, 2) as monto, f.moneda,
                       oc.numero_oc
                FROM facturas f
                JOIN ordenes_compra oc ON oc.id_oc = f.id_oc
                ORDER BY f.fecha_emision DESC
                LIMIT 10
            """, con)
            con.close()
            
            if len(facturas) > 0:
                st.dataframe(facturas, width="stretch", hide_index=True)
            else:
                st.info("No hay facturas registradas")


# ================================================================
#  N4: TRAZABILIDAD (Historial + Hashes)
# ================================================================

elif menu == "🪶 N4: Trazabilidad":
    st.markdown('<div class="main-header">🪶 Núcleo 4: Trazabilidad Forense</div>', unsafe_allow_html=True)
    st.markdown("**Sistema de auditoría con hash SHA256**")
    
    tab1, tab2 = st.tabs(["📋 Historial General", "🔐 Verificación de Hashes"])
    
    # TAB: Historial
    with tab1:
        st.subheader("Historial de Eventos")
        
        con = conectar()
        
        # Filtros
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            filtro_entidad = st.selectbox("Filtrar por entidad", 
                                         ["Todas", "empresa", "contacto", "prospecto", "oportunidad", 
                                          "cotizacion", "orden_compra", "factura"])
        
        with col_f2:
            filtro_accion = st.selectbox("Filtrar por acción",
                                        ["Todas", "CREAR", "ACTUALIZAR", "GANAR", "OC_RECIBIDA"])
        
        with col_f3:
            limite = st.number_input("Límite de registros", min_value=10, max_value=100, value=50, step=10)
        
        # Construir query con filtros
        query = "SELECT * FROM historial_general WHERE 1=1"
        params = []
        
        if filtro_entidad != "Todas":
            query += " AND entidad = ?"
            params.append(filtro_entidad)
        
        if filtro_accion != "Todas":
            query += " AND accion = ?"
            params.append(filtro_accion)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limite)
        
        historial = pd.read_sql(query, con, params=params)
        con.close()
        
        if len(historial) > 0:
            # Mostrar con hash truncado
            historial['hash_corto'] = historial['hash_evento'].str[:16]
            st.dataframe(
                historial[['id_evento', 'entidad', 'id_entidad', 'accion', 'valor_nuevo', 
                          'usuario', 'timestamp', 'hash_corto']],
                width="stretch",
                hide_index=True
            )
        else:
            st.info("No hay eventos que cumplan los filtros")
    
    # TAB: Verificación de hashes
    with tab2:
        st.subheader("Verificación de Integridad Forense")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Hashes de Cotizaciones:**")
            con = conectar()
            hashes_cot = pd.read_sql("""
                SELECT h.id_hash, h.id_registro, substr(h.hash_sha256, 1, 20) as hash,
                       h.timestamp
                FROM hash_registros h
                WHERE h.tabla_origen = 'cotizaciones'
                ORDER BY h.timestamp DESC
                LIMIT 10
            """, con)
            con.close()
            
            if len(hashes_cot) > 0:
                st.dataframe(hashes_cot, width="stretch", hide_index=True)
            else:
                st.info("No hay hashes de cotizaciones")
        
        with col2:
            st.markdown("**Hashes de Facturas:**")
            con = conectar()
            hashes_fact = pd.read_sql("""
                SELECT h.id_hash, h.id_registro, substr(h.hash_sha256, 1, 20) as hash,
                       h.timestamp
                FROM hash_registros h
                WHERE h.tabla_origen = 'facturas'
                ORDER BY h.timestamp DESC
                LIMIT 10
            """, con)
            con.close()
            
            if len(hashes_fact) > 0:
                st.dataframe(hashes_fact, width="stretch", hide_index=True)
            else:
                st.info("No hay hashes de facturas")
        
        st.divider()
        
        # Estadísticas de integridad
        st.subheader("📊 Estadísticas del Sistema")
        
        con = conectar()
        
        col_s1, col_s2, col_s3 = st.columns(3)
        
        with col_s1:
            total_eventos = pd.read_sql("SELECT COUNT(*) as total FROM historial_general", con).iloc[0]["total"]
            st.metric("Total de Eventos", total_eventos)
        
        with col_s2:
            total_hashes = pd.read_sql("SELECT COUNT(*) as total FROM hash_registros", con).iloc[0]["total"]
            st.metric("Hashes Forenses", total_hashes)
        
        with col_s3:
            usuarios_activos = pd.read_sql("SELECT COUNT(DISTINCT usuario) as total FROM historial_general", con).iloc[0]["total"]
            st.metric("Usuarios Registrados", usuarios_activos)
        
        con.close()


# ================================================================
#  PIPELINE VISUAL
# ================================================================

elif menu == "📊 Pipeline Visual":
    st.markdown('<div class="main-header">📊 Pipeline Visual Completo</div>', unsafe_allow_html=True)
    
    con = conectar()

    cfdi_valido = False
    if CFDI_DISPONIBLE:
        try:
            cfdi_valido, _ = validar_configuracion_cfdi()
        except Exception:
            cfdi_valido = False

    metricas_helper = obtener_metricas_helper(con)
    recomendaciones_helper = construir_recomendaciones_helper(metricas_helper, cfdi_valido)
    score_oportunidades = obtener_scores_oportunidad(con)
    score_oportunidades = enriquecer_scores_con_historial(con, score_oportunidades)
    persistir_scores_oportunidad(con, score_oportunidades)

    st.subheader("🤖 Helper interno del flujo")
    st.caption("Recomendaciones determinísticas calculadas con datos reales del pipeline, sin LLM.")

    for index, recomendacion in enumerate(recomendaciones_helper[:4], start=1):
        col_h1, col_h2, col_h3 = st.columns([5, 2, 2])
        with col_h1:
            if recomendacion["prioridad"] == "Alta":
                st.warning(f"{recomendacion['prioridad']}: {recomendacion['mensaje']}")
            elif recomendacion["prioridad"] == "Media":
                st.info(f"{recomendacion['prioridad']}: {recomendacion['mensaje']}")
            else:
                st.success(recomendacion["mensaje"])
            st.caption(f"Riesgo: {recomendacion['riesgo']}")
        with col_h2:
            st.metric(f"Acción {index}", recomendacion["accion"])
        with col_h3:
            if recomendacion["menu"] != "📊 Pipeline Visual":
                if st.button(f"Ir ahora {index}", key=f"helper_ir_{index}"):
                    st.session_state.menu_redireccion_pendiente = recomendacion["menu"]
                    st.rerun()

    st.divider()

    st.subheader("🎯 Prioridad por oportunidad")
    st.caption("Scoring interno por salud del flujo. Prioriza casos con mayor riesgo operativo y menor avance verificable.")

    if len(score_oportunidades) > 0:
        snapshots_info = pd.read_sql("""
            SELECT COUNT(*) AS total_snapshots, MAX(fecha_snapshot) AS ultima_fecha
            FROM pipeline_helper_oportunidad_snapshots
        """, con).iloc[0]

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.metric("Snapshots helper", int(snapshots_info["total_snapshots"]))
        with col_p2:
            st.metric("Último snapshot", snapshots_info["ultima_fecha"] or "N/D")

        st.dataframe(
            score_oportunidades[[
                "id_oportunidad", "empresa", "oportunidad", "etapa", "probabilidad",
                "dias_abierta", "cotizaciones", "ocs", "facturas", "score_flujo",
                "score_anterior", "delta_score", "salud_flujo", "prioridad", "hallazgos", "accion_sugerida"
            ]],
            width="stretch",
            hide_index=True,
            column_config={
                "id_oportunidad": st.column_config.NumberColumn("ID", format="%d"),
                "empresa": "Empresa",
                "oportunidad": "Oportunidad",
                "etapa": "Etapa",
                "probabilidad": st.column_config.NumberColumn("Prob. %", format="%d"),
                "dias_abierta": st.column_config.NumberColumn("Días", format="%.1f"),
                "cotizaciones": st.column_config.NumberColumn("Cot.", format="%d"),
                "ocs": st.column_config.NumberColumn("OCs", format="%d"),
                "facturas": st.column_config.NumberColumn("Fact.", format="%d"),
                "score_flujo": st.column_config.NumberColumn("Score", format="%d"),
                "score_anterior": st.column_config.NumberColumn("Score ant.", format="%d"),
                "delta_score": st.column_config.NumberColumn("Delta", format="%d"),
                "salud_flujo": "Salud",
                "prioridad": "Prioridad",
                "hallazgos": "Hallazgos",
                "accion_sugerida": "Acción sugerida",
            }
        )

        st.caption("Casos más urgentes")
        for index, row in score_oportunidades.head(3).iterrows():
            col_u1, col_u2, col_u3 = st.columns([5, 2, 2])
            with col_u1:
                if row["prioridad"] == "Alta":
                    st.warning(f"{row['empresa']} | {row['oportunidad']} | {row['hallazgos']}")
                elif row["prioridad"] == "Media":
                    st.info(f"{row['empresa']} | {row['oportunidad']} | {row['hallazgos']}")
                else:
                    st.success(f"{row['empresa']} | {row['oportunidad']} | {row['hallazgos']}")
            with col_u2:
                st.metric(f"Score {int(row['id_oportunidad'])}", int(row["score_flujo"]))
            with col_u3:
                if st.button(f"Atender {int(row['id_oportunidad'])}", key=f"score_ir_{int(row['id_oportunidad'])}"):
                    st.session_state.menu_redireccion_pendiente = row["menu_sugerido"]
                    st.rerun()
    else:
        st.info("No hay oportunidades para calcular score de flujo.")

    st.divider()

    # Este bloque es el mejor punto para insertar un helper interno futuro,
    # porque aqui ya convergen estados, conversiones y tiempos del recorrido.
    st.subheader("🧭 Recorrido sugerido")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        st.info("1. Empresa → Contacto")
    with col_f2:
        st.info("2. Prospecto → Oportunidad")
    with col_f3:
        st.info("3. Cotización → OC")
    with col_f4:
        st.info("4. Factura → Trazabilidad")
    
    st.divider()
    
    # Flujo completo desde empresas hasta facturas
    flujo_completo = pd.read_sql("""
        SELECT 
            e.id_empresa,
            e.nombre as empresa,
            COUNT(DISTINCT c.id_contacto) as contactos,
            COUNT(DISTINCT p.id_prospecto) as prospectos,
            COUNT(DISTINCT CASE WHEN p.es_cliente = 0 THEN p.id_prospecto END) as prospectos_activos,
            COUNT(DISTINCT CASE WHEN p.es_cliente = 1 THEN p.id_prospecto END) as clientes,
            COUNT(DISTINCT o.id_oportunidad) as oportunidades,
            COUNT(DISTINCT CASE WHEN o.etapa = 'Ganada' THEN o.id_oportunidad END) as ganadas,
            ROUND(COALESCE(SUM(CASE WHEN o.etapa = 'Ganada' THEN o.monto_estimado END), 0), 2) as monto_ganado
        FROM empresas e
        LEFT JOIN contactos c ON c.id_empresa = e.id_empresa
        LEFT JOIN prospectos p ON p.id_empresa = e.id_empresa
        LEFT JOIN oportunidades o ON o.id_prospecto = p.id_prospecto
        GROUP BY e.id_empresa
        ORDER BY monto_ganado DESC, oportunidades DESC
    """, con)
    
    if len(flujo_completo) > 0:
        st.dataframe(
            flujo_completo,
            width="stretch",
            hide_index=True,
            column_config={
                "empresa": "Empresa",
                "contactos": st.column_config.NumberColumn("Contactos", format="%d"),
                "prospectos": st.column_config.NumberColumn("Prospectos Total", format="%d"),
                "prospectos_activos": st.column_config.NumberColumn("Activos", format="%d"),
                "clientes": st.column_config.NumberColumn("Clientes", format="%d"),
                "oportunidades": st.column_config.NumberColumn("Oportunidades", format="%d"),
                "ganadas": st.column_config.NumberColumn("Ganadas", format="%d"),
                "monto_ganado": st.column_config.NumberColumn("Monto Ganado", format="$%.2f")
            }
        )
    else:
        st.info("No hay datos para mostrar. Comienza registrando empresas en N1: Identidad")
    
    st.divider()
    
    # Resumen de conversión
    st.subheader("📈 Embudo de Conversión")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_emp = pd.read_sql("SELECT COUNT(*) as total FROM empresas", con).iloc[0]["total"]
    total_pros = pd.read_sql("SELECT COUNT(*) as total FROM prospectos WHERE es_cliente=0", con).iloc[0]["total"]
    total_opor = pd.read_sql("SELECT COUNT(*) as total FROM oportunidades WHERE etapa NOT IN ('Perdida')", con).iloc[0]["total"]
    total_cli = pd.read_sql("SELECT COUNT(*) as total FROM prospectos WHERE es_cliente=1", con).iloc[0]["total"]
    
    with col1:
        st.metric("🏢 Empresas", total_emp)
    
    with col2:
        st.metric("📈 Prospectos", total_pros)
        if total_emp > 0:
            st.caption(f"Conversión: {(total_pros/total_emp*100):.1f}%")
    
    with col3:
        st.metric("🎯 Oportunidades", total_opor)
        if total_pros > 0:
            st.caption(f"Conversión: {(total_opor/total_pros*100):.1f}%")
    
    with col4:
        st.metric("✅ Clientes", total_cli)
        if total_opor > 0:
            st.caption(f"Conversión: {(total_cli/max(total_opor,1)*100):.1f}%")

    st.divider()

    st.subheader("⏱️ Ahorro operativo estimado")
    st.caption("Se calcula con timestamps reales del sistema y una línea base explícita por tramo. Úsalo como indicador operativo, no como ROI financiero auditado.")

    costo_hora = st.number_input(
        "Costo hora de referencia (MXN)",
        min_value=0.0,
        value=350.0,
        step=50.0,
        help="Sirve para traducir el ahorro de tiempo estimado a valor operativo recuperable.",
    )

    tiempos_flujo = pd.read_sql("""
        SELECT 'Prospecto a oportunidad' AS tramo,
               COUNT(*) AS casos,
               ROUND(AVG((julianday(o.fecha_creacion) - julianday(p.fecha_creacion)) * 24), 1) AS horas_reales
        FROM oportunidades o
        JOIN prospectos p ON p.id_prospecto = o.id_prospecto
        WHERE p.fecha_creacion IS NOT NULL AND o.fecha_creacion IS NOT NULL

        UNION ALL

        SELECT 'Oportunidad a OC' AS tramo,
               COUNT(*) AS casos,
               ROUND(AVG((julianday(oc.fecha_oc) - julianday(o.fecha_creacion)) * 24), 1) AS horas_reales
        FROM ordenes_compra oc
        JOIN oportunidades o ON o.id_oportunidad = oc.id_oportunidad
        WHERE oc.fecha_oc IS NOT NULL AND o.fecha_creacion IS NOT NULL

        UNION ALL

        SELECT 'OC a factura' AS tramo,
               COUNT(*) AS casos,
               ROUND(AVG((julianday(f.fecha_emision) - julianday(oc.fecha_oc)) * 24), 1) AS horas_reales
        FROM facturas f
        JOIN ordenes_compra oc ON oc.id_oc = f.id_oc
        WHERE f.fecha_emision IS NOT NULL AND oc.fecha_oc IS NOT NULL

        UNION ALL

        SELECT 'Prospecto a cliente' AS tramo,
               COUNT(*) AS casos,
               ROUND(AVG((julianday(p.fecha_conversion_cliente) - julianday(p.fecha_creacion)) * 24), 1) AS horas_reales
        FROM prospectos p
        WHERE p.es_cliente = 1
          AND p.fecha_conversion_cliente IS NOT NULL
          AND p.fecha_creacion IS NOT NULL
    """, con)

    tiempos_flujo["horas_reales"] = pd.to_numeric(tiempos_flujo["horas_reales"], errors="coerce")
    tiempos_flujo["baseline_horas"] = tiempos_flujo["tramo"].map(ROI_BASELINE_HOURS)
    tiempos_flujo["ahorro_horas"] = (tiempos_flujo["baseline_horas"] - tiempos_flujo["horas_reales"]).clip(lower=0)
    tiempos_flujo["ahorro_pct"] = ((tiempos_flujo["ahorro_horas"] / tiempos_flujo["baseline_horas"]) * 100).round(1)
    tiempos_flujo["valor_mxn"] = (tiempos_flujo["ahorro_horas"] * costo_hora).round(2)

    resumen_roi = tiempos_flujo.dropna(subset=["horas_reales"]).copy()

    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        ahorro_total = float(resumen_roi["ahorro_horas"].sum()) if len(resumen_roi) > 0 else 0.0
        st.metric("Horas ahorradas estimadas", f"{ahorro_total:.1f} h")

    with col_r2:
        valor_total = float(resumen_roi["valor_mxn"].sum()) if len(resumen_roi) > 0 else 0.0
        st.metric("Valor operativo estimado", f"${valor_total:,.0f}")

    with col_r3:
        tramos_medidos = int((resumen_roi["casos"] > 0).sum()) if len(resumen_roi) > 0 else 0
        st.metric("Tramos medidos", tramos_medidos)

    if len(resumen_roi) > 0:
        st.dataframe(
            resumen_roi[["tramo", "casos", "horas_reales", "baseline_horas", "ahorro_horas", "ahorro_pct", "valor_mxn"]],
            width="stretch",
            hide_index=True,
            column_config={
                "tramo": "Tramo",
                "casos": st.column_config.NumberColumn("Casos", format="%d"),
                "horas_reales": st.column_config.NumberColumn("Horas reales", format="%.1f h"),
                "baseline_horas": st.column_config.NumberColumn("Línea base", format="%.1f h"),
                "ahorro_horas": st.column_config.NumberColumn("Ahorro estimado", format="%.1f h"),
                "ahorro_pct": st.column_config.NumberColumn("Ahorro %", format="%.1f%%"),
                "valor_mxn": st.column_config.NumberColumn("Valor estimado", format="$%.2f"),
            }
        )

        chart_roi = resumen_roi.set_index("tramo")[["horas_reales", "baseline_horas"]]
        st.caption("Comparativo entre tiempo real observado y línea base esperada por tramo")
        st.bar_chart(chart_roi)
    else:
        st.info("Aún no hay suficientes timestamps para estimar ahorro operativo en el flujo.")
    
    con.close()


# ================================================================
#  CONFIGURACIÓN CFDI
# ================================================================

elif menu == "⚙️ Configuración CFDI":
    if CFDI_DISPONIBLE:
        # Mostrar interfaz completa de configuración CFDI
        ui_registro_emisor()
        
        # Widget de estado al final
        st.divider()
        st.subheader("📊 Estado de Configuración")
        
        valido, mensaje = validar_configuracion_cfdi()
        
        if valido:
            st.success(f"✅ {mensaje}")
            st.info("""
            **Siguiente paso:** 
            - Ir a la sección **💰 N3: Facturación** para timbrar facturas
            - Verifica que el emisor coincida con tus datos fiscales
            - Revisa la vigencia de tus certificados CSD
            """)
        else:
            st.warning(f"⚠️ {mensaje}")
            st.info("""
            **Completa la configuración:**
            1. Registra tu cuenta en https://timbracfdi33.mx
            2. Obtén tu token de API (pruebas o producción)
            3. Descarga tus certificados CSD del portal del SAT
            4. Completa el formulario arriba
            """)
    else:
        st.error("❌ Módulo CFDI no disponible")
        st.warning("""
        **El módulo de facturación CFDI no se pudo cargar.**
        
        Posibles causas:
        - Archivos faltantes en `crm_exo_v2/core/facturacion/`
        - Archivos faltantes en `crm_exo_v2/ui/`
        - Dependencias no instaladas (`pip install requests`)
        
        Verifica que existan:
        - `crm_exo_v2/core/facturacion/cfdi_emisor.py`
        - `crm_exo_v2/ui/ui_cfdi_emisor.py`
        """)


# ================================================================
#  FOOTER
# ================================================================

st.divider()
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9rem;'>
    <strong>CRM-EXO v2</strong> | Arquitectura AUP de 4 núcleos | 
    Identidad → Transacción → Facturación → Trazabilidad<br>
    Sistema forense con hash SHA256 | Resolución inversa | Fallos tolerados, estructura no
</div>
""", unsafe_allow_html=True)
