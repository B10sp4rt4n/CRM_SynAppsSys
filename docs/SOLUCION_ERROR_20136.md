# 🔧 Solución al Error 20136: "Error al validar llave privada"

## ❓ ¿Qué significa este error?

El **error 20136** del PAC TimbrarCFDI33 indica que hubo un problema al intentar validar el archivo de llave privada (`.key`) que subiste. Este error significa que el PAC no pudo desencriptar o validar correctamente tu certificado.

## 🎯 Causas más comunes

### 1. � Modo Pruebas con Certificado Real (CAUSA FRECUENTE)
Estás usando un **CSD real del SAT** pero configuraste **modo "pruebas"** en el PAC.

**El problema:**
- Tu certificado es válido (el SAT lo confirmó) ✅
- Pero el ambiente de pruebas del PAC puede rechazar certificados reales
- El PAC de pruebas espera certificados de prueba específicos

**Solución:**
Si tu CSD es **real y lo validó el SAT**, debes usar:
- **Modo:** Producción (NO pruebas)
- **Token:** Token de producción de TimbrarCFDI33
- **Certificado:** Tu CSD real del SAT

**Cómo cambiar:**
1. Ve a ⚙️ Configuración CFDI
2. Cambia el "Modo de Operación" a **produccion**
3. Verifica que estés usando tu **token de producción**
4. Registra el emisor nuevamente

📖 **Ver más:** [MODO_PRUEBAS_VS_PRODUCCION.md](./MODO_PRUEBAS_VS_PRODUCCION.md)

### 2. 🔑 Contraseña incorrecta
Otra causa muy común del error 20136 es una **contraseña incorrecta** del archivo `.key`.

**Solución:**
- Verifica la contraseña que usaste al generar el CSD
- No confundas la contraseña del CSD con la de tu FIEL/e.firma
- Copia y pega la contraseña para evitar errores de tipeo
- Verifica que no haya espacios al inicio o final

### 2. 🚫 Archivos que no coinciden
Los archivos `.cer` y `.key` que subiste **no pertenecen al mismo certificado**.

**Solución:**
- Verifica que ambos archivos sean de la misma descarga del SAT
- No mezcles archivos de diferentes generaciones de certificados
- Descarga nuevamente ambos archivos desde el portal del SAT

### 3. ⚠️ Es una FIEL/e.firma, no un CSD
Subiste un certificado **FIEL o e.firma** en lugar de un **CSD**.

**Diferencias clave:**
- **FIEL/e.firma**: Para trámites fiscales y firmar declaraciones
- **CSD (Certificado de Sello Digital)**: Específicamente para timbrar CFDI

**Solución:**
1. Ingresa al [Portal del SAT](https://www.sat.gob.mx)
2. Ve a: Trámites > Certificado de Sello Digital (CSD)
3. Genera tu CSD y descarga los archivos `.cer` y `.key`
4. Usa esos archivos en lugar de tu FIEL

### 4. 📁 Archivo corrupto o incompleto
El archivo `.key` está dañado, incompleto o tiene un formato inválido.

**Solución:**
- Descarga nuevamente los archivos desde el SAT
- No edites los archivos con editores de texto
- Verifica que la descarga se completó correctamente

### 5. 📅 Certificado expirado
Tu CSD ya expiró y no puede usarse para timbrar.

**Solución:**
- Los CSD tienen vigencia de 4 años
- Genera un nuevo CSD en el portal del SAT
- No se pueden renovar, debes generar uno nuevo

## 🔍 Cómo diagnosticar el problema

La aplicación CRM-EXO v2 ahora incluye una **herramienta de diagnóstico** que valida tus certificados ANTES de enviarlos al PAC.

### Usar la herramienta de diagnóstico:

1. **Navega a:** ⚙️ Configuración CFDI
2. **Selecciona la pestaña:** 🔍 Diagnóstico de Certificados
3. **Carga tus archivos:**
   - Archivo `.cer`
   - Archivo `.key`
   - Contraseña del `.key`
4. **Haz clic en:** 🔍 Diagnosticar Certificados

La herramienta te dirá **exactamente** cuál es el problema:
- ✅ Si la contraseña es correcta
- ✅ Si los archivos coinciden
- ✅ Si es un CSD o una FIEL
- ✅ Si el certificado está vigente
- ✅ Si el formato es válido

## 🛠️ Pasos para resolver el error 20136

### Paso 1: Ejecuta el diagnóstico
Usa la herramienta de diagnóstico incluida en la app para identificar el problema específico.

### Paso 2: Según el resultado

#### Si dice "Contraseña incorrecta":
1. Verifica la contraseña en tus registros
2. Intenta con diferentes variaciones si no estás seguro
3. Si no la recuerdas, genera un nuevo CSD

#### Si dice "Es una FIEL/e.firma":
1. Descarga tu CSD desde el SAT
2. NO uses tu FIEL para facturación
3. Carga los archivos correctos

#### Si dice "Los archivos NO coinciden":
1. Descarga nuevamente ambos archivos (.cer y .key) del mismo certificado
2. Verifica que no hayas mezclado archivos de diferentes descargas

#### Si dice "Certificado expirado":
1. Genera un nuevo CSD en el portal del SAT
2. Descarga los nuevos archivos
3. Carga los nuevos certificados

#### Si dice "Archivo corrupto":
1. Descarga los archivos nuevamente
2. No los edites con editores de texto
3. Verifica la integridad de la descarga

### Paso 3: Vuelve a intentar
Una vez solucionado el problema identificado:
1. Ve a la pestaña "📝 Registrar Emisor"
2. Completa el formulario con los archivos correctos
3. El sistema validará localmente antes de enviar al PAC

## 📚 Recursos adicionales

### Cómo obtener tu CSD del SAT:

1. **Ingresa al portal del SAT:**
   - URL: https://www.sat.gob.mx
   - Usa tu RFC y contraseña o FIEL

2. **Navega a Certificados:**
   - Trámites > Certificado de Sello Digital (CSD)
   - O busca "CSD" en el portal

3. **Genera el certificado:**
   - Sigue el asistente del SAT
   - Establece una contraseña segura
   - **¡GUARDA BIEN ESTA CONTRASEÑA!**

4. **Descarga los archivos:**
   - Archivo `.cer` (certificado público)
   - Archivo `.key` (llave privada)
   - Conserva ambos en un lugar seguro

5. **Registra en el CRM:**
   - Usa estos archivos en la configuración CFDI
   - Ingresa la contraseña que estableciste
   - Completa el registro en el PAC

### Diferencias CSD vs FIEL:

| Característica | CSD | FIEL/e.firma |
|----------------|-----|--------------|
| Uso principal | Timbrar CFDI (facturas) | Trámites fiscales |
| Dónde se obtiene | Portal SAT > CSD | Portal SAT > Certificado Digital |
| Para qué sirve | Facturación electrónica | Firmas electrónicas, declaraciones |
| Se puede usar para facturar | ✅ SÍ | ❌ NO |
| Vigencia | 4 años | 4 años |

## ✅ Checklist final

Antes de registrar tu emisor en el PAC, verifica:

- [ ] Tengo los archivos `.cer` y `.key` del **CSD** (no FIEL)
- [ ] Los archivos `.cer` y `.key` son del **mismo certificado**
- [ ] Tengo la **contraseña correcta** del archivo `.key`
- [ ] Los archivos **no están corruptos** ni editados
- [ ] El certificado **está vigente** (no expirado)
- [ ] Ejecuté el **diagnóstico** y pasó todas las validaciones
- [ ] Tengo mi **token de API** de TimbrarCFDI33
- [ ] El token corresponde al **modo correcto** (pruebas/producción)

## 🆘 ¿Aún tienes problemas?

Si después de seguir esta guía aún tienes el error 20136:

1. **Verifica con el SAT:**
   - Confirma que tu CSD esté activo
   - Verifica que no haya sido revocado

2. **Contacta al PAC:**
   - Soporte de TimbrarCFDI33
   - Proporciona el código de error 20136

3. **Genera un nuevo CSD:**
   - Como último recurso, genera un certificado nuevo
   - Descarga los archivos frescos
   - Intenta nuevamente

---

**Última actualización:** Marzo 2026  
**Versión CRM:** EXO v2  
**PAC:** TimbrarCFDI33
