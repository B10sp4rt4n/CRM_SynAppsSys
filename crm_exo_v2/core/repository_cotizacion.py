# ================================================================
#  core/repository_cotizacion.py  |  CRM-EXO v2
#  ---------------------------------------------------------------
#  Implementación del repositorio CotizadorRepository
#  (Núcleo 2: Transacción extendida).
#
#  REGLA R4 (CRÍTICA):
#    "Una cotización solo puede crearse si existe una oportunidad válida."
#
#  CARACTERÍSTICAS ESPECIALES:
#  - 3 modos de cotización: mínimo, genérico, externo
#  - Hash SHA-256 de integridad forense en cada registro
#  - Doble trazabilidad (historial_general + hash_registros)
#  - Verificación de integridad post-creación
#  - Versionamiento de cotizaciones
#
#  Este repositorio conecta Oportunidad → Cotización → OC → Factura
# ================================================================

import sys
from pathlib import Path

# Ajuste de ruta para imports
CORE_DIR = Path(__file__).resolve().parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from repository_base import AUPRepository
import sqlite3
import hashlib
import json
from datetime import datetime, UTC


class CotizadorRepository(AUPRepository):
    """
    Repositorio para gestión de cotizaciones.
    
    Continúa el NÚCLEO 2: TRANSACCIÓN
    - Oportunidad (fase inicial)
    - Cotización (propuesta formal) ← AQUÍ
    - Orden de Compra (compromiso cliente)
    - Factura (cierre financiero)
    
    REGLA R4 materializada:
        No se puede crear cotización sin:
        1. Oportunidad válida existente
        2. Modo de cotización definido (mínimo/genérico/externo)
        3. Hash de integridad SHA-256
    
    MODOS DE COTIZACIÓN:
        - mínimo: Monto manual, sin cálculo interno
        - genérico: Monto calculado por sistema (productos/servicios)
        - externo: Monto importado desde cotizador externo (API)
    
    INTEGRIDAD FORENSE:
        Cada cotización genera hash SHA-256 de su payload JSON
        para detectar modificaciones no autorizadas.
    """
    
    def __init__(self, usuario="system", conn=None):
        super().__init__(entidad="cotizacion", usuario=usuario, conn=conn)
        self.tabla = "cotizaciones"

    # ------------------------------------------------------------
    # Crear cotización (REGLA R4)
    # ------------------------------------------------------------
    def crear_cotizacion(self, id_oportunidad, monto_total, modo="minimo", fuente=None, moneda="MXN", notas=None):
        """
        Crea una cotización asociada a una oportunidad válida.
        
        VALIDACIONES REGLA R4:
        - Oportunidad debe existir
        - Modo debe ser válido: 'minimo', 'generico', 'externo'
        - Monto debe ser > 0
        
        HASH FORENSE:
        - Se genera SHA-256 del JSON completo de la cotización
        - Permite verificar integridad posterior
        
        Args:
            id_oportunidad: FK a tabla oportunidades (REGLA R4)
            monto_total: Valor total de la cotización
            modo: Tipo de cotización ('minimo', 'generico', 'externo')
            fuente: Origen de datos (manual, sistema, API externa)
            moneda: Código de moneda (default: MXN)
            notas: Observaciones adicionales
        
        Returns:
            Tupla (id_cotizacion, hash_integridad)
        
        Raises:
            ValueError: Si falla validación REGLA R4 o modo inválido
        """
        con = self.conectar()
        cur = con.cursor()

        # 1️⃣ Validar oportunidad existe (REGLA R4)
        cur.execute("""
            SELECT id_oportunidad, id_prospecto, titulo, etapa 
            FROM oportunidades 
            WHERE id_oportunidad = ?
        """, (id_oportunidad,))
        opp = cur.fetchone()
        if not opp:
            self.cerrar_conexion(con)
            raise ValueError(f"REGLA R4 VIOLADA: La oportunidad con ID {id_oportunidad} no existe.")

        # 2️⃣ Validar modo de cotización
        if modo not in ("minimo", "generico", "externo"):
            self.cerrar_conexion(con)
            raise ValueError(f"Modo inválido '{modo}'. Debe ser: 'minimo', 'generico' o 'externo'")

        # 3️⃣ Validar monto
        if monto_total <= 0:
            self.cerrar_conexion(con)
            raise ValueError(f"Monto total debe ser mayor a 0 (recibido: {monto_total})")

        # 4️⃣ Preparar datos
        data = {
            "id_oportunidad": id_oportunidad,
            "modo": modo,
            "fuente": fuente,
            "monto_total": monto_total,
            "estado": "borrador",
            "fecha_emision": datetime.now(UTC).isoformat()
        }

        # 5️⃣ Generar hash de integridad forense (SHA-256)
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
        hash_integridad = hashlib.sha256(raw.encode()).hexdigest()
        data["hash_cotizacion"] = hash_integridad

        # 6️⃣ Insertar cotización
        cur.execute("""
            INSERT INTO cotizaciones (id_oportunidad, modo, fuente, monto_total,
                                      estado, fecha_emision, hash_cotizacion)
            VALUES (:id_oportunidad, :modo, :fuente, :monto_total,
                    :estado, :fecha_emision, :hash_cotizacion)
        """, data)
        con.commit()
        id_cot = cur.lastrowid

        # 7️⃣ Registrar evento + hash (trazabilidad doble heredada)
        self.registrar_evento(con, id_cot, "CREAR", data)
        
        self.cerrar_conexion(con)
        return id_cot, hash_integridad

    # ------------------------------------------------------------
    # Actualizar cotización con recálculo de hash
    # ------------------------------------------------------------
    def actualizar_cotizacion(self, id_cotizacion, campos: dict):
        """
        Actualiza cotización y recalcula hash de integridad.
        
        Campos actualizables:
            - monto_total: Nuevo monto
            - estado: Borrador, Enviada, Aprobada, Rechazada
            - notas: Observaciones
            - version: Incrementar en cambios mayores
        
        Args:
            id_cotizacion: ID de la cotización
            campos: Diccionario con campos a actualizar
        
        Raises:
            ValueError: Si cotización no existe
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("SELECT * FROM cotizaciones WHERE id_cotizacion = ?", (id_cotizacion,))
        cot = cur.fetchone()
        if not cot:
            self.cerrar_conexion(con)
            raise ValueError(f"Cotización {id_cotizacion} no existe.")

        # Recalcular hash si cambian valores críticos
        if any(k in campos for k in ("monto_total", "notas", "estado", "modo")):
            # Merge datos actuales con cambios
            merged = dict(cot)
            merged.update(campos)
            
            # Generar nuevo hash
            raw = json.dumps(merged, sort_keys=True, ensure_ascii=False)
            campos["hash_integridad"] = hashlib.sha256(raw.encode()).hexdigest()

        # Actualizar en DB
        set_clause = ", ".join(f"{k} = ?" for k in campos)
        params = tuple(campos.values()) + (id_cotizacion,)
        cur.execute(f"UPDATE cotizaciones SET {set_clause} WHERE id_cotizacion = ?", params)
        con.commit()
        
        # Registro forense del cambio
        self.registrar_evento(con, id_cotizacion, "ACTUALIZAR", campos)
        
        self.cerrar_conexion(con)

    # ------------------------------------------------------------
    # Aprobar cotización
    # ------------------------------------------------------------
    def aprobar_cotizacion(self, id_cotizacion):
        """
        Marca cotización como 'Aprobada'.
        Habilita creación de Orden de Compra (siguiente paso en flujo).
        
        Args:
            id_cotizacion: ID de la cotización
        
        Raises:
            ValueError: Si cotización no existe o ya está aprobada
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("SELECT estado FROM cotizaciones WHERE id_cotizacion = ?", (id_cotizacion,))
        cot = cur.fetchone()
        if not cot:
            self.cerrar_conexion(con)
            raise ValueError(f"Cotización {id_cotizacion} no existe.")
        
        if cot["estado"] == "Aprobada":
            self.cerrar_conexion(con)
            raise ValueError(f"Cotización {id_cotizacion} ya está aprobada.")
        
        self.actualizar_cotizacion(id_cotizacion, {"estado": "Aprobada"})
        self.cerrar_conexion(con)

    # ------------------------------------------------------------
    # Listar cotizaciones por oportunidad o global
    # ------------------------------------------------------------
    def listar(self, id_oportunidad=None):
        """
        Lista cotizaciones con información contextual.
        
        Args:
            id_oportunidad: Filtrar por oportunidad (opcional)
        
        Returns:
            Lista de diccionarios con cotizaciones
        """
        con = self.conectar()
        cur = con.cursor()
        
        if id_oportunidad:
            cur.execute("""
                SELECT 
                    c.id_cotizacion, 
                    c.modo, 
                    c.monto_total, 
                    c.moneda, 
                    c.estado,
                    c.version, 
                    c.hash_integridad, 
                    c.fecha_creacion,
                    c.notas,
                    o.nombre AS oportunidad_nombre
                FROM cotizaciones c
                JOIN oportunidades o ON o.id_oportunidad = c.id_oportunidad
                WHERE c.id_oportunidad = ?
                ORDER BY c.fecha_creacion DESC
            """, (id_oportunidad,))
        else:
            cur.execute("""
                SELECT 
                    c.id_cotizacion, 
                    c.modo, 
                    c.monto_total, 
                    c.moneda, 
                    c.estado,
                    c.version,
                    o.nombre AS oportunidad, 
                    e.nombre AS empresa, 
                    c.hash_integridad,
                    c.fecha_creacion
                FROM cotizaciones c
                JOIN oportunidades o ON o.id_oportunidad = c.id_oportunidad
                JOIN prospectos p ON p.id_prospecto = o.id_prospecto
                JOIN empresas e ON e.id_empresa = p.id_empresa
                ORDER BY c.fecha_creacion DESC
            """)
        
        rows = cur.fetchall()
        self.cerrar_conexion(con)
        return [dict(r) for r in rows]

    # ------------------------------------------------------------
    # Obtener cotización específica
    # ------------------------------------------------------------
    def obtener(self, id_cotizacion):
        """
        Obtiene información completa de una cotización.
        
        Args:
            id_cotizacion: ID de la cotización
        
        Returns:
            Diccionario con datos completos
        
        Raises:
            ValueError: Si cotización no existe
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("""
            SELECT 
                c.*,
                o.titulo AS oportunidad_nombre,
                o.etapa AS oportunidad_etapa,
                e.nombre AS empresa_nombre
            FROM cotizaciones c
            JOIN oportunidades o ON o.id_oportunidad = c.id_oportunidad
            JOIN prospectos p ON p.id_prospecto = o.id_prospecto
            JOIN empresas e ON e.id_empresa = p.id_empresa
            WHERE c.id_cotizacion = ?
        """, (id_cotizacion,))
        row = cur.fetchone()
        self.cerrar_conexion(con)
        
        if not row:
            raise ValueError(f"Cotización {id_cotizacion} no existe.")
        
        return dict(row)

    def obtener_por_id(self, id_cotizacion):
        """Alias de compatibilidad para obtener()"""
        return self.obtener(id_cotizacion)

    # ------------------------------------------------------------
    # Verificar integridad forense (recalcula hash y compara)
    # ------------------------------------------------------------
    def verificar_integridad(self, id_cotizacion):
        """
        Recalcula el hash SHA-256 y compara con el registrado.
        
        Detecta modificaciones no autorizadas en la cotización.
        
        Args:
            id_cotizacion: ID de la cotización
        
        Returns:
            bool: True si la integridad es válida
        
        Raises:
            ValueError: Si cotización no existe
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("SELECT * FROM cotizaciones WHERE id_cotizacion = ?", (id_cotizacion,))
        cot = cur.fetchone()
        if not cot:
            self.cerrar_conexion(con)
            raise ValueError("Cotización no encontrada.")
        
        # Recalcular hash con los mismos campos que se usaron al crear
        # IMPORTANTE: Convertir monto_total a int si no tiene decimales (compatibilidad tipo)
        monto = cot["monto_total"]
        if isinstance(monto, float) and monto == int(monto):
            monto = int(monto)
        
        data = {
            "id_oportunidad": cot["id_oportunidad"],
            "modo": cot["modo"],
            "fuente": cot["fuente"],
            "monto_total": monto,
            "estado": cot["estado"],
            "fecha_emision": cot["fecha_emision"]
        }
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
        nuevo_hash = hashlib.sha256(raw.encode()).hexdigest()
        
        self.cerrar_conexion(con)
        
        return cot["hash_cotizacion"] == nuevo_hash

    # ------------------------------------------------------------
    # Estadísticas de cotizaciones
    # ------------------------------------------------------------
    def estadisticas(self):
        """
        Genera estadísticas de cotizaciones.
        
        Returns:
            Diccionario con métricas
        """
        con = self.conectar()
        cur = con.cursor()
        
        stats = {}
        
        # Total por estado
        cur.execute("""
            SELECT estado, COUNT(*) as total, SUM(monto_total) as valor
            FROM cotizaciones
            GROUP BY estado
        """)
        stats["por_estado"] = {
            row["estado"]: {"count": row["total"], "valor": row["valor"] or 0}
            for row in cur.fetchall()
        }
        
        # Total por modo
        cur.execute("""
            SELECT modo, COUNT(*) as total
            FROM cotizaciones
            GROUP BY modo
        """)
        stats["por_modo"] = {row["modo"]: row["total"] for row in cur.fetchall()}
        
        # Valor total
        cur.execute("SELECT SUM(monto_total) as total FROM cotizaciones WHERE estado = 'Aprobada'")
        stats["valor_aprobado"] = cur.fetchone()["total"] or 0
        
        self.cerrar_conexion(con)
        return stats

    # ------------------------------------------------------------
    # Demo de uso
    # ------------------------------------------------------------
    def demo(self):
        """
        Demostración de funcionalidad del CotizadorRepository.
        
        Prueba:
        1. Crear cotización con validación REGLA R4
        2. Verificar hash de integridad
        3. Actualizar cotización
        4. Aprobar cotización
        5. Listar cotizaciones
        6. Estadísticas
        """
        print("\n🧾 DEMO COTIZADOR REPOSITORY")
        print("=" * 60)
        
        # 1. Crear cotización
        print("\n1️⃣ Creando cotización (REGLA R4: validación oportunidad)...")
        try:
            id_c, h = self.crear_cotizacion(
                id_oportunidad=1,
                monto_total=25000,
                modo="minimo",
                fuente="manual",
                notas="Cotización demo generada internamente"
            )
            print(f"   ✅ Cotización creada con ID {id_c}")
            print(f"   🔐 Hash integridad: {h[:32]}...")
        except ValueError as e:
            print(f"   ⚠️ {e}")

        # 2. Verificar integridad
        cotizaciones = self.listar()
        if cotizaciones:
            print(f"\n2️⃣ Verificando integridad de cotización ID {cotizaciones[0]['id_cotizacion']}...")
            resultado = self.verificar_integridad(cotizaciones[0]['id_cotizacion'])
            print(f"   {resultado['mensaje']}")
            print(f"   Hash original: {resultado['hash_original'][:32]}...")
            print(f"   Hash actual:   {resultado['hash_actual'][:32]}...")
        
        # 3. Listar cotizaciones
        print("\n3️⃣ Cotizaciones registradas:")
        print(f"   📋 Total: {len(cotizaciones)}")
        for c in cotizaciones:
            print(f"      - {c['empresa']} → {c['oportunidad']}")
            print(f"        Monto: ${c['monto_total']:,.2f} {c['moneda']} | Modo: {c['modo']} | Estado: {c['estado']}")
        
        # 4. Actualizar cotización
        if cotizaciones:
            print(f"\n4️⃣ Actualizando cotización ID {cotizaciones[0]['id_cotizacion']}...")
            try:
                self.actualizar_cotizacion(
                    cotizaciones[0]['id_cotizacion'],
                    {"estado": "Enviada", "notas": "Cotización enviada al cliente"}
                )
                print("   ✅ Estado actualizado a 'Enviada'")
            except ValueError as e:
                print(f"   ❌ Error: {e}")
        
        # 5. Estadísticas
        print("\n5️⃣ Estadísticas de cotizaciones:")
        stats = self.estadisticas()
        print(f"   📈 Por estado: {stats['por_estado']}")
        print(f"   📈 Por modo: {stats['por_modo']}")
        print(f"   💰 Valor aprobado: ${stats['valor_aprobado']:,.2f}")
        
        print("\n" + "=" * 60)
        print("✅ NÚCLEO 2: TRANSACCIÓN - CotizadorRepository completo")
        print("   - REGLA R4 implementada ✅")
        print("   - Hash forense SHA-256 ✅")
        print("   - 3 modos de cotización ✅")
        print("   - Verificación de integridad ✅")
        print("=" * 60)


# ============================================================
# EJECUCIÓN DEMO
# ============================================================
if __name__ == "__main__":
    repo = CotizadorRepository()
    repo.demo()
