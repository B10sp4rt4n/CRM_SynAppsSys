# ================================================================
#  ui/identidad.py  |  CRM-EXO v2  (Núcleo 1: Identidad)
#  ---------------------------------------------------------------
#  Interfaz Streamlit para:
#   • Alta de Empresa
#   • Alta de Contacto (ligado a empresa)
#   • Generación de Prospecto (empresa + contacto)
#   • Visualización de trazabilidad forense
# ================================================================

import streamlit as st
import sqlite3
import hashlib
from datetime import datetime
import pandas as pd
import os
from pathlib import Path

# Ruta relativa desde raíz del proyecto
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "crm_exo_v2" / "data" / "crm_exo_v2.sqlite"


# ================================================================
#  FUNCIONES AUXILIARES
# ================================================================

def conectar():
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def hash_evento(entidad, accion, valores):
    """Calcula hash SHA256 simplificado para eventos UI"""
    raw = f"{entidad}|{accion}|{valores}|{datetime.utcnow().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()

def registrar_evento(con, entidad, id_entidad, accion, valor_nuevo, usuario="ui"):
    """Inserta evento en historial_general con hash automático"""
    ts = datetime.utcnow().isoformat()
    h = hash_evento(entidad, accion, valor_nuevo)
    con.execute("""
        INSERT INTO historial_general
        (entidad, id_entidad, accion, valor_nuevo, usuario, timestamp, hash_evento)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (entidad, id_entidad, accion, valor_nuevo, usuario, ts, h))
    con.commit()
    return h


# ================================================================
#  PANELES DE ALTA Y VISUALIZACIÓN
# ================================================================

st.set_page_config(page_title="CRM-EXO v2 - Identidad", layout="wide")
st.title("🏗️ CRM-EXO v2 — Núcleo 1: Identidad (AUP)")

# Tabs para organizar mejor la interfaz
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard",
    "🏢 Empresas",
    "👤 Contactos",
    "📈 Prospectos"
])

# ---------------------------------------------------------------
# TAB 1: Dashboard de resumen
# ---------------------------------------------------------------
with tab1:
    st.header("Dashboard de Identidad")
    
    con = conectar()
    
    # Métricas generales
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_empresas = pd.read_sql("SELECT COUNT(*) as total FROM empresas", con).iloc[0]["total"]
        st.metric("Empresas Registradas", total_empresas)
    
    with col2:
        total_contactos = pd.read_sql("SELECT COUNT(*) as total FROM contactos", con).iloc[0]["total"]
        st.metric("Contactos", total_contactos)
    
    with col3:
        total_prospectos = pd.read_sql("SELECT COUNT(*) as total FROM prospectos WHERE estado='Activo'", con).iloc[0]["total"]
        st.metric("Prospectos Activos", total_prospectos)
    
    st.divider()
    
    # Últimos prospectos generados
    st.subheader("📈 Últimos Prospectos Generados")
    pros_recientes = pd.read_sql("""
        SELECT p.id_prospecto, e.nombre AS empresa, c.nombre AS contacto,
               p.estado, p.origen, p.fecha_creacion
        FROM prospectos p
        JOIN empresas e ON e.id_empresa = p.id_empresa
        JOIN contactos c ON c.id_contacto = p.id_contacto
        ORDER BY p.fecha_creacion DESC
        LIMIT 5
    """, con)
    
    if len(pros_recientes) > 0:
        st.dataframe(pros_recientes, use_container_width=True)
    else:
        st.info("No hay prospectos registrados aún.")
    
    st.divider()
    
    # Historial forense reciente
    st.subheader("🪶 Últimos Eventos del Sistema (Trazabilidad)")
    logs = pd.read_sql("""
        SELECT entidad, id_entidad, accion, valor_nuevo, usuario, 
               timestamp, substr(hash_evento,1,16) AS hash_corto
        FROM historial_general
        ORDER BY id_evento DESC
        LIMIT 10
    """, con)
    
    if len(logs) > 0:
        st.dataframe(logs, use_container_width=True)
    else:
        st.info("No hay eventos registrados.")
    
    con.close()

# ---------------------------------------------------------------
# TAB 2: Empresas
# ---------------------------------------------------------------
with tab2:
    st.header("🏢 Gestión de Empresas")
    
    col_form, col_list = st.columns([1, 1])
    
    with col_form:
        st.subheader("Alta de Empresa")
        
        with st.form("alta_empresa"):
            nombre = st.text_input("Nombre de empresa *", placeholder="Ej: ACME Corporation")
            rfc = st.text_input("RFC", placeholder="Ej: ACM123456ABC")
            sector = st.text_input("Sector", placeholder="Ej: Tecnología, Manufactura")
            telefono = st.text_input("Teléfono", placeholder="Ej: +52 55 1234 5678")
            correo = st.text_input("Correo", placeholder="Ej: contacto@empresa.com")
            submitted_emp = st.form_submit_button("✅ Registrar empresa", use_container_width=True)
        
        if submitted_emp:
            if not nombre:
                st.error("❌ El nombre de la empresa es obligatorio")
            else:
                con = conectar()
                cur = con.cursor()
                cur.execute("""
                    INSERT INTO empresas (nombre, rfc, sector, telefono, correo)
                    VALUES (?, ?, ?, ?, ?)
                """, (nombre, rfc or None, sector or None, telefono or None, correo or None))
                con.commit()
                id_emp = cur.lastrowid
                h = registrar_evento(con, "empresa", id_emp, "CREAR", f"Empresa: {nombre}")
                con.close()
                st.success(f"✅ Empresa '{nombre}' registrada correctamente")
                st.caption(f"🔐 Hash forense: {h[:16]}...")
                st.rerun()
    
    with col_list:
        st.subheader("Empresas Registradas")
        
        con = conectar()
        empresas = pd.read_sql("""
            SELECT e.id_empresa, e.nombre, e.rfc, e.sector, 
                   COUNT(c.id_contacto) as total_contactos
            FROM empresas e
            LEFT JOIN contactos c ON c.id_empresa = e.id_empresa
            GROUP BY e.id_empresa
            ORDER BY e.fecha_alta DESC
        """, con)
        con.close()
        
        if len(empresas) > 0:
            st.dataframe(
                empresas,
                use_container_width=True,
                column_config={
                    "id_empresa": "ID",
                    "nombre": "Empresa",
                    "rfc": "RFC",
                    "sector": "Sector",
                    "total_contactos": st.column_config.NumberColumn("Contactos", format="%d")
                }
            )
        else:
            st.info("No hay empresas registradas. Crea la primera usando el formulario.")

# ---------------------------------------------------------------
# TAB 3: Contactos
# ---------------------------------------------------------------
with tab3:
    st.header("👤 Gestión de Contactos")
    
    con = conectar()
    empresas = pd.read_sql("SELECT id_empresa, nombre FROM empresas ORDER BY nombre", con)
    con.close()
    
    if len(empresas) == 0:
        st.warning("⚠️ Primero debes registrar al menos una empresa en la pestaña 'Empresas'.")
    else:
        col_form, col_list = st.columns([1, 1])
        
        with col_form:
            st.subheader("Alta de Contacto")
            
            with st.form("alta_contacto"):
                empresa_sel = st.selectbox("Empresa *", empresas["nombre"].tolist())
                id_empresa = int(empresas.loc[empresas["nombre"] == empresa_sel, "id_empresa"].iloc[0])
                nombre_c = st.text_input("Nombre completo *", placeholder="Ej: Juan Pérez García")
                correo_c = st.text_input("Correo *", placeholder="Ej: juan.perez@empresa.com")
                telefono_c = st.text_input("Teléfono", placeholder="Ej: +52 55 9876 5432")
                puesto_c = st.text_input("Puesto", placeholder="Ej: Director de Compras")
                submitted_con = st.form_submit_button("✅ Registrar contacto", use_container_width=True)
            
            if submitted_con:
                if not nombre_c or not correo_c:
                    st.error("❌ Nombre y correo son obligatorios")
                else:
                    con = conectar()
                    cur = con.cursor()
                    cur.execute("""
                        INSERT INTO contactos (id_empresa, nombre, correo, telefono, puesto)
                        VALUES (?, ?, ?, ?, ?)
                    """, (id_empresa, nombre_c, correo_c, telefono_c or None, puesto_c or None))
                    con.commit()
                    id_con = cur.lastrowid
                    h = registrar_evento(con, "contacto", id_con, "CREAR", f"Contacto: {nombre_c} en {empresa_sel}")
                    con.close()
                    st.success(f"✅ Contacto '{nombre_c}' registrado correctamente")
                    st.caption(f"🔐 Hash forense: {h[:16]}...")
                    st.rerun()
        
        with col_list:
            st.subheader("Contactos Registrados")
            
            con = conectar()
            contactos = pd.read_sql("""
                SELECT c.id_contacto, e.nombre as empresa, c.nombre, 
                       c.correo, c.puesto, c.telefono
                FROM contactos c
                JOIN empresas e ON e.id_empresa = c.id_empresa
                ORDER BY c.fecha_alta DESC
            """, con)
            con.close()
            
            if len(contactos) > 0:
                st.dataframe(contactos, use_container_width=True)
            else:
                st.info("No hay contactos registrados. Crea el primero usando el formulario.")

# ---------------------------------------------------------------
# TAB 4: Prospectos (REGLA R1)
# ---------------------------------------------------------------
with tab4:
    st.header("📈 Generación de Prospectos")
    
    st.info("🔒 **REGLA R1:** Solo se pueden generar prospectos desde empresas que tengan al menos un contacto registrado.")
    
    con = conectar()
    empresas_disp = pd.read_sql("""
        SELECT e.id_empresa, e.nombre AS empresa, COUNT(c.id_contacto) as total_contactos
        FROM empresas e
        INNER JOIN contactos c ON c.id_empresa = e.id_empresa
        GROUP BY e.id_empresa
        HAVING COUNT(c.id_contacto) > 0
        ORDER BY e.nombre
    """, con)
    con.close()
    
    if len(empresas_disp) == 0:
        st.warning("⚠️ No hay empresas con contactos válidos. Primero registra empresas y sus contactos.")
    else:
        col_form, col_list = st.columns([1, 1])
        
        with col_form:
            st.subheader("Generar Prospecto")
            
            with st.form("alta_prospecto"):
                emp_sel = st.selectbox(
                    "Empresa *", 
                    empresas_disp["empresa"].tolist(),
                    help="Solo se muestran empresas con contactos registrados (REGLA R1)"
                )
                id_empresa = int(empresas_disp.loc[empresas_disp["empresa"] == emp_sel, "id_empresa"].iloc[0])
                
                # Cargar contactos de la empresa seleccionada
                con = conectar()
                contactos_disp = pd.read_sql("""
                    SELECT id_contacto, nombre, puesto FROM contactos WHERE id_empresa = ?
                """, con, params=(id_empresa,))
                con.close()
                
                if len(contactos_disp) > 0:
                    # Mostrar info del contacto con nombre y puesto
                    contactos_display = contactos_disp.apply(
                        lambda x: f"{x['nombre']} ({x['puesto']})" if x['puesto'] else x['nombre'], 
                        axis=1
                    ).tolist()
                    
                    cont_sel_idx = st.selectbox("Contacto principal *", range(len(contactos_display)), 
                                                format_func=lambda i: contactos_display[i])
                    id_contacto = int(contactos_disp.iloc[cont_sel_idx]["id_contacto"])
                    
                    origen = st.text_input("Origen del prospecto", 
                                          placeholder="Ej: Campaña Google Ads, Referencia, Evento",
                                          help="¿Cómo llegó este prospecto?")
                    
                    submitted_pros = st.form_submit_button("✅ Generar prospecto", use_container_width=True)
                    
                    if submitted_pros:
                        con = conectar()
                        cur = con.cursor()
                        cur.execute("""
                            INSERT INTO prospectos (id_empresa, id_contacto, origen, estado)
                            VALUES (?, ?, ?, 'Activo')
                        """, (id_empresa, id_contacto, origen or "Sin especificar"))
                        con.commit()
                        id_pros = cur.lastrowid
                        h = registrar_evento(con, "prospecto", id_pros, "CREAR", 
                                           f"Prospecto: {emp_sel} (origen: {origen or 'N/A'})")
                        con.close()
                        st.success(f"✅ Prospecto generado correctamente (ID: {id_pros})")
                        st.caption(f"🔐 Hash forense: {h[:16]}...")
                        st.rerun()
                else:
                    st.error("❌ Error: La empresa seleccionada no tiene contactos (violación de REGLA R1)")
        
        with col_list:
            st.subheader("Prospectos Activos")
            
            con = conectar()
            prospectos = pd.read_sql("""
                SELECT p.id_prospecto, e.nombre AS empresa, c.nombre AS contacto,
                       c.puesto, p.origen, p.estado, p.fecha_creacion
                FROM prospectos p
                JOIN empresas e ON e.id_empresa = p.id_empresa
                JOIN contactos c ON c.id_contacto = p.id_contacto
                WHERE p.estado = 'Activo'
                ORDER BY p.fecha_creacion DESC
            """, con)
            con.close()
            
            if len(prospectos) > 0:
                st.dataframe(
                    prospectos,
                    use_container_width=True,
                    column_config={
                        "id_prospecto": "ID",
                        "empresa": "Empresa",
                        "contacto": "Contacto",
                        "puesto": "Puesto",
                        "origen": "Origen",
                        "estado": "Estado",
                        "fecha_creacion": st.column_config.DatetimeColumn("Fecha Creación", format="DD/MM/YYYY HH:mm")
                    }
                )
            else:
                st.info("No hay prospectos activos. Genera el primero usando el formulario.")
