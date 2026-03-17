# 🔄 Modo Pruebas vs Producción en CFDI

## 🎯 Diferencias Clave

### Modo PRUEBAS
**Cuándo usar:**
- Estás haciendo **testing** de integración
- No quieres timbres reales que afecten tu cuota
- Estás en desarrollo

**Qué necesitas:**
- Token de **PRUEBAS** de TimbrarCFDI33
- Endpoint: `https://pruebas.timbracfdi33.mx:1444`
- Certificado de **PRUEBAS** (proporcionado por el PAC o certificados especiales)

**Características:**
- ❌ Los timbres NO son válidos ante el SAT
- ✅ No consumen tu cuota de timbres
- ✅ Ideal para desarrollo y testing
- ⚠️ Puede requerir certificados especiales de prueba

### Modo PRODUCCIÓN
**Cuándo usar:**
- Vas a emitir **facturas reales**
- Los CFDI deben ser válidos ante el SAT
- Ya terminaste el testing

**Qué necesitas:**
- Token de **PRODUCCIÓN** de TimbrarCFDI33
- Endpoint: `https://api.timbracfdi33.mx:1444`
- Tu **CSD real** (descargado del SAT)

**Características:**
- ✅ Los timbres SON válidos ante el SAT
- ⚠️ Consumen tu cuota de timbres (costo por timbre)
- ✅ Para operación real
- ✅ Usa tu certificado CSD oficial

## 🚨 Error 20136 en Modo Pruebas

Si recibes el **error 20136** y estás en **modo pruebas**, probablemente:

### Causa: Certificado Real en Ambiente de Pruebas
- Estás usando tu **CSD real del SAT** ✅
- Pero en el ambiente de **pruebas** del PAC ⚠️
- El PAC de pruebas puede rechazar certificados de producción

### Solución A: Cambiar a Modo Producción
Si tu intención es **timbrar facturas reales**:

1. Cambia el modo a **"produccion"**
2. Usa tu **token de producción** de TimbrarCFDI33
3. Usa tu **CSD real** del SAT
4. Registra el emisor nuevamente

### Solución B: Obtener Certificados de Prueba
Si quieres seguir en **modo pruebas**:

1. Contacta a TimbrarCFDI33 para obtener certificados de prueba
2. O usa los certificados de prueba proporcionados por el PAC
3. Usa tu **token de pruebas**
4. Configura con los certificados de prueba

## 📋 Verificación de Configuración

### ✅ Configuración CORRECTA para Producción:
```
Modo: produccion
Token: token_de_produccion_abc123xyz
Certificado: Tu CSD real del SAT
Endpoint usado: https://api.timbracfdi33.mx:1444
Resultado: Timbres válidos ante SAT
```

### ✅ Configuración CORRECTA para Pruebas:
```
Modo: pruebas
Token: token_de_pruebas_test123
Certificado: Certificado de prueba del PAC
Endpoint usado: https://pruebas.timbracfdi33.mx:1444
Resultado: Timbres de prueba (no válidos ante SAT)
```

### ❌ Configuración INCORRECTA (causa error 20136):
```
Modo: pruebas
Token: token_de_pruebas_test123
Certificado: Tu CSD real del SAT ← PROBLEMA
Endpoint usado: https://pruebas.timbracfdi33.mx:1444
Resultado: Error 20136 - Certificado rechazado
```

## 🔧 Cómo Cambiar de Modo en el CRM

1. Ve a **⚙️ Configuración CFDI**
2. En el formulario, selecciona el modo:
   - **pruebas** → Para testing
   - **produccion** → Para operación real
3. Asegúrate de usar el **token correspondiente** al modo
4. Registra el emisor

## 💡 Recomendación

### Para tu caso (CSD validado por el SAT):

**Si ya tienes un CSD real del SAT:**
➡️ Usa **modo PRODUCCIÓN** con tu token de producción

**¿Por qué?**
- Tu certificado ya es real y válido
- El modo pruebas es solo para desarrollo/testing
- En producción tu certificado funcionará correctamente
- Los timbres serán válidos ante el SAT

### Flujo recomendado:

1. **Desarrollo/Testing:**
   - Modo: pruebas
   - Certificados: De prueba del PAC
   - Sin costo por timbre
   - Para probar integración

2. **Operación Real:**
   - Modo: produccion
   - Certificados: Tu CSD real del SAT
   - Con costo por timbre
   - Facturas válidas

## 🆘 Contacto con TimbrarCFDI33

Si necesitas certificados de prueba:
- Soporte: https://timbracfdi33.mx/soporte
- Pregunta por: "Certificados CSD para ambiente de pruebas"
- Explica que necesitas testing antes de usar producción

---

**Conclusión:** Si tu CSD es real y válido (el SAT lo confirmó), lo más probable es que debas usar **modo PRODUCCIÓN** en lugar de modo pruebas.
