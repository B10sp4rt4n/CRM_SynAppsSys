import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
from core.database import init_db
from core.config_global import mostrar_estado
from modules import clientes, oportunidades, productos, facturacion, usuarios, prospectos, dashboard_oportunidades
from modules.auth import esta_autenticado, cerrar_sesion, obtener_usuario_actual
from ui import sidebar, dashboard, login

st.set_page_config(page_title="AUP CRM", layout="wide")

def main():
    init_db()
    
    # Verificar si existe al menos un usuario en el sistema
    from core.database import get_connection
    from modules.auth import hash_password
    
    conn = get_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM aup_agentes WHERE tipo='usuario'")
        resultado = cur.fetchone()
        total_usuarios = resultado['total'] if resultado else 0
        conn.close()
        
        # Si no hay usuarios, mostrar modo setup
        if total_usuarios == 0:
            st.title("🚀 Configuración Inicial - CRM AUP")
            st.info("👋 Bienvenido! No hay usuarios registrados. Crea el primer administrador para comenzar.")
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                with st.form("setup_admin"):
                    st.subheader("👤 Crear Administrador Inicial")
                    nombre = st.text_input("Nombre completo", value="Administrador")
                    correo = st.text_input("Correo electrónico", value="admin@synappssys.com")
                    password = st.text_input("Contraseña", type="password")
                    password_confirm = st.text_input("Confirmar contraseña", type="password")
                    submit = st.form_submit_button("🎯 Crear y Comenzar", use_container_width=True)
                
                if submit:
                    if password and password == password_confirm and len(password) >= 6:
                        conn = get_connection()
                        cur = conn.cursor()
                        password_hash = hash_password(password)
                        cur.execute("""
                            INSERT INTO aup_agentes (tipo, nombre, atributos, password, activo)
                            VALUES (?, ?, ?, ?, ?)
                        """, ("usuario", nombre, f"correo={correo};rol=Administrador", password_hash, 1))
                        conn.commit()
                        conn.close()
                        st.success("✅ Administrador creado! Recarga la página para iniciar sesión.")
                        st.balloons()
                    else:
                        st.error("❌ Las contraseñas no coinciden o son muy cortas (mínimo 6 caracteres)")
            return
    
    # Verificar si el usuario está autenticado
    if not esta_autenticado():
        login.show_login()
        return
    
    # Si está autenticado, mostrar la aplicación
    st.title("💼 CRM AUP - SynAppsSys")
    
    # Mostrar información del usuario en la sidebar
    usuario = obtener_usuario_actual()
    st.sidebar.success(f"👤 {usuario['nombre']}\n🎭 Rol: {usuario['rol']}")
    
    if st.sidebar.button("🚪 Cerrar Sesión"):
        cerrar_sesion()
        st.rerun()
    
    st.sidebar.divider()
    
    # Mostrar estado del sistema
    mostrar_estado()
    
    st.sidebar.divider()
    
    page = sidebar.show_sidebar()

    if page == "Dashboard":
        dashboard.show()
    elif page == "Usuarios":
        # Solo administradores pueden ver usuarios
        if usuario['rol'] == "Administrador":
            usuarios.show()
        else:
            st.warning("⚠️ No tienes permisos para acceder a esta sección.")
    elif page == "Prospectos":
        prospectos.show()
    elif page == "Clientes":
        clientes.show()
    elif page == "Oportunidades":
        oportunidades.show()
    elif page == "Dashboard Oportunidades":
        dashboard_oportunidades.show()
    elif page == "Productos":
        productos.show()
    elif page == "Facturación":
        facturacion.show()
    else:
        st.write("Seleccione una sección desde el menú.")

if __name__ == "__main__":
    main()
