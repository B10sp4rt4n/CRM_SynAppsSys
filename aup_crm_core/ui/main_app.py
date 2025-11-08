import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
from core.database import init_db
from core.config_global import mostrar_estado
from modules import clientes, oportunidades, productos, facturacion, usuarios
from modules.auth import esta_autenticado, cerrar_sesion, obtener_usuario_actual
from ui import sidebar, dashboard, login

st.set_page_config(page_title="AUP CRM", layout="wide")

def main():
    init_db()
    
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
    elif page == "Clientes":
        clientes.show()
    elif page == "Oportunidades":
        oportunidades.show()
    elif page == "Productos":
        productos.show()
    elif page == "Facturación":
        facturacion.show()
    else:
        st.write("Seleccione una sección desde el menú.")

if __name__ == "__main__":
    main()
