# -*- coding: utf-8 -*-
"""
Módulo: Facturación CFDI 4.0 - Registro de Emisor
Integración con timbracfdi33.mx para CRM-EXO v2
Autor: SynAppsSys / Salvador Ruiz Esparza
Archivo: cfdi_emisor.py
"""

import base64
import requests
from datetime import datetime
from typing import Dict, Optional, Tuple
from pathlib import Path
import sys

# Agregar ruta del core al path para imports
CORE_PATH = Path(__file__).parent.parent
sys.path.insert(0, str(CORE_PATH))

from database import DatabaseV2


# ==========================================================
# 🔧 CONFIGURACIÓN API TIMBRACFDI33
# ==========================================================
API_CONFIG = {
    "pruebas": "https://pruebas.timbracfdi33.mx:1444/api/v2/Timbrado/RegistraEmisor",
    "produccion": "https://api.timbracfdi33.mx:1444/api/v2/Timbrado/RegistraEmisor"
}


# ==========================================================
# 🗄️ GESTIÓN DE BASE DE DATOS
# ==========================================================
class ConfiguracionEmisor:
    """Gestiona la configuración del emisor CFDI en la base de datos"""
    
    def __init__(self):
        self.db = DatabaseV2()
        self._crear_tablas()
    
    def _crear_tablas(self):
        """Crea las tablas necesarias para configuración CFDI si no existen"""
        conn = self.db.connection
        cursor = conn.cursor()
        
        # Tabla de configuración del emisor
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_cfdi_emisor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfc_emisor TEXT NOT NULL UNIQUE,
                razon_social TEXT,
                regimen_fiscal TEXT,
                token_api TEXT NOT NULL,
                modo TEXT NOT NULL CHECK(modo IN ('pruebas', 'produccion')),
                fecha_registro TEXT NOT NULL,
                fecha_actualizacion TEXT,
                activo INTEGER DEFAULT 1,
                UNIQUE(rfc_emisor)
            )
        """)
        
        # Tabla para guardar archivos CSD (certificados)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_cfdi_certificados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_emisor INTEGER NOT NULL,
                cer_base64 TEXT NOT NULL,
                key_base64 TEXT NOT NULL,
                numero_certificado TEXT,
                fecha_inicio_vigencia TEXT,
                fecha_fin_vigencia TEXT,
                fecha_carga TEXT NOT NULL,
                activo INTEGER DEFAULT 1,
                FOREIGN KEY (id_emisor) REFERENCES config_cfdi_emisor(id)
            )
        """)
        
        conn.commit()
    
    def guardar_emisor(self, rfc: str, token: str, modo: str, 
                       razon_social: str = None, regimen_fiscal: str = None) -> int:
        """
        Guarda o actualiza configuración del emisor
        
        Args:
            rfc: RFC del emisor
            token: Token de API de timbracfdi33.mx
            modo: 'pruebas' o 'produccion'
            razon_social: Nombre o razón social del emisor
            regimen_fiscal: Clave del régimen fiscal (ej: '601')
            
        Returns:
            ID del emisor guardado
        """
        conn = self.db.connection
        cursor = conn.cursor()
        
        # Verificar si ya existe
        cursor.execute("SELECT id FROM config_cfdi_emisor WHERE rfc_emisor = ?", (rfc,))
        row = cursor.fetchone()
        
        fecha_actual = datetime.now().isoformat()
        
        if row:
            # Actualizar
            cursor.execute("""
                UPDATE config_cfdi_emisor 
                SET token_api = ?, modo = ?, razon_social = ?, 
                    regimen_fiscal = ?, fecha_actualizacion = ?
                WHERE rfc_emisor = ?
            """, (token, modo, razon_social, regimen_fiscal, fecha_actual, rfc))
            emisor_id = row[0]
        else:
            # Insertar
            cursor.execute("""
                INSERT INTO config_cfdi_emisor 
                (rfc_emisor, razon_social, regimen_fiscal, token_api, modo, fecha_registro)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (rfc, razon_social, regimen_fiscal, token, modo, fecha_actual))
            emisor_id = cursor.lastrowid
        
        conn.commit()
        return emisor_id
    
    def guardar_certificados(self, emisor_id: int, cer_bytes: bytes, 
                            key_bytes: bytes, numero_cert: str = None) -> int:
        """
        Guarda los certificados CSD del emisor
        
        Args:
            emisor_id: ID del emisor en la BD
            cer_bytes: Contenido binario del archivo .cer
            key_bytes: Contenido binario del archivo .key
            numero_cert: Número del certificado (opcional)
            
        Returns:
            ID del registro de certificados
        """
        conn = self.db.connection
        cursor = conn.cursor()
        
        # Convertir a base64
        cer_b64 = base64.b64encode(cer_bytes).decode("utf-8")
        key_b64 = base64.b64encode(key_bytes).decode("utf-8")
        
        # Desactivar certificados anteriores
        cursor.execute("""
            UPDATE config_cfdi_certificados 
            SET activo = 0 
            WHERE id_emisor = ?
        """, (emisor_id,))
        
        # Insertar nuevo certificado
        cursor.execute("""
            INSERT INTO config_cfdi_certificados 
            (id_emisor, cer_base64, key_base64, numero_certificado, fecha_carga)
            VALUES (?, ?, ?, ?, ?)
        """, (emisor_id, cer_b64, key_b64, numero_cert, datetime.now().isoformat()))
        
        cert_id = cursor.lastrowid
        conn.commit()
        return cert_id
    
    def obtener_emisor_activo(self) -> Optional[Dict]:
        """Obtiene la configuración del emisor activo"""
        conn = self.db.connection
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, rfc_emisor, razon_social, regimen_fiscal, token_api, modo
            FROM config_cfdi_emisor
            WHERE activo = 1
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'rfc': row[1],
                'razon_social': row[2],
                'regimen_fiscal': row[3],
                'token': row[4],
                'modo': row[5]
            }
        return None
    
    def obtener_certificados_activos(self, emisor_id: int) -> Optional[Dict]:
        """Obtiene los certificados activos del emisor"""
        conn = self.db.connection
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT cer_base64, key_base64, numero_certificado
            FROM config_cfdi_certificados
            WHERE id_emisor = ? AND activo = 1
            LIMIT 1
        """, (emisor_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'cer_base64': row[0],
                'key_base64': row[1],
                'numero_certificado': row[2]
            }
        return None


# ==========================================================
# 🌐 INTEGRACIÓN CON API TIMBRACFDI33
# ==========================================================
class RegistroEmisorCFDI:
    """Cliente para registro de emisor en PAC TimbrarCFDI33"""
    
    def __init__(self):
        self.config_repo = ConfiguracionEmisor()
        self.db = DatabaseV2()
    
    def registrar_emisor(self, rfc: str, cer_bytes: bytes, key_bytes: bytes, 
                        contrasena: str, token: str, modo: str,
                        razon_social: str = None, regimen_fiscal: str = None) -> Tuple[bool, str, Dict]:
        """
        Registra el emisor en el PAC TimbrarCFDI33
        
        Args:
            rfc: RFC del emisor
            cer_bytes: Contenido del archivo .cer
            key_bytes: Contenido del archivo .key
            contrasena: Contraseña del archivo .key
            token: Token de API
            modo: 'pruebas' o 'produccion'
            razon_social: Razón social del emisor
            regimen_fiscal: Clave de régimen fiscal
            
        Returns:
            Tupla (éxito: bool, mensaje: str, datos_respuesta: dict)
        """
        try:
            # Preparar datos para API
            cer_b64 = base64.b64encode(cer_bytes).decode("utf-8")
            key_b64 = base64.b64encode(key_bytes).decode("utf-8")
            
            data = {
                "RfcEmisor": rfc,
                "Base64Cer": cer_b64,
                "Base64Key": key_b64,
                "Contrasena": contrasena
            }
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # Seleccionar URL según modo
            api_url = API_CONFIG.get(modo)
            if not api_url:
                return False, f"Modo inválido: {modo}", {}
            
            # Hacer petición al PAC
            response = requests.post(api_url, json=data, headers=headers, timeout=30)
            
            # Procesar respuesta
            if response.status_code == 200:
                # Guardar configuración en BD
                emisor_id = self.config_repo.guardar_emisor(
                    rfc=rfc,
                    token=token,
                    modo=modo,
                    razon_social=razon_social,
                    regimen_fiscal=regimen_fiscal
                )
                
                # Guardar certificados
                self.config_repo.guardar_certificados(
                    emisor_id=emisor_id,
                    cer_bytes=cer_bytes,
                    key_bytes=key_bytes
                )
                
                # Registrar en historial
                self._registrar_evento(
                    entidad="cfdi_emisor",
                    id_entidad=emisor_id,
                    accion="Registro exitoso en PAC",
                    valor_nuevo=f"RFC: {rfc} | Modo: {modo}",
                    usuario=rfc
                )
                
                return True, "Emisor registrado correctamente", response.json()
            
            elif response.status_code == 401:
                self._registrar_evento(
                    entidad="cfdi_emisor",
                    id_entidad=0,
                    accion="Error 401 - Token inválido",
                    valor_nuevo=f"RFC: {rfc}",
                    usuario=rfc
                )
                return False, "Token inválido o caducado (Error 401)", {}
            
            else:
                self._registrar_evento(
                    entidad="cfdi_emisor",
                    id_entidad=0,
                    accion=f"Error {response.status_code}",
                    valor_nuevo=response.text[:200],
                    usuario=rfc
                )
                return False, f"Error {response.status_code}: {response.text}", {}
        
        except requests.exceptions.Timeout:
            return False, "Tiempo de espera agotado. Verifica tu conexión.", {}
        except requests.exceptions.ConnectionError:
            return False, "Error de conexión. Verifica tu internet.", {}
        except Exception as e:
            self._registrar_evento(
                entidad="cfdi_emisor",
                id_entidad=0,
                accion="Error general",
                valor_nuevo=str(e),
                usuario=rfc
            )
            return False, f"Error inesperado: {str(e)}", {}
    
    def _registrar_evento(self, entidad: str, id_entidad: int, accion: str, 
                         valor_nuevo: str, usuario: str):
        """Registra evento en historial_general"""
        conn = self.db.connection
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        hash_evento = self._generar_hash(entidad, id_entidad, accion, timestamp)
        
        cursor.execute("""
            INSERT INTO historial_general 
            (entidad, id_entidad, accion, valor_nuevo, usuario, timestamp, hash_evento)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (entidad, id_entidad, accion, valor_nuevo, usuario, timestamp, hash_evento))
        
        conn.commit()
    
    def _generar_hash(self, entidad: str, id_entidad: int, accion: str, timestamp: str) -> str:
        """Genera hash para evento de historial"""
        import hashlib
        cadena = f"{entidad}{id_entidad}{accion}{timestamp}"
        return hashlib.sha256(cadena.encode()).hexdigest()[:16]


# ==========================================================
# 🔍 FUNCIONES DE CONSULTA
# ==========================================================
def obtener_configuracion_emisor() -> Optional[Dict]:
    """Obtiene la configuración completa del emisor activo"""
    config = ConfiguracionEmisor()
    emisor = config.obtener_emisor_activo()
    
    if emisor:
        certificados = config.obtener_certificados_activos(emisor['id'])
        if certificados:
            emisor['certificados'] = certificados
    
    return emisor


def validar_configuracion_cfdi() -> Tuple[bool, str]:
    """
    Valida que exista configuración completa para facturación
    
    Returns:
        Tupla (válido: bool, mensaje: str)
    """
    config = obtener_configuracion_emisor()
    
    if not config:
        return False, "No hay emisor configurado"
    
    if not config.get('token'):
        return False, "Falta token de API"
    
    if 'certificados' not in config:
        return False, "No hay certificados CSD cargados"
    
    return True, "Configuración CFDI completa"
