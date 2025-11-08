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
    
    # Mostrar cada cliente
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
            st.caption(f"**Estado original:** {estado} | **Vigencia:** {vigencia}")
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
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(f"📊 Ver oportunidades", key=f"opor_{c['id']}", use_container_width=True, disabled=True):
                st.info("Módulo de Oportunidades próximamente")
        
        with col2:
            texto_btn = "❌ Desactivar" if c["activo"] else "✅ Activar"
            if st.button(texto_btn, key=f"toggle_{c['id']}", type="secondary", use_container_width=True):
                toggle_activo(c["id"], c["nombre"], c["activo"])
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
