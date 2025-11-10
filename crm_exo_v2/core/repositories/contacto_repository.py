# ================================================================
#  core/repositories/contacto_repository.py  |  CRM-EXO v2
#  ---------------------------------------------------------------
#  Repositorio de Contactos heredado de AUPRepository.
#  
#  Gestiona contactos asociados a empresas con validación de FK,
#  listado por empresa, búsqueda y trazabilidad forense completa.
#  
#  FUNCIONALIDADES:
#  - Alta de contacto con validación de empresa existente (FK)
#  - Listado de contactos por empresa
#  - Conteo de contactos por empresa (soporte REGLA R1)
#  - Búsqueda por nombre o correo
#  - Actualización con trazabilidad automática
# ================================================================

import sys
from pathlib import Path
from datetime import datetime, UTC
from typing import List, Dict, Optional
import sqlite3

# Agregar directorio padre al path
CORE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORE_DIR))

from repository_base import AUPRepository


class ContactoRepository(AUPRepository):
    """
    Repositorio para gestión de Contactos con trazabilidad AUP
    
    Características:
    - Validación de foreign key (empresa debe existir)
    - Listado por empresa
    - Conteo para validar REGLA R1
    - Hash forense automático
    
    Uso:
    >>> repo = ContactoRepository(usuario="admin")
    >>> id_contacto = repo.crear_contacto(
    ...     id_empresa=1,
    ...     nombre="Juan Pérez",
    ...     correo="juan@empresa.com",
    ...     puesto="Director"
    ... )
    """
    
    def __init__(self, usuario: str = "system", conn: Optional[sqlite3.Connection] = None):
        super().__init__(entidad="contacto", usuario=usuario, conn=conn)
        self.tabla = "contactos"
        self.id_campo = "id_contacto"

    # ------------------------------------------------------------
    # Alta de contacto con validación de FK
    # ------------------------------------------------------------
    def crear_contacto(self, id_empresa: int, nombre: str, correo: Optional[str] = None,
                      telefono: Optional[str] = None, puesto: Optional[str] = None) -> int:
        """
        Crea un nuevo contacto asociado a una empresa
        
        VALIDACIÓN FK:
        - La empresa debe existir en la tabla empresas
        - Si no existe, lanza ValueError
        
        Args:
            id_empresa: ID de la empresa (obligatorio, FK)
            nombre: Nombre completo del contacto
            correo: Email del contacto
            telefono: Teléfono del contacto
            puesto: Cargo o puesto
        
        Returns:
            int: ID del contacto creado
        
        Raises:
            ValueError: Si la empresa no existe
        """
        con = self.conectar()
        try:
            cur = con.cursor()
            
            # Validar que la empresa exista
            cur.execute("SELECT id_empresa, nombre FROM empresas WHERE id_empresa = ?", (id_empresa,))
            empresa = cur.fetchone()
            
            if not empresa:
                raise ValueError(f"La empresa con ID {id_empresa} no existe")
            
            # Preparar datos
            data = {
                "id_empresa": id_empresa,
                "nombre": nombre.strip(),
                "correo": correo.lower().strip() if correo else None,
                "telefono": telefono.strip() if telefono else None,
                "puesto": puesto.strip() if puesto else None,
                "fecha_alta": datetime.now(UTC).isoformat()
            }
            
            # Insertar contacto
            cur.execute("""
                INSERT INTO contactos (id_empresa, nombre, correo, telefono, puesto, fecha_alta)
                VALUES (:id_empresa, :nombre, :correo, :telefono, :puesto, :fecha_alta)
            """, data)
            con.commit()
            id_contacto = cur.lastrowid
            
            # Registro forense
            self.registrar_evento(con, id_contacto, "CREAR", {
                **data,
                "empresa_nombre": empresa["nombre"]
            })
            
            return id_contacto
        
        except Exception as e:
            con.rollback()
            raise e
        finally:
            self.cerrar_conexion(con)

    # ------------------------------------------------------------
    # Listado de contactos por empresa
    # ------------------------------------------------------------
    def listar_por_empresa(self, id_empresa: int) -> List[Dict]:
        """
        Lista todos los contactos de una empresa específica
        
        Args:
            id_empresa: ID de la empresa
        
        Returns:
            List[Dict]: Contactos ordenados por fecha de alta descendente
        """
        return self.listar(
            tabla=self.tabla,
            filtros={"id_empresa": id_empresa},
            orden="fecha_alta DESC"
        )

    # ------------------------------------------------------------
    # Conteo de contactos por empresa (REGLA R1)
    # ------------------------------------------------------------
    def contar_por_empresa(self, id_empresa: int) -> int:
        """
        Cuenta cuántos contactos tiene una empresa
        
        SOPORTE REGLA R1:
        Solo si el conteo > 0, la empresa puede generar prospectos
        
        Args:
            id_empresa: ID de la empresa
        
        Returns:
            int: Número de contactos asociados
        """
        con = self.conectar()
        try:
            cur = con.cursor()
            cur.execute("""
                SELECT COUNT(*) as total FROM contactos WHERE id_empresa = ?
            """, (id_empresa,))
            
            resultado = cur.fetchone()
            return resultado["total"] if resultado else 0
        
        finally:
            self.cerrar_conexion(con)

    # ------------------------------------------------------------
    # Búsqueda de contactos
    # ------------------------------------------------------------
    def buscar_contactos(self, texto: str) -> List[Dict]:
        """
        Busca contactos por nombre o correo (LIKE case-insensitive)
        
        Incluye información de la empresa en el resultado (JOIN)
        
        Args:
            texto: Texto a buscar
        
        Returns:
            List[Dict]: Contactos encontrados con datos de empresa
        """
        con = self.conectar()
        try:
            cur = con.cursor()
            patron = f"%{texto}%"
            
            cur.execute("""
                SELECT 
                    c.id_contacto,
                    c.nombre,
                    c.correo,
                    c.telefono,
                    c.puesto,
                    c.fecha_alta,
                    e.id_empresa,
                    e.nombre as empresa_nombre
                FROM contactos c
                JOIN empresas e ON e.id_empresa = c.id_empresa
                WHERE c.nombre LIKE ? OR c.correo LIKE ?
                ORDER BY c.fecha_alta DESC
            """, (patron, patron))
            
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        
        finally:
            self.cerrar_conexion(con)

    # ------------------------------------------------------------
    # Obtener contacto por ID
    # ------------------------------------------------------------
    def obtener_contacto(self, id_contacto: int) -> Optional[Dict]:
        """
        Obtiene un contacto específico con información de empresa
        
        Returns:
            Dict: Datos del contacto + empresa, None si no existe
        """
        con = self.conectar()
        try:
            cur = con.cursor()
            cur.execute("""
                SELECT 
                    c.*,
                    e.nombre as empresa_nombre,
                    e.rfc as empresa_rfc
                FROM contactos c
                JOIN empresas e ON e.id_empresa = c.id_empresa
                WHERE c.id_contacto = ?
            """, (id_contacto,))
            
            row = cur.fetchone()
            return dict(row) if row else None
        
        finally:
            self.cerrar_conexion(con)
    
    def obtener_por_id(self, id_contacto: int) -> Optional[Dict]:
        """Alias de obtener_contacto para compatibilidad con tests"""
        return self.obtener_contacto(id_contacto)

    # ------------------------------------------------------------
    # Actualizar contacto
    # ------------------------------------------------------------
    def actualizar_contacto(self, id_contacto: int, **campos) -> bool:
        """
        Actualiza campos de un contacto existente
        
        Args:
            id_contacto: ID del contacto a actualizar
            **campos: Campos a actualizar (nombre, correo, telefono, puesto)
        
        Returns:
            bool: True si se actualizó correctamente
        
        Ejemplo:
        >>> repo.actualizar_contacto(1, puesto="Gerente General", correo="nuevo@email.com")
        """
        campos_validos = ["nombre", "correo", "telefono", "puesto"]
        data = {k: v for k, v in campos.items() if k in campos_validos}
        
        if not data:
            raise ValueError("No se proporcionaron campos válidos para actualizar")
        
        return self.actualizar(self.tabla, self.id_campo, id_contacto, data)

    # ------------------------------------------------------------
    # Demo de uso
    # ------------------------------------------------------------
    def demo(self):
        """Demostración completa del repositorio de contactos"""
        print("=" * 60)
        print("👤 DEMO CONTACTO REPOSITORY")
        print("=" * 60)
        
        # Primero verificar que exista al menos una empresa
        con = self.conectar()
        cur = con.cursor()
        cur.execute("SELECT id_empresa, nombre FROM empresas LIMIT 1")
        empresa = cur.fetchone()
        self.cerrar_conexion(con)
        
        if not empresa:
            print("\n⚠️  No hay empresas registradas. Primero ejecuta EmpresaRepository.demo()")
            return
        
        id_empresa = empresa["id_empresa"]
        nombre_empresa = empresa["nombre"]
        
        # Test 1: Crear contacto
        print(f"\n1️⃣ Creando contacto para empresa '{nombre_empresa}' (ID: {id_empresa})...")
        try:
            id_contacto = self.crear_contacto(
                id_empresa=id_empresa,
                nombre="María González Demo",
                correo="maria.gonzalez@demo.com",
                telefono="+52 55 1234 5678",
                puesto="Directora de Compras"
            )
            print(f"   ✅ Contacto creado con ID {id_contacto}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return
        
        # Test 2: Listar contactos de la empresa
        print(f"\n2️⃣ Listando contactos de empresa ID {id_empresa}:")
        contactos = self.listar_por_empresa(id_empresa)
        print(f"   📋 Total: {len(contactos)}")
        for c in contactos:
            print(f"      - {c['nombre']} ({c.get('puesto', 'Sin puesto')})")
        
        # Test 3: Conteo para REGLA R1
        print(f"\n3️⃣ Conteo de contactos (validación REGLA R1):")
        total = self.contar_por_empresa(id_empresa)
        print(f"   🔢 Empresa ID {id_empresa} tiene {total} contacto(s)")
        if total > 0:
            print(f"   ✅ REGLA R1: Esta empresa PUEDE generar prospectos")
        else:
            print(f"   ❌ REGLA R1: Esta empresa NO puede generar prospectos")
        
        # Test 4: Búsqueda
        print(f"\n4️⃣ Búsqueda de contactos con 'Demo':")
        resultados = self.buscar_contactos("Demo")
        print(f"   📋 Encontrados: {len(resultados)}")
        for r in resultados:
            print(f"      - {r['nombre']} en {r['empresa_nombre']}")
        
        # Test 5: Obtener contacto con JOIN
        print(f"\n5️⃣ Obtener contacto ID {id_contacto} (con empresa):")
        detalle = self.obtener_contacto(id_contacto)
        if detalle:
            print(f"   Nombre: {detalle['nombre']}")
            print(f"   Email: {detalle.get('correo', 'N/A')}")
            print(f"   Empresa: {detalle['empresa_nombre']} ({detalle['empresa_rfc']})")
        
        print("\n" + "=" * 60)
        print("✅ Demo completado")
        print("=" * 60)


# ================================================================
#  EJECUCIÓN DIRECTA (modo demo)
# ================================================================
if __name__ == "__main__":
    print("🚀 Testing ContactoRepository - Segundo repositorio derivado\n")
    
    repo = ContactoRepository(usuario="demo")
    repo.demo()
