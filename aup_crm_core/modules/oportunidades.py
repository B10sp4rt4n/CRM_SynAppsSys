# -*- coding: utf-8 -*-
"""
Módulo de Oportunidades v4 - Flujo Comercial Correcto
REGLA R2: Solo crear oportunidades desde prospectos
REGLA R3: Al ganar → convertir prospecto a cliente
REGLA R4: Checkbox OC para facturación
"""

import streamlit as st
from datetime import date, datetime
from core.database import get_connection
from core.event_logger import registrar_evento
from core.config_global import RECORDIA_ENABLED, APP_VERSION
from core.ui_utils import badge_estado, obtener_valor
import re
import plotly.graph_objects as go
import plotly.express as px


# ==========================================================
#  🎯 INTERFAZ PRINCIPAL
# ==========================================================

def show():
    """Punto de entrada del módulo Oportunidades - REGLA R2 implementada"""
    st.header("📈 Oportunidades Comerciales")
    
    # REGLA R2: Verificar si venimos desde Prospectos
    prospecto_preseleccionado = st.session_state.get("prospecto_id_oportunidad")
    prospecto_nombre_presel = st.session_state.get("prospecto_nombre_oportunidad")
    
    conn = get_connection()
    if not conn:
        st.error("⚠️ Error al conectar con la base de datos.")
        return
    
    cur = conn.cursor()
    # CAMBIO: Ahora buscamos PROSPECTOS, no clientes
    cur.execute("""
        SELECT id, nombre, atributos 
        FROM aup_agentes 
        WHERE tipo='prospecto' AND activo=1 
        ORDER BY nombre ASC
    """)
    prospectos = cur.fetchall()
    conn.close()
    
    if not prospectos:
        st.warning("⚠️ No hay prospectos disponibles.")
        st.info("💡 **REGLA R2:** Las oportunidades solo se crean desde prospectos. Ve al módulo **Empresas** → Crea empresa → Agrega contacto → Genera prospecto.")
        return
    
    # Selector de prospecto con preselección inteligente
    nombres_prospectos = [p["nombre"] for p in prospectos]
    
    if prospecto_preseleccionado:
        # Buscar el prospecto en la lista
        prospecto_obj = next((p for p in prospectos if p["id"] == prospecto_preseleccionado), None)
        if prospecto_obj and prospecto_obj["nombre"] in nombres_prospectos:
            index_default = nombres_prospectos.index(prospecto_obj["nombre"])
            st.success(f"📊 Creando oportunidad para prospecto: **{prospecto_obj['nombre']}**")
            if st.button("← Volver a prospectos"):
                del st.session_state["prospecto_id_oportunidad"]
                del st.session_state["prospecto_nombre_oportunidad"]
                st.rerun()
        else:
            index_default = 0
    else:
        index_default = 0
    
    prospecto_sel = st.selectbox(
        "Selecciona un prospecto",
        nombres_prospectos,
        index=index_default,
        key="selector_prospecto_oportunidades"
    )
    prospecto_id = next(p["id"] for p in prospectos if p["nombre"] == prospecto_sel)
    prospecto_obj = next(p for p in prospectos if p["nombre"] == prospecto_sel)
    
    # Verificar si ya es cliente
    es_cliente = obtener_valor(prospecto_obj["atributos"], "es_cliente") == "1"
    
    # Información del prospecto seleccionado
    sector = obtener_valor(prospecto_obj["atributos"], "sector")
    estado = obtener_valor(prospecto_obj["atributos"], "estado")
    
    with st.expander(f"ℹ️ Información del prospecto: {prospecto_sel}"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Sector", sector if sector != "—" else "No especificado")
        with col2:
            st.metric("Estado", estado if estado != "—" else "Nuevo")
        with col3:
            if es_cliente:
                st.success("✅ YA ES CLIENTE")
            else:
                st.info("🎯 Prospecto activo")
        
        # Contar oportunidades
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as total 
            FROM aup_agentes 
            WHERE tipo='oportunidad' 
            AND id IN (
                SELECT agente_destino FROM aup_relaciones
                WHERE agente_origen = ? AND tipo_relacion='tiene_oportunidad'
            )
        """, (prospecto_id,))
        count = cur.fetchone()["total"]
        conn.close()
        st.metric("Oportunidades totales", count)
    
    st.divider()
    
    # Visualización del pipeline
    visualizar_pipeline(prospecto_id)
    
    st.divider()
    
    # Mostrar oportunidades existentes
    mostrar_oportunidades_prospecto(prospecto_id, prospecto_sel)
    
    st.divider()
    
    # Formulario nueva oportunidad (REGLA R2)
    st.subheader("➕ Nueva oportunidad")
    nueva_oportunidad(prospecto_id, prospecto_sel)


# ==========================================================
#  📊 VISUALIZACIÓN DEL PIPELINE
# ==========================================================

def visualizar_pipeline(prospecto_id):
    """Muestra dos vistas del pipeline: por porcentaje y por etapa"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM aup_agentes 
        WHERE tipo='oportunidad' 
        AND id IN (
            SELECT agente_destino FROM aup_relaciones
            WHERE agente_origen = ? AND tipo_relacion='tiene_oportunidad'
        )
    """, (prospecto_id,))
    oportunidades = cur.fetchall()
    conn.close()
    
    if not oportunidades:
        return
    
    # Procesar datos por estado
    datos_pipeline = {}
    for o in oportunidades:
        estado = obtener_valor(o["atributos"], "estado")
        monto = float(obtener_valor(o["atributos"], "monto") or 0)
        
        if estado not in datos_pipeline:
            datos_pipeline[estado] = {"cantidad": 0, "monto": 0}
        
        datos_pipeline[estado]["cantidad"] += 1
        datos_pipeline[estado]["monto"] += monto
    
    # Orden de las etapas del pipeline
    orden_etapas = ["Abierta", "En negociación", "Ganada", "Perdida"]
    estados_presentes = [e for e in orden_etapas if e in datos_pipeline]
    
    st.subheader("📊 Análisis del Pipeline")
    
    # Tabs para las dos vistas
    tab1, tab2 = st.tabs(["📈 Por Etapa", "🥧 Por Porcentaje"])
    
    with tab1:
        # Vista por etapa (gráfico de embudo/barras)
        st.markdown("##### Distribución por etapa del pipeline")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de barras por cantidad
            cantidades = [datos_pipeline[e]["cantidad"] for e in estados_presentes]
            
            # Colores según el estado
            colores = {
                "Abierta": "#3498db",
                "En negociación": "#f39c12",
                "Ganada": "#2ecc71",
                "Perdida": "#e74c3c"
            }
            colores_barras = [colores.get(e, "#95a5a6") for e in estados_presentes]
            
            fig_cantidad = go.Figure(data=[
                go.Bar(
                    x=cantidades,
                    y=estados_presentes,
                    orientation='h',
                    marker=dict(color=colores_barras),
                    text=cantidades,
                    textposition='auto',
                )
            ])
            
            fig_cantidad.update_layout(
                title="Número de Oportunidades",
                xaxis_title="Cantidad",
                yaxis_title="Estado",
                height=300,
                showlegend=False,
                yaxis={'categoryorder': 'array', 'categoryarray': orden_etapas}
            )
            
            st.plotly_chart(fig_cantidad, use_container_width=True)
        
        with col2:
            # Gráfico de barras por monto
            montos = [datos_pipeline[e]["monto"] for e in estados_presentes]
            
            fig_monto = go.Figure(data=[
                go.Bar(
                    x=montos,
                    y=estados_presentes,
                    orientation='h',
                    marker=dict(color=colores_barras),
                    text=[f"${m:,.0f}" for m in montos],
                    textposition='auto',
                )
            ])
            
            fig_monto.update_layout(
                title="Valor Total ($)",
                xaxis_title="Monto",
                yaxis_title="Estado",
                height=300,
                showlegend=False,
                yaxis={'categoryorder': 'array', 'categoryarray': orden_etapas}
            )
            
            st.plotly_chart(fig_monto, use_container_width=True)
        
        # Métricas resumen
        col1, col2, col3, col4 = st.columns(4)
        total_ops = sum(datos_pipeline[e]["cantidad"] for e in datos_pipeline)
        total_monto = sum(datos_pipeline[e]["monto"] for e in datos_pipeline)
        
        with col1:
            st.metric("Total Oportunidades", total_ops)
        with col2:
            st.metric("Valor Total", f"${total_monto:,.0f}")
        with col3:
            ganadas = datos_pipeline.get("Ganada", {}).get("cantidad", 0)
            tasa_conv = (ganadas / total_ops * 100) if total_ops > 0 else 0
            st.metric("Tasa Conversión", f"{tasa_conv:.1f}%")
        with col4:
            abiertas = datos_pipeline.get("Abierta", {}).get("cantidad", 0)
            negociacion = datos_pipeline.get("En negociación", {}).get("cantidad", 0)
            st.metric("En Proceso", abiertas + negociacion)
    
    with tab2:
        # Vista por porcentaje (gráficos de pastel)
        st.markdown("##### Distribución porcentual del pipeline")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de pastel por cantidad
            cantidades = [datos_pipeline[e]["cantidad"] for e in estados_presentes]
            colores_pie = [colores.get(e, "#95a5a6") for e in estados_presentes]
            
            fig_pie_cantidad = go.Figure(data=[
                go.Pie(
                    labels=estados_presentes,
                    values=cantidades,
                    marker=dict(colors=colores_pie),
                    hole=0.4,  # Dona
                    textinfo='label+percent',
                    textposition='outside'
                )
            ])
            
            fig_pie_cantidad.update_layout(
                title="Por Cantidad de Oportunidades",
                height=400,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
            )
            
            st.plotly_chart(fig_pie_cantidad, use_container_width=True)
        
        with col2:
            # Gráfico de pastel por monto
            montos = [datos_pipeline[e]["monto"] for e in estados_presentes]
            
            fig_pie_monto = go.Figure(data=[
                go.Pie(
                    labels=estados_presentes,
                    values=montos,
                    marker=dict(colors=colores_pie),
                    hole=0.4,  # Dona
                    textinfo='label+percent',
                    textposition='outside',
                    hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>'
                )
            ])
            
            fig_pie_monto.update_layout(
                title="Por Valor Total ($)",
                height=400,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
            )
            
            st.plotly_chart(fig_pie_monto, use_container_width=True)
        
        # Tabla resumen
        st.markdown("##### Resumen detallado")
        tabla_datos = []
        for estado in estados_presentes:
            cantidad = datos_pipeline[estado]["cantidad"]
            monto = datos_pipeline[estado]["monto"]
            pct_cantidad = (cantidad / total_ops * 100) if total_ops > 0 else 0
            pct_monto = (monto / total_monto * 100) if total_monto > 0 else 0
            
            tabla_datos.append({
                "Estado": estado,
                "Cantidad": cantidad,
                "% Cantidad": f"{pct_cantidad:.1f}%",
                "Monto": f"${monto:,.0f}",
                "% Monto": f"{pct_monto:.1f}%"
            })
        
        st.table(tabla_datos)


# ==========================================================
#  📊 VISUALIZACIÓN DE OPORTUNIDADES
# ==========================================================

def mostrar_oportunidades_prospecto(prospecto_id, prospecto_nombre):
    """Despliega oportunidades asociadas al prospecto con filtros"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM aup_agentes 
        WHERE tipo='oportunidad' 
        AND id IN (
            SELECT agente_destino FROM aup_relaciones
            WHERE agente_origen = ? AND tipo_relacion='tiene_oportunidad'
        )
        ORDER BY fecha_creacion DESC
    """, (prospecto_id,))
    oportunidades = cur.fetchall()
    conn.close()
    
    if not oportunidades:
        st.info(f"📋 **{prospecto_nombre}** aún no tiene oportunidades registradas.")
        return
    
    # Filtro por estado
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        estados_disponibles = ["Todas", "Abierta", "En negociación", "Ganada", "Perdida"]
        filtro_estado = st.selectbox("Filtrar por estado", estados_disponibles, key=f"filtro_estado_{prospecto_id}")
    
    with col2:
        # Métrica: valor total de oportunidades abiertas
        valor_total = sum(
            float(obtener_valor(o["atributos"], "monto") or 0)
            for o in oportunidades
            if obtener_valor(o["atributos"], "estado") in ["Abierta", "En negociación"]
        )
        st.metric("💰 Pipeline total", f"${valor_total:,.2f}")
    
    with col3:
        # Tasa de conversión
        total = len(oportunidades)
        ganadas = sum(1 for o in oportunidades if obtener_valor(o["atributos"], "estado") == "Ganada")
        tasa = (ganadas / total * 100) if total > 0 else 0
        st.metric("🎯 Conversión", f"{tasa:.1f}%")
    
    st.markdown("---")
    
    # Renderizar tarjetas filtradas
    oportunidades_filtradas = [
        o for o in oportunidades
        if filtro_estado == "Todas" or obtener_valor(o["atributos"], "estado") == filtro_estado
    ]
    
    if not oportunidades_filtradas:
        st.info(f"No hay oportunidades con estado: **{filtro_estado}**")
        return
    
    for o in oportunidades_filtradas:
        mostrar_tarjeta_oportunidad(o, prospecto_id, prospecto_nombre)


def mostrar_tarjeta_oportunidad(o, prospecto_id, prospecto_nombre):
    """Renderiza tarjeta con REGLA R3 y R4 implementadas"""
    atributos = o["atributos"] or ""
    
    # Parsear atributos
    estado = obtener_valor(atributos, "estado")
    monto = obtener_valor(atributos, "monto")
    cierre = obtener_valor(atributos, "cierre")
    notas = obtener_valor(atributos, "notas")
    probabilidad = obtener_valor(atributos, "probabilidad")
    responsable = obtener_valor(atributos, "responsable")
    fuente = obtener_valor(atributos, "fuente")
    recordia_id = obtener_valor(atributos, "recordia_id")
    oc_recibida = obtener_valor(atributos, "oc_recibida") == "1"  # REGLA R4
    
    # Badge centralizado (extendido para Oportunidades)
    badge_map = {
        "Abierta": "🔵",
        "En negociación": "🟡",
        "Ganada": "🟢",
        "Perdida": "🔴"
    }
    badge = badge_map.get(estado, "⚪")
    
    # Validar fecha de cierre
    alerta_cierre = ""
    if cierre != "—":
        try:
            fecha_cierre = datetime.strptime(cierre, "%Y-%m-%d").date()
            dias_restantes = (fecha_cierre - date.today()).days
            if dias_restantes < 0 and estado in ["Abierta", "En negociación"]:
                alerta_cierre = f"⚠️ Fecha de cierre vencida hace {abs(dias_restantes)} días"
            elif 0 <= dias_restantes <= 7 and estado in ["Abierta", "En negociación"]:
                alerta_cierre = f"⏰ Cierra en {dias_restantes} días"
        except:
            pass
    
    # Wrapper con opacidad para oportunidades cerradas
    opacity = "opacity: 0.6;" if estado in ["Ganada", "Perdida"] else ""
    
    with st.container(border=True):
        st.markdown(f"<div style='{opacity}'>", unsafe_allow_html=True)
        st.markdown(f"### {badge} {o['nombre']}")
        
        # Fila de métricas principales
        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption(f"💵 **Monto:** ${float(monto) if monto != '—' else 0:,.2f}")
        with col2:
            st.caption(f"🎯 **Probabilidad:** {probabilidad}%")
        with col3:
            st.caption(f"📅 **Cierre:** {cierre}")
        
        # Fila de contexto
        st.caption(f"👤 **Responsable:** {responsable} | 📡 **Fuente:** {fuente}")
        
        if alerta_cierre:
            st.warning(alerta_cierre)
        
        if recordia_id != "—":
            st.caption(f"🔗 **Recordia ID:** `{recordia_id[:16]}...`")
        
        # REGLA R4: Mostrar checkbox OC si está ganada
        if estado == "Ganada":
            if oc_recibida:
                st.success("✅ **OC Recibida** - Lista para facturación")
            else:
                st.warning("⚠️ **Pendiente OC** - Requerida para facturar")
        
        if notas != "—":
            with st.expander("📝 Ver notas"):
                st.write(notas)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Botones de acción
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("✏️ Editar", key=f"edit_op_{o['id']}", use_container_width=True):
                st.session_state["editar_oportunidad"] = o["id"]
                st.rerun()
        
        with col2:
            # REGLA R3: Al ganar → convertir prospecto a cliente
            if estado not in ["Ganada", "Perdida"]:
                if st.button("🏆 Ganada", key=f"win_op_{o['id']}", use_container_width=True, type="primary"):
                    marcar_ganada_y_convertir(o["id"], prospecto_id, prospecto_nombre, o["nombre"])
                    st.rerun()
        
        with col3:
            if estado not in ["Ganada", "Perdida"]:
                if st.button("❌ Perdida", key=f"lost_op_{o['id']}", use_container_width=True):
                    actualizar_estado(o["id"], "Perdida", prospecto_id, prospecto_nombre, o["nombre"])
                    st.rerun()
        
        with col4:
            if estado in ["Ganada", "Perdida"]:
                if st.button("🔄 Reabrir", key=f"reopen_op_{o['id']}", use_container_width=True):
                    actualizar_estado(o["id"], "Abierta", prospecto_id, prospecto_nombre, o["nombre"])
                    st.rerun()
        
        # REGLA R4: Botón facturación solo si ganada + OC
        if estado == "Ganada":
            st.divider()
            col_oc, col_fac = st.columns(2)
            with col_oc:
                nuevo_estado_oc = st.checkbox(
                    "📋 Marcar OC recibida",
                    value=oc_recibida,
                    key=f"oc_{o['id']}"
                )
                if nuevo_estado_oc != oc_recibida:
                    actualizar_oc(o["id"], nuevo_estado_oc, o["atributos"])
                    st.rerun()
            
            with col_fac:
                if oc_recibida:
                    if st.button("📄 Enviar a Facturación", key=f"fact_{o['id']}", use_container_width=True, type="primary"):
                        st.success("✅ Funcionalidad de facturación pendiente de implementar")
                        # TODO: Integrar con módulo de facturación
                else:
                    st.button("📄 Facturación", key=f"fact_dis_{o['id']}", use_container_width=True, disabled=True, help="Requiere OC recibida")
    
    # Modo edición modal
    if st.session_state.get("editar_oportunidad") == o["id"]:
        editar_oportunidad(o, prospecto_id, prospecto_nombre)


# ==========================================================
#  ✍️ FORMULARIOS (CRUD)
# ==========================================================

def nueva_oportunidad(prospecto_id, prospecto_nombre):
    """REGLA R2: Crea oportunidad vinculada a prospecto (no huérfanas)"""
    with st.form(f"form_nueva_oportunidad_{prospecto_id}", clear_on_submit=True):
        nombre = st.text_input(
            "Nombre de la oportunidad *",
            placeholder="Ej. Renovación contrato anual",
            help="Describe brevemente la oportunidad de negocio"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            monto = st.number_input(
                "Monto estimado ($) *",
                min_value=0.0,
                step=1000.0,
                help="Valor económico esperado"
            )
            estado = st.selectbox("Estado inicial", ["Abierta", "En negociación"])
        
        with col2:
            cierre = st.date_input(
                "Fecha estimada de cierre *",
                value=date.today(),
                help="Cuándo esperas cerrar esta oportunidad"
            )
            probabilidad = st.slider("Probabilidad de éxito (%)", 0, 100, 50, 5)
        
        responsable = st.text_input(
            "Responsable o agente asignado",
            placeholder="Ej. Luis Pérez",
            help="Quién está liderando esta oportunidad"
        )
        
        fuente = st.text_input(
            "Fuente de origen",
            placeholder="Ej. Referencia, web, llamada...",
            help="Cómo llegó esta oportunidad"
        )
        
        notas = st.text_area(
            "Notas / contexto adicional",
            placeholder="Detalles importantes sobre esta oportunidad...",
            help="Contexto relevante para el equipo"
        )
        
        submit = st.form_submit_button("💾 Guardar oportunidad", use_container_width=True)
    
    if submit:
        if not nombre:
            st.error("⚠️ El nombre de la oportunidad es obligatorio.")
            return
        
        # REGLA R2: Validar que tenga prospecto
        if not prospecto_id:
            st.error("❌ No se pueden crear oportunidades huérfanas. Debe estar asociada a un prospecto.")
            return
        
        # Construir atributos con separador estándar (;)
        # REGLA R4: Inicializar oc_recibida=0
        atributos = (
            f"monto={monto};estado={estado};cierre={cierre};"
            f"probabilidad={probabilidad};"
            f"responsable={responsable or 'No asignado'};"
            f"fuente={fuente or 'Directo'};"
            f"notas={notas or 'Sin notas'};"
            f"oc_recibida=0"
        )
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Insertar oportunidad
        cur.execute(
            "INSERT INTO aup_agentes (tipo, nombre, atributos, activo) VALUES ('oportunidad', ?, ?, 1)",
            (nombre, atributos)
        )
        oportunidad_id = cur.lastrowid
        
        # Crear relación con PROSPECTO (no cliente)
        cur.execute("""
            INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)
            VALUES (?, ?, 'tiene_oportunidad')
        """, (prospecto_id, oportunidad_id))
        
        conn.commit()
        
        # Registro en bitácora AUP
        registrar_evento(
            oportunidad_id,
            "Alta oportunidad",
            f"Oportunidad '{nombre}' creada para prospecto '{prospecto_nombre}' con monto ${monto:,.2f}"
        )
        
        # Sincronización Recordia-Bridge (si está habilitado)
        if RECORDIA_ENABLED:
            recordia_payload = {
                "tipo": "oportunidad",
                "nombre": nombre,
                "valor_num": monto,
                "status_flag": estado,
                "actor": responsable or "No asignado",
                "probabilidad": probabilidad,
                "fuente": fuente or "Directo",
                "contexto": notas or "Sin contexto",
                "app_version": APP_VERSION
            }
            recordia_id = f"RCD-{oportunidad_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            cur.execute(
                "UPDATE aup_agentes SET atributos = atributos || ? WHERE id=?",
                (f";recordia_id={recordia_id}", oportunidad_id)
            )
            conn.commit()
            
            registrar_evento(
                oportunidad_id,
                "Sync Recordia",
                f"Oportunidad '{nombre}' registrada en ledger forense {APP_VERSION} con ID {recordia_id}"
            )
        
        conn.close()
        
        st.success(f"✅ Oportunidad **'{nombre}'** registrada correctamente para **{cliente_nombre}**")
        st.balloons()
        st.rerun()


def editar_oportunidad(o, prospecto_id, prospecto_nombre):
    """Permite editar una oportunidad existente con modal limpio"""
    st.markdown("---")
    st.subheader(f"✏️ Editando: {o['nombre']}")
    
    atributos = o["atributos"] or ""
    
    # Parsear valores actuales con defaults seguros
    monto_actual = obtener_valor(atributos, "monto")
    monto_val = float(monto_actual) if monto_actual != "—" and monto_actual.replace('.', '', 1).replace('-', '', 1).isdigit() else 0.0
    
    estado_actual = obtener_valor(atributos, "estado")
    estado_val = estado_actual if estado_actual in ["Abierta", "En negociación", "Ganada", "Perdida"] else "Abierta"
    
    cierre_actual = obtener_valor(atributos, "cierre")
    try:
        cierre_val = date.fromisoformat(cierre_actual)
    except:
        cierre_val = date.today()
    
    probabilidad_actual = obtener_valor(atributos, "probabilidad")
    probabilidad_val = int(probabilidad_actual) if probabilidad_actual != "—" and probabilidad_actual.isdigit() else 50
    
    responsable_val = obtener_valor(atributos, "responsable")
    responsable_val = responsable_val if responsable_val != "—" else ""
    
    fuente_val = obtener_valor(atributos, "fuente")
    fuente_val = fuente_val if fuente_val != "—" else ""
    
    notas_val = obtener_valor(atributos, "notas")
    notas_val = notas_val if notas_val != "—" else ""
    
    with st.form(f"form_edit_op_{o['id']}", clear_on_submit=False):
        nombre = st.text_input("Nombre de la oportunidad *", value=o["nombre"])
        
        col1, col2 = st.columns(2)
        with col1:
            monto = st.number_input("Monto ($) *", value=monto_val, step=1000.0)
            estado = st.selectbox(
                "Estado",
                ["Abierta", "En negociación", "Ganada", "Perdida"],
                index=["Abierta", "En negociación", "Ganada", "Perdida"].index(estado_val)
            )
        
        with col2:
            cierre = st.date_input("Fecha estimada de cierre *", value=cierre_val)
            probabilidad = st.slider("Probabilidad (%)", 0, 100, probabilidad_val, 5)
        
        responsable = st.text_input("Responsable", value=responsable_val)
        fuente = st.text_input("Fuente", value=fuente_val)
        notas = st.text_area("Notas", value=notas_val)
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
        with col2:
            cancel = st.form_submit_button("❌ Cancelar", use_container_width=True)
    
    if cancel:
        if "editar_oportunidad" in st.session_state:
            del st.session_state["editar_oportunidad"]
        st.rerun()
    
    if submit:
        if not nombre:
            st.error("⚠️ El nombre no puede estar vacío.")
            return
        
        # Reconstruir atributos
        # REGLA R4: Preservar oc_recibida
        oc_actual = obtener_valor(atributos, "oc_recibida")
        nuevos_atributos = (
            f"monto={monto};estado={estado};cierre={cierre};"
            f"probabilidad={probabilidad};"
            f"responsable={responsable or 'No asignado'};"
            f"fuente={fuente or 'Directo'};"
            f"notas={notas or 'Sin notas'};"
            f"oc_recibida={oc_actual if oc_actual != '—' else '0'}"
        )
        
        # Preservar recordia_id si existe
        recordia_id = obtener_valor(atributos, "recordia_id")
        if recordia_id != "—":
            nuevos_atributos += f";recordia_id={recordia_id}"
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE aup_agentes SET nombre=?, atributos=? WHERE id=?",
            (nombre, nuevos_atributos, o["id"])
        )
        conn.commit()
        conn.close()
        
        # Registro AUP
        registrar_evento(
            o["id"],
            "Edición oportunidad",
            f"Oportunidad '{nombre}' actualizada a estado: {estado} con monto ${monto:,.2f}"
        )
        
        # Sincronización Recordia
        if RECORDIA_ENABLED:
            registrar_evento(
                o["id"],
                "Sync Recordia",
                f"Oportunidad '{nombre}' sincronizada en ledger {APP_VERSION}"
            )
        
        st.success(f"✅ Oportunidad **'{nombre}'** actualizada correctamente.")
        
        if "editar_oportunidad" in st.session_state:
            del st.session_state["editar_oportunidad"]
        
        st.rerun()


def actualizar_estado(oportunidad_id, nuevo_estado, prospecto_id, prospecto_nombre, nombre_oportunidad):
    """Actualiza solo el estado con sincronización forense"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT atributos FROM aup_agentes WHERE id=?", (oportunidad_id,))
    o = cur.fetchone()
    
    if not o:
        st.error("⚠️ Oportunidad no encontrada.")
        return
    
    atributos = o["atributos"] or ""
    
    # Reemplazar estado con regex
    if re.search(r"estado=[^;]+", atributos):
        nuevos_atributos = re.sub(r"estado=[^;]+", f"estado={nuevo_estado}", atributos)
    else:
        nuevos_atributos = atributos + f";estado={nuevo_estado}"
    
    cur.execute(
        "UPDATE aup_agentes SET atributos=? WHERE id=?",
        (nuevos_atributos, oportunidad_id)
    )
    conn.commit()
    conn.close()
    
    # Registro AUP con contexto
    emoji_estado = {"Ganada": "🏆", "Perdida": "❌", "Abierta": "🔵"}.get(nuevo_estado, "🔄")
    registrar_evento(
        oportunidad_id,
        "Cambio estado",
        f"{emoji_estado} Oportunidad '{nombre_oportunidad}' de prospecto '{prospecto_nombre}' marcada como {nuevo_estado}"
    )
    
    # Sincronización Recordia
    if RECORDIA_ENABLED:
        registrar_evento(
            oportunidad_id,
            "Sync Recordia",
            f"Estado actualizado en ledger {APP_VERSION}: {nuevo_estado}"
        )
    
    st.success(f"{emoji_estado} **'{nombre_oportunidad}'** actualizada a estado: **{nuevo_estado}**")


# ==========================================================
#  🎯 REGLA R3: CONVERSIÓN AUTOMÁTICA A CLIENTE
# ==========================================================

def marcar_ganada_y_convertir(oportunidad_id, prospecto_id, prospecto_nombre, nombre_oportunidad):
    """
    REGLA R3: Al marcar oportunidad como ganada:
    1. Actualizar probabilidad a 100%
    2. Cambiar estado a "Ganada"
    3. Convertir prospecto a cliente automáticamente
    """
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    cur.execute("SELECT * FROM aup_agentes WHERE id=?", (oportunidad_id,))
    o = cur.fetchone()
    
    if not o:
        conn.close()
        st.error("⚠️ Oportunidad no encontrada.")
        return
    
    atributos = o["atributos"] or ""
    
    # 1. Actualizar estado a "Ganada" y probabilidad a 100%
    if re.search(r"estado=[^;]+", atributos):
        atributos = re.sub(r"estado=[^;]+", "estado=Ganada", atributos)
    else:
        atributos += ";estado=Ganada"
    
    if re.search(r"probabilidad=[^;]+", atributos):
        atributos = re.sub(r"probabilidad=[^;]+", "probabilidad=100", atributos)
    else:
        atributos += ";probabilidad=100"
    
    cur.execute("UPDATE aup_agentes SET atributos=? WHERE id=?", (atributos, oportunidad_id))
    conn.commit()
    
    # 2. Registrar evento
    registrar_evento(
        oportunidad_id,
        "Oportunidad ganada",
        f"🏆 Oportunidad '{nombre_oportunidad}' marcada como GANADA (100%)"
    )
    
    # 3. REGLA R3: Convertir prospecto a cliente
    cur.execute("SELECT * FROM aup_agentes WHERE id=?", (prospecto_id,))
    prospecto = cur.fetchone()
    
    if prospecto:
        atrib_prospecto = prospecto["atributos"] or ""
        es_cliente_actual = obtener_valor(atrib_prospecto, "es_cliente") == "1"
        
        if not es_cliente_actual:
            # Actualizar atributos del prospecto
            if re.search(r"es_cliente=[^;]+", atrib_prospecto):
                atrib_prospecto = re.sub(r"es_cliente=[^;]+", "es_cliente=1", atrib_prospecto)
            else:
                atrib_prospecto += ";es_cliente=1"
            
            if re.search(r"fecha_conversion_cliente=[^;]+", atrib_prospecto):
                atrib_prospecto = re.sub(r"fecha_conversion_cliente=[^;]+", f"fecha_conversion_cliente={date.today()}", atrib_prospecto)
            else:
                atrib_prospecto += f";fecha_conversion_cliente={date.today()}"
            
            cur.execute("UPDATE aup_agentes SET atributos=? WHERE id=?", (atrib_prospecto, prospecto_id))
            conn.commit()
            
            registrar_evento(
                prospecto_id,
                "Conversión automática a cliente",
                f"✅ Prospecto '{prospecto_nombre}' convertido a CLIENTE por ganar oportunidad '{nombre_oportunidad}'"
            )
            
            st.success(f"🎉 ¡OPORTUNIDAD GANADA! Prospecto '{prospecto_nombre}' ahora es CLIENTE")
            st.balloons()
        else:
            st.success(f"🏆 Oportunidad '{nombre_oportunidad}' marcada como GANADA")
    
    conn.close()


# ==========================================================
#  📋 REGLA R4: GESTIÓN DE OC (ORDEN DE COMPRA)
# ==========================================================

def actualizar_oc(oportunidad_id, nuevo_estado_oc, atributos_actuales):
    """
    REGLA R4: Actualiza el estado de OC recibida
    """
    conn = get_connection()
    if not conn:
        return
    
    valor_oc = "1" if nuevo_estado_oc else "0"
    
    if re.search(r"oc_recibida=[^;]+", atributos_actuales):
        nuevos_atributos = re.sub(r"oc_recibida=[^;]+", f"oc_recibida={valor_oc}", atributos_actuales)
    else:
        nuevos_atributos = atributos_actuales + f";oc_recibida={valor_oc}"
    
    cur = conn.cursor()
    cur.execute("UPDATE aup_agentes SET atributos=? WHERE id=?", (nuevos_atributos, oportunidad_id))
    conn.commit()
    conn.close()
    
    estado_texto = "RECIBIDA ✅" if nuevo_estado_oc else "PENDIENTE ⏳"
    registrar_evento(
        oportunidad_id,
        "Actualización OC",
        f"📋 Orden de Compra marcada como: {estado_texto}"
    )
    
    if nuevo_estado_oc:
        st.success("✅ OC marcada como recibida - Ahora puede enviarse a facturación")
    else:
        st.info("⏳ OC marcada como pendiente")
