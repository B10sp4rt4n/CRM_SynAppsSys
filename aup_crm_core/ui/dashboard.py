import streamlit as st
import pandas as pd
from core.database import get_connection

def show():
    st.subheader("📊 Panel General")
    conn = get_connection()
    agentes = pd.read_sql_query("SELECT * FROM aup_agentes", conn)
    eventos = pd.read_sql_query("SELECT * FROM aup_eventos", conn)

    st.metric("Total de Agentes", len(agentes))
    st.metric("Eventos Registrados", len(eventos))

    if not eventos.empty:
        st.dataframe(eventos)
    else:
        st.info("No hay eventos registrados aún.")
