-- ================================================================
--  ESQUEMA AUP-EXO v2 - Base de datos CRM estructural
--  Resolución inversa | Forense por diseño | Compatibilidad progresiva
--  Creado: 2025-11-10 | Sincronizado con app_crm_exo_v2.py: 2025-11-xx
-- ================================================================
-- FUENTE DE VERDAD: app_crm_exo_v2.py → inicializar_db() + aplicar_migraciones()
-- Este archivo representa el schema objetivo (fresh install == post-migraciones).
-- Para DBs existentes las migraciones en aplicar_migraciones() son el camino.
-- ================================================================

-- ================================================================
--  NÚCLEO 1: IDENTIDAD
--  Define entidades comerciales y relaciones base
-- ================================================================

CREATE TABLE IF NOT EXISTS empresas (
    id_empresa       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre           TEXT NOT NULL,
    rfc              TEXT,
    sector           TEXT,
    telefono         TEXT,
    correo           TEXT,
    fecha_alta       TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contactos (
    id_contacto      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_empresa       INTEGER NOT NULL,
    nombre           TEXT NOT NULL,
    correo           TEXT,
    telefono         TEXT,
    puesto           TEXT,
    fecha_alta       TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_empresa) REFERENCES empresas(id_empresa)
);

-- es_cliente y fecha_conversion_cliente añadidos en migración (Nov 2025)
CREATE TABLE IF NOT EXISTS prospectos (
    id_prospecto              INTEGER PRIMARY KEY AUTOINCREMENT,
    id_empresa                INTEGER NOT NULL,
    id_contacto               INTEGER NOT NULL,
    estado                    TEXT DEFAULT 'Activo',
    origen                    TEXT,
    es_cliente                INTEGER DEFAULT 0,
    fecha_conversion_cliente  TEXT,
    fecha_creacion            TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_empresa)  REFERENCES empresas(id_empresa),
    FOREIGN KEY (id_contacto) REFERENCES contactos(id_contacto)
);

-- ================================================================
--  NÚCLEO 2: TRANSACCIÓN
--  Ciclo comercial activo y sus valores económicos
-- ================================================================

-- oc_recibida y fecha_estimada_cierre añadidos en migración (Nov 2025)
CREATE TABLE IF NOT EXISTS oportunidades (
    id_oportunidad       INTEGER PRIMARY KEY AUTOINCREMENT,
    id_prospecto         INTEGER NOT NULL,
    nombre               TEXT,
    etapa                TEXT DEFAULT 'Calificación',
    probabilidad         INTEGER DEFAULT 0,
    monto_estimado       REAL,
    oc_recibida          INTEGER DEFAULT 0,
    fecha_estimada_cierre TEXT,
    fecha_creacion       TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_prospecto) REFERENCES prospectos(id_prospecto)
);

CREATE TABLE IF NOT EXISTS cotizaciones (
    id_cotizacion    INTEGER PRIMARY KEY AUTOINCREMENT,
    id_oportunidad   INTEGER NOT NULL,
    modo             TEXT CHECK(modo IN ('minimo','generico','externo')),
    fuente           TEXT,
    monto_total      REAL NOT NULL,
    moneda           TEXT DEFAULT 'MXN',
    version          INTEGER DEFAULT 1,
    estado           TEXT DEFAULT 'Borrador',
    fecha_creacion   TEXT DEFAULT CURRENT_TIMESTAMP,
    hash_integridad  TEXT,
    notas            TEXT,
    FOREIGN KEY (id_oportunidad) REFERENCES oportunidades(id_oportunidad)
);

-- Integración con proveedores externos (DynamiQuote, etc.)
CREATE TABLE IF NOT EXISTS cotizaciones_externas (
    id_sync            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cotizacion      INTEGER NOT NULL,
    proveedor          TEXT NOT NULL,
    external_quote_id  TEXT,
    playbook           TEXT,
    api_url            TEXT,
    request_payload    TEXT,
    response_payload   TEXT,
    estado_sync        TEXT DEFAULT 'importada',
    fecha_sync         TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_cotizacion) REFERENCES cotizaciones(id_cotizacion)
);

-- ================================================================
--  NÚCLEO 3: FACTURACIÓN
--  Cierre contable y validación documental
-- ================================================================

CREATE TABLE IF NOT EXISTS ordenes_compra (
    id_oc            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_oportunidad   INTEGER NOT NULL,
    numero_oc        TEXT,
    fecha_oc         TEXT,
    monto_oc         REAL,
    moneda           TEXT,
    archivo_pdf      TEXT,
    FOREIGN KEY (id_oportunidad) REFERENCES oportunidades(id_oportunidad)
);

CREATE TABLE IF NOT EXISTS facturas (
    id_factura    INTEGER PRIMARY KEY AUTOINCREMENT,
    id_oc         INTEGER NOT NULL,
    uuid          TEXT,
    serie         TEXT,
    folio         TEXT,
    fecha_emision TEXT,
    monto_total   REAL,
    moneda        TEXT,
    archivo_xml   TEXT,
    archivo_pdf   TEXT,
    FOREIGN KEY (id_oc) REFERENCES ordenes_compra(id_oc)
);

-- Registro de pagos recibidos (cobranza real)
CREATE TABLE IF NOT EXISTS pagos (
    id_pago          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_factura       INTEGER NOT NULL,
    fecha_pago       TEXT NOT NULL,
    monto_pagado     REAL NOT NULL,
    moneda           TEXT DEFAULT 'MXN',
    metodo_pago      TEXT,
    referencia       TEXT,
    notas            TEXT,
    fecha_registro   TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_factura) REFERENCES facturas(id_factura)
);

-- ================================================================
--  NÚCLEO 4: TRAZABILIDAD
--  Registro forense, auditoría y consistencia AUP
-- ================================================================

CREATE TABLE IF NOT EXISTS historial_general (
    id_evento      INTEGER PRIMARY KEY AUTOINCREMENT,
    entidad        TEXT,
    id_entidad     INTEGER,
    accion         TEXT,
    valor_anterior TEXT,
    valor_nuevo    TEXT,
    usuario        TEXT,
    timestamp      TEXT DEFAULT CURRENT_TIMESTAMP,
    hash_evento    TEXT
);

CREATE TABLE IF NOT EXISTS hash_registros (
    id_hash      INTEGER PRIMARY KEY AUTOINCREMENT,
    tabla_origen TEXT,
    id_registro  INTEGER,
    hash_sha256  TEXT,
    timestamp    TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Snapshots del pipeline para análisis de salud (score_flujo, salud, prioridad)
CREATE TABLE IF NOT EXISTS pipeline_helper_oportunidad_snapshots (
    id_snapshot      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_oportunidad   INTEGER NOT NULL,
    fecha_snapshot   TEXT NOT NULL,
    score_flujo      INTEGER NOT NULL,
    salud_flujo      TEXT NOT NULL,
    prioridad        TEXT NOT NULL,
    accion_sugerida  TEXT,
    hallazgos        TEXT,
    creado_en        TEXT DEFAULT CURRENT_TIMESTAMP,
    actualizado_en   TEXT,
    UNIQUE(id_oportunidad, fecha_snapshot),
    FOREIGN KEY (id_oportunidad) REFERENCES oportunidades(id_oportunidad)
);

-- ================================================================
--  CONFIGURACIÓN CFDI (Facturación electrónica SAT)
-- ================================================================

CREATE TABLE IF NOT EXISTS config_cfdi_emisor (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    rfc_emisor           TEXT NOT NULL UNIQUE,
    razon_social         TEXT,
    regimen_fiscal       TEXT,
    token_api            TEXT NOT NULL,
    modo                 TEXT NOT NULL CHECK(modo IN ('pruebas', 'produccion')),
    fecha_registro       TEXT NOT NULL,
    fecha_actualizacion  TEXT,
    activo               INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS config_cfdi_certificados (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_emisor              INTEGER NOT NULL,
    cer_base64             TEXT NOT NULL,
    key_base64             TEXT NOT NULL,
    numero_certificado     TEXT,
    fecha_inicio_vigencia  TEXT,
    fecha_fin_vigencia     TEXT,
    fecha_carga            TEXT NOT NULL,
    activo                 INTEGER DEFAULT 1,
    FOREIGN KEY (id_emisor) REFERENCES config_cfdi_emisor(id)
);

-- ================================================================
--  EXTENSIBILIDAD PARAMÉTRICA (Atributos Dinámicos)
-- ================================================================

CREATE TABLE IF NOT EXISTS atributos_entidad (
    id_attr        INTEGER PRIMARY KEY AUTOINCREMENT,
    entidad        TEXT NOT NULL,
    id_entidad     INTEGER NOT NULL,
    nombre_attr    TEXT NOT NULL,
    valor_attr     TEXT,
    tipo_dato      TEXT DEFAULT 'text',
    fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ================================================================
--  ÍNDICES PARA RENDIMIENTO
-- ================================================================

-- Identidad
CREATE INDEX IF NOT EXISTS idx_contactos_empresa  ON contactos(id_empresa);
CREATE INDEX IF NOT EXISTS idx_prospectos_empresa ON prospectos(id_empresa);

-- Transacción
CREATE INDEX IF NOT EXISTS idx_oportunidades_prospecto    ON oportunidades(id_prospecto);
CREATE INDEX IF NOT EXISTS idx_cotizaciones_oportunidad   ON cotizaciones(id_oportunidad);
CREATE INDEX IF NOT EXISTS idx_cotizaciones_externas_cot  ON cotizaciones_externas(id_cotizacion);

-- Facturación
CREATE INDEX IF NOT EXISTS idx_ordenes_oportunidad ON ordenes_compra(id_oportunidad);
CREATE INDEX IF NOT EXISTS idx_facturas_oc         ON facturas(id_oc);
CREATE INDEX IF NOT EXISTS idx_pagos_factura       ON pagos(id_factura);

-- Trazabilidad
CREATE INDEX IF NOT EXISTS idx_historial_entidad           ON historial_general(entidad, id_entidad);
CREATE INDEX IF NOT EXISTS idx_hash_origen                 ON hash_registros(tabla_origen, id_registro);
CREATE INDEX IF NOT EXISTS idx_helper_snapshot_oportunidad ON pipeline_helper_oportunidad_snapshots(id_oportunidad, fecha_snapshot);

-- Extensibilidad
CREATE INDEX IF NOT EXISTS idx_atributos_entidad ON atributos_entidad(entidad, id_entidad);

-- ================================================================
--  ÍNDICES ÚNICOS (integridad de negocio)
-- ================================================================

-- RFC único por empresa (índice parcial: ignora NULL y cadena vacía)
CREATE UNIQUE INDEX IF NOT EXISTS idx_empresas_rfc_unique
    ON empresas(rfc) WHERE rfc IS NOT NULL AND rfc != '';

-- UUID único por factura CFDI (un UUID no puede reutilizarse)
CREATE UNIQUE INDEX IF NOT EXISTS idx_facturas_uuid_unique
    ON facturas(uuid) WHERE uuid IS NOT NULL AND uuid != '';
