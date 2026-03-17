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
from facturacion.validador_certificados import ValidadorCertificados


# ==========================================================
# 🎨 INTERFAZ: REGISTRO DE EMISOR
# ==========================================================
def ui_registro_emisor():
    """Interfaz para registrar emisor CFDI en el PAC"""
    
    st.title("💼 Configuración de Facturación CFDI 4.0")
    st.caption("Configura tu emisor y certificados digitales para emitir facturas electrónicas válidas ante el SAT")
    
    # Verificar si ya existe configuración
    config_actual = obtener_configuracion_emisor()
    
    if config_actual:
        st.success(f"✅ **Emisor activo:** {config_actual['rfc']} — Modo: {config_actual['modo'].upper()}")
        
        with st.expander("📋 Ver información completa del emisor"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**RFC:**", config_actual['rfc'])
                st.write("**Modo de operación:**", config_actual['modo'].upper())
            with col2:
                if config_actual.get('razon_social'):
                    st.write("**Razón Social:**", config_actual['razon_social'])
                if config_actual.get('regimen_fiscal'):
                    st.write("**Régimen Fiscal:**", config_actual['regimen_fiscal'])
            
            if 'certificados' in config_actual:
                st.success("🔐 Certificados CSD registrados correctamente")
                if config_actual['certificados'].get('numero_certificado'):
                    st.write("**Número de certificado:**", config_actual['certificados']['numero_certificado'])
        
        st.divider()
        st.subheader("🔄 Actualizar o Modificar Configuración")
        st.caption("Usa el formulario abajo para cambiar de emisor, actualizar certificados o modificar el modo de operación")
    else:
        st.warning("⚠️ **Primer uso:** No tienes ningún emisor configurado. Completa el formulario para habilitar la facturación.")
    
    # Formulario de registro
    with st.form("form_registro_emisor", clear_on_submit=False):
        st.subheader("📝 Datos del Emisor")
        
        col1, col2 = st.columns(2)
        
        with col1:
            rfc = st.text_input(
                "RFC del Emisor *",
                value=config_actual['rfc'] if config_actual else "",
                max_chars=13,
                placeholder="XAXX010101000",
                help="📋 RFC de 12 (personas morales) o 13 caracteres (personas físicas). Este RFC aparecerá como emisor en todas tus facturas."
            ).upper()
            
            razon_social = st.text_input(
                "Razón Social o Nombre Comercial",
                value=config_actual.get('razon_social', '') if config_actual else "",
                placeholder="Mi Empresa S.A. de C.V.",
                help="💼 Nombre legal de tu empresa o tu nombre completo (personas físicas). Opcional pero recomendado."
            )
        
        with col2:
            regimen_fiscal = st.text_input(
                "Régimen Fiscal (Clave SAT)",
                value=config_actual.get('regimen_fiscal', '') if config_actual else "",
                max_chars=3,
                placeholder="601",
                help="🏛️ Clave de 3 dígitos según tu régimen fiscal. Ejemplos: 601 (General de Ley), 612 (Personas Físicas con Actividades Empresariales), 626 (Régimen Simplificado de Confianza)."
            )
            
            modo = st.selectbox(
                "Modo de Operación *",
                options=["pruebas", "produccion"],
                index=0 if not config_actual else (0 if config_actual['modo'] == 'pruebas' else 1),
                help="⚙️ PRUEBAS: Para desarrollo y testing (timbres sin validez fiscal). PRODUCCIÓN: Para emitir facturas reales válidas ante el SAT."
            )
        
        # Advertencia sobre modo pruebas vs producción
        if modo == "pruebas":
            st.info("""
            **🧪 Modo PRUEBAS activado**
            
            ✅ **Úsalo para:** Desarrollo y testing sin costo de timbres  
            ⚠️ **Importante:** Los timbres generados NO son válidos fiscalmente ante el SAT  
            📌 **Nota técnica:** Algunos PAC requieren certificados de prueba específicos
            
            💡 **¿Tienes un CSD real del SAT?** Usa modo **PRODUCCIÓN** en lugar de pruebas para evitar el error 20136.
            """)
        else:
            st.success("""
            **✅ Modo PRODUCCIÓN activado**
            
            ✅ **Para:** Emitir facturas reales con validez fiscal ante el SAT  
            💰 **Importante:** Los timbres tienen costo y se descontarán de tu saldo en el PAC  
            🔐 **Requisito:** Debes usar tu CSD real descargado desde el portal del SAT
            """)
        
        st.divider()
        st.subheader("🔐 Certificados y Autenticación")
        
        col1, col2 = st.columns(2)
        
        with col1:
            cer_file = st.file_uploader(
                "Certificado Digital (.cer) *",
                type=["cer"],
                help="🔐 Archivo .cer de tu Certificado de Sello Digital (CSD), descargado del portal del SAT. NO es tu e.firma ni FIEL."
            )
            
            key_file = st.file_uploader(
                "Llave Privada (.key) *",
                type=["key"],
                help="🔑 Archivo .key que acompaña a tu certificado .cer. Ambos deben ser del mismo CSD descargado del SAT."
            )
        
        with col2:
            contrasena = st.text_input(
                "Contraseña del CSD *",
                type="password",
                placeholder="●●●●●●●●",
                help="🔒 Contraseña que asignaste al generar tu CSD en el portal del SAT. Es diferente a la contraseña de tu FIEL."
            )
            
            token = st.text_input(
                "Token API del PAC *",
                type="password",
                value=config_actual.get('token', '') if config_actual else "",
                placeholder="Tu token de TimbrarCFDI33",
                help="🎫 Token de autenticación proporcionado por timbracfdi33.mx. Lo encuentras en el panel de tu cuenta del PAC."
            )
        
        st.caption("**Los campos marcados con * son obligatorios**")
        
        # Botones de acción
        col_submit, col_help = st.columns([3, 1])
        
        with col_submit:
            submitted = st.form_submit_button(
                "🚀 Registrar Emisor y Certificados",
                use_container_width=True,
                type="primary"
            )
        
        with col_help:
            if st.form_submit_button("❓ Guía rápida", use_container_width=True):
                st.info("""
                **📚 ¿Dónde obtengo cada dato?**
                
                🏛️ **RFC y CSD (.cer/.key):**  
                Portal del SAT → Trámites → Certificado de Sello Digital
                
                🎫 **Token del PAC:**  
                Panel de control en timbracfdi33.mx → Configuración API
                
                📋 **Régimen Fiscal:**  
                Tu Constancia de Situación Fiscal del SAT
                
                ℹ️ **Recuerda:** El CSD es diferente a tu FIEL/e.firma
                """)
        
        # Procesar formulario
        if submitted:
            # Validaciones
            if not rfc or len(rfc) not in [12, 13]:
                st.error("⚠️ **RFC inválido:** Debe tener 12 caracteres (morales) o 13 (físicas). Ej: XAXX010101000")
                return
            
            if not token:
                st.error("⚠️ **Falta el token del PAC:** Ingésalo para autenticarte con el servicio de timbrado.")
                return
            
            if not cer_file or not key_file:
                st.error("⚠️ **Certificados incompletos:** Debes cargar AMBOS archivos (.cer Y .key) del mismo CSD.")
                return
            
            if not contrasena:
                st.error("⚠️ **Falta la contraseña:** Necesitas la contraseña del archivo .key para validar tu certificado.")
                return
            
            # Leer archivos
            cer_bytes = cer_file.read()
            key_bytes = key_file.read()
            
            # Resetear punteros de archivos
            cer_file.seek(0)
            key_file.seek(0)
            
            # 🔍 PASO 1: Validar certificados localmente ANTES de enviar al PAC
            with st.spinner("🔍 Paso 1/2: Validando certificados localmente... Esto asegura que estén correctos antes de enviarlos al PAC."):
                validador = ValidadorCertificados()
                cert_valido, cert_mensaje, cert_detalles = validador.validar_certificado_completo(
                    cer_bytes, key_bytes, contrasena
                )
            
            # Mostrar resultado de validación local
            if not cert_valido:
                st.error(f"❌ {cert_mensaje}")
                
                if cert_detalles:
                    with st.expander("🔍 Detalles del diagnóstico"):
                        for clave, valor in cert_detalles.items():
                            st.write(f"**{clave}:** {valor}")
                
                # Mostrar ayuda contextual
                if "FIEL" in cert_mensaje or "e.firma" in cert_mensaje.lower():
                    st.warning("""
                    **📌 Diferencia entre FIEL/e.firma y CSD:**
                    
                    - **FIEL/e.firma**: Para trámites fiscales, firmar declaraciones
                    - **CSD (Certificado de Sello Digital)**: Para timbrar CFDI (facturas electrónicas)
                    
                    **Cómo obtener tu CSD:**
                    1. Entra al portal del SAT con tu RFC y contraseña
                    2. Ve a "Trámites" > "Certificado de Sello Digital"
                    3. Genera y descarga tu CSD (.cer y .key)
                    4. Guarda bien la contraseña que asignes
                    """)
                elif "contraseña" in cert_mensaje.lower():
                    st.warning("""
                    **🔑 Problema con la contraseña:**
                    
                    - Verifica que sea la contraseña correcta del archivo .key
                    - No uses espacios al inicio o final
                    - Distingue entre mayúsculas y minúsculas
                    - Asegúrate de usar la contraseña del CSD, no de tu FIEL
                    """)
                elif "NO coinciden" in cert_mensaje:
                    st.warning("""
                    **⚠️ Los archivos no pertenecen al mismo certificado:**
                    
                    - Verifica que los archivos .cer y .key sean de la misma descarga
                    - Asegúrate de no mezclar archivos de diferentes certificados
                    - Descarga nuevamente ambos archivos desde el SAT si es necesario
                    """)
                elif "EXPIRÓ" in cert_mensaje:
                    st.warning("""
                    **📅 Certificado expirado:**
                    
                    - El CSD tiene una vigencia limitada (generalmente 4 años)
                    - Debes generar un nuevo CSD en el portal del SAT
                    - No puedes renovar un CSD, debes generar uno nuevo
                    """)
                
                st.stop()  # No continuar con el registro en el PAC
            
            # Mostrar éxito de validación local
            st.success(f"✅ **Paso 1 completado:** {cert_mensaje}")
            
            if 'advertencia' in cert_detalles:
                st.warning(f"⚠️ **Advertencia:** {cert_detalles['advertencia']}")
            
            if cert_detalles:
                with st.expander("📊 Ver información del certificado validado"):
                    for clave, valor in cert_detalles.items():
                        if clave != 'advertencia':
                            st.write(f"**{clave}:** {valor}")
            
            # 🚀 PASO 2: Enviar al PAC (solo si la validación local fue exitosa)
            with st.spinner("📡 Paso 2/2: Registrando emisor en el PAC TimbrarCFDI33... Conectando al servicio de timbrado."):
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
                st.success(f"✅ **¡Registro exitoso!** {mensaje}")
                st.balloons()
                
                if datos:
                    with st.expander("📝 Ver respuesta completa del PAC"):
                        st.json(datos)
                
                st.info("🔄 **Próximo paso:** Recarga la página o navega a otra sección para ver la configuración actualizada.")
                
                # Registrar en session state para auto-rerun
                if 'emisor_registrado' not in st.session_state:
                    st.session_state.emisor_registrado = True
                    st.rerun()
            else:
                st.error(f"❌ **Error en el registro:** {mensaje}")
                
                if datos:
                    with st.expander("🔍 Ver detalles técnicos del error"):
                        st.json(datos)
                
                # Ayuda contextual según error
                if "401" in mensaje or (datos and "401" in str(datos.get("Codigo", ""))):
                    st.warning("""
                    **🔑 Error de autenticación (401)**
                    
                    **Posibles causas:**
                    ❌ Token inválido, expirado o incorrecto  
                    ❌ Token de PRUEBAS usado en modo PRODUCCIÓN (o viceversa)  
                    ❌ Permisos insuficientes en tu cuenta del PAC  
                    ❌ Servicio del PAC temporalmente no disponible
                    
                    **🛠️ Solución:**
                    1. ✅ Verifica tu token en el panel de **timbracfdi33.mx**
                    2. ✅ Asegúrate de usar el token correcto según el modo (pruebas/producción)
                    3. ✅ Copia y pega el token directamente desde el PAC
                    """)
                elif datos.get("Codigo") == 20136 or "20136" in str(datos):
                    st.error("""
                    ### ⚠️ Error 20136: Problema con la Llave Privada
                    
                    Este error del PAC indica que no pudo validar correctamente tu certificado.
                    """)
                    
                    # Detectar si están en modo pruebas
                    if modo == "pruebas":
                        st.error("""
                        **🎯 CAUSA MÁS PROBABLE: Certificado Real en Modo PRUEBAS**
                        
                        Estás usando modo "**pruebas**" pero tu certificado es un CSD **real del SAT**.
                        
                        **🛠️ SOLUCIÓN RECOMENDADA:**
                        
                        1. ✅ Cambia el "Modo de Operación" a **PRODUCCIÓN**
                        2. ✅ Asegúrate de usar tu **token de producción** del PAC
                        3. ✅ Vuelve a registrar el emisor con estos cambios
                        
                        **¿Por qué ocurre esto?**  
                        El ambiente de PRUEBAS del PAC puede rechazar certificados reales de producción. 
                        Si tu CSD es válido (confirmado por el SAT), debes usar modo **producción**.
                        
                        📚 **Documentación:** Consulta `docs/MODO_PRUEBAS_VS_PRODUCCION.md` para más detalles.
                        """)
                    else:
                        st.warning("""
                        **🔍 Otras causas posibles del error 20136:**
                        
                        1. ❌ **Contraseña incorrecta** del archivo .key
                        2. ❌ **Archivos .cer y .key no coinciden** (no son del mismo certificado)
                        3. ❌ **El certificado es una FIEL**, no un CSD para timbrado
                        4. ❌ **Archivo .key corrupto** o dañado
                        5. ❌ **Problema de compatibilidad** con el PAC
                        """)
                    
                    st.info("""
                    **🛠️ Pasos para diagnosticar el problema:**
                    
                    1. ✅ Ve a la sección **"🔍 Diagnóstico de Certificados"**
                    2. ✅ Carga tus archivos para una validación local completa
                    3. ✅ Sigue las recomendaciones específicas que te proporcione
                    4. ✅ Una vez validados localmente, vuelve a intentar el registro
                    """)
                elif "contraseña" in mensaje.lower():
                    st.warning("""
                    **🔑 Error relacionado con la contraseña**
                    
                    **Verificaciones necesarias:**
                    ✅ Asegúrate de que sea la contraseña correcta del .key  
                    ✅ Confirma que los archivos .cer y .key correspondan entre sí  
                    ✅ Evita espacios al inicio o final de la contraseña  
                    ✅ Distingue entre mayúsculas y minúsculas
                    
                    💡 **Tip:** Usa la herramienta de **Diagnóstico de Certificados** para validar localmente.
                    """)
                elif "fiel" in mensaje.lower() or datos.get("Codigo") == 20133:
                    st.warning("""
                    **🚫 Certificado incorrecto: FIEL/e.firma detectada**

                    El certificado cargado es una **FIEL** o **e.firma**, no un CSD.

                    **Para timbrar CFDI necesitas:**
                    ✅ Certificado de Sello Digital (CSD) del SAT  
                    ✅ Archivo .cer del CSD  
                    ✅ Archivo .key del CSD  
                    ✅ Contraseña de esa llave privada

                    ⚠️ **Recuerda:** La e.firma/FIEL NO sirve para timbrado de facturas.
                    
                    👉 **Obtén tu CSD en:** Portal SAT → Trámites → Certificado de Sello Digital
                    """)

    st.divider()
    st.subheader("🧪 Prueba de Timbrado Manual")
    st.caption("""
    Herramienta de validación rápida para probar tu conexión con el PAC. Úsala mientras desarrollas 
el generador XML nativo del CRM. Pega o carga un XML CFDI sin timbrar para validar que tu configuración funciona.
    """)

    valido_cfdi, mensaje_cfdi = validar_configuracion_cfdi()
    if not valido_cfdi:
        st.warning(f"⚠️ {mensaje_cfdi}")
        st.info("👆 **Primero configura el emisor** en la sección de arriba para habilitar esta prueba.")
        return

    config_timbrado = obtener_configuracion_emisor()
    if config_timbrado:
        st.success(f"⚙️ Configuración activa: RFC **{config_timbrado['rfc']}** en modo **{config_timbrado['modo'].upper()}**")

    with st.form("form_prueba_timbrado", clear_on_submit=False):
        col_xml_1, col_xml_2 = st.columns([2, 1])

        with col_xml_1:
            xml_texto = st.text_area(
                "XML CFDI sin timbrar",
                height=240,
                placeholder="Pega aquí el contenido XML de tu comprobante fiscal sin timbrar...\n\nDebe iniciar con <?xml version=\"1.0\" encoding=\"UTF-8\"?>",
                help="📝 XML CFDI 4.0 completo antes de timbrar. Puedes generarlo con tu sistema o usar un XML de prueba."
            )

        with col_xml_2:
            xml_file = st.file_uploader(
                "O sube un archivo XML",
                type=["xml"],
                help="📄 Si cargas un archivo, este tendrá prioridad sobre el texto pegado"
            )
            id_comprobante = st.text_input(
                "ID de Rastreo (opcional)",
                placeholder="FACT-2026-001",
                help="🔖 Identificador único para rastrear este comprobante en el PAC. Útil para soporte técnico."
            )

        enviar_timbrado = st.form_submit_button(
            "📡 Enviar a Timbrar en el PAC",
            use_container_width=True,
            type="primary"
        )

        if enviar_timbrado:
            xml_payload = xml_texto.strip()
            if xml_file is not None:
                xml_payload = xml_file.read().decode("utf-8", errors="ignore").strip()

            if not xml_payload:
                st.error("⚠️ **No hay XML para timbrar:** Pega el contenido XML o carga un archivo antes de continuar.")
                return

            if "<cfdi:Comprobante" not in xml_payload and "<Comprobante" not in xml_payload:
                st.warning("⚠️ **Posible formato incorrecto:** El contenido no parece un CFDI válido. Verifica que el XML sea un comprobante fiscal.")

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
# 🔍 HERRAMIENTA: DIAGNÓSTICO DE CERTIFICADOS
# ==========================================================
def ui_diagnostico_certificados():
    """Herramienta independiente para diagnosticar certificados CSD"""
    
    st.title("🔍 Diagnóstico de Certificados CSD")
    st.caption("🩺 Valida tus archivos .cer y .key LOCALMENTE antes de enviarlos al PAC")
    
    st.info("""
    **¿Para qué sirve esta herramienta?**
    
    Esta validación **local** verifica tus certificados ANTES de registrarlos en el PAC, 
    ayudándote a identificar y resolver problemas comunes:
    
    ✅ **Contraseña correcta** del archivo .key  
    ✅ **Correspondencia** entre archivos .cer y .key  
    ✅ **Tipo de certificado** (CSD vs FIEL/e.firma)  
    ✅ **Vigencia** del certificado (no expirado)  
    ✅ **Integridad** y formato de los archivos
    
    💡 **Usa esta herramienta si recibes el error 20136** del PAC para diagnosticar la causa exacta.
    """)
    
    with st.form("form_diagnostico_cert", clear_on_submit=False):
        st.subheader("📁 Carga tus Archivos de Certificado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            diag_cer = st.file_uploader(
                "Certificado Público (.cer)",
                type=["cer"],
                key="diag_cer",
                help="🔓 Archivo de certificado público con extensión .cer del SAT"
            )
        
        with col2:
            diag_key = st.file_uploader(
                "Llave Privada (.key)",
                type=["key"],
                key="diag_key",
                help="🔑 Archivo de llave privada con extensión .key que acompaña al .cer"
            )
        
        diag_password = st.text_input(
            "Contraseña de la Llave Privada",
            type="password",
            key="diag_password",
            placeholder="●●●●●●●●",
            help="🔐 Contraseña que asignaste al generar el certificado en el portal del SAT"
        )
        
        diagnosticar = st.form_submit_button(
            "🔬 Ejecutar Diagnóstico Completo",
            type="primary",
            use_container_width=True
        )
        
        if diagnosticar:
            if not diag_cer or not diag_key:
                st.error("⚠️ **Archivos incompletos:** Debes cargar AMBOS archivos (.cer Y .key) para realizar el diagnóstico.")
            elif not diag_password:
                st.error("⚠️ **Falta la contraseña:** Ingresa la contraseña del archivo .key para continuar con la validación.")
            else:
                # Leer archivos
                cer_bytes = diag_cer.read()
                key_bytes = diag_key.read()
                
                # Resetear punteros
                diag_cer.seek(0)
                diag_key.seek(0)
                
                # Ejecutar diagnóstico
                with st.spinner("� Analizando certificados en detalle...  Esto puede tomar unos segundos..."):
                    validador = ValidadorCertificados()
                    valido, mensaje, detalles = validador.validar_certificado_completo(
                        cer_bytes, key_bytes, diag_password
                    )
                
                # Mostrar resultado
                st.divider()
                
                if valido:
                    st.success(f"### ✅ {mensaje}")
                    st.balloons()
                    
                    st.success("🎉 **¡Excelente! Tu certificado está listo para usarse.**")
                    st.info("➡️ **Siguiente paso:** Ve a la sección de *Configuración de Facturación CFDI* para registrar estos certificados en el PAC.")
                    
                    if 'advertencia' in detalles:
                        st.warning(f"⚠️ **Advertencia:** {detalles['advertencia']}")
                else:
                    st.error(f"### ❌ {mensaje}")
                    
                    # Mostrar ayuda contextual según el error
                    if "FIEL" in mensaje or "e.firma" in mensaje.lower():
                        st.warning("""
                        ### 🚫 Problema Identificado: FIEL/e.firma (no es CSD)
                        
                        **¿Qué significa esto?**  
                        Cargaste un certificado tipo **FIEL** o **e.firma**, pero para facturación electrónica necesitas un **CSD** (Certificado de Sello Digital).
                        
                        **🔑 Diferencias clave:**
                        | Certificado | Uso Principal |
                        |-------------|---------------|
                        | **FIEL/e.firma** | Trámites fiscales, declaraciones, firma de documentos |
                        | **CSD** | **Timbrado de CFDI** (facturas electrónicas) |
                        
                        **🛠️ Cómo obtener tu CSD:**
                        1. Inicia sesión en el [Portal del SAT](https://www.sat.gob.mx)
                        2. Menú: **Trámites** → **Certificado de Sello Digital (CSD)**
                        3. Sigue el proceso de generación
                        4. Descarga los archivos **.cer** y **.key** generados
                        5. **Guarda bien la contraseña** que asignes
                        """)
                    
                    elif "contraseña" in mensaje.lower() or "password" in mensaje.lower():
                        st.warning("""
                        ### 🔑 Problema Identificado: Contraseña Incorrecta
                        
                        **Causas comunes:**
                        ❌ La contraseña no es la correcta  
                        ❌ Espacios extra al inicio o final  
                        ❌ Distingues malúsculas/minúsculas  
                        ❌ Confundes la contraseña del CSD con la de tu FIEL  
                        ❌ El archivo .key está dañado o corrupto
                        
                        **🛠️ Soluciones:**
                        1. ✅ Verifica la contraseña que asignaste al generar el CSD
                        2. ✅ Copia y pega la contraseña para evitar errores de tipeo
                        3. ✅ Asegúrate de no incluir espacios antes/después
                        4. ✅ Si no recuerdas la contraseña, **genera un nuevo CSD** en el SAT
                        
                        ⚠️ **Nota:** No es posible recuperar la contraseña de un CSD existente.
                        """)
                    
                    elif "NO coinciden" in mensaje:
                        st.warning("""
                        ### ⚠️ Problema Identificado: Archivos No Coinciden
                        
                        **¿Qué significa esto?**  
                        El archivo **.cer** y el archivo **.key** que cargaste **no pertenecen al mismo certificado**.
                        
                        **Causas comunes:**
                        ❌ Mezclaste archivos de diferentes descargas  
                        ❌ Un archivo es de un CSD viejo y el otro de uno nuevo  
                        ❌ Confundiste archivos del CSD con los de la FIEL
                        
                        **🛠️ Solución:**
                        1. ✅ Verifica que AMBOS archivos sean de la **misma descarga**
                        2. ✅ Revisa las fechas de generación de los archivos
                        3. ✅ Si tienes duda, **descarga nuevamente** el CSD desde el SAT
                        4. ✅ Usa los archivos .cer y .key de esa misma descarga
                        """)
                    
                    elif "EXPIRÓ" in mensaje:
                        st.warning("""
                        ### 📅 Problema Identificado: Certificado Expirado
                        
                        **¿Qué significa esto?**  
                        Tu certificado CSD ya **venció** y no puede usarse para timbrar facturas.
                        
                        **📌 Información importante:**
                        - Los CSD tienen una **vigencia de 4 años**
                        - No se pueden *renovar*, debes generar uno **nuevo**
                        - El SAT no permite usar certificados vencidos
                        
                        **🛠️ Qué hacer:**
                        1. ✅ Genera un **nuevo CSD** en el portal del SAT
                        2. ✅ Ve a: Trámites → Certificado de Sello Digital
                        3. ✅ Descarga los nuevos archivos .cer y .key
                        4. ✅ Usa esos archivos en lugar de los vencidos
                        """)
                    
                    elif "muy pequeño" in mensaje or "vacío" in mensaje:
                        st.warning("""
                        ### 📁 Problema Identificado: Archivos Dañados o Incompletos
                        
                        **¿Qué significa esto?**  
                        Los archivos que cargaste están **vacíos, incompletos o corruptos**.
                        
                        **Causas comunes:**
                        ❌ La descarga desde el SAT no se completó correctamente  
                        ❌ Los archivos se dañaron al transferirlos  
                        ❌ Se editaron con un editor de texto  
                        ❌ El tamaño del archivo es 0 bytes
                        
                        **🛠️ Solución:**
                        1. ✅ **Descarga nuevamente** los archivos desde el portal del SAT
                        2. ✅ Verifica que los archivos tengan **tamaño mayor a 0 bytes**
                        3. ✅ **NO edites** los archivos con bloc de notas u otros editores
                        4. ✅ Usa los archivos **tal como los descargó el SAT**
                        """)
                
                # Mostrar detalles técnicos
                if detalles:
                    with st.expander("� Ver Información Técnica Completa del Certificado"):
                        st.caption("Detalles extraidos del certificado digital:")
                        for clave, valor in detalles.items():
                            if clave != 'advertencia':
                                st.write(f"**{clave}:** `{valor}`")


# ==========================================================
# 🔍 WIDGET: ESTADO DE CONFIGURACIÓN
# ==========================================================
def widget_estado_cfdi():
    """Widget compacto que muestra el estado de la configuración CFDI"""
    
    valido, mensaje = validar_configuracion_cfdi()
    
    if valido:
        config = obtener_configuracion_emisor()
        st.success(f"✅ **Facturación activa:** RFC {config['rfc']} | Modo: {config['modo'].upper()}")
        if config.get('razon_social'):
            st.caption(f"🏛️ {config['razon_social']}")
    else:
        st.warning(f"⚠️ {mensaje}")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.caption("👉 Configure su emisor para habilitar la facturación electrónica")
        with col2:
            if st.button("⚙️ Configurar", key="btn_config_cfdi_widget", use_container_width=True):
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
