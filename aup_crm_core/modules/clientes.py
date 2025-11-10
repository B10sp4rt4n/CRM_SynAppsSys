# -*- coding: utf-8 -*-
"""
Módulo de Clientes - Vista de prospectos convertidos
Muestra solo prospectos con es_cliente=1 (REGLA R3)
"""

import streamlit as st
from datetime import date, datetime
from core.database import get_connection
from core.event_logger import registrar_evento
from core.config_global import RECORDIA_ENABLED, APP_VERSION
from core.ui_utils import badge_estado, obtener_valor, validar_vigencia
import re


def show():
    """Interfaz principal del módulo de clientes - Vista de prospectos convertidos"""
    st.header("👥 Clientes")
    
    st.info("💡 Los clientes son prospectos que ganaron al menos una oportunidad y se convirtieron automáticamente.")
    
    # Obtener PROSPECTOS que son clientes (es_cliente=1)
    conn = get_connection()
    if not conn:
        st.error("Error al conectar con la base de datos")
        return
        
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM aup_agentes 
        WHERE tipo='prospecto'
        ORDER BY fecha_creacion DESC
    """)
    todos_prospectos = cur.fetchall()
    conn.close()
    
    # Filtrar solo los que son clientes
    clientes = [p for p in todos_prospectos if obtener_valor(p["atributos"], "es_cliente") == "1"]
    
    if not clientes:
        st.warning("📋 No hay clientes registrados aún.")
        st.caption("� Los clientes se generan automáticamente cuando una **oportunidad** se marca como **Ganada** (REGLA R3)")
        st.caption("🔄 **Flujo:** Empresa → Contacto → Prospecto → Oportunidad Ganada → **CLIENTE**")
        return
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        mostrar_inactivos = st.checkbox("Mostrar inactivos", value=False)
    with col2:
        # Ordenar por
        orden = st.selectbox("Ordenar por", ["Fecha conversión (reciente)", "Nombre (A-Z)", "Más antiguo"])
    with col3:
        st.metric("Total clientes", len(clientes))
    
    st.divider()
    
    # Aplicar filtros
    clientes_filtrados = []
    for c in clientes:
        if not mostrar_inactivos and not c["activo"]:
            continue
        clientes_filtrados.append(c)
    
    # Ordenar
    if orden == "Nombre (A-Z)":
        clientes_filtrados.sort(key=lambda x: x["nombre"])
    elif orden == "Más antiguo":
        clientes_filtrados.sort(key=lambda x: x["fecha_creacion"])
    else:  # Fecha conversión reciente
        clientes_filtrados.sort(
            key=lambda x: obtener_valor(x["atributos"], "fecha_conversion_cliente"), 
            reverse=True
        )
    
    st.caption(f"Mostrando {len(clientes_filtrados)} de {len(clientes)} clientes")
    
    # Mostrar tarjetas
    for c in clientes_filtrados:
        mostrar_tarjeta_cliente(c)


def mostrar_tarjeta_cliente(c):
    """Muestra la tarjeta de un cliente (prospecto convertido)"""
    atributos = c["atributos"] or ""
    
    # Parsear atributos
    sector = obtener_valor(atributos, "sector")
    telefono = obtener_valor(atributos, "telefono")
    fecha_conversion = obtener_valor(atributos, "fecha_conversion_cliente")
    estado = obtener_valor(atributos, "estado")
    
    # Obtener empresa origen y oportunidades
    conn = get_connection()
    empresa_nombre = "—"
    contactos_count = 0
    oportunidades_total = 0
    oportunidades_ganadas = 0
    monto_total_ganado = 0.0
    
    if conn:
        cur = conn.cursor()
        
        # Obtener empresa origen
        cur.execute("""
            SELECT a.nombre FROM aup_agentes a
            INNER JOIN aup_relaciones r ON r.agente_destino = a.id
            WHERE r.agente_origen = ? AND r.tipo_relacion = 'tiene_contacto'
            LIMIT 1
        """, (c["id"],))
        empresa = cur.fetchone()
        if empresa:
            empresa_nombre = empresa["nombre"]
        
        # Contar contactos
        cur.execute("""
            SELECT COUNT(*) as total FROM aup_relaciones
            WHERE agente_origen = ? AND tipo_relacion = 'tiene_contacto'
        """, (c["id"],))
        contactos_count = cur.fetchone()["total"]
        
        # Contar oportunidades y calcular monto ganado
        cur.execute("""
            SELECT a.* FROM aup_agentes a
            INNER JOIN aup_relaciones r ON r.agente_destino = a.id
            WHERE r.agente_origen = ? AND r.tipo_relacion = 'tiene_oportunidad'
        """, (c["id"],))
        oportunidades = cur.fetchall()
        oportunidades_total = len(oportunidades)
        
        for o in oportunidades:
            estado_op = obtener_valor(o["atributos"], "estado")
            if estado_op == "Ganada":
                oportunidades_ganadas += 1
                monto = obtener_valor(o["atributos"], "monto")
                if monto != "—":
                    monto_total_ganado += float(monto)
        
        conn.close()
    
    with st.container(border=True):
        # Encabezado con indicador de cliente
        st.markdown(f"### ✅ {c['nombre']}")
        st.success(f"**Cliente desde:** {fecha_conversion}")
        
        # Métricas principales
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.caption(f"**Sector:** {sector}")
        with col2:
            st.metric("Oportunidades ganadas", f"{oportunidades_ganadas}/{oportunidades_total}")
        with col3:
            st.metric("Facturación total", f"${monto_total_ganado:,.0f}")
        with col4:
            st.metric("Contactos", contactos_count)
        
        # Información adicional
        with st.expander("📊 Ver detalles completos"):
            st.caption(f"**📞 Teléfono:** {telefono}")
            st.caption(f"**🏢 Empresa origen:** {empresa_nombre}")
            st.caption(f"**📅 Fecha creación (como prospecto):** {c['fecha_creacion'][:10]}")
            st.caption(f"**✅ Fecha conversión a cliente:** {fecha_conversion}")
            st.caption(f"**ID Prospecto:** {c['id']}")
            
            # Mostrar estado de actividad
            if c["activo"]:
                st.success("✅ Cliente activo")
            else:
                st.error("❌ Cliente inactivo")
        
        # Botones de acción
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📈 Ver oportunidades", key=f"ver_op_cli_{c['id']}", use_container_width=True):
                # Redirigir al módulo de oportunidades con este prospecto
                st.session_state["prospecto_id_oportunidad"] = c["id"]
                st.session_state["prospecto_nombre_oportunidad"] = c["nombre"]
                st.switch_page("pages/oportunidades.py") if hasattr(st, 'switch_page') else st.info("Ir a módulo Oportunidades")
        
        with col2:
            if st.button("👤 Ver contactos", key=f"ver_cont_cli_{c['id']}", use_container_width=True):
                ver_contactos_cliente(c["id"], c["nombre"])
        
        with col3:
            if c["activo"]:
                if st.button("❌ Desactivar", key=f"deact_cli_{c['id']}", use_container_width=True):
                    desactivar_cliente(c["id"], c["nombre"])
                    st.rerun()
            else:
                if st.button("✅ Activar", key=f"act_cli_{c['id']}", use_container_width=True):
                    activar_cliente(c["id"], c["nombre"])
                    st.rerun()


def ver_contactos_cliente(cliente_id, cliente_nombre):
    """Muestra los contactos asociados al cliente"""
    conn = get_connection()
    if not conn:
        return
    
    st.markdown(f"### 📇 Contactos de {cliente_nombre}")
    
    cur = conn.cursor()
    cur.execute("""
        SELECT a.* FROM aup_agentes a
        INNER JOIN aup_relaciones r ON r.agente_destino = a.id
        WHERE r.agente_origen = ? AND r.tipo_relacion = 'tiene_contacto'
    """, (cliente_id,))
    contactos = cur.fetchall()
    conn.close()
    
    if not contactos:
        st.info("No hay contactos registrados")
        return
    
    for c in contactos:
        cargo = obtener_valor(c["atributos"], "cargo")
        telefono = obtener_valor(c["atributos"], "telefono")
        correo = obtener_valor(c["atributos"], "correo")
        
        with st.container(border=True):
            st.markdown(f"**{c['nombre']}** — {cargo}")
            st.caption(f"📞 {telefono} | ✉️ {correo}")


def desactivar_cliente(cliente_id, nombre):
    """Desactiva un cliente (prospecto convertido)"""
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("UPDATE aup_agentes SET activo=0 WHERE id=?", (cliente_id,))
        conn.commit()
        conn.close()
        registrar_evento(cliente_id, "Desactivación cliente", f"Cliente '{nombre}' desactivado")
        st.success(f"✅ Cliente '{nombre}' desactivado")


def activar_cliente(cliente_id, nombre):
    """Activa un cliente"""
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("UPDATE aup_agentes SET activo=1 WHERE id=?", (cliente_id,))
        conn.commit()
        conn.close()
        registrar_evento(cliente_id, "Activación cliente", f"Cliente '{nombre}' activado")
        st.success(f"✅ Cliente '{nombre}' activado")

        cur = conn.cursor()
        cur.execute("""
            SELECT agente_origen FROM aup_relaciones 
            WHERE agente_destino = ? AND tipo_relacion = 'convertido_en'
        """, (c["id"],))
        resultado = cur.fetchone()
        if resultado:
            prospecto_id = resultado["agente_origen"]
        conn.close()
    
    # Estilo atenuado para clientes inactivos
    if not c["activo"]:
        st.markdown("<div style='opacity: 0.6;'>", unsafe_allow_html=True)
    
    with st.container(border=True):
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"### 💼 {c['nombre']}")
            st.caption(f"**Sector:** {sector} | **📞 Tel. empresa:** {telefono_empresa}")
            st.caption(f"{badge} **Estado:** {estado} | **Vigencia:** {vigencia_str}")
            
            # Indicador visual de expiración
            if estado_vigencia == "vencida":
                st.error(f"⚠️ Vigencia vencida hace {dias_restantes} días")
            elif estado_vigencia == "próxima":
                st.warning(f"⏰ Vigencia próxima a vencer en {dias_restantes} días")
            
            if prospecto_id:
                st.caption(f"🔄 Convertido desde prospecto ID: {prospecto_id}")
            if not c["activo"]:
                st.warning("⚠️ Cliente inactivo")
        
        with col2:
            st.caption(f"ID: {c['id']}")
            st.caption(f"📅 {c['fecha_creacion'][:10]}")
        
        with col3:
            if c["activo"]:
                st.success("✅ Activo")
            else:
                st.error("❌ Inactivo")
        
        # Mostrar contactos asociados
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT a.* FROM aup_agentes a
                INNER JOIN aup_relaciones r ON a.id = r.agente_destino
                WHERE r.agente_origen = ? AND r.tipo_relacion IN ('contacto_principal', 'tiene_contacto')
                ORDER BY a.fecha_creacion DESC
            """, (c["id"],))
            contactos = cur.fetchall()
            conn.close()
            
            if contactos:
                st.markdown("**📇 Contactos principales:**")
                for contacto in contactos:
                    nombre_contacto = contacto["nombre"]
                    telefono_contacto = obtener_valor(contacto["atributos"], "telefono_contacto")
                    correo = obtener_valor(contacto["atributos"], "correo")
                    cargo = obtener_valor(contacto["atributos"], "cargo")
                    
                    estado_contacto = "✅" if contacto["activo"] else "❌"
                    st.write(f"  {estado_contacto} **{nombre_contacto}** — {cargo} | 📞 {telefono_contacto} | ✉️ {correo}")
                
                st.caption(f"Total de contactos: {len(contactos)}")
            else:
                st.info("💡 Sin contactos asociados")
        
        # Botones de acción
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button(f"✏️ Editar", key=f"edit_{c['id']}", use_container_width=True):
                st.session_state["editar_cliente"] = c["id"]
                st.rerun()
        
        with col2:
            if st.button("📊 Ver oportunidades", key=f"ver_oportunidades_{c['id']}", use_container_width=True):
                # Navegar al módulo de Oportunidades con cliente preseleccionado
                st.session_state["cliente_seleccionado"] = c["id"]
                st.session_state["cliente_nombre"] = c["nombre"]
                st.session_state["pagina_actual"] = "Oportunidades"
                st.rerun()
        
        with col3:
            texto_btn = "❌ Desactivar" if c["activo"] else "✅ Activar"
            if st.button(texto_btn, key=f"toggle_{c['id']}", type="secondary", use_container_width=True):
                toggle_activo(c["id"], c["nombre"], c["activo"])
                st.rerun()
    
    # Cerrar div de estilo atenuado para clientes inactivos
    if not c["activo"]:
        st.markdown("</div>", unsafe_allow_html=True)


def editar_cliente(cliente_id):
    """Permite editar los datos clave del cliente"""
    conn = get_connection()
    if not conn:
        st.error("Error de conexión")
        return
        
    cur = conn.cursor()
    cur.execute("SELECT * FROM aup_agentes WHERE id=?", (cliente_id,))
    c = cur.fetchone()
    conn.close()

    if not c:
        st.error("❌ Cliente no encontrado.")
        return

    st.subheader(f"✏️ Editar cliente: {c['nombre']}")
    
    # Obtener valores actuales
    atributos = c["atributos"] or ""
    estado_actual = obtener_valor(atributos, "estado")
    
    # Si el estado viene del prospecto original, mapearlo a estados de cliente
    mapeo_estados = {
        "Nuevo": "Activo",
        "En negociación": "Activo",
        "Cerrado": "Activo",
        "Perdido": "Suspendido"
    }
    
    if estado_actual in mapeo_estados:
        estado_actual = mapeo_estados[estado_actual]
    elif estado_actual == "—":
        estado_actual = "Activo"
    
    with st.form("form_editar_cliente"):
        nombre = st.text_input("Nombre del cliente", value=c["nombre"])
        
        col1, col2 = st.columns(2)
        with col1:
            sector = st.text_input("Sector", value=obtener_valor(atributos, "sector"))
            telefono_empresa = st.text_input("📞 Teléfono empresa", value=obtener_valor(atributos, "telefono_empresa"))
        with col2:
            estados_cliente = ["Activo", "Suspendido", "No renovado"]
            idx = estados_cliente.index(estado_actual) if estado_actual in estados_cliente else 0
            estado = st.selectbox("Estado del cliente", estados_cliente, index=idx)
            
            # Manejar vigencia
            vigencia_str = obtener_valor(atributos, "vigencia")
            try:
                vigencia_actual = date.fromisoformat(vigencia_str) if vigencia_str != "—" else date.today()
            except:
                vigencia_actual = date.today()
            
            vigencia = st.date_input("Vigente hasta", value=vigencia_actual)
        
        activo = st.checkbox("Cliente activo", value=bool(c["activo"]))
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
        with col2:
            cancel = st.form_submit_button("❌ Cancelar", use_container_width=True)
    
    if cancel:
        del st.session_state["editar_cliente"]
        st.rerun()
    
    if submit:
        # Seguridad: valores por defecto para campos vacíos
        sector = sector or "No definido"
        telefono_empresa = telefono_empresa or "Sin teléfono"
        
        # Sincronizar vigencia automática si se marca como inactivo
        if not activo and vigencia > date.today():
            vigencia = date.today()
        
        nuevos_atributos = f"sector={sector};telefono_empresa={telefono_empresa};estado={estado};vigencia={vigencia}"
        
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE aup_agentes SET nombre=?, atributos=?, activo=? WHERE id=?",
                (nombre, nuevos_atributos, 1 if activo else 0, cliente_id)
            )
            conn.commit()
            conn.close()
            
            registrar_evento(cliente_id, "Edición cliente", f"Cliente '{nombre}' actualizado. Estado: {estado}")
            
            # Gancho para integración futura con Recordia-Bridge (registro forense)
            if RECORDIA_ENABLED:
                registrar_evento(
                    cliente_id, 
                    "Sync Recordia", 
                    f"Cliente '{nombre}' actualizado y registrado en ledger {APP_VERSION}."
                )
            
            st.success("✅ Cliente actualizado correctamente.")
            del st.session_state["editar_cliente"]
            st.rerun()


def toggle_activo(cliente_id, nombre, activo_actual):
    """Activa/desactiva cliente"""
    nuevo_estado = 0 if activo_actual else 1
    
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("UPDATE aup_agentes SET activo=? WHERE id=?", (nuevo_estado, cliente_id))
        conn.commit()
        conn.close()
        
        accion = "activado" if nuevo_estado else "desactivado"
        registrar_evento(cliente_id, "Cambio estado", f"Cliente '{nombre}' {accion}")
        st.success(f"✅ Cliente {accion}")
