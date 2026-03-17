# -*- coding: utf-8 -*-
"""
Conector de Base de Datos Flexible - AUP-EXO v2
Soporte para SQLite y PostgreSQL con auto-detección
Gestión centralizada con patrón Singleton adaptable
"""

import sqlite3
from pathlib import Path
from typing import Optional, Any, Union, Tuple, List
from contextlib import contextmanager

try:
    from .db_config import get_db_config, DBEngine
except ImportError:
    from db_config import get_db_config, DBEngine

# Importaciones opcionales
try:
    import psycopg
    from psycopg.rows import dict_row
    PSYCOPG_AVAILABLE = True
except ImportError:
    psycopg = None
    dict_row = None
    PSYCOPG_AVAILABLE = False


class DatabaseV2:
    """
    Singleton para conexión flexible a SQLite o PostgreSQL
    
    Características:
    - Auto-detección de motor de BD (PostgreSQL si DATABASE_URL existe, sino SQLite)
    - Conexión única por aplicación (Singleton)
    - Row factory para acceso por nombre de columna
    - Foreign keys habilitadas (SQLite)
    - API unificada independiente del motor
    - Manejo automático de diferencias SQL
    
    Ejemplos:
        >>> db = DatabaseV2()
        >>> print(db.engine_name)
        'postgresql'
        >>> cursor = db.execute("SELECT * FROM empresas WHERE id = %s", (1,))
        >>> row = cursor.fetchone()
    """
    
    _instance: Optional['DatabaseV2'] = None
    _connection: Optional[Union[sqlite3.Connection, Any]] = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._connection is None:
            self._config = get_db_config()
            self._connect()
    
    def _connect(self):
        """Establece conexión según el motor configurado"""
        if self._config.is_postgres:
            self._connect_postgres()
        else:
            self._connect_sqlite()
    
    def _connect_sqlite(self):
        """Establece conexión con SQLite"""
        self._connection = sqlite3.connect(
            self._config.connection_string,
            check_same_thread=self._config.options.get('check_same_thread', False),
            timeout=self._config.options.get('timeout', 30.0)
        )
        
        # Habilitar acceso por nombre de columna
        self._connection.row_factory = sqlite3.Row
        
        # Habilitar foreign keys
        self._connection.execute("PRAGMA foreign_keys = ON")
    
    def _connect_postgres(self):
        """Establece conexión con PostgreSQL"""
        if not PSYCOPG_AVAILABLE:
            raise ImportError(
                "psycopg no está instalado. "
                "Instálalo con: pip install 'psycopg[binary]>=3.3.3'"
            )
        
        self._connection = psycopg.connect(
            self._config.connection_string,
            autocommit=self._config.options.get('autocommit', False),
            row_factory=dict_row
        )
    
    @property
    def connection(self) -> Union[sqlite3.Connection, Any]:
        """Retorna la conexión activa"""
        if self._connection is None:
            self._connect()
        return self._connection
    
    @property
    def engine_name(self) -> str:
        """Retorna el nombre del motor actual"""
        return self._config.engine.value
    
    @property
    def is_postgres(self) -> bool:
        """True si el motor actual es PostgreSQL"""
        return self._config.is_postgres
    
    @property
    def is_sqlite(self) -> bool:
        """True si el motor actual es SQLite"""
        return self._config.is_sqlite
    
    def execute(self, query: str, params: Union[Tuple, List] = ()):
        """
        Ejecuta una consulta adaptándola al motor actual
        
        Args:
            query: Query SQL (puede usar ? para placeholders)
            params: Parámetros de la query
            
        Returns:
            Cursor con los resultados
            
        Nota:
            Las queries con ? se convierten automáticamente a %s en PostgreSQL
        """
        adapted_query = self._config.adapt_query(query)
        
        if self.is_postgres:
            cursor = self.connection.cursor()
            cursor.execute(adapted_query, params)
            return cursor
        else:
            return self.connection.execute(adapted_query, params)
    
    def executemany(self, query: str, params_list: List[Tuple]):
        """
        Ejecuta múltiples inserts/updates en batch
        
        Args:
            query: Query SQL
            params_list: Lista de tuplas con parámetros
        """
        adapted_query = self._config.adapt_query(query)
        
        if self.is_postgres:
            with self.connection.cursor() as cursor:
                cursor.executemany(adapted_query, params_list)
        else:
            self.connection.executemany(adapted_query, params_list)
    
    def commit(self):
        """Confirma transacción"""
        self.connection.commit()
    
    def rollback(self):
        """Revierte transacción"""
        self.connection.rollback()
    
    @contextmanager
    def transaction(self):
        """
        Context manager para transacciones
        
        Ejemplos:
            >>> db = DatabaseV2()
            >>> with db.transaction():
            ...     db.execute("INSERT INTO empresas (nombre) VALUES (?)", ("Test",))
            ...     # Auto-commit al salir del contexto
        """
        try:
            yield self
            self.commit()
        except Exception:
            self.rollback()
            raise
    
    def get_last_insert_id(self, cursor=None) -> Optional[int]:
        """
        Obtiene el ID del último registro insertado
        
        Args:
            cursor: Cursor de PostgreSQL (ignorado en SQLite)
            
        Returns:
            ID del último insert
        """
        if self.is_postgres:
            if cursor and hasattr(cursor, 'fetchone'):
                row = cursor.fetchone()
                if row and isinstance(row, dict):
                    # Buscar la primera columna que termine en 'id'
                    for key in row.keys():
                        if key.endswith('_id') or key == 'id':
                            return row[key]
                return None
            return None
        else:
            return self.connection.cursor().lastrowid
    
    def close(self):
        """Cierra la conexión"""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    def __repr__(self) -> str:
        return f"DatabaseV2(engine={self.engine_name}, connected={self._connection is not None})"


def get_db() -> DatabaseV2:
    """
    Factory function para obtener instancia de DB
    
    Returns:
        Instancia singleton de DatabaseV2
        
    Ejemplos:
        >>> db = get_db()
        >>> print(f"Usando {db.engine_name}")
        Usando postgresql
    """
    return DatabaseV2()
