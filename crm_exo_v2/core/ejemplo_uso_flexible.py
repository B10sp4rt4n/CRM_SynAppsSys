# -*- coding: utf-8 -*-
"""
Ejemplo de Uso: Código Flexible SQLite/PostgreSQL
Demuestra cómo escribir código que funciona en ambos motores sin modificaciones
"""

from crm_exo_v2.core.database import get_db
from crm_exo_v2.core.sql_helpers import insert_returning_id, update_by_id, get_sql_builder


def ejemplo_basico():
    """Ejemplo 1: Insert básico que funciona en ambos motores"""
    
    db = get_db()
    print(f"🔌 Conectado a: {db.engine_name}")
    
    # Insertar una empresa
    # Este código funciona IGUAL en SQLite y PostgreSQL
    empresa_data = {
        'nombre': 'Mi Empresa SA',
        'rfc': 'MEX010101XXX',
        'sector': 'Tecnología'
    }
    
    # Método 1: Usando helper (recomendado)
    new_id = insert_returning_id(db, 'empresas', empresa_data)
    print(f"✅ Empresa creada con ID: {new_id}")
    
    db.commit()


def ejemplo_query_parametrizada():
    """Ejemplo 2: Queries con placeholders adaptativos"""
    
    db = get_db()
    builder = get_sql_builder()
    
    # Construir SELECT adaptativo
    query, params = builder.build_select(
        table='empresas',
        columns=['id_empresa', 'nombre', 'rfc'],
        where_clause='sector = ?',
        where_params=('Tecnología',),
        order_by='nombre',
        limit=10
    )
    
    # En SQLite: SELECT ... WHERE sector = ? ...
    # En PostgreSQL: SELECT ... WHERE sector = %s ...
    cursor = db.execute(query, params)
    
    for row in cursor:
        print(f"📊 {row['nombre']} - {row['rfc']}")


def ejemplo_update():
    """Ejemplo 3: Update con helper"""
    
    db = get_db()
    
    # Actualizar registro
    actualizado = update_by_id(
        db,
        table='empresas',
        record_id=1,
        data={'nombre': 'Empresa Actualizada SA'},
        id_column='id_empresa'
    )
    
    if actualizado:
        print("✅ Empresa actualizada")
        db.commit()
    else:
        print("❌ No se encontró el registro")


def ejemplo_transaccion():
    """Ejemplo 4: Transacciones con context manager"""
    
    db = get_db()
    
    try:
        with db.transaction():
            # Insertar empresa
            empresa_id = insert_returning_id(db, 'empresas', {
                'nombre': 'Nueva Empresa',
                'rfc': 'NUE010101XXX'
            })
            
            # Insertar contacto
            contacto_id = insert_returning_id(db, 'contactos', {
                'id_empresa': empresa_id,
                'nombre': 'Juan Pérez',
                'correo': 'juan@empresa.com'
            })
            
            # Si todo OK, auto-commit al salir del contexto
            print(f"✅ Empresa {empresa_id} y contacto {contacto_id} creados")
            
    except Exception as e:
        # Auto-rollback en caso de error
        print(f"❌ Error: {e}")


def ejemplo_query_manual_adaptada():
    """Ejemplo 5: Query manual con adaptación automática"""
    
    db = get_db()
    builder = get_sql_builder()
    
    # Escribir query en formato SQLite (con ?)
    query_sqlite = """
        SELECT e.nombre, COUNT(c.id_contacto) as total_contactos
        FROM empresas e
        LEFT JOIN contactos c ON e.id_empresa = c.id_empresa
        WHERE e.sector = ?
        GROUP BY e.id_empresa, e.nombre
        ORDER BY total_contactos DESC
    """
    
    # Adaptar automáticamente
    query_adaptada = builder.adapt_query(query_sqlite)
    # PostgreSQL: ? → %s automáticamente
    
    cursor = db.execute(query_adaptada, ('Tecnología',))
    
    for row in cursor:
        print(f"🏢 {row['nombre']}: {row['total_contactos']} contactos")


def ejemplo_timestamp():
    """Ejemplo 6: Timestamps adaptativos"""
    
    db = get_db()
    builder = get_sql_builder()
    
    # Obtener función de timestamp actual según motor
    timestamp_func = builder.get_current_timestamp()
    
    # SQLite: CURRENT_TIMESTAMP
    # PostgreSQL: NOW()
    
    query = f"""
        INSERT INTO historial_general (entidad, accion, fecha)
        VALUES (?, ?, {timestamp_func})
    """
    
    adapted = builder.adapt_query(query)
    db.execute(adapted, ('empresas', 'ejemplo'))
    db.commit()
    
    print(f"✅ Timestamp insertado usando: {timestamp_func}")


def ejemplo_deteccion_motor():
    """Ejemplo 7: Lógica condicional según motor"""
    
    db = get_db()
    
    if db.is_postgres:
        print("🐘 Usando PostgreSQL - Optimizaciones avanzadas activadas")
        # Activar índices específicos, particionamiento, etc.
        
    elif db.is_sqlite:
        print("🗄️ Usando SQLite - Modo desarrollo activo")
        # Optimizaciones para SQLite (pragma, etc.)
    
    # El resto del código es idéntico


def main():
    """Ejecuta todos los ejemplos"""
    
    print("=" * 60)
    print("🔄 EJEMPLOS DE CÓDIGO FLEXIBLE SQLite/PostgreSQL")
    print("=" * 60)
    
    print("\n📝 Ejemplo 1: Insert básico")
    # ejemplo_basico()  # Descomentar para ejecutar
    
    print("\n📝 Ejemplo 2: Query parametrizada")
    # ejemplo_query_parametrizada()
    
    print("\n📝 Ejemplo 3: Update")
    # ejemplo_update()
    
    print("\n📝 Ejemplo 4: Transacción")
    # ejemplo_transaccion()
    
    print("\n📝 Ejemplo 5: Query manual adaptada")
    # ejemplo_query_manual_adaptada()
    
    print("\n📝 Ejemplo 6: Timestamps")
    # ejemplo_timestamp()
    
    print("\n📝 Ejemplo 7: Detección de motor")
    ejemplo_deteccion_motor()
    
    print("\n" + "=" * 60)
    print("✅ Todos los ejemplos completados")
    print("=" * 60)


if __name__ == "__main__":
    main()
