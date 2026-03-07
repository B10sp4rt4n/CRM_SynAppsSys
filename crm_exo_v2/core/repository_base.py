# ================================================================
#  core/repository_base.py  |  CRM-EXO v2
#  ---------------------------------------------------------------
#  Clase base AUPRepository: patrón universal de datos con trazabilidad,
#  hash estructural JSON y validación de integridad.
#
#  Se hereda por todos los repositorios del sistema.
#  
#  FILOSOFÍA AUP:
#  - "Fallos tolerados, estructura no"
#  - Hash forense en cada operación (SHA-256)
#  - Trazabilidad doble (historial_general + hash_registros)
#  - Validación de integridad automática
#  - Commit seguro con rollback en caso de error
# ================================================================

import sqlite3
import hashlib
import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional, Dict, List, Any

try:
    from .db_runtime import get_sqlite_db_path
except ImportError:
    from db_runtime import get_sqlite_db_path


# ================================================================
#  CONFIGURACIÓN GLOBAL
# ================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = get_sqlite_db_path(BASE_DIR.parent)


# ================================================================
#  CLASE BASE UNIVERSAL
# ================================================================

class AUPRepository:
    """
    Clase base para repositorios AUP-EXO v2.
    
    Características:
      - Conexión SQLite centralizada con row_factory
      - Inserciones/actualizaciones seguras con commit controlado
      - Registro automático en historial_general y hash_registros
      - Hash JSON estructurado SHA-256 con payload normalizado
      - Validación de integridad y foreign keys
      - Modo demo para testing estructural
    
    Uso:
    >>> class EmpresaRepository(AUPRepository):
    >>>     def __init__(self, usuario="system"):
    >>>         super().__init__(entidad="empresa", usuario=usuario)
    >>>     
    >>>     def crear_empresa(self, nombre, rfc):
    >>>         data = {"nombre": nombre, "rfc": rfc}
    >>>         return self.crear("empresas", data)
    """

    def __init__(self, entidad: str, usuario: str = "system", conn: Optional[sqlite3.Connection] = None):
        """
        Inicializa el repositorio base
        
        Args:
            entidad: Nombre de la entidad (empresa, contacto, prospecto, etc.)
            usuario: Usuario que realiza las operaciones (para trazabilidad)
            conn: Conexión SQLite externa (para testing con DB temporal)
        """
        self.entidad = entidad
        self.usuario = usuario
        self._external_conn = conn  # Conexión inyectada para tests
        if not conn:  # Solo validar DB_PATH si no hay conexión externa
            self._validate_db_path()

    # ------------------------------------------------------------
    # Validación inicial
    # ------------------------------------------------------------
    def _validate_db_path(self):
        """Valida que la base de datos exista"""
        if not DB_PATH.exists():
            raise FileNotFoundError(
                f"Base de datos no encontrada: {DB_PATH}\n"
                f"Ejecuta 'python init_db_v2.py' para crearla."
            )

    # ------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------
    def conectar(self) -> sqlite3.Connection:
        """
        Establece conexión SQLite con configuración AUP.
        Soporta inyección de conexión para testing.
        
        Returns:
            sqlite3.Connection: Conexión configurada con row_factory y FK habilitadas
        """
        # Si existe conexión externa inyectada (testing), usarla
        if hasattr(self, '_external_conn') and self._external_conn:
            return self._external_conn
        
        # Conexión normal a DB de producción
        con = sqlite3.connect(str(DB_PATH))
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con
    
    def cerrar_conexion(self, con: sqlite3.Connection):
        """
        Cierra la conexión solo si NO es externa (inyectada para testing).
        En testing, la conexión se maneja externamente y no debe cerrarse.
        """
        if not (hasattr(self, '_external_conn') and self._external_conn):
            con.close()

    # ------------------------------------------------------------
    # Hash estructurado (SHA-256 JSON)
    # ------------------------------------------------------------
    def generar_hash(self, accion: str, valores: Dict[str, Any]) -> tuple[str, Dict]:
        """
        Genera hash forense JSON-SHA256 con campos normalizados
        
        El hash incluye:
        - entidad: Tipo de entidad afectada
        - accion: Operación realizada (CREAR, ACTUALIZAR, ELIMINAR)
        - valores: Datos de la operación
        - usuario: Responsable de la acción
        - timestamp: Momento exacto UTC
        
        Args:
            accion: Tipo de acción (CREAR, ACTUALIZAR, ELIMINAR, etc.)
            valores: Diccionario con los datos de la operación
        
        Returns:
            tuple: (hash_sha256, payload_completo)
        """
        payload = {
            "entidad": self.entidad,
            "accion": accion,
            "valores": valores,
            "usuario": self.usuario,
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        # JSON normalizado (sorted keys, sin espacios, UTF-8)
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        hash_forense = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        
        return hash_forense, payload

    # ------------------------------------------------------------
    # Registro de evento forense
    # ------------------------------------------------------------
    def registrar_evento(self, con: sqlite3.Connection, id_entidad: int, 
                        accion: str, valor_nuevo: Dict, valor_anterior: Optional[Dict] = None) -> str:
        """
        Registra evento en historial_general + hash_registros
        
        TRAZABILIDAD DOBLE:
        1. historial_general: Evento completo con hash
        2. hash_registros: Hash independiente para verificación
        
        Args:
            con: Conexión SQLite activa
            id_entidad: ID del registro afectado
            accion: Tipo de acción
            valor_nuevo: Nuevo estado
            valor_anterior: Estado previo (opcional)
        
        Returns:
            str: Hash SHA-256 del evento
        """
        hash_evt, payload = self.generar_hash(accion, valor_nuevo)
        
        # Insertar en historial_general
        con.execute("""
            INSERT INTO historial_general
            (entidad, id_entidad, accion, valor_anterior, valor_nuevo, usuario, timestamp, hash_evento)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.entidad,
            id_entidad,
            accion,
            json.dumps(valor_anterior) if valor_anterior else None,
            json.dumps(valor_nuevo),
            self.usuario,
            payload["timestamp"],
            hash_evt
        ))
        
        # Insertar en hash_registros (trazabilidad independiente)
        con.execute("""
            INSERT INTO hash_registros (tabla_origen, id_registro, hash_sha256)
            VALUES (?, ?, ?)
        """, (self.entidad, id_entidad, hash_evt))
        
        con.commit()
        return hash_evt

    # ------------------------------------------------------------
    # Creación genérica (INSERT)
    # ------------------------------------------------------------
    def crear(self, tabla: str, data: Dict[str, Any]) -> int:
        """
        Crea un nuevo registro con trazabilidad automática
        
        COMMIT SEGURO:
        - Si falla la inserción → rollback automático
        - Si falla el registro de evento → rollback total
        
        Args:
            tabla: Nombre de la tabla
            data: Diccionario con columnas y valores
        
        Returns:
            int: ID del registro creado
        
        Raises:
            sqlite3.IntegrityError: Si viola foreign keys o constraints
        """
        con = self.conectar()
        try:
            cols = ", ".join(data.keys())
            marks = ", ".join("?" for _ in data)
            cur = con.cursor()
            
            cur.execute(f"INSERT INTO {tabla} ({cols}) VALUES ({marks})", tuple(data.values()))
            id_entidad = cur.lastrowid
            
            # Registro forense
            self.registrar_evento(con, id_entidad, "CREAR", data)
            
            return id_entidad
        
        except Exception as e:
            con.rollback()
            raise e
        finally:
            self.cerrar_conexion(con)

    # ------------------------------------------------------------
    # Actualización genérica (UPDATE)
    # ------------------------------------------------------------
    def actualizar(self, tabla: str, id_campo: str, id_entidad: int, data: Dict[str, Any]) -> bool:
        """
        Actualiza un registro existente con trazabilidad
        
        Args:
            tabla: Nombre de la tabla
            id_campo: Nombre del campo ID (ej: 'id_empresa', 'id_contacto')
            id_entidad: Valor del ID a actualizar
            data: Diccionario con campos a actualizar
        
        Returns:
            bool: True si se actualizó correctamente
        """
        con = self.conectar()
        try:
            # Obtener estado anterior (para trazabilidad)
            cur = con.cursor()
            cur.execute(f"SELECT * FROM {tabla} WHERE {id_campo} = ?", (id_entidad,))
            anterior = cur.fetchone()
            valor_anterior = dict(anterior) if anterior else None
            
            # Actualizar
            set_clause = ", ".join(f"{k} = ?" for k in data.keys())
            params = tuple(data.values()) + (id_entidad,)
            cur.execute(f"UPDATE {tabla} SET {set_clause} WHERE {id_campo} = ?", params)
            
            # Registro forense
            self.registrar_evento(con, id_entidad, "ACTUALIZAR", data, valor_anterior)
            
            return cur.rowcount > 0
        
        except Exception as e:
            con.rollback()
            raise e
        finally:
            self.cerrar_conexion(con)

    # ------------------------------------------------------------
    # Lectura genérica (SELECT)
    # ------------------------------------------------------------
    def listar(self, tabla: str, filtros: Optional[Dict[str, Any]] = None, 
               orden: Optional[str] = None, limite: Optional[int] = None) -> List[Dict]:
        """
        Lista registros con filtros opcionales
        
        Args:
            tabla: Nombre de la tabla
            filtros: Diccionario con condiciones WHERE (ej: {"activo": 1})
            orden: Campo para ORDER BY (ej: "fecha_creacion DESC")
            limite: Número máximo de registros
        
        Returns:
            List[Dict]: Lista de registros como diccionarios
        """
        con = self.conectar()
        try:
            query = f"SELECT * FROM {tabla}"
            params = ()
            
            # Filtros WHERE
            if filtros:
                where_clause = " AND ".join(f"{k} = ?" for k in filtros.keys())
                query += f" WHERE {where_clause}"
                params = tuple(filtros.values())
            
            # Ordenamiento
            if orden:
                query += f" ORDER BY {orden}"
            
            # Límite
            if limite:
                query += f" LIMIT {limite}"
            
            cur = con.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            
            return [dict(r) for r in rows]
        
        finally:
            self.cerrar_conexion(con)

    def obtener_por_id(self, tabla: str, id_campo: str, id_valor: int) -> Optional[Dict]:
        """
        Obtiene un registro por su ID
        
        Returns:
            Dict: Registro encontrado, None si no existe
        """
        resultados = self.listar(tabla, filtros={id_campo: id_valor})
        return resultados[0] if resultados else None

    # ------------------------------------------------------------
    # Eliminación segura (DELETE)
    # ------------------------------------------------------------
    def eliminar(self, tabla: str, id_campo: str, id_entidad: int) -> bool:
        """
        Elimina un registro con trazabilidad forense
        
        ADVERTENCIA: Eliminación física (no soft delete)
        Considera usar un campo 'activo' para soft delete
        
        Returns:
            bool: True si se eliminó correctamente
        """
        con = self.conectar()
        try:
            # Obtener datos antes de eliminar (para trazabilidad)
            cur = con.cursor()
            cur.execute(f"SELECT * FROM {tabla} WHERE {id_campo} = ?", (id_entidad,))
            eliminado = cur.fetchone()
            
            if eliminado:
                cur.execute(f"DELETE FROM {tabla} WHERE {id_campo} = ?", (id_entidad,))
                self.registrar_evento(con, id_entidad, "ELIMINAR", {"deleted": dict(eliminado)})
                return True
            
            return False
        
        except Exception as e:
            con.rollback()
            raise e
        finally:
            self.cerrar_conexion(con)

    # ------------------------------------------------------------
    # Validación de integridad estructural
    # ------------------------------------------------------------
    def validar_integridad(self) -> Dict[str, bool]:
        """
        Valida que la estructura base esté correcta
        
        Verifica:
        - Foreign keys habilitadas
        - Tablas de trazabilidad existentes
        - Conexión funcional
        
        Returns:
            Dict: Estado de validación
        """
        con = self.conectar()
        try:
            cur = con.cursor()
            
            # Verificar foreign keys
            cur.execute("PRAGMA foreign_keys")
            fk_enabled = cur.fetchone()[0]
            
            # Verificar tablas críticas
            cur.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('historial_general', 'hash_registros', 'atributos_entidad')
            """)
            tablas = [r[0] for r in cur.fetchall()]
            
            return {
                "foreign_keys_enabled": bool(fk_enabled),
                "historial_general_exists": "historial_general" in tablas,
                "hash_registros_exists": "hash_registros" in tablas,
                "atributos_entidad_exists": "atributos_entidad" in tablas,
                "estructura_completa": len(tablas) == 3 and bool(fk_enabled)
            }
        
        finally:
            self.cerrar_conexion(con)

    # ------------------------------------------------------------
    # Demostración estructural
    # ------------------------------------------------------------
    def demo(self):
        """
        Modo demo: inserta y consulta datos de ejemplo con trazabilidad completa
        
        Útil para:
        - Testing de repositorios heredados
        - Validación de estructura
        - Ejemplos de uso
        """
        print("=" * 60)
        print(f"🧩 DEMO AUPRepository: {self.entidad.upper()}")
        print("=" * 60)
        
        # Validar integridad
        print("\n1️⃣ Validando integridad estructural...")
        validacion = self.validar_integridad()
        for k, v in validacion.items():
            status = "✅" if v else "❌"
            print(f"   {status} {k}: {v}")
        
        if not validacion["estructura_completa"]:
            print("\n⚠️  Estructura incompleta. Abortando demo.")
            return
        
        # Crear registro de prueba
        print(f"\n2️⃣ Creando {self.entidad} de prueba...")
        tabla = f"{self.entidad}s"
        data = {
            "nombre": f"Demo {self.entidad.capitalize()}",
            "correo": f"demo@{self.entidad}.local"
        }
        
        try:
            id_creado = self.crear(tabla, data)
            print(f"   ✅ {self.entidad.capitalize()} creado con ID {id_creado}")
        except Exception as e:
            print(f"   ❌ Error al crear: {e}")
            return
        
        # Listar registros
        print(f"\n3️⃣ Listando {self.entidad}s...")
        items = self.listar(tabla, limite=5)
        print(f"   📋 Total de registros: {len(items)}")
        for item in items:
            print(f"      - ID {item.get('id_' + self.entidad, 'N/A')}: {item.get('nombre', 'Sin nombre')}")
        
        # Verificar trazabilidad
        print(f"\n4️⃣ Verificando trazabilidad forense...")
        con = self.conectar()
        cur = con.cursor()
        cur.execute("""
            SELECT COUNT(*) as total FROM historial_general WHERE entidad = ?
        """, (self.entidad,))
        eventos = cur.fetchone()[0]
        print(f"   🪶 Eventos registrados: {eventos}")
        
        cur.execute("""
            SELECT COUNT(*) as total FROM hash_registros WHERE tabla_origen = ?
        """, (self.entidad,))
        hashes = cur.fetchone()[0]
        print(f"   🔐 Hashes forenses: {hashes}")
        self.cerrar_conexion(con)
        
        print("\n" + "=" * 60)
        print("✅ Demo completado exitosamente")
        print("=" * 60)


# ================================================================
#  MODO TEST
# ================================================================

if __name__ == "__main__":
    print("🚀 Testing AUPRepository - Clase Base Universal\n")
    
    # Test 1: Validación de integridad
    print("Test 1: Validación de integridad estructural")
    repo = AUPRepository(entidad="test", usuario="demo")
    validacion = repo.validar_integridad()
    print(f"Resultado: {validacion}\n")
    
    # Test 2: Demo completo
    print("Test 2: Demostración completa")
    try:
        repo.demo()
    except Exception as e:
        print(f"❌ Error en demo: {e}")
