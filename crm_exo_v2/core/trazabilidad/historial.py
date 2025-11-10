# -*- coding: utf-8 -*-
"""
Módulo Historial - Entidad de Trazabilidad AUP
Sistema forense de auditoría con hash SHA256
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import hashlib
import json


@dataclass
class EventoHistorial:
    """
    Evento de auditoría forense según arquitectura AUP-EXO v2
    
    Registra toda acción en el sistema con:
    - Qué se modificó (entidad + id)
    - Qué cambió (valor_anterior → valor_nuevo)
    - Quién lo hizo (usuario)
    - Cuándo (timestamp)
    - Hash forense (SHA256)
    
    Atributos:
    - id: Identificador único del evento
    - entidad: Tipo de entidad (empresa, prospecto, oportunidad, etc.)
    - id_entidad: ID del registro afectado
    - accion: Tipo de acción (crear, actualizar, eliminar, convertir)
    - valor_anterior: Estado previo (JSON)
    - valor_nuevo: Estado nuevo (JSON)
    - usuario: Usuario que ejecutó la acción
    - timestamp: Fecha/hora exacta del evento
    - hash_evento: Hash SHA256 del evento completo
    """
    
    id: Optional[int] = None
    entidad: str = ""
    id_entidad: Optional[int] = None
    accion: str = ""
    valor_anterior: str = ""
    valor_nuevo: str = ""
    usuario: str = "sistema"
    timestamp: Optional[datetime] = None
    hash_evento: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def generar_hash(self) -> str:
        """
        Genera hash SHA256 forense del evento
        
        Incluye todos los campos críticos para detectar cualquier alteración
        """
        data = {
            "entidad": self.entidad,
            "id_entidad": self.id_entidad,
            "accion": self.accion,
            "valor_anterior": self.valor_anterior,
            "valor_nuevo": self.valor_nuevo,
            "usuario": self.usuario,
            "timestamp": self.timestamp.isoformat() if self.timestamp else ""
        }
        
        data_str = json.dumps(data, sort_keys=True)
        self.hash_evento = hashlib.sha256(data_str.encode()).hexdigest()
        return self.hash_evento
    
    def to_dict(self) -> dict:
        """Convierte el evento a diccionario"""
        return {
            "id": self.id,
            "entidad": self.entidad,
            "id_entidad": self.id_entidad,
            "accion": self.accion,
            "valor_anterior": self.valor_anterior,
            "valor_nuevo": self.valor_nuevo,
            "usuario": self.usuario,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "hash_evento": self.hash_evento
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'EventoHistorial':
        """Crea una instancia de EventoHistorial desde un diccionario"""
        return cls(
            id=data.get("id"),
            entidad=data.get("entidad", ""),
            id_entidad=data.get("id_entidad"),
            accion=data.get("accion", ""),
            valor_anterior=data.get("valor_anterior", ""),
            valor_nuevo=data.get("valor_nuevo", ""),
            usuario=data.get("usuario", "sistema"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
            hash_evento=data.get("hash_evento")
        )


class HistorialRepository:
    """Repositorio para operaciones de auditoría forense"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def registrar_evento(
        self,
        entidad: str,
        id_entidad: int,
        accion: str,
        valor_anterior: str = "",
        valor_nuevo: str = "",
        usuario: str = "sistema"
    ) -> int:
        """
        Registra un evento en el historial forense
        
        Args:
            entidad: Tipo de entidad afectada
            id_entidad: ID del registro
            accion: Acción ejecutada (crear, actualizar, eliminar, etc.)
            valor_anterior: Estado previo (JSON string)
            valor_nuevo: Estado nuevo (JSON string)
            usuario: Usuario responsable
        
        Returns:
            int: ID del evento creado
        """
        # Crear evento
        evento = EventoHistorial(
            entidad=entidad,
            id_entidad=id_entidad,
            accion=accion,
            valor_anterior=valor_anterior,
            valor_nuevo=valor_nuevo,
            usuario=usuario
        )
        
        # Generar hash forense
        evento.generar_hash()
        
        # Insertar en DB
        cur = self.db.cursor()
        cur.execute("""
            INSERT INTO historial_general (
                entidad, id_entidad, accion, valor_anterior, 
                valor_nuevo, usuario, timestamp, hash_evento
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            evento.entidad,
            evento.id_entidad,
            evento.accion,
            evento.valor_anterior,
            evento.valor_nuevo,
            evento.usuario,
            evento.timestamp.isoformat() if evento.timestamp else datetime.now().isoformat(),
            evento.hash_evento
        ))
        
        evento_id = cur.lastrowid
        self.db.commit()
        
        return evento_id
    
    def obtener_historial_entidad(
        self,
        entidad: str,
        id_entidad: int,
        limite: int = 50
    ) -> list:
        """
        Obtiene el historial completo de una entidad específica
        
        Returns:
            list: Lista de EventoHistorial ordenados cronológicamente
        """
        cur = self.db.cursor()
        cur.execute("""
            SELECT * FROM historial_general
            WHERE entidad = ? AND id_entidad = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (entidad, id_entidad, limite))
        
        eventos = []
        for row in cur.fetchall():
            eventos.append(EventoHistorial(
                id=row["id_evento"],
                entidad=row["entidad"],
                id_entidad=row["id_entidad"],
                accion=row["accion"],
                valor_anterior=row["valor_anterior"] or "",
                valor_nuevo=row["valor_nuevo"] or "",
                usuario=row["usuario"],
                timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None,
                hash_evento=row["hash_evento"]
            ))
        
        return eventos
    
    def obtener_historial_completo(self, limite: int = 100) -> list:
        """Obtiene el historial completo del sistema"""
        cur = self.db.cursor()
        cur.execute("""
            SELECT * FROM historial_general
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limite,))
        
        eventos = []
        for row in cur.fetchall():
            eventos.append(EventoHistorial(
                id=row["id_evento"],
                entidad=row["entidad"],
                id_entidad=row["id_entidad"],
                accion=row["accion"],
                valor_anterior=row["valor_anterior"] or "",
                valor_nuevo=row["valor_nuevo"] or "",
                usuario=row["usuario"],
                timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None,
                hash_evento=row["hash_evento"]
            ))
        
        return eventos
    
    def verificar_integridad_evento(self, evento_id: int) -> tuple[bool, str]:
        """
        Verifica la integridad forense de un evento específico
        
        Returns:
            tuple: (es_integro, mensaje)
        """
        cur = self.db.cursor()
        cur.execute("SELECT * FROM historial_general WHERE id_evento = ?", (evento_id,))
        row = cur.fetchone()
        
        if not row:
            return False, "Evento no encontrado"
        
        # Reconstruir evento
        evento = EventoHistorial(
            entidad=row["entidad"],
            id_entidad=row["id_entidad"],
            accion=row["accion"],
            valor_anterior=row["valor_anterior"] or "",
            valor_nuevo=row["valor_nuevo"] or "",
            usuario=row["usuario"],
            timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None
        )
        
        # Calcular hash actual
        hash_calculado = evento.generar_hash()
        hash_almacenado = row["hash_evento"]
        
        if hash_calculado == hash_almacenado:
            return True, "✓ Integridad verificada"
        else:
            return False, f"⚠️ INTEGRIDAD COMPROMETIDA - Evento #{evento_id}"
    
    def generar_cadena_custodia(self, entidad: str, id_entidad: int) -> dict:
        """
        Genera un reporte de cadena de custodia forense
        
        Returns:
            dict: Informe completo con todos los eventos y verificación de integridad
        """
        eventos = self.obtener_historial_entidad(entidad, id_entidad, limite=1000)
        
        reporte = {
            "entidad": entidad,
            "id_entidad": id_entidad,
            "total_eventos": len(eventos),
            "fecha_reporte": datetime.now().isoformat(),
            "eventos": [],
            "integridad_verificada": True,
            "eventos_comprometidos": []
        }
        
        for evento in eventos:
            es_integro, mensaje = self.verificar_integridad_evento(evento.id)
            
            evento_data = evento.to_dict()
            evento_data["integridad"] = es_integro
            reporte["eventos"].append(evento_data)
            
            if not es_integro:
                reporte["integridad_verificada"] = False
                reporte["eventos_comprometidos"].append(evento.id)
        
        return reporte
