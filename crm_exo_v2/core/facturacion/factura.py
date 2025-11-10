# -*- coding: utf-8 -*-
"""
Módulo Factura - Entidad de Facturación AUP
Gestiona facturas CFDI con hash forense
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
import hashlib
import json


@dataclass
class Factura:
    """
    Entidad Factura según arquitectura AUP-EXO v2
    
    Representa facturas CFDI con trazabilidad forense completa
    
    Atributos:
    - id: Identificador único
    - id_oc: Orden de compra asociada (obligatoria - REGLA R4)
    - uuid: UUID fiscal del CFDI
    - serie: Serie de la factura
    - folio: Folio de la factura
    - fecha_emision: Fecha de emisión
    - monto_total: Monto total facturado
    - moneda: Moneda (MXN, USD)
    - archivo_xml: Ruta del archivo XML
    - archivo_pdf: Ruta del archivo PDF
    """
    
    id: Optional[int] = None
    id_oc: Optional[int] = None
    uuid: str = ""
    serie: str = ""
    folio: str = ""
    fecha_emision: Optional[date] = None
    monto_total: Decimal = Decimal("0.00")
    moneda: str = "MXN"
    archivo_xml: Optional[str] = None
    archivo_pdf: Optional[str] = None
    
    def __post_init__(self):
        if isinstance(self.monto_total, (int, float)):
            self.monto_total = Decimal(str(self.monto_total))
    
    def validar(self) -> tuple[bool, str]:
        """
        Valida los datos de la factura
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        # REGLA R4: Debe tener OC asociada
        if not self.id_oc:
            return False, "La factura debe estar asociada a una orden de compra"
        
        if not self.uuid:
            return False, "El UUID fiscal es obligatorio"
        
        if not self.fecha_emision:
            return False, "La fecha de emisión es obligatoria"
        
        if self.monto_total <= 0:
            return False, "El monto debe ser mayor a cero"
        
        if self.moneda not in ["MXN", "USD", "EUR"]:
            return False, "Moneda inválida"
        
        return True, ""
    
    def generar_hash_forense(self) -> str:
        """
        Genera hash SHA256 forense de la factura
        
        Incluye: uuid, serie, folio, fecha_emision, monto_total
        """
        data = {
            "uuid": self.uuid,
            "serie": self.serie,
            "folio": self.folio,
            "fecha_emision": self.fecha_emision.isoformat() if self.fecha_emision else "",
            "monto_total": float(self.monto_total),
            "moneda": self.moneda
        }
        
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def to_dict(self) -> dict:
        """Convierte la factura a diccionario"""
        return {
            "id": self.id,
            "id_oc": self.id_oc,
            "uuid": self.uuid,
            "serie": self.serie,
            "folio": self.folio,
            "fecha_emision": self.fecha_emision.isoformat() if self.fecha_emision else None,
            "monto_total": float(self.monto_total),
            "moneda": self.moneda,
            "archivo_xml": self.archivo_xml,
            "archivo_pdf": self.archivo_pdf
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Factura':
        """Crea una instancia de Factura desde un diccionario"""
        return cls(
            id=data.get("id"),
            id_oc=data.get("id_oc"),
            uuid=data.get("uuid", ""),
            serie=data.get("serie", ""),
            folio=data.get("folio", ""),
            fecha_emision=date.fromisoformat(data["fecha_emision"]) if data.get("fecha_emision") else None,
            monto_total=Decimal(str(data.get("monto_total", "0.00"))),
            moneda=data.get("moneda", "MXN"),
            archivo_xml=data.get("archivo_xml"),
            archivo_pdf=data.get("archivo_pdf")
        )


class FacturaRepository:
    """Repositorio para operaciones CRUD de Factura"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def crear(self, factura: Factura) -> Optional[int]:
        """
        Crea una nueva factura con hash forense
        
        REGLA R4: Solo si existe OC asociada
        
        Returns:
            int: ID de la factura creada
        """
        # Validar
        es_valido, mensaje = factura.validar()
        if not es_valido:
            raise ValueError(mensaje)
        
        # REGLA R4: Verificar que la OC exista
        cur = self.db.cursor()
        cur.execute("SELECT id_oc FROM ordenes_compra WHERE id_oc = ?", (factura.id_oc,))
        if not cur.fetchone():
            raise ValueError("La orden de compra no existe - REGLA R4 violada")
        
        # Generar hash forense
        hash_forense = factura.generar_hash_forense()
        
        # Insertar factura
        cur.execute("""
            INSERT INTO facturas (
                id_oc, uuid, serie, folio, fecha_emision, 
                monto_total, moneda, archivo_xml, archivo_pdf
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            factura.id_oc,
            factura.uuid,
            factura.serie,
            factura.folio,
            factura.fecha_emision.isoformat() if factura.fecha_emision else None,
            float(factura.monto_total),
            factura.moneda,
            factura.archivo_xml,
            factura.archivo_pdf
        ))
        
        factura_id = cur.lastrowid
        
        # Registrar hash forense en trazabilidad
        cur.execute("""
            INSERT INTO hash_registros (tabla_origen, id_registro, hash_sha256)
            VALUES (?, ?, ?)
        """, ("facturas", factura_id, hash_forense))
        
        # Registrar evento
        cur.execute("""
            INSERT INTO historial_general (entidad, id_entidad, accion, valor_nuevo, usuario)
            VALUES (?, ?, ?, ?, ?)
        """, ("factura", factura_id, "crear", f"Factura {factura.serie}-{factura.folio} UUID:{factura.uuid}", "sistema"))
        
        self.db.commit()
        return factura_id
    
    def obtener_por_id(self, factura_id: int) -> Optional[Factura]:
        """Obtiene una factura por ID"""
        cur = self.db.cursor()
        cur.execute("SELECT * FROM facturas WHERE id_factura = ?", (factura_id,))
        row = cur.fetchone()
        
        if not row:
            return None
        
        return Factura(
            id=row["id_factura"],
            id_oc=row["id_oc"],
            uuid=row["uuid"],
            serie=row["serie"],
            folio=row["folio"],
            fecha_emision=date.fromisoformat(row["fecha_emision"]) if row["fecha_emision"] else None,
            monto_total=Decimal(str(row["monto_total"])),
            moneda=row["moneda"],
            archivo_xml=row["archivo_xml"],
            archivo_pdf=row["archivo_pdf"]
        )
    
    def obtener_por_oc(self, oc_id: int) -> Optional[Factura]:
        """Obtiene la factura asociada a una OC"""
        cur = self.db.cursor()
        cur.execute("SELECT * FROM facturas WHERE id_oc = ?", (oc_id,))
        row = cur.fetchone()
        
        if not row:
            return None
        
        return Factura(
            id=row["id_factura"],
            id_oc=row["id_oc"],
            uuid=row["uuid"],
            serie=row["serie"],
            folio=row["folio"],
            fecha_emision=date.fromisoformat(row["fecha_emision"]) if row["fecha_emision"] else None,
            monto_total=Decimal(str(row["monto_total"])),
            moneda=row["moneda"],
            archivo_xml=row["archivo_xml"],
            archivo_pdf=row["archivo_pdf"]
        )
    
    def listar_todas(self, limite: int = 100) -> list:
        """Lista todas las facturas"""
        cur = self.db.cursor()
        cur.execute("""
            SELECT f.*, oc.numero_oc
            FROM facturas f
            LEFT JOIN ordenes_compra oc ON oc.id_oc = f.id_oc
            ORDER BY f.fecha_emision DESC
            LIMIT ?
        """, (limite,))
        
        facturas = []
        for row in cur.fetchall():
            facturas.append(Factura(
                id=row["id_factura"],
                id_oc=row["id_oc"],
                uuid=row["uuid"],
                serie=row["serie"],
                folio=row["folio"],
                fecha_emision=date.fromisoformat(row["fecha_emision"]) if row["fecha_emision"] else None,
                monto_total=Decimal(str(row["monto_total"])),
                moneda=row["moneda"],
                archivo_xml=row["archivo_xml"],
                archivo_pdf=row["archivo_pdf"]
            ))
        
        return facturas
    
    def verificar_integridad(self, factura_id: int) -> tuple[bool, str]:
        """
        Verifica la integridad forense de una factura
        
        Returns:
            tuple: (es_integra, mensaje)
        """
        factura = self.obtener_por_id(factura_id)
        if not factura:
            return False, "Factura no encontrada"
        
        # Calcular hash actual
        hash_actual = factura.generar_hash_forense()
        
        # Obtener hash almacenado
        cur = self.db.cursor()
        cur.execute("""
            SELECT hash_sha256 FROM hash_registros
            WHERE tabla_origen = 'facturas' AND id_registro = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (factura_id,))
        
        row = cur.fetchone()
        if not row:
            return False, "No hay hash forense registrado"
        
        hash_almacenado = row["hash_sha256"]
        
        if hash_actual == hash_almacenado:
            return True, "Integridad verificada ✓"
        else:
            return False, f"⚠️ INTEGRIDAD COMPROMETIDA - Hash actual: {hash_actual[:16]}... vs Almacenado: {hash_almacenado[:16]}..."
