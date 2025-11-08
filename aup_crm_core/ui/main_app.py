import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
from core.database import init_db
from modules import clientes, oportunidades, productos, facturacion
from ui import sidebar, dashboard

st.set_page_config(page_title="AUP CRM", layout="wide")

def main():
    st.title("💼 CRM AUP - SynAppsSys")
    init_db()
    page = sidebar.show_sidebar()

    if page == "Dashboard":
        dashboard.show()
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
