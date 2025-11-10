# -*- coding: utf-8 -*-
"""
Módulo Orden de Compra - Entidad de Facturación AUP
Gestiona órdenes de compra como requisito previo a facturación
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path


@dataclass
class OrdenCompra:
    """
    Entidad Orden de Compra según arquitectura AUP-EXO v2
    
    REGLA R4 (v1): OC recibida es requisito para facturar
    
    Atributos:
    - id: Identificador único
    - id_oportunidad: Oportunidad asociada (obligatoria)
    - numero_oc: Número de la orden de compra del cliente
    - fecha_oc: Fecha de emisión de la OC
    - monto_oc: Monto de la orden de compra
    - moneda: Moneda (MXN, USD)
    - archivo_pdf: Ruta del archivo PDF de la OC
    """
    
    id: Optional[int] = None
    id_oportunidad: Optional[int] = None
    numero_oc: str = ""
    fecha_oc: Optional[date] = None
    monto_oc: Decimal = Decimal("0.00")
    moneda: str = "MXN"
    archivo_pdf: Optional[str] = None
    
    def __post_init__(self):
        if isinstance(self.monto_oc, (int, float)):
            self.monto_oc = Decimal(str(self.monto_oc))
    
    def validar(self) -> tuple[bool, str]:
        """
        Valida los datos de la orden de compra
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not self.id_oportunidad:
            return False, "La OC debe estar asociada a una oportunidad"
        
        if not self.numero_oc:
            return False, "El número de OC es obligatorio"
        
        if not self.fecha_oc:
            return False, "La fecha de OC es obligatoria"
        
        if self.monto_oc <= 0:
            return False, "El monto debe ser mayor a cero"
        
        if self.moneda not in ["MXN", "USD", "EUR"]:
            return False, "Moneda inválida"
        
        return True, ""
    
    def tiene_archivo_adjunto(self) -> bool:
        """Verifica si tiene archivo PDF adjunto"""
        if not self.archivo_pdf:
            return False
        return Path(self.archivo_pdf).exists()
    
    def to_dict(self) -> dict:
        """Convierte la OC a diccionario"""
        return {
            "id": self.id,
            "id_oportunidad": self.id_oportunidad,
            "numero_oc": self.numero_oc,
            "fecha_oc": self.fecha_oc.isoformat() if self.fecha_oc else None,
            "monto_oc": float(self.monto_oc),
            "moneda": self.moneda,
            "archivo_pdf": self.archivo_pdf
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'OrdenCompra':
        """Crea una instancia de OrdenCompra desde un diccionario"""
        return cls(
            id=data.get("id"),
            id_oportunidad=data.get("id_oportunidad"),
            numero_oc=data.get("numero_oc", ""),
            fecha_oc=date.fromisoformat(data["fecha_oc"]) if data.get("fecha_oc") else None,
            monto_oc=Decimal(str(data.get("monto_oc", "0.00"))),
            moneda=data.get("moneda", "MXN"),
            archivo_pdf=data.get("archivo_pdf")
        )


class OrdenCompraRepository:
    """Repositorio para operaciones CRUD de OrdenCompra"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def crear(self, oc: OrdenCompra) -> Optional[int]:
        """
        Crea una nueva orden de compra
        
        Returns:
            int: ID de la OC creada
        """
        # Validar
        es_valido, mensaje = oc.validar()
        if not es_valido:
            raise ValueError(mensaje)
        
        # Verificar que la oportunidad exista
        cur = self.db.cursor()
        cur.execute("SELECT id_oportunidad FROM oportunidades WHERE id_oportunidad = ?", (oc.id_oportunidad,))
        if not cur.fetchone():
            raise ValueError("La oportunidad no existe")
        
        # Insertar
        cur.execute("""
            INSERT INTO ordenes_compra (
                id_oportunidad, numero_oc, fecha_oc, monto_oc, moneda, archivo_pdf
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            oc.id_oportunidad,
            oc.numero_oc,
            oc.fecha_oc.isoformat() if oc.fecha_oc else None,
            float(oc.monto_oc),
            oc.moneda,
            oc.archivo_pdf
        ))
        
        oc_id = cur.lastrowid
        
        # Registrar evento en trazabilidad
        cur.execute("""
            INSERT INTO historial_general (entidad, id_entidad, accion, valor_nuevo, usuario)
            VALUES (?, ?, ?, ?, ?)
        """, ("orden_compra", oc_id, "crear", f"OC #{oc.numero_oc} - ${float(oc.monto_oc)} {oc.moneda}", "sistema"))
        
        self.db.commit()
        return oc_id
    
    def obtener_por_id(self, oc_id: int) -> Optional[OrdenCompra]:
        """Obtiene una OC por ID"""
        cur = self.db.cursor()
        cur.execute("SELECT * FROM ordenes_compra WHERE id_oc = ?", (oc_id,))
        row = cur.fetchone()
        
        if not row:
            return None
        
        return OrdenCompra(
            id=row["id_oc"],
            id_oportunidad=row["id_oportunidad"],
            numero_oc=row["numero_oc"],
            fecha_oc=date.fromisoformat(row["fecha_oc"]) if row["fecha_oc"] else None,
            monto_oc=Decimal(str(row["monto_oc"])),
            moneda=row["moneda"],
            archivo_pdf=row["archivo_pdf"]
        )
    
    def obtener_por_oportunidad(self, oportunidad_id: int) -> Optional[OrdenCompra]:
        """Obtiene la OC asociada a una oportunidad"""
        cur = self.db.cursor()
        cur.execute("""
            SELECT * FROM ordenes_compra WHERE id_oportunidad = ?
        """, (oportunidad_id,))
        row = cur.fetchone()
        
        if not row:
            return None
        
        return OrdenCompra(
            id=row["id_oc"],
            id_oportunidad=row["id_oportunidad"],
            numero_oc=row["numero_oc"],
            fecha_oc=date.fromisoformat(row["fecha_oc"]) if row["fecha_oc"] else None,
            monto_oc=Decimal(str(row["monto_oc"])),
            moneda=row["moneda"],
            archivo_pdf=row["archivo_pdf"]
        )
    
    def actualizar(self, oc: OrdenCompra) -> bool:
        """Actualiza una orden de compra existente"""
        if not oc.id:
            return False
        
        es_valido, mensaje = oc.validar()
        if not es_valido:
            raise ValueError(mensaje)
        
        cur = self.db.cursor()
        cur.execute("""
            UPDATE ordenes_compra 
            SET numero_oc = ?, fecha_oc = ?, monto_oc = ?, moneda = ?, archivo_pdf = ?
            WHERE id_oc = ?
        """, (
            oc.numero_oc,
            oc.fecha_oc.isoformat() if oc.fecha_oc else None,
            float(oc.monto_oc),
            oc.moneda,
            oc.archivo_pdf,
            oc.id
        ))
        
        # Registrar evento
        cur.execute("""
            INSERT INTO historial_general (entidad, id_entidad, accion, valor_nuevo, usuario)
            VALUES (?, ?, ?, ?, ?)
        """, ("orden_compra", oc.id, "actualizar", f"OC #{oc.numero_oc} actualizada", "sistema"))
        
        self.db.commit()
        return True
    
    def listar_todas(self) -> list:
        """Lista todas las órdenes de compra"""
        cur = self.db.cursor()
        cur.execute("""
            SELECT oc.*, o.nombre as nombre_oportunidad
            FROM ordenes_compra oc
            LEFT JOIN oportunidades o ON o.id_oportunidad = oc.id_oportunidad
            ORDER BY oc.fecha_oc DESC
        """)
        
        ocs = []
        for row in cur.fetchall():
            ocs.append(OrdenCompra(
                id=row["id_oc"],
                id_oportunidad=row["id_oportunidad"],
                numero_oc=row["numero_oc"],
                fecha_oc=date.fromisoformat(row["fecha_oc"]) if row["fecha_oc"] else None,
                monto_oc=Decimal(str(row["monto_oc"])),
                moneda=row["moneda"],
                archivo_pdf=row["archivo_pdf"]
            ))
        
        return ocs
