# -*- coding: utf-8 -*-
"""
Módulo Empresa - Entidad de Identidad AUP
Representa empresas en el sistema CRM-EXO v2
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class Empresa:
    """
    Entidad Empresa según arquitectura AUP
    
    Atributos de identidad:
    - id: Identificador único
    - nombre: Razón social
    - rfc: Registro Federal de Contribuyentes
    - sector: Sector o giro empresarial
    - direccion: Domicilio fiscal
    - telefono: Teléfono principal
    - activo: Estado de la empresa
    """
    
    id: Optional[int] = None
    nombre: str = ""
    rfc: str = ""
    sector: str = ""
    direccion: str = ""
    telefono: str = ""
    activo: bool = True
    fecha_creacion: Optional[datetime] = None
    fecha_modificacion: Optional[datetime] = None
    
    def __post_init__(self):
        """Inicialización automática de fechas"""
        if self.fecha_creacion is None:
            self.fecha_creacion = datetime.now()
        if self.fecha_modificacion is None:
            self.fecha_modificacion = datetime.now()
    
    def validar(self) -> tuple[bool, str]:
        """
        Valida los datos de la empresa
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not self.nombre or len(self.nombre.strip()) == 0:
            return False, "El nombre de la empresa es obligatorio"
        
        if self.rfc and len(self.rfc) not in [12, 13]:
            return False, "RFC inválido (debe tener 12 o 13 caracteres)"
        
        return True, ""
    
    def to_dict(self) -> dict:
        """Convierte la empresa a diccionario"""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "rfc": self.rfc,
            "sector": self.sector,
            "direccion": self.direccion,
            "telefono": self.telefono,
            "activo": self.activo,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            "fecha_modificacion": self.fecha_modificacion.isoformat() if self.fecha_modificacion else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Empresa':
        """Crea una instancia de Empresa desde un diccionario"""
        return cls(
            id=data.get("id"),
            nombre=data.get("nombre", ""),
            rfc=data.get("rfc", ""),
            sector=data.get("sector", ""),
            direccion=data.get("direccion", ""),
            telefono=data.get("telefono", ""),
            activo=data.get("activo", True),
            fecha_creacion=datetime.fromisoformat(data["fecha_creacion"]) if data.get("fecha_creacion") else None,
            fecha_modificacion=datetime.fromisoformat(data["fecha_modificacion"]) if data.get("fecha_modificacion") else None
        )


class EmpresaRepository:
    """
    Repositorio para operaciones CRUD de Empresa
    Implementa patrón Repository para separar lógica de persistencia
    """
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def crear(self, empresa: Empresa) -> int:
        """
        Crea una nueva empresa en la base de datos
        
        Returns:
            int: ID de la empresa creada
        """
        cur = self.db.cursor()
        cur.execute("""
            INSERT INTO aup_agentes (tipo, nombre, atributos, activo)
            VALUES (?, ?, ?, ?)
        """, (
            "empresa",
            empresa.nombre,
            f"rfc={empresa.rfc};sector={empresa.sector};direccion={empresa.direccion};telefono={empresa.telefono}",
            1 if empresa.activo else 0
        ))
        self.db.commit()
        return cur.lastrowid
    
    def obtener_por_id(self, empresa_id: int) -> Optional[Empresa]:
        """Obtiene una empresa por su ID"""
        cur = self.db.cursor()
        cur.execute("SELECT * FROM aup_agentes WHERE id=? AND tipo='empresa'", (empresa_id,))
        row = cur.fetchone()
        
        if not row:
            return None
        
        # Parsear atributos
        atributos = row["atributos"] or ""
        attrs_dict = {}
        for item in atributos.split(";"):
            if "=" in item:
                key, val = item.split("=", 1)
                attrs_dict[key] = val
        
        return Empresa(
            id=row["id"],
            nombre=row["nombre"],
            rfc=attrs_dict.get("rfc", ""),
            sector=attrs_dict.get("sector", ""),
            direccion=attrs_dict.get("direccion", ""),
            telefono=attrs_dict.get("telefono", ""),
            activo=bool(row["activo"]),
            fecha_creacion=datetime.fromisoformat(row["fecha_creacion"]) if row.get("fecha_creacion") else None
        )
    
    def listar_todas(self, solo_activas: bool = True) -> List[Empresa]:
        """Lista todas las empresas"""
        cur = self.db.cursor()
        query = "SELECT * FROM aup_agentes WHERE tipo='empresa'"
        if solo_activas:
            query += " AND activo=1"
        query += " ORDER BY nombre ASC"
        
        cur.execute(query)
        rows = cur.fetchall()
        
        empresas = []
        for row in rows:
            atributos = row["atributos"] or ""
            attrs_dict = {}
            for item in atributos.split(";"):
                if "=" in item:
                    key, val = item.split("=", 1)
                    attrs_dict[key] = val
            
            empresas.append(Empresa(
                id=row["id"],
                nombre=row["nombre"],
                rfc=attrs_dict.get("rfc", ""),
                sector=attrs_dict.get("sector", ""),
                direccion=attrs_dict.get("direccion", ""),
                telefono=attrs_dict.get("telefono", ""),
                activo=bool(row["activo"]),
                fecha_creacion=datetime.fromisoformat(row["fecha_creacion"]) if row.get("fecha_creacion") else None
            ))
        
        return empresas
    
    def actualizar(self, empresa: Empresa) -> bool:
        """Actualiza una empresa existente"""
        if not empresa.id:
            return False
        
        empresa.fecha_modificacion = datetime.now()
        
        cur = self.db.cursor()
        cur.execute("""
            UPDATE aup_agentes 
            SET nombre=?, 
                atributos=?, 
                activo=?
            WHERE id=? AND tipo='empresa'
        """, (
            empresa.nombre,
            f"rfc={empresa.rfc};sector={empresa.sector};direccion={empresa.direccion};telefono={empresa.telefono}",
            1 if empresa.activo else 0,
            empresa.id
        ))
        self.db.commit()
        return cur.rowcount > 0
    
    def desactivar(self, empresa_id: int) -> bool:
        """Desactiva una empresa (soft delete)"""
        cur = self.db.cursor()
        cur.execute("""
            UPDATE aup_agentes SET activo=0 
            WHERE id=? AND tipo='empresa'
        """, (empresa_id,))
        self.db.commit()
        return cur.rowcount > 0
