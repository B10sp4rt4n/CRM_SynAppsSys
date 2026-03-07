# -*- coding: utf-8 -*-
"""
Módulo de Prospectos - Gestión Relacional AUP
Manejo de estados, vigencias y conversiones
Teléfonos diferenciados: empresa (prospecto) y personal (contacto)
"""

import streamlit as st
from datetime import date, timedelta
from core.database import get_connection
from core.event_logger import registrar_evento
from core.ui_utils import badge_estado, obtener_valor
import re


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
                telefono_empresa = st.text_input("📞 Teléfono principal de la empresa")
            with col2:
                estado = st.selectbox("Estado inicial", ["Nuevo", "En negociación", "Cerrado", "Perdido"])
                vigencia_dias = st.number_input("Vigencia (días)", min_value=1, value=90)
            
            submit = st.form_submit_button("💾 Guardar prospecto", width="stretch")
            
            if submit and nombre:
                conn = get_connection()
                if conn:
                    cur = conn.cursor()
                    vigencia = date.today() + timedelta(days=int(vigencia_dias))
                    atributos = f"sector={sector};telefono_empresa={telefono_empresa};estado={estado};vigencia={vigencia}"
                    cur.execute("""
                        INSERT INTO aup_agentes (tipo, nombre, atributos, activo)
                        VALUES (?, ?, ?, ?)
                    """, ("prospecto", nombre, atributos, 1))
                    prospecto_id = cur.lastrowid
                    conn.commit()
                    conn.close()
                    
                    registrar_evento(prospecto_id, "Alta prospecto", f"Prospecto '{nombre}' creado en estado '{estado}'")
                    st.success(f"✅ Prospecto '{nombre}' registrado correctamente")
                    st.balloons()
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
    
    # SI hay un formulario modal abierto, mostrarlo y salir
    if "prospecto_seleccionado" in st.session_state:
        st.divider()
        agregar_contacto(
            st.session_state["prospecto_seleccionado"],
            st.session_state.get("prospecto_nombre", "")
        )
        return  # No mostrar las tarjetas cuando hay un formulario abierto
    
    if "editar_prospecto" in st.session_state:
        st.divider()
        editar_prospecto(st.session_state["editar_prospecto"])
        return  # No mostrar las tarjetas cuando hay un formulario abierto
    
    # Mostrar tarjetas solo si no hay formularios modales abiertos
    for p in prospectos_filtrados:
        mostrar_tarjeta_prospecto(p)


def mostrar_tarjeta_prospecto(p):
    """Muestra la tarjeta de un prospecto con sus detalles y contactos"""
    atributos = p["atributos"] or ""
    
    # Parsear atributos con la función auxiliar
    estado = obtener_valor(atributos, "estado")
    sector = obtener_valor(atributos, "sector")
    telefono_empresa = obtener_valor(atributos, "telefono_empresa")
    vigencia = obtener_valor(atributos, "vigencia")
    
    # Usar badge centralizado (mantiene emoji + color para prospectos)
    badge = badge_estado(estado)
    
    # Colores específicos para prospectos (complemento visual)
    colores = {
        "Nuevo": "🔵",
        "En negociación": "🟡",
        "Cerrado": "🟢",
        "Perdido": "🔴"
    }
    color = colores.get(estado, "⚪")
    
    with st.container(border=True):
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"### {badge} {p['nombre']}")
            st.caption(f"**Sector:** {sector} | **📞 Tel. empresa:** {telefono_empresa}")
            st.caption(f"{color} **Estado:** {estado} | **Vigencia:** {vigencia}")
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
        
        # Mostrar contactos asociados
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT a.* FROM aup_agentes a
                INNER JOIN aup_relaciones r ON a.id = r.agente_destino
                WHERE r.agente_origen = ? AND r.tipo_relacion = 'tiene_contacto'
                ORDER BY a.fecha_creacion DESC
            """, (p["id"],))
            contactos = cur.fetchall()
            conn.close()
            
            if contactos:
                st.markdown("**📇 Contactos asociados:**")
                for c in contactos:
                    nombre_contacto = c["nombre"]
                    telefono_contacto = obtener_valor(c["atributos"], "telefono_contacto")
                    correo = obtener_valor(c["atributos"], "correo")
                    cargo = obtener_valor(c["atributos"], "cargo")
                    
                    estado_contacto = "✅" if c["activo"] else "❌"
                    st.write(f"  {estado_contacto} **{nombre_contacto}** — {cargo} | 📞 {telefono_contacto} | ✉️ {correo}")
                
                st.caption(f"Total de contactos vinculados: {len(contactos)}")
            else:
                st.info("💡 Sin contactos asociados aún")
        
        # Botones de acción
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button(f"✏️ Editar", key=f"edit_{p['id']}", width="stretch"):
                st.session_state["editar_prospecto"] = p["id"]
                st.rerun()
        
        with col2:
            if st.button(f"👤 Nuevo contacto", key=f"cont_{p['id']}", width="stretch"):
                st.session_state["prospecto_seleccionado"] = p["id"]
                st.session_state["prospecto_nombre"] = p["nombre"]
                st.rerun()
        
        with col3:
            if st.button(f"🔄 Convertir", key=f"conv_{p['id']}", width="stretch"):
                convertir_a_cliente(p["id"], p["nombre"], p["atributos"])
                st.rerun()
        
        with col4:
            texto_btn = "❌ Desactivar" if p["activo"] else "✅ Activar"
            if st.button(texto_btn, key=f"toggle_{p['id']}", type="secondary", width="stretch"):
                toggle_activo(p["id"], p["nombre"], p["activo"])
                st.rerun()


def editar_prospecto(prospecto_id):
    """Formulario de edición de prospecto"""
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
    
    # Obtener valores actuales
    atributos = p["atributos"] or ""
    
    with st.form("form_editar_prospecto"):
        nombre = st.text_input("Nombre", value=p["nombre"])
        
        col1, col2 = st.columns(2)
        with col1:
            sector = st.text_input("Sector", value=obtener_valor(atributos, "sector"))
            telefono_empresa = st.text_input("📞 Teléfono empresa", value=obtener_valor(atributos, "telefono_empresa"))
        with col2:
            estado_actual = obtener_valor(atributos, "estado")
            if estado_actual == "—":
                estado_actual = "Nuevo"
            estados = ["Nuevo", "En negociación", "Cerrado", "Perdido"]
            idx = estados.index(estado_actual) if estado_actual in estados else 0
            estado = st.selectbox("Estado", estados, index=idx)
            activo = st.checkbox("Vigente", value=bool(p["activo"]))
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("💾 Guardar cambios", width="stretch")
        with col2:
            cancel = st.form_submit_button("❌ Cancelar", width="stretch")
    
    if cancel:
        del st.session_state["editar_prospecto"]
        st.rerun()
    
    if submit:
        vigencia_actual = obtener_valor(atributos, "vigencia")
        nuevos_atributos = f"sector={sector};telefono_empresa={telefono_empresa};estado={estado};vigencia={vigencia_actual}"
        
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE aup_agentes SET nombre=?, atributos=?, activo=? WHERE id=?",
                (nombre, nuevos_atributos, 1 if activo else 0, prospecto_id)
            )
            conn.commit()
            conn.close()
            
            registrar_evento(prospecto_id, "Actualización", f"Prospecto '{nombre}' actualizado. Estado: {estado}")
            st.success("✅ Prospecto actualizado correctamente.")
            del st.session_state["editar_prospecto"]
            st.rerun()


def agregar_contacto(prospecto_id, prospecto_nombre):
    """Agrega un nuevo contacto vinculado al prospecto"""
    st.subheader(f"� Nuevo contacto para: {prospecto_nombre}")
    
    with st.form("form_nuevo_contacto", clear_on_submit=True):
        nombre_contacto = st.text_input("Nombre del contacto")
        
        col1, col2 = st.columns(2)
        with col1:
            telefono_contacto = st.text_input("📱 Teléfono directo o móvil")
            correo = st.text_input("✉️ Correo electrónico")
        with col2:
            cargo = st.text_input("💼 Cargo o puesto")
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("💾 Guardar contacto", width="stretch")
        with col2:
            cancel = st.form_submit_button("❌ Cancelar", width="stretch")
    
    if cancel:
        if "prospecto_seleccionado" in st.session_state:
            del st.session_state["prospecto_seleccionado"]
        if "prospecto_nombre" in st.session_state:
            del st.session_state["prospecto_nombre"]
        st.rerun()
    
    if submit and nombre_contacto:
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            atributos = f"telefono_contacto={telefono_contacto};correo={correo};cargo={cargo}"
            cur.execute("""
                INSERT INTO aup_agentes (tipo, nombre, atributos, activo)
                VALUES (?, ?, ?, ?)
            """, ("contacto", nombre_contacto, atributos, 1))
            contacto_id = cur.lastrowid
            
            cur.execute("""
                INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)
                VALUES (?, ?, ?)
            """, (prospecto_id, contacto_id, "tiene_contacto"))
            
            conn.commit()
            conn.close()
            
            registrar_evento(contacto_id, "Alta contacto", f"Contacto '{nombre_contacto}' agregado al prospecto ID {prospecto_id}")
            st.success(f"✅ Contacto '{nombre_contacto}' vinculado correctamente al prospecto")
            
            # Limpiar session state
            if "prospecto_seleccionado" in st.session_state:
                del st.session_state["prospecto_seleccionado"]
            if "prospecto_nombre" in st.session_state:
                del st.session_state["prospecto_nombre"]
            st.rerun()


def convertir_a_cliente(prospecto_id, nombre, atributos):
    """Convierte un prospecto en cliente y transfiere sus contactos"""
    conn = get_connection()
    if not conn:
        st.error("❌ Error al conectar con la base de datos.")
        return
    
    cur = conn.cursor()
    
    # Verificar si ya fue convertido
    cur.execute("""
        SELECT * FROM aup_relaciones 
        WHERE agente_origen = ? AND tipo_relacion = 'convertido_en'
    """, (prospecto_id,))
    
    if cur.fetchone():
        st.warning("⚠️ Este prospecto ya fue convertido a cliente.")
        conn.close()
        return
    
    # Crear el nuevo cliente con los mismos atributos
    cur.execute("""
        INSERT INTO aup_agentes (tipo, nombre, atributos, activo)
        VALUES (?, ?, ?, ?)
    """, ("cliente", nombre, atributos, 1))
    cliente_id = cur.lastrowid
    
    # Crear relación de conversión
    cur.execute("""
        INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)
        VALUES (?, ?, ?)
    """, (prospecto_id, cliente_id, "convertido_en"))
    
    # Transferir contactos al nuevo cliente
    cur.execute("""
        SELECT agente_destino FROM aup_relaciones 
        WHERE agente_origen = ? AND tipo_relacion = 'tiene_contacto'
    """, (prospecto_id,))
    contactos = cur.fetchall()
    
    for contacto in contactos:
        cur.execute("""
            INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)
            VALUES (?, ?, ?)
        """, (cliente_id, contacto['agente_destino'], "contacto_principal"))
    
    conn.commit()
    conn.close()
    
    registrar_evento(cliente_id, "Conversión", f"Prospecto '{nombre}' convertido a cliente (ID: {cliente_id}). {len(contactos)} contactos transferidos.")
    st.success(f"🎉 ¡Prospecto '{nombre}' ahora es cliente! (ID: {cliente_id})")
    if contactos:
        st.info(f"📇 {len(contactos)} contacto(s) transferido(s) al nuevo cliente")
    st.balloons()


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
