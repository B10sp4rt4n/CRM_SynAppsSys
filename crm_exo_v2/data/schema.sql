-- ================================================================
--  ESQUEMA AUP-EXO v2 - Base de datos CRM estructural
--  Resolución inversa | Forense por diseño | Compatibilidad progresiva
--  Creado: 2025-11-10
-- ================================================================

-- ================================================================
--  NÚCLEO 1: IDENTIDAD
--  Define entidades comerciales y relaciones base
-- ================================================================

CREATE TABLE empresas (
    id_empresa       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre           TEXT NOT NULL,
    rfc              TEXT,
    sector           TEXT,
    telefono         TEXT,
    correo           TEXT,
    fecha_alta       TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE contactos (
    id_contacto      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_empresa       INTEGER NOT NULL,
    nombre           TEXT NOT NULL,
    correo           TEXT,
    telefono         TEXT,
    puesto           TEXT,
    fecha_alta       TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_empresa) REFERENCES empresas(id_empresa)
);

CREATE TABLE prospectos (
    id_prospecto     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_empresa       INTEGER NOT NULL,
    id_contacto      INTEGER NOT NULL,
    estado           TEXT DEFAULT 'Activo',
    origen           TEXT,
    fecha_creacion   TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_empresa) REFERENCES empresas(id_empresa),
    FOREIGN KEY (id_contacto) REFERENCES contactos(id_contacto)
);

-- ================================================================
--  NÚCLEO 2: TRANSACCIÓN
--  Ciclo comercial activo y sus valores económicos
-- ================================================================

CREATE TABLE oportunidades (
    id_oportunidad   INTEGER PRIMARY KEY AUTOINCREMENT,
    id_prospecto     INTEGER NOT NULL,
    nombre           TEXT,
    etapa            TEXT DEFAULT 'Inicial',
    probabilidad     INTEGER DEFAULT 0,
    monto_estimado   REAL,
    fecha_creacion   TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_prospecto) REFERENCES prospectos(id_prospecto)
);

CREATE TABLE cotizaciones (
    id_cotizacion        INTEGER PRIMARY KEY AUTOINCREMENT,
    id_oportunidad       INTEGER NOT NULL,
    modo                 TEXT CHECK(modo IN ('minimo','generico','externo')),
    fuente               TEXT,
    monto_total          REAL NOT NULL,
    moneda               TEXT DEFAULT 'MXN',
    version              INTEGER DEFAULT 1,
    estado               TEXT DEFAULT 'Borrador',
    fecha_creacion       TEXT DEFAULT CURRENT_TIMESTAMP,
    hash_integridad      TEXT,
    notas                TEXT,
    FOREIGN KEY (id_oportunidad) REFERENCES oportunidades(id_oportunidad)
);

-- ================================================================
--  NÚCLEO 3: FACTURACIÓN
--  Cierre contable y validación documental
-- ================================================================

CREATE TABLE ordenes_compra (
    id_oc             INTEGER PRIMARY KEY AUTOINCREMENT,
    id_oportunidad    INTEGER NOT NULL,
    numero_oc         TEXT,
    fecha_oc          TEXT,
    monto_oc          REAL,
    moneda            TEXT,
    archivo_pdf       TEXT,
    FOREIGN KEY (id_oportunidad) REFERENCES oportunidades(id_oportunidad)
);

CREATE TABLE facturas (
    id_factura        INTEGER PRIMARY KEY AUTOINCREMENT,
    id_oc             INTEGER NOT NULL,
    uuid              TEXT,
    serie             TEXT,
    folio             TEXT,
    fecha_emision     TEXT,
    monto_total       REAL,
    moneda            TEXT,
    archivo_xml       TEXT,
    archivo_pdf       TEXT,
    FOREIGN KEY (id_oc) REFERENCES ordenes_compra(id_oc)
);

-- ================================================================
--  NÚCLEO 4: TRAZABILIDAD
--  Registro forense, auditoría y consistencia AUP
-- ================================================================

CREATE TABLE historial_general (
    id_evento         INTEGER PRIMARY KEY AUTOINCREMENT,
    entidad           TEXT,
    id_entidad        INTEGER,
    accion            TEXT,
    valor_anterior    TEXT,
    valor_nuevo       TEXT,
    usuario           TEXT,
    timestamp         TEXT DEFAULT CURRENT_TIMESTAMP,
    hash_evento       TEXT
);

CREATE TABLE hash_registros (
    id_hash           INTEGER PRIMARY KEY AUTOINCREMENT,
    tabla_origen      TEXT,
    id_registro       INTEGER,
    hash_sha256       TEXT,
    timestamp         TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ================================================================
--  EXTENSIBILIDAD PARAMÉTRICA (Atributos Dinámicos)
-- ================================================================

CREATE TABLE atributos_entidad (
    id_attr           INTEGER PRIMARY KEY AUTOINCREMENT,
    entidad           TEXT NOT NULL,
    id_entidad        INTEGER NOT NULL,
    nombre_attr       TEXT NOT NULL,
    valor_attr        TEXT,
    tipo_dato         TEXT DEFAULT 'text',
    fecha_creacion    TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ================================================================
--  ÍNDICES PARA RENDIMIENTO
-- ================================================================

CREATE INDEX IF NOT EXISTS idx_contactos_empresa ON contactos(id_empresa);
CREATE INDEX IF NOT EXISTS idx_prospectos_empresa ON prospectos(id_empresa);
CREATE INDEX IF NOT EXISTS idx_oportunidades_prospecto ON oportunidades(id_prospecto);
CREATE INDEX IF NOT EXISTS idx_cotizaciones_oportunidad ON cotizaciones(id_oportunidad);
CREATE INDEX IF NOT EXISTS idx_ordenes_oportunidad ON ordenes_compra(id_oportunidad);
CREATE INDEX IF NOT EXISTS idx_facturas_oc ON facturas(id_oc);
CREATE INDEX IF NOT EXISTS idx_historial_entidad ON historial_general(entidad, id_entidad);
CREATE INDEX IF NOT EXISTS idx_hash_origen ON hash_registros(tabla_origen, id_registro);
CREATE INDEX IF NOT EXISTS idx_atributos_entidad ON atributos_entidad(entidad, id_entidad);
