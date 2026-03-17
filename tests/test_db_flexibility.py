# -*- coding: utf-8 -*-
"""
Tests para configuración flexible de base de datos
Verifica que el sistema se adapta correctamente entre SQLite y PostgreSQL
"""

import pytest
import os
from pathlib import Path

from crm_exo_v2.core.db_config import DBConfig, DBEngine, get_db_config, reset_db_config
from crm_exo_v2.core.database import DatabaseV2, get_db
from crm_exo_v2.core.sql_helpers import SQLBuilder, get_sql_builder


class TestDBConfig:
    """Tests para DBConfig"""
    
    def test_sqlite_default(self):
        """SQLite se usa por defecto sin DATABASE_URL"""
        # Asegurar que DATABASE_URL no existe
        old_url = os.environ.get('DATABASE_URL')
        if 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']
        
        reset_db_config()
        config = get_db_config()
        
        assert config.is_sqlite
        assert not config.is_postgres
        assert config.engine == DBEngine.SQLITE
        assert '.sqlite' in config.connection_string
        
        # Restaurar
        if old_url:
            os.environ['DATABASE_URL'] = old_url
        reset_db_config()
    
    def test_postgres_from_env(self):
        """PostgreSQL se detecta desde DATABASE_URL"""
        os.environ['DATABASE_URL'] = 'postgresql://user:pass@localhost/test'
        reset_db_config()
        
        config = get_db_config()
        
        assert config.is_postgres
        assert not config.is_sqlite
        assert config.engine == DBEngine.POSTGRESQL
        assert 'postgresql://' in config.connection_string
        
        # Limpiar
        del os.environ['DATABASE_URL']
        reset_db_config()
    
    def test_placeholder_char(self):
        """Placeholders se adaptan según motor"""
        # SQLite
        os.environ.pop('DATABASE_URL', None)
        reset_db_config()
        config_sqlite = get_db_config()
        assert config_sqlite.get_placeholder_char() == '?'
        
        # PostgreSQL
        os.environ['DATABASE_URL'] = 'postgresql://localhost/test'
        reset_db_config()
        config_pg = get_db_config()
        assert config_pg.get_placeholder_char() == '%s'
        
        # Limpiar
        os.environ.pop('DATABASE_URL', None)
        reset_db_config()
    
    def test_adapt_query(self):
        """Queries se adaptan automáticamente"""
        os.environ['DATABASE_URL'] = 'postgresql://localhost/test'
        reset_db_config()
        config = get_db_config()
        
        query_sqlite = "SELECT * FROM tabla WHERE id = ?"
        query_pg = config.adapt_query(query_sqlite)
        
        assert '%s' in query_pg
        assert '?' not in query_pg
        
        # Limpiar
        del os.environ['DATABASE_URL']
        reset_db_config()


class TestSQLBuilder:
    """Tests para SQLBuilder"""
    
    def test_build_insert_sqlite(self):
        """INSERT en formato SQLite"""
        os.environ.pop('DATABASE_URL', None)
        reset_db_config()
        
        builder = SQLBuilder()
        query, params = builder.build_insert('empresas', {
            'nombre': 'Test',
            'rfc': 'XXX'
        })
        
        assert 'INSERT INTO empresas' in query
        assert '?' in query
        assert params == ('Test', 'XXX')
        
        reset_db_config()
    
    def test_build_insert_postgres(self):
        """INSERT en formato PostgreSQL con RETURNING"""
        os.environ['DATABASE_URL'] = 'postgresql://localhost/test'
        reset_db_config()
        
        builder = SQLBuilder()
        query, params = builder.build_insert('empresas', {
            'nombre': 'Test',
            'rfc': 'XXX'
        }, return_id=True)
        
        assert 'INSERT INTO empresas' in query
        assert '%s' in query
        assert 'RETURNING id_empresa' in query
        assert params == ('Test', 'XXX')
        
        # Limpiar
        del os.environ['DATABASE_URL']
        reset_db_config()
    
    def test_build_update(self):
        """UPDATE se construye correctamente"""
        builder = SQLBuilder()
        query, params = builder.build_update(
            'empresas',
            {'nombre': 'Nuevo'},
            'id_empresa = ?',
            (1,)
        )
        
        assert 'UPDATE empresas SET' in query
        assert 'WHERE' in query
        assert params == ('Nuevo', 1)
    
    def test_build_select(self):
        """SELECT se construye correctamente"""
        builder = SQLBuilder()
        query, params = builder.build_select(
            'empresas',
            columns=['nombre', 'rfc'],
            where_clause='sector = ?',
            where_params=('Tech',),
            order_by='nombre',
            limit=10
        )
        
        assert 'SELECT nombre, rfc FROM empresas' in query
        assert 'WHERE' in query
        assert 'ORDER BY nombre' in query
        assert 'LIMIT 10' in query
        assert params == ('Tech',)


class TestDatabaseV2Flexibility:
    """Tests de integración para DatabaseV2"""
    
    def test_database_detects_sqlite(self):
        """DatabaseV2 detecta SQLite por defecto"""
        os.environ.pop('DATABASE_URL', None)
        reset_db_config()
        
        # Resetear singleton
        DatabaseV2._instance = None
        DatabaseV2._connection = None
        DatabaseV2._config = None
        
        db = get_db()
        
        assert db.is_sqlite
        assert not db.is_postgres
        assert db.engine_name == 'sqlite'
        
        db.close()
        reset_db_config()
    
    def test_adapt_query_execution(self):
        """Query con ? se adapta automáticamente"""
        os.environ.pop('DATABASE_URL', None)
        reset_db_config()
        
        DatabaseV2._instance = None
        DatabaseV2._connection = None
        DatabaseV2._config = None
        
        db = get_db()
        
        # Esta query usa ? (formato SQLite)
        # Debe funcionar independientemente del motor
        cursor = db.execute(
            "SELECT 1 as test WHERE 1 = ?",
            (1,)
        )
        
        row = cursor.fetchone()
        assert row is not None
        
        db.close()
        reset_db_config()


def test_integration_example():
    """Test de integración completo"""
    # Asegurar SQLite
    os.environ.pop('DATABASE_URL', None)
    reset_db_config()
    
    DatabaseV2._instance = None
    DatabaseV2._connection = None
    DatabaseV2._config = None
    
    db = get_db()
    
    # Este código debe funcionar igual en ambos motores
    try:
        # Verificar que podemos ejecutar queries
        cursor = db.execute("SELECT 'flexible' as test")
        row = cursor.fetchone()
        
        assert row is not None
        assert row['test'] == 'flexible'
        
        print(f"✅ Test exitoso con motor: {db.engine_name}")
        
    finally:
        db.close()
        reset_db_config()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
