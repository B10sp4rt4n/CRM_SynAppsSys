"""
Configuración de fixtures para pytest - CRM-EXO v2
Autor: AUP
Fecha: 2025-11-10
Descripción: Fixtures compartidos para testing con base de datos temporal
"""

import pytest
import sqlite3
from pathlib import Path


@pytest.fixture
def db_connection(tmp_path):
    """
    Crea una base de datos SQLite temporal en memoria o disco para testing.
    Se destruye automáticamente al finalizar el test.
    """
    db_path = tmp_path / "test_crm.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Crear esquema completo - Compatible con arquitectura AUP (tabla aup_agentes)
    schema_sql = """
    -- Tabla unificada AUP para agentes
    CREATE TABLE aup_agentes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL,
        nombre TEXT NOT NULL,
        atributos TEXT,
        activo INTEGER DEFAULT 1,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- NÚCLEO 1: IDENTIDAD (manteniendo tablas legacy para compatibilidad)
    CREATE TABLE empresas (
        id_empresa INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        rfc TEXT,
        sector TEXT,
        direccion TEXT,
        telefono TEXT,
        correo TEXT,
        fecha_alta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        tipo_cliente TEXT DEFAULT 'cliente' CHECK(tipo_cliente IN ('cliente', 'prospecto'))
    );

    CREATE TABLE contactos (
        id_contacto INTEGER PRIMARY KEY AUTOINCREMENT,
        id_empresa INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        correo TEXT UNIQUE NOT NULL,
        telefono TEXT,
        puesto TEXT,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id_empresa) REFERENCES empresas(id_empresa)
    );

    CREATE TABLE prospectos (
        id_prospecto INTEGER PRIMARY KEY AUTOINCREMENT,
        id_empresa INTEGER NOT NULL UNIQUE,
        id_contacto INTEGER,
        fuente TEXT,
        estado TEXT DEFAULT 'nuevo' CHECK(estado IN ('nuevo', 'contactado', 'calificado', 'convertido')),
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id_empresa) REFERENCES empresas(id_empresa),
        FOREIGN KEY (id_contacto) REFERENCES contactos(id_contacto)
    );

    -- NÚCLEO 2: TRANSACCIÓN
    CREATE TABLE oportunidades (
        id_oportunidad INTEGER PRIMARY KEY AUTOINCREMENT,
        id_prospecto INTEGER,
        id_cliente INTEGER,
        titulo TEXT NOT NULL,
        descripcion TEXT,
        monto REAL,
        probabilidad INTEGER DEFAULT 50,
        etapa TEXT DEFAULT 'calificacion',
        estado TEXT DEFAULT 'abierta' CHECK(estado IN ('abierta', 'ganada', 'perdida', 'cerrada')),
        fecha_cierre_esperada DATE,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id_prospecto) REFERENCES prospectos(id_prospecto),
        FOREIGN KEY (id_cliente) REFERENCES empresas(id_empresa)
    );

    CREATE TABLE cotizaciones (
        id_cotizacion INTEGER PRIMARY KEY AUTOINCREMENT,
        id_oportunidad INTEGER NOT NULL,
        numero_cotizacion TEXT UNIQUE,
        monto_total REAL NOT NULL,
        fecha_emision TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_vigencia DATE,
        estado TEXT DEFAULT 'borrador' CHECK(estado IN ('borrador', 'enviada', 'aceptada', 'rechazada')),
        modo TEXT DEFAULT 'minimo' CHECK(modo IN ('minimo', 'generico', 'externo')),
        fuente TEXT DEFAULT 'manual',
        hash_cotizacion TEXT,
        FOREIGN KEY (id_oportunidad) REFERENCES oportunidades(id_oportunidad)
    );

    -- NÚCLEO 3: FACTURACIÓN
    CREATE TABLE ordenes_compra (
        id_oc INTEGER PRIMARY KEY AUTOINCREMENT,
        id_oportunidad INTEGER NOT NULL,
        numero_oc TEXT UNIQUE NOT NULL,
        monto_oc REAL NOT NULL,
        fecha_emision TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        estado TEXT DEFAULT 'pendiente' CHECK(estado IN ('pendiente', 'facturada', 'cancelada')),
        hash_oc TEXT,
        FOREIGN KEY (id_oportunidad) REFERENCES oportunidades(id_oportunidad)
    );

    CREATE TABLE facturas (
        id_factura INTEGER PRIMARY KEY AUTOINCREMENT,
        id_oc INTEGER NOT NULL,
        uuid TEXT UNIQUE NOT NULL,
        serie TEXT,
        folio TEXT,
        fecha_emision TIMESTAMP NOT NULL,
        monto_total REAL NOT NULL,
        estado TEXT DEFAULT 'activa' CHECK(estado IN ('activa', 'cancelada', 'pagada')),
        hash_factura TEXT,
        FOREIGN KEY (id_oc) REFERENCES ordenes_compra(id_oc)
    );

    -- NÚCLEO 4: TRAZABILIDAD
    CREATE TABLE historial_general (
        id_evento INTEGER PRIMARY KEY AUTOINCREMENT,
        entidad TEXT NOT NULL,
        id_entidad INTEGER NOT NULL,
        accion TEXT NOT NULL,
        usuario TEXT DEFAULT 'sistema',
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        datos_antes TEXT,
        datos_despues TEXT,
        metadatos TEXT,
        hash_evento TEXT
    );

    CREATE TABLE hash_registros (
        id_hash INTEGER PRIMARY KEY AUTOINCREMENT,
        entidad TEXT NOT NULL,
        id_entidad INTEGER NOT NULL,
        hash_sha256 TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadatos TEXT
    );

    -- Tabla de atributos dinámicos
    CREATE TABLE atributos_entidad (
        id_atributo INTEGER PRIMARY KEY AUTOINCREMENT,
        entidad TEXT NOT NULL,
        id_entidad INTEGER NOT NULL,
        clave TEXT NOT NULL,
        valor TEXT,
        tipo TEXT DEFAULT 'texto',
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    conn.executescript(schema_sql)
    conn.commit()
    
    yield conn
    
    conn.close()


@pytest.fixture
def repos(db_connection):
    """
    Inicializa todos los repositorios con la conexión de base de datos temporal.
    Usa inyección de dependencias para aislar los tests.
    """
    import sys
    from pathlib import Path
    
    # Agregar path del proyecto al sys.path
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # Importar desde las ubicaciones correctas
    from crm_exo_v2.core.repositories.empresa_repository import EmpresaRepository
    from crm_exo_v2.core.repositories.contacto_repository import ContactoRepository
    from crm_exo_v2.core.repository_prospecto import ProspectoRepository
    from crm_exo_v2.core.repository_oportunidad import OportunidadRepository
    from crm_exo_v2.core.repository_cotizacion import CotizadorRepository
    from crm_exo_v2.core.repository_facturacion import OrdenCompraRepository, FacturaRepository
    from crm_exo_v2.core.repository_trazabilidad import HistorialGeneralRepository, HashRepository
    
    # Crear instancias con conexión inyectada
    return {
        "empresa": EmpresaRepository(usuario="test", conn=db_connection),
        "contacto": ContactoRepository(usuario="test", conn=db_connection),
        "prospecto": ProspectoRepository(usuario="test", conn=db_connection),
        "oportunidad": OportunidadRepository(usuario="test", conn=db_connection),
        "cotizacion": CotizadorRepository(usuario="test", conn=db_connection),
        "oc": OrdenCompraRepository(usuario="test", conn=db_connection),
        "factura": FacturaRepository(usuario="test", conn=db_connection),
        "historial": HistorialGeneralRepository(conn=db_connection),
        "hash": HashRepository(conn=db_connection)
    }
