# ================================================================
#  core/repositories/prospecto_repository.py  |  CRM-EXO v2
#  ---------------------------------------------------------------
#  Implementación del repositorio ProspectoRepository,
#  heredado de AUPRepository.
#  
#  REGLA R1 (CRÍTICA): Solo se puede crear prospecto si empresa tiene contactos > 0
#  REGLA R3 (conversión): Prospecto se puede convertir a cliente
#  
#  Gestiona alta, búsqueda y validación de prospectos
#  vinculados a empresas y contactos, con trazabilidad forense completa.
# ================================================================

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# Ajuste de ruta para imports
CORE_DIR = Path(__file__).resolve().parent.parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from repository_base import AUPRepository


class ProspectoRepository(AUPRepository):
    """
    Repositorio para gestión de prospectos.
    
    ESQUEMA DB (real):
        - id_prospecto: INTEGER PRIMARY KEY
        - id_empresa: INTEGER NOT NULL (FK)
        - id_contacto: INTEGER NOT NULL (FK)
        - estado: TEXT DEFAULT 'Activo'
        - origen: TEXT
        - fecha_creacion: TEXT DEFAULT CURRENT_TIMESTAMP
    
    REGLA R1: No se puede crear prospecto si empresa NO tiene contactos
    REGLA R3: Prospecto puede convertirse a cliente (extensión futura)
    """
    
    def __init__(self, usuario: str = "system"):
        """
        Inicializa repositorio de prospectos.
        
        Args:
            usuario: Usuario que ejecuta operaciones (para trazabilidad)
        """
        super().__init__(entidad="prospecto", usuario=usuario)
        self.conn = self.conectar()
    
    def _validar_regla_r1(self, empresa_id: int) -> bool:
        """
        REGLA R1: Empresa debe tener al menos 1 contacto.
        
        Args:
            empresa_id: ID de empresa a validar
            
        Returns:
            True si empresa tiene contactos, False si no
            
        Raises:
            ValueError: Si empresa no existe o no tiene contactos
        """
        cursor = self.conn.cursor()
        
        # Verificar que empresa exista
        cursor.execute(
            "SELECT COUNT(*) FROM empresas WHERE id_empresa = ?",
            (empresa_id,)
        )
        if cursor.fetchone()[0] == 0:
            raise ValueError(f"❌ Empresa ID {empresa_id} no existe")
        
        # REGLA R1: Contar contactos
        cursor.execute(
            "SELECT COUNT(*) FROM contactos WHERE id_empresa = ?",
            (empresa_id,)
        )
        count = cursor.fetchone()[0]
        
        if count == 0:
            raise ValueError(
                f"❌ REGLA R1 VIOLADA: Empresa ID {empresa_id} NO tiene contactos. "
                f"No se puede crear prospecto sin contacto previo."
            )
        
        return True
    
    # ------------------------------------------------------------
    # Alta de prospecto con validación REGLA R1
    # ------------------------------------------------------------
    def crear_prospecto(
        self,
        id_empresa: int,
        id_contacto: int,
        estado: str = "Activo",
        origen: Optional[str] = None
    ) -> int:
        """
        Crea prospecto validando REGLA R1.
        
        Args:
            id_empresa: FK a empresas (DEBE tener contactos)
            id_contacto: FK a contactos (debe existir)
            estado: Estado del prospecto (default: 'Activo')
            origen: Origen del prospecto (ej: 'Llamada fría', 'Referido')
            
        Returns:
            id_prospecto: ID del prospecto creado
            
        Raises:
            ValueError: Si empresa no cumple REGLA R1 o contacto no existe
        """
        # VALIDACIÓN REGLA R1 - CRÍTICA
        self._validar_regla_r1(id_empresa)
        
        # Validar que contacto existe y pertenece a la empresa
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id_contacto FROM contactos WHERE id_contacto = ? AND id_empresa = ?",
            (id_contacto, id_empresa)
        )
        if not cursor.fetchone():
            raise ValueError(
                f"❌ Contacto ID {id_contacto} no existe o no pertenece a empresa ID {id_empresa}"
            )
        
        # Preparar datos
        datos = {
            "id_empresa": id_empresa,
            "id_contacto": id_contacto,
            "estado": estado,
            "origen": origen,
            "fecha_creacion": datetime.utcnow().isoformat()
        }
        
        # Usar método heredado para crear
        prospecto_id = self.crear("prospectos", datos)
        
        return prospecto_id
    
    # ------------------------------------------------------------
    # Búsqueda y listado
    # ------------------------------------------------------------
    def listar_por_empresa(self, id_empresa: int) -> List[Dict[str, Any]]:
        """
        Lista todos los prospectos de una empresa.
        
        Args:
            id_empresa: ID de empresa
            
        Returns:
            Lista de prospectos con información de empresa y contacto
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                p.*,
                e.nombre AS empresa_nombre,
                e.rfc AS empresa_rfc,
                c.nombre AS contacto_nombre,
                c.correo AS contacto_correo
            FROM prospectos p
            INNER JOIN empresas e ON p.id_empresa = e.id_empresa
            INNER JOIN contactos c ON p.id_contacto = c.id_contacto
            WHERE p.id_empresa = ?
            ORDER BY p.fecha_creacion DESC
        """, (id_empresa,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def buscar_prospectos(
        self,
        texto: Optional[str] = None,
        estado: Optional[str] = None,
        solo_activos: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Búsqueda flexible de prospectos.
        
        Args:
            texto: Búsqueda en empresa/contacto/origen
            estado: Filtro por estado
            solo_activos: Si True, solo prospectos activos
            
        Returns:
            Lista de prospectos con empresa y contacto
        """
        cursor = self.conn.cursor()
        
        query = """
            SELECT 
                p.*,
                e.nombre AS empresa_nombre,
                e.rfc AS empresa_rfc,
                c.nombre AS contacto_nombre,
                c.correo AS contacto_correo
            FROM prospectos p
            INNER JOIN empresas e ON p.id_empresa = e.id_empresa
            INNER JOIN contactos c ON p.id_contacto = c.id_contacto
            WHERE 1=1
        """
        params = []
        
        if solo_activos:
            query += " AND p.estado = 'Activo'"
        
        if texto:
            query += " AND (e.nombre LIKE ? OR c.nombre LIKE ? OR p.origen LIKE ?)"
            like_text = f"%{texto}%"
            params.extend([like_text, like_text, like_text])
        
        if estado:
            query += " AND p.estado = ?"
            params.append(estado)
        
        query += " ORDER BY p.fecha_creacion DESC"
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    # ------------------------------------------------------------
    # Estadísticas
    # ------------------------------------------------------------
    def obtener_estadisticas(self) -> Dict[str, Any]:
        """
        Genera estadísticas de prospectos.
        
        Returns:
            Diccionario con estadísticas
        """
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Total prospectos
        cursor.execute("SELECT COUNT(*) FROM prospectos")
        stats["total"] = cursor.fetchone()[0]
        
        # Por estado
        cursor.execute("""
            SELECT estado, COUNT(*) as count
            FROM prospectos
            GROUP BY estado
        """)
        stats["por_estado"] = {row["estado"]: row["count"] for row in cursor.fetchall()}
        
        # Por empresa (top 5)
        cursor.execute("""
            SELECT e.nombre, COUNT(*) as count
            FROM prospectos p
            INNER JOIN empresas e ON p.id_empresa = e.id_empresa
            WHERE p.estado = 'Activo'
            GROUP BY e.nombre
            ORDER BY count DESC
            LIMIT 5
        """)
        stats["top_empresas"] = {row["nombre"]: row["count"] for row in cursor.fetchall()}
        
        return stats


# ============================================================
# DEMO
# ============================================================
def demo():
    """
    Demostración del ProspectoRepository.
    
    Prueba:
    1. Crear prospecto para empresa existente (ID 1) con contacto existente
    2. Verificar validación REGLA R1 (empresa sin contactos)
    3. Listar prospectos por empresa
    4. Estadísticas
    """
    print("\n🚀 Testing ProspectoRepository - Tercer repositorio derivado")
    print("=" * 60)
    
    repo = ProspectoRepository()
    
    print("\n👥 DEMO PROSPECTO REPOSITORY")
    print("=" * 60)
    
    # 1. Crear prospecto para empresa existente con contacto
    print("\n1️⃣ Creando prospecto para empresa ID 1 con contacto ID 1...")
    try:
        prospecto_id = repo.crear_prospecto(
            id_empresa=1,
            id_contacto=1,
            estado="Activo",
            origen="Contacto directo - María González"
        )
        print(f"   ✅ Prospecto creado con ID {prospecto_id}")
    except ValueError as e:
        print(f"   ❌ Error: {e}")
    
    # 2. Intentar crear prospecto para empresa SIN contactos
    print("\n2️⃣ Prueba REGLA R1: Intentar crear prospecto para empresa sin contactos...")
    try:
        # Crear empresa temporal sin contactos
        from repositories.empresa_repository import EmpresaRepository
        emp_repo = EmpresaRepository()
        empresa_sin_contactos = emp_repo.crear_empresa(
            nombre="Empresa Prueba Sin Contactos",
            rfc="EPSC999999XXX",
            sector="Prueba"
        )
        
        # Intentar crear prospecto (debe fallar)
        repo.crear_prospecto(
            id_empresa=empresa_sin_contactos,
            id_contacto=1,  # Contacto válido pero de otra empresa
            estado="Activo",
            origen="Prueba"
        )
        print("   ❌ REGLA R1 NO VALIDADA - esto NO debería ocurrir")
    except ValueError as e:
        print(f"   ✅ REGLA R1 VALIDADA: {e}")
    
    # 3. Listar prospectos de empresa 1
    print("\n3️⃣ Listando prospectos de empresa ID 1:")
    prospectos = repo.listar_por_empresa(id_empresa=1)
    print(f"   📋 Total: {len(prospectos)}")
    for p in prospectos:
        print(f"      - Estado: {p['estado']} | Contacto: {p['contacto_nombre']} | Origen: {p.get('origen', 'N/A')}")
    
    # 4. Búsqueda
    print("\n4️⃣ Búsqueda de prospectos activos:")
    resultados = repo.buscar_prospectos(solo_activos=True)
    print(f"   📋 Encontrados: {len(resultados)}")
    for r in resultados:
        print(f"      - {r['empresa_nombre']} vía {r['contacto_nombre']}")
    
    # 5. Estadísticas
    print("\n5️⃣ Estadísticas generales:")
    stats = repo.obtener_estadisticas()
    print(f"   📈 Total prospectos: {stats['total']}")
    print(f"   📈 Por estado: {stats['por_estado']}")
    print(f"   📈 Top empresas: {stats['top_empresas']}")
    
    print("\n" + "=" * 60)
    print("✅ Demo completado")
    print("=" * 60)


if __name__ == "__main__":
    demo()
