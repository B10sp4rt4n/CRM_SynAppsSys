#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de mantenimiento: Eliminar duplicados de prospectos
Ejecutar: python limpiar_duplicados.py
"""

import sqlite3
import sys
from pathlib import Path

# Determinar ruta de la BD
DB_PATH = Path(__file__).resolve().parent / "data" / "aup_crm.sqlite"

def limpiar_duplicados():
    """Elimina prospectos duplicados conservando el ID más antiguo"""
    
    if not DB_PATH.exists():
        print(f"❌ Base de datos no encontrada: {DB_PATH}")
        print("💡 Ejecuta la aplicación primero para crear la BD")
        return False
    
    print(f"📂 Conectando a: {DB_PATH}\n")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # 1. Verificar que existe la tabla
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='aup_agentes'")
    if not cur.fetchone():
        print("❌ Tabla 'aup_agentes' no existe")
        conn.close()
        return False
    
    # 2. Ver estado actual
    print("📊 PROSPECTOS ACTUALES:\n")
    cur.execute("SELECT id, nombre, activo FROM aup_agentes WHERE tipo='prospecto' ORDER BY id")
    prospectos = cur.fetchall()
    
    if not prospectos:
        print("   (No hay prospectos registrados)\n")
        conn.close()
        return True
    
    for p in prospectos:
        activo_txt = "✅ Activo" if p['activo'] else "❌ Inactivo"
        print(f"   ID {p['id']:3d}: {p['nombre']:<40} {activo_txt}")
    
    # 3. Detectar duplicados por nombre (case-insensitive)
    print(f"\n{'='*70}")
    print("🔍 BUSCANDO DUPLICADOS...\n")
    
    cur.execute("""
        SELECT LOWER(TRIM(nombre)) as nombre_lower, 
               COUNT(*) as cantidad, 
               GROUP_CONCAT(id) as ids,
               GROUP_CONCAT(nombre) as nombres_originales
        FROM aup_agentes 
        WHERE tipo='prospecto'
        GROUP BY LOWER(TRIM(nombre))
        HAVING COUNT(*) > 1
    """)
    duplicados = cur.fetchall()
    
    if not duplicados:
        print("✅ No se encontraron duplicados.\n")
        conn.close()
        return True
    
    # 4. Mostrar duplicados encontrados
    print(f"⚠️  Encontrados {len(duplicados)} grupo(s) de duplicados:\n")
    
    total_eliminados = 0
    
    for dup in duplicados:
        ids = dup['ids'].split(',')
        nombres = dup['nombres_originales'].split(',')
        
        print(f"   Nombre: '{dup['nombre_lower']}'")
        print(f"   Total registros: {dup['cantidad']}")
        print(f"   IDs encontrados: {', '.join(ids)}")
        
        # Mostrar detalles de cada duplicado
        for i, (id_str, nombre_orig) in enumerate(zip(ids, nombres)):
            marca = "✅ CONSERVAR" if i == 0 else "🗑️  ELIMINAR"
            print(f"      ID {id_str}: '{nombre_orig}' → {marca}")
        
        # Confirmar eliminación
        print(f"\n   ¿Eliminar duplicados y conservar ID {ids[0]}? (s/N): ", end='')
        respuesta = input().strip().lower()
        
        if respuesta == 's':
            ids_a_eliminar = [int(id) for id in ids[1:]]
            
            for id_eliminar in ids_a_eliminar:
                # Eliminar prospecto
                cur.execute("DELETE FROM aup_agentes WHERE id=?", (id_eliminar,))
                
                # Limpiar relaciones huérfanas
                cur.execute("DELETE FROM aup_relaciones WHERE agente_origen=? OR agente_destino=?", 
                           (id_eliminar, id_eliminar))
                
                # Registrar en eventos
                cur.execute("""
                    INSERT INTO aup_eventos (agente_id, accion, descripcion)
                    VALUES (?, ?, ?)
                """, (id_eliminar, "Eliminación duplicado", 
                      f"Registro duplicado eliminado (nombre: {dup['nombre_lower']})"))
                
                total_eliminados += 1
            
            conn.commit()
            print(f"   ✅ Eliminados {len(ids_a_eliminar)} duplicado(s)")
        else:
            print(f"   ⏭️  Omitido")
        
        print()
    
    # 5. Mostrar resumen final
    print(f"{'='*70}")
    print(f"✅ PROCESO COMPLETADO")
    print(f"   Total eliminados: {total_eliminados}")
    
    # 6. Verificar estado final
    print(f"\n📊 PROSPECTOS DESPUÉS DE LIMPIEZA:\n")
    cur.execute("SELECT id, nombre, activo FROM aup_agentes WHERE tipo='prospecto' ORDER BY id")
    prospectos_final = cur.fetchall()
    
    for p in prospectos_final:
        activo_txt = "✅ Activo" if p['activo'] else "❌ Inactivo"
        print(f"   ID {p['id']:3d}: {p['nombre']:<40} {activo_txt}")
    
    conn.close()
    return True


if __name__ == "__main__":
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║     🔧 LIMPIADOR DE DUPLICADOS - CRM SynAppsSys              ║")
    print("╚═══════════════════════════════════════════════════════════════╝\n")
    
    try:
        exito = limpiar_duplicados()
        sys.exit(0 if exito else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso cancelado por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
