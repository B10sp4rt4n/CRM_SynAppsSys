# 🗂️ Propuesta de Estructura v2 - Reestructuración AUP

## Estructura Mínima Recomendada

```
crm_exo_v2/
│
├── core/                   # 🧠 Módulos lógicos centrales
│   ├── aup_engine.py      # Motor AUP (Arquitectura Universal de Procesos)
│   ├── database.py        # Gestión SQLite con modelo AUP
│   ├── event_logger.py    # Trazabilidad forense completa
│   ├── cotizador.py       # Motor de cotizaciones
│   ├── config_global.py   # Configuración centralizada
│   ├── recordia_bridge.py # Integración con Recordia
│   └── ui_utils.py        # Utilidades UI compartidas
│
├── ui/                     # 🎨 Vistas Streamlit
│   ├── dashboard.py       # Dashboard ejecutivo
│   ├── sidebar.py         # Navegación
│   ├── main_app.py        # Aplicación principal
│   └── login.py           # Autenticación
│
├── modules/                # 📦 Módulos funcionales
│   ├── empresas.py        # Gestión de empresas
│   ├── prospectos.py      # Gestión de prospectos
│   ├── oportunidades.py   # Pipeline de ventas
│   ├── clientes.py        # Clientes (prospectos convertidos)
│   ├── facturacion.py     # Facturación
│   ├── productos.py       # Catálogo de productos
│   ├── usuarios.py        # Gestión de usuarios
│   └── auth.py            # Autenticación y permisos
│
├── data/                   # 💾 Almacenamiento local
│   ├── aup_crm.sqlite     # Base de datos SQLite
│   ├── exports/           # Exportaciones CSV/Excel
│   └── backups/           # Respaldos automáticos
│
├── docs/                   # 📚 Documentación
│   ├── aup_manifesto.md   # Manifiesto AUP
│   ├── architecture.md    # Arquitectura del sistema
│   ├── diagrams/          # Diagramas de flujo
│   │   ├── flujo_comercial.png
│   │   ├── modelo_aup.png
│   │   └── relaciones_db.png
│   ├── api_reference.md   # Referencia de funciones
│   └── changelog.md       # Registro de cambios
│
├── tests/                  # 🧪 Validaciones y pruebas
│   ├── test_aup_engine.py
│   ├── test_database.py
│   ├── test_reglas_negocio.py
│   ├── validation_suite.py # Suite de validación completa
│   └── fixtures/          # Datos de prueba
│
├── scripts/                # 🛠️ Utilidades
│   ├── init_db.py         # Inicialización de BD
│   ├── migrate_v1_to_v2.py # Migración desde v1
│   ├── limpiar_duplicados.py
│   └── backup_restore.py  # Respaldos
│
├── .github/                # ⚙️ GitHub Actions (CI/CD)
│   └── workflows/
│       ├── tests.yml      # Pruebas automáticas
│       └── deploy.yml     # Despliegue
│
├── requirements.txt        # 📋 Dependencias Python
├── .gitignore             # Ignorar archivos
├── README.md              # Documentación principal
├── LICENSE                # Licencia
└── CHANGELOG.md           # Historial de cambios
```

---

## 📋 Descripción de Directorios

### 🧠 `/core/` - Módulos Lógicos

**Propósito:** Lógica de negocio separada de la UI.

- `aup_engine.py`: Motor central de la arquitectura AUP
- `database.py`: Capa de abstracción para SQLite
- `event_logger.py`: Sistema de trazabilidad forense
- `cotizador.py`: Lógica de cotizaciones
- `recordia_bridge.py`: Integración con sistemas externos

### 🎨 `/ui/` - Vistas Streamlit

**Propósito:** Separación clara entre lógica y presentación.

- Solo componentes visuales
- No lógica de negocio
- Importan desde `/core/` y `/modules/`

### 📦 `/modules/` - Módulos Funcionales

**Propósito:** Funcionalidades específicas del CRM.

- Un archivo por entidad principal
- Implementan las 4 reglas de negocio
- Usan servicios de `/core/`

### 💾 `/data/` - Almacenamiento

**Propósito:** Persistencia de datos local.

- Base de datos SQLite
- Exportaciones temporales
- Backups automáticos

### 📚 `/docs/` - Documentación

**Propósito:** Documentación técnica y de negocio.

- Diagramas visuales
- Manifiesto AUP
- Referencias API
- Changelog detallado

### 🧪 `/tests/` - Validaciones

**Propósito:** Garantizar calidad del código.

- Pruebas unitarias
- Pruebas de integración
- Validación de reglas de negocio
- Fixtures para datos de prueba

---

## 🔄 Migración desde v1

### Pasos Recomendados:

1. **Backup completo de v1**
   ```bash
   cp -r aup_crm_core/ ../backup_v1_$(date +%Y%m%d)/
   ```

2. **Crear nueva estructura**
   ```bash
   mkdir -p crm_exo_v2/{core,ui,modules,data,docs,tests,scripts}
   ```

3. **Migrar archivos existentes**
   - `aup_crm_core/core/*` → `crm_exo_v2/core/`
   - `aup_crm_core/ui/*` → `crm_exo_v2/ui/`
   - `aup_crm_core/modules/*` → `crm_exo_v2/modules/`

4. **Ejecutar script de migración**
   ```bash
   python scripts/migrate_v1_to_v2.py
   ```

---

## 🎯 Ventajas de esta Estructura

### ✅ Separación de Responsabilidades
- Lógica (core) separada de UI
- Fácil testing
- Mantenibilidad mejorada

### ✅ Escalabilidad
- Nuevos módulos sin afectar existentes
- Estructura clara para nuevos desarrolladores

### ✅ Trazabilidad
- Documentación centralizada
- Historial de cambios claro
- Tests automatizados

### ✅ Profesionalización
- Estándares de la industria
- CI/CD con GitHub Actions
- Versionado semántico

---

## 📝 Archivos Clave a Crear

### `README.md` Principal
```markdown
# CRM-EXO v2 - Sistema AUP

Sistema de CRM con Arquitectura Universal de Procesos.

## Instalación
\`\`\`bash
pip install -r requirements.txt
python scripts/init_db.py
streamlit run ui/main_app.py
\`\`\`

## Flujo Comercial
Empresa → Contacto → Prospecto → Oportunidad → Cliente → Facturación
```

### `requirements.txt` Actualizado
```
streamlit>=1.28.0
plotly>=5.18.0
pandas>=2.1.0
openpyxl>=3.1.0
pytest>=7.4.0
black>=23.10.0
flake8>=6.1.0
```

### `.gitignore`
```
# Python
__pycache__/
*.py[cod]
*.so
.Python

# Virtual Environment
venv/
env/

# Data
data/*.sqlite
data/*.db
data/exports/
data/backups/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

---

## 🚀 Próximos Pasos Inmediatos

1. ✅ Crear estructura de directorios
2. ✅ Migrar archivos de v1 a v2
3. ✅ Actualizar imports
4. ✅ Crear tests básicos
5. ✅ Documentar cambios en CHANGELOG.md
6. ✅ Commit y push a `v2-restructure`

---

## 🔐 Buenas Prácticas Implementadas

### Protección de Rama Main
```
GitHub → Settings → Branches → Branch protection rules
- Require pull request reviews
- Require status checks to pass
```

### Versionado Semántico
```
v1.0.0 - Release inicial estable
v1.1.0 - Mejoras menores
v2.0.0 - Reestructuración AUP (breaking changes)
```

### Commits Convencionales
```
feat: Nueva funcionalidad
fix: Corrección de bug
docs: Cambios en documentación
refactor: Refactorización de código
test: Agregar tests
```

---

**Fecha de propuesta:** 2025-11-10  
**Versión base:** v1.0-freeze (`b14510f`)  
**Rama de trabajo:** v2-restructure
