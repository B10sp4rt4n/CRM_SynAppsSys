# ================================================================
#  core/repository_trazabilidad.py  |  CRM-EXO v2
#  ---------------------------------------------------------------
#  Núcleo 4: Trazabilidad - Corazón de la verificación estructural
#
#  PROPÓSITO:
#    Ledger unificado de auditoría forense donde convergen todos
#    los eventos de los núcleos anteriores (Identidad, Transacción,
#    Facturación).
#
#  INCLUYE:
#    - HistorialGeneralRepository: Log de eventos completo
#    - HashRepository: Verificación de integridad SHA-256
#
#  CAPACIDADES:
#    ✓ Qué entidad se modificó
#    ✓ Cuándo y por quién
#    ✓ Qué valores cambiaron (payload JSON)
#    ✓ Cuál fue el hash resultante
#    ✓ Validación cruzada de integridad
#    ✓ Reconstrucción de eventos (NOM-151/Recordia-Bridge)
#
#  FILOSOFÍA AUP:
#    "Lo que no se puede auditar, no se puede confiar"
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
from typing import Optional, Dict, List, Any


# ================================================================
#  HISTORIAL GENERAL REPOSITORY
# ================================================================
class HistorialGeneralRepository(AUPRepository):
    """
    Repositorio para consulta del historial general de eventos.
    
    NÚCLEO 4: TRAZABILIDAD (parte 1)
    - Historial General (log de eventos) ← AQUÍ
    - Hash Registros (verificación de integridad)
    
    ESTRUCTURA:
        Cada evento registrado incluye:
        - entidad: Tabla origen (empresas, contactos, oportunidades, etc.)
        - id_entidad: ID del registro modificado
        - accion: Tipo de operación (CREAR, ACTUALIZAR, ELIMINAR, etc.)
        - usuario: Quién ejecutó la acción
        - payload: Datos completos en JSON
        - hash_evento: SHA-256 del payload
        - timestamp: Cuándo ocurrió
    
    USO:
        Auditoría completa del sistema
        Reconstrucción de eventos históricos
        Compliance (NOM-151, SOX, etc.)
        Forense digital
    """
    
    def __init__(self, usuario="system", conn=None):
        super().__init__(entidad="historial_general", usuario=usuario, conn=conn)
        self.tabla = "historial_general"

    # ------------------------------------------------------------
    # Listar últimos eventos
    # ------------------------------------------------------------
    def listar_eventos(self, limite=25, entidad=None):
        """
        Lista los eventos más recientes del sistema.
        
        Args:
            limite: Número máximo de eventos a retornar
            entidad: Filtrar por tabla origen (opcional)
        
        Returns:
            Lista de eventos ordenados por más reciente
        """
        con = self.conectar()
        cur = con.cursor()
        
        if entidad:
            cur.execute("""
                SELECT 
                    id_evento, 
                    entidad, 
                    id_entidad, 
                    accion, 
                    usuario,
                    timestamp, 
                    substr(hash_evento,1,16) AS hash_corto,
                    hash_evento
                FROM historial_general
                WHERE entidad = ?
                ORDER BY id_evento DESC
                LIMIT ?
            """, (entidad, limite))
        else:
            cur.execute("""
                SELECT 
                    id_evento, 
                    entidad, 
                    id_entidad, 
                    accion, 
                    usuario,
                    timestamp, 
                    substr(hash_evento,1,16) AS hash_corto,
                    hash_evento
                FROM historial_general
                ORDER BY id_evento DESC
                LIMIT ?
            """, (limite,))
        
        rows = cur.fetchall()
        self.cerrar_conexion(con)
        return [dict(r) for r in rows]

    # ------------------------------------------------------------
    # Buscar eventos por entidad, usuario o acción
    # ------------------------------------------------------------
    def buscar(self, texto, limite=50):
        """
        Búsqueda flexible en el historial.
        
        Args:
            texto: Texto a buscar en entidad, usuario o acción
            limite: Máximo de resultados
        
        Returns:
            Lista de eventos que coinciden
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("""
            SELECT 
                id_evento, 
                entidad, 
                id_entidad,
                accion, 
                usuario, 
                timestamp,
                substr(hash_evento,1,16) AS hash_corto
            FROM historial_general
            WHERE entidad LIKE ? OR usuario LIKE ? OR accion LIKE ?
            ORDER BY id_evento DESC
            LIMIT ?
        """, (f"%{texto}%", f"%{texto}%", f"%{texto}%", limite))
        rows = cur.fetchall()
        self.cerrar_conexion(con)
        return [dict(r) for r in rows]

    # ------------------------------------------------------------
    # Obtener detalle completo de evento
    # ------------------------------------------------------------
    def detalle_evento(self, id_evento):
        """
        Obtiene el payload completo de un evento específico.
        
        Args:
            id_evento: ID del evento
        
        Returns:
            Diccionario con toda la información del evento
        
        Raises:
            ValueError: Si evento no existe
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("""
            SELECT * FROM historial_general WHERE id_evento = ?
        """, (id_evento,))
        row = cur.fetchone()
        self.cerrar_conexion(con)
        
        if not row:
            raise ValueError(f"Evento {id_evento} no existe.")
        
        return dict(row)

    # ------------------------------------------------------------
    # Obtener línea de tiempo de una entidad
    # ------------------------------------------------------------
    def linea_tiempo(self, entidad, id_entidad):
        """
        Reconstruye la historia completa de un registro.
        
        Args:
            entidad: Tabla origen (ej: 'empresas', 'oportunidades')
            id_entidad: ID del registro
        
        Returns:
            Lista cronológica de todos los eventos del registro
        """
        con = self.conectar()
        cur = con.cursor()
        cur.execute("""
            SELECT 
                id_evento,
                accion,
                usuario,
                timestamp,
                valor_anterior,
                valor_nuevo,
                hash_evento
            FROM historial_general
            WHERE entidad = ? AND id_entidad = ?
            ORDER BY id_evento ASC
        """, (entidad, id_entidad))
        rows = cur.fetchall()
        self.cerrar_conexion(con)
        return [dict(r) for r in rows]

    # ------------------------------------------------------------
    # Estadísticas del historial
    # ------------------------------------------------------------
    def estadisticas(self):
        """
        Genera estadísticas del historial de eventos.
        
        Returns:
            Diccionario con métricas de auditoría
        """
        con = self.conectar()
        cur = con.cursor()
        
        stats = {}
        
        # Total de eventos
        cur.execute("SELECT COUNT(*) as total FROM historial_general")
        stats["total_eventos"] = cur.fetchone()["total"]
        
        # Por entidad
        cur.execute("""
            SELECT entidad, COUNT(*) as count
            FROM historial_general
            GROUP BY entidad
            ORDER BY count DESC
        """)
        stats["por_entidad"] = {row["entidad"]: row["count"] for row in cur.fetchall()}
        
        # Por acción
        cur.execute("""
            SELECT accion, COUNT(*) as count
            FROM historial_general
            GROUP BY accion
            ORDER BY count DESC
        """)
        stats["por_accion"] = {row["accion"]: row["count"] for row in cur.fetchall()}
        
        # Por usuario
        cur.execute("""
            SELECT usuario, COUNT(*) as count
            FROM historial_general
            GROUP BY usuario
            ORDER BY count DESC
            LIMIT 10
        """)
        stats["top_usuarios"] = {row["usuario"]: row["count"] for row in cur.fetchall()}
        
        self.cerrar_conexion(con)
        return stats


# ================================================================
#  HASH REPOSITORY
# ================================================================
class HashRepository(AUPRepository):
    """
    Repositorio para verificación de integridad mediante hashes.
    
    NÚCLEO 4: TRAZABILIDAD (parte 2)
    - Historial General (log de eventos)
    - Hash Registros (verificación de integridad) ← AQUÍ
    
    PROPÓSITO:
        Mantener registro independiente de hashes SHA-256 para
        validación cruzada con historial_general.
    
    VERIFICACIÓN:
        Compara hashes entre:
        - hash_registros (tabla independiente)
        - historial_general (log de eventos)
        
        Si coinciden → Integridad OK
        Si difieren → Posible modificación no autorizada
    
    USO:
        Auditoría forense
        Detección de tampering
        Compliance regulatorio
    """
    
    def __init__(self, usuario="system", conn=None):
        super().__init__(entidad="hash_registros", usuario=usuario, conn=conn)
        self.tabla = "hash_registros"

    # ------------------------------------------------------------
    # Listar hashes recientes
    # ------------------------------------------------------------
    def listar(self, limite=25, tabla_origen=None):
        """
        Lista los hashes más recientes.
        
        Args:
            limite: Número máximo de hashes a retornar
            tabla_origen: Filtrar por tabla (opcional)
        
        Returns:
            Lista de hashes ordenados por más reciente
        """
        con = self.conectar()
        cur = con.cursor()
        
        if tabla_origen:
            cur.execute("""
                SELECT 
                    id_hash, 
                    tabla_origen AS entidad, 
                    id_registro,
                    substr(hash_sha256,1,16) AS hash_corto,
                    hash_sha256,
                    timestamp
                FROM hash_registros
                WHERE tabla_origen = ?
                ORDER BY id_hash DESC
                LIMIT ?
            """, (tabla_origen, limite))
        else:
            cur.execute("""
                SELECT 
                    id_hash, 
                    tabla_origen AS entidad, 
                    id_registro,
                    substr(hash_sha256,1,16) AS hash_corto,
                    hash_sha256,
                    timestamp
                FROM hash_registros
                ORDER BY id_hash DESC
                LIMIT ?
            """, (limite,))
        
        rows = cur.fetchall()
        self.cerrar_conexion(con)
        return [dict(r) for r in rows]

    # ------------------------------------------------------------
    # Verificar integridad cruzada
    # ------------------------------------------------------------
    def verificar_integridad_cruzada(self, tabla_origen, id_registro):
        """
        Compara el último hash guardado con el evento más reciente
        del historial_general para la misma entidad.
        
        VALIDACIÓN CRUZADA:
            1. Obtiene último hash de hash_registros
            2. Obtiene último hash de historial_general
            3. Compara ambos
        
        Args:
            tabla_origen: Tabla de origen (ej: 'empresas')
            id_registro: ID del registro
        
        Returns:
            Diccionario con resultado de verificación
        """
        con = self.conectar()
        cur = con.cursor()

        # Hash desde hash_registros
        cur.execute("""
            SELECT hash_sha256 FROM hash_registros
            WHERE tabla_origen = ? AND id_registro = ?
            ORDER BY id_hash DESC LIMIT 1
        """, (tabla_origen, id_registro))
        hash_reg = cur.fetchone()

        # Hash desde historial_general
        cur.execute("""
            SELECT hash_evento FROM historial_general
            WHERE entidad = ? AND id_entidad = ?
            ORDER BY id_evento DESC LIMIT 1
        """, (tabla_origen, id_registro))
        hash_event = cur.fetchone()

        self.cerrar_conexion(con)
        
        if not hash_reg or not hash_event:
            return {
                "resultado": "sin_datos",
                "mensaje": "No hay suficientes datos para verificar integridad"
            }

        integridad_ok = hash_reg[0] == hash_event[0]
        
        return {
            "tabla_origen": tabla_origen,
            "id_registro": id_registro,
            "hash_registro": hash_reg[0][:32] + "...",
            "hash_evento": hash_event[0][:32] + "...",
            "hash_completo_registro": hash_reg[0],
            "hash_completo_evento": hash_event[0],
            "integridad_ok": integridad_ok,
            "mensaje": "✅ Integridad verificada" if integridad_ok else "❌ ALERTA: Hashes no coinciden"
        }

    # ------------------------------------------------------------
    # Auditoría masiva de integridad
    # ------------------------------------------------------------
    def auditoria_completa(self):
        """
        Verifica la integridad de todos los registros con hash.
        
        Returns:
            Diccionario con resultados de auditoría
        """
        con = self.conectar()
        cur = con.cursor()
        
        # Obtener todos los registros únicos
        cur.execute("""
            SELECT DISTINCT tabla_origen, id_registro
            FROM hash_registros
        """)
        registros = cur.fetchall()
        self.cerrar_conexion(con)
        
        resultados = {
            "total_verificados": 0,
            "integridad_ok": 0,
            "integridad_error": 0,
            "sin_datos": 0,
            "detalles": []
        }
        
        for reg in registros:
            resultado = self.verificar_integridad_cruzada(
                reg["tabla_origen"],
                reg["id_registro"]
            )
            
            resultados["total_verificados"] += 1
            
            if resultado.get("resultado") == "sin_datos":
                resultados["sin_datos"] += 1
            elif resultado.get("integridad_ok"):
                resultados["integridad_ok"] += 1
            else:
                resultados["integridad_error"] += 1
                resultados["detalles"].append(resultado)
        
        return resultados

    # ------------------------------------------------------------
    # Estadísticas de hashes
    # ------------------------------------------------------------
    def estadisticas(self):
        """
        Genera estadísticas de hashes registrados.
        
        Returns:
            Diccionario con métricas
        """
        con = self.conectar()
        cur = con.cursor()
        
        stats = {}
        
        # Total de hashes
        cur.execute("SELECT COUNT(*) as total FROM hash_registros")
        stats["total_hashes"] = cur.fetchone()["total"]
        
        # Por tabla
        cur.execute("""
            SELECT tabla_origen, COUNT(*) as count
            FROM hash_registros
            GROUP BY tabla_origen
            ORDER BY count DESC
        """)
        stats["por_tabla"] = {row["tabla_origen"]: row["count"] for row in cur.fetchall()}
        
        self.cerrar_conexion(con)
        return stats


# ================================================================
#  DEMO UNIFICADO - NÚCLEO 4: TRAZABILIDAD
# ================================================================
def demo():
    """
    Demostración completa del NÚCLEO 4: TRAZABILIDAD.
    
    Prueba:
    1. Listar eventos recientes
    2. Listar hashes recientes
    3. Verificación cruzada de integridad
    4. Línea de tiempo de una entidad
    5. Estadísticas de auditoría
    6. Auditoría masiva de integridad
    """
    print("\n🔎 DEMO TRAZABILIDAD CRM-EXO v2")
    print("=" * 60)

    h_repo = HistorialGeneralRepository(usuario="demo")
    hash_repo = HashRepository(usuario="demo")

    # 1️⃣ Últimos eventos
    print("\n1️⃣ Últimos 10 eventos del sistema:")
    eventos = h_repo.listar_eventos(10)
    if eventos:
        print(f"   📜 Total mostrado: {len(eventos)}")
        for e in eventos:
            print(f"      [{e['id_evento']:3d}] {e['entidad']:20s} → {e['accion']:15s} by {e['usuario']:10s} | {e['hash_corto']}")
    else:
        print("   📜 No hay eventos registrados")

    # 2️⃣ Últimos hashes
    print("\n2️⃣ Últimos 10 hashes forenses:")
    hashes = hash_repo.listar(10)
    if hashes:
        print(f"   🔐 Total mostrado: {len(hashes)}")
        for h in hashes:
            print(f"      {h['tabla_origen']:20s}[{h['id_registro']:3d}] → {h['hash_corto']} ({h['timestamp']})")
    else:
        print("   🔐 No hay hashes registrados")

    # 3️⃣ Verificación cruzada
    if hashes:
        muestra = hashes[0]
        print(f"\n3️⃣ Verificación cruzada de integridad:")
        print(f"   Entidad: {muestra['tabla_origen']}[{muestra['id_registro']}]")
        res = hash_repo.verificar_integridad_cruzada(
            muestra["tabla_origen"], 
            muestra["id_registro"]
        )
        print(f"   {res['mensaje']}")
        if not res.get('integridad_ok', True):
            print(f"   ⚠️ Hash Registro: {res['hash_registro']}")
            print(f"   ⚠️ Hash Evento:   {res['hash_evento']}")

    # 4️⃣ Línea de tiempo
    print("\n4️⃣ Línea de tiempo de 'empresas' ID 1:")
    linea = h_repo.linea_tiempo("empresas", 1)
    if linea:
        print(f"   📅 Total eventos: {len(linea)}")
        for evento in linea[:5]:  # Mostrar primeros 5
            print(f"      {evento['timestamp'][:19]} | {evento['accion']:15s} by {evento['usuario']}")
    else:
        print("   📅 Sin eventos para esta entidad")

    # 5️⃣ Estadísticas historial
    print("\n5️⃣ Estadísticas del Historial General:")
    stats_h = h_repo.estadisticas()
    print(f"   📊 Total eventos: {stats_h['total_eventos']}")
    print(f"   📊 Por entidad: {stats_h['por_entidad']}")
    print(f"   📊 Por acción: {stats_h['por_accion']}")

    # 6️⃣ Estadísticas hashes
    print("\n6️⃣ Estadísticas de Hashes:")
    stats_hash = hash_repo.estadisticas()
    print(f"   🔐 Total hashes: {stats_hash['total_hashes']}")
    print(f"   🔐 Por tabla: {stats_hash['por_tabla']}")

    # 7️⃣ Auditoría masiva
    print("\n7️⃣ Auditoría masiva de integridad:")
    auditoria = hash_repo.auditoria_completa()
    print(f"   🔍 Registros verificados: {auditoria['total_verificados']}")
    print(f"   ✅ Integridad OK: {auditoria['integridad_ok']}")
    print(f"   ❌ Errores: {auditoria['integridad_error']}")
    print(f"   ⚠️ Sin datos: {auditoria['sin_datos']}")
    
    if auditoria['detalles']:
        print("\n   ⚠️ Registros con problemas de integridad:")
        for detalle in auditoria['detalles']:
            print(f"      - {detalle['tabla_origen']}[{detalle['id_registro']}]: {detalle['mensaje']}")

    print("\n" + "=" * 60)
    print("✅ NÚCLEO 4: TRAZABILIDAD COMPLETO")
    print("   - HistorialGeneralRepository ✅")
    print("   - HashRepository ✅")
    print("   - Verificación cruzada de integridad ✅")
    print("   - Auditoría forense ✅")
    print("   - Línea de tiempo de entidades ✅")
    print("   - Compliance (NOM-151/Recordia-Bridge ready) ✅")
    print("=" * 60)


if __name__ == "__main__":
    demo()
