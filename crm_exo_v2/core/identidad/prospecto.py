# -*- coding: utf-8 -*-
"""
Módulo Prospecto - Entidad de Identidad AUP
Representa prospectos generados desde empresas con contactos
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, date


@dataclass
class Prospecto:
    """
    Entidad Prospecto según arquitectura AUP
    
    REGLA R1: Solo se crea desde Empresa con al menos 1 contacto
    REGLA R3: Se convierte a cliente cuando gana una oportunidad
    
    Atributos:
    - id: Identificador único
    - nombre: Nombre del prospecto (heredado de empresa)
    - empresa_id: ID de la empresa origen
    - estado: Estado del prospecto (Nuevo, En negociación, Cerrado, Perdido)
    - es_cliente: Bandera de conversión a cliente
    - fecha_conversion_cliente: Fecha en que se convirtió a cliente
    """
    
    id: Optional[int] = None
    nombre: str = ""
    empresa_id: Optional[int] = None
    sector: str = ""
    telefono: str = ""
    estado: str = "Nuevo"
    es_cliente: bool = False
    fecha_conversion_cliente: Optional[date] = None
    activo: bool = True
    fecha_creacion: Optional[datetime] = None
    
    def __post_init__(self):
        if self.fecha_creacion is None:
            self.fecha_creacion = datetime.now()
    
    def validar(self) -> tuple[bool, str]:
        """
        Valida los datos del prospecto
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not self.nombre:
            return False, "El nombre del prospecto es obligatorio"
        
        if not self.empresa_id:
            return False, "El prospecto debe estar asociado a una empresa"
        
        if self.estado not in ["Nuevo", "En negociación", "Cerrado", "Perdido"]:
            return False, "Estado inválido"
        
        return True, ""
    
    def convertir_a_cliente(self):
        """
        REGLA R3: Convierte el prospecto a cliente
        Se ejecuta automáticamente al ganar una oportunidad
        """
        self.es_cliente = True
        self.fecha_conversion_cliente = date.today()
    
    def es_elegible_para_oportunidades(self) -> bool:
        """
        REGLA R2: Verifica si el prospecto puede tener oportunidades
        """
        return self.activo and not self.es_cliente
    
    def to_dict(self) -> dict:
        """Convierte el prospecto a diccionario"""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "empresa_id": self.empresa_id,
            "sector": self.sector,
            "telefono": self.telefono,
            "estado": self.estado,
            "es_cliente": self.es_cliente,
            "fecha_conversion_cliente": self.fecha_conversion_cliente.isoformat() if self.fecha_conversion_cliente else None,
            "activo": self.activo,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Prospecto':
        """Crea una instancia de Prospecto desde un diccionario"""
        return cls(
            id=data.get("id"),
            nombre=data.get("nombre", ""),
            empresa_id=data.get("empresa_id"),
            sector=data.get("sector", ""),
            telefono=data.get("telefono", ""),
            estado=data.get("estado", "Nuevo"),
            es_cliente=data.get("es_cliente", False),
            fecha_conversion_cliente=date.fromisoformat(data["fecha_conversion_cliente"]) if data.get("fecha_conversion_cliente") else None,
            activo=data.get("activo", True),
            fecha_creacion=datetime.fromisoformat(data["fecha_creacion"]) if data.get("fecha_creacion") else None
        )


class ProspectoRepository:
    """Repositorio para operaciones CRUD de Prospecto"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def crear_desde_empresa(self, empresa_id: int, nombre: str, sector: str, telefono: str) -> Optional[int]:
        """
        REGLA R1: Crea prospecto solo si la empresa tiene contactos
        
        Returns:
            int: ID del prospecto creado, None si no cumple reglas
        """
        # Verificar que la empresa tenga contactos
        cur = self.db.cursor()
        cur.execute("""
            SELECT COUNT(*) as total FROM aup_relaciones
            WHERE agente_origen = ? AND tipo_relacion IN ('tiene_contacto', 'contacto_principal')
        """, (empresa_id,))
        
        if cur.fetchone()["total"] == 0:
            return None  # REGLA R1: No crear sin contactos
        
        # Crear prospecto
        atributos = f"sector={sector};telefono={telefono};estado=Nuevo;es_cliente=0"
        cur.execute("""
            INSERT INTO aup_agentes (tipo, nombre, atributos, activo)
            VALUES (?, ?, ?, ?)
        """, ("prospecto", nombre, atributos, 1))
        prospecto_id = cur.lastrowid
        
        # Crear relación empresa → prospecto
        cur.execute("""
            INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)
            VALUES (?, ?, ?)
        """, (empresa_id, prospecto_id, "genero_prospecto"))
        
        # Copiar contactos de la empresa al prospecto
        cur.execute("""
            SELECT agente_destino FROM aup_relaciones
            WHERE agente_origen = ? AND tipo_relacion IN ('tiene_contacto', 'contacto_principal')
        """, (empresa_id,))
        
        for row in cur.fetchall():
            cur.execute("""
                INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)
                VALUES (?, ?, ?)
            """, (prospecto_id, row["agente_destino"], "tiene_contacto"))
        
        self.db.commit()
        return prospecto_id
    
    def listar_todos(self, solo_activos: bool = True, solo_no_clientes: bool = False) -> list:
        """Lista todos los prospectos"""
        cur = self.db.cursor()
        query = "SELECT * FROM aup_agentes WHERE tipo='prospecto'"
        if solo_activos:
            query += " AND activo=1"
        query += " ORDER BY fecha_creacion DESC"
        
        cur.execute(query)
        rows = cur.fetchall()
        
        prospectos = []
        for row in rows:
            atributos = row["atributos"] or ""
            attrs_dict = {}
            for item in atributos.split(";"):
                if "=" in item:
                    key, val = item.split("=", 1)
                    attrs_dict[key] = val
            
            es_cliente = attrs_dict.get("es_cliente", "0") == "1"
            
            # Filtrar si solo queremos no-clientes
            if solo_no_clientes and es_cliente:
                continue
            
            prospectos.append(Prospecto(
                id=row["id"],
                nombre=row["nombre"],
                sector=attrs_dict.get("sector", ""),
                telefono=attrs_dict.get("telefono", ""),
                estado=attrs_dict.get("estado", "Nuevo"),
                es_cliente=es_cliente,
                fecha_conversion_cliente=date.fromisoformat(attrs_dict["fecha_conversion_cliente"]) if attrs_dict.get("fecha_conversion_cliente") else None,
                activo=bool(row["activo"]),
                fecha_creacion=datetime.fromisoformat(row["fecha_creacion"]) if row.get("fecha_creacion") else None
            ))
        
        return prospectos
    
    def listar_clientes(self) -> list:
        """
        Lista solo los prospectos que ya son clientes (es_cliente=1)
        Para el módulo de Clientes
        """
        return [p for p in self.listar_todos() if p.es_cliente]
    
    def convertir_a_cliente(self, prospecto_id: int) -> bool:
        """
        REGLA R3: Convierte un prospecto a cliente
        Actualiza es_cliente=1 y registra fecha_conversion
        """
        cur = self.db.cursor()
        cur.execute("SELECT * FROM aup_agentes WHERE id=? AND tipo='prospecto'", (prospecto_id,))
        row = cur.fetchone()
        
        if not row:
            return False
        
        atributos = row["atributos"] or ""
        # Actualizar atributos
        import re
        if re.search(r"es_cliente=[^;]+", atributos):
            atributos = re.sub(r"es_cliente=[^;]+", "es_cliente=1", atributos)
        else:
            atributos += ";es_cliente=1"
        
        if re.search(r"fecha_conversion_cliente=[^;]+", atributos):
            atributos = re.sub(r"fecha_conversion_cliente=[^;]+", f"fecha_conversion_cliente={date.today()}", atributos)
        else:
            atributos += f";fecha_conversion_cliente={date.today()}"
        
        cur.execute("""
            UPDATE aup_agentes SET atributos=? WHERE id=?
        """, (atributos, prospecto_id))
        
        self.db.commit()
        return True
