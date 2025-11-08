#!/usr/bin/env python3
"""
Script CLI para inicializar el CRM AUP
Útil para entornos de desarrollo, testing o deployment automatizado
"""

import sys
import hashlib
from pathlib import Path

# Agregar aup_crm_core al path
sys.path.insert(0, str(Path(__file__).parent / "aup_crm_core"))

from core.database import init_db, get_connection, borrar_db

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def crear_admin(nombre="Administrador", correo="admin@synappssys.com", password="admin123"):
    """Crea el usuario administrador inicial"""
    conn = get_connection()
    if not conn:
        print("❌ Error al conectar con la base de datos")
        return False
    
    cur = conn.cursor()
    
    # Verificar si ya existe un admin
    cur.execute("SELECT COUNT(*) as total FROM aup_agentes WHERE tipo='usuario'")
    total = cur.fetchone()['total']
    
    if total > 0:
        print(f"⚠️  Ya existen {total} usuario(s) en el sistema")
        respuesta = input("¿Deseas crear otro usuario administrador? (s/n): ")
        if respuesta.lower() != 's':
            conn.close()
            return False
    
    # Crear admin
    password_hash = hash_password(password)
    cur.execute("""
        INSERT INTO aup_agentes (tipo, nombre, atributos, password, activo)
        VALUES (?, ?, ?, ?, ?)
    """, ("usuario", nombre, f"correo={correo};rol=Administrador", password_hash, 1))
    
    conn.commit()
    admin_id = cur.lastrowid
    conn.close()
    
    print(f"✅ Usuario administrador creado exitosamente")
    print(f"   ID: {admin_id}")
    print(f"   Nombre: {nombre}")
    print(f"   Correo: {correo}")
    print(f"   Contraseña: {password}")
    
    return True

def menu_principal():
    """Menú interactivo"""
    print("\n" + "="*60)
    print("🔧 INICIALIZADOR CRM AUP - SynAppsSys")
    print("="*60)
    print("\n1. Inicializar base de datos")
    print("2. Crear usuario administrador")
    print("3. Borrar base de datos (⚠️  PELIGRO)")
    print("4. Verificar estado del sistema")
    print("5. Salir")
    print("\n" + "-"*60)
    
    opcion = input("\nSelecciona una opción (1-5): ")
    
    if opcion == "1":
        print("\n🔨 Inicializando base de datos...")
        init_db()
        print("✅ Base de datos lista")
        
    elif opcion == "2":
        print("\n👤 Crear usuario administrador")
        nombre = input("Nombre completo [Administrador]: ") or "Administrador"
        correo = input("Correo electrónico [admin@synappssys.com]: ") or "admin@synappssys.com"
        password = input("Contraseña [admin123]: ") or "admin123"
        crear_admin(nombre, correo, password)
        
    elif opcion == "3":
        print("\n⚠️  ADVERTENCIA: Esto eliminará TODA la base de datos")
        confirmar = input("Escribe 'BORRAR' para confirmar: ")
        if confirmar == "BORRAR":
            borrar_db()
        else:
            print("❌ Cancelado")
            
    elif opcion == "4":
        print("\n📊 Estado del sistema:")
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            
            # Contar usuarios
            cur.execute("SELECT COUNT(*) as total FROM aup_agentes WHERE tipo='usuario'")
            usuarios = cur.fetchone()['total']
            
            # Contar clientes
            cur.execute("SELECT COUNT(*) as total FROM aup_agentes WHERE tipo='cliente'")
            clientes = cur.fetchone()['total']
            
            # Contar eventos
            cur.execute("SELECT COUNT(*) as total FROM aup_eventos")
            eventos = cur.fetchone()['total']
            
            conn.close()
            
            print(f"   Usuarios: {usuarios}")
            print(f"   Clientes: {clientes}")
            print(f"   Eventos registrados: {eventos}")
        else:
            print("❌ No se pudo conectar a la base de datos")
            
    elif opcion == "5":
        print("\n👋 ¡Hasta luego!")
        return False
        
    else:
        print("\n❌ Opción inválida")
    
    return True

def main():
    """Punto de entrada principal"""
    continuar = True
    
    while continuar:
        continuar = menu_principal()
        if continuar:
            input("\nPresiona ENTER para continuar...")

if __name__ == "__main__":
    main()
