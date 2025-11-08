import streamlit as st
from core.event_logger import registrar_evento

def show():
    st.subheader("👥 Gestión de Clientes")
    st.info("Módulo Clientes — próximamente funcional")
    if st.button("Registrar cliente de prueba"):
        registrar_evento(1, "Alta cliente", "Cliente de prueba agregado.")
