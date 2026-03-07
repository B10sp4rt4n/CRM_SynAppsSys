import streamlit as st
from modules.auth import iniciar_sesion

def show_login():
    """Pantalla de inicio de sesión"""
    
    # Centrar el login con columnas
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("## 🔐 Inicio de Sesión")
        st.markdown("### CRM AUP - SynAppsSys")
        st.divider()
        
        with st.form("login_form"):
            correo = st.text_input("📧 Correo electrónico", placeholder="usuario@ejemplo.com")
            password = st.text_input("🔑 Contraseña", type="password", placeholder="••••••••")
            submit = st.form_submit_button("Iniciar Sesión", width="stretch")
        
        if submit:
            if correo and password:
                if iniciar_sesion(correo, password):
                    st.success("✅ ¡Inicio de sesión exitoso!")
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas o usuario inactivo.")
            else:
                st.warning("⚠️ Por favor completa todos los campos.")
        
        st.divider()
        st.info("💡 **Nota**: Si no tienes cuenta, contacta al administrador del sistema.")
