# -*- coding: utf-8 -*-
"""
Módulo Oportunidad - Entidad de Transacción AUP
Gestiona oportunidades de negocio vinculadas a prospectos
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, date
from decimal import Decimal


@dataclass
class Oportunidad:
    """
    Entidad Oportunidad según arquitectura AUP
    
    REGLA R2: Solo puede crearse desde un prospecto válido
    REGLA R3: Al marcar como ganada (probabilidad=100%), convierte prospecto a cliente
    REGLA R4: Requiere OC recibida (oc_recibida=True) para poder facturar
    
    Atributos:
    - id: Identificador único
    - nombre: Nombre descriptivo de la oportunidad
    - prospecto_id: ID del prospecto (obligatorio)
    - monto: Monto estimado
    - probabilidad: Probabilidad de cierre (0-100)
    - etapa: Etapa del pipeline (Calificación, Propuesta, Negociación, Cierre)
    - oc_recibida: Bandera de OC recibida (REGLA R4)
    - fecha_estimada_cierre: Fecha estimada de cierre
    """
    
    id: Optional[int] = None
    nombre: str = ""
    prospecto_id: Optional[int] = None
    monto: Decimal = Decimal("0.00")
    probabilidad: int = 0
    etapa: str = "Calificación"
    oc_recibida: bool = False
    fecha_estimada_cierre: Optional[date] = None
    descripcion: str = ""
    activo: bool = True
    fecha_creacion: Optional[datetime] = None
    
    def __post_init__(self):
        if self.fecha_creacion is None:
            self.fecha_creacion = datetime.now()
        if isinstance(self.monto, (int, float)):
            self.monto = Decimal(str(self.monto))
    
    def validar(self) -> tuple[bool, str]:
        """
        Valida los datos de la oportunidad
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not self.nombre:
            return False, "El nombre de la oportunidad es obligatorio"
        
        # REGLA R2: Debe tener prospecto asociado
        if not self.prospecto_id:
            return False, "La oportunidad debe estar asociada a un prospecto válido"
        
        if self.probabilidad < 0 or self.probabilidad > 100:
            return False, "La probabilidad debe estar entre 0 y 100"
        
        if self.etapa not in ["Calificación", "Propuesta", "Negociación", "Cierre", "Ganada", "Perdida"]:
            return False, "Etapa inválida"
        
        if self.monto < 0:
            return False, "El monto no puede ser negativo"
        
        return True, ""
    
    def marcar_como_ganada(self):
        """
        REGLA R3: Marca la oportunidad como ganada
        Establece probabilidad=100% y etapa=Ganada
        El repositorio se encarga de convertir el prospecto a cliente
        """
        self.probabilidad = 100
        self.etapa = "Ganada"
    
    def marcar_oc_recibida(self):
        """
        REGLA R4: Marca la OC como recibida
        Habilita el proceso de facturación
        """
        self.oc_recibida = True
    
    def puede_facturar(self) -> bool:
        """
        REGLA R4: Verifica si se puede generar factura
        Requiere: oportunidad ganada + OC recibida
        """
        return self.etapa == "Ganada" and self.oc_recibida
    
    def to_dict(self) -> dict:
        """Convierte la oportunidad a diccionario"""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "prospecto_id": self.prospecto_id,
            "monto": float(self.monto),
            "probabilidad": self.probabilidad,
            "etapa": self.etapa,
            "oc_recibida": self.oc_recibida,
            "fecha_estimada_cierre": self.fecha_estimada_cierre.isoformat() if self.fecha_estimada_cierre else None,
            "descripcion": self.descripcion,
            "activo": self.activo,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Oportunidad':
        """Crea una instancia de Oportunidad desde un diccionario"""
        return cls(
            id=data.get("id"),
            nombre=data.get("nombre", ""),
            prospecto_id=data.get("prospecto_id"),
            monto=Decimal(str(data.get("monto", "0.00"))),
            probabilidad=data.get("probabilidad", 0),
            etapa=data.get("etapa", "Calificación"),
            oc_recibida=data.get("oc_recibida", False),
            fecha_estimada_cierre=date.fromisoformat(data["fecha_estimada_cierre"]) if data.get("fecha_estimada_cierre") else None,
            descripcion=data.get("descripcion", ""),
            activo=data.get("activo", True),
            fecha_creacion=datetime.fromisoformat(data["fecha_creacion"]) if data.get("fecha_creacion") else None
        )


class OportunidadRepository:
    """Repositorio para operaciones CRUD de Oportunidad"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def crear(self, oportunidad: Oportunidad) -> Optional[int]:
        """
        REGLA R2: Crea una oportunidad asociada a un prospecto
        
        Returns:
            int: ID de la oportunidad creada, None si falla validación
        """
        # Validar
        es_valido, mensaje = oportunidad.validar()
        if not es_valido:
            raise ValueError(mensaje)
        
        # REGLA R2: Verificar que el prospecto exista y sea válido
        cur = self.db.cursor()
        cur.execute("""
            SELECT * FROM aup_agentes WHERE id=? AND tipo='prospecto' AND activo=1
        """, (oportunidad.prospecto_id,))
        
        if not cur.fetchone():
            raise ValueError("El prospecto no existe o no está activo")
        
        # Crear oportunidad
        atributos = (
            f"monto={float(oportunidad.monto)};"
            f"probabilidad={oportunidad.probabilidad};"
            f"etapa={oportunidad.etapa};"
            f"oc_recibida={'1' if oportunidad.oc_recibida else '0'};"
            f"descripcion={oportunidad.descripcion};"
        )
        
        if oportunidad.fecha_estimada_cierre:
            atributos += f"fecha_estimada_cierre={oportunidad.fecha_estimada_cierre.isoformat()};"
        
        cur.execute("""
            INSERT INTO aup_agentes (tipo, nombre, atributos, activo)
            VALUES (?, ?, ?, ?)
        """, ("oportunidad", oportunidad.nombre, atributos, 1))
        oportunidad_id = cur.lastrowid
        
        # Crear relación prospecto → oportunidad
        cur.execute("""
            INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)
            VALUES (?, ?, ?)
        """, (oportunidad.prospecto_id, oportunidad_id, "tiene_oportunidad"))
        
        self.db.commit()
        return oportunidad_id
    
    def marcar_ganada_y_convertir(self, oportunidad_id: int) -> bool:
        """
        REGLA R3: Marca oportunidad como ganada y convierte prospecto a cliente
        
        Ejecuta dos acciones:
        1. Actualiza oportunidad: probabilidad=100, etapa=Ganada
        2. Convierte prospecto asociado: es_cliente=1, fecha_conversion_cliente=hoy
        """
        cur = self.db.cursor()
        
        # Obtener oportunidad y prospecto asociado
        cur.execute("""
            SELECT o.*, r.agente_origen as prospecto_id
            FROM aup_agentes o
            LEFT JOIN aup_relaciones r ON r.agente_destino = o.id AND r.tipo_relacion = 'tiene_oportunidad'
            WHERE o.id = ? AND o.tipo = 'oportunidad'
        """, (oportunidad_id,))
        
        row = cur.fetchone()
        if not row:
            return False
        
        prospecto_id = row["prospecto_id"]
        
        # 1. Actualizar oportunidad
        atributos = row["atributos"] or ""
        import re
        
        # Actualizar probabilidad
        if re.search(r"probabilidad=[^;]+", atributos):
            atributos = re.sub(r"probabilidad=[^;]+", "probabilidad=100", atributos)
        else:
            atributos += ";probabilidad=100"
        
        # Actualizar etapa
        if re.search(r"etapa=[^;]+", atributos):
            atributos = re.sub(r"etapa=[^;]+", "etapa=Ganada", atributos)
        else:
            atributos += ";etapa=Ganada"
        
        cur.execute("""
            UPDATE aup_agentes SET atributos=? WHERE id=?
        """, (atributos, oportunidad_id))
        
        # 2. REGLA R3: Convertir prospecto a cliente
        cur.execute("SELECT * FROM aup_agentes WHERE id=? AND tipo='prospecto'", (prospecto_id,))
        prospecto = cur.fetchone()
        
        if prospecto:
            atributos_prospecto = prospecto["atributos"] or ""
            
            # Marcar es_cliente=1
            if re.search(r"es_cliente=[^;]+", atributos_prospecto):
                atributos_prospecto = re.sub(r"es_cliente=[^;]+", "es_cliente=1", atributos_prospecto)
            else:
                atributos_prospecto += ";es_cliente=1"
            
            # Registrar fecha_conversion
            hoy = date.today().isoformat()
            if re.search(r"fecha_conversion_cliente=[^;]+", atributos_prospecto):
                atributos_prospecto = re.sub(r"fecha_conversion_cliente=[^;]+", f"fecha_conversion_cliente={hoy}", atributos_prospecto)
            else:
                atributos_prospecto += f";fecha_conversion_cliente={hoy}"
            
            cur.execute("""
                UPDATE aup_agentes SET atributos=? WHERE id=?
            """, (atributos_prospecto, prospecto_id))
        
        self.db.commit()
        return True
    
    def actualizar_oc(self, oportunidad_id: int, oc_recibida: bool) -> bool:
        """
        REGLA R4: Actualiza el estado de la OC recibida
        Habilita/deshabilita la facturación
        """
        cur = self.db.cursor()
        cur.execute("SELECT * FROM aup_agentes WHERE id=? AND tipo='oportunidad'", (oportunidad_id,))
        row = cur.fetchone()
        
        if not row:
            return False
        
        atributos = row["atributos"] or ""
        import re
        
        valor = "1" if oc_recibida else "0"
        if re.search(r"oc_recibida=[^;]+", atributos):
            atributos = re.sub(r"oc_recibida=[^;]+", f"oc_recibida={valor}", atributos)
        else:
            atributos += f";oc_recibida={valor}"
        
        cur.execute("""
            UPDATE aup_agentes SET atributos=? WHERE id=?
        """, (atributos, oportunidad_id))
        
        self.db.commit()
        return True
    
    def listar_por_prospecto(self, prospecto_id: int) -> list:
        """Lista todas las oportunidades de un prospecto"""
        cur = self.db.cursor()
        cur.execute("""
            SELECT o.*
            FROM aup_agentes o
            INNER JOIN aup_relaciones r ON r.agente_destino = o.id
            WHERE r.agente_origen = ? AND r.tipo_relacion = 'tiene_oportunidad' AND o.tipo = 'oportunidad'
            ORDER BY o.fecha_creacion DESC
        """, (prospecto_id,))
        
        return self._parse_rows(cur.fetchall())
    
    def listar_todas(self, solo_activas: bool = True) -> list:
        """Lista todas las oportunidades del sistema"""
        cur = self.db.cursor()
        query = "SELECT * FROM aup_agentes WHERE tipo='oportunidad'"
        if solo_activas:
            query += " AND activo=1"
        query += " ORDER BY fecha_creacion DESC"
        
        cur.execute(query)
        return self._parse_rows(cur.fetchall())
    
    def _parse_rows(self, rows) -> list:
        """Convierte filas de DB en objetos Oportunidad"""
        oportunidades = []
        for row in rows:
            atributos = row["atributos"] or ""
            attrs_dict = {}
            for item in atributos.split(";"):
                if "=" in item:
                    key, val = item.split("=", 1)
                    attrs_dict[key] = val
            
            oportunidades.append(Oportunidad(
                id=row["id"],
                nombre=row["nombre"],
                prospecto_id=None,  # Se obtendría de la relación si es necesario
                monto=Decimal(attrs_dict.get("monto", "0.00")),
                probabilidad=int(attrs_dict.get("probabilidad", "0")),
                etapa=attrs_dict.get("etapa", "Calificación"),
                oc_recibida=attrs_dict.get("oc_recibida", "0") == "1",
                fecha_estimada_cierre=date.fromisoformat(attrs_dict["fecha_estimada_cierre"]) if attrs_dict.get("fecha_estimada_cierre") else None,
                descripcion=attrs_dict.get("descripcion", ""),
                activo=bool(row["activo"]),
                fecha_creacion=datetime.fromisoformat(row["fecha_creacion"]) if row.get("fecha_creacion") else None
            ))
        
        return oportunidades
