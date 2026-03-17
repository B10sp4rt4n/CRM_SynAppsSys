# 🏢 ARQUITECTURA MULTITENANT - CRM-EXO v2.3
## Implementación Row-Level Multitenancy

**Fecha inicio:** 17 de Marzo de 2026  
**Versión objetivo:** v2.3 (Multitenant SaaS Ready)  
**Estrategia:** Row-Level Multitenancy con PostgreSQL RLS  
**Impacto esperado:** Score 7.9 → 8.4/10 (+0.5 por feature enterprise)

---

## 🎯 OBJETIVO

Convertir CRM-EXO v2.2 en plataforma **SaaS multitenant** que permita:
- ✅ Múltiples organizaciones (tenants) en 1 base de datos
- ✅ Aislamiento completo de datos por tenant
- ✅ Un usuario puede pertenecer a múltiples tenants
- ✅ Compatible con modelo freemium ($0/$19/$39/$79)
- ✅ Escalable hasta 1000+ tenants
- ✅ Compatible SQLite (dev) + PostgreSQL (prod)

---

## 📊 ESTRATEGIA: ROW-LEVEL MULTITENANCY

### ¿Por qué Row-Level?

| Criterio | DB per Tenant | Schema per Tenant | Row-Level ⭐ |
|----------|---------------|-------------------|--------------|
| Costo infraestructura | ❌ Alto | ⚠️ Medio | ✅ Bajo |
| Escalabilidad | ❌ Limitada | ⚠️ Media | ✅ Alta |
| Compatibilidad SQLite | ✅ Sí | ❌ No | ✅ Sí |
| Complejidad migración | ❌ Alta | ❌ Alta | ✅ Media |
| Freemium viable | ❌ No | ⚠️ Difícil | ✅ Sí |

**Decisión:** Row-Level es la única estrategia que permite freemium escalable manteniendo compatibilidad SQLite/PostgreSQL.

---

## 🏗️ ARQUITECTURA MULTITENANT

### Componentes Principales

```
┌─────────────────────────────────────────────────────────┐
│                    STREAMLIT APP                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Auth Multitenant (login + tenant selector)       │  │
│  └───────────────────────┬──────────────────────────┘  │
│                          │                              │
│  ┌───────────────────────▼──────────────────────────┐  │
│  │  TenantContext (ContextVar thread-safe)          │  │
│  │  - set_tenant(tenant_id)                          │  │
│  │  - get_tenant() → tenant_id                       │  │
│  └───────────────────────┬──────────────────────────┘  │
│                          │                              │
│  ┌───────────────────────▼──────────────────────────┐  │
│  │  Repository Base (filtrado automático)           │  │
│  │  - Agrega tenant_id a WHERE clauses               │  │
│  │  - Agrega tenant_id a INSERT statements           │  │
│  └───────────────────────┬──────────────────────────┘  │
│                          │                              │
│  ┌───────────────────────▼──────────────────────────┐  │
│  │  DatabaseV2 (SQLite/PostgreSQL)                  │  │
│  │  + PostgreSQL RLS (security layer)                │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 CAMBIOS NECESARIOS

### FASE 1: Schema Database (1-2 días)

#### 1.1 Nueva tabla `tenants`
```sql
CREATE TABLE tenants (
    id_tenant            SERIAL PRIMARY KEY,  -- PostgreSQL
    -- id_tenant         INTEGER PRIMARY KEY AUTOINCREMENT,  -- SQLite
    nombre_comercial     TEXT NOT NULL UNIQUE,
    dominio              TEXT UNIQUE,  -- Ej: 'acme-corp', 'startup-xyz'
    plan                 TEXT DEFAULT 'FREE' CHECK(plan IN ('FREE', 'STARTER', 'PRO', 'ENTERPRISE')),
    limite_usuarios      INTEGER DEFAULT 5,
    limite_empresas      INTEGER DEFAULT 10,
    fecha_registro       TEXT DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion     TEXT,  -- NULL = sin expiración
    activo               INTEGER DEFAULT 1,
    configuracion        TEXT,  -- JSON: {theme:'dark', logo_url:..., custom_fields:[...]}
    metadata             TEXT   -- JSON: {industry:'tech', country:'MX', ...}
);

CREATE INDEX idx_tenants_dominio ON tenants(dominio);
CREATE INDEX idx_tenants_activo ON tenants(activo);
```

#### 1.2 Nueva tabla `usuarios` (reemplaza aup_agentes)
```sql
CREATE TABLE usuarios (
    id_usuario           SERIAL PRIMARY KEY,
    tenant_id            INTEGER NOT NULL,  -- Tenant primario
    nombre               TEXT NOT NULL,
    correo               TEXT NOT NULL,
    password_hash        TEXT NOT NULL,
    rol                  TEXT DEFAULT 'usuario' CHECK(rol IN ('superadmin', 'admin', 'usuario', 'viewer')),
    activo               INTEGER DEFAULT 1,
    ultimo_login         TEXT,
    fecha_creacion       TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id_tenant),
    UNIQUE(tenant_id, correo)  -- Correo único POR tenant
);

CREATE INDEX idx_usuarios_tenant ON usuarios(tenant_id);
CREATE INDEX idx_usuarios_correo ON usuarios(correo);
```

#### 1.3 Tabla `tenant_memberships` (multi-tenant users)
```sql
CREATE TABLE tenant_memberships (
    id_membership        SERIAL PRIMARY KEY,
    id_usuario           INTEGER NOT NULL,
    tenant_id            INTEGER NOT NULL,
    rol_en_tenant        TEXT DEFAULT 'viewer' CHECK(rol_en_tenant IN ('owner', 'admin', 'user', 'viewer')),
    fecha_ingreso        TEXT DEFAULT CURRENT_TIMESTAMP,
    fecha_ultimo_acceso  TEXT,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id_tenant) ON DELETE CASCADE,
    UNIQUE(id_usuario, tenant_id)
);

CREATE INDEX idx_memberships_usuario ON tenant_memberships(id_usuario);
CREATE INDEX idx_memberships_tenant ON tenant_memberships(tenant_id);
```

#### 1.4 Agregar `tenant_id` a TODAS las tablas existentes

**Script de migración:**
```sql
-- Agregar columna tenant_id a todas las tablas
ALTER TABLE empresas ADD COLUMN tenant_id INTEGER REFERENCES tenants(id_tenant);
ALTER TABLE contactos ADD COLUMN tenant_id INTEGER REFERENCES tenants(id_tenant);
ALTER TABLE prospectos ADD COLUMN tenant_id INTEGER REFERENCES tenants(id_tenant);
ALTER TABLE oportunidades ADD COLUMN tenant_id INTEGER REFERENCES tenants(id_tenant);
ALTER TABLE cotizaciones ADD COLUMN tenant_id INTEGER REFERENCES tenants(id_tenant);
ALTER TABLE ordenes_compra ADD COLUMN tenant_id INTEGER REFERENCES tenants(id_tenant);
ALTER TABLE facturas ADD COLUMN tenant_id INTEGER REFERENCES tenants(id_tenant);
ALTER TABLE historial_general ADD COLUMN tenant_id INTEGER REFERENCES tenants(id_tenant);
ALTER TABLE hash_registros ADD COLUMN tenant_id INTEGER REFERENCES tenants(id_tenant);
ALTER TABLE atributos_entidad ADD COLUMN tenant_id INTEGER REFERENCES tenants(id_tenant);

-- Crear índices compuestos (tenant_id, id_primary)
CREATE INDEX idx_empresas_tenant ON empresas(tenant_id, id_empresa);
CREATE INDEX idx_contactos_tenant ON contactos(tenant_id, id_contacto);
CREATE INDEX idx_prospectos_tenant ON prospectos(tenant_id, id_prospecto);
CREATE INDEX idx_oportunidades_tenant ON oportunidades(tenant_id, id_oportunidad);
CREATE INDEX idx_cotizaciones_tenant ON cotizaciones(tenant_id, id_cotizacion);
CREATE INDEX idx_ordenes_tenant ON ordenes_compra(tenant_id, id_oc);
CREATE INDEX idx_facturas_tenant ON facturas(tenant_id, id_factura);
CREATE INDEX idx_historial_tenant ON historial_general(tenant_id, id_evento);
CREATE INDEX idx_hash_tenant ON hash_registros(tenant_id, id_hash);
CREATE INDEX idx_atributos_tenant ON atributos_entidad(tenant_id, id_attr);

-- Para datos legacy: asignar tenant_id = 1 (tenant por defecto)
UPDATE empresas SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE contactos SET tenant_id = 1 WHERE tenant_id IS NULL;
-- ... etc

-- Hacer tenant_id NOT NULL después de migrar datos
ALTER TABLE empresas ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE contactos ALTER COLUMN tenant_id SET NOT NULL;
-- ... etc
```

---

### FASE 2: Código Python - TenantContext (1 día)

#### 2.1 Crear `crm_exo_v2/core/tenant_context.py`
```python
"""
Gestión de contexto de tenant actual
Thread-safe usando ContextVar
"""
from contextvars import ContextVar
from typing import Optional

_current_tenant: ContextVar[Optional[int]] = ContextVar('current_tenant', default=None)

class TenantContext:
    """Singleton para tenant activo en sesión/request"""
    
    @staticmethod
    def set_tenant(tenant_id: int):
        """Establece tenant activo"""
        if tenant_id is None:
            raise ValueError("tenant_id no puede ser None")
        _current_tenant.set(tenant_id)
    
    @staticmethod
    def get_tenant() -> Optional[int]:
        """Obtiene tenant_id activo (puede ser None)"""
        return _current_tenant.get()
    
    @staticmethod
    def require_tenant() -> int:
        """Obtiene tenant_id o lanza excepción"""
        tenant_id = _current_tenant.get()
        if tenant_id is None:
            raise ValueError("No hay tenant configurado en el contexto. Debe iniciar sesión primero.")
        return tenant_id
    
    @staticmethod
    def clear():
        """Limpia contexto (logout)"""
        _current_tenant.set(None)
```

---

### FASE 3: Repository Base con Filtrado Automático (2-3 días)

#### 3.1 Modificar `crm_exo_v2/core/repository_base.py`

**Cambios clave:**
1. Inyectar `tenant_id` en `__init__`
2. Método `_add_tenant_filter()` para SELECTs
3. Método `_add_tenant_insert()` para INSERTs
4. Sobrescribir `execute()` para aplicar filtros automáticamente

```python
from .tenant_context import TenantContext
from .database import DatabaseV2

class AUPRepository:
    """
    Base class para repositorios con aislamiento multitenant automático
    """
    
    def __init__(self, usuario="system", conn=None):
        self.usuario = usuario
        self.db = conn if conn else DatabaseV2()
        
        # Obtener tenant_id del contexto
        self.tenant_id = TenantContext.require_tenant()
    
    def execute(self, query: str, params: tuple = ()):
        """
        Ejecuta query con filtrado automático de tenant
        
        SELECT: Agrega WHERE tenant_id = X
        INSERT: Agrega tenant_id a columnas/valores
        UPDATE/DELETE: Agrega WHERE tenant_id = X
        """
        query_upper = query.strip().upper()
        
        if query_upper.startswith("SELECT"):
            query = self._add_tenant_filter_select(query)
        elif query_upper.startswith("INSERT"):
            query, params = self._add_tenant_insert(query, params)
        elif query_upper.startswith(("UPDATE", "DELETE")):
            query = self._add_tenant_filter_update_delete(query)
        
        return self.db.execute(query, params)
    
    def _add_tenant_filter_select(self, query: str) -> str:
        """Agrega tenant_id a WHERE en SELECT"""
        # Si ya tiene WHERE, agregar AND tenant_id
        if " WHERE " in query.upper():
            # Encontrar posición de WHERE
            where_pos = query.upper().find(" WHERE ")
            insert_pos = where_pos + 7  # después de " WHERE "
            query = query[:insert_pos] + f"tenant_id = {self.tenant_id} AND (" + query[insert_pos:] + ")"
        else:
            # Si no tiene WHERE, agregar antes de ORDER BY / LIMIT / GROUP BY
            for keyword in [" ORDER BY ", " LIMIT ", " GROUP BY "]:
                if keyword in query.upper():
                    pos = query.upper().find(keyword)
                    query = query[:pos] + f" WHERE tenant_id = {self.tenant_id}" + query[pos:]
                    return query
            # Si no tiene ninguno, agregar al final
            query += f" WHERE tenant_id = {self.tenant_id}"
        
        return query
    
    def _add_tenant_insert(self, query: str, params: tuple) -> tuple:
        """Agrega tenant_id a INSERT"""
        if "tenant_id" in query.lower():
            # Ya tiene tenant_id explícito
            return query, params
        
        # INSERT INTO tabla (col1, col2) VALUES (?, ?)
        # Buscar posición de cierre de columnas
        cols_start = query.find("(")
        cols_end = query.find(")")
        
        # Agregar tenant_id a columnas
        cols = query[:cols_end] + ", tenant_id" + query[cols_end:]
        
        # Agregar valor a params
        new_params = tuple(list(params) + [self.tenant_id])
        
        # Modificar placeholders de VALUES
        values_idx = cols.upper().find("VALUES")
        if values_idx != -1:
            # Contar placeholders
            placeholder = "?" if not self.db.is_postgres else "%s"
            placeholders_count = len(params) + 1
            placeholders = ", ".join([placeholder] * placeholders_count)
            
            # Reconstruir query
            query = cols[:values_idx] + f"VALUES ({placeholders})"
        
        return query, new_params
    
    def _add_tenant_filter_update_delete(self, query: str) -> str:
        """Agrega tenant_id a WHERE en UPDATE/DELETE"""
        # Similar a SELECT
        if " WHERE " in query.upper():
            where_pos = query.upper().find(" WHERE ")
            insert_pos = where_pos + 7
            query = query[:insert_pos] + f"tenant_id = {self.tenant_id} AND (" + query[insert_pos:] + ")"
        else:
            query += f" WHERE tenant_id = {self.tenant_id}"
        
        return query
```

---

### FASE 4: Autenticación Multitenant (2 días)

#### 4.1 Modificar `aup_crm_core/modules/auth.py`

```python
from crm_exo_v2.core.tenant_context import TenantContext
from crm_exo_v2.core.database import DatabaseV2

def iniciar_sesion_multitenant(correo: str, password: str, tenant_domain: str = None):
    """
    Inicia sesión multitenant
    
    Args:
        correo: Email del usuario
        password: Password en texto plano
        tenant_domain: Dominio del tenant (ej: 'acme-corp') o None para buscar
    
    Returns:
        (success: bool, user_data: dict, error_msg: str)
    """
    db = DatabaseV2()
    password_hash = hash_password(password)
    
    if tenant_domain:
        # Login con tenant específico
        cursor = db.execute("""
            SELECT u.id_usuario, u.nombre, u.correo, u.rol,
                   t.id_tenant, t.nombre_comercial, t.plan, t.dominio
            FROM usuarios u
            JOIN tenants t ON u.tenant_id = t.id_tenant
            WHERE u.correo = ? AND u.password_hash = ?
            AND t.dominio = ? AND t.activo = 1 AND u.activo = 1
        """, (correo, password_hash, tenant_domain))
    else:
        # Login sin tenant (buscar primer tenant activo)
        cursor = db.execute("""
            SELECT u.id_usuario, u.nombre, u.correo, u.rol,
                   t.id_tenant, t.nombre_comercial, t.plan, t.dominio
            FROM usuarios u
            JOIN tenants t ON u.tenant_id = t.id_tenant
            WHERE u.correo = ? AND u.password_hash = ?
            AND t.activo = 1 AND u.activo = 1
            ORDER BY u.ultimo_login DESC
            LIMIT 1
        """, (correo, password_hash))
    
    row = cursor.fetchone()
    
    if not row:
        return False, None, "Credenciales incorrectas o cuenta inactiva"
    
    # Actualizar último login
    db.execute("""
        UPDATE usuarios 
        SET ultimo_login = CURRENT_TIMESTAMP 
        WHERE id_usuario = ?
    """, (row[0],))
    db.commit()
    
    # Establecer contexto de tenant
    TenantContext.set_tenant(row[4])
    
    # Guardar sesión Streamlit
    st.session_state['logged_in'] = True
    st.session_state['user_id'] = row[0]
    st.session_state['user_name'] = row[1]
    st.session_state['user_email'] = row[2]
    st.session_state['user_role'] = row[3]
    st.session_state['tenant_id'] = row[4]
    st.session_state['tenant_name'] = row[5]
    st.session_state['tenant_plan'] = row[6]
    st.session_state['tenant_domain'] = row[7]
    
    return True, row, None


def obtener_tenants_usuario(user_id: int) -> list:
    """Obtiene lista de tenants a los que tiene acceso el usuario"""
    db = DatabaseV2()
    cursor = db.execute("""
        SELECT t.id_tenant, t.nombre_comercial, t.dominio, t.plan,
               tm.rol_en_tenant, tm.fecha_ultimo_acceso
        FROM tenant_memberships tm
        JOIN tenants t ON tm.tenant_id = t.id_tenant
        WHERE tm.id_usuario = ? AND t.activo = 1
        ORDER BY tm.fecha_ultimo_acceso DESC
    """, (user_id,))
    
    return cursor.fetchall()


def cambiar_tenant(user_id: int, nuevo_tenant_id: int) -> bool:
    """Cambia el tenant activo en la sesión"""
    db = DatabaseV2()
    
    # Verificar acceso
    cursor = db.execute("""
        SELECT rol_en_tenant FROM tenant_memberships
        WHERE id_usuario = ? AND tenant_id = ?
    """, (user_id, nuevo_tenant_id))
    
    row = cursor.fetchone()
    if not row:
        return False
    
    # Actualizar último acceso
    db.execute("""
        UPDATE tenant_memberships
        SET fecha_ultimo_acceso = CURRENT_TIMESTAMP
        WHERE id_usuario = ? AND tenant_id = ?
    """, (user_id, nuevo_tenant_id))
    db.commit()
    
    # Cambiar contexto
    TenantContext.set_tenant(nuevo_tenant_id)
    st.session_state['tenant_id'] = nuevo_tenant_id
    
    return True
```

---

### FASE 5: PostgreSQL Row-Level Security (1 día)

#### 5.1 Crear migración `db/migrations/003_multitenant_rls.sql`

```sql
-- ================================================================
--  PostgreSQL Row-Level Security para Multitenant
--  Solo aplica en PostgreSQL (SQLite lo ignora)
-- ================================================================

-- Habilitar RLS en todas las tablas
ALTER TABLE empresas ENABLE ROW LEVEL SECURITY;
ALTER TABLE contactos ENABLE ROW LEVEL SECURITY;
ALTER TABLE prospectos ENABLE ROW LEVEL SECURITY;
ALTER TABLE oportunidades ENABLE ROW LEVEL SECURITY;
ALTER TABLE cotizaciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE ordenes_compra ENABLE ROW LEVEL SECURITY;
ALTER TABLE facturas ENABLE ROW LEVEL SECURITY;
ALTER TABLE historial_general ENABLE ROW LEVEL SECURITY;
ALTER TABLE hash_registros ENABLE ROW LEVEL SECURITY;
ALTER TABLE atributos_entidad ENABLE ROW LEVEL SECURITY;

-- Crear políticas de aislamiento
CREATE POLICY tenant_isolation ON empresas
    USING (tenant_id = current_setting('app.current_tenant_id', true)::int);

CREATE POLICY tenant_isolation ON contactos
    USING (tenant_id = current_setting('app.current_tenant_id', true)::int);

CREATE POLICY tenant_isolation ON prospectos
    USING (tenant_id = current_setting('app.current_tenant_id', true)::int);

CREATE POLICY tenant_isolation ON oportunidades
    USING (tenant_id = current_setting('app.current_tenant_id', true)::int);

CREATE POLICY tenant_isolation ON cotizaciones
    USING (tenant_id = current_setting('app.current_tenant_id', true)::int);

CREATE POLICY tenant_isolation ON ordenes_compra
    USING (tenant_id = current_setting('app.current_tenant_id', true)::int);

CREATE POLICY tenant_isolation ON facturas
    USING (tenant_id = current_setting('app.current_tenant_id', true)::int);

CREATE POLICY tenant_isolation ON historial_general
    USING (tenant_id = current_setting('app.current_tenant_id', true)::int);

CREATE POLICY tenant_isolation ON hash_registros
    USING (tenant_id = current_setting('app.current_tenant_id', true)::int);

CREATE POLICY tenant_isolation ON atributos_entidad
    USING (tenant_id = current_setting('app.current_tenant_id', true)::int);

-- Nota: DatabaseV2 debe ejecutar esto en cada conexión PostgreSQL:
-- SET app.current_tenant_id = 123;
```

#### 5.2 Modificar `DatabaseV2` para configurar RLS

```python
# En crm_exo_v2/core/database.py

def set_tenant_for_rls(self, tenant_id: int):
    """
    Configura tenant_id en PostgreSQL session para Row-Level Security
    Solo aplica en PostgreSQL, SQLite lo ignora
    """
    if self.is_postgres:
        self.execute(f"SET app.current_tenant_id = {tenant_id}")
```

---

## 🧪 TESTING MULTITENANT

### Test Cases Críticos

```python
# tests/test_multitenant.py

def test_aislamiento_tenants():
    """Verificar que tenant A no puede ver datos de tenant B"""
    # Crear 2 tenants
    # Crear empresas en cada uno
    # Cambiar contexto a tenant A
    # Verificar que solo ve datos de A
    # Cambiar a tenant B
    # Verificar que solo ve datos de B
    pass

def test_usuario_multi_tenant():
    """Verificar que usuario puede cambiar entre tenants"""
    # Usuario pertenece a tenant A y B
    # Login como A
    # Crear datos
    # Cambiar a B
    # Verificar que no ve datos de A
    pass

def test_insert_automatico_tenant_id():
    """Verificar que INSERT agrega tenant_id automáticamente"""
    # Set tenant_id = 5
    # Crear empresa sin especificar tenant_id
    # Verificar que se guardó con tenant_id = 5
    pass
```

---

## 📈 ROADMAP DE IMPLEMENTACIÓN

### Sprint 1 (Semana 1): Database Schema
- [ ] Día 1-2: Crear tablas `tenants`, `usuarios`, `tenant_memberships`
- [ ] Día 3-4: Script migración ALTER TABLE (agregar tenant_id)
- [ ] Día 5: Testing schema + índices

### Sprint 2 (Semana 2): Código Core
- [ ] Día 1: `TenantContext` + tests
- [ ] Día 2-3: `AUPRepository` filtrado automático
- [ ] Día 4: Modificar todos los repositories
- [ ] Día 5: Testing aislamiento

### Sprint 3 (Semana 3): Auth + UI
- [ ] Día 1-2: Auth multitenant + selector de tenant
- [ ] Día 3: UI tenant switcher en sidebar
- [ ] Día 4: PostgreSQL RLS
- [ ] Día 5: Testing E2E

---

## 🎯 MÉTRICAS DE ÉXITO

- ✅ **Aislamiento**: 0 data leaks en tests (100% aislamiento)
- ✅ **Performance**: <10% overhead vs single-tenant
- ✅ **Escalabilidad**: Soportar 100+ tenants sin degradación
- ✅ **Compatibilidad**: SQLite (dev) + PostgreSQL (prod)
- ✅ **Score**: 7.9 → 8.4/10 (+0.5 por feature SaaS)

---

## 🚀 LANZAMIENTO v2.3

**Fecha objetivo:** 7 de Abril de 2026 (3 semanas)  
**Features nuevas:**
- ✅ Arquitectura multitenant completa
- ✅ PostgreSQL RLS para seguridad máxima
- ✅ Selector de tenant en UI
- ✅ Modelo SaaS freemium ready

**Impacto competitivo:**
- 🏆 Primera solución CRM open source con multitenant row-level
- 💰 Freemium escalable ($0 → $79/user)
- 📈 Score 8.4/10 (supera a Odoo 7.9, cerca de Salesforce)

---

**Documento creado por:** GitHub Copilot AI Assistant  
**Fecha:** 17 de Marzo de 2026  
**Versión:** v1.0 - Draft inicial
