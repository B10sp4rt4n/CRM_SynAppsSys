# 🔄 Migración SQLite ↔ PostgreSQL

## Guía de Configuración Flexible de Base de Datos

CRM-EXO v2 ahora soporta **SQLite y PostgreSQL** con auto-detección transparente.

---

## 🎯 Cómo Funciona

El sistema detecta automáticamente qué motor usar:

```python
# Prioridad de detección:
1. DATABASE_URL en variables de entorno → PostgreSQL
2. DATABASE_URL en Streamlit secrets → PostgreSQL  
3. Fallback automático → SQLite local
```

**Sin cambios de código necesarios** - funciona transparente para toda la aplicación.

---

## 📦 Configuración por Entorno

### Opción 1: SQLite (Predeterminado)

**No requiere configuración**. Funciona "out of the box":

```bash
# Simplemente ejecuta la app
streamlit run app_crm_exo_v2.py
```

SQLite almacena datos en:
```
crm_exo_v2/data/crm_exo_v2.sqlite
```

**✅ Ideal para:**
- Desarrollo local
- Demos y pruebas
- Equipos pequeños (1-10 usuarios)
- Entornos sin internet

---

### Opción 2: PostgreSQL (Producción)

#### A. Usando Streamlit Secrets (Recomendado)

Crea `.streamlit/secrets.toml` en la raíz del proyecto:

```toml
DATABASE_URL = "postgresql://user:password@host:5432/database?sslmode=require"
```

**Ejemplo con Neon.tech:**
```toml
DATABASE_URL = "postgresql://alex:AbC123xyz@ep-cool-darkness-123456.us-east-2.aws.neon.tech/neondb?sslmode=require"
```

#### B. Usando Variables de Entorno

```bash
# Linux/Mac
export DATABASE_URL="postgresql://user:password@host/database"
streamlit run app_crm_exo_v2.py

# Windows (CMD)
set DATABASE_URL=postgresql://user:password@host/database
streamlit run app_crm_exo_v2.py

# Windows (PowerShell)
$env:DATABASE_URL="postgresql://user:password@host/database"
streamlit run app_crm_exo_v2.py
```

#### C. Usando archivo .env (Scripts)

Crea `.env` en la raíz:
```env
DATABASE_URL=postgresql://user:password@host/database
```

Luego carga con python-dotenv:
```python
from dotenv import load_dotenv
load_dotenv()

from crm_exo_v2.core.database import get_db
db = get_db()  # Auto-detecta PostgreSQL
```

**✅ Ideal para:**
- Producción cloud (Render, Railway, Heroku)
- Equipos medianos/grandes (10-100+ usuarios)
- Datos sensibles/críticos
- Escalabilidad horizontal
- Integraciones BI/Analytics

---

## 🧪 Verificar Configuración Actual

```python
from crm_exo_v2.core.database import get_db

db = get_db()
print(f"Motor actual: {db.engine_name}")
print(f"¿Es PostgreSQL?: {db.is_postgres}")
print(f"¿Es SQLite?: {db.is_sqlite}")
```

**Salida esperada:**
```
Motor actual: postgresql
¿Es PostgreSQL?: True
¿Es SQLite?: False
```

---

## 🔀 Migración de Datos

### SQLite → PostgreSQL

#### Paso 1: Preparar PostgreSQL

Ejecuta el schema en tu instancia PostgreSQL:

```bash
# Conectar a tu PostgreSQL
psql $DATABASE_URL

# Ejecutar migraciones
\i db/migrations/001_schema_canonico_postgres.sql
\i db/migrations/002_views_integracion_fradma_dashboard3.sql
```

#### Paso 2: Exportar datos de SQLite

```bash
cd scripts
python migrate_sqlite_to_canonical_pg.py
```

Este script:
- ✅ Lee de `crm_exo_v2.sqlite`
- ✅ Convierte tipos de datos
- ✅ Inserta en PostgreSQL
- ✅ Preserva IDs y relaciones
- ✅ Valida integridad

#### Paso 3: Configurar DATABASE_URL

```toml
# .streamlit/secrets.toml
DATABASE_URL = "postgresql://..."
```

#### Paso 4: Reiniciar la app

```bash
streamlit run app_crm_exo_v2.py
```

La app detectará PostgreSQL automáticamente.

---

### PostgreSQL → SQLite (Rollback)

#### Paso 1: Exportar con pg_dump

```bash
pg_dump $DATABASE_URL > backup_postgres.sql
```

#### Paso 2: Convertir formato

```bash
# Herramienta: pgloader o conversión manual
# (Específico según tu caso)
```

#### Paso 3: Remover DATABASE_URL

```bash
# Comentar o eliminar
# DATABASE_URL = "..."
```

#### Paso 4: Reiniciar

La app volverá automáticamente a SQLite local.

---

## 🛠️ Diferencias Manejadas Automáticamente

El sistema adapta automáticamente estas diferencias:

| Aspecto | SQLite | PostgreSQL | Adaptación Automática |
|---------|--------|------------|----------------------|
| **Placeholders** | `?` | `%s` | ✅ Auto-convertido |
| **AUTOINCREMENT** | `AUTOINCREMENT` | `SERIAL` | ✅ Auto-convertido |
| **Last Insert ID** | `lastrowid` | `RETURNING id` | ✅ Helper unified |
| **Row factory** | `sqlite3.Row` | `dict_row` | ✅ Dict-like en ambos |
| **Timestamp** | `CURRENT_TIMESTAMP` | `NOW()` | ✅ Helper `get_current_timestamp()` |

**Código del desarrollador:**
```python
# Funciona en AMBOS motores sin cambios:
from crm_exo_v2.core.sql_helpers import insert_returning_id

new_id = insert_returning_id(db, 'empresas', {
    'nombre': 'Mi Empresa',
    'rfc': 'XXX010101XXX'
})
```

---

## 📊 Comparativa de Rendimiento

### SQLite
- ✅ **Setup:** Instantáneo (0 configuración)
- ✅ **Latencia:** Ultra-baja (local)
- ✅ **Concurrencia:** Baja (lecturas ok, escrituras bloqueantes)
- ⚠️ **Límite:** ~10 usuarios concurrentes
- ✅ **Costo:** $0

### PostgreSQL
- ⚠️ **Setup:** Requiere servidor/cloud
- ⚠️ **Latencia:** 10-100ms (network)
- ✅ **Concurrencia:** Alta (MVCC)
- ✅ **Límite:** 100-10,000+ usuarios
- ⚠️ **Costo:** $0-$500/mes (cloud)

---

## 🔐 Seguridad de Credentials

### ⚠️ NUNCA Hagas Esto

```python
# ❌ NO hardcodear credentials
DATABASE_URL = "postgresql://user:password@host/db"
```

```toml
# ❌ NO commitear secrets.toml
# .streamlit/secrets.toml debe estar en .gitignore
```

### ✅ Buenas Prácticas

1. **Usa .gitignore:**
```gitignore
.streamlit/secrets.toml
.env
*.sqlite
```

2. **Usa variables de entorno en CI/CD:**
```yaml
# GitHub Actions
env:
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

3. **Rota credentials regularmente:**
```bash
# Cambiar password cada 90 días
# Invalida tokens viejos
```

---

## 🧪 Testing con Ambos Motores

```python
# conftest.py
import pytest
from crm_exo_v2.core.db_config import reset_db_config, get_db_config

@pytest.fixture
def use_sqlite():
    reset_db_config()
    # Forzar SQLite
    import os
    old_url = os.environ.get('DATABASE_URL')
    if 'DATABASE_URL' in os.environ:
        del os.environ['DATABASE_URL']
    
    yield
    
    if old_url:
        os.environ['DATABASE_URL'] = old_url
    reset_db_config()

@pytest.fixture
def use_postgres():
    reset_db_config()
    # Usar DATABASE_URL del entorno
    yield
    reset_db_config()
```

---

## 📚 Recursos Adicionales

- [Neon.tech](https://neon.tech) - PostgreSQL serverless gratuito
- [psycopg3 docs](https://www.psycopg.org/psycopg3/docs/) - Driver PostgreSQL
- [SQLite limits](https://www.sqlite.org/limits.html) - Límites técnicos
- [PostgreSQL tutorial](https://www.postgresqltutorial.com/) - Guías

---

## 🆘 Troubleshooting

### Error: "psycopg not installed"

```bash
pip install 'psycopg[binary]>=3.3.3'
```

### Error: "Connection refused"

```bash
# Verificar que PostgreSQL esté corriendo
pg_isready -h host -p 5432

# Verificar firewall/seguridad
# Neon: Whitelist IP en dashboard
```

### Error: "SSL required"

Agregar `?sslmode=require` al DATABASE_URL:
```
postgresql://user:pass@host/db?sslmode=require
```

### Los tests fallan con PostgreSQL

```bash
# Crear base de datos de test
createdb crm_test

# Ejecutar migraciones
psql crm_test < db/migrations/001_schema_canonico_postgres.sql

# Configurar DATABASE_URL de test
export DATABASE_URL="postgresql://localhost/crm_test"
pytest
```

---

## 🎯 Recomendaciones por Escenario

| Escenario | Motor Recomendado | Justificación |
|-----------|-------------------|---------------|
| **Desarrollo local** | SQLite | Cero configuración, rápido |
| **Demo/POC** | SQLite | Fácil compartir archivo |
| **Producción <10 usuarios** | SQLite o PostgreSQL | Ambos funcionan |
| **Producción 10-50 usuarios** | PostgreSQL | Mejor concurrencia |
| **Producción >50 usuarios** | PostgreSQL | Única opción viable |
| **Multi-tenant SaaS** | PostgreSQL | Schema isolation |
| **Integración BI** | PostgreSQL | Vistas y analytics |
| **Edge computing** | SQLite | Sin dependencias externas |

---

## ✅ Checklist de Migración

- [ ] Backup completo de datos actuales
- [ ] PostgreSQL configurado y accesible
- [ ] Migraciones ejecutadas (001, 002)
- [ ] DATABASE_URL configurado
- [ ] Tests ejecutados exitosamente
- [ ] Validación de integridad de datos
- [ ] Rollback plan documentado
- [ ] Monitoreo configurado
- [ ] Equipo capacitado en nuevo setup

---

**Autor:** CRM-EXO v2 Team  
**Última actualización:** Marzo 2026  
**Versión:** 2.1.0
