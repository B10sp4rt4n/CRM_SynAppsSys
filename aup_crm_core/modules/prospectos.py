# -*- coding: utf-8 -*-
"""
Módulo de Prospectos - Gestión Relacional AUP
Manejo de estados, vigencias y conversiones
"""

import streamlit as st
from datetime import date, timedelta
from core.database import get_connection
from core.event_logger import registrar_evento

def show():
    """Interfaz principal del módulo de prospectos"""
    st.header("🎯 Gestión de Prospectos")
    
    # Crear nuevo prospecto
    with st.expander("➕ Registrar nuevo prospecto"):
        with st.form("form_nuevo_prospecto"):
            nombre = st.text_input("Nombre del prospecto o empresa")
            col1, col2 = st.columns(2)
            with col1:
                sector = st.text_input("Sector o giro")
                telefono = st.text_input("Teléfono")
            with col2:
                estado = st.selectbox("Estado inicial", ["Nuevo", "En negociación", "Cerrado", "Perdido"])
                vigencia_dias = st.number_input("Vigencia (días)", min_value=1, value=90)
            
            submit = st.form_submit_button("💾 Guardar prospecto", use_container_width=True)
            
            if submit and nombre:
                conn = get_connection()
                if conn:
                    cur = conn.cursor()
                    vigencia = date.today() + timedelta(days=int(vigencia_dias))
                    atributos = f"sector={sector};telefono={telefono};estado={estado};vigencia={vigencia}"
                    cur.execute("""
                        INSERT INTO aup_agentes (tipo, nombre, atributos, activo)
                        VALUES (?, ?, ?, ?)
                    """, ("prospecto", nombre, atributos, 1))
                    prospecto_id = cur.lastrowid
                    conn.commit()
                    conn.close()
                    
                    registrar_evento(prospecto_id, "Alta prospecto", f"Prospecto creado en estado {estado}")
                    st.success(f"✅ Prospecto {nombre} registrado")
                    st.rerun()
    
    st.divider()
    
    # Listado de prospectos
    st.subheader("📋 Listado de Prospectos")
    
    conn = get_connection()
    if not conn:
        st.error("Error de conexión")
        return
        
    cur = conn.cursor()
    cur.execute("SELECT * FROM aup_agentes WHERE tipo=? ORDER BY fecha_creacion DESC", ("prospecto",))
    prospectos = cur.fetchall()
    conn.close()
    
    if not prospectos:
        st.info("No hay prospectos registrados aún.")
        return
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        filtro_estado = st.multiselect(
            "Filtrar por estado",
            ["Nuevo", "En negociación", "Cerrado", "Perdido"],
            default=["Nuevo", "En negociación"]
        )
    with col2:
        mostrar_inactivos = st.checkbox("Mostrar inactivos", value=False)
    
    # Aplicar filtros
    prospectos_filtrados = []
    for p in prospectos:
        atributos = p["atributos"] or ""
        estado = "Nuevo"
        if "estado=" in atributos:
            estado = atributos.split("estado=")[1].split(";")[0]
        
        if estado not in filtro_estado:
            continue
        if not mostrar_inactivos and not p["activo"]:
            continue
        
        prospectos_filtrados.append(p)
    
    st.caption(f"Mostrando {len(prospectos_filtrados)} de {len(prospectos)} prospectos")
    
    # Mostrar tarjetas
    for p in prospectos_filtrados:
        mostrar_tarjeta_prospecto(p)
    
    # Formularios modales
    if "editar_prospecto" in st.session_state:
        st.divider()
        editar_prospecto(st.session_state["editar_prospecto"])
    
    if "contactos_prospecto" in st.session_state:
        st.divider()
        gestionar_contactos(
            st.session_state["contactos_prospecto"],
            st.session_state.get("contactos_prospecto_nombre", "")
        )


def mostrar_tarjeta_prospecto(p):
    """Muestra tarjeta de un prospecto"""
    atributos = p["atributos"] or ""
    
    attrs = {}
    for attr in atributos.split(";"):
        if "=" in attr:
            key, value = attr.split("=", 1)
            attrs[key] = value
    
    estado = attrs.get("estado", "Nuevo")
    sector = attrs.get("sector", "N/A")
    telefono = attrs.get("telefono", "N/A")
    vigencia = attrs.get("vigencia", "N/A")
    
    # Emojis por estado
    estado_config = {
        "Nuevo": {"emoji": "🆕", "color": "🔵"},
        "En negociación": {"emoji": "💬", "color": "🟡"},
        "Cerrado": {"emoji": "✅", "color": "🟢"},
        "Perdido": {"emoji": "❌", "color": "🔴"}
    }
    
    config = estado_config.get(estado, {"emoji": "📋", "color": "⚪"})
    
    with st.container(border=True):
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"### {config['emoji']} {p['nombre']}")
            st.caption(f"**Sector:** {sector} | **Tel:** {telefono}")
            st.caption(f"{config['color']} **Estado:** {estado} | **Vigencia:** {vigencia}")
            if not p["activo"]:
                st.warning("⚠️ Prospecto inactivo")
        
        with col2:
            st.caption(f"ID: {p['id']}")
            st.caption(f"📅 {p['fecha_creacion'][:10]}")
        
        with col3:
            if p["activo"]:
                st.success("✅ Vigente")
            else:
                st.error("❌ Inactivo")
        
        # Botones de acción
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button(f"✏️ Editar", key=f"edit_{p['id']}", use_container_width=True):
                st.session_state["editar_prospecto"] = p["id"]
                st.rerun()
        
        with col2:
            if st.button(f"👤 Contactos", key=f"cont_{p['id']}", use_container_width=True):
                st.session_state["contactos_prospecto"] = p["id"]
                st.session_state["contactos_prospecto_nombre"] = p["nombre"]
                st.rerun()
        
        with col3:
            if st.button(f"🔄 Convertir", key=f"conv_{p['id']}", use_container_width=True):
                convertir_a_cliente(p["id"], p["nombre"])
                st.rerun()
        
        with col4:
            texto_btn = "❌ Desactivar" if p["activo"] else "✅ Activar"
            if st.button(texto_btn, key=f"toggle_{p['id']}", type="secondary", use_container_width=True):
                toggle_activo(p["id"], p["nombre"], p["activo"])
                st.rerun()


def editar_prospecto(prospecto_id):
    """Formulario de edición"""
    conn = get_connection()
    if not conn:
        st.error("Error de conexión")
        return
        
    cur = conn.cursor()
    cur.execute("SELECT * FROM aup_agentes WHERE id=?", (prospecto_id,))
    p = cur.fetchone()
    conn.close()
    
    if not p:
        st.error("❌ Prospecto no encontrado.")
        return
    
    st.subheader(f"✏️ Editar prospecto: {p['nombre']}")
    
    atributos = p["atributos"] or ""
    attrs = {}
    for attr in atributos.split(";"):
        if "=" in attr:
            key, value = attr.split("=", 1)
            attrs[key] = value
    
    with st.form("form_editar_prospecto"):
        nombre = st.text_input("Nombre", value=p["nombre"])
        
        col1, col2 = st.columns(2)
        with col1:
            sector = st.text_input("Sector", value=attrs.get("sector", ""))
            telefono = st.text_input("Teléfono", value=attrs.get("telefono", ""))
        with col2:
            estado_actual = attrs.get("estado", "Nuevo")
            estados = ["Nuevo", "En negociación", "Cerrado", "Perdido"]
            idx = estados.index(estado_actual) if estado_actual in estados else 0
            estado = st.selectbox("Estado", estados, index=idx)
            activo = st.checkbox("Vigente", value=bool(p["activo"]))
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
        with col2:
            cancel = st.form_submit_button("❌ Cancelar", use_container_width=True)
    
    if cancel:
        del st.session_state["editar_prospecto"]
        st.rerun()
    
    if submit:
        nuevos_atributos = f"sector={sector};telefono={telefono};estado={estado};vigencia={attrs.get('vigencia', date.today())}"
        
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE aup_agentes SET nombre=?, atributos=?, activo=? WHERE id=?",
                (nombre, nuevos_atributos, 1 if activo else 0, prospecto_id)
            )
            conn.commit()
            conn.close()
            
            registrar_evento(prospecto_id, "Actualización", f"Prospecto actualizado. Estado: {estado}")
            st.success("✅ Prospecto actualizado correctamente.")
            del st.session_state["editar_prospecto"]
            st.rerun()


def gestionar_contactos(prospecto_id, prospecto_nombre):
    """Gestión de contactos"""
    st.subheader(f"👥 Contactos de: {prospecto_nombre}")
    
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT a.* FROM aup_agentes a
            INNER JOIN aup_relaciones r ON a.id = r.agente_destino
            WHERE r.agente_origen = ? AND r.tipo_relacion = 'tiene_contacto'
            ORDER BY a.fecha_creacion DESC
        """, (prospecto_id,))
        contactos = cur.fetchall()
        conn.close()
        
        if contactos:
            for c in contactos:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**{c['nombre']}**")
                with col2:
                    st.success("✅" if c["activo"] else "❌")
        else:
            st.info("No hay contactos registrados.")
    
    # Agregar contacto
    with st.form("form_nuevo_contacto"):
        st.write("➕ Agregar nuevo contacto")
        nombre_contacto = st.text_input("Nombre del contacto")
        submit = st.form_submit_button("💾 Guardar", use_container_width=True)
        
        if submit and nombre_contacto:
            conn = get_connection()
            if conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO aup_agentes (tipo, nombre, atributos, activo) VALUES (?, ?, ?, ?)",
                    ("contacto", nombre_contacto, "", 1)
                )
                contacto_id = cur.lastrowid
                
                cur.execute(
                    "INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion) VALUES (?, ?, ?)",
                    (prospecto_id, contacto_id, "tiene_contacto")
                )
                
                conn.commit()
                conn.close()
                
                registrar_evento(prospecto_id, "Contacto agregado", f"Contacto {nombre_contacto} asociado")
                st.success(f"✅ Contacto agregado")
                st.rerun()
    
    if st.button("← Volver", use_container_width=True):
        del st.session_state["contactos_prospecto"]
        if "contactos_prospecto_nombre" in st.session_state:
            del st.session_state["contactos_prospecto_nombre"]
        st.rerun()


def convertir_a_cliente(prospecto_id, nombre):
    """Convierte prospecto a cliente"""
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        
        cur.execute("UPDATE aup_agentes SET tipo='cliente' WHERE id=?", (prospecto_id,))
        
        cur.execute(
            "INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion) VALUES (?, ?, ?)",
            (prospecto_id, prospecto_id, "convertido_en_cliente")
        )
        
        conn.commit()
        conn.close()
        
        registrar_evento(prospecto_id, "Conversión", f"Prospecto {nombre} convertido en cliente")
        st.success(f"🎉 ¡Prospecto {nombre} convertido en cliente!")


def toggle_activo(prospecto_id, nombre, activo_actual):
    """Activa/desactiva prospecto"""
    nuevo_estado = 0 if activo_actual else 1
    
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("UPDATE aup_agentes SET activo=? WHERE id=?", (nuevo_estado, prospecto_id))
        conn.commit()
        conn.close()
        
        accion = "activado" if nuevo_estado else "desactivado"
        registrar_evento(prospecto_id, "Cambio estado", f"Prospecto {nombre} {accion}")
        st.success(f"✅ Prospecto {accion}")
