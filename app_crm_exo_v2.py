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
import json
import requests
from datetime import datetime, date
import pandas as pd
from pathlib import Path
from decimal import Decimal
import sys

try:
    import altair as alt
    ALTAIR_DISPONIBLE = True
except ImportError:
    alt = None
    ALTAIR_DISPONIBLE = False

# Ruta relativa desde raíz del proyecto
BASE_DIR = Path(__file__).parent

# Agregar rutas para imports de módulos internos
sys.path.insert(0, str(BASE_DIR / "crm_exo_v2" / "core"))
sys.path.insert(0, str(BASE_DIR / "crm_exo_v2" / "ui"))

from db_runtime import get_legacy_app_backend, get_legacy_app_backend_status, get_sqlite_db_path
from dynamiquote_bridge import (
    DEFAULT_DYNAMIQUOTE_API_URL,
    DEFAULT_PLAYBOOK_NAME,
    DynamiQuoteError,
    importar_cotizacion_desde_dynamiquote,
)

DB_PATH = get_sqlite_db_path(BASE_DIR)

# Importar módulos de facturación CFDI
try:
    from ui_cfdi_emisor import ui_registro_emisor, widget_estado_cfdi, ui_diagnostico_certificados
    from facturacion.cfdi_emisor import validar_configuracion_cfdi, obtener_configuracion_emisor
    CFDI_DISPONIBLE = True
except ImportError as e:
    CFDI_DISPONIBLE = False
    print(f"⚠️ Módulo CFDI no disponible: {e}")

# Importar componentes UX mejorados (Nivel 1 + Nivel 2)
try:
    from ux_components import (
        advanced_search_widget,
        pipeline_funnel_interactive,
        timeline_actividad_visual,
        grafico_metricas_dashboard,
        keyboard_shortcuts_handler,
        smart_navigation_menu,
        contextual_quick_actions,
        notification_center,
        bulk_operations_widget,
        import_export_wizard,
        dark_mode_toggle
    )
    UX_COMPONENTS_DISPONIBLES = True
except ImportError as e:
    UX_COMPONENTS_DISPONIBLES = False
    print(f"⚠️ Componentes UX no disponibles: {e}")


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

PIPELINE_ETAPA_ORDEN = [
    "Calificación",
    "Propuesta",
    "Negociación",
    "Cierre",
    "Ganada",
    "Perdida",
    "Sin etapa",
]

DEFAULT_DYNAMIQUOTE_ITEMS_JSON = """[
    {
        "sku": "LIC-001",
        "description": "Licencia anual",
        "quantity": 10,
        "cost_unit": 100,
        "price_unit": 150
    },
    {
        "sku": "SERV-IMP",
        "description": "Implementación",
        "quantity": 1,
        "cost_unit": 800,
        "price_unit": 1200
    }
]"""


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
            CAST(julianday('now') - julianday(o.fecha_creacion) AS INTEGER) AS dias_abierta,
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


def preparar_visualizaciones_pipeline(score_df):
    if len(score_df) == 0:
        return score_df, pd.DataFrame(), pd.DataFrame()

    visual_df = score_df.copy()
    visual_df["etapa"] = visual_df["etapa"].fillna("Sin etapa")
    visual_df["dias_abierta"] = pd.to_numeric(visual_df["dias_abierta"], errors="coerce").fillna(0).astype(int)
    visual_df["probabilidad"] = pd.to_numeric(visual_df["probabilidad"], errors="coerce").fillna(0)
    visual_df["score_flujo"] = pd.to_numeric(visual_df["score_flujo"], errors="coerce").fillna(0)
    visual_df["delta_score"] = pd.to_numeric(visual_df.get("delta_score"), errors="coerce")
    visual_df["prioridad_valor"] = visual_df["prioridad"].map({"Alta": 3, "Media": 2, "Baja": 1}).fillna(1)
    visual_df["peso_operativo"] = (
        (100 - visual_df["score_flujo"]).clip(lower=0)
        + visual_df["dias_abierta"].clip(upper=120) * 0.55
        + (100 - visual_df["probabilidad"]).clip(lower=0) * 0.15
        + visual_df["prioridad_valor"] * 8
    ).round(1)
    visual_df["etiqueta_oportunidad"] = visual_df.apply(
        lambda row: f"{row['empresa']} | {row['oportunidad']}",
        axis=1,
    )

    heatmap_df = visual_df.groupby(["etapa", "prioridad"], as_index=False).agg(
        oportunidades=("id_oportunidad", "count"),
        peso_total=("peso_operativo", "sum"),
        score_promedio=("score_flujo", "mean"),
    )

    top_riesgo_df = visual_df.sort_values(
        ["peso_operativo", "score_flujo", "dias_abierta"],
        ascending=[False, True, False],
    ).head(10)

    return visual_df, heatmap_df, top_riesgo_df


def filtrar_pipeline_visual(score_df):
    if len(score_df) == 0:
        return score_df

    st.markdown("#### 🎛️ Filtros visuales")
    col_f1, col_f2, col_f3 = st.columns([2, 3, 4])

    with col_f1:
        alcance = st.radio(
            "Alcance",
            ["Activas", "Todas"],
            horizontal=True,
            key="pipeline_filtro_alcance",
        )

    opciones_prioridad = ["Alta", "Media", "Baja"]
    with col_f2:
        prioridades = st.multiselect(
            "Prioridad",
            options=opciones_prioridad,
            default=opciones_prioridad,
            key="pipeline_filtro_prioridad",
        )

    etapas_disponibles = [etapa for etapa in PIPELINE_ETAPA_ORDEN if etapa in score_df["etapa"].fillna("Sin etapa").unique()]
    etapas_default = [etapa for etapa in etapas_disponibles if etapa not in ("Ganada", "Perdida")]
    if not etapas_default:
        etapas_default = etapas_disponibles

    with col_f3:
        etapas = st.multiselect(
            "Etapa",
            options=etapas_disponibles,
            default=etapas_default if alcance == "Activas" else etapas_disponibles,
            key=f"pipeline_filtro_etapa_{alcance.lower()}",
        )

    filtrado = score_df.copy()
    filtrado["etapa"] = filtrado["etapa"].fillna("Sin etapa")

    if alcance == "Activas":
        filtrado = filtrado[~filtrado["etapa"].isin(["Ganada", "Perdida"])]

    if prioridades:
        filtrado = filtrado[filtrado["prioridad"].isin(prioridades)]

    if etapas:
        filtrado = filtrado[filtrado["etapa"].isin(etapas)]

    st.caption(f"Mostrando {len(filtrado)} de {len(score_df)} oportunidades en la vista analítica.")
    return filtrado


def renderizar_vistas_graficas_pipeline(score_df):
    if len(score_df) == 0:
        return

    visual_df, heatmap_df, top_riesgo_df = preparar_visualizaciones_pipeline(score_df)

    st.markdown("#### 👁️ Vista gráfica del pipeline")
    st.caption("Cambia de vista para detectar carga operativa, urgencia y zonas de fricción del pipeline.")

    if not ALTAIR_DISPONIBLE:
        st.info("Altair no está disponible en este entorno. Se mantiene la tabla operativa como respaldo.")
        return

    vista_grafica = st.radio(
        "Visualización",
        ["Mapa de calor", "Burbujas", "Ranking de riesgo"],
        horizontal=True,
        key="pipeline_visual_grafica",
    )

    if vista_grafica == "Mapa de calor":
        heatmap_chart = alt.Chart(heatmap_df).mark_rect(cornerRadius=6).encode(
            x=alt.X("prioridad:N", sort=["Alta", "Media", "Baja"], title="Prioridad"),
            y=alt.Y("etapa:N", sort=PIPELINE_ETAPA_ORDEN, title="Etapa"),
            color=alt.Color("peso_total:Q", title="Peso operativo", scale=alt.Scale(scheme="orangered")),
            tooltip=[
                alt.Tooltip("etapa:N", title="Etapa"),
                alt.Tooltip("prioridad:N", title="Prioridad"),
                alt.Tooltip("oportunidades:Q", title="Oportunidades"),
                alt.Tooltip("peso_total:Q", title="Peso total", format=".1f"),
                alt.Tooltip("score_promedio:Q", title="Score promedio", format=".1f"),
            ],
        )
        heatmap_labels = alt.Chart(heatmap_df).mark_text(fontSize=14, fontWeight="bold").encode(
            x=alt.X("prioridad:N", sort=["Alta", "Media", "Baja"]),
            y=alt.Y("etapa:N", sort=PIPELINE_ETAPA_ORDEN),
            text=alt.Text("oportunidades:Q"),
            color=alt.value("white"),
        )
        st.altair_chart((heatmap_chart + heatmap_labels).properties(height=320), width="stretch")
        st.caption("La intensidad sube cuando convergen score bajo, muchos días abierta y prioridad alta.")

    elif vista_grafica == "Burbujas":
        lineas_control = alt.Chart(pd.DataFrame({"y": [60, 85]})).mark_rule(color="#7f8c8d", strokeDash=[5, 5]).encode(
            y="y:Q"
        )
        bubble_chart = alt.Chart(visual_df).mark_circle(opacity=0.82, stroke="white", strokeWidth=1).encode(
            x=alt.X("dias_abierta:Q", title="Días abierta"),
            y=alt.Y("score_flujo:Q", title="Score de flujo", scale=alt.Scale(domain=[0, 100])),
            size=alt.Size("peso_operativo:Q", title="Peso operativo", scale=alt.Scale(range=[120, 1800])),
            color=alt.Color(
                "prioridad:N",
                title="Prioridad",
                scale=alt.Scale(domain=["Alta", "Media", "Baja"], range=["#d73027", "#fdae61", "#1a9850"]),
            ),
            tooltip=[
                alt.Tooltip("empresa:N", title="Empresa"),
                alt.Tooltip("oportunidad:N", title="Oportunidad"),
                alt.Tooltip("etapa:N", title="Etapa"),
                alt.Tooltip("prioridad:N", title="Prioridad"),
                alt.Tooltip("score_flujo:Q", title="Score", format=".0f"),
                alt.Tooltip("dias_abierta:Q", title="Días", format=".0f"),
                alt.Tooltip("probabilidad:Q", title="Probabilidad", format=".0f"),
                alt.Tooltip("peso_operativo:Q", title="Peso operativo", format=".1f"),
            ],
        )
        st.altair_chart((bubble_chart + lineas_control).properties(height=380), width="stretch")
        st.caption("Arriba a la izquierda: oportunidades más sanas. Abajo y con burbujas grandes: foco inmediato.")

    else:
        ranking_chart = alt.Chart(top_riesgo_df).mark_bar(cornerRadiusEnd=6).encode(
            y=alt.Y("etiqueta_oportunidad:N", sort="-x", title=None),
            x=alt.X("peso_operativo:Q", title="Peso operativo"),
            color=alt.Color(
                "prioridad:N",
                scale=alt.Scale(domain=["Alta", "Media", "Baja"], range=["#d73027", "#fdae61", "#1a9850"]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("empresa:N", title="Empresa"),
                alt.Tooltip("oportunidad:N", title="Oportunidad"),
                alt.Tooltip("etapa:N", title="Etapa"),
                alt.Tooltip("prioridad:N", title="Prioridad"),
                alt.Tooltip("score_flujo:Q", title="Score", format=".0f"),
                alt.Tooltip("dias_abierta:Q", title="Días", format=".0f"),
                alt.Tooltip("delta_score:Q", title="Delta", format=".0f"),
                alt.Tooltip("peso_operativo:Q", title="Peso operativo", format=".1f"),
            ],
        )
        st.altair_chart(ranking_chart.properties(height=360), width="stretch")
        st.caption("Ranking directo para decidir qué atender primero sin revisar toda la tabla.")


# ================================================================
#  INICIALIZACIÓN Y CONEXIÓN
# ================================================================

def inicializar_db():
    """Crea la base de datos si no existe"""
    if APP_DB_BACKEND != "sqlite":
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

    CREATE TABLE IF NOT EXISTS cotizaciones_externas (
        id_sync INTEGER PRIMARY KEY AUTOINCREMENT,
        id_cotizacion INTEGER NOT NULL,
        proveedor TEXT NOT NULL,
        external_quote_id TEXT,
        playbook TEXT,
        api_url TEXT,
        request_payload TEXT,
        response_payload TEXT,
        estado_sync TEXT DEFAULT 'importada',
        fecha_sync TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id_cotizacion) REFERENCES cotizaciones(id_cotizacion)
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
    CREATE INDEX IF NOT EXISTS idx_cotizaciones_externas_cotizacion ON cotizaciones_externas(id_cotizacion);
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


def registrar_sync_cotizacion_externa(
    con,
    id_cotizacion,
    proveedor,
    api_url,
    playbook,
    request_payload,
    response_payload,
    external_quote_id=None,
    estado_sync="importada",
):
    con.execute(
        """
        INSERT INTO cotizaciones_externas
        (id_cotizacion, proveedor, external_quote_id, playbook, api_url,
         request_payload, response_payload, estado_sync)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            id_cotizacion,
            proveedor,
            external_quote_id,
            playbook,
            api_url,
            json.dumps(request_payload, ensure_ascii=False, sort_keys=True),
            json.dumps(response_payload, ensure_ascii=False, sort_keys=True),
            estado_sync,
        ),
    )
    con.commit()


def obtener_nodos_integracion_demo(con):
    return pd.read_sql("""
        SELECT
            'empresa' AS nodo_tipo,
            e.id_empresa AS nodo_id,
            COALESCE(NULLIF(e.rfc, ''), 'EMP-' || e.id_empresa) AS clave_negocio,
            e.nombre AS titulo,
            COALESCE(e.sector, 'Sin sector') AS subtitulo,
            'registrada' AS estado,
            NULL AS monto,
            NULL AS moneda,
            e.fecha_alta AS fecha_evento
        FROM empresas e

        UNION ALL

        SELECT
            'prospecto' AS nodo_tipo,
            p.id_prospecto AS nodo_id,
            'PROS-' || p.id_prospecto AS clave_negocio,
            e.nombre AS titulo,
            COALESCE(c.nombre, 'Sin contacto') AS subtitulo,
            CASE WHEN p.es_cliente = 1 THEN 'convertido' ELSE COALESCE(p.estado, 'Activo') END AS estado,
            NULL AS monto,
            NULL AS moneda,
            p.fecha_creacion AS fecha_evento
        FROM prospectos p
        JOIN empresas e ON e.id_empresa = p.id_empresa
        LEFT JOIN contactos c ON c.id_contacto = p.id_contacto

        UNION ALL

        SELECT
            'oportunidad' AS nodo_tipo,
            o.id_oportunidad AS nodo_id,
            'OP-' || o.id_oportunidad AS clave_negocio,
            o.nombre AS titulo,
            e.nombre AS subtitulo,
            COALESCE(o.etapa, 'Sin etapa') AS estado,
            o.monto_estimado AS monto,
            'MXN' AS moneda,
            o.fecha_creacion AS fecha_evento
        FROM oportunidades o
        JOIN prospectos p ON p.id_prospecto = o.id_prospecto
        JOIN empresas e ON e.id_empresa = p.id_empresa

        UNION ALL

        SELECT
            'cotizacion' AS nodo_tipo,
            c.id_cotizacion AS nodo_id,
            'COT-' || c.id_cotizacion AS clave_negocio,
            'Cotización ' || c.id_cotizacion AS titulo,
            o.nombre AS subtitulo,
            COALESCE(c.estado, 'Borrador') AS estado,
            c.monto_total AS monto,
            c.moneda AS moneda,
            c.fecha_creacion AS fecha_evento
        FROM cotizaciones c
        JOIN oportunidades o ON o.id_oportunidad = c.id_oportunidad

        UNION ALL

        SELECT
            'orden_compra' AS nodo_tipo,
            oc.id_oc AS nodo_id,
            COALESCE(NULLIF(oc.numero_oc, ''), 'OC-' || oc.id_oc) AS clave_negocio,
            COALESCE(NULLIF(oc.numero_oc, ''), 'OC-' || oc.id_oc) AS titulo,
            o.nombre AS subtitulo,
            CASE WHEN EXISTS (SELECT 1 FROM facturas f WHERE f.id_oc = oc.id_oc) THEN 'facturada' ELSE 'pendiente' END AS estado,
            oc.monto_oc AS monto,
            oc.moneda AS moneda,
            oc.fecha_oc AS fecha_evento
        FROM ordenes_compra oc
        JOIN oportunidades o ON o.id_oportunidad = oc.id_oportunidad

        UNION ALL

        SELECT
            'factura' AS nodo_tipo,
            f.id_factura AS nodo_id,
            COALESCE(NULLIF(f.uuid, ''), 'FACT-' || f.id_factura) AS clave_negocio,
            COALESCE(NULLIF(TRIM(COALESCE(f.serie, '') || CASE WHEN COALESCE(f.folio, '') <> '' THEN '-' || f.folio ELSE '' END), ''), COALESCE(f.uuid, 'FACT-' || f.id_factura)) AS titulo,
            COALESCE(NULLIF(oc.numero_oc, ''), 'OC-' || oc.id_oc) AS subtitulo,
            'emitida' AS estado,
            f.monto_total AS monto,
            f.moneda AS moneda,
            f.fecha_emision AS fecha_evento
        FROM facturas f
        JOIN ordenes_compra oc ON oc.id_oc = f.id_oc
    """, con)


def obtener_aristas_integracion_demo(con):
    return pd.read_sql("""
        SELECT
            'empresa' AS nodo_origen_tipo,
            p.id_empresa AS nodo_origen_id,
            e.nombre AS origen_titulo,
            'tiene_prospecto' AS tipo_relacion,
            'prospecto' AS nodo_destino_tipo,
            p.id_prospecto AS nodo_destino_id,
            'PROS-' || p.id_prospecto AS destino_titulo
        FROM prospectos p
        JOIN empresas e ON e.id_empresa = p.id_empresa

        UNION ALL

        SELECT
            'prospecto' AS nodo_origen_tipo,
            o.id_prospecto AS nodo_origen_id,
            'PROS-' || o.id_prospecto AS origen_titulo,
            'evoluciona_a' AS tipo_relacion,
            'oportunidad' AS nodo_destino_tipo,
            o.id_oportunidad AS nodo_destino_id,
            o.nombre AS destino_titulo
        FROM oportunidades o

        UNION ALL

        SELECT
            'oportunidad' AS nodo_origen_tipo,
            c.id_oportunidad AS nodo_origen_id,
            o.nombre AS origen_titulo,
            'genera' AS tipo_relacion,
            'cotizacion' AS nodo_destino_tipo,
            c.id_cotizacion AS nodo_destino_id,
            'Cotización ' || c.id_cotizacion AS destino_titulo
        FROM cotizaciones c
        JOIN oportunidades o ON o.id_oportunidad = c.id_oportunidad

        UNION ALL

        SELECT
            'oportunidad' AS nodo_origen_tipo,
            oc.id_oportunidad AS nodo_origen_id,
            o.nombre AS origen_titulo,
            'recibe_oc' AS tipo_relacion,
            'orden_compra' AS nodo_destino_tipo,
            oc.id_oc AS nodo_destino_id,
            COALESCE(NULLIF(oc.numero_oc, ''), 'OC-' || oc.id_oc) AS destino_titulo
        FROM ordenes_compra oc
        JOIN oportunidades o ON o.id_oportunidad = oc.id_oportunidad

        UNION ALL

        SELECT
            'orden_compra' AS nodo_origen_tipo,
            f.id_oc AS nodo_origen_id,
            COALESCE(NULLIF(oc.numero_oc, ''), 'OC-' || oc.id_oc) AS origen_titulo,
            'sustenta_factura' AS tipo_relacion,
            'factura' AS nodo_destino_tipo,
            f.id_factura AS nodo_destino_id,
            COALESCE(NULLIF(f.uuid, ''), 'FACT-' || f.id_factura) AS destino_titulo
        FROM facturas f
        JOIN ordenes_compra oc ON oc.id_oc = f.id_oc
    """, con)


def obtener_pipeline_integracion_demo(con):
    return pd.read_sql("""
        SELECT
            COALESCE(o.etapa, 'Sin etapa') AS etapa,
            COUNT(DISTINCT o.id_oportunidad) AS oportunidades_total,
            ROUND(COALESCE(SUM(o.monto_estimado), 0), 2) AS monto_pipeline,
            COUNT(DISTINCT c.id_cotizacion) AS cotizaciones_total,
            COUNT(DISTINCT oc.id_oc) AS ordenes_compra_total,
            COUNT(DISTINCT f.id_factura) AS facturas_total
        FROM oportunidades o
        LEFT JOIN cotizaciones c ON c.id_oportunidad = o.id_oportunidad
        LEFT JOIN ordenes_compra oc ON oc.id_oportunidad = o.id_oportunidad
        LEFT JOIN facturas f ON f.id_oc = oc.id_oc
        GROUP BY COALESCE(o.etapa, 'Sin etapa')
        ORDER BY CASE COALESCE(o.etapa, 'Sin etapa')
            WHEN 'Calificación' THEN 1
            WHEN 'Propuesta' THEN 2
            WHEN 'Negociación' THEN 3
            WHEN 'Cierre' THEN 4
            WHEN 'Ganada' THEN 5
            WHEN 'Perdida' THEN 6
            ELSE 7
        END
    """, con)


def obtener_cxc_integracion_demo(con):
    return pd.read_sql("""
        SELECT
            f.id_factura,
            COALESCE(NULLIF(f.uuid, ''), 'FACT-' || f.id_factura) AS uuid,
            e.nombre AS cliente,
            COALESCE(NULLIF(oc.numero_oc, ''), 'OC-' || oc.id_oc) AS numero_oc,
            f.fecha_emision,
            ROUND(COALESCE(f.monto_total, 0), 2) AS total_factura,
            0.00 AS total_pagado,
            ROUND(COALESCE(f.monto_total, 0), 2) AS saldo_pendiente,
            CASE
                WHEN julianday('now') - julianday(f.fecha_emision) > 60 THEN 'vencido_60+'
                WHEN julianday('now') - julianday(f.fecha_emision) > 30 THEN 'vencido_30+'
                ELSE 'sin_pagos_legacy'
            END AS estado_cobranza,
            CAST(julianday('now') - julianday(f.fecha_emision) AS INTEGER) AS antiguedad_dias
        FROM facturas f
        JOIN ordenes_compra oc ON oc.id_oc = f.id_oc
        JOIN oportunidades o ON o.id_oportunidad = oc.id_oportunidad
        JOIN prospectos p ON p.id_prospecto = o.id_prospecto
        JOIN empresas e ON e.id_empresa = p.id_empresa
        ORDER BY f.fecha_emision DESC, f.id_factura DESC
    """, con)


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
    
    # Modo Oscuro (Nivel 2 UX)
    if UX_COMPONENTS_DISPONIBLES:
        dark_mode_toggle()
    
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
            "📦 Import/Export",
            "🧭 Demo Integración",
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
    
    # Sistema de Notificaciones Inteligente (Nivel 2)
    if UX_COMPONENTS_DISPONIBLES:
        try:
            con_notif = conectar()
            notification_center(con_notif)
            con_notif.close()
        except Exception as e:
            # Si falla, no romper el sidebar
            print(f"⚠️ Error en notificaciones: {e}")
    
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
    
    # Agregar navegación mejorada y shortcuts
    if UX_COMPONENTS_DISPONIBLES:
        smart_navigation_menu("Dashboard")
        keyboard_shortcuts_handler()
    
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
    
    # Indicadores de completitud con gráfico mejorado
    if UX_COMPONENTS_DISPONIBLES:
        try:
            metricas = obtener_metricas_helper(con)
            metricas_display = {
                "Empresas sin contacto": metricas.get("empresas_sin_contacto", 0),
                "Prospectos sin oportunidad": metricas.get("prospectos_sin_oportunidad", 0),
                "Oportunidades sin cotización": metricas.get("oportunidades_sin_cotizacion", 0),
                "Ganadas sin OC": metricas.get("ganadas_sin_oc", 0),
                "OCs sin factura": metricas.get("ocs_sin_factura", 0)
            }
            grafico_metricas_dashboard(metricas_display)
        except Exception as e:
            print(f"Error en gráfico de métricas: {e}")
    
    st.divider()
    
    # Widget de estado CFDI
    if CFDI_DISPONIBLE:
        try:
            widget_estado_cfdi()
            st.divider()
        except Exception:
            pass  # Si falla el widget, no romper el dashboard
    
    # Pipeline por etapa con visualización mejorada
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
        # Usar funnel interactivo si está disponible
        if UX_COMPONENTS_DISPONIBLES:
            try:
                df_opor = pd.read_sql("SELECT * FROM oportunidades WHERE etapa NOT IN ('Perdida')", con)
                pipeline_funnel_interactive(df_opor)
            except Exception as e:
                print(f"Error en funnel interactivo: {e}")
                # Fallback a visualización básica
                col_pipe1, col_pipe2 = st.columns(2)
                with col_pipe1:
                    st.dataframe(pipeline, width="stretch")
                with col_pipe2:
                    chart_data = pipeline.set_index('etapa')['monto_total']
                    st.bar_chart(chart_data)
        else:
            # Visualización básica original
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
    
    # Navegación mejorada y shortcuts
    if UX_COMPONENTS_DISPONIBLES:
        smart_navigation_menu("Identidad")
        keyboard_shortcuts_handler()
        contextual_quick_actions("empresas")
    
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
                    con.close()
                else:
                    cur.execute("INSERT INTO empresas (nombre, rfc, sector, telefono, correo) VALUES (?, ?, ?, ?, ?)",
                               (nombre, rfc, sector, telefono, correo))
                    con.commit()
                    registrar_evento(con, "empresa", cur.lastrowid, "CREAR", f"Empresa: {nombre}")
                    con.close()
                    st.success(f"✅ Empresa '{nombre}' creada")
                    st.rerun()
        
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
                # Búsqueda avanzada si está disponible
                if UX_COMPONENTS_DISPONIBLES:
                    empresas_filtradas = advanced_search_widget(
                        empresas,
                        entity_name="Empresas",
                        search_columns=['nombre', 'rfc', 'sector'],
                        category_filters={'sector': 'Sector'}
                    )
                    st.dataframe(empresas_filtradas, width="stretch", hide_index=True)
                    
                    # Operaciones masivas
                    st.divider()
                    
                    def eliminar_empresas(ids):
                        con_bulk = conectar()
                        cur = con_bulk.cursor()
                        for id_empresa in ids:
                            # Verificar si tiene contactos
                            cur.execute("SELECT COUNT(*) as total FROM contactos WHERE id_empresa = ?", (id_empresa,))
                            if cur.fetchone()["total"] > 0:
                                raise Exception(f"Empresa ID {id_empresa} tiene contactos asociados")
                            cur.execute("DELETE FROM empresas WHERE id_empresa = ?", (id_empresa,))
                            registrar_evento(con_bulk, "empresa", id_empresa, "ELIMINAR", "Eliminación masiva")
                        con_bulk.commit()
                        con_bulk.close()
                    
                    bulk_operations_widget(
                        empresas_filtradas,
                        entity_name="Empresas",
                        id_column='id_empresa',
                        name_column='nombre',
                        on_delete_callback=eliminar_empresas,
                        updatable_fields=['sector', 'telefono', 'correo']
                    )
                else:
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
                    con.close()
                    st.success(f"✅ Contacto '{nombre_c}' creado")
                    st.rerun()
            
            with col2:
                con = conectar()
                contactos = pd.read_sql("""
                    SELECT c.id_contacto, e.nombre as empresa, c.nombre, c.correo, c.puesto, c.telefono
                    FROM contactos c
                    JOIN empresas e ON e.id_empresa = c.id_empresa
                    ORDER BY c.fecha_alta DESC
                """, con)
                con.close()
                
                if len(contactos) > 0:
                    # Búsqueda avanzada si está disponible
                    if UX_COMPONENTS_DISPONIBLES:
                        contactos_filtrados = advanced_search_widget(
                            contactos,
                            entity_name="Contactos",
                            search_columns=['nombre', 'correo', 'empresa', 'puesto'],
                            category_filters={'empresa': 'Empresa'}
                        )
                        st.dataframe(contactos_filtrados, width="stretch", hide_index=True)
                        
                        # Operaciones masivas
                        st.divider()
                        
                        def eliminar_contactos(ids):
                            con_bulk = conectar()
                            cur = con_bulk.cursor()
                            for id_contacto in ids:
                                cur.execute("DELETE FROM contactos WHERE id_contacto = ?", (id_contacto,))
                                registrar_evento(con_bulk, "contacto", id_contacto, "ELIMINAR", "Eliminación masiva")
                            con_bulk.commit()
                            con_bulk.close()
                        
                        bulk_operations_widget(
                            contactos_filtrados,
                            entity_name="Contactos",
                            id_column='id_contacto',
                            name_column='nombre',
                            on_delete_callback=eliminar_contactos,
                            updatable_fields=['correo', 'telefono', 'puesto']
                        )
                    else:
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
                # Selector de empresa FUERA del form para que el selectbox de contacto se actualice al cambiar empresa
                if "prospecto_empresa_nombre" not in st.session_state:
                    st.session_state["prospecto_empresa_nombre"] = empresas_validas.iloc[0]["nombre"]
                if st.session_state["prospecto_empresa_nombre"] not in empresas_validas["nombre"].tolist():
                    st.session_state["prospecto_empresa_nombre"] = empresas_validas.iloc[0]["nombre"]

                emp_sel = st.selectbox(
                    "Empresa *",
                    empresas_validas["nombre"].tolist(),
                    key="prospecto_empresa_nombre",
                )
                id_emp = int(empresas_validas[empresas_validas["nombre"] == emp_sel]["id_empresa"].iloc[0])

                con = conectar()
                contactos_emp = pd.read_sql(
                    "SELECT id_contacto, nombre, puesto FROM contactos WHERE id_empresa = ?",
                    con, params=(id_emp,)
                )
                con.close()

                if len(contactos_emp) == 0:
                    st.warning("⚠️ Esta empresa no tiene contactos")
                else:
                    cont_display = [
                        f"{row['nombre']} ({row['puesto']})" if row["puesto"] else row["nombre"]
                        for _, row in contactos_emp.iterrows()
                    ]
                    with st.form("form_prospecto"):
                        st.caption(f"Empresa seleccionada: {emp_sel}")
                        cont_sel = st.selectbox("Contacto *", cont_display)
                        id_cont = int(contactos_emp.iloc[cont_display.index(cont_sel)]["id_contacto"])
                        origen = st.text_input("Origen", placeholder="Campaña, Referencia, etc.")
                        submit_p = st.form_submit_button("✅ Generar Prospecto")
                        
                        if submit_p:
                            con = conectar()
                            cur = con.cursor()
                            cur.execute(
                                "SELECT COUNT(*) as total FROM prospectos WHERE id_empresa=? AND id_contacto=?",
                                (id_emp, id_cont)
                            )
                            if cur.fetchone()["total"] > 0:
                                con.close()
                                st.error(
                                    f"❌ Ya existe un prospecto o cliente con '{emp_sel}' y ese contacto. "
                                    "Si necesitas una nueva oportunidad, créala directamente en N2."
                                )
                            else:
                                cur.execute("INSERT INTO prospectos (id_empresa, id_contacto, origen, estado) VALUES (?, ?, ?, 'Activo')",
                                           (id_emp, id_cont, origen))
                                con.commit()
                                registrar_evento(con, "prospecto", cur.lastrowid, "CREAR", f"Prospecto: {emp_sel}")
                                con.close()
                                st.success(f"✅ Prospecto generado (ID: {cur.lastrowid})")
                                st.rerun()
            
            with col2:
                con = conectar()
                prospectos = pd.read_sql("""
                    SELECT p.id_prospecto, e.nombre as empresa, c.nombre as contacto,
                           p.estado, p.origen, p.es_cliente, p.fecha_creacion
                    FROM prospectos p
                    JOIN empresas e ON e.id_empresa = p.id_empresa
                    JOIN contactos c ON c.id_contacto = p.id_contacto
                    ORDER BY p.es_cliente ASC, p.fecha_creacion DESC
                    LIMIT 20
                """, con)
                con.close()
                
                if len(prospectos) > 0:
                    def _badge(row):
                        return "🏢 Cliente" if row["es_cliente"] == 1 else "🔵 Prospecto"
                    prospectos["tipo"] = prospectos.apply(_badge, axis=1)
                    st.dataframe(
                        prospectos.drop(columns=["es_cliente"]).rename(columns={"tipo": "Tipo"}),
                        width="stretch", hide_index=True
                    )
                else:
                    st.info("No hay prospectos activos")


# ================================================================
#  N2: TRANSACCIÓN (Oportunidades → Cotizaciones)
# ================================================================

elif menu == "💼 N2: Transacción":
    st.markdown('<div class="main-header">💼 Núcleo 2: Transacción</div>', unsafe_allow_html=True)
    st.markdown("⬆️ **Flujo:** Prospecto → Oportunidad → Cotización → Ganar oportunidad → Marcar OC recibida → Ir a N3 para registrar OC y Factura")
    
    tab1, tab2 = st.tabs(["🎯 Oportunidades", "💰 Cotizaciones"])
    
    # TAB: Oportunidades (REGLAS R2, R3, R4)
    with tab1:
        st.subheader("Gestión de Oportunidades")
        st.info("🔒 **REGLAS:** R2 (solo desde prospectos) | R3 (conversión automática a cliente al ganar) | R4 (marcar OC aquí es la pre-aprobación; el documento OC se registra en N3)")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            con = conectar()
            prospectos_disp = pd.read_sql("""
                SELECT p.id_prospecto, e.nombre as empresa, c.nombre as contacto,
                       p.es_cliente
                FROM prospectos p
                JOIN empresas e ON e.id_empresa = p.id_empresa
                JOIN contactos c ON c.id_contacto = p.id_contacto
                WHERE p.estado = 'Activo'
                ORDER BY p.es_cliente ASC, p.fecha_creacion DESC
            """, con)
            con.close()
            
            if len(prospectos_disp) == 0:
                st.warning("⚠️ No hay prospectos ni clientes activos. Crea uno en N1: Identidad")
            else:
                with st.form("form_oportunidad"):
                    pros_display = [
                        f"{'\U0001f3e2 ' if row['es_cliente'] else ''}{row['empresa']} - {row['contacto']}"
                        for _, row in prospectos_disp.iterrows()
                    ]
                    pros_sel = st.selectbox("Empresa / Contacto *", pros_display)
                    id_pros = int(prospectos_disp.iloc[pros_display.index(pros_sel)]["id_prospecto"])
                    
                    nombre_op = st.text_input("Nombre de oportunidad *", placeholder="Venta de software CRM")
                    monto = st.number_input("Monto estimado *", min_value=0.01, step=1000.0)
                    etapa = st.selectbox("Etapa", ["Calificación", "Propuesta", "Negociación", "Cierre"])
                    probabilidad = st.slider("Probabilidad (%)", 0, 100, 25, 5)
                    fecha_cierre = st.date_input("Fecha estimada cierre")
                    submit_op = st.form_submit_button("✅ Crear Oportunidad")
                    
                    if submit_op:
                        if not nombre_op:
                            st.error("❌ El nombre de oportunidad es obligatorio.")
                        elif monto <= 0:
                            st.error("❌ El monto estimado debe ser mayor a 0.")
                        else:
                            con = conectar()
                            cur = con.cursor()
                            cur.execute("""
                                INSERT INTO oportunidades 
                                (id_prospecto, nombre, etapa, probabilidad, monto_estimado, fecha_estimada_cierre)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (id_pros, nombre_op, etapa, probabilidad, monto, fecha_cierre.isoformat()))
                            con.commit()
                            registrar_evento(con, "oportunidad", cur.lastrowid, "CREAR", f"Oportunidad: {nombre_op}")
                            con.close()
                            st.success(f"✅ Oportunidad '{nombre_op}' creada")
                            st.rerun()
        
        with col2:
            con = conectar()
            oportunidades = pd.read_sql("""
                SELECT o.id_oportunidad, o.nombre, o.etapa, o.probabilidad,
                       ROUND(o.monto_estimado, 2) as monto, o.oc_recibida,
                       e.nombre as empresa, o.fecha_estimada_cierre
                FROM oportunidades o
                JOIN prospectos p ON p.id_prospecto = o.id_prospecto
                JOIN empresas e ON e.id_empresa = p.id_empresa
                ORDER BY o.fecha_creacion DESC
            """, con)
            con.close()
            
            if len(oportunidades) > 0:
                # Búsqueda avanzada si está disponible
                if UX_COMPONENTS_DISPONIBLES:
                    oportunidades_filtradas = advanced_search_widget(
                        oportunidades,
                        entity_name="Oportunidades",
                        search_columns=['nombre', 'empresa'],
                        category_filters={'etapa': 'Etapa', 'empresa': 'Empresa'}
                    )
                    st.dataframe(oportunidades_filtradas, width="stretch", hide_index=True)
                    
                    # Operaciones masivas
                    st.divider()
                    
                    def eliminar_oportunidades(ids):
                        con_bulk = conectar()
                        cur = con_bulk.cursor()
                        for id_oportunidad in ids:
                            cur.execute("SELECT COUNT(*) as total FROM cotizaciones WHERE id_oportunidad = ?", (id_oportunidad,))
                            if cur.fetchone()["total"] > 0:
                                raise Exception(f"Oportunidad ID {id_oportunidad} tiene cotizaciones asociadas")
                            cur.execute("SELECT COUNT(*) as total FROM ordenes_compra WHERE id_oportunidad = ?", (id_oportunidad,))
                            if cur.fetchone()["total"] > 0:
                                raise Exception(f"Oportunidad ID {id_oportunidad} tiene OCs asociadas")
                            cur.execute("DELETE FROM oportunidades WHERE id_oportunidad = ?", (id_oportunidad,))
                            registrar_evento(con_bulk, "oportunidad", id_oportunidad, "ELIMINAR", "Eliminación masiva")
                        con_bulk.commit()
                        con_bulk.close()
                    
                    bulk_operations_widget(
                        oportunidades_filtradas,
                        entity_name="Oportunidades",
                        id_column='id_oportunidad',
                        name_column='nombre',
                        on_delete_callback=eliminar_oportunidades,
                        updatable_fields=['etapa', 'probabilidad', 'fecha_estimada_cierre']
                    )
                else:
                    st.dataframe(oportunidades, width="stretch", hide_index=True)
                
                # Acciones sobre oportunidades
                st.divider()
                st.markdown("**Acciones sobre oportunidad:**")

                # Construir opciones desde el dataframe ya cargado (evita que el usuario adivine IDs)
                _odf = oportunidades_filtradas if UX_COMPONENTS_DISPONIBLES else oportunidades
                _opor_opciones = {
                    int(row["id_oportunidad"]): (
                        f"#{row['id_oportunidad']} · {row['nombre']} · {row['etapa']} · {row['empresa']}"
                    )
                    for _, row in _odf.iterrows()
                }
                opor_sel_id = st.selectbox(
                    "Selecciona oportunidad",
                    list(_opor_opciones.keys()),
                    format_func=lambda k: _opor_opciones[k],
                    key="oportunidad_accion_sel",
                )

                col_a1, col_a2, col_a3 = st.columns(3)

                with col_a1:
                    if st.button("🎉 Marcar como Ganada (REGLA R3)", width="stretch"):
                        con = conectar()
                        cur = con.cursor()
                        cur.execute("SELECT etapa FROM oportunidades WHERE id_oportunidad=?", (opor_sel_id,))
                        row_act = cur.fetchone()
                        if row_act is None:
                            con.close()
                            st.error(f"❌ No existe la oportunidad con ID {opor_sel_id}")
                        elif row_act["etapa"] == "Ganada":
                            con.close()
                            st.warning("⚠️ Esta oportunidad ya está marcada como Ganada.")
                        elif row_act["etapa"] == "Perdida":
                            con.close()
                            st.error("❌ No se puede reabrir una oportunidad Perdida.")
                        else:
                            cur.execute("UPDATE oportunidades SET etapa='Ganada', probabilidad=100 WHERE id_oportunidad=?",
                                       (opor_sel_id,))
                            # REGLA R3: Convertir prospecto a cliente
                            cur.execute("""
                                UPDATE prospectos SET es_cliente=1, fecha_conversion_cliente=?
                                WHERE id_prospecto = (SELECT id_prospecto FROM oportunidades WHERE id_oportunidad=?)
                            """, (date.today().isoformat(), opor_sel_id))
                            con.commit()
                            registrar_evento(con, "oportunidad", opor_sel_id, "GANAR", "Oportunidad ganada → Cliente convertido")
                            con.close()
                            st.success("✅ Oportunidad ganada y prospecto convertido a cliente")
                            st.rerun()

                with col_a2:
                    if st.button("📋 Marcar OC Recibida (REGLA R4)", width="stretch"):
                        try:
                            con = conectar()
                            cur = con.cursor()
                            cur.execute("SELECT etapa, oc_recibida FROM oportunidades WHERE id_oportunidad=?", (opor_sel_id,))
                            row_opor = cur.fetchone()
                            if row_opor is None:
                                raise ValueError(f"No existe la oportunidad con ID {opor_sel_id}")
                            if row_opor["etapa"] != "Ganada":
                                raise ValueError(f"Solo se puede marcar OC en oportunidades Ganadas (etapa actual: {row_opor['etapa']})")
                            if row_opor["oc_recibida"] == 1:
                                st.warning("⚠️ Esta oportunidad ya tiene OC marcada como recibida.")
                            else:
                                cur.execute("UPDATE oportunidades SET oc_recibida=1 WHERE id_oportunidad=?", (opor_sel_id,))
                                con.commit()
                                registrar_evento(con, "oportunidad", opor_sel_id, "OC_RECIBIDA", "OC marcada como recibida")
                                st.success("✅ OC recibida marcada. Ve a N3: Facturación para registrar el documento.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al marcar OC: {str(e)}")
                        finally:
                            if 'con' in locals():
                                con.close()

                with col_a3:
                    if st.button("❌ Marcar como Perdida", width="stretch"):
                        con = conectar()
                        cur = con.cursor()
                        cur.execute("SELECT etapa FROM oportunidades WHERE id_oportunidad=?", (opor_sel_id,))
                        row_act = cur.fetchone()
                        if row_act is None:
                            con.close()
                            st.error(f"❌ No existe la oportunidad con ID {opor_sel_id}")
                        elif row_act["etapa"] == "Perdida":
                            con.close()
                            st.warning("⚠️ Esta oportunidad ya está marcada como Perdida.")
                        elif row_act["etapa"] == "Ganada":
                            con.close()
                            st.error("❌ No se puede marcar como Perdida una oportunidad ya Ganada.")
                        else:
                            cur.execute("UPDATE oportunidades SET etapa='Perdida', probabilidad=0 WHERE id_oportunidad=?",
                                       (opor_sel_id,))
                            con.commit()
                            registrar_evento(con, "oportunidad", opor_sel_id, "ACTUALIZAR", "Oportunidad marcada como Perdida")
                            con.close()
                            st.success("❌ Oportunidad marcada como Perdida")
                            st.rerun()
            else:
                st.info("No hay oportunidades registradas")
    
    # TAB: Cotizaciones
    with tab2:
        st.subheader("Gestión de Cotizaciones")
        st.info("🔒 **Modos:** Mínimo (solo monto) | Genérico (monto + descripción de ítems) | Externo (cálculo DynamiQuote)")

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
                if "cotizacion_items_dynamiquote_json" not in st.session_state:
                    st.session_state["cotizacion_items_dynamiquote_json"] = DEFAULT_DYNAMIQUOTE_ITEMS_JSON
                if "cotizacion_oportunidad_id" not in st.session_state:
                    st.session_state["cotizacion_oportunidad_id"] = int(opor_para_cot.iloc[0]["id_oportunidad"])

                opciones_oportunidad = [int(row["id_oportunidad"]) for _, row in opor_para_cot.iterrows()]
                if st.session_state["cotizacion_oportunidad_id"] not in opciones_oportunidad:
                    st.session_state["cotizacion_oportunidad_id"] = opciones_oportunidad[0]

                oportunidades_por_id = {
                    int(row["id_oportunidad"]): {
                        "nombre": row["nombre"],
                        "etapa": row["etapa"],
                        "monto": row["monto"],
                    }
                    for _, row in opor_para_cot.iterrows()
                }

                id_opor = st.selectbox(
                    "Oportunidad relacionada *",
                    opciones_oportunidad,
                    key="cotizacion_oportunidad_id",
                    format_func=lambda op_id: (
                        f"#{op_id} · {oportunidades_por_id[op_id]['nombre']} · "
                        f"{oportunidades_por_id[op_id]['etapa']} · ${oportunidades_por_id[op_id]['monto']}"
                    ),
                    help="La cotización se guardará enlazada a esta oportunidad.",
                )
                oportunidad_seleccionada = oportunidades_por_id[id_opor]
                st.caption(
                    f"Cotización vinculada a oportunidad #{id_opor}: {oportunidad_seleccionada['nombre']} | "
                    f"Etapa: {oportunidad_seleccionada['etapa']} | Monto estimado: ${oportunidad_seleccionada['monto']}"
                )
                if oportunidad_seleccionada["etapa"] == "Ganada":
                    st.warning(
                        "⚠️ Esta oportunidad ya está **Ganada**. "
                        "Normalmente las cotizaciones se generan antes del cierre. "
                        "Puedes continuar si necesitas una cotización complementaria o rectificatoria."
                    )

                mode_helps = {
                    "minimo": "⚡ Monto total único, sin desglose de ítems.",
                    "generico": "📋 Monto manual con descripción libre de ítems (texto).",
                    "externo": "🔗 Cálculo automático vía DynamiQuote API (líneas con costo/precio).",
                }
                modo = st.selectbox(
                    "Modo *",
                    ["minimo", "generico", "externo"],
                    key="cotizacion_modo_selector",
                    help=mode_helps.get(st.session_state.get("cotizacion_modo_selector", "minimo"), ""),
                )
                st.caption(mode_helps[modo])
                with st.form("form_cotizacion"):
                    st.caption(f"Oportunidad bloqueada para esta cotización: #{id_opor}")
                    st.caption(f"Modo seleccionado: {modo}")
                    dynamiquote_api_url = DEFAULT_DYNAMIQUOTE_API_URL
                    playbook_name = DEFAULT_PLAYBOOK_NAME
                    items_dynamiquote_json = ""
                    items_genericos = ""
                    if modo == "generico":
                        st.caption("📋 Describe los ítems manualmente. El monto se captura abajo.")
                        items_genericos = st.text_area(
                            "Descripción de ítems",
                            placeholder="Ej:\n- 10 licencias anuales $1,500 c/u\n- 1 implementación $8,000",
                            height=120,
                            help="Texto libre que se guarda en notas para trazabilidad.",
                        )
                    if modo == "externo":
                        st.caption("DynamiQuote calcula el total desde líneas. El monto manual se desactiva en este modo.")
                        dynamiquote_api_url = st.text_input(
                            "DynamiQuote API URL",
                            value=DEFAULT_DYNAMIQUOTE_API_URL,
                            help="Ejemplo: http://127.0.0.1:8000",
                        ).strip() or DEFAULT_DYNAMIQUOTE_API_URL
                        playbook_name = st.selectbox(
                            "Playbook DynamiQuote",
                            ["General", "MSP", "Gobierno", "Penetracion"],
                            index=0,
                        )
                        st.caption("Puedes editar el ejemplo precargado o reemplazarlo con tus líneas reales.")
                        items_dynamiquote_json = st.text_area(
                            "Items JSON *",
                            height=220,
                            value=st.session_state["cotizacion_items_dynamiquote_json"],
                            key="cotizacion_items_dynamiquote_json",
                            help="DynamiQuote consume quantity, cost_unit y price_unit. sku y description se guardan en la auditoría local.",
                        )
                    if modo == "externo":
                        st.caption("💡 El monto será calculado por DynamiQuote al enviar.")
                        monto_cot = 0.0
                    else:
                        monto_cot = st.number_input(
                            "Monto total *",
                            min_value=0.0,
                            step=100.0,
                        )
                    moneda = st.selectbox("Moneda", ["MXN", "USD", "EUR"])
                    notas = st.text_area("Notas", placeholder="Descripción de la cotización")
                    submit_cot = st.form_submit_button("✅ Crear Cotización")
                    
                    if submit_cot:
                        con = None
                        try:
                            fuente = "manual"
                            monto_final = monto_cot
                            notas_finales = notas
                            resultado_externo = None

                            if modo == "externo":
                                resultado_externo = importar_cotizacion_desde_dynamiquote(
                                    raw_items_json=items_dynamiquote_json,
                                    playbook_name=playbook_name,
                                    api_url=dynamiquote_api_url,
                                )
                                monto_final = resultado_externo["total_revenue"]
                                fuente = "dynamiquote_api"
                                resumen_externo = (
                                    f"DynamiQuote | playbook={resultado_externo['playbook_name']} | "
                                    f"lineas={resultado_externo['line_count']} | "
                                    f"margen={resultado_externo['margin_pct']}% | "
                                    f"health={resultado_externo['health_summary']}"
                                )
                                notas_finales = f"{notas}\n\n{resumen_externo}".strip()
                            elif modo == "generico":
                                if monto_cot <= 0:
                                    raise ValueError("El monto total debe ser mayor a 0.")
                                if items_genericos.strip():
                                    notas_finales = f"{notas}\n\n--- Ítems ---\n{items_genericos}".strip()
                            elif monto_cot <= 0:
                                raise ValueError("El monto total debe ser mayor a 0.")

                            data = {
                                "id_oportunidad": id_opor,
                                "modo": modo,
                                "fuente": fuente,
                                "monto": monto_final,
                                "moneda": moneda,
                                # Timestamp asegura unicidad del hash aunque los datos sean idénticos
                                "ts": datetime.utcnow().isoformat(),
                            }
                            hash_int = hashlib.sha256(
                                json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
                            ).hexdigest()

                            con = conectar()
                            cur = con.cursor()
                            # Calcular versión: cuenta cotizaciones previas de esta oportunidad + 1
                            cur.execute(
                                "SELECT COUNT(*) as total FROM cotizaciones WHERE id_oportunidad = ?",
                                (id_opor,),
                            )
                            version_cot = cur.fetchone()["total"] + 1
                            cur.execute(
                                """
                                INSERT INTO cotizaciones
                                (id_oportunidad, modo, fuente, monto_total, moneda, version, estado, hash_integridad, notas)
                                VALUES (?, ?, ?, ?, ?, ?, 'Borrador', ?, ?)
                                """,
                                (id_opor, modo, fuente, monto_final, moneda, version_cot, hash_int, notas_finales),
                            )
                            con.commit()
                            cot_id = cur.lastrowid
                            cur.execute(
                                "INSERT INTO hash_registros (tabla_origen, id_registro, hash_sha256) VALUES ('cotizaciones', ?, ?)",
                                (cot_id, hash_int),
                            )
                            con.commit()

                            if resultado_externo is not None:
                                registrar_sync_cotizacion_externa(
                                    con=con,
                                    id_cotizacion=cot_id,
                                    proveedor="DynamiQuote",
                                    api_url=resultado_externo["api_url"],
                                    playbook=resultado_externo["playbook_name"],
                                    request_payload=resultado_externo["audit_payload"],
                                    response_payload=resultado_externo["response_payload"],
                                    external_quote_id=resultado_externo["external_quote_id"],
                                )
                                registrar_evento(
                                    con,
                                    "cotizacion",
                                    cot_id,
                                    "SYNC_DYNAMIQUOTE",
                                    (
                                        f"DynamiQuote importada | lineas={resultado_externo['line_count']} | "
                                        f"total={resultado_externo['total_revenue']} {moneda} | "
                                        f"health={resultado_externo['health_summary']}"
                                    ),
                                )
                            else:
                                registrar_evento(
                                    con,
                                    "cotizacion",
                                    cot_id,
                                    "CREAR",
                                    f"Cotización modo {modo} - ${monto_final} {moneda}",
                                )

                            mensaje = f"✅ Cotización creada con hash: {hash_int[:16]}..."
                            if resultado_externo is not None:
                                mensaje += (
                                    f" | DynamiQuote: {resultado_externo['line_count']} líneas, "
                                    f"margen {resultado_externo['margin_pct']}%"
                                )
                            st.success(mensaje)
                            st.rerun()
                        except (ValueError, DynamiQuoteError, requests.RequestException) as exc:
                            st.error(f"❌ No se pudo crear la cotización: {exc}")
                        finally:
                            if con is not None:
                                con.close()
        
        with col2:
            con = conectar()
            cotizaciones = pd.read_sql("""
                SELECT c.id_cotizacion, o.nombre as oportunidad, c.modo,
                    COALESCE(
                        (SELECT cx2.proveedor FROM cotizaciones_externas cx2
                         WHERE cx2.id_cotizacion = c.id_cotizacion
                         ORDER BY cx2.fecha_sync DESC LIMIT 1),
                        c.fuente, 'manual'
                    ) as fuente,
                    ROUND(c.monto_total, 2) as monto, c.moneda,
                    c.estado, c.version,
                    substr(c.hash_integridad, 1, 16) as hash
                FROM cotizaciones c
                JOIN oportunidades o ON o.id_oportunidad = c.id_oportunidad
                ORDER BY c.fecha_creacion DESC
                LIMIT 20
            """, con)
            con.close()

            if len(cotizaciones) > 0:
                st.dataframe(cotizaciones, width="stretch", hide_index=True)
                st.divider()
                st.markdown("**Cambiar estado de cotización:**")
                _cot_opciones = {
                    int(row["id_cotizacion"]): (
                        f"#{row['id_cotizacion']} · v{row['version']} · {row['oportunidad']} · "
                        f"${row['monto']} {row['moneda']} · [{row['estado']}]"
                    )
                    for _, row in cotizaciones.iterrows()
                }
                _cot_sel_id = st.selectbox(
                    "Cotización",
                    list(_cot_opciones.keys()),
                    format_func=lambda k: _cot_opciones[k],
                    key="cotizacion_estado_sel",
                )
                _estados_cot = ["Borrador", "Enviada", "Aprobada", "Rechazada", "Vencida"]
                _nuevo_estado = st.selectbox(
                    "Nuevo estado",
                    _estados_cot,
                    key="cotizacion_estado_nuevo",
                )
                if st.button("✏️ Actualizar Estado", key="btn_actualizar_estado_cot"):
                    con = conectar()
                    cur = con.cursor()
                    cur.execute(
                        "UPDATE cotizaciones SET estado = ? WHERE id_cotizacion = ?",
                        (_nuevo_estado, _cot_sel_id),
                    )
                    con.commit()
                    registrar_evento(con, "cotizacion", _cot_sel_id, "ESTADO", f"Estado → {_nuevo_estado}")
                    con.close()
                    st.success(f"✅ Estado actualizado a '{_nuevo_estado}'")
                    st.rerun()
            else:
                st.info("No hay cotizaciones registradas")


# ================================================================
#  N3: FACTURACIÓN (OC → Facturas)
# ================================================================

elif menu == "💰 N3: Facturación":
    st.markdown('<div class="main-header">💰 Núcleo 3: Facturación</div>', unsafe_allow_html=True)
    st.markdown("⬆️ **Flujo:** Oportunidad Ganada + OC marcada (N2) → Registrar OC → Registrar Factura")
    
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
            # Muestra todas las oportunidades Ganadas — oc_recibida ya no bloquea el acceso
            # El flag se setea automáticamente al registrar la primera OC desde este formulario
            opor_ganadas = pd.read_sql("""
                SELECT o.id_oportunidad, o.nombre, ROUND(o.monto_estimado, 2) as monto,
                       e.nombre as empresa,
                       o.oc_recibida,
                       COUNT(DISTINCT c.id_cotizacion) as total_cots,
                       MAX(CASE WHEN c.estado = 'Aprobada' THEN c.monto_total END) as monto_cotizacion_aprobada,
                       MAX(CASE WHEN c.estado = 'Aprobada' THEN c.moneda END) as moneda_cotizacion_aprobada,
                       COUNT(DISTINCT oc.id_oc) as ocs_existentes
                FROM oportunidades o
                JOIN prospectos p ON p.id_prospecto = o.id_prospecto
                JOIN empresas e ON e.id_empresa = p.id_empresa
                LEFT JOIN cotizaciones c ON c.id_oportunidad = o.id_oportunidad
                LEFT JOIN ordenes_compra oc ON oc.id_oportunidad = o.id_oportunidad
                WHERE o.etapa = 'Ganada'
                GROUP BY o.id_oportunidad, o.nombre, o.monto_estimado, e.nombre, o.oc_recibida
                ORDER BY o.fecha_creacion DESC
            """, con)
            con.close()

            if len(opor_ganadas) == 0:
                st.warning("⚠️ No hay oportunidades ganadas. Primero cierra una en N2.")
            else:
                # Selector de oportunidad fuera del form para mostrar contexto dinámico
                if "oc_opor_sel_id" not in st.session_state:
                    st.session_state["oc_opor_sel_id"] = int(opor_ganadas.iloc[0]["id_oportunidad"])
                opor_ids = [int(r["id_oportunidad"]) for _, r in opor_ganadas.iterrows()]
                opor_map = {
                    int(r["id_oportunidad"]): r for _, r in opor_ganadas.iterrows()
                }
                if st.session_state["oc_opor_sel_id"] not in opor_ids:
                    st.session_state["oc_opor_sel_id"] = opor_ids[0]

                id_opor = st.selectbox(
                    "Oportunidad *",
                    opor_ids,
                    format_func=lambda k: (
                        f"#{k} · {opor_map[k]['nombre']} · {opor_map[k]['empresa']} · ${opor_map[k]['monto']}"
                        + (f" · {int(opor_map[k]['ocs_existentes'])} OC(s) registrada(s)" if int(opor_map[k]['ocs_existentes']) > 0 else "")
                    ),
                    key="oc_opor_sel_id",
                )
                opor_ctx = opor_map[id_opor]

                # Contexto comercial de la oportunidad seleccionada
                if opor_ctx["total_cots"] == 0:
                    st.warning("⚠️ Esta oportunidad no tiene cotizaciones. Se recomienda generar una antes de registrar OC.")
                elif opor_ctx["monto_cotizacion_aprobada"] is None:
                    st.info(f"ℹ️ Hay {int(opor_ctx['total_cots'])} cotización(es) pero ninguna está aprobada. Considera aprobar la cotización desde N2.")
                else:
                    st.success(
                        f"✅ Cotización aprobada: ${opor_ctx['monto_cotizacion_aprobada']:,.2f} {opor_ctx['moneda_cotizacion_aprobada']}"
                    )

                with st.form("form_oc"):
                    st.caption(f"Registrando OC para: #{id_opor} — {opor_ctx['nombre']}")
                    numero_oc = st.text_input("Número de OC *", placeholder="OC-2025-001")
                    fecha_oc = st.date_input("Fecha OC *")
                    # Precargar monto desde cotización aprobada si existe
                    monto_default = float(opor_ctx["monto_cotizacion_aprobada"]) if opor_ctx["monto_cotizacion_aprobada"] else 0.0
                    monto_oc = st.number_input(
                        "Monto OC *",
                        min_value=0.01,
                        value=monto_default if monto_default > 0 else 0.01,
                        step=100.0,
                        help="Precargado desde cotización aprobada. Ajusta si el cliente negoció diferente.",
                    )
                    moneda_oc = st.selectbox(
                        "Moneda",
                        ["MXN", "USD", "EUR"],
                        index=["MXN", "USD", "EUR"].index(opor_ctx["moneda_cotizacion_aprobada"])
                        if opor_ctx["moneda_cotizacion_aprobada"] in ["MXN", "USD", "EUR"] else 0,
                    )
                    submit_oc = st.form_submit_button("✅ Registrar OC")

                    if submit_oc:
                        if not numero_oc:
                            st.error("❌ El número de OC es obligatorio.")
                        elif monto_oc <= 0:
                            st.error("❌ El monto de la OC debe ser mayor a 0.")
                        else:
                            con = conectar()
                            cur = con.cursor()
                            cur.execute("""
                                INSERT INTO ordenes_compra (id_oportunidad, numero_oc, fecha_oc, monto_oc, moneda)
                                VALUES (?, ?, ?, ?, ?)
                            """, (id_opor, numero_oc, fecha_oc.isoformat(), monto_oc, moneda_oc))
                            con.commit()
                            oc_id_nuevo = cur.lastrowid
                            # Fix #5: setear oc_recibida=1 automáticamente al registrar la primera OC
                            # Elimina la necesidad de hacerlo manualmente desde N2
                            cur.execute(
                                "UPDATE oportunidades SET oc_recibida=1 WHERE id_oportunidad=? AND oc_recibida=0",
                                (id_opor,)
                            )
                            con.commit()
                            registrar_evento(con, "orden_compra", oc_id_nuevo, "CREAR", f"OC {numero_oc} - ${monto_oc} {moneda_oc}")
                            con.close()
                            st.success(f"✅ OC '{numero_oc}' registrada por ${monto_oc:,.2f} {moneda_oc}")
                            st.rerun()

        with col2:
            con = conectar()
            ocs = pd.read_sql("""
                SELECT oc.id_oc, oc.numero_oc, oc.fecha_oc,
                       ROUND(oc.monto_oc, 2) as monto, oc.moneda,
                       o.nombre as oportunidad,
                       CASE WHEN f.id_factura IS NOT NULL THEN '✅ Facturada' ELSE '⏳ Pendiente' END as estado_factura
                FROM ordenes_compra oc
                JOIN oportunidades o ON o.id_oportunidad = oc.id_oportunidad
                LEFT JOIN facturas f ON f.id_oc = oc.id_oc
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
                SELECT oc.id_oc, oc.numero_oc, ROUND(oc.monto_oc, 2) as monto,
                       oc.moneda, o.nombre as oportunidad,
                       COUNT(f.id_factura) as facturas_existentes
                FROM ordenes_compra oc
                JOIN oportunidades o ON o.id_oportunidad = oc.id_oportunidad
                LEFT JOIN facturas f ON f.id_oc = oc.id_oc
                GROUP BY oc.id_oc, oc.numero_oc, oc.monto_oc, oc.moneda, o.nombre
                ORDER BY oc.fecha_oc DESC
            """, con)
            con.close()

            if len(ocs_sin_factura) == 0:
                st.warning("⚠️ No hay OCs registradas")
            else:
                # Mostrar opción de timbrado automático si CFDI está configurado
                if CFDI_DISPONIBLE:
                    valido_cfdi, _ = validar_configuracion_cfdi()
                    if valido_cfdi:
                        st.success("✅ Emisor CFDI configurado - Timbrado disponible")
                        st.info("🚧 **Próximamente:** Timbrado automático CFDI 4.0")
                        st.caption("Por ahora, registra facturas manualmente con el UUID del PAC")

                # Selector OC fuera del form para mostrar contexto de monto
                if "factura_oc_sel_id" not in st.session_state:
                    st.session_state["factura_oc_sel_id"] = int(ocs_sin_factura.iloc[0]["id_oc"])
                oc_ids = [int(r["id_oc"]) for _, r in ocs_sin_factura.iterrows()]
                oc_map = {int(r["id_oc"]): r for _, r in ocs_sin_factura.iterrows()}
                if st.session_state["factura_oc_sel_id"] not in oc_ids:
                    st.session_state["factura_oc_sel_id"] = oc_ids[0]

                id_oc = st.selectbox(
                    "Orden de Compra *",
                    oc_ids,
                    format_func=lambda k: (
                        f"OC #{k} · {oc_map[k]['numero_oc']} · ${oc_map[k]['monto']:,.2f} {oc_map[k]['moneda']} · {oc_map[k]['oportunidad']}"
                        + (f" · {int(oc_map[k]['facturas_existentes'])} factura(s)" if int(oc_map[k]['facturas_existentes']) > 0 else "")
                    ),
                    key="factura_oc_sel_id",
                )
                oc_ctx = oc_map[id_oc]
                st.caption(
                    f"Monto OC de referencia: **${oc_ctx['monto']:,.2f} {oc_ctx['moneda']}**. "
                    "El monto de la factura no debería exceder este valor."
                )

                with st.form("form_factura"):
                    st.markdown("### 📝 Registro Manual de Factura")
                    st.caption("Ingresa los datos de la factura ya timbrada en tu PAC")

                    uuid = st.text_input("UUID CFDI *", placeholder="A1B2C3D4-...")
                    serie = st.text_input("Serie", placeholder="A")
                    folio = st.text_input("Folio", placeholder="12345")
                    fecha_emision = st.date_input("Fecha emisión *")
                    monto_fact = st.number_input(
                        "Monto total *",
                        min_value=0.01,
                        value=float(oc_ctx["monto"]),
                        step=100.0,
                        help="Debe coincidir con el monto timbrado por el PAC.",
                    )
                    moneda_fact = st.selectbox(
                        "Moneda",
                        ["MXN", "USD", "EUR"],
                        index=["MXN", "USD", "EUR"].index(oc_ctx["moneda"])
                        if oc_ctx["moneda"] in ["MXN", "USD", "EUR"] else 0,
                    )
                    submit_fact = st.form_submit_button("✅ Registrar Factura")

                    if submit_fact:
                        if not uuid:
                            st.error("❌ El UUID CFDI es obligatorio.")
                        elif monto_fact <= 0:
                            st.error("❌ El monto debe ser mayor a 0.")
                        elif monto_fact > float(oc_ctx["monto"]) * 1.10:
                            # Tolerancia del 10% por IVA u otros ajustes
                            st.warning(
                                f"⚠️ El monto de la factura (${monto_fact:,.2f}) supera en más del 10% "
                                f"el monto de la OC (${oc_ctx['monto']:,.2f}). Verifica antes de registrar."
                            )
                        else:
                            data_fact = {"uuid": uuid, "serie": serie, "folio": folio,
                                        "fecha": fecha_emision.isoformat(), "monto": monto_fact,
                                        "ts": datetime.utcnow().isoformat()}
                            hash_fact = hashlib.sha256(json.dumps(data_fact, sort_keys=True).encode()).hexdigest()

                            con = conectar()
                            cur = con.cursor()
                            cur.execute("""
                                INSERT INTO facturas (id_oc, uuid, serie, folio, fecha_emision, monto_total, moneda)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (id_oc, uuid, serie, folio, fecha_emision.isoformat(), monto_fact, moneda_fact))
                            con.commit()
                            fact_id = cur.lastrowid
                            cur.execute(
                                "INSERT INTO hash_registros (tabla_origen, id_registro, hash_sha256) VALUES ('facturas', ?, ?)",
                                (fact_id, hash_fact),
                            )
                            con.commit()
                            registrar_evento(con, "factura", fact_id, "CREAR", f"Factura {serie}-{folio} UUID:{uuid[:16]}...")
                            con.close()
                            st.success(f"✅ Factura creada con hash: {hash_fact[:16]}...")
                            st.rerun()
        
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
    
    # Navegación mejorada y shortcuts
    if UX_COMPONENTS_DISPONIBLES:
        smart_navigation_menu("Trazabilidad")
        keyboard_shortcuts_handler()
    
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
                                        ["Todas", "CREAR", "ACTUALIZAR", "ELIMINAR",
                                         "GANAR", "OC_RECIBIDA", "ESTADO", "SYNC_DYNAMIQUOTE"])
        
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
            # Timeline visual si está disponible
            if UX_COMPONENTS_DISPONIBLES:
                try:
                    timeline_actividad_visual(historial, limit=50)
                except Exception as e:
                    print(f"Error en timeline visual: {e}")
            
            # Tabla con hash truncado
            historial['hash_corto'] = historial['hash_evento'].str[:16]
            
            # Búsqueda avanzada si está disponible
            if UX_COMPONENTS_DISPONIBLES:
                historial_filtrado = advanced_search_widget(
                    historial,
                    entity_name="Historial",
                    search_columns=['entidad', 'accion', 'valor_nuevo', 'usuario'],
                    date_column='timestamp',
                    category_filters={'entidad': 'Entidad', 'accion': 'Acción'}
                )
            else:
                historial_filtrado = historial
            
            st.dataframe(
                historial_filtrado[['id_evento', 'entidad', 'id_entidad', 'accion', 'valor_nuevo', 
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
    
    # Navegación mejorada y shortcuts
    if UX_COMPONENTS_DISPONIBLES:
        smart_navigation_menu("Pipeline Visual")
        keyboard_shortcuts_handler()
        contextual_quick_actions("oportunidades")
    
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
            st.markdown(f"**Acción {index}**")
            st.write(recomendacion["accion"])
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

        score_oportunidades_filtradas = filtrar_pipeline_visual(score_oportunidades)

        if len(score_oportunidades_filtradas) == 0:
            st.info("Los filtros actuales dejan la vista sin oportunidades. Ajusta prioridad o etapa para continuar.")
        else:
            renderizar_vistas_graficas_pipeline(score_oportunidades_filtradas)

            st.dataframe(
            score_oportunidades_filtradas[[
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
                "dias_abierta": st.column_config.NumberColumn("Días", format="%d"),
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
            for index, row in score_oportunidades_filtradas.head(3).iterrows():
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
#  IMPORT/EXPORT MASIVO
# ================================================================

elif menu == "📦 Import/Export":
    st.markdown('<div class="main-header">📦 Import/Export Masivo</div>', unsafe_allow_html=True)
    st.markdown("**Asistente para importación y exportación masiva de datos**")
    
    if UX_COMPONENTS_DISPONIBLES:
        tab1, tab2, tab3, tab4 = st.tabs(["🏢 Empresas", "👤 Contactos", "🎯 Oportunidades", "💰 Facturas"])
        
        # TAB: Empresas
        with tab1:
            con = conectar()
            import_export_wizard(
                con,
                entity_name="Empresas",
                table_name="empresas",
                columns_map={
                    'nombre': 'nombre',
                    'rfc': 'rfc',
                    'sector': 'sector',
                    'telefono': 'telefono',
                    'correo': 'correo'
                }
            )
            con.close()
        
        # TAB: Contactos
        with tab2:
            con = conectar()
            import_export_wizard(
                con,
                entity_name="Contactos",
                table_name="contactos",
                columns_map={
                    'nombre': 'nombre',
                    'correo': 'correo',
                    'telefono': 'telefono',
                    'puesto': 'puesto'
                }
            )
            con.close()
        
        # TAB: Oportunidades
        with tab3:
            con = conectar()
            import_export_wizard(
                con,
                entity_name="Oportunidades",
                table_name="oportunidades",
                columns_map={
                    'nombre': 'nombre',
                    'etapa': 'etapa',
                    'probabilidad': 'probabilidad',
                    'monto_estimado': 'monto_estimado'
                }
            )
            con.close()
        
        # TAB: Facturas
        with tab4:
            con = conectar()
            import_export_wizard(
                con,
                entity_name="Facturas",
                table_name="facturas",
                columns_map={
                    'folio_fiscal': 'folio_fiscal',
                    'fecha_emision': 'fecha_emision',
                    'subtotal': 'subtotal',
                    'iva': 'iva',
                    'total': 'total'
                }
            )
            con.close()
    else:
        st.warning("⚠️ Componentes UX no disponibles. Instala los componentes necesarios.")


# ================================================================
#  DEMO INTEGRACIÓN
# ================================================================

elif menu == "🧭 Demo Integración":
    st.markdown('<div class="main-header">🧭 Demo de Integración con Grafo</div>', unsafe_allow_html=True)
    st.caption("Vista demo montada sobre el esquema legacy actual. Sirve para visualizar desde ya el contrato que después consumirá fradma_dashboard3.")

    con = conectar()
    nodos_demo = obtener_nodos_integracion_demo(con)
    aristas_demo = obtener_aristas_integracion_demo(con)
    pipeline_demo = obtener_pipeline_integracion_demo(con)
    cxc_demo = obtener_cxc_integracion_demo(con)

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("Nodos", len(nodos_demo))
    with col_m2:
        st.metric("Aristas", len(aristas_demo))
    with col_m3:
        st.metric("Etapas pipeline", len(pipeline_demo))
    with col_m4:
        st.metric("Facturas en CxC", len(cxc_demo))

    st.divider()

    if len(nodos_demo) == 0:
        st.info("Aún no hay datos suficientes para la demo. Empieza registrando empresas, prospectos y oportunidades.")
    else:
        resumen_nodos = nodos_demo.groupby("nodo_tipo", as_index=False).size().rename(columns={"size": "total"})
        if len(aristas_demo) > 0:
            resumen_aristas = aristas_demo.groupby("tipo_relacion", as_index=False).size().rename(columns={"size": "total"})
        else:
            resumen_aristas = pd.DataFrame(columns=["tipo_relacion", "total"])

        col_v1, col_v2 = st.columns(2)
        with col_v1:
            st.subheader("Distribución de nodos")
            st.dataframe(resumen_nodos, width="stretch", hide_index=True)
            st.bar_chart(resumen_nodos.set_index("nodo_tipo")["total"])
        with col_v2:
            st.subheader("Distribución de aristas")
            if len(resumen_aristas) > 0:
                st.dataframe(resumen_aristas, width="stretch", hide_index=True)
                st.bar_chart(resumen_aristas.set_index("tipo_relacion")["total"])
            else:
                st.info("Todavía no hay relaciones suficientes para pintar aristas.")

        st.divider()

        tab1, tab2, tab3, tab4 = st.tabs(["🔵 Nodos", "🔗 Aristas", "📊 Pipeline", "💸 CxC"])

        with tab1:
            st.subheader("Contrato de nodos")
            st.dataframe(
                nodos_demo,
                width="stretch",
                hide_index=True,
                column_config={
                    "nodo_tipo": "Tipo",
                    "nodo_id": st.column_config.NumberColumn("ID", format="%d"),
                    "clave_negocio": "Clave",
                    "titulo": "Título",
                    "subtitulo": "Subtítulo",
                    "estado": "Estado",
                    "monto": st.column_config.NumberColumn("Monto", format="$%.2f"),
                    "moneda": "Moneda",
                    "fecha_evento": "Fecha"
                }
            )

        with tab2:
            st.subheader("Contrato de aristas")
            if len(aristas_demo) > 0:
                st.dataframe(
                    aristas_demo,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "nodo_origen_tipo": "Origen tipo",
                        "nodo_origen_id": st.column_config.NumberColumn("Origen ID", format="%d"),
                        "origen_titulo": "Origen",
                        "tipo_relacion": "Relación",
                        "nodo_destino_tipo": "Destino tipo",
                        "nodo_destino_id": st.column_config.NumberColumn("Destino ID", format="%d"),
                        "destino_titulo": "Destino"
                    }
                )
            else:
                st.info("Aún no hay aristas disponibles en la base actual.")

        with tab3:
            st.subheader("Resumen de pipeline para dashboard")
            if len(pipeline_demo) > 0:
                st.dataframe(
                    pipeline_demo,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "etapa": "Etapa",
                        "oportunidades_total": st.column_config.NumberColumn("Oportunidades", format="%d"),
                        "monto_pipeline": st.column_config.NumberColumn("Monto", format="$%.2f"),
                        "cotizaciones_total": st.column_config.NumberColumn("Cotizaciones", format="%d"),
                        "ordenes_compra_total": st.column_config.NumberColumn("OCs", format="%d"),
                        "facturas_total": st.column_config.NumberColumn("Facturas", format="%d")
                    }
                )
                st.bar_chart(pipeline_demo.set_index("etapa")[["oportunidades_total", "facturas_total"]])
            else:
                st.info("No hay oportunidades para construir el pipeline de integración.")

        with tab4:
            st.subheader("CxC derivado del esquema legacy")
            st.caption("En esta demo el esquema legacy no tiene pagos, por eso total_pagado queda en 0 y el saldo se muestra completo.")
            if len(cxc_demo) > 0:
                st.dataframe(
                    cxc_demo,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "id_factura": st.column_config.NumberColumn("Factura ID", format="%d"),
                        "uuid": "UUID",
                        "cliente": "Cliente",
                        "numero_oc": "OC",
                        "fecha_emision": "Fecha emisión",
                        "total_factura": st.column_config.NumberColumn("Total", format="$%.2f"),
                        "total_pagado": st.column_config.NumberColumn("Pagado", format="$%.2f"),
                        "saldo_pendiente": st.column_config.NumberColumn("Saldo", format="$%.2f"),
                        "estado_cobranza": "Estado cobranza",
                        "antiguedad_dias": st.column_config.NumberColumn("Antigüedad", format="%d")
                    }
                )
                st.bar_chart(cxc_demo.set_index("cliente")["saldo_pendiente"])
            else:
                st.info("Todavía no hay facturas para construir la vista CxC.")

    con.close()


# ================================================================
#  CONFIGURACIÓN CFDI
# ================================================================

elif menu == "⚙️ Configuración CFDI":
    if CFDI_DISPONIBLE:
        st.markdown('<div class="main-header">⚙️ Configuración de Facturación CFDI</div>', unsafe_allow_html=True)
        
        # Tabs para organizar las funcionalidades
        tab_config, tab_diagnostico = st.tabs([
            "📝 Registrar Emisor",
            "🔍 Diagnóstico de Certificados"
        ])
        
        with tab_config:
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
        
        with tab_diagnostico:
            # Mostrar herramienta de diagnóstico de certificados
            ui_diagnostico_certificados()
    
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
