# ================================================================
#  core/atributos_dinamicos.py  |  CRM-EXO v2  (Extensión AUP)
#  ---------------------------------------------------------------
#  Permite agregar, modificar y consultar atributos extendidos
#  de cualquier entidad (empresa, contacto, prospecto, etc.)
#  con trazabilidad completa y hash forense SHA-256.
#  
#  Este módulo permite que cualquier entidad pueda extenderse
#  dinámicamente sin alterar su estructura base, manteniendo
#  coherencia con el modelo AUP-EXO v2 y compatibilidad forense.
# ================================================================

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
import hashlib
import json


@dataclass
class AtributoExtendido:
    """
    Atributo dinámico que extiende cualquier entidad del sistema
    
    Filosofía AUP: "Fallos tolerados, estructura no"
    El cliente pide un campo nuevo → no rompemos nada, agregamos un atributo
    
    Atributos:
    - id_attr: Identificador único
    - entidad: Tipo de entidad (empresa, contacto, prospecto, etc.)
    - id_entidad: ID del registro específico
    - nombre_attr: Nombre del atributo personalizado
    - valor_attr: Valor del atributo
    - tipo_dato: Tipo de dato (text, number, date, boolean)
    """
    
    id_attr: Optional[int] = None
    entidad: str = ""
    id_entidad: Optional[int] = None
    nombre_attr: str = ""
    valor_attr: str = ""
    tipo_dato: str = "text"
    fecha_creacion: Optional[datetime] = None
    
    def __post_init__(self):
        if self.fecha_creacion is None:
            self.fecha_creacion = datetime.now()
    
    def to_dict(self) -> dict:
        """Convierte el atributo a diccionario"""
        return {
            "id_attr": self.id_attr,
            "entidad": self.entidad,
            "id_entidad": self.id_entidad,
            "nombre_attr": self.nombre_attr,
            "valor_attr": self.valor_attr,
            "tipo_dato": self.tipo_dato,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None
        }


class AtributosRepository:
    """
    Repositorio para gestión de atributos dinámicos
    
    FILOSOFÍA AUP: "Fallos tolerados, estructura no"
    - Cliente pide campo nuevo → no rompemos estructura base
    - Agregamos atributo paramétrico con trazabilidad forense
    - Hash SHA256 en cada operación
    """
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def _calcular_hash_evento(self, entidad: str, accion: str, nombre_attr: str, 
                              valor_attr: str, id_entidad: int) -> str:
        """Calcula hash SHA256 forense del evento de atributo"""
        data = {
            "entidad": entidad,
            "id_entidad": id_entidad,
            "accion": accion,
            "nombre_attr": nombre_attr,
            "valor_attr": valor_attr,
            "timestamp": datetime.utcnow().isoformat()
        }
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def _registrar_evento_forense(self, entidad: str, id_attr: int, accion: str, 
                                   nombre_attr: str, valor_attr: str, usuario: str = "system"):
        """Registra evento en historial_general + hash_registros"""
        ts = datetime.utcnow().isoformat()
        valor_forense = f"{nombre_attr}={valor_attr}"
        hash_evt = self._calcular_hash_evento(entidad, accion, nombre_attr, valor_attr, id_attr)
        
        # Insertar en historial_general
        self.db.execute("""
            INSERT INTO historial_general
            (entidad, id_entidad, accion, valor_anterior, valor_nuevo, usuario, timestamp, hash_evento)
            VALUES (?, ?, ?, NULL, ?, ?, ?, ?)
        """, (f"{entidad}_attr", id_attr, accion, valor_forense, usuario, ts, hash_evt))
        
        # Insertar hash en hash_registros
        self.db.execute("""
            INSERT INTO hash_registros (tabla_origen, id_registro, hash_sha256)
            VALUES ('atributos_entidad', ?, ?)
        """, (id_attr, hash_evt))
        
        self.db.commit()
        return hash_evt
    
    def agregar_atributo(self, entidad: str, id_entidad: int, nombre_attr: str, 
                         valor_attr: str, tipo_dato: str = "text", usuario: str = "system") -> tuple[int, str]:
        """
        Agrega un atributo personalizado a una entidad
        
        CASO DE USO:
        Cliente: "Quiero agregar 'Giro comercial' a Empresa"
        → repo.agregar_atributo("empresa", 5, "Giro comercial", "Manufactura")
        → NO se altera la tabla empresas
        → Se inserta en atributos_entidad con hash forense
        
        Args:
            entidad: Tipo de entidad (empresa, contacto, prospecto, etc.)
            id_entidad: ID del registro específico
            nombre_attr: Nombre del campo personalizado
            valor_attr: Valor del campo
            tipo_dato: Tipo de dato (text, number, date, boolean)
            usuario: Usuario que crea el atributo
        
        Returns:
            tuple: (id_attr, hash_forense)
        """
        cur = self.db.cursor()
        
        # Verificar si ya existe el atributo
        cur.execute("""
            SELECT id_attr FROM atributos_entidad
            WHERE entidad = ? AND id_entidad = ? AND nombre_attr = ?
        """, (entidad, id_entidad, nombre_attr))
        
        existe = cur.fetchone()
        
        if existe:
            # Actualizar valor existente
            id_attr = existe["id_attr"]
            cur.execute("""
                UPDATE atributos_entidad
                SET valor_attr = ?, tipo_dato = ?
                WHERE id_attr = ?
            """, (valor_attr, tipo_dato, id_attr))
            self.db.commit()
            hash_evt = self._registrar_evento_forense(entidad, id_attr, "ATTR_UPDATE", 
                                                       nombre_attr, valor_attr, usuario)
            return id_attr, hash_evt
        else:
            # Insertar nuevo atributo
            cur.execute("""
                INSERT INTO atributos_entidad (entidad, id_entidad, nombre_attr, valor_attr, tipo_dato)
                VALUES (?, ?, ?, ?, ?)
            """, (entidad, id_entidad, nombre_attr, valor_attr, tipo_dato))
            self.db.commit()
            id_attr = cur.lastrowid
            hash_evt = self._registrar_evento_forense(entidad, id_attr, "ATTR_CREATE", 
                                                       nombre_attr, valor_attr, usuario)
            return id_attr, hash_evt
    
    def actualizar_atributo(self, id_attr: int, nuevo_valor: str, usuario: str = "system") -> str:
        """
        Actualiza el valor de un atributo existente con trazabilidad forense
        
        Returns:
            str: Hash forense del evento
        """
        cur = self.db.cursor()
        cur.execute("SELECT * FROM atributos_entidad WHERE id_attr = ?", (id_attr,))
        attr = cur.fetchone()
        
        if not attr:
            raise ValueError(f"Atributo ID {id_attr} no encontrado")
        
        cur.execute("""
            UPDATE atributos_entidad
            SET valor_attr = ?
            WHERE id_attr = ?
        """, (nuevo_valor, id_attr))
        self.db.commit()
        
        hash_evt = self._registrar_evento_forense(
            attr["entidad"], id_attr, "ATTR_UPDATE", 
            attr["nombre_attr"], nuevo_valor, usuario
        )
        
        return hash_evt
    
    def listar_atributos(self, entidad: str, id_entidad: int) -> List[dict]:
        """
        Devuelve todos los atributos dinámicos asociados a una entidad
        
        Returns:
            List[dict]: Lista de diccionarios con estructura de atributo
        """
        cur = self.db.cursor()
        cur.execute("""
            SELECT id_attr, nombre_attr, valor_attr, tipo_dato, fecha_creacion
            FROM atributos_entidad
            WHERE entidad = ? AND id_entidad = ?
            ORDER BY fecha_creacion DESC
        """, (entidad, id_entidad))
        
        return [dict(row) for row in cur.fetchall()]
    
    def obtener_atributos(self, entidad: str, id_entidad: int) -> List[AtributoExtendido]:
        """
        Obtiene todos los atributos personalizados como objetos AtributoExtendido
        
        Returns:
            List[AtributoExtendido]: Lista de atributos
        """
        cur = self.db.cursor()
        cur.execute("""
            SELECT * FROM atributos_entidad
            WHERE entidad = ? AND id_entidad = ?
            ORDER BY fecha_creacion
        """, (entidad, id_entidad))
        
        atributos = []
        for row in cur.fetchall():
            atributos.append(AtributoExtendido(
                id_attr=row["id_attr"],
                entidad=row["entidad"],
                id_entidad=row["id_entidad"],
                nombre_attr=row["nombre_attr"],
                valor_attr=row["valor_attr"],
                tipo_dato=row["tipo_dato"],
                fecha_creacion=datetime.fromisoformat(row["fecha_creacion"]) if row["fecha_creacion"] else None
            ))
        
        return atributos
    
    def obtener_valor(self, entidad: str, id_entidad: int, nombre_attr: str) -> Optional[str]:
        """
        Obtiene el valor de un atributo específico
        
        Returns:
            str: Valor del atributo, None si no existe
        """
        cur = self.db.cursor()
        cur.execute("""
            SELECT valor_attr FROM atributos_entidad
            WHERE entidad = ? AND id_entidad = ? AND nombre_attr = ?
        """, (entidad, id_entidad, nombre_attr))
        
        row = cur.fetchone()
        return row["valor_attr"] if row else None
    
    def eliminar_atributo(self, id_attr: int) -> bool:
        """Elimina un atributo personalizado"""
        cur = self.db.cursor()
        cur.execute("DELETE FROM atributos_entidad WHERE id_attr = ?", (id_attr,))
        self.db.commit()
        return cur.rowcount > 0
    
    def listar_atributos_por_tipo(self, entidad: str) -> dict:
        """
        Lista todos los atributos únicos definidos para un tipo de entidad
        Útil para mostrar "plantillas" de campos personalizados
        
        Returns:
            dict: {nombre_attr: tipo_dato}
        """
        cur = self.db.cursor()
        cur.execute("""
            SELECT DISTINCT nombre_attr, tipo_dato
            FROM atributos_entidad
            WHERE entidad = ?
            ORDER BY nombre_attr
        """, (entidad,))
        
        atributos_unicos = {}
        for row in cur.fetchall():
            atributos_unicos[row["nombre_attr"]] = row["tipo_dato"]
        
        return atributos_unicos


# ================================================================
#  FUNCIONES HELPER PARA STREAMLIT
# ================================================================

def atributos_entidad(entidad: str, id_entidad: int, db_connection) -> List[dict]:
    """
    Helper function para usar en Streamlit (interfaz simplificada)
    
    Uso en Streamlit:
    >>> for attr in atributos_entidad("empresa", id_emp, con):
    >>>     st.text_input(attr["nombre_attr"], attr["valor_attr"])
    
    Returns:
        List[dict]: Lista de diccionarios con nombre_attr, valor_attr, tipo_dato
    """
    repo = AtributosRepository(db_connection)
    return repo.listar_atributos(entidad, id_entidad)


def guardar_atributo_custom(entidad: str, id_entidad: int, nombre: str, 
                            valor: str, tipo: str, db_connection, usuario: str = "ui") -> tuple[int, str]:
    """
    Helper para guardar atributos desde Streamlit con trazabilidad
    
    Uso:
    >>> id_attr, hash_evt = guardar_atributo_custom("empresa", 5, "Giro comercial", "Tecnología", "text", con)
    >>> st.success(f"Atributo guardado. Hash: {hash_evt[:16]}...")
    
    Returns:
        tuple: (id_attr, hash_forense)
    """
    repo = AtributosRepository(db_connection)
    return repo.agregar_atributo(entidad, id_entidad, nombre, valor, tipo, usuario)


# ================================================================
#  MODO DEMO / TEST
# ================================================================

if __name__ == "__main__":
    import sqlite3
    from pathlib import Path
    
    # Conectar a la DB de prueba
    BASE_DIR = Path(__file__).parent.parent
    DB_PATH = BASE_DIR / "data" / "crm_exo_v2.sqlite"
    
    print("🧪 Modo Demo - Atributos Dinámicos")
    print(f"📦 DB: {DB_PATH}")
    print()
    
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    
    repo = AtributosRepository(con)
    
    # Test 1: Agregar atributo a empresa ficticia
    print("Test 1: Agregar 'Giro comercial' a empresa ID=1")
    try:
        id_attr, hash_evt = repo.agregar_atributo(
            entidad="empresa",
            id_entidad=1,
            nombre_attr="Giro comercial",
            valor_attr="Tecnología",
            tipo_dato="text",
            usuario="demo"
        )
        print(f"✅ Atributo creado ID={id_attr}")
        print(f"🔐 Hash forense: {hash_evt[:16]}...")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()
    
    # Test 2: Listar atributos
    print("Test 2: Listar atributos de empresa ID=1")
    attrs = repo.listar_atributos("empresa", 1)
    if attrs:
        for attr in attrs:
            print(f"  - {attr['nombre_attr']}: {attr['valor_attr']} ({attr['tipo_dato']})")
    else:
        print("  (sin atributos)")
    
    print()
    
    # Test 3: Actualizar atributo
    if attrs:
        print(f"Test 3: Actualizar atributo ID={attrs[0]['id_attr']}")
        try:
            hash_upd = repo.actualizar_atributo(attrs[0]['id_attr'], "Desarrollo de Software", "demo")
            print(f"✅ Atributo actualizado")
            print(f"🔐 Hash forense: {hash_upd[:16]}...")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    self.cerrar_conexion(con)
    print()
    print("=" * 60)
    print("✅ Tests completados")
