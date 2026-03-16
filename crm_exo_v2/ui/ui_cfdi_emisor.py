# -*- coding: utf-8 -*-
"""
UI: Configuración de Emisor CFDI 4.0
Interfaz Streamlit para registro de emisor y certificados CSD
Integración con timbracfdi33.mx
"""

import streamlit as st
import sys
from pathlib import Path

# Agregar ruta del core al path
CORE_PATH = Path(__file__).parent.parent / "core"
sys.path.insert(0, str(CORE_PATH))

from facturacion.cfdi_emisor import (
    RegistroEmisorCFDI,
    TimbradoCFDI,
    obtener_configuracion_emisor,
    validar_configuracion_cfdi
)


# ==========================================================
# 🎨 INTERFAZ: REGISTRO DE EMISOR
# ==========================================================
def ui_registro_emisor():
    """Interfaz para registrar emisor CFDI en el PAC"""
    
    st.title("💼 Configuración de Facturación CFDI")
    st.caption("Registra tu emisor y certificados CSD para timbrar facturas electrónicas")
    
    # Verificar si ya existe configuración
    config_actual = obtener_configuracion_emisor()
    
    if config_actual:
        st.info(f"✅ **Emisor configurado:** {config_actual['rfc']} ({config_actual['modo']})")
        
        with st.expander("📋 Ver configuración actual"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**RFC:**", config_actual['rfc'])
                st.write("**Modo:**", config_actual['modo'].upper())
            with col2:
                if config_actual.get('razon_social'):
                    st.write("**Razón Social:**", config_actual['razon_social'])
                if config_actual.get('regimen_fiscal'):
                    st.write("**Régimen Fiscal:**", config_actual['regimen_fiscal'])
            
            if 'certificados' in config_actual:
                st.success("🔐 Certificados CSD cargados")
                if config_actual['certificados'].get('numero_certificado'):
                    st.write("**No. Certificado:**", config_actual['certificados']['numero_certificado'])
        
        st.divider()
        st.subheader("🔄 Actualizar Configuración")
    else:
        st.warning("⚠️ No hay emisor configurado. Completa el formulario para comenzar.")
    
    # Formulario de registro
    with st.form("form_registro_emisor", clear_on_submit=False):
        st.subheader("📝 Datos del Emisor")
        
        col1, col2 = st.columns(2)
        
        with col1:
            rfc = st.text_input(
                "RFC del Emisor *",
                value=config_actual['rfc'] if config_actual else "",
                max_chars=13,
                help="RFC de la persona física o moral emisora"
            ).upper()
            
            razon_social = st.text_input(
                "Razón Social",
                value=config_actual.get('razon_social', '') if config_actual else "",
                help="Nombre o razón social del emisor"
            )
        
        with col2:
            regimen_fiscal = st.text_input(
                "Régimen Fiscal",
                value=config_actual.get('regimen_fiscal', '') if config_actual else "",
                max_chars=3,
                help="Clave del régimen fiscal (ej: 601, 612, 626)"
            )
            
            modo = st.selectbox(
                "Modo de Operación *",
                options=["pruebas", "produccion"],
                index=0 if not config_actual else (0 if config_actual['modo'] == 'pruebas' else 1),
                help="Usar 'pruebas' para testing, 'produccion' para facturas reales"
            )
        
        st.divider()
        st.subheader("🔐 Certificados y Autenticación")
        
        col1, col2 = st.columns(2)
        
        with col1:
            cer_file = st.file_uploader(
                "Archivo CSD (.cer) *",
                type=["cer"],
                help="Certificado digital del SAT"
            )
            
            key_file = st.file_uploader(
                "Archivo Key (.key) *",
                type=["key"],
                help="Llave privada del certificado"
            )
        
        with col2:
            contrasena = st.text_input(
                "Contraseña del CSD *",
                type="password",
                help="Contraseña para desencriptar el archivo .key"
            )
            
            token = st.text_input(
                "Token API TimbrarCFDI33 *",
                type="password",
                value=config_actual.get('token', '') if config_actual else "",
                help="Token de autenticación de tu cuenta en timbracfdi33.mx"
            )
        
        st.caption("**Campos obligatorios marcados con ***")
        
        # Botones de acción
        col_submit, col_help = st.columns([3, 1])
        
        with col_submit:
            submitted = st.form_submit_button(
                "🚀 Registrar Emisor en PAC",
                width="stretch",
                type="primary"
            )
        
        with col_help:
            if st.form_submit_button("❓ Ayuda"):
                st.info("""
                **¿Dónde obtengo estos datos?**
                
                - **RFC y CSD:** Portal del SAT
                - **Token API:** Panel de timbracfdi33.mx
                - **Régimen Fiscal:** En tu Constancia de Situación Fiscal
                """)
        
        # Procesar formulario
        if submitted:
            # Validaciones
            if not rfc or len(rfc) not in [12, 13]:
                st.error("⚠️ RFC inválido. Debe tener 12 o 13 caracteres.")
                return
            
            if not token:
                st.error("⚠️ El token de API es obligatorio.")
                return
            
            if not cer_file or not key_file:
                st.error("⚠️ Debes cargar ambos archivos del certificado (.cer y .key).")
                return
            
            if not contrasena:
                st.error("⚠️ La contraseña del CSD es obligatoria.")
                return
            
            # Leer archivos
            cer_bytes = cer_file.read()
            key_bytes = key_file.read()
            
            # Resetear punteros de archivos
            cer_file.seek(0)
            key_file.seek(0)
            
            # Intentar registrar
            with st.spinner("📡 Conectando con el PAC TimbrarCFDI33..."):
                registro = RegistroEmisorCFDI()
                exito, mensaje, datos = registro.registrar_emisor(
                    rfc=rfc,
                    cer_bytes=cer_bytes,
                    key_bytes=key_bytes,
                    contrasena=contrasena,
                    token=token,
                    modo=modo,
                    razon_social=razon_social if razon_social else None,
                    regimen_fiscal=regimen_fiscal if regimen_fiscal else None
                )
            
            # Mostrar resultado
            if exito:
                st.success(f"✅ {mensaje}")
                st.balloons()
                
                if datos:
                    with st.expander("📄 Respuesta del PAC"):
                        st.json(datos)
                
                st.info("🔄 Recarga la página para ver la configuración actualizada")
                
                # Registrar en session state para auto-rerun
                if 'emisor_registrado' not in st.session_state:
                    st.session_state.emisor_registrado = True
                    st.rerun()
            else:
                st.error(f"❌ {mensaje}")
                
                if datos:
                    with st.expander("🔍 Detalles del error"):
                        st.json(datos)
                
                # Ayuda contextual según error
                if "401" in mensaje:
                    st.warning("""
                    **Posibles causas del error 401:**
                    - Token inválido o caducado
                    - Token de pruebas usado en modo producción (o viceversa)
                    - Permisos insuficientes en tu cuenta
                    
                    👉 Verifica tu token en el panel de timbracfdi33.mx
                    """)
                elif "contraseña" in mensaje.lower():
                    st.warning("""
                    **Error de contraseña CSD:**
                    - Verifica que sea la contraseña correcta del archivo .key
                    - Asegúrate de que los archivos .cer y .key correspondan
                    """)
                elif "fiel" in mensaje.lower() or datos.get("Codigo") == 20133:
                    st.warning("""
                    **El certificado cargado es una FIEL/e.firma, no un CSD.**

                    Para timbrar CFDI necesitas el Certificado de Sello Digital del SAT:
                    - Archivo .cer del CSD
                    - Archivo .key del CSD
                    - Contraseña de esa llave privada

                    La e.firma/FIEL no sirve para timbrado.
                    """)

    st.divider()
    st.subheader("🧪 Prueba manual de timbrado")
    st.caption("Úsala para validar conexión con TimbrarCFDI33 mientras el generador XML nativo del CRM aún no está conectado al flujo de facturación.")

    valido_cfdi, mensaje_cfdi = validar_configuracion_cfdi()
    if not valido_cfdi:
        st.warning(f"⚠️ {mensaje_cfdi}. Primero configura el emisor y sus certificados para habilitar esta prueba.")
        return

    config_timbrado = obtener_configuracion_emisor()
    if config_timbrado:
        st.info(f"Timbrando con RFC {config_timbrado['rfc']} en modo {config_timbrado['modo']}")

    with st.form("form_prueba_timbrado", clear_on_submit=False):
        col_xml_1, col_xml_2 = st.columns([2, 1])

        with col_xml_1:
            xml_texto = st.text_area(
                "XML CFDI",
                height=240,
                placeholder="Pega aquí el XML CFDI sin timbrar..."
            )

        with col_xml_2:
            xml_file = st.file_uploader(
                "O carga un XML",
                type=["xml"],
                help="Si cargas archivo, se usará sobre el texto pegado"
            )
            id_comprobante = st.text_input(
                "IdComprobante",
                help="Campo opcional para rastreo del lado del PAC o soporte"
            )

        enviar_timbrado = st.form_submit_button(
            "📮 Timbrar XML en PAC",
            width="stretch",
            type="primary"
        )

        if enviar_timbrado:
            xml_payload = xml_texto.strip()
            if xml_file is not None:
                xml_payload = xml_file.read().decode("utf-8", errors="ignore").strip()

            if not xml_payload:
                st.error("⚠️ Debes pegar o cargar un XML antes de timbrar.")
                return

            if "<cfdi:Comprobante" not in xml_payload and "<Comprobante" not in xml_payload:
                st.warning("El contenido no parece un CFDI válido. Revisa que el XML sea el comprobante sin timbrar.")

            with st.spinner("📡 Enviando XML al PAC para timbrado..."):
                cliente_timbrado = TimbradoCFDI()
                exito, mensaje, datos = cliente_timbrado.timbrar_cfdi(
                    xml_comprobante=xml_payload,
                    id_comprobante=id_comprobante.strip() or None
                )

            if exito:
                st.success(f"✅ {mensaje}")
                if datos.get("UUID"):
                    st.write("UUID timbrado:", datos["UUID"])
                if datos.get("CadenaOriginalTimbre"):
                    with st.expander("🔗 Cadena original del timbre"):
                        st.code(datos["CadenaOriginalTimbre"])
                if datos.get("Xml"):
                    with st.expander("📄 XML timbrado"):
                        st.code(datos["Xml"], language="xml")
                    st.download_button(
                        "⬇️ Descargar XML timbrado",
                        data=datos["Xml"],
                        file_name=f"cfdi_timbrado_{datos.get('UUID', 'salida')}.xml",
                        mime="application/xml"
                    )
                if datos.get("CodigoQr"):
                    st.caption("El PAC devolvió CodigoQr; queda disponible en la respuesta para una futura representación impresa.")
                with st.expander("🧾 Respuesta completa del PAC"):
                    st.json(datos)
            else:
                st.error(f"❌ {mensaje}")
                if datos:
                    with st.expander("🔍 Respuesta de error del PAC"):
                        st.json(datos)


# ==========================================================
# 🔍 WIDGET: ESTADO DE CONFIGURACIÓN
# ==========================================================
def widget_estado_cfdi():
    """Widget compacto que muestra el estado de la configuración CFDI"""
    
    valido, mensaje = validar_configuracion_cfdi()
    
    if valido:
        config = obtener_configuracion_emisor()
        st.success(f"✅ CFDI configurado: **{config['rfc']}** ({config['modo']})")
    else:
        st.warning(f"⚠️ {mensaje}")
        if st.button("⚙️ Configurar ahora", key="btn_config_cfdi_widget"):
            st.session_state.menu_seleccionado = "⚙️ Configuración CFDI"
            st.rerun()


# ==========================================================
# 🚀 EJECUCIÓN DIRECTA (PARA TESTING)
# ==========================================================
if __name__ == "__main__":
    st.set_page_config(
        page_title="Configuración CFDI - CRM EXO",
        page_icon="💼",
        layout="wide"
    )
    
    ui_registro_emisor()
