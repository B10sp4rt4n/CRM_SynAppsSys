# 🚀 AUP-EXO v2 - PUNTO CERO ESTRUCTURAL

**Fecha de creación:** 2025-11-10  
**Branch:** `v2-restructure`  
**Modelo:** Resolución inversa + Forense por diseño  
**Status:** ✅ Núcleos implementados

---

## 📊 Arquitectura de 4 Núcleos

```
┌─────────────────────────────────────────────────────────────┐
│  NÚCLEO 1: IDENTIDAD                                        │
│  ✅ empresas → contactos → prospectos                       │
│  📁 core/identidad/{empresa.py, contacto.py, prospecto.py}  │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│  NÚCLEO 2: TRANSACCIÓN                                      │
│  ✅ oportunidades → cotizaciones (3 modos)                  │
│  📁 core/transaccion/{oportunidad.py, cotizacion.py}        │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│  NÚCLEO 3: FACTURACIÓN                                      │
│  ✅ ordenes_compra → facturas (CFDI + hash)                 │
│  📁 core/facturacion/{orden_compra.py, factura.py}          │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│  NÚCLEO 4: TRAZABILIDAD                                     │
│  ✅ historial_general + hash_registros (forense SHA256)     │
│  📁 core/trazabilidad/historial.py                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Base de Datos SQLite

**Archivo:** `crm_exo_v2/data/crm_exo_v2.sqlite`  
**Esquema:** `crm_exo_v2/data/schema.sql`

### Tablas creadas (9 tablas + 8 índices):

#### NÚCLEO 1: Identidad
- `empresas` (id_empresa, nombre, rfc, sector, telefono, correo)
- `contactos` (id_contacto, id_empresa FK, nombre, correo, puesto)
- `prospectos` (id_prospecto, id_empresa FK, id_contacto FK, estado)

#### NÚCLEO 2: Transacción
- `oportunidades` (id_oportunidad, id_prospecto FK, etapa, probabilidad, monto_estimado)
- `cotizaciones` (id_cotizacion, id_oportunidad FK, modo, monto_total, hash_integridad)

#### NÚCLEO 3: Facturación
- `ordenes_compra` (id_oc, id_oportunidad FK, numero_oc, monto_oc, archivo_pdf)
- `facturas` (id_factura, id_oc FK, uuid, serie, folio, archivo_xml, archivo_pdf)

#### NÚCLEO 4: Trazabilidad
- `historial_general` (id_evento, entidad, accion, valor_anterior, valor_nuevo, hash_evento)
- `hash_registros` (id_hash, tabla_origen, id_registro, hash_sha256)

---

## 🧩 Entidades Implementadas

### Patrón de diseño: **Dataclass + Repository**

Cada entidad sigue el patrón:
```python
@dataclass
class Entidad:
    # Atributos con validación
    def validar() -> tuple[bool, str]
    def to_dict() -> dict
    @classmethod from_dict(data: dict) -> Entidad

class EntidadRepository:
    def crear(entidad) -> int
    def obtener_por_id(id) -> Entidad
    def listar_todas() -> list
    # Métodos específicos según lógica de negocio
```

### Entidades Core (7 módulos):

1. **`core/identidad/empresa.py`**
   - `Empresa` dataclass
   - `EmpresaRepository` (crear, obtener_por_id, listar_todas, actualizar, desactivar)

2. **`core/identidad/contacto.py`**
   - `Contacto` dataclass con validación de email
   - `ContactoRepository` (crear, obtener_por_empresa, contar_por_empresa)

3. **`core/identidad/prospecto.py`** ⭐
   - `Prospecto` dataclass
   - **REGLA R1:** `crear_desde_empresa()` valida contactos antes de crear
   - **REGLA R3:** `convertir_a_cliente()` marca es_cliente=1 + fecha_conversion
   - `ProspectoRepository` (crear_desde_empresa, listar_clientes, convertir_a_cliente)

4. **`core/transaccion/oportunidad.py`** ⭐
   - `Oportunidad` dataclass
   - **REGLA R2:** `crear()` valida prospecto_id obligatorio
   - **REGLA R3:** `marcar_ganada_y_convertir()` actualiza probabilidad=100 + convierte prospecto
   - **REGLA R4:** `actualizar_oc()` gestiona checkbox OC + `puede_facturar()` valida
   - `OportunidadRepository` (crear, marcar_ganada_y_convertir, actualizar_oc, listar_por_prospecto)

5. **`core/transaccion/cotizacion.py`** ⭐
   - `Cotizacion` dataclass con 3 modos (mínimo|genérico|externo)
   - `generar_hash()` → SHA256 forense de integridad
   - `verificar_integridad()` → Validación de hash
   - `CotizacionRepository` (crear, obtener_por_id, listar_por_oportunidad, crear_nueva_version)

6. **`core/facturacion/orden_compra.py`** ⭐
   - `OrdenCompra` dataclass
   - **REGLA R4:** OC obligatoria antes de facturar
   - `OrdenCompraRepository` (crear, obtener_por_oportunidad, actualizar, listar_todas)

7. **`core/facturacion/factura.py`** ⭐
   - `Factura` dataclass para CFDI
   - `generar_hash_forense()` → SHA256 del UUID + monto + fecha
   - **REGLA R4:** Validación de OC antes de crear
   - `FacturaRepository` (crear, obtener_por_oc, verificar_integridad)

8. **`core/trazabilidad/historial.py`** ⭐
   - `EventoHistorial` dataclass con hash SHA256
   - `generar_hash()` → Hash forense del evento completo
   - `HistorialRepository`:
     - `registrar_evento()` → Auditoría automática
     - `obtener_historial_entidad()` → Timeline completo
     - `verificar_integridad_evento()` → Validación forense
     - `generar_cadena_custodia()` → Reporte de auditoría

---

## 🔐 Sistema Forense

### Hash SHA256 en 3 niveles:

1. **Cotizaciones:** Hash de (id_oportunidad + modo + monto + versión + fecha)
2. **Facturas:** Hash de (uuid + serie + folio + fecha + monto)
3. **Eventos:** Hash de (entidad + acción + valor_anterior + valor_nuevo + usuario + timestamp)

Todos los hashes se almacenan en:
- Tabla principal (campo `hash_integridad` o `hash_evento`)
- Tabla `hash_registros` para trazabilidad independiente

### Verificación de integridad:

```python
# Verificar cotización
repo = CotizacionRepository(db)
cotizacion = repo.obtener_por_id(1)
es_integra = cotizacion.verificar_integridad()  # True/False

# Verificar factura
repo_factura = FacturaRepository(db)
es_integra, mensaje = repo_factura.verificar_integridad(factura_id)

# Verificar evento
repo_historial = HistorialRepository(db)
es_integro, mensaje = repo_historial.verificar_integridad_evento(evento_id)

# Cadena de custodia completa
reporte = repo_historial.generar_cadena_custodia("oportunidad", 5)
```

---

## 🎯 Reglas de Negocio Implementadas

### REGLA R1: Prospecto desde Empresa con Contactos
```python
# prospecto.py → ProspectoRepository.crear_desde_empresa()
# Valida COUNT(contactos) > 0 antes de crear
# Copia automáticamente contactos de empresa a prospecto
```

### REGLA R2: Oportunidades solo desde Prospectos
```python
# oportunidad.py → OportunidadRepository.crear()
# Valida que prospecto_id exista y esté activo
# Bloquea oportunidades "huérfanas"
```

### REGLA R3: Conversión Automática a Cliente
```python
# oportunidad.py → marcar_ganada_y_convertir()
# Al ganar oportunidad (probabilidad=100%):
#   1. Actualiza etapa = "Ganada"
#   2. Convierte prospecto: es_cliente=1, fecha_conversion_cliente=hoy
```

### REGLA R4: OC Obligatoria para Facturar
```python
# orden_compra.py + factura.py
# Factura.crear() valida que id_oc exista antes de insertar
# oportunidad.puede_facturar() → etapa=="Ganada" AND oc_recibida==True
```

---

## 🛠️ Conexión a Base de Datos

**Módulo:** `core/database.py`

```python
from crm_exo_v2.core.database import get_db

db = get_db()  # Singleton pattern
conn = db.connection

# Uso con Repositories
from crm_exo_v2.core.identidad.empresa import EmpresaRepository

repo = EmpresaRepository(conn)
empresa_id = repo.crear(Empresa(nombre="ACME Corp", rfc="ACM123456ABC"))
```

Características:
- **Singleton:** Una sola conexión por aplicación
- **Row factory:** Acceso por nombre de columna (`row["nombre"]`)
- **Foreign keys:** Habilitadas automáticamente
- **Thread-safe:** Compatible con Streamlit

---

## 📐 Flujo Estructural Completo

```
🏗️ Alta Empresa + Contacto
    ↓ (REGLA R1: validar contactos > 0)
📈 Generar Prospecto
    ↓ (REGLA R2: prospecto_id obligatorio)
🎯 Crear Oportunidad
    ↓
💰 Generar Cotización (modo: mínimo|genérico|externo)
    ↓ (REGLA R3: probabilidad=100%)
👥 Marcar Ganada → Convertir a Cliente
    ↓ (REGLA R4: OC obligatoria)
🧾 Registrar Orden de Compra
    ↓
📄 Generar Factura (CFDI + hash forense)
    ↓
🪶 Trazabilidad Total (historial + hash SHA256)
```

---

## 📋 Checklist de Implementación

### ✅ E1 – Identidad estructural
- [x] Tabla `empresas` + entidad `Empresa`
- [x] Tabla `contactos` + entidad `Contacto`
- [x] Tabla `prospectos` + entidad `Prospecto`
- [x] REGLA R1: Validación de contactos

### ✅ E2 – Motor de oportunidades
- [x] Tabla `oportunidades` + entidad `Oportunidad`
- [x] REGLA R2: Validación de prospecto
- [x] REGLA R3: Conversión automática a cliente
- [x] REGLA R4: Gestión de OC

### ✅ E3 – Cotizador AUP (3 modos)
- [x] Tabla `cotizaciones` + entidad `Cotizacion`
- [x] Modo mínimo, genérico, externo
- [x] Hash forense de integridad
- [x] Versionamiento de cotizaciones

### ✅ E4 – Facturación básica (OC)
- [x] Tabla `ordenes_compra` + entidad `OrdenCompra`
- [x] Tabla `facturas` + entidad `Factura`
- [x] REGLA R4: OC obligatoria antes de facturar
- [x] Hash forense de facturas CFDI

### ✅ E5 – Bitácora estructural
- [x] Tabla `historial_general` + entidad `EventoHistorial`
- [x] Tabla `hash_registros` para trazabilidad
- [x] Generación automática de hash SHA256
- [x] Verificación de integridad forense
- [x] Generación de cadena de custodia

### ⏳ E6 – Interfaz Streamlit
- [ ] Módulo `ui/` con vistas principales
- [ ] Dashboard de oportunidades
- [ ] Gestión de empresas/contactos/prospectos
- [ ] Generación de cotizaciones
- [ ] Gestión de facturación
- [ ] Visualización de trazabilidad forense

---

## 🎯 Siguiente Paso

**ETAPA 6:** Implementar interfaz Streamlit modular

```python
# ui/app.py → Aplicación principal
# ui/views/empresas.py → Vista de empresas
# ui/views/prospectos.py → Vista de prospectos
# ui/views/oportunidades.py → Pipeline visual
# ui/views/cotizaciones.py → Cotizador (3 modos)
# ui/views/facturacion.py → OC + Facturas
# ui/views/trazabilidad.py → Auditoría forense
```

---

## 🔬 Metodología de Desarrollo

### Resolución inversa:
Cada módulo parte de su resultado estructural y se resuelve hacia atrás.

### Fallos tolerados, estructura no:
Si algo falla, el sistema retrocede de nivel, pero nunca deja estructura inválida.

### Forense por diseño:
Todo cambio genera un hash, timestamp y actor.

### Compatibilidad progresiva:
El modo mínimo siempre funciona (sin API, sin conectores).

---

## 📊 Métricas del Proyecto

- **Entidades core:** 8 módulos
- **Tablas DB:** 9 tablas
- **Índices:** 8 índices de rendimiento
- **Reglas de negocio:** 4 reglas implementadas (R1-R4)
- **Sistema forense:** 3 niveles de hash SHA256
- **Repositorios:** 8 clases Repository
- **Validadores:** 8 métodos `validar()`
- **Líneas de código:** ~2,000 líneas (core + schema)

---

**Versión:** AUP-EXO v2.0  
**Hash de referencia v1.0:** `b14510f1d6f64a7d1dda10e0413eb06b418635a7`  
**Arquitectura:** 4 núcleos independientes + trazabilidad forense total
