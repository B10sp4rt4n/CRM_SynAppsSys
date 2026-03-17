# -*- coding: utf-8 -*-
"""
SQL Helpers - Adaptación entre SQLite y PostgreSQL
Funciones helper para construcción de queries compatibles con ambos motores
"""

from typing import Dict, Any, Tuple, List, Optional
from .db_config import get_db_config


class SQLBuilder:
    """
    Constructor de queries SQL adaptativas
    
    Genera SQL compatible con SQLite y PostgreSQL automáticamente
    según el motor configurado
    """
    
    def __init__(self):
        self.config = get_db_config()
    
    def build_insert(
        self,
        table: str,
        data: Dict[str, Any],
        return_id: bool = True
    ) -> Tuple[str, Tuple]:
        """
        Construye un INSERT adaptado al motor actual
        
        Args:
            table: Nombre de la tabla
            data: Diccionario con columnas y valores
            return_id: Si debe retornar el ID insertado (PostgreSQL usa RETURNING)
            
        Returns:
            (query, params) listo para execute()
            
        Ejemplos:
            >>> builder = SQLBuilder()
            >>> query, params = builder.build_insert('empresas', {'nombre': 'Test', 'rfc': 'XXX'})
            >>> # PostgreSQL: INSERT INTO empresas (nombre, rfc) VALUES (%s, %s) RETURNING id_empresa
            >>> # SQLite: INSERT INTO empresas (nombre, rfc) VALUES (?, ?)
        """
        columns = list(data.keys())
        values = tuple(data.values())
        
        placeholder = self.config.get_placeholder_char()
        placeholders = ", ".join([placeholder] * len(columns))
        columns_str = ", ".join(columns)
        
        query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
        
        # PostgreSQL: agregar RETURNING
        if return_id and self.config.is_postgres:
            # Detectar columna ID (convencion: id_{tabla} o id)
            id_column = f"id_{table.rstrip('s')}" if not table.endswith('s') else f"id_{table[:-1]}"
            
            # Casos especiales
            special_ids = {
                'empresas': 'id_empresa',
                'contactos': 'id_contacto',
                'prospectos': 'id_prospecto',
                'oportunidades': 'id_oportunidad',
                'cotizaciones': 'id_cotizacion',
                'ordenes_compra': 'id_oc',
                'facturas': 'id_factura',
                'historial_general': 'id_evento',
                'hash_registros': 'id_hash'
            }
            
            id_column = special_ids.get(table, 'id')
            query += f" RETURNING {id_column}"
        
        return query, values
    
    def build_update(
        self,
        table: str,
        data: Dict[str, Any],
        where_clause: str,
        where_params: Tuple = ()
    ) -> Tuple[str, Tuple]:
        """
        Construye un UPDATE adaptado al motor actual
        
        Args:
            table: Nombre de la tabla
            data: Diccionario con columnas a actualizar
            where_clause: Condición WHERE (sin la keyword WHERE)
            where_params: Parámetros del WHERE
            
        Returns:
            (query, params) listo para execute()
            
        Ejemplos:
            >>> builder = SQLBuilder()
            >>> query, params = builder.build_update(
            ...     'empresas',
            ...     {'nombre': 'Nuevo'},
            ...     'id_empresa = ?',
            ...     (1,)
            ... )
        """
        placeholder = self.config.get_placeholder_char()
        
        set_parts = [f"{col} = {placeholder}" for col in data.keys()]
        set_clause = ", ".join(set_parts)
        
        # Adaptar WHERE clause
        adapted_where = where_clause.replace('?', placeholder)
        
        query = f"UPDATE {table} SET {set_clause} WHERE {adapted_where}"
        params = tuple(data.values()) + where_params
        
        return query, params
    
    def build_select(
        self,
        table: str,
        columns: List[str] = None,
        where_clause: str = None,
        where_params: Tuple = (),
        order_by: str = None,
        limit: int = None
    ) -> Tuple[str, Tuple]:
        """
        Construye un SELECT adaptado al motor actual
        
        Args:
            table: Nombre de la tabla
            columns: Lista de columnas (None = *)
            where_clause: Condición WHERE (sin la keyword)
            where_params: Parámetros del WHERE
            order_by: Columnas para ORDER BY
            limit: Número de registros máximo
            
        Returns:
            (query, params)
        """
        placeholder = self.config.get_placeholder_char()
        
        cols = "*" if not columns else ", ".join(columns)
        query = f"SELECT {cols} FROM {table}"
        
        if where_clause:
            adapted_where = where_clause.replace('?', placeholder)
            query += f" WHERE {adapted_where}"
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        return query, where_params
    
    def get_current_timestamp(self) -> str:
        """
        Retorna la expresión SQL para timestamp actual
        
        Returns:
            'NOW()' para PostgreSQL, 'CURRENT_TIMESTAMP' para SQLite
        """
        return self.config.get_datetime_function()
    
    def adapt_query(self, query: str) -> str:
        """
        Adapta una query manualmente escrita
        
        Convierte ? a %s si es PostgreSQL
        
        Args:
            query: Query con placeholders ?
            
        Returns:
            Query adaptada
        """
        return self.config.adapt_query(query)


# Instancia global
_sql_builder: Optional[SQLBuilder] = None


def get_sql_builder() -> SQLBuilder:
    """
    Retorna instancia singleton del SQL Builder
    
    Returns:
        SQLBuilder configurado
    """
    global _sql_builder
    if _sql_builder is None:
        _sql_builder = SQLBuilder()
    return _sql_builder


def insert_returning_id(
    db_connection,
    table: str,
    data: Dict[str, Any]
) -> int:
    """
    Helper para INSERT que retorna el ID insertado
    Compatible con SQLite y PostgreSQL
    
    Args:
        db_connection: Conexión de DatabaseV2
        table: Nombre de la tabla
        data: Datos a insertar
        
    Returns:
        ID del registro insertado
        
    Ejemplos:
        >>> from .database import get_db
        >>> db = get_db()
        >>> new_id = insert_returning_id(db, 'empresas', {'nombre': 'Test Inc'})
        >>> print(new_id)
        42
    """
    builder = get_sql_builder()
    query, params = builder.build_insert(table, data, return_id=True)
    
    cursor = db_connection.execute(query, params)
    
    if db_connection.is_postgres:
        # PostgreSQL usa RETURNING
        row = cursor.fetchone()
        if row:
            # Detectar la columna ID
            for key in row.keys():
                if 'id' in key.lower():
                    return row[key]
        return None
    else:
        # SQLite usa lastrowid
        return cursor.lastrowid


def update_by_id(
    db_connection,
    table: str,
    record_id: int,
    data: Dict[str, Any],
    id_column: str = None
) -> bool:
    """
    Helper para UPDATE por ID
    
    Args:
        db_connection: Conexión de DatabaseV2
        table: Nombre de la tabla
        record_id: ID del registro
        data: Datos a actualizar
        id_column: Nombre de la columna ID (auto-detectado si None)
        
    Returns:
        True si se actualizó al menos un registro
    """
    if id_column is None:
        # Auto-detectar columna ID
        special_ids = {
            'empresas': 'id_empresa',
            'contactos': 'id_contacto',
            'prospectos': 'id_prospecto',
            'oportunidades': 'id_oportunidad',
            'cotizaciones': 'id_cotizacion',
            'ordenes_compra': 'id_oc',
            'facturas': 'id_factura'
        }
        id_column = special_ids.get(table, 'id')
    
    builder = get_sql_builder()
    query, params = builder.build_update(
        table,
        data,
        f"{id_column} = ?",
        (record_id,)
    )
    
    cursor = db_connection.execute(query, params)
    
    if db_connection.is_postgres:
        return cursor.rowcount > 0
    else:
        return cursor.rowcount > 0
