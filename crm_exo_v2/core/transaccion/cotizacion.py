# -*- coding: utf-8 -*-
"""
Módulo Cotización - Entidad de Transacción AUP
Gestiona cotizaciones con 3 modos: mínimo, genérico, externo
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from decimal import Decimal
import hashlib
import json


@dataclass
class Cotizacion:
    """
    Entidad Cotización según arquitectura AUP-EXO v2
    
    MODO MÍNIMO: Sin desglose, solo monto total
    MODO GENÉRICO: Catálogo interno de productos/servicios
    MODO EXTERNO: Importación desde archivo (PDF/Excel/API)
    
    Atributos:
    - id: Identificador único
    - id_oportunidad: Oportunidad asociada (obligatoria)
    - modo: Tipo de cotización (minimo|generico|externo)
    - fuente: Origen de datos (manual|catalogo|import_pdf|api)
    - monto_total: Monto total de la cotización
    - moneda: Moneda (MXN, USD)
    - version: Número de versión de la cotización
    - estado: Estado actual (Borrador|Enviada|Aprobada|Rechazada)
    - hash_integridad: Hash SHA256 para trazabilidad
    """
    
    id: Optional[int] = None
    id_oportunidad: Optional[int] = None
    modo: str = "minimo"  # minimo|generico|externo
    fuente: str = "manual"
    monto_total: Decimal = Decimal("0.00")
    moneda: str = "MXN"
    version: int = 1
    estado: str = "Borrador"
    fecha_creacion: Optional[datetime] = None
    hash_integridad: Optional[str] = None
    notas: str = ""
    
    def __post_init__(self):
        if self.fecha_creacion is None:
            self.fecha_creacion = datetime.now()
        if isinstance(self.monto_total, (int, float)):
            self.monto_total = Decimal(str(self.monto_total))
    
    def validar(self) -> tuple[bool, str]:
        """
        Valida los datos de la cotización
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        if not self.id_oportunidad:
            return False, "La cotización debe estar asociada a una oportunidad"
        
        if self.modo not in ["minimo", "generico", "externo"]:
            return False, "Modo de cotización inválido (minimo|generico|externo)"
        
        if self.monto_total <= 0:
            return False, "El monto total debe ser mayor a cero"
        
        if self.moneda not in ["MXN", "USD", "EUR"]:
            return False, "Moneda inválida"
        
        if self.estado not in ["Borrador", "Enviada", "Aprobada", "Rechazada"]:
            return False, "Estado inválido"
        
        return True, ""
    
    def generar_hash(self) -> str:
        """
        Genera hash SHA256 de integridad forense
        
        Incluye: id_oportunidad, modo, monto_total, version, fecha_creacion
        """
        data = {
            "id_oportunidad": self.id_oportunidad,
            "modo": self.modo,
            "monto_total": float(self.monto_total),
            "moneda": self.moneda,
            "version": self.version,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else ""
        }
        
        data_str = json.dumps(data, sort_keys=True)
        self.hash_integridad = hashlib.sha256(data_str.encode()).hexdigest()
        return self.hash_integridad
    
    def verificar_integridad(self) -> bool:
        """Verifica que el hash actual coincida con el almacenado"""
        hash_actual = self.generar_hash()
        return hash_actual == self.hash_integridad
    
    def to_dict(self) -> dict:
        """Convierte la cotización a diccionario"""
        return {
            "id": self.id,
            "id_oportunidad": self.id_oportunidad,
            "modo": self.modo,
            "fuente": self.fuente,
            "monto_total": float(self.monto_total),
            "moneda": self.moneda,
            "version": self.version,
            "estado": self.estado,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            "hash_integridad": self.hash_integridad,
            "notas": self.notas
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Cotizacion':
        """Crea una instancia de Cotización desde un diccionario"""
        return cls(
            id=data.get("id"),
            id_oportunidad=data.get("id_oportunidad"),
            modo=data.get("modo", "minimo"),
            fuente=data.get("fuente", "manual"),
            monto_total=Decimal(str(data.get("monto_total", "0.00"))),
            moneda=data.get("moneda", "MXN"),
            version=data.get("version", 1),
            estado=data.get("estado", "Borrador"),
            fecha_creacion=datetime.fromisoformat(data["fecha_creacion"]) if data.get("fecha_creacion") else None,
            hash_integridad=data.get("hash_integridad"),
            notas=data.get("notas", "")
        )


class CotizacionRepository:
    """Repositorio para operaciones CRUD de Cotización"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def crear(self, cotizacion: Cotizacion) -> Optional[int]:
        """
        Crea una nueva cotización con hash forense
        
        Returns:
            int: ID de la cotización creada
        """
        # Validar
        es_valido, mensaje = cotizacion.validar()
        if not es_valido:
            raise ValueError(mensaje)
        
        # Generar hash de integridad
        cotizacion.generar_hash()
        
        # Insertar
        cur = self.db.cursor()
        cur.execute("""
            INSERT INTO cotizaciones (
                id_oportunidad, modo, fuente, monto_total, moneda,
                version, estado, fecha_creacion, hash_integridad, notas
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cotizacion.id_oportunidad,
            cotizacion.modo,
            cotizacion.fuente,
            float(cotizacion.monto_total),
            cotizacion.moneda,
            cotizacion.version,
            cotizacion.estado,
            cotizacion.fecha_creacion.isoformat() if cotizacion.fecha_creacion else datetime.now().isoformat(),
            cotizacion.hash_integridad,
            cotizacion.notas
        ))
        
        cotizacion_id = cur.lastrowid
        
        # Registrar hash en trazabilidad
        cur.execute("""
            INSERT INTO hash_registros (tabla_origen, id_registro, hash_sha256)
            VALUES (?, ?, ?)
        """, ("cotizaciones", cotizacion_id, cotizacion.hash_integridad))
        
        self.db.commit()
        return cotizacion_id
    
    def obtener_por_id(self, cotizacion_id: int) -> Optional[Cotizacion]:
        """Obtiene una cotización por ID"""
        cur = self.db.cursor()
        cur.execute("SELECT * FROM cotizaciones WHERE id_cotizacion = ?", (cotizacion_id,))
        row = cur.fetchone()
        
        if not row:
            return None
        
        return Cotizacion(
            id=row["id_cotizacion"],
            id_oportunidad=row["id_oportunidad"],
            modo=row["modo"],
            fuente=row["fuente"],
            monto_total=Decimal(str(row["monto_total"])),
            moneda=row["moneda"],
            version=row["version"],
            estado=row["estado"],
            fecha_creacion=datetime.fromisoformat(row["fecha_creacion"]) if row["fecha_creacion"] else None,
            hash_integridad=row["hash_integridad"],
            notas=row["notas"] or ""
        )
    
    def listar_por_oportunidad(self, oportunidad_id: int) -> list:
        """Lista todas las cotizaciones de una oportunidad"""
        cur = self.db.cursor()
        cur.execute("""
            SELECT * FROM cotizaciones
            WHERE id_oportunidad = ?
            ORDER BY version DESC, fecha_creacion DESC
        """, (oportunidad_id,))
        
        cotizaciones = []
        for row in cur.fetchall():
            cotizaciones.append(Cotizacion(
                id=row["id_cotizacion"],
                id_oportunidad=row["id_oportunidad"],
                modo=row["modo"],
                fuente=row["fuente"],
                monto_total=Decimal(str(row["monto_total"])),
                moneda=row["moneda"],
                version=row["version"],
                estado=row["estado"],
                fecha_creacion=datetime.fromisoformat(row["fecha_creacion"]) if row["fecha_creacion"] else None,
                hash_integridad=row["hash_integridad"],
                notas=row["notas"] or ""
            ))
        
        return cotizaciones
    
    def actualizar_estado(self, cotizacion_id: int, nuevo_estado: str) -> bool:
        """Actualiza el estado de una cotización"""
        if nuevo_estado not in ["Borrador", "Enviada", "Aprobada", "Rechazada"]:
            return False
        
        cur = self.db.cursor()
        cur.execute("""
            UPDATE cotizaciones SET estado = ? WHERE id_cotizacion = ?
        """, (nuevo_estado, cotizacion_id))
        
        self.db.commit()
        return True
    
    def crear_nueva_version(self, cotizacion_id: int) -> Optional[int]:
        """
        Crea una nueva versión de una cotización existente
        Incrementa el número de versión y copia los datos
        """
        cotizacion_original = self.obtener_por_id(cotizacion_id)
        if not cotizacion_original:
            return None
        
        # Crear nueva versión
        nueva = Cotizacion(
            id_oportunidad=cotizacion_original.id_oportunidad,
            modo=cotizacion_original.modo,
            fuente=cotizacion_original.fuente,
            monto_total=cotizacion_original.monto_total,
            moneda=cotizacion_original.moneda,
            version=cotizacion_original.version + 1,
            estado="Borrador",
            notas=f"Versión {cotizacion_original.version + 1} basada en cotización #{cotizacion_id}"
        )
        
        return self.crear(nueva)
