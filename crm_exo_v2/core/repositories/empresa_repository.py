# ================================================================
#  core/repositories/empresa_repository.py  |  CRM-EXO v2
#  ---------------------------------------------------------------
#  Implementación del repositorio EmpresaRepository,
#  heredado de AUPRepository.
#  
#  Gestiona alta, búsqueda y listado de empresas
#  con trazabilidad forense completa.
#  
#  FUNCIONALIDADES:
#  - Alta con validación de duplicados (nombre/RFC)
#  - Búsqueda por nombre o RFC (LIKE)
#  - Listado general ordenado
#  - Listado de empresas con contactos (JOIN)
#  - Trazabilidad automática heredada de AUPRepository
# ================================================================

import sys
from pathlib import Path
from datetime import datetime, UTC
from typing import List, Dict, Optional
import sqlite3

# Agregar directorio padre al path para imports relativos
CORE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CORE_DIR))

from repository_base import AUPRepository


class EmpresaRepository(AUPRepository):
    """
    Repositorio para gestión de Empresas con trazabilidad AUP
    
    Características:
    - Validación de duplicados por nombre y RFC
    - Búsqueda inteligente (nombre o RFC)
    - JOIN con contactos para análisis
    - Hash forense automático en cada operación
    
    Uso:
    >>> repo = EmpresaRepository(usuario="admin")
    >>> id_emp = repo.crear_empresa("ACME Corp", "ACM123456ABC", "Tecnología")
    >>> empresas = repo.listar_empresas_con_contactos()
    """
    
    def __init__(self, usuario: str = "system", conn: Optional[sqlite3.Connection] = None):
        """
        Inicializa el repositorio de empresas
        
        Args:
            usuario: Usuario que realiza las operaciones (para trazabilidad)
            conn: Conexión SQLite externa (para testing)
        """
        super().__init__(entidad="empresa", usuario=usuario, conn=conn)
        self.tabla = "empresas"
        self.id_campo = "id_empresa"

    # ------------------------------------------------------------
    # Alta de empresa con validación de duplicados
    # ------------------------------------------------------------
    def crear_empresa(self, nombre: str, rfc: Optional[str] = None, 
                     sector: Optional[str] = None, direccion: Optional[str] = None,
                     telefono: Optional[str] = None, correo: Optional[str] = None, 
                     tipo_cliente: str = "cliente") -> int:
        """
        Crea una nueva empresa con validación de duplicados
        
        VALIDACIONES:
        - Nombre no debe existir (case-insensitive)
        - RFC no debe existir (si se proporciona)
        
        TRAZABILIDAD:
        - Evento CREAR en historial_general
        - Hash SHA-256 en hash_registros
        
        Args:
            nombre: Nombre de la empresa (obligatorio)
            rfc: RFC fiscal (opcional pero debe ser único)
            sector: Sector económico
            direccion: Dirección fiscal
            telefono: Teléfono de contacto
            correo: Email corporativo
            tipo_cliente: Tipo de cliente ('cliente' o 'prospecto')
        
        Returns:
            int: ID de la empresa creada
        
        Raises:
            ValueError: Si ya existe empresa con ese nombre o RFC
        """
        con = self.conectar()
        try:
            cur = con.cursor()
            
            # Validar duplicados
            if rfc:
                cur.execute("""
                    SELECT id_empresa, nombre FROM empresas 
                    WHERE LOWER(nombre) = LOWER(?) OR UPPER(rfc) = UPPER(?)
                """, (nombre, rfc))
            else:
                cur.execute("""
                    SELECT id_empresa, nombre FROM empresas 
                    WHERE LOWER(nombre) = LOWER(?)
                """, (nombre,))
            
            existe = cur.fetchone()
            if existe:
                raise ValueError(
                    f"Empresa duplicada: '{existe['nombre']}' (ID: {existe['id_empresa']}) "
                    f"ya existe en el sistema"
                )
            
            # Preparar datos
            data = {
                "nombre": nombre.strip(),
                "rfc": rfc.upper().strip() if rfc else None,
                "sector": sector.strip() if sector else None,
                "direccion": direccion.strip() if direccion else None,
                "telefono": telefono.strip() if telefono else None,
                "correo": correo.lower().strip() if correo else None,
                "tipo_cliente": tipo_cliente,
                "fecha_alta": datetime.now(UTC).isoformat()
            }
            
            # Insertar empresa
            cur.execute("""
                INSERT INTO empresas (nombre, rfc, sector, direccion, telefono, correo, tipo_cliente, fecha_alta)
                VALUES (:nombre, :rfc, :sector, :direccion, :telefono, :correo, :tipo_cliente, :fecha_alta)
            """, data)
            con.commit()
            id_empresa = cur.lastrowid
            
            # Registro forense automático
            self.registrar_evento(con, id_empresa, "CREAR", data)
            
            return id_empresa
        
        except Exception as e:
            con.rollback()
            raise e
        finally:
            con.close()

    # ------------------------------------------------------------
    # Búsqueda inteligente por nombre o RFC
    # ------------------------------------------------------------
    def buscar_por_nombre(self, texto: str) -> List[Dict]:
        """
        Busca empresas por coincidencia parcial en nombre o RFC
        
        Búsqueda case-insensitive con LIKE en:
        - Nombre de la empresa
        - RFC fiscal
        
        Args:
            texto: Texto a buscar (parcial)
        
        Returns:
            List[Dict]: Lista de empresas que coinciden
        
        Ejemplo:
        >>> repo.buscar_por_nombre("ACME")
        [{'id_empresa': 1, 'nombre': 'ACME Corporation', 'rfc': 'ACM123456ABC', ...}]
        """
        con = self.conectar()
        try:
            cur = con.cursor()
            patron = f"%{texto}%"
            
            cur.execute("""
                SELECT id_empresa, nombre, rfc, sector, telefono, correo, fecha_alta
                FROM empresas
                WHERE nombre LIKE ? OR rfc LIKE ?
                ORDER BY fecha_alta DESC
            """, (patron, patron))
            
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        
        finally:
            con.close()

    # ------------------------------------------------------------
    # Listado general de empresas
    # ------------------------------------------------------------
    def listar_empresas(self, limite: Optional[int] = None) -> List[Dict]:
        """
        Devuelve todas las empresas registradas
        
        Args:
            limite: Número máximo de registros (None = sin límite)
        
        Returns:
            List[Dict]: Empresas ordenadas por fecha de alta descendente
        """
        return self.listar(
            tabla=self.tabla,
            orden="fecha_alta DESC",
            limite=limite
        )

    # ------------------------------------------------------------
    # Empresas con contactos (JOIN con tabla contactos)
    # ------------------------------------------------------------
    def listar_empresas_con_contactos(self) -> List[Dict]:
        """
        Devuelve empresas que tienen al menos un contacto asociado
        
        REGLA R1 (validación indirecta):
        Solo estas empresas pueden generar prospectos
        
        JOIN con tabla contactos + COUNT agregado
        
        Returns:
            List[Dict]: Empresas con total de contactos, ordenadas por cantidad
        
        Estructura del resultado:
        {
            'id_empresa': 1,
            'nombre': 'ACME Corp',
            'rfc': 'ACM123456ABC',
            'total_contactos': 5
        }
        """
        con = self.conectar()
        try:
            cur = con.cursor()
            cur.execute("""
                SELECT 
                    e.id_empresa, 
                    e.nombre, 
                    e.rfc, 
                    e.sector,
                    COUNT(c.id_contacto) AS total_contactos
                FROM empresas e
                INNER JOIN contactos c ON c.id_empresa = e.id_empresa
                GROUP BY e.id_empresa
                HAVING COUNT(c.id_contacto) > 0
                ORDER BY total_contactos DESC, e.nombre ASC
            """)
            
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        
        finally:
            con.close()

    # ------------------------------------------------------------
    # Obtener empresa por ID
    # ------------------------------------------------------------
    def obtener_empresa(self, id_empresa: int) -> Optional[Dict]:
        """
        Obtiene una empresa específica por su ID
        
        Returns:
            Dict: Datos de la empresa, None si no existe
        """
        return self.obtener_por_id(self.tabla, self.id_campo, id_empresa)

    # ------------------------------------------------------------
    # Actualizar empresa
    # ------------------------------------------------------------
    def actualizar_empresa(self, id_empresa: int, **campos) -> bool:
        """
        Actualiza campos de una empresa existente
        
        Args:
            id_empresa: ID de la empresa a actualizar
            **campos: Campos a actualizar (nombre, rfc, sector, telefono, correo)
        
        Returns:
            bool: True si se actualizó correctamente
        
        Ejemplo:
        >>> repo.actualizar_empresa(1, sector="Tecnología avanzada", telefono="555-1234")
        """
        # Filtrar solo campos válidos
        campos_validos = ["nombre", "rfc", "sector", "telefono", "correo"]
        data = {k: v for k, v in campos.items() if k in campos_validos}
        
        if not data:
            raise ValueError("No se proporcionaron campos válidos para actualizar")
        
        return self.actualizar(self.tabla, self.id_campo, id_empresa, data)

    # ------------------------------------------------------------
    # Demo de uso
    # ------------------------------------------------------------
    def demo(self):
        """Demostración completa del repositorio de empresas"""
        print("=" * 60)
        print("🏗️  DEMO EMPRESA REPOSITORY")
        print("=" * 60)
        
        # Test 1: Crear empresa
        print("\n1️⃣ Creando empresa de prueba...")
        try:
            id_emp = self.crear_empresa(
                nombre="SynAppsSys Demo",
                rfc="SDE001122AUP",
                sector="Tecnología",
                telefono="+52 55 5555 5555",
                correo="demo@synappssys.mx"
            )
            print(f"   ✅ Empresa creada con ID {id_emp}")
        except ValueError as e:
            print(f"   ⚠️  {e}")
        
        # Test 2: Listar empresas
        print("\n2️⃣ Listado de empresas registradas:")
        empresas = self.listar_empresas(limite=10)
        if empresas:
            for e in empresas:
                print(f"   - ID {e['id_empresa']}: {e['nombre']} ({e.get('rfc', 'Sin RFC')})")
        else:
            print("   (sin empresas registradas)")
        
        # Test 3: Búsqueda
        print("\n3️⃣ Búsqueda por texto 'Demo':")
        resultados = self.buscar_por_nombre("Demo")
        print(f"   📋 Encontradas: {len(resultados)}")
        for r in resultados:
            print(f"      - {r['nombre']}")
        
        # Test 4: Empresas con contactos
        print("\n4️⃣ Empresas con contactos (REGLA R1):")
        con_contactos = self.listar_empresas_con_contactos()
        if con_contactos:
            for ec in con_contactos:
                print(f"   - {ec['nombre']}: {ec['total_contactos']} contactos")
        else:
            print("   (ninguna empresa tiene contactos aún)")
        
        # Test 5: Validación de integridad
        print("\n5️⃣ Validación de integridad estructural:")
        integridad = self.validar_integridad()
        for k, v in integridad.items():
            status = "✅" if v else "❌"
            print(f"   {status} {k}: {v}")
        
        print("\n" + "=" * 60)
        print("✅ Demo completado")
        print("=" * 60)


# ================================================================
#  EJECUCIÓN DIRECTA (modo demo)
# ================================================================
if __name__ == "__main__":
    print("🚀 Testing EmpresaRepository - Primer repositorio derivado real\n")
    
    repo = EmpresaRepository(usuario="demo")
    repo.demo()
