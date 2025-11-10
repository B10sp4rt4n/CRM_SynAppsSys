# -*- coding: utf-8 -*-
"""
Módulo Contacto - Entidad de Identidad AUP
Representa contactos vinculados a empresas
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import re


@dataclass
class Contacto:
    """
    Entidad Contacto según arquitectura AUP
    
    Atributos:
    - id: Identificador único
    - nombre: Nombre completo del contacto
    - cargo: Puesto o posición
    - telefono: Teléfono personal/directo
    - correo: Email del contacto
    - empresa_id: ID de la empresa asociada
    - es_principal: Indica si es el contacto principal
    """
    
    id: Optional[int] = None
    nombre: str = ""
    cargo: str = ""
    telefono: str = ""
    correo: str = ""
    empresa_id: Optional[int] = None
    es_principal: bool = False
    activo: bool = True
    fecha_creacion: Optional[datetime] = None
    
    def __post_init__(self):
        if self.fecha_creacion is None:
            self.fecha_creacion = datetime.now()
    
    def validar(self) -> tuple[bool, str]:
        """
        Valida los datos del contacto
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not self.nombre or len(self.nombre.strip()) == 0:
            return False, "El nombre del contacto es obligatorio"
        
        if not self.empresa_id:
            return False, "El contacto debe estar asociado a una empresa"
        
        # Validar formato de email si se proporciona
        if self.correo and not re.match(r"[^@]+@[^@]+\.[^@]+", self.correo):
            return False, "Formato de correo electrónico inválido"
        
        return True, ""
    
    def to_dict(self) -> dict:
        """Convierte el contacto a diccionario"""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "cargo": self.cargo,
            "telefono": self.telefono,
            "correo": self.correo,
            "empresa_id": self.empresa_id,
            "es_principal": self.es_principal,
            "activo": self.activo,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Contacto':
        """Crea una instancia de Contacto desde un diccionario"""
        return cls(
            id=data.get("id"),
            nombre=data.get("nombre", ""),
            cargo=data.get("cargo", ""),
            telefono=data.get("telefono", ""),
            correo=data.get("correo", ""),
            empresa_id=data.get("empresa_id"),
            es_principal=data.get("es_principal", False),
            activo=data.get("activo", True),
            fecha_creacion=datetime.fromisoformat(data["fecha_creacion"]) if data.get("fecha_creacion") else None
        )


class ContactoRepository:
    """Repositorio para operaciones CRUD de Contacto"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def crear(self, contacto: Contacto) -> int:
        """Crea un nuevo contacto y lo vincula a una empresa"""
        cur = self.db.cursor()
        
        # Crear contacto
        cur.execute("""
            INSERT INTO aup_agentes (tipo, nombre, atributos, activo)
            VALUES (?, ?, ?, ?)
        """, (
            "contacto",
            contacto.nombre,
            f"cargo={contacto.cargo};telefono={contacto.telefono};correo={contacto.correo}",
            1 if contacto.activo else 0
        ))
        contacto_id = cur.lastrowid
        
        # Crear relación con empresa
        tipo_relacion = "contacto_principal" if contacto.es_principal else "tiene_contacto"
        cur.execute("""
            INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)
            VALUES (?, ?, ?)
        """, (contacto.empresa_id, contacto_id, tipo_relacion))
        
        self.db.commit()
        return contacto_id
    
    def obtener_por_empresa(self, empresa_id: int) -> list:
        """Obtiene todos los contactos de una empresa"""
        cur = self.db.cursor()
        cur.execute("""
            SELECT a.*, r.tipo_relacion FROM aup_agentes a
            INNER JOIN aup_relaciones r ON r.agente_destino = a.id
            WHERE r.agente_origen = ? 
            AND r.tipo_relacion IN ('tiene_contacto', 'contacto_principal')
            AND a.activo = 1
            ORDER BY a.nombre ASC
        """, (empresa_id,))
        
        rows = cur.fetchall()
        contactos = []
        
        for row in rows:
            atributos = row["atributos"] or ""
            attrs_dict = {}
            for item in atributos.split(";"):
                if "=" in item:
                    key, val = item.split("=", 1)
                    attrs_dict[key] = val
            
            contactos.append(Contacto(
                id=row["id"],
                nombre=row["nombre"],
                cargo=attrs_dict.get("cargo", ""),
                telefono=attrs_dict.get("telefono", ""),
                correo=attrs_dict.get("correo", ""),
                empresa_id=empresa_id,
                es_principal=(row["tipo_relacion"] == "contacto_principal"),
                activo=bool(row["activo"]),
                fecha_creacion=datetime.fromisoformat(row["fecha_creacion"]) if row.get("fecha_creacion") else None
            ))
        
        return contactos
    
    def contar_por_empresa(self, empresa_id: int) -> int:
        """Cuenta los contactos activos de una empresa"""
        cur = self.db.cursor()
        cur.execute("""
            SELECT COUNT(*) as total FROM aup_relaciones
            WHERE agente_origen = ? 
            AND tipo_relacion IN ('tiene_contacto', 'contacto_principal')
        """, (empresa_id,))
        return cur.fetchone()["total"]
