# -*- coding: utf-8 -*-
"""
Módulo de Oportunidades v3 - Enterprise Grade
Gestión relacional AUP con UI centralizada y validaciones robustas
Integración con Recordia-Bridge y trazabilidad forense completa
"""

import streamlit as st
from datetime import date, datetime
from core.database import get_connection
from core.event_logger import registrar_evento
from core.config_global import RECORDIA_ENABLED, APP_VERSION
from core.ui_utils import badge_estado, obtener_valor
import re


# ==========================================================
#  🎯 INTERFAZ PRINCIPAL
# ==========================================================

def show():
    """Punto de entrada del módulo Oportunidades"""
    st.header("📈 Oportunidades Comerciales")
    
    conn = get_connection()
    if not conn:
        st.error("⚠️ Error al conectar con la base de datos.")
        return
    
    # Detectar si venimos desde Clientes con session_state
    cliente_preseleccionado = st.session_state.get("cliente_seleccionado")
    cliente_nombre_presel = st.session_state.get("cliente_nombre")
    
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nombre, atributos 
        FROM aup_agentes 
        WHERE tipo='cliente' AND activo=1 
        ORDER BY nombre ASC
    """)
    clientes = cur.fetchall()
    conn.close()
    
    if not clientes:
        st.warning("⚠️ No hay clientes activos disponibles. Crea un cliente primero desde el módulo Clientes.")
        return
    
    # Selector de cliente con preselección inteligente
    nombres_clientes = [c["nombre"] for c in clientes]
    
    if cliente_preseleccionado and cliente_nombre_presel in nombres_clientes:
        index_default = nombres_clientes.index(cliente_nombre_presel)
        st.info(f"📊 Mostrando oportunidades de: **{cliente_nombre_presel}**")
        # Limpiar session_state para próxima visita
        if st.button("← Volver a selección de clientes"):
            del st.session_state["cliente_seleccionado"]
            del st.session_state["cliente_nombre"]
            st.rerun()
    else:
        index_default = 0
    
    cliente_sel = st.selectbox(
        "Selecciona un cliente",
        nombres_clientes,
        index=index_default,
        key="selector_cliente_oportunidades"
    )
    cliente_id = next(c["id"] for c in clientes if c["nombre"] == cliente_sel)
    cliente_obj = next(c for c in clientes if c["nombre"] == cliente_sel)
    
    # Información del cliente seleccionado
    sector = obtener_valor(cliente_obj["atributos"], "sector")
    with st.expander(f"ℹ️ Información del cliente: {cliente_sel}"):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Sector", sector if sector != "—" else "No especificado")
        with col2:
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
            """, (cliente_id,))
            count = cur.fetchone()["total"]
            conn.close()
            st.metric("Oportunidades activas", count)
    
    st.divider()
    
    # Mostrar oportunidades existentes
    mostrar_oportunidades_cliente(cliente_id, cliente_sel)
    
    st.divider()
    
    # Formulario nueva oportunidad
    st.subheader("➕ Nueva oportunidad")
    nueva_oportunidad(cliente_id, cliente_sel)


# ==========================================================
#  📊 VISUALIZACIÓN DE OPORTUNIDADES
# ==========================================================

def mostrar_oportunidades_cliente(cliente_id, cliente_nombre):
    """Despliega oportunidades asociadas al cliente con filtros"""
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
    """, (cliente_id,))
    oportunidades = cur.fetchall()
    conn.close()
    
    if not oportunidades:
        st.info(f"📋 **{cliente_nombre}** aún no tiene oportunidades registradas.")
        return
    
    # Filtro por estado
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        estados_disponibles = ["Todas", "Abierta", "En negociación", "Ganada", "Perdida"]
        filtro_estado = st.selectbox("Filtrar por estado", estados_disponibles, key=f"filtro_estado_{cliente_id}")
    
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
        mostrar_tarjeta_oportunidad(o, cliente_id, cliente_nombre)


def mostrar_tarjeta_oportunidad(o, cliente_id, cliente_nombre):
    """Renderiza una tarjeta enterprise-grade con badges centralizados"""
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
            if estado not in ["Ganada", "Perdida"]:
                if st.button("🏆 Ganada", key=f"win_op_{o['id']}", use_container_width=True):
                    actualizar_estado(o["id"], "Ganada", cliente_id, cliente_nombre, o["nombre"])
                    st.rerun()
        
        with col3:
            if estado not in ["Ganada", "Perdida"]:
                if st.button("❌ Perdida", key=f"lost_op_{o['id']}", use_container_width=True):
                    actualizar_estado(o["id"], "Perdida", cliente_id, cliente_nombre, o["nombre"])
                    st.rerun()
        
        with col4:
            if estado in ["Ganada", "Perdida"]:
                if st.button("🔄 Reabrir", key=f"reopen_op_{o['id']}", use_container_width=True):
                    actualizar_estado(o["id"], "Abierta", cliente_id, cliente_nombre, o["nombre"])
                    st.rerun()
    
    # Modo edición modal (como Clientes/Prospectos)
    if st.session_state.get("editar_oportunidad") == o["id"]:
        editar_oportunidad(o, cliente_id, cliente_nombre)


# ==========================================================
#  ✍️ FORMULARIOS (CRUD)
# ==========================================================

def nueva_oportunidad(cliente_id, cliente_nombre):
    """Crea una nueva oportunidad con trazabilidad AUP-Recordia"""
    with st.form(f"form_nueva_oportunidad_{cliente_id}", clear_on_submit=True):
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
        
        # Construir atributos con separador estándar (;)
        atributos = (
            f"monto={monto};estado={estado};cierre={cierre};"
            f"probabilidad={probabilidad};"
            f"responsable={responsable or 'No asignado'};"
            f"fuente={fuente or 'Directo'};"
            f"notas={notas or 'Sin notas'}"
        )
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Insertar oportunidad
        cur.execute(
            "INSERT INTO aup_agentes (tipo, nombre, atributos, activo) VALUES ('oportunidad', ?, ?, 1)",
            (nombre, atributos)
        )
        oportunidad_id = cur.lastrowid
        
        # Crear relación con cliente
        cur.execute("""
            INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)
            VALUES (?, ?, 'tiene_oportunidad')
        """, (cliente_id, oportunidad_id))
        
        conn.commit()
        
        # Registro en bitácora AUP
        registrar_evento(
            oportunidad_id,
            "Alta oportunidad",
            f"Oportunidad '{nombre}' creada para cliente '{cliente_nombre}' con monto ${monto:,.2f}"
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


def editar_oportunidad(o, cliente_id, cliente_nombre):
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
        nuevos_atributos = (
            f"monto={monto};estado={estado};cierre={cierre};"
            f"probabilidad={probabilidad};"
            f"responsable={responsable or 'No asignado'};"
            f"fuente={fuente or 'Directo'};"
            f"notas={notas or 'Sin notas'}"
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


def actualizar_estado(oportunidad_id, nuevo_estado, cliente_id, cliente_nombre, nombre_oportunidad):
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
        f"{emoji_estado} Oportunidad '{nombre_oportunidad}' de cliente '{cliente_nombre}' marcada como {nuevo_estado}"
    )
    
    # Sincronización Recordia
    if RECORDIA_ENABLED:
        registrar_evento(
            oportunidad_id,
            "Sync Recordia",
            f"Estado actualizado en ledger {APP_VERSION}: {nuevo_estado}"
        )
    
    st.success(f"{emoji_estado} **'{nombre_oportunidad}'** actualizada a estado: **{nuevo_estado}**")
