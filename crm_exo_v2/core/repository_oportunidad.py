# ================================================================
#  core/repository_oportunidad.py  |  CRM-EXO v2
#  ---------------------------------------------------------------
#  Implementación del repositorio OportunidadRepository
#  (Núcleo 2: Transacción).
#
#  REGLA R2 (CRÍTICA):
#    "Una oportunidad solo puede crearse a partir de un prospecto
#     válido y activo."
#
#  REGLA R3 (CONVERSIÓN):
#    "Al ganar una oportunidad, el prospecto se convierte en Cliente."
#
#  Este repositorio conecta el flujo desde Identidad (Prospecto)
#  hacia Transacción (Oportunidad → Cotización → OC → Factura).
# ================================================================

import sys
from pathlib import Path

# Ajuste de ruta para imports
CORE_DIR = Path(__file__).resolve().parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from repository_base import AUPRepository
import sqlite3
from datetime import datetime, UTC


class OportunidadRepository(AUPRepository):
    """
    Repositorio para gestión de oportunidades de venta.
    
    Inicia el NÚCLEO 2: TRANSACCIÓN
    - Oportunidad (primera fase de venta) ← AQUÍ
    - Cotización (propuesta formal)
    - Orden de Compra (compromiso del cliente)
    - Factura (cierre financiero)
    
    REGLA R2 materializada:
        No se puede crear oportunidad sin:
        1. Prospecto válido existente
        2. Prospecto en estado "Activo"
        3. Sin duplicados de nombre por prospecto
    
    REGLA R3 vinculada:
        Al marcar oportunidad como "Ganada":
        - Prospecto cambia a estado "Cliente"
        - Se habilita la creación de cotizaciones
    """
    
    def __init__(self, usuario="system", conn=None):
        super().__init__(entidad="oportunidad", usuario=usuario, conn=conn)
        self.tabla = "oportunidades"

    # ------------------------------------------------------------
    # Crear oportunidad (REGLA R2)
    # ------------------------------------------------------------
    def crear_oportunidad(self, id_prospecto, titulo_o_nombre=None, monto_o_estimado=None,
                         titulo=None, nombre=None, monto=None, monto_estimado=None,
                         etapa="Inicial", probabilidad=0, descripcion=None):
        """
        Crea una nueva oportunidad para un prospecto activo.
        
        VALIDACIONES REGLA R2:
        - Prospecto debe existir
        - Prospecto debe estar activo (no convertido ni perdido)
        - No debe existir otra oportunidad con el mismo título para este prospecto
        
        Args:
            id_prospecto: FK a tabla prospectos
            titulo_o_nombre: Posicional 1 - título de la oportunidad
            monto_o_estimado: Posicional 2 - monto estimado
            titulo/nombre: Nombre descriptivo de la oportunidad (kwargs)
            monto/monto_estimado: Valor estimado en moneda local (kwargs)
            descripcion: Descripción detallada (opcional)
            etapa: Etapa del ciclo de venta  
            probabilidad: % de cierre (0-100)
        
        Returns:
            id_oportunidad: ID de la oportunidad creada
        
        Raises:
            ValueError: Si falla validación REGLA R2 o hay duplicados
        """
        # Compatibilidad: soporta args posicionales y kwargs
        titulo_final = titulo_o_nombre or titulo or nombre
        monto_final = monto_o_estimado or monto or monto_estimado
        
        if not titulo_final:
            raise ValueError("Debe proporcionar un título/nombre para la oportunidad")
        if monto_final is None:
            raise ValueError("Debe proporcionar un monto estimado para la oportunidad")
        
        con = self.conectar()
        cur = con.cursor()

        # 1️⃣ Validar prospecto existe
        cur.execute("""
            SELECT id_prospecto, estado, id_empresa, id_contacto
            FROM prospectos
            WHERE id_prospecto = ?
        """, (id_prospecto,))
        p = cur.fetchone()
        if not p:
            self.cerrar_conexion(con)
            raise ValueError(f"El prospecto con ID {id_prospecto} no existe.")
        
        # 2️⃣ Validar prospecto está activo (REGLA R2)
        # Estados válidos para crear oportunidad: nuevo, contactado, calificado (no convertido)
        if p["estado"] in ["convertido", "perdido"]:
            self.cerrar_conexion(con)
            raise ValueError(
                f"REGLA R2 VIOLADA: El prospecto {id_prospecto} tiene estado '{p['estado']}'. "
                f"Solo prospectos activos pueden generar oportunidades."
            )

        # 3️⃣ Verificar duplicado (titulo de oportunidad dentro del mismo prospecto)
        cur.execute("""
            SELECT id_oportunidad FROM oportunidades
            WHERE id_prospecto = ? AND titulo = ?
        """, (id_prospecto, titulo_final))
        if cur.fetchone():
            self.cerrar_conexion(con)
            raise ValueError(f"Ya existe una oportunidad con el título '{titulo_final}' para este prospecto.")

        # 4️⃣ Crear oportunidad
        data = {
            "id_prospecto": id_prospecto,
            "titulo": titulo_final,
            "descripcion": descripcion,
            "etapa": etapa,
            "probabilidad": probabilidad,
            "monto": monto_final,
            "fecha_creacion": datetime.now(UTC).isoformat()
        }
        cur.execute("""
            INSERT INTO oportunidades (id_prospecto, titulo, descripcion, etapa, probabilidad, monto, fecha_creacion)
            VALUES (:id_prospecto, :titulo, :descripcion, :etapa, :probabilidad, :monto, :fecha_creacion)
        """, data)
        con.commit()
        id_opp = cur.lastrowid
        
        # Trazabilidad forense
        self.registrar_evento(con, id_opp, "CREAR", data)
        
        self.cerrar_conexion(con)
        return id_opp

    # ------------------------------------------------------------
    # Actualizar etapa o probabilidad
    # ------------------------------------------------------------
    def actualizar_oportunidad(self, id_oportunidad, etapa=None, probabilidad=None, monto_estimado=None):
        """
        Actualiza etapa, probabilidad o monto estimado de una oportunidad.
        
        Etapas comunes:
            - Inicial: Primera detección
            - Calificación: Validando fit
            - Negociación: Discutiendo términos
            - Propuesta: Cotización enviada
            - Ganada: Cliente confirmó
            - Perdida: Descartada
        
        Args:
            id_oportunidad: ID de la oportunidad
            etapa: Nueva etapa (opcional)
            probabilidad: Nueva probabilidad 0-100 (opcional)
            monto_estimado: Nuevo monto (opcional)
        
        Raises:
            ValueError: Si oportunidad no existe o no hay campos a actualizar
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("SELECT * FROM oportunidades WHERE id_oportunidad = ?", (id_oportunidad,))
        o = cur.fetchone()
        if not o:
            self.cerrar_conexion(con)
            raise ValueError(f"Oportunidad {id_oportunidad} no existe.")

        campos = {}
        if etapa is not None:
            campos["etapa"] = etapa
        if probabilidad is not None:
            campos["probabilidad"] = probabilidad
        if monto_estimado is not None:
            campos["monto_estimado"] = monto_estimado

        if not campos:
            self.cerrar_conexion(con)
            raise ValueError("No se proporcionaron campos para actualizar.")

        set_clause = ", ".join(f"{k} = ?" for k in campos)
        params = tuple(campos.values()) + (id_oportunidad,)
        cur.execute(f"UPDATE oportunidades SET {set_clause} WHERE id_oportunidad = ?", params)
        con.commit()
        
        # Registro forense del cambio
        self.registrar_evento(con, id_oportunidad, "ACTUALIZAR", campos)
        
        self.cerrar_conexion(con)

    # ------------------------------------------------------------
    # Marcar ganada y convertir prospecto a cliente (REGLA R3)
    # ------------------------------------------------------------
    def marcar_ganada_y_convertir(self, id_oportunidad):
        """
        REGLA R3: Marca oportunidad como 'Ganada' y convierte prospecto a 'Cliente'.
        
        Esta acción:
        1. Cambia etapa de oportunidad a "Ganada"
        2. Establece probabilidad a 100%
        3. Convierte el prospecto asociado a estado "Cliente"
        4. Habilita la creación de cotizaciones y OCs
        
        Args:
            id_oportunidad: ID de la oportunidad a marcar como ganada
        
        Raises:
            ValueError: Si oportunidad no existe
        """
        con = self.conectar()
        cur = con.cursor()

        # Validar oportunidad y obtener prospecto
        cur.execute("""
            SELECT o.id_oportunidad, o.id_prospecto, p.estado
            FROM oportunidades o
            JOIN prospectos p ON p.id_prospecto = o.id_prospecto
            WHERE o.id_oportunidad = ?
        """, (id_oportunidad,))
        row = cur.fetchone()
        if not row:
            self.cerrar_conexion(con)
            raise ValueError(f"Oportunidad {id_oportunidad} no existe.")

        id_prospecto = row["id_prospecto"]

        # 1️⃣ Actualizar oportunidad a Ganada
        cur.execute("""
            UPDATE oportunidades SET etapa = 'Ganada', estado = 'ganada', probabilidad = 100
            WHERE id_oportunidad = ?
        """, (id_oportunidad,))
        con.commit()
        self.registrar_evento(con, id_oportunidad, "MARCAR_GANADA", {"etapa": "Ganada", "estado": "ganada", "probabilidad": 100})

        # 2️⃣ REGLA R3: Convertir prospecto a Cliente
        cur.execute("""
            UPDATE prospectos SET estado = 'convertido' WHERE id_prospecto = ?
        """, (id_prospecto,))
        
        # 3️⃣ REGLA R3: Actualizar empresa a tipo 'cliente'
        cur.execute("""
            UPDATE empresas SET tipo_cliente = 'cliente'
            WHERE id_empresa = (SELECT id_empresa FROM prospectos WHERE id_prospecto = ?)
        """, (id_prospecto,))
        
        # 4️⃣ REGLA R3: Vincular oportunidad al cliente (id_empresa)
        cur.execute("""
            UPDATE oportunidades SET id_cliente = (
                SELECT id_empresa FROM prospectos WHERE id_prospecto = ?
            )
            WHERE id_oportunidad = ?
        """, (id_prospecto, id_oportunidad))
        
        con.commit()
        self.registrar_evento(con, id_prospecto, "CONVERSION_CLIENTE", {
            "estado": "convertido",
            "razon": f"Oportunidad {id_oportunidad} ganada"
        })
        
        self.cerrar_conexion(con)
        return True

    # ------------------------------------------------------------
    # Listado general y por prospecto
    # ------------------------------------------------------------
    def listar(self, id_prospecto=None):
        """
        Lista todas las oportunidades o solo las de un prospecto específico.
        
        Args:
            id_prospecto: Filtrar por prospecto (opcional)
        
        Returns:
            Lista de diccionarios con información completa
        """
        con = self.conectar()
        cur = con.cursor()
        
        if id_prospecto:
            cur.execute("""
                SELECT 
                    o.id_oportunidad, 
                    o.nombre, 
                    o.etapa, 
                    o.probabilidad, 
                    o.monto_estimado, 
                    o.fecha_creacion,
                    p.id_prospecto,
                    e.nombre AS empresa,
                    c.nombre AS contacto
                FROM oportunidades o
                JOIN prospectos p ON p.id_prospecto = o.id_prospecto
                JOIN empresas e ON e.id_empresa = p.id_empresa
                JOIN contactos c ON c.id_contacto = p.id_contacto
                WHERE o.id_prospecto = ?
                ORDER BY o.fecha_creacion DESC
            """, (id_prospecto,))
        else:
            cur.execute("""
                SELECT 
                    o.id_oportunidad, 
                    o.nombre, 
                    o.etapa, 
                    o.probabilidad, 
                    o.monto_estimado,
                    o.fecha_creacion,
                    p.id_prospecto, 
                    e.nombre AS empresa, 
                    c.nombre AS contacto
                FROM oportunidades o
                JOIN prospectos p ON p.id_prospecto = o.id_prospecto
                JOIN empresas e ON e.id_empresa = p.id_empresa
                JOIN contactos c ON c.id_contacto = p.id_contacto
                ORDER BY o.fecha_creacion DESC
            """)
        
        rows = cur.fetchall()
        self.cerrar_conexion(con)
        return [dict(r) for r in rows]

    # ------------------------------------------------------------
    # Obtener oportunidad específica
    # ------------------------------------------------------------
    def obtener(self, id_oportunidad):
        """
        Obtiene información completa de una oportunidad.
        
        Args:
            id_oportunidad: ID de la oportunidad
        
        Returns:
            Diccionario con datos completos (oportunidad + prospecto + empresa + contacto)
        
        Raises:
            ValueError: Si oportunidad no existe
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("""
            SELECT 
                o.*,
                p.estado AS prospecto_estado,
                e.nombre AS empresa_nombre,
                e.rfc AS empresa_rfc,
                c.nombre AS contacto_nombre,
                c.correo AS contacto_correo
            FROM oportunidades o
            JOIN prospectos p ON p.id_prospecto = o.id_prospecto
            JOIN empresas e ON e.id_empresa = p.id_empresa
            JOIN contactos c ON c.id_contacto = p.id_contacto
            WHERE o.id_oportunidad = ?
        """, (id_oportunidad,))
        row = cur.fetchone()
        self.cerrar_conexion(con)
        
        if not row:
            raise ValueError(f"Oportunidad {id_oportunidad} no existe.")
        
        return dict(row)
    
    def obtener_por_id(self, id_oportunidad):
        """Alias de obtener() para compatibilidad con tests"""
        return self.obtener(id_oportunidad)

    # ------------------------------------------------------------
    # Estadísticas del pipeline
    # ------------------------------------------------------------
    def estadisticas_pipeline(self):
        """
        Genera estadísticas del pipeline de ventas.
        
        Returns:
            Diccionario con métricas clave del pipeline
        """
        con = self.conectar()
        cur = con.cursor()
        
        stats = {}
        
        # Total por etapa
        cur.execute("""
            SELECT etapa, COUNT(*) as total, SUM(monto_estimado) as valor_total
            FROM oportunidades
            GROUP BY etapa
        """)
        stats["por_etapa"] = {
            row["etapa"]: {"count": row["total"], "valor": row["valor_total"] or 0}
            for row in cur.fetchall()
        }
        
        # Tasa de conversión
        cur.execute("SELECT COUNT(*) as total FROM oportunidades")
        total_opp = cur.fetchone()["total"]
        
        cur.execute("SELECT COUNT(*) as ganadas FROM oportunidades WHERE etapa = 'Ganada'")
        ganadas = cur.fetchone()["ganadas"]
        
        stats["tasa_conversion"] = (ganadas / total_opp * 100) if total_opp > 0 else 0
        
        # Valor total del pipeline
        cur.execute("""
            SELECT SUM(monto_estimado * probabilidad / 100) as pipeline_ponderado
            FROM oportunidades
            WHERE etapa NOT IN ('Ganada', 'Perdida')
        """)
        stats["pipeline_ponderado"] = cur.fetchone()["pipeline_ponderado"] or 0
        
        self.cerrar_conexion(con)
        return stats

    # ------------------------------------------------------------
    # Demo de uso
    # ------------------------------------------------------------
    def demo(self):
        """
        Demostración de funcionalidad del OportunidadRepository.
        
        Prueba:
        1. Crear oportunidad con validación REGLA R2
        2. Actualizar etapa y probabilidad
        3. Listar oportunidades
        4. Marcar como ganada (REGLA R3)
        5. Estadísticas del pipeline
        """
        print("\n💼 DEMO OPORTUNIDAD REPOSITORY")
        print("=" * 60)
        
        # 1. Crear oportunidad
        print("\n1️⃣ Creando oportunidad (REGLA R2: validación prospecto activo)...")
        try:
            id_o = self.crear_oportunidad(
                id_prospecto=1,
                nombre="Oportunidad Demo - ThreatDown Licencias",
                monto_estimado=25000,
                etapa="Inicial",
                probabilidad=20
            )
            print(f"   ✅ Oportunidad creada con ID {id_o}")
        except ValueError as e:
            print(f"   ⚠️ {e}")

        # 2. Listar oportunidades
        print("\n2️⃣ Oportunidades registradas:")
        oportunidades = self.listar()
        if oportunidades:
            print(f"   📋 Total: {len(oportunidades)}")
            for o in oportunidades:
                print(f"      - {o['empresa']} / {o['contacto']} → {o['nombre']}")
                print(f"        Etapa: {o['etapa']} | Probabilidad: {o['probabilidad']}% | Monto: ${o['monto_estimado']:,.2f}")
        else:
            print("   📋 No hay oportunidades registradas")
        
        # 3. Actualizar oportunidad
        if oportunidades:
            print(f"\n3️⃣ Actualizando oportunidad ID {oportunidades[0]['id_oportunidad']}...")
            try:
                self.actualizar_oportunidad(
                    id_oportunidad=oportunidades[0]['id_oportunidad'],
                    etapa="Negociación",
                    probabilidad=40
                )
                print("   ✅ Oportunidad actualizada: Etapa=Negociación, Probabilidad=40%")
            except ValueError as e:
                print(f"   ❌ Error: {e}")
        
        # 4. Estadísticas del pipeline
        print("\n4️⃣ Estadísticas del pipeline:")
        stats = self.estadisticas_pipeline()
        print(f"   📈 Por etapa: {stats['por_etapa']}")
        print(f"   📈 Tasa de conversión: {stats['tasa_conversion']:.1f}%")
        print(f"   💰 Pipeline ponderado: ${stats['pipeline_ponderado']:,.2f}")
        
        # 5. Marcar como ganada (REGLA R3)
        if oportunidades:
            print(f"\n5️⃣ REGLA R3: Marcando oportunidad ID {oportunidades[0]['id_oportunidad']} como Ganada...")
            try:
                self.marcar_ganada_y_convertir(oportunidades[0]['id_oportunidad'])
                print("   ✅ Oportunidad marcada como Ganada")
                print("   ✅ Prospecto convertido a Cliente (REGLA R3)")
            except ValueError as e:
                print(f"   ❌ Error: {e}")
        
        print("\n" + "=" * 60)
        print("✅ NÚCLEO 2: TRANSACCIÓN - OportunidadRepository completo")
        print("   - REGLA R2 implementada ✅")
        print("   - REGLA R3 implementada ✅")
        print("=" * 60)


# ============================================================
# EJECUCIÓN DEMO
# ============================================================
if __name__ == "__main__":
    repo = OportunidadRepository()
    repo.demo()
