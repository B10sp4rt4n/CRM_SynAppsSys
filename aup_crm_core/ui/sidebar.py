import streamlit as st
from pathlib import Path

def show_sidebar():
    # Intentar cargar el logo, pero continuar si falla
    try:
        logo_path = Path(__file__).resolve().parent.parent / "assets" / "logo_synappssys.png"
        if logo_path.exists() and logo_path.is_file():
            st.sidebar.image(str(logo_path), width=160)
    except Exception as e:
        # Si falla, simplemente mostramos el título sin logo
        st.sidebar.markdown("### 💼 SynAppsSys")
    
    st.sidebar.title("Navegación")
    return st.sidebar.radio(
        "Selecciona una sección",
        ["Dashboard", "Clientes", "Oportunidades", "Productos", "Facturación"]
    )
