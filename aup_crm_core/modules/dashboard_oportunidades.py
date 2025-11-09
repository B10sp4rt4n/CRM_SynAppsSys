# -*- coding: utf-8 -*-
"""
Dashboard Ejecutivo de Oportunidades - AUP-EXO v3 Enterprise
Autor: SynAppsSys / Salvador Ruiz Esparza
Visualización de KPIs y rendimiento comercial con Plotly interactivo
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from core.database import get_connection
from core.config_global import RECORDIA_ENABLED, APP_VERSION
from core.ui_utils import obtener_valor, validar_vigencia
import re


# ==========================================================
#  📊 OBTENCIÓN DE DATOS
# ==========================================================

def obtener_oportunidades():
    """Extrae todas las oportunidades del sistema AUP"""
    conn = get_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    cur.execute("""
        SELECT a.*, 
               (SELECT nombre FROM aup_agentes WHERE id = r.agente_origen) as cliente_nombre
        FROM aup_agentes a
        LEFT JOIN aup_relaciones r ON a.id = r.agente_destino AND r.tipo_relacion='tiene_oportunidad'
        WHERE a.tipo='oportunidad'
        ORDER BY a.fecha_creacion DESC
    """)
    data = cur.fetchall()
    conn.close()
    return data


def obtener_clientes():
    """Obtiene estadísticas de clientes para métricas integradas"""
    conn = get_connection()
    if not conn:
        return {"total": 0, "activos": 0, "con_oportunidades": 0}
    
    cur = conn.cursor()
    
    # Total clientes
    cur.execute("SELECT COUNT(*) as total FROM aup_agentes WHERE tipo='cliente'")
    total = cur.fetchone()["total"]
    
    # Clientes activos
    cur.execute("SELECT COUNT(*) as activos FROM aup_agentes WHERE tipo='cliente' AND activo=1")
    activos = cur.fetchone()["activos"]
    
    # Clientes con oportunidades
    cur.execute("""
        SELECT COUNT(DISTINCT agente_origen) as con_op 
        FROM aup_relaciones 
        WHERE tipo_relacion='tiene_oportunidad'
    """)
    con_op = cur.fetchone()["con_op"]
    
    conn.close()
    return {"total": total, "activos": activos, "con_oportunidades": con_op}


# ==========================================================
#  📊 DASHBOARD PRINCIPAL
# ==========================================================

def show():
    """Interfaz principal del dashboard ejecutivo"""
    st.header("📊 Dashboard Ejecutivo - Oportunidades Comerciales")
    st.caption(f"Sistema AUP-EXO v3 Enterprise | Versión {APP_VERSION}")
    
    # Obtener datos
    oportunidades = obtener_oportunidades()
    stats_clientes = obtener_clientes()
    
    if not oportunidades:
        st.warning("⚠️ No hay oportunidades registradas todavía.")
        st.info("💡 Ve al módulo **Clientes** → Selecciona un cliente → **Ver oportunidades** → **Nueva oportunidad**")
        return
    
    # Crear DataFrame con parsing robusto
    df = pd.DataFrame([
        {
            "id": o["id"],
            "nombre": o["nombre"],
            "cliente": o["cliente_nombre"] if "cliente_nombre" in o.keys() and o["cliente_nombre"] else "Sin cliente",
            "monto": float(obtener_valor(o["atributos"], "monto") or 0),
            "estado": obtener_valor(o["atributos"], "estado") or "Desconocido",
            "probabilidad": int(obtener_valor(o["atributos"], "probabilidad") or 0),
            "responsable": obtener_valor(o["atributos"], "responsable") or "No asignado",
            "fuente": obtener_valor(o["atributos"], "fuente") or "No especificada",
            "cierre": obtener_valor(o["atributos"], "cierre") or None,
            "fecha_creacion": o["fecha_creacion"] if "fecha_creacion" in o.keys() else None
        }
        for o in oportunidades
    ])
    
    # Calcular días hasta cierre
    def calcular_dias_cierre(fecha_str):
        if not fecha_str or fecha_str == "—":
            return None
        try:
            fecha_cierre = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            return (fecha_cierre - date.today()).days
        except:
            return None
    
    df["dias_hasta_cierre"] = df["cierre"].apply(calcular_dias_cierre)
    
    # ==========================================================
    #  📈 SECCIÓN 1: KPIs GLOBALES
    # ==========================================================
    
    st.subheader("📈 Indicadores Clave de Rendimiento (KPIs)")
    
    # Métricas principales
    total_op = len(df)
    total_monto = df["monto"].sum()
    
    ganadas = df[df["estado"] == "Ganada"]
    perdidas = df[df["estado"] == "Perdida"]
    abiertas = df[df["estado"].isin(["Abierta", "En negociación"])]
    
    monto_ganado = ganadas["monto"].sum()
    monto_pipeline = abiertas["monto"].sum()
    
    # Fila 1: Oportunidades
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "🎯 Total Oportunidades",
            f"{total_op}",
            help="Todas las oportunidades en el sistema"
        )
    
    with col2:
        st.metric(
            "💰 Valor Total",
            f"${total_monto:,.2f}",
            help="Suma de montos de todas las oportunidades"
        )
    
    with col3:
        st.metric(
            "🏆 Ganadas",
            f"{len(ganadas)}",
            delta=f"${monto_ganado:,.0f}",
            help="Oportunidades cerradas exitosamente"
        )
    
    with col4:
        st.metric(
            "❌ Perdidas",
            f"{len(perdidas)}",
            delta=f"-${perdidas['monto'].sum():,.0f}",
            delta_color="inverse",
            help="Oportunidades no concretadas"
        )
    
    # Fila 2: Pipeline y conversión
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        tasa_exito = (len(ganadas) / (len(ganadas) + len(perdidas)) * 100) if (len(ganadas) + len(perdidas)) > 0 else 0
        st.metric(
            "🎯 Tasa de Éxito",
            f"{tasa_exito:.1f}%",
            help="(Ganadas / (Ganadas + Perdidas)) × 100"
        )
    
    with col6:
        st.metric(
            "🔵 Pipeline Activo",
            f"{len(abiertas)}",
            delta=f"${monto_pipeline:,.0f}",
            help="Oportunidades Abiertas + En negociación"
        )
    
    with col7:
        prob_promedio = abiertas["probabilidad"].mean() if len(abiertas) > 0 else 0
        st.metric(
            "📊 Probabilidad Promedio",
            f"{prob_promedio:.0f}%",
            help="Promedio de probabilidad en pipeline activo"
        )
    
    with col8:
        # Penetración: clientes con oportunidades / clientes activos
        penetracion = (stats_clientes["con_oportunidades"] / stats_clientes["activos"] * 100) if stats_clientes["activos"] > 0 else 0
        st.metric(
            "🎯 Penetración",
            f"{penetracion:.0f}%",
            help=f"{stats_clientes['con_oportunidades']} de {stats_clientes['activos']} clientes activos tienen oportunidades"
        )
    
    st.divider()
    
    # ==========================================================
    #  📊 SECCIÓN 2: GRÁFICOS INTERACTIVOS (PLOTLY)
    # ==========================================================
    
    st.subheader("📊 Análisis Visual")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Distribución por Estado",
        "👤 Rendimiento por Responsable",
        "🎯 Análisis de Probabilidad",
        "📅 Línea de Tiempo"
    ])
    
    # TAB 1: Distribución por estado
    with tab1:
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("**🥧 Pie Chart: Oportunidades por Estado**")
            dist_estado = df["estado"].value_counts().reset_index()
            dist_estado.columns = ["Estado", "Cantidad"]
            
            # Colores consistentes con badges
            color_map = {
                "Abierta": "#3b82f6",      # Azul
                "En negociación": "#eab308", # Amarillo
                "Ganada": "#22c55e",       # Verde
                "Perdida": "#ef4444"       # Rojo
            }
            
            fig_pie = px.pie(
                dist_estado,
                values="Cantidad",
                names="Estado",
                color="Estado",
                color_discrete_map=color_map,
                hole=0.3
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col_right:
            st.markdown("**📊 Barras: Valor $ por Estado**")
            dist_monto = df.groupby("estado")["monto"].sum().reset_index()
            dist_monto.columns = ["Estado", "Monto"]
            
            fig_bar_estado = px.bar(
                dist_monto,
                x="Estado",
                y="Monto",
                color="Estado",
                color_discrete_map=color_map,
                text="Monto"
            )
            fig_bar_estado.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
            fig_bar_estado.update_layout(showlegend=False, yaxis_title="Monto ($)")
            st.plotly_chart(fig_bar_estado, use_container_width=True)
    
    # TAB 2: Rendimiento por responsable
    with tab2:
        st.markdown("**👤 Top Responsables por Valor de Pipeline**")
        
        df_resp = df.groupby("responsable").agg({
            "monto": "sum",
            "id": "count",
            "probabilidad": "mean"
        }).reset_index()
        df_resp.columns = ["Responsable", "Monto Total", "Oportunidades", "Prob. Promedio"]
        df_resp = df_resp.sort_values("Monto Total", ascending=False)
        
        fig_resp = px.bar(
            df_resp,
            x="Monto Total",
            y="Responsable",
            orientation="h",
            color="Prob. Promedio",
            color_continuous_scale="blues",
            text="Monto Total",
            hover_data=["Oportunidades", "Prob. Promedio"]
        )
        fig_resp.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
        fig_resp.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_resp, use_container_width=True)
        
        # Tabla detallada
        with st.expander("📋 Ver detalle por responsable"):
            df_resp["Monto Total"] = df_resp["Monto Total"].apply(lambda x: f"${x:,.2f}")
            df_resp["Prob. Promedio"] = df_resp["Prob. Promedio"].apply(lambda x: f"{x:.0f}%")
            st.dataframe(df_resp, use_container_width=True, hide_index=True)
    
    # TAB 3: Análisis de probabilidad
    with tab3:
        col_prob1, col_prob2 = st.columns(2)
        
        with col_prob1:
            st.markdown("**🎯 Probabilidad Promedio por Estado**")
            df_prob = df.groupby("estado")["probabilidad"].mean().reset_index()
            df_prob.columns = ["Estado", "Probabilidad"]
            
            fig_prob = px.bar(
                df_prob,
                x="Estado",
                y="Probabilidad",
                color="Estado",
                color_discrete_map=color_map,
                text="Probabilidad"
            )
            fig_prob.update_traces(texttemplate='%{text:.0f}%', textposition='outside')
            fig_prob.update_layout(showlegend=False, yaxis_title="Probabilidad (%)")
            st.plotly_chart(fig_prob, use_container_width=True)
        
        with col_prob2:
            st.markdown("**💰 Valor Esperado (Monto × Probabilidad)**")
            df_valor_esp = df[df["estado"].isin(["Abierta", "En negociación"])].copy()
            df_valor_esp["Valor Esperado"] = df_valor_esp["monto"] * df_valor_esp["probabilidad"] / 100
            
            valor_esperado_total = df_valor_esp["Valor Esperado"].sum()
            st.metric("💎 Valor Esperado del Pipeline", f"${valor_esperado_total:,.2f}")
            
            # Top 5 oportunidades por valor esperado
            top_val_esp = df_valor_esp.nlargest(5, "Valor Esperado")[["nombre", "monto", "probabilidad", "Valor Esperado"]]
            top_val_esp["Valor Esperado"] = top_val_esp["Valor Esperado"].apply(lambda x: f"${x:,.0f}")
            top_val_esp["monto"] = top_val_esp["monto"].apply(lambda x: f"${x:,.0f}")
            top_val_esp["probabilidad"] = top_val_esp["probabilidad"].apply(lambda x: f"{x}%")
            
            st.caption("Top 5 por Valor Esperado")
            st.dataframe(top_val_esp, use_container_width=True, hide_index=True)
    
    # TAB 4: Línea de tiempo
    with tab4:
        st.markdown("**📅 Oportunidades Próximas a Cerrar (30 días)**")
        
        # Filtrar oportunidades con fecha de cierre en próximos 30 días
        df_timeline = df[
            (df["dias_hasta_cierre"].notna()) & 
            (df["dias_hasta_cierre"] <= 30) &
            (df["dias_hasta_cierre"] >= -7) &  # Incluir hasta 7 días vencidas
            (df["estado"].isin(["Abierta", "En negociación"]))
        ].copy()
        
        if len(df_timeline) > 0:
            df_timeline = df_timeline.sort_values("dias_hasta_cierre")
            
            # Añadir columna de alerta
            df_timeline["Alerta"] = df_timeline["dias_hasta_cierre"].apply(
                lambda x: "🔴 Vencida" if x < 0 else ("🟡 Próxima (7d)" if x <= 7 else "🟢 Activa")
            )
            
            fig_timeline = px.scatter(
                df_timeline,
                x="dias_hasta_cierre",
                y="monto",
                size="probabilidad",
                color="Alerta",
                hover_name="nombre",
                hover_data={"responsable": True, "cliente": True, "dias_hasta_cierre": True},
                color_discrete_map={
                    "🔴 Vencida": "#ef4444",
                    "🟡 Próxima (7d)": "#eab308",
                    "🟢 Activa": "#22c55e"
                }
            )
            fig_timeline.update_layout(
                xaxis_title="Días hasta cierre",
                yaxis_title="Monto ($)",
                showlegend=True
            )
            st.plotly_chart(fig_timeline, use_container_width=True)
            
            # Tabla de oportunidades urgentes
            with st.expander("📋 Ver detalle de oportunidades próximas"):
                df_timeline_display = df_timeline[["nombre", "cliente", "responsable", "monto", "probabilidad", "dias_hasta_cierre", "Alerta"]]
                df_timeline_display["monto"] = df_timeline_display["monto"].apply(lambda x: f"${x:,.0f}")
                df_timeline_display["probabilidad"] = df_timeline_display["probabilidad"].apply(lambda x: f"{x}%")
                st.dataframe(df_timeline_display, use_container_width=True, hide_index=True)
        else:
            st.info("✅ No hay oportunidades próximas a cerrar en los próximos 30 días")
    
    st.divider()
    
    # ==========================================================
    #  📋 SECCIÓN 3: DETALLE DE OPORTUNIDADES
    # ==========================================================
    
    st.subheader("📋 Detalle de Oportunidades Activas")
    
    # Filtros
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        filtro_estado = st.multiselect(
            "Filtrar por estado",
            df["estado"].unique(),
            default=["Abierta", "En negociación"]
        )
    
    with col_f2:
        filtro_responsable = st.multiselect(
            "Filtrar por responsable",
            df["responsable"].unique(),
            default=df["responsable"].unique()
        )
    
    with col_f3:
        orden = st.selectbox(
            "Ordenar por",
            ["Probabilidad ↓", "Monto ↓", "Fecha cierre ↑", "Fecha creación ↓"]
        )
    
    # Aplicar filtros
    df_filtrado = df[
        (df["estado"].isin(filtro_estado)) &
        (df["responsable"].isin(filtro_responsable))
    ].copy()
    
    # Aplicar ordenamiento
    if orden == "Probabilidad ↓":
        df_filtrado = df_filtrado.sort_values("probabilidad", ascending=False)
    elif orden == "Monto ↓":
        df_filtrado = df_filtrado.sort_values("monto", ascending=False)
    elif orden == "Fecha cierre ↑":
        df_filtrado = df_filtrado.sort_values("dias_hasta_cierre", na_position='last')
    else:  # Fecha creación
        df_filtrado = df_filtrado.sort_values("fecha_creacion", ascending=False)
    
    # Mostrar tabla
    if len(df_filtrado) > 0:
        df_display = df_filtrado[["nombre", "cliente", "responsable", "monto", "probabilidad", "fuente", "cierre", "estado"]].copy()
        df_display["monto"] = df_display["monto"].apply(lambda x: f"${x:,.2f}")
        df_display["probabilidad"] = df_display["probabilidad"].apply(lambda x: f"{x}%")
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "nombre": st.column_config.TextColumn("Oportunidad", width="medium"),
                "cliente": st.column_config.TextColumn("Cliente", width="small"),
                "monto": st.column_config.TextColumn("Monto", width="small"),
                "estado": st.column_config.TextColumn("Estado", width="small")
            }
        )
        
        st.caption(f"Mostrando {len(df_filtrado)} de {total_op} oportunidades")
    else:
        st.info("No hay oportunidades que coincidan con los filtros seleccionados")
    
    st.divider()
    
    # ==========================================================
    #  🔗 SECCIÓN 4: INFORMACIÓN DEL SISTEMA
    # ==========================================================
    
    with st.expander("ℹ️ Información del Sistema", expanded=False):
        col_info1, col_info2 = st.columns(2)
        
        with col_info1:
            st.markdown("**📊 Estadísticas Generales**")
            st.caption(f"Total de oportunidades: {total_op}")
            st.caption(f"Clientes con oportunidades: {stats_clientes['con_oportunidades']}")
            st.caption(f"Responsables activos: {df['responsable'].nunique()}")
            st.caption(f"Fuentes de origen: {df['fuente'].nunique()}")
        
        with col_info2:
            st.markdown("**🔧 Configuración**")
            st.caption(f"Versión del sistema: {APP_VERSION}")
            
            if RECORDIA_ENABLED:
                st.success("🔗 Recordia-Bridge ACTIVO — Sincronización forense habilitada")
            else:
                st.warning("⚠️ Recordia-Bridge INACTIVO — Métricas basadas en datos locales")
            
            st.caption("Base de datos: SQLite (AUP Schema)")
            st.caption("Motor de gráficos: Plotly Express")
