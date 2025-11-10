# ================================================================
#  core/repository_prospecto.py  |  CRM-EXO v2
#  ---------------------------------------------------------------
#  Implementación del repositorio ProspectoRepository,
#  heredado de AUPRepository.
#  Gestiona la creación, validación y listado de prospectos,
#  integrando Empresa + Contacto bajo la regla R1.
#
#  REGLA R1 (CRÍTICA):
#    "Solo se puede crear un prospecto si existe una empresa válida
#     y al menos un contacto asociado a ella."
#
#  Este módulo integra a EmpresaRepository y ContactoRepository
#  de forma estructural y mantiene la trazabilidad forense completa
#  mediante herencia de AUPRepository.
# ================================================================

import sys
from pathlib import Path

# Ajuste de ruta para imports
CORE_DIR = Path(__file__).resolve().parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from repository_base import AUPRepository
import sqlite3
from datetime import datetime

class ProspectoRepository(AUPRepository):
    """
    Repositorio para gestión de prospectos.
    
    Cierra el NÚCLEO 1: IDENTIDAD
    - Empresa (base)
    - Contacto (personas)
    - Prospecto (oportunidad inicial) ← AQUÍ
    
    REGLA R1 materializada:
        No se puede crear prospecto sin:
        1. Empresa válida
        2. Contacto existente vinculado a esa empresa
        3. Sin duplicados activos
    """
    
    def __init__(self, usuario="system", conn=None):
        super().__init__(entidad="prospecto", usuario=usuario, conn=conn)
        self.tabla = "prospectos"

    # ------------------------------------------------------------
    # Crear prospecto (Regla R1)
    # ------------------------------------------------------------
    def crear_prospecto(self, id_empresa, id_contacto, origen=None):
        """
        Crea un prospecto solo si:
          - La empresa existe.
          - El contacto existe y pertenece a esa empresa.
          - No existe ya un prospecto activo con esa combinación.
        
        Args:
            id_empresa: FK a tabla empresas
            id_contacto: FK a tabla contactos (debe pertenecer a id_empresa)
            origen: Origen del prospecto (ej: "Campaña", "Referido", "Llamada fría")
        
        Returns:
            id_prospecto: ID del prospecto creado
        
        Raises:
            ValueError: Si falla validación REGLA R1 o hay duplicados
        """
        con = self.conectar()
        cur = con.cursor()

        # 1️⃣ Validar empresa
        cur.execute("SELECT id_empresa, nombre FROM empresas WHERE id_empresa = ?", (id_empresa,))
        empresa = cur.fetchone()
        if not empresa:
            con.close()
            raise ValueError(f"La empresa con ID {id_empresa} no existe.")

        # 2️⃣ Validar contacto y pertenencia (REGLA R1)
        cur.execute("SELECT id_contacto, nombre, id_empresa FROM contactos WHERE id_contacto = ?", (id_contacto,))
        contacto = cur.fetchone()
        if not contacto:
            con.close()
            raise ValueError(f"El contacto con ID {id_contacto} no existe.")
        if contacto["id_empresa"] != id_empresa:
            con.close()
            raise ValueError(f"El contacto '{contacto['nombre']}' no pertenece a la empresa seleccionada.")

        # 3️⃣ Evitar duplicados activos
        cur.execute("""
            SELECT id_prospecto FROM prospectos
            WHERE id_empresa = ? AND id_contacto = ? AND estado = 'Activo'
        """, (id_empresa, id_contacto))
        if cur.fetchone():
            con.close()
            raise ValueError("Ya existe un prospecto activo para esta empresa y contacto.")

        # 4️⃣ Crear prospecto
        data = {
            "id_empresa": id_empresa,
            "id_contacto": id_contacto,
            "estado": "Activo",
            "origen": origen,
            "fecha_creacion": datetime.utcnow().isoformat()
        }
        cur.execute("""
            INSERT INTO prospectos (id_empresa, id_contacto, estado, origen, fecha_creacion)
            VALUES (:id_empresa, :id_contacto, :estado, :origen, :fecha_creacion)
        """, data)
        con.commit()
        id_prospecto = cur.lastrowid
        
        # Trazabilidad forense (heredado de AUPRepository)
        self.registrar_evento(con, id_prospecto, "CREAR", data)
        
        con.close()
        return id_prospecto

    # ------------------------------------------------------------
    # Cambiar estado (para cierre o conversión)
    # ------------------------------------------------------------
    def cambiar_estado(self, id_prospecto, nuevo_estado):
        """
        Cambia el estado del prospecto (Activo, Ganado, Perdido, etc.)
        
        Estados válidos:
            - Activo: En proceso
            - Ganado: Convertido a oportunidad/cliente
            - Perdido: Descartado
            - En espera: Pausado temporalmente
        
        Args:
            id_prospecto: ID del prospecto
            nuevo_estado: Nuevo estado a asignar
        
        Raises:
            ValueError: Si prospecto no existe
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("SELECT * FROM prospectos WHERE id_prospecto = ?", (id_prospecto,))
        p = cur.fetchone()
        if not p:
            con.close()
            raise ValueError(f"Prospecto {id_prospecto} no existe.")

        cur.execute("""
            UPDATE prospectos SET estado = ? WHERE id_prospecto = ?
        """, (nuevo_estado, id_prospecto))
        con.commit()
        
        # Registro forense del cambio
        self.registrar_evento(con, id_prospecto, "CAMBIO_ESTADO", {"estado": nuevo_estado})
        
        con.close()

    # ------------------------------------------------------------
    # Listar prospectos activos
    # ------------------------------------------------------------
    def listar_activos(self):
        """
        Devuelve los prospectos activos con su empresa y contacto.
        
        Returns:
            Lista de diccionarios con información completa del prospecto
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("""
            SELECT p.id_prospecto, e.nombre AS empresa, c.nombre AS contacto,
                   p.estado, p.origen, p.fecha_creacion
            FROM prospectos p
            JOIN empresas e ON e.id_empresa = p.id_empresa
            JOIN contactos c ON c.id_contacto = p.id_contacto
            WHERE p.estado = 'Activo'
            ORDER BY p.fecha_creacion DESC
        """)
        rows = cur.fetchall()
        con.close()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------
    # Buscar prospecto
    # ------------------------------------------------------------
    def buscar(self, texto):
        """
        Busca prospectos por nombre de empresa o contacto.
        
        Args:
            texto: Texto a buscar (coincidencia parcial)
        
        Returns:
            Lista de prospectos que coinciden
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("""
            SELECT p.id_prospecto, e.nombre AS empresa, c.nombre AS contacto,
                   p.estado, p.origen, p.fecha_creacion
            FROM prospectos p
            JOIN empresas e ON e.id_empresa = p.id_empresa
            JOIN contactos c ON c.id_contacto = p.id_contacto
            WHERE e.nombre LIKE ? OR c.nombre LIKE ?
            ORDER BY p.fecha_creacion DESC
        """, (f"%{texto}%", f"%{texto}%"))
        rows = cur.fetchall()
        con.close()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------
    # Obtener prospecto completo
    # ------------------------------------------------------------
    def obtener(self, id_prospecto):
        """
        Obtiene información completa de un prospecto.
        
        Args:
            id_prospecto: ID del prospecto
        
        Returns:
            Diccionario con datos del prospecto + empresa + contacto
        
        Raises:
            ValueError: Si prospecto no existe
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("""
            SELECT 
                p.*,
                e.nombre AS empresa_nombre,
                e.rfc AS empresa_rfc,
                e.sector AS empresa_sector,
                c.nombre AS contacto_nombre,
                c.correo AS contacto_correo,
                c.telefono AS contacto_telefono,
                c.puesto AS contacto_puesto
            FROM prospectos p
            JOIN empresas e ON e.id_empresa = p.id_empresa
            JOIN contactos c ON c.id_contacto = p.id_contacto
            WHERE p.id_prospecto = ?
        """, (id_prospecto,))
        row = cur.fetchone()
        con.close()
        
        if not row:
            raise ValueError(f"Prospecto {id_prospecto} no existe.")
        
        return dict(row)

    # ------------------------------------------------------------
    # Estadísticas
    # ------------------------------------------------------------
    def estadisticas(self):
        """
        Genera estadísticas generales de prospectos.
        
        Returns:
            Diccionario con contadores por estado
        """
        con = self.conectar()
        cur = con.cursor()
        
        stats = {}
        
        # Total por estado
        cur.execute("""
            SELECT estado, COUNT(*) as total
            FROM prospectos
            GROUP BY estado
        """)
        stats["por_estado"] = {row["estado"]: row["total"] for row in cur.fetchall()}
        
        # Total general
        cur.execute("SELECT COUNT(*) as total FROM prospectos")
        stats["total"] = cur.fetchone()["total"]
        
        # Por origen
        cur.execute("""
            SELECT origen, COUNT(*) as total
            FROM prospectos
            WHERE origen IS NOT NULL
            GROUP BY origen
        """)
        stats["por_origen"] = {row["origen"]: row["total"] for row in cur.fetchall()}
        
        con.close()
        return stats

    # ------------------------------------------------------------
    # Demo de uso
    # ------------------------------------------------------------
    def demo(self):
        """
        Demostración de funcionalidad del ProspectoRepository.
        
        Prueba:
        1. Crear prospecto con validación REGLA R1
        2. Listar prospectos activos
        3. Buscar por texto
        4. Cambiar estado
        5. Estadísticas
        """
        print("\n🤝 DEMO PROSPECTO REPOSITORY")
        print("=" * 60)
        
        # 1. Crear prospecto
        print("\n1️⃣ Creando prospecto (REGLA R1: validación empresa + contacto)...")
        try:
            id_p = self.crear_prospecto(
                id_empresa=1,
                id_contacto=1,
                origen="Campaña Demo"
            )
            print(f"   ✅ Prospecto creado con ID {id_p}")
        except ValueError as e:
            print(f"   ⚠️ {e}")
        
        # 2. Listar activos
        print("\n2️⃣ Prospectos activos:")
        prospectos = self.listar_activos()
        if prospectos:
            print(f"   📋 Total: {len(prospectos)}")
            for p in prospectos:
                print(f"      - {p['empresa']} → {p['contacto']} ({p['estado']}) | Origen: {p.get('origen', 'N/A')}")
        else:
            print("   📋 No hay prospectos activos")
        
        # 3. Búsqueda
        print("\n3️⃣ Búsqueda por 'Demo':")
        resultados = self.buscar("Demo")
        print(f"   📋 Encontrados: {len(resultados)}")
        for r in resultados:
            print(f"      - {r['empresa']} vía {r['contacto']}")
        
        # 4. Cambiar estado
        if prospectos:
            print(f"\n4️⃣ Cambiando estado del prospecto ID {prospectos[0]['id_prospecto']}...")
            try:
                self.cambiar_estado(prospectos[0]['id_prospecto'], "En espera")
                print("   ✅ Estado actualizado a 'En espera'")
            except ValueError as e:
                print(f"   ❌ Error: {e}")
        
        # 5. Estadísticas
        print("\n5️⃣ Estadísticas generales:")
        stats = self.estadisticas()
        print(f"   📈 Total prospectos: {stats['total']}")
        print(f"   📈 Por estado: {stats['por_estado']}")
        print(f"   📈 Por origen: {stats.get('por_origen', {})}")
        
        print("\n" + "=" * 60)
        print("✅ NÚCLEO 1: IDENTIDAD COMPLETO")
        print("   - EmpresaRepository ✅")
        print("   - ContactoRepository ✅")
        print("   - ProspectoRepository ✅")
        print("   - REGLA R1 implementada ✅")
        print("=" * 60)


# ============================================================
# EJECUCIÓN DEMO
# ============================================================
if __name__ == "__main__":
    repo = ProspectoRepository()
    repo.demo()
