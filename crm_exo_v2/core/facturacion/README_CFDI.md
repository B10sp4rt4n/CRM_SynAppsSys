# 💼 Módulo de Facturación CFDI 4.0

## 📋 Descripción

Módulo de facturación electrónica integrado con **TimbrarCFDI33.mx** para CRM-EXO v2.

Permite registrar emisores, gestionar certificados CSD y preparar el sistema para timbrado de facturas CFDI 4.0.

## 🏗️ Arquitectura

```
crm_exo_v2/
├── core/
│   └── facturacion/
│       ├── cfdi_emisor.py        # Lógica de registro y configuración
│       ├── factura.py            # Gestión de facturas (existente)
│       └── orden_compra.py       # Gestión de OC (existente)
└── ui/
    └── ui_cfdi_emisor.py         # Interfaz Streamlit
```

## 🗄️ Esquema de Base de Datos

### Tabla: `config_cfdi_emisor`
Almacena la configuración del emisor CFDI.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | INTEGER | PK autoincremental |
| `rfc_emisor` | TEXT | RFC del emisor (UNIQUE) |
| `razon_social` | TEXT | Razón social del emisor |
| `regimen_fiscal` | TEXT | Clave de régimen fiscal (ej: 601) |
| `token_api` | TEXT | Token de autenticación TimbrarCFDI33 |
| `modo` | TEXT | 'pruebas' o 'produccion' |
| `fecha_registro` | TEXT | Fecha de creación ISO 8601 |
| `fecha_actualizacion` | TEXT | Última actualización |
| `activo` | INTEGER | 1=activo, 0=inactivo |

### Tabla: `config_cfdi_certificados`
Almacena los certificados CSD del emisor.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | INTEGER | PK autoincremental |
| `id_emisor` | INTEGER | FK a config_cfdi_emisor |
| `cer_base64` | TEXT | Archivo .cer codificado en base64 |
| `key_base64` | TEXT | Archivo .key codificado en base64 |
| `numero_certificado` | TEXT | Número del certificado SAT |
| `fecha_inicio_vigencia` | TEXT | Inicio de vigencia |
| `fecha_fin_vigencia` | TEXT | Fin de vigencia |
| `fecha_carga` | TEXT | Fecha de carga |
| `activo` | INTEGER | 1=activo, 0=inactivo |

## 🚀 Uso

### 1. Importar en tu aplicación principal

```python
# En app_crm_exo_v2.py
from crm_exo_v2.ui.ui_cfdi_emisor import ui_registro_emisor, widget_estado_cfdi
```

### 2. Agregar a tu menú de navegación

```python
if menu_seleccionado == "Configuración CFDI":
    ui_registro_emisor()
```

### 3. Usar widget de estado (opcional)

```python
# En dashboard o página principal
widget_estado_cfdi()
```

## 📦 Dependencias

```bash
pip install requests>=2.31.0
```

Ya incluido en `requirements.txt` del proyecto.

## 🔐 Configuración Inicial

### Paso 1: Obtener Token de TimbrarCFDI33

1. Regístrate en https://timbracfdi33.mx
2. Obtén tu token de API desde el panel
3. **Modo Pruebas**: Token de ambiente de pruebas
4. **Modo Producción**: Token de ambiente productivo

### Paso 2: Obtener Certificados CSD

1. Descarga tus certificados desde el portal del SAT
2. Necesitarás:
   - Archivo `.cer` (certificado público)
   - Archivo `.key` (llave privada)
   - Contraseña del archivo `.key`

### Paso 3: Registrar Emisor

1. Accede a la interfaz de configuración CFDI
2. Completa el formulario:
   - **RFC**: Tu RFC de 12 o 13 caracteres
   - **Razón Social**: Nombre o razón social
   - **Régimen Fiscal**: Clave del catálogo SAT (ej: 601, 612)
   - **Token API**: Token de TimbrarCFDI33
   - **Modo**: pruebas o produccion
   - **Archivos CSD**: .cer y .key
   - **Contraseña**: Contraseña del .key

3. Haz clic en **"Registrar Emisor en PAC"**

## 🔄 Sistema de Auto-Rehidratación

Las tablas de configuración CFDI se crean automáticamente mediante el sistema de migraciones de `app_crm_exo_v2.py`.

En cada arranque, el sistema:
1. Verifica si las tablas existen
2. Las crea si no existen
3. No afecta datos existentes

## 📡 API de TimbrarCFDI33

### Endpoints utilizados

**Pruebas:**
```
https://pruebas.timbracfdi33.mx:1444/api/v2/Timbrado/RegistraEmisor
```

**Producción:**
```
https://api.timbracfdi33.mx:1444/api/v2/Timbrado/RegistraEmisor
```

### Códigos de respuesta

| Código | Significado |
|--------|-------------|
| 200 | Emisor registrado correctamente |
| 401 | Token inválido o caducado |
| 400 | Datos incorrectos o certificado inválido |
| 500 | Error del servidor PAC |

## 🧪 Testing

### Modo Pruebas

En modo pruebas puedes:
- Registrar emisores de prueba
- Usar certificados CSD de prueba del SAT
- Timbrar facturas sin consumir timbres reales

### Validación de Configuración

```python
from crm_exo_v2.core.facturacion.cfdi_emisor import validar_configuracion_cfdi

valido, mensaje = validar_configuracion_cfdi()
if valido:
    print("✅ Configuración CFDI completa")
else:
    print(f"❌ {mensaje}")
```

## 📊 Eventos en Historial

Todos los eventos de configuración CFDI se registran en `historial_general`:

- **Registro exitoso en PAC**
- **Error 401 - Token inválido**
- **Error general**
- **Actualización de configuración**

## 🔒 Seguridad

### Datos Sensibles

- **Certificados**: Almacenados en base64 en SQLite
- **Token API**: Almacenado en texto plano (considera encriptar en producción)
- **Contraseña CSD**: NO se almacena, solo se usa para registro

### Recomendaciones

1. **Respalda tu base de datos** regularmente
2. **Restringe acceso** a la BD en producción
3. **Rota tokens** periódicamente
4. **Usa HTTPS** en producción
5. **Considera vault** para secrets en producción empresarial

## 🛠️ Troubleshooting

### Error 401: Token inválido

**Causas:**
- Token caducado
- Token de pruebas en modo producción (o viceversa)
- Permisos insuficientes

**Solución:**
- Genera un nuevo token en el panel de TimbrarCFDI33
- Verifica que el modo coincida con el tipo de token

### Error: Contraseña incorrecta del CSD

**Causas:**
- Contraseña incorrecta
- Archivos .cer y .key no coinciden
- Certificado corrupto

**Solución:**
- Verifica la contraseña del archivo .key
- Descarga nuevamente los certificados del SAT

### No se muestran los certificados

**Causas:**
- Error al cargar archivos
- Formato de archivo incorrecto

**Solución:**
- Asegúrate de cargar archivos .cer y .key válidos
- Verifica que no estén dañados

## 📚 Próximas Funcionalidades

- [ ] Timbrado de facturas CFDI 4.0
- [ ] Cancelación de facturas
- [ ] Generación de XML
- [ ] Envío por correo electrónico
- [ ] Generación de PDF
- [ ] Consulta de saldos de timbres
- [ ] Reportes de facturación
- [ ] Integración con addendas
- [ ] Facturación recurrente
- [ ] Multi-emisor

## 👨‍💻 Autor

**SynAppsSys / Salvador Ruiz Esparza**

## 📄 Licencia

Propiedad de SynAppsSys - CRM-EXO v2
