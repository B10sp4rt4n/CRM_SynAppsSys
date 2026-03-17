# -*- coding: utf-8 -*-
"""
Configuración flexible de Base de Datos - SQLite/PostgreSQL
Detecta automáticamente qué motor usar y proporciona conexiones adaptadas
"""

import os
from enum import Enum
from typing import Optional, Any, Dict
from pathlib import Path

try:
    import streamlit as st
except ImportError:
    st = None


class DBEngine(Enum):
    """Motores de base de datos soportados"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class DBConfig:
    """
    Configuración centralizada de base de datos
    
    Detecta automáticamente qué motor usar:
    1. PostgreSQL si DATABASE_URL está configurado
    2. SQLite como fallback
    
    Ejemplos:
        >>> config = DBConfig.from_environment()
        >>> print(config.engine)
        DBEngine.POSTGRESQL
        >>> print(config.is_postgres)
        True
    """
    
    def __init__(
        self,
        engine: DBEngine,
        connection_string: str,
        **kwargs
    ):
        self.engine = engine
        self.connection_string = connection_string
        self.options = kwargs
    
    @property
    def is_sqlite(self) -> bool:
        """True si el motor es SQLite"""
        return self.engine == DBEngine.SQLITE
    
    @property
    def is_postgres(self) -> bool:
        """True si el motor es PostgreSQL"""
        return self.engine == DBEngine.POSTGRESQL
    
    @classmethod
    def from_environment(cls, base_dir: Optional[Path] = None) -> 'DBConfig':
        """
        Crea configuración detectando automáticamente el entorno
        
        Prioridad:
        1. DATABASE_URL en variables de entorno
        2. DATABASE_URL en Streamlit secrets
        3. SQLite local (fallback)
        
        Args:
            base_dir: Directorio base del proyecto (para SQLite)
            
        Returns:
            DBConfig configurado según el entorno
        """
        # Intentar obtener DATABASE_URL
        database_url = cls._get_database_url()
        
        if database_url and database_url.startswith('postgresql'):
            return cls(
                engine=DBEngine.POSTGRESQL,
                connection_string=database_url,
                autocommit=False,
                pool_size=5
            )
        
        # Fallback a SQLite
        if base_dir is None:
            base_dir = Path(__file__).resolve().parents[2]
        
        sqlite_path = base_dir / "crm_exo_v2" / "data" / "crm_exo_v2.sqlite"
        
        return cls(
            engine=DBEngine.SQLITE,
            connection_string=str(sqlite_path),
            check_same_thread=False,
            timeout=30.0
        )
    
    @staticmethod
    def _get_database_url() -> Optional[str]:
        """Obtiene DATABASE_URL del entorno o Streamlit secrets"""
        # 1. Variable de entorno
        env_url = os.getenv("DATABASE_URL")
        if env_url:
            return env_url
        
        # 2. Streamlit secrets
        if st is not None:
            try:
                secret_url = st.secrets.get("DATABASE_URL")
                if secret_url:
                    return str(secret_url)
            except Exception:
                pass
        
        return None
    
    def get_placeholder_char(self) -> str:
        """
        Retorna el carácter de placeholder para queries parametrizadas
        
        SQLite: ?
        PostgreSQL: %s
        """
        if self.is_postgres:
            return "%s"
        return "?"
    
    def get_autoincrement_keyword(self) -> str:
        """
        Retorna la keyword para autoincremento
        
        SQLite: AUTOINCREMENT
        PostgreSQL: SERIAL o GENERATED ALWAYS AS IDENTITY
        """
        if self.is_postgres:
            return "SERIAL"
        return "AUTOINCREMENT"
    
    def get_datetime_function(self) -> str:
        """
        Retorna la función para obtener timestamp actual
        
        SQLite: CURRENT_TIMESTAMP
        PostgreSQL: NOW()
        """
        if self.is_postgres:
            return "NOW()"
        return "CURRENT_TIMESTAMP"
    
    def get_last_insert_id_query(self) -> Optional[str]:
        """
        Retorna la query para obtener el último ID insertado
        
        SQLite: usa lastrowid (no necesita query)
        PostgreSQL: RETURNING id
        """
        if self.is_postgres:
            return "RETURNING id"
        return None
    
    def adapt_query(self, query: str) -> str:
        """
        Adapta una query de SQLite a PostgreSQL si es necesario
        
        Conversiones:
        - AUTOINCREMENT → SERIAL
        - ? → %s
        - CURRENT_TIMESTAMP (si se necesita ajustar)
        
        Args:
            query: Query en formato SQLite
            
        Returns:
            Query adaptada al motor actual
        """
        if not self.is_postgres:
            return query
        
        # Convertir placeholders
        adapted = query.replace("?", "%s")
        
        # Convertir AUTOINCREMENT a SERIAL
        adapted = adapted.replace("AUTOINCREMENT", "SERIAL PRIMARY KEY")
        adapted = adapted.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        
        return adapted
    
    def __repr__(self) -> str:
        return f"DBConfig(engine={self.engine.value}, connection={self.connection_string[:50]}...)"


# Instancia global (singleton lazy)
_global_config: Optional[DBConfig] = None


def get_db_config(base_dir: Optional[Path] = None) -> DBConfig:
    """
    Obtiene la configuración global de base de datos
    
    Usa patrón singleton para reutilizar la misma configuración
    
    Args:
        base_dir: Directorio base (solo usado en primera llamada)
        
    Returns:
        DBConfig configurado
        
    Ejemplos:
        >>> config = get_db_config()
        >>> if config.is_postgres:
        ...     print("Usando PostgreSQL")
        ... else:
        ...     print("Usando SQLite")
    """
    global _global_config
    
    if _global_config is None:
        _global_config = DBConfig.from_environment(base_dir)
    
    return _global_config


def reset_db_config():
    """Resetea la configuración global (útil para testing)"""
    global _global_config
    _global_config = None
