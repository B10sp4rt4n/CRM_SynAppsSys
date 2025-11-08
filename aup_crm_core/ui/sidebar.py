import streamlit as st

def show_sidebar():
    st.sidebar.image("assets/logo_synappssys.png", width=160)
    st.sidebar.title("Navegación")
    return st.sidebar.radio(
        "Selecciona una sección",
        ["Dashboard", "Clientes", "Oportunidades", "Productos", "Facturación"]
    )
