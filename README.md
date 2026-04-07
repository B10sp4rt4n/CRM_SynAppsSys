# CRM_SynAppsSys

**Sistema CRM con trazabilidad forense, facturación CFDI 4.0 y soporte flexible SQLite/PostgreSQL**

---

## 🎯 Características Principales

### ✨ **Arquitectura Flexible de Base de Datos**
- 🔄 **Auto-detección SQLite ↔ PostgreSQL** - Sin cambios de código
- 🏠 **SQLite** para desarrollo local y equipos pequeños (0 configuración)
- 🚀 **PostgreSQL** para producción y escalabilidad (10-1000+ usuarios)
- 📊 **Migración transparente** entre motores

### 🔐 **Trazabilidad Forense SHA-256 Única**
- Hash dual-layer en 9 tablas críticas
- Detección automática de tampering
- Compliance-ready para auditorías
- **Única en el mercado CRM**

### 🧾 **Facturación CFDI 4.0 Integrada**
- Validador local de certificados CSD
- Integración con PAC TimbrarCFDI33
- Diagnóstico automático de errores
- Gestión completa: OC → CFDI → Pagos

### 🧬 **4 Núcleos Modulares**
```
N1: IDENTIDAD    → empresas → contactos → prospectos
N2: TRANSACCIÓN  → oportunidades → cotizaciones
N3: FACTURACIÓN  → órdenes_compra → facturas → pagos
N4: TRAZABILIDAD → historial + hashes forenses
```

### 🎨 **UX Nivel Enterprise (Nivel 1 + Nivel 2 Completo)** 🆕
- 🔍 **Búsqueda avanzada** con filtros múltiples
- 📊 **Visualizaciones Plotly** interactivas (funnel, timeline)
- ⌨️ **Shortcuts de teclado** (Ctrl+K, Ctrl+N, Ctrl+S)
- 🔔 **Sistema de notificaciones** inteligente (5 tipos de alertas)
- 📦 **Operaciones masivas** (bulk delete, export, update)
- 📥 **Import/Export wizard** para migración masiva de datos
- 🌙 **Modo oscuro** con theme switcher
- 🧭 **Navegación mejorada** con breadcrumbs
- ⏳ **Loading states** y feedback visual
- **Score UX: 9.4/10** ⭐ (vs 5/10 baseline Streamlit)

### ✅ **Calidad Enterprise**
- 28/28 tests pasando (100%)
- Reglas de negocio validadas (R1-R5)
- Repository pattern profesional
- Type hints completos
- 98/100 score de calidad (+3 con DB flexibility)

---

## 📊 Configuración de Base de Datos

### SQLite (Predeterminado)
```bash
# Cero configuración - funciona inmediatamente
streamlit run app_crm_exo_v2.py
```

### PostgreSQL (Producción)
```toml
# .streamlit/secrets.toml
DATABASE_URL = "postgresql://user:password@host:5432/database"
```

### DynamiQuote (Modo externo de cotización)
```bash
export DYNAMIQUOTE_API_URL="http://127.0.0.1:8000"
python -m streamlit run app_crm_exo_v2.py --server.headless true
```

En N2 → Cotizaciones, el modo externo puede enviar líneas a DynamiQuote, recuperar el total calculado y guardar la traza de sincronización en el CRM.

**El sistema auto-detecta y adapta todo automáticamente.**

📖 **Guía completa:** [docs/MIGRACION_SQLITE_POSTGRES.md](docs/MIGRACION_SQLITE_POSTGRES.md)

---

## 📚 Documentación Clave

### Arquitectura y Base de Datos
- [DIAGRAMA_GRAFO_CRM_CFDI.md](docs/DIAGRAMA_GRAFO_CRM_CFDI.md) - Modelo de grafos canónico
- [CONFIG_POSTGRES_NEON.md](docs/CONFIG_POSTGRES_NEON.md) - Setup PostgreSQL/Neon
- [MIGRACION_SQLITE_POSTGRES.md](docs/MIGRACION_SQLITE_POSTGRES.md) - Migración entre motores
- [INTEGRACION_FRADMA_DASHBOARD3.md](docs/INTEGRACION_FRADMA_DASHBOARD3.md) - Integración BI/Analytics

### UX y Mejoras de Usuario 🆕
- [ROADMAP_UX.md](docs/ROADMAP_UX.md) - Roadmap completo UX (3 niveles)
- [UX_NIVEL1_IMPLEMENTADAS.md](docs/UX_NIVEL1_IMPLEMENTADAS.md) - Detalles técnicos Nivel 1
- [NOTIFICACIONES_SISTEMA.md](docs/NOTIFICACIONES_SISTEMA.md) - Sistema de notificaciones
- [BULK_OPERATIONS.md](docs/BULK_OPERATIONS.md) - Operaciones masivas
- [IMPORT_EXPORT_DARK_MODE.md](docs/IMPORT_EXPORT_DARK_MODE.md) - Import/Export + Modo Oscuro 🆕
- [UX_QUICKSTART.md](UX_QUICKSTART.md) - Guía rápida de uso

### Calidad y Benchmarking
- [BENCHMARKING_COMPETITIVO.md](docs/BENCHMARKING_COMPETITIVO.md) - Análisis vs mercado (7.9/10) 🏆
- [CALIFICACION_PROYECTO.md](docs/CALIFICACION_PROYECTO.md) - Métricas de calidad (98/100)
- [ESTRATEGIA_PRICING.md](docs/ESTRATEGIA_PRICING.md) - Modelo de monetización y TCO 🆕

---

## 🚀 Instalación Rápida

```bash
# 1. Clonar repositorio
git clone https://github.com/B10sp4rt4n/CRM_SynAppsSys.git
cd CRM_SynAppsSys

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar aplicación (SQLite automático)
streamlit run app_crm_exo_v2.py

# 3b. O con PostgreSQL
export DATABASE_URL="postgresql://..."
streamlit run app_crm_exo_v2.py
```

---

## 💡 Ventajas Competitivas

| Característica | CRM-EXO v2.1 | Salesforce | HubSpot | Odoo |
|----------------|---------|------------|---------|------|
| **Trazabilidad Forense SHA-256** | ✅ Única | ❌ | ❌ | ❌ |
| **Costo Anual (10 users)** | **$0** | $9K-$36K | $5.4K-$14K | $2.8K-$6K |
| **CFDI México Nativo** | ✅ | Requiere App | ❌ | Básico |
| **SQLite ↔ PostgreSQL** | ✅ Auto | ❌ | ❌ | Solo PostgreSQL |
| **Sistema Notificaciones** | ✅ 🆕 | ✅ | ✅ | ✅ |
| **Score UX** | **7.9/10** 🆕 | 10/10 | 10/10 | 8/10 |
| **100% Python Open** | ✅ | ❌ Apex | ❌ Cerrado | ✅ |

**Score Competitivo General:** 7.4/10 (+0.8 vs v2.0)

---

## 🎯 ¿Para Quién?

**Ideal para:**
- 🏢 PyMEs 5-50 empleados
- 💻 Equipos con Python in-house
- 🔒 Empresas con requerimientos compliance
- 💰 Startups con presupuesto limitado ($0-$500/mes)
- 🇲🇽 Empresas mexicanas (CFDI 4.0)
- 📊 Organizaciones que necesitan BI/Analytics

---

## 📈 Roadmap

- [x] v1.0: Core CRM + CFDI
- [x] v2.0: Arquitectura Repository + 100% tests
- [x] v2.1: **Soporte SQLite/PostgreSQL flexible + UX Nivel 1**
- [x] v2.1.1: **Sistema de Notificaciones Inteligente** 🆕
- [ ] v2.2: Bulk operations + Import/Export wizard + API REST
- [ ] v2.3: Mobile app (React Native)
- [ ] v3.0: Multi-tenancy + SaaS

---

## 📄 Licencia

MIT License - Ver [LICENSE](LICENSE) para detalles

**Autor:** B10sp4rt4n  
**Última actualización:** Marzo 2026