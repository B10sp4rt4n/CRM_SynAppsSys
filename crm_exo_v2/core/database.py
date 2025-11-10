# -*- coding: utf-8 -*-
"""
Conector de Base de Datos - AUP-EXO v2
Gestión centralizada de conexión SQLite con patrón Singleton
"""

import sqlite3
from pathlib import Path
from typing import Optional


class DatabaseV2:
    """
    Singleton para conexión a crm_exo_v2.sqlite
    
    Características:
    - Conexión única por aplicación
    - Row factory para acceso por nombre de columna
    - Foreign keys habilitadas
    - Rutas absolutas desde proyecto
    """
    
    _instance: Optional['DatabaseV2'] = None
    _connection: Optional[sqlite3.Connection] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._connection is None:
            self._connect()
    
    def _connect(self):
        """Establece conexión con la base de datos"""
        db_path = Path(__file__).parent.parent / "data" / "crm_exo_v2.sqlite"
        
        self._connection = sqlite3.connect(
            str(db_path),
            check_same_thread=False  # Permitir uso en Streamlit
        )
        
        # Habilitar acceso por nombre de columna
        self._connection.row_factory = sqlite3.Row
        
        # Habilitar foreign keys
        self._connection.execute("PRAGMA foreign_keys = ON")
    
    @property
    def connection(self) -> sqlite3.Connection:
        """Retorna la conexión activa"""
        if self._connection is None:
            self._connect()
        return self._connection
    
    def execute(self, query: str, params: tuple = ()):
        """Ejecuta una consulta directa"""
        return self.connection.execute(query, params)
    
    def commit(self):
        """Confirma transacción"""
        self.connection.commit()
    
    def rollback(self):
        """Revierte transacción"""
        self.connection.rollback()
    
    def close(self):
        """Cierra la conexión"""
        if self._connection:
            self._connection.close()
            self._connection = None


def get_db() -> DatabaseV2:
    """Factory function para obtener instancia de DB"""
    return DatabaseV2()
