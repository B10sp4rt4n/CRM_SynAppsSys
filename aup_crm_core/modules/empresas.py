# -*- coding: utf-8 -*-
"""
Módulo de Empresas - Base del flujo comercial
Empresa → Contactos → [Generar Prospecto]
"""

import streamlit as st
from datetime import date
from core.database import get_connection
from core.event_logger import registrar_evento
from core.ui_utils import obtener_valor
import re


def show():
    """Interfaz principal del módulo de empresas"""
    st.header("🏢 Gestión de Empresas")
    
    # Crear nueva empresa
    with st.expander("➕ Registrar nueva empresa"):
        with st.form("form_nueva_empresa"):
            nombre = st.text_input("Nombre de la empresa *", placeholder="Ej. Acme Corporation")
            col1, col2 = st.columns(2)
            with col1:
                sector = st.text_input("Sector o giro", placeholder="Ej. Tecnología")
                telefono = st.text_input("📞 Teléfono principal", placeholder="Ej. +52 55 1234 5678")
            with col2:
                direccion = st.text_area("Dirección", placeholder="Calle, número, colonia, ciudad")
                rfc = st.text_input("RFC", placeholder="Opcional")
            
            submit = st.form_submit_button("💾 Guardar empresa", use_container_width=True)
            
            if submit and nombre:
                conn = get_connection()
                if conn:
                    cur = conn.cursor()
                    atributos = f"sector={sector};telefono={telefono};direccion={direccion};rfc={rfc}"
                    cur.execute("""
                        INSERT INTO aup_agentes (tipo, nombre, atributos, activo)
                        VALUES (?, ?, ?, ?)
                    """, ("empresa", nombre, atributos, 1))
                    empresa_id = cur.lastrowid
                    conn.commit()
                    conn.close()
                    
                    registrar_evento(empresa_id, "Alta empresa", f"Empresa '{nombre}' creada")
                    st.success(f"✅ Empresa '{nombre}' registrada correctamente")
                    st.balloons()
                    st.rerun()
    
    st.divider()
    
    # Listado de empresas
    st.subheader("📋 Listado de Empresas")
    
    conn = get_connection()
    if not conn:
        st.error("Error de conexión")
        return
        
    cur = conn.cursor()
    cur.execute("SELECT * FROM aup_agentes WHERE tipo='empresa' ORDER BY nombre ASC")
    empresas = cur.fetchall()
    conn.close()
    
    if not empresas:
        st.info("No hay empresas registradas aún.")
        return
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        mostrar_inactivos = st.checkbox("Mostrar inactivas", value=False)
    with col2:
        st.metric("Total empresas", len(empresas))
    
    # Aplicar filtros
    empresas_filtradas = [e for e in empresas if mostrar_inactivos or e["activo"]]
    
    st.caption(f"Mostrando {len(empresas_filtradas)} de {len(empresas)} empresas")
    st.divider()
    
    # SI hay un formulario modal abierto, mostrarlo y salir
    if "editar_empresa" in st.session_state:
        editar_empresa(st.session_state["editar_empresa"])
        return
    
    if "agregar_contacto_empresa" in st.session_state:
        agregar_contacto(st.session_state["agregar_contacto_empresa"])
        return
    
    # Mostrar tarjetas
    for e in empresas_filtradas:
        mostrar_tarjeta_empresa(e)


def mostrar_tarjeta_empresa(e):
    """Muestra la tarjeta de una empresa con contactos y botón generar prospecto"""
    atributos = e["atributos"] or ""
    
    sector = obtener_valor(atributos, "sector")
    telefono = obtener_valor(atributos, "telefono")
    direccion = obtener_valor(atributos, "direccion")
    rfc = obtener_valor(atributos, "rfc")
    
    # Obtener contactos
    conn = get_connection()
    contactos = []
    prospecto_id = None
    
    if conn:
        cur = conn.cursor()
        # Obtener contactos asociados
        cur.execute("""
            SELECT a.* FROM aup_agentes a
            INNER JOIN aup_relaciones r ON r.agente_destino = a.id
            WHERE r.agente_origen = ? AND r.tipo_relacion = 'tiene_contacto'
            AND a.activo = 1
        """, (e["id"],))
        contactos = cur.fetchall()
        
        # Verificar si ya tiene prospecto generado
        cur.execute("""
            SELECT agente_destino FROM aup_relaciones
            WHERE agente_origen = ? AND tipo_relacion = 'genero_prospecto'
        """, (e["id"],))
        resultado = cur.fetchone()
        if resultado:
            prospecto_id = resultado["agente_destino"]
        
        conn.close()
    
    tiene_contactos = len(contactos) > 0
    opacity = "opacity: 0.6;" if not e["activo"] else ""
    
    with st.container(border=True):
        st.markdown(f"<div style='{opacity}'>", unsafe_allow_html=True)
        st.markdown(f"### 🏢 {e['nombre']}")
        
        # Métricas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption(f"**Sector:** {sector}")
        with col2:
            st.caption(f"**📞:** {telefono}")
        with col3:
            st.caption(f"**Contactos:** {len(contactos)}")
        
        if direccion != "—":
            st.caption(f"📍 **Dirección:** {direccion}")
        if rfc != "—":
            st.caption(f"**RFC:** {rfc}")
        
        # Mostrar contactos
        if contactos:
            with st.expander(f"📇 Ver contactos ({len(contactos)})"):
                for c in contactos:
                    nombre_contacto = c["nombre"]
                    cargo = obtener_valor(c["atributos"], "cargo")
                    telefono_contacto = obtener_valor(c["atributos"], "telefono")
                    correo = obtener_valor(c["atributos"], "correo")
                    st.write(f"**{nombre_contacto}** — {cargo}")
                    st.caption(f"📞 {telefono_contacto} | ✉️ {correo}")
                    st.divider()
        else:
            st.warning("⚠️ Esta empresa no tiene contactos registrados")
        
        # Mostrar estado del prospecto si existe
        if prospecto_id:
            st.success(f"✅ Prospecto generado (ID: {prospecto_id})")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Botones de acción
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("✏️ Editar", key=f"edit_emp_{e['id']}", use_container_width=True):
                st.session_state["editar_empresa"] = e["id"]
                st.rerun()
        
        with col2:
            if st.button("👤 + Contacto", key=f"add_cont_{e['id']}", use_container_width=True):
                st.session_state["agregar_contacto_empresa"] = e["id"]
                st.rerun()
        
        with col3:
            # REGLA R1: Solo habilitar si tiene contactos y no tiene prospecto
            if tiene_contactos and not prospecto_id:
                if st.button("🎯 Generar Prospecto", key=f"gen_pros_{e['id']}", use_container_width=True, type="primary"):
                    generar_prospecto(e["id"], e["nombre"])
                    st.rerun()
            elif not tiene_contactos:
                st.button("🎯 Generar Prospecto", key=f"gen_pros_dis_{e['id']}", use_container_width=True, disabled=True, help="Requiere al menos 1 contacto")
            elif prospecto_id:
                st.button("✅ Prospecto creado", key=f"gen_pros_ok_{e['id']}", use_container_width=True, disabled=True)
        
        with col4:
            if e["activo"]:
                if st.button("❌ Desactivar", key=f"deact_emp_{e['id']}", use_container_width=True):
                    desactivar_empresa(e["id"], e["nombre"])
                    st.rerun()
            else:
                if st.button("✅ Activar", key=f"act_emp_{e['id']}", use_container_width=True):
                    activar_empresa(e["id"], e["nombre"])
                    st.rerun()


def agregar_contacto(empresa_id):
    """Formulario modal para agregar contacto a una empresa"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    cur.execute("SELECT * FROM aup_agentes WHERE id=?", (empresa_id,))
    empresa = cur.fetchone()
    conn.close()
    
    if not empresa:
        return
    
    st.subheader(f"👤 Agregar contacto a: {empresa['nombre']}")
    
    with st.form("form_nuevo_contacto"):
        nombre = st.text_input("Nombre completo del contacto *", placeholder="Ej. Juan Pérez")
        col1, col2 = st.columns(2)
        with col1:
            cargo = st.text_input("Cargo o puesto", placeholder="Ej. Director de Compras")
            telefono = st.text_input("📞 Teléfono personal", placeholder="Ej. +52 55 9876 5432")
        with col2:
            correo = st.text_input("✉️ Correo electrónico", placeholder="ejemplo@empresa.com")
            principal = st.checkbox("Es contacto principal", value=False)
        
        col_submit, col_cancel = st.columns(2)
        with col_submit:
            submit = st.form_submit_button("💾 Guardar contacto", use_container_width=True)
        with col_cancel:
            cancel = st.form_submit_button("❌ Cancelar", use_container_width=True)
        
        if cancel:
            del st.session_state["agregar_contacto_empresa"]
            st.rerun()
        
        if submit and nombre:
            # Validar email
            if correo and not re.match(r"[^@]+@[^@]+\.[^@]+", correo):
                st.error("❌ Formato de correo inválido")
                return
            
            conn = get_connection()
            if conn:
                cur = conn.cursor()
                atributos = f"cargo={cargo};telefono={telefono};correo={correo}"
                
                # Crear contacto
                cur.execute("""
                    INSERT INTO aup_agentes (tipo, nombre, atributos, activo)
                    VALUES (?, ?, ?, ?)
                """, ("contacto", nombre, atributos, 1))
                contacto_id = cur.lastrowid
                
                # Crear relación
                tipo_rel = "contacto_principal" if principal else "tiene_contacto"
                cur.execute("""
                    INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)
                    VALUES (?, ?, ?)
                """, (empresa_id, contacto_id, tipo_rel))
                
                conn.commit()
                conn.close()
                
                registrar_evento(contacto_id, "Alta contacto", f"Contacto '{nombre}' vinculado a empresa ID {empresa_id}")
                st.success(f"✅ Contacto '{nombre}' agregado correctamente")
                del st.session_state["agregar_contacto_empresa"]
                st.rerun()


def generar_prospecto(empresa_id, empresa_nombre):
    """REGLA R1: Genera prospecto solo si empresa tiene contactos"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    
    # Verificar que tenga contactos
    cur.execute("""
        SELECT COUNT(*) as total FROM aup_relaciones
        WHERE agente_origen = ? AND tipo_relacion = 'tiene_contacto'
    """, (empresa_id,))
    
    if cur.fetchone()["total"] == 0:
        st.error("❌ No se puede generar prospecto sin contactos")
        conn.close()
        return
    
    # Obtener datos de la empresa para heredar
    cur.execute("SELECT * FROM aup_agentes WHERE id=?", (empresa_id,))
    empresa = cur.fetchone()
    
    # Crear prospecto con atributos base
    atributos_empresa = empresa["atributos"] or ""
    atributos_prospecto = atributos_empresa + ";estado=Nuevo;es_cliente=0"
    
    cur.execute("""
        INSERT INTO aup_agentes (tipo, nombre, atributos, activo)
        VALUES (?, ?, ?, ?)
    """, ("prospecto", empresa_nombre, atributos_prospecto, 1))
    prospecto_id = cur.lastrowid
    
    # Crear relación empresa → prospecto
    cur.execute("""
        INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)
        VALUES (?, ?, ?)
    """, (empresa_id, prospecto_id, "genero_prospecto"))
    
    # Copiar relaciones de contactos al prospecto
    cur.execute("""
        SELECT agente_destino FROM aup_relaciones
        WHERE agente_origen = ? AND tipo_relacion IN ('tiene_contacto', 'contacto_principal')
    """, (empresa_id,))
    contactos = cur.fetchall()
    
    for c in contactos:
        cur.execute("""
            INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)
            VALUES (?, ?, ?)
        """, (prospecto_id, c["agente_destino"], "tiene_contacto"))
    
    conn.commit()
    conn.close()
    
    registrar_evento(prospecto_id, "Generación prospecto", f"Prospecto generado desde empresa ID {empresa_id}")
    st.success(f"✅ Prospecto '{empresa_nombre}' generado correctamente (ID: {prospecto_id})")
    st.balloons()


def editar_empresa(empresa_id):
    """Formulario modal para editar empresa"""
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    cur.execute("SELECT * FROM aup_agentes WHERE id=?", (empresa_id,))
    empresa = cur.fetchone()
    conn.close()
    
    if not empresa:
        return
    
    atributos = empresa["atributos"] or ""
    
    st.subheader(f"✏️ Editar: {empresa['nombre']}")
    
    with st.form("form_editar_empresa"):
        nombre = st.text_input("Nombre", value=empresa["nombre"])
        col1, col2 = st.columns(2)
        with col1:
            sector = st.text_input("Sector", value=obtener_valor(atributos, "sector"))
            telefono = st.text_input("Teléfono", value=obtener_valor(atributos, "telefono"))
        with col2:
            direccion = st.text_area("Dirección", value=obtener_valor(atributos, "direccion"))
            rfc = st.text_input("RFC", value=obtener_valor(atributos, "rfc"))
        
        col_submit, col_cancel = st.columns(2)
        with col_submit:
            submit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
        with col_cancel:
            cancel = st.form_submit_button("❌ Cancelar", use_container_width=True)
        
        if cancel:
            del st.session_state["editar_empresa"]
            st.rerun()
        
        if submit:
            conn = get_connection()
            if conn:
                cur = conn.cursor()
                nuevos_atributos = f"sector={sector};telefono={telefono};direccion={direccion};rfc={rfc}"
                cur.execute("""
                    UPDATE aup_agentes 
                    SET nombre=?, atributos=?
                    WHERE id=?
                """, (nombre, nuevos_atributos, empresa_id))
                conn.commit()
                conn.close()
                
                registrar_evento(empresa_id, "Edición empresa", f"Empresa '{nombre}' actualizada")
                st.success("✅ Empresa actualizada correctamente")
                del st.session_state["editar_empresa"]
                st.rerun()


def desactivar_empresa(empresa_id, nombre):
    """Desactiva una empresa"""
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("UPDATE aup_agentes SET activo=0 WHERE id=?", (empresa_id,))
        conn.commit()
        conn.close()
        registrar_evento(empresa_id, "Desactivación", f"Empresa '{nombre}' desactivada")
        st.success(f"✅ Empresa '{nombre}' desactivada")


def activar_empresa(empresa_id, nombre):
    """Activa una empresa"""
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("UPDATE aup_agentes SET activo=1 WHERE id=?", (empresa_id,))
        conn.commit()
        conn.close()
        registrar_evento(empresa_id, "Activación", f"Empresa '{nombre}' activada")
        st.success(f"✅ Empresa '{nombre}' activada")
