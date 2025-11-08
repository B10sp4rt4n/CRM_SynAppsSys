# ==========================================================
# 🔐 CONFIGURACIÓN GLOBAL DEL SISTEMA AUP CRM
# ==========================================================

import os

# === MODO SEGURO DE ROLLBACK AUTH ===
# Si es True: desactiva registro de eventos con usuario,
# ignora verificaciones de rol y usa autenticación simplificada.
AUTH_ROLLBACK_MODE = True

# === CONFIGURACIÓN BASE DE ENTORNO ===
APP_NAME = "SynAppsSys CRM AUP"
APP_VERSION = "1.3.ROLLBACK"
APP_ENV = os.getenv("AUP_ENV", "development")

# === OPCIONAL ===
# Define aquí endpoints futuros para Recordia/HotVault o variables globales
RECORDIA_ENABLED = False
RECORDIA_ENDPOINT = ""
NOM151_PROVIDER = ""

# === LOG DE CONFIGURACIÓN ===
def mostrar_estado():
    """Muestra el estado actual de configuración global"""
    import streamlit as st
    st.sidebar.markdown("### 🧭 Estado del Sistema")
    st.sidebar.info(
        f"**Modo autenticación:** {'🔓 Rollback' if AUTH_ROLLBACK_MODE else '🔐 Estructurado'}\n"
        f"**Versión:** {APP_VERSION}\n"
        f"**Entorno:** {APP_ENV}"
    )
