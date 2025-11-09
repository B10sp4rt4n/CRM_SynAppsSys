# -*- coding: utf-8 -*-
"""
Módulo de Clientes - Gestión Relacional AUP
Visualización de prospectos convertidos en clientes
"""

import streamlit as st
from datetime import date
from core.database import get_connection
from core.event_logger import registrar_evento
import re

# ==========================================================
#  🧩 FUNCIONES AUXILIARES
# ==========================================================

def obtener_valor(atributos, clave):
    """Extrae un valor del string de atributos usando regex"""
    match = re.search(rf"{clave}=([^;]+)", atributos or "")
    return match.group(1) if match else "—"


def show():
    """Interfaz principal del módulo de clientes"""
    st.header("👥 Gestión de Clientes")
    
    # Obtener clientes
    conn = get_connection()
    if not conn:
        st.error("Error al conectar con la base de datos")
        return
        
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM aup_agentes 
        WHERE tipo='cliente' 
        ORDER BY fecha_creacion DESC
    """)
    clientes = cur.fetchall()
    conn.close()
    
    if not clientes:
        st.info("📋 No hay clientes registrados aún.")
        st.caption("💡 Los clientes aparecen aquí cuando conviertes un prospecto usando el botón '🔄 Convertir' en el módulo de Prospectos.")
        return
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        mostrar_inactivos = st.checkbox("Mostrar inactivos", value=False)
    with col2:
        st.metric("Total clientes", len(clientes))
    
    st.divider()
    
    # Aplicar filtros
    clientes_filtrados = []
    for c in clientes:
        if not mostrar_inactivos and not c["activo"]:
            continue
        clientes_filtrados.append(c)
    
    st.caption(f"Mostrando {len(clientes_filtrados)} de {len(clientes)} clientes")
    
    # SI hay un formulario modal abierto, mostrarlo y salir
    if "editar_cliente" in st.session_state:
        st.divider()
        editar_cliente(st.session_state["editar_cliente"])
        return  # No mostrar las tarjetas cuando hay un formulario abierto
    
    # Mostrar tarjetas solo si no hay formularios modales abiertos
    for c in clientes_filtrados:
        mostrar_tarjeta_cliente(c)


def mostrar_tarjeta_cliente(c):
    """Muestra la tarjeta de un cliente con sus detalles y contactos"""
    atributos = c["atributos"] or ""
    
    # Parsear atributos
    estado = obtener_valor(atributos, "estado")
    sector = obtener_valor(atributos, "sector")
    telefono_empresa = obtener_valor(atributos, "telefono_empresa")
    vigencia = obtener_valor(atributos, "vigencia")
    
    # Badges visuales por estado comercial
    color_estado = {
        "Activo": "🟢",
        "Suspendido": "🟠",
        "No renovado": "🔴",
        "Nuevo": "🔵",
        "En negociación": "🟡",
        "Cerrado": "🟢",
        "Perdido": "🔴"
    }
    badge_estado = color_estado.get(estado, "⚪")
    
    # Obtener prospecto original
    conn = get_connection()
    prospecto_id = None
    if conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT agente_origen FROM aup_relaciones 
            WHERE agente_destino = ? AND tipo_relacion = 'convertido_en'
        """, (c["id"],))
        resultado = cur.fetchone()
        if resultado:
            prospecto_id = resultado["agente_origen"]
        conn.close()
    
    with st.container(border=True):
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"### 💼 {c['nombre']}")
            st.caption(f"**Sector:** {sector} | **📞 Tel. empresa:** {telefono_empresa}")
            st.caption(f"{badge_estado} **Estado:** {estado} | **Vigencia:** {vigencia}")
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
            if st.button(f"📊 Ver oportunidades", key=f"opor_{c['id']}", use_container_width=True, disabled=True):
                st.info("Módulo de Oportunidades próximamente")
        
        with col3:
            texto_btn = "❌ Desactivar" if c["activo"] else "✅ Activar"
            if st.button(texto_btn, key=f"toggle_{c['id']}", type="secondary", use_container_width=True):
                toggle_activo(c["id"], c["nombre"], c["activo"])
                st.rerun()


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
