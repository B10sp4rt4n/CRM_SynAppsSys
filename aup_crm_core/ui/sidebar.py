import streamlit as st
from pathlib import Path

def show_sidebar():
    logo_path = Path(__file__).resolve().parent.parent / "assets" / "logo_synappssys.png"
    if logo_path.exists():
        st.sidebar.image(str(logo_path), width=160)
    st.sidebar.title("Navegación")
    return st.sidebar.radio(
        "Selecciona una sección",
        ["Dashboard", "Clientes", "Oportunidades", "Productos", "Facturación"]
    )
