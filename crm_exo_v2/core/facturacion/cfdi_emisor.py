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
from typing import Dict, Optional, Tuple, Union
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

# Agregar ruta del core al path para imports
CORE_PATH = Path(__file__).parent.parent
sys.path.insert(0, str(CORE_PATH))

from database import DatabaseV2


# ==========================================================
# 🔧 CONFIGURACIÓN API TIMBRACFDI33
# ==========================================================
API_CONFIG = {
    "pruebas": {
        "registra_emisor": "https://pruebas.timbracfdi33.mx:1444/api/v2/Timbrado/RegistraEmisor",
        "timbrado_cfdi": "https://pruebas.timbracfdi33.mx:1444/api/v2/Timbrado/TimbraCFDI"
    },
    "produccion": {
        "registra_emisor": "https://api.timbracfdi33.mx:1444/api/v2/Timbrado/RegistraEmisor",
        "timbrado_cfdi": "https://api.timbracfdi33.mx:1444/api/v2/Timbrado/TimbraCFDI"
    }
}


def obtener_endpoint_api(modo: str, operacion: str) -> Optional[str]:
    config_modo = API_CONFIG.get(modo)
    if not config_modo:
        return None
    return config_modo.get(operacion)


# ==========================================================
# 🗄️ GESTIÓN DE BASE DE DATOS
# ==========================================================
class ConfiguracionEmisor:
    """Gestiona la configuración del emisor CFDI en la base de datos"""
    
    def __init__(self):
        self.db = DatabaseV2()
        self._crear_tablas()
    
    def _get_lastrowid(self, cursor) -> int:
        """
        Obtiene el ID del último registro insertado de forma compatible con SQLite y PostgreSQL
        
        Args:
            cursor: Cursor de la base de datos
            
        Returns:
            ID del último registro insertado
        """
        if self.db.is_postgres:
            # En PostgreSQL con psycopg, el ID viene en el cursor después de un INSERT con RETURNING
            # Si no usamos RETURNING, debemos hacer un query separado
            # Por ahora, asumimos que lastrowid funciona en psycopg (versión 3+)
            return cursor.lastrowid if hasattr(cursor, 'lastrowid') else None
        else:
            # En SQLite funciona normal
            return cursor.lastrowid
    
    def _crear_tablas(self):
        """Crea las tablas necesarias para configuración CFDI si no existen"""
        # Detectar sintaxis de auto-increment según motor de DB
        if self.db.is_postgres:
            # PostgreSQL usa SERIAL o GENERATED ALWAYS AS IDENTITY
            pk_autoincrement = "SERIAL PRIMARY KEY"
        else:
            # SQLite usa AUTOINCREMENT
            pk_autoincrement = "INTEGER PRIMARY KEY AUTOINCREMENT"
        
        # Tabla de configuración del emisor
        self.db.execute(f"""
            CREATE TABLE IF NOT EXISTS config_cfdi_emisor (
                id {pk_autoincrement},
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
        self.db.execute(f"""
            CREATE TABLE IF NOT EXISTS config_cfdi_certificados (
                id {pk_autoincrement},
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
        
        self.db.commit()
    
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
        # Verificar si ya existe
        cursor = self.db.execute("SELECT id FROM config_cfdi_emisor WHERE rfc_emisor = ?", (rfc,))
        row = cursor.fetchone()
        
        fecha_actual = datetime.now().isoformat()
        
        if row:
            # Actualizar
            self.db.execute("""
                UPDATE config_cfdi_emisor 
                SET token_api = ?, modo = ?, razon_social = ?, 
                    regimen_fiscal = ?, fecha_actualizacion = ?
                WHERE rfc_emisor = ?
            """, (token, modo, razon_social, regimen_fiscal, fecha_actual, rfc))
            emisor_id = row[0]
        else:
            # Insertar
            cursor = self.db.execute("""
                INSERT INTO config_cfdi_emisor 
                (rfc_emisor, razon_social, regimen_fiscal, token_api, modo, fecha_registro)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (rfc, razon_social, regimen_fiscal, token, modo, fecha_actual))
            emisor_id = self._get_lastrowid(cursor)
        
        self.db.commit()
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
        # Convertir a base64
        cer_b64 = base64.b64encode(cer_bytes).decode("utf-8")
        key_b64 = base64.b64encode(key_bytes).decode("utf-8")
        
        # Desactivar certificados anteriores
        self.db.execute("""
            UPDATE config_cfdi_certificados 
            SET activo = 0 
            WHERE id_emisor = ?
        """, (emisor_id,))
        
        # Insertar nuevo certificado
        cursor = self.db.execute("""
            INSERT INTO config_cfdi_certificados 
            (id_emisor, cer_base64, key_base64, numero_certificado, fecha_carga)
            VALUES (?, ?, ?, ?, ?)
        """, (emisor_id, cer_b64, key_b64, numero_cert, datetime.now().isoformat()))
        
        cert_id = self._get_lastrowid(cursor)
        self.db.commit()
        return cert_id
    
    def obtener_emisor_activo(self) -> Optional[Dict]:
        """Obtiene la configuración del emisor activo"""
        cursor = self.db.execute("""
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
        cursor = self.db.execute("""
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
            api_url = obtener_endpoint_api(modo, "registra_emisor")
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
                try:
                    response_data = response.json()
                except ValueError:
                    response_data = {}

                mensaje_pac = response_data.get("Mensaje") if isinstance(response_data, dict) else None
                codigo_pac = response_data.get("Codigo") if isinstance(response_data, dict) else None

                self._registrar_evento(
                    entidad="cfdi_emisor",
                    id_entidad=0,
                    accion=f"Error {response.status_code}",
                    valor_nuevo=response.text[:200],
                    usuario=rfc
                )

                if codigo_pac == 20133 or mensaje_pac == "Certificado es FIEL.":
                    return False, (
                        "El PAC rechazó el certificado porque es una FIEL/e.firma. "
                        "Para timbrar debes cargar un CSD vigente del SAT: archivo .cer, archivo .key y su contraseña correspondientes al sello digital."
                    ), response_data

                if mensaje_pac:
                    return False, f"Error {response.status_code}: {mensaje_pac}", response_data

                return False, f"Error {response.status_code}: {response.text}", response_data
        
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
        timestamp = datetime.now().isoformat()
        hash_evento = self._generar_hash(entidad, id_entidad, accion, timestamp)

        self.db.execute("""
            INSERT INTO historial_general
            (entidad, id_entidad, accion, valor_nuevo, usuario, timestamp, hash_evento)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (entidad, id_entidad, accion, valor_nuevo, usuario, timestamp, hash_evento))

        self.db.commit()

    def _generar_hash(self, entidad: str, id_entidad: int, accion: str, timestamp: str) -> str:
        """Genera hash para evento de historial"""
        import hashlib
        cadena = f"{entidad}{id_entidad}{accion}{timestamp}"
        return hashlib.sha256(cadena.encode()).hexdigest()[:16]


class TimbradoCFDI:
    """Cliente para timbrado CFDI usando TimbrarCFDI33."""

    def __init__(self):
        self.config_repo = ConfiguracionEmisor()
        self.db = DatabaseV2()

    def timbrar_cfdi(self, xml_comprobante: Union[str, bytes], id_comprobante: Optional[str] = None) -> Tuple[bool, str, Dict]:
        config = self.config_repo.obtener_emisor_activo()
        if not config:
            return False, "No hay emisor CFDI configurado", {}

        token = config.get("token")
        modo = config.get("modo")
        rfc = config.get("rfc") or "desconocido"

        if not token:
            return False, "La configuración CFDI no tiene token API", {}

        api_url = obtener_endpoint_api(modo, "timbrado_cfdi")
        if not api_url:
            return False, f"Modo inválido: {modo}", {}

        if isinstance(xml_comprobante, str):
            xml_bytes = xml_comprobante.encode("utf-8")
        else:
            xml_bytes = xml_comprobante

        payload = {
            "XmlComprobanteBase64": base64.b64encode(xml_bytes).decode("utf-8")
        }
        if id_comprobante:
            payload["IdComprobante"] = id_comprobante

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)
            response_data = self._parse_response_json(response)

            if response.status_code == 200 and response_data.get("Codigo") == 0:
                xml_timbrado = response_data.get("Xml", "")
                uuid = self._extraer_uuid_xml(xml_timbrado)
                self._registrar_evento(
                    entidad="cfdi_timbrado",
                    id_entidad=0,
                    accion="Timbrado exitoso",
                    valor_nuevo=f"RFC: {rfc} | UUID: {uuid or 'sin_uuid'} | IdComprobante: {id_comprobante or 'n/d'}",
                    usuario=rfc
                )
                if uuid:
                    response_data["UUID"] = uuid
                return True, "CFDI timbrado correctamente", response_data

            mensaje_error = self._build_error_message(response.status_code, response_data, response.text)
            self._registrar_evento(
                entidad="cfdi_timbrado",
                id_entidad=0,
                accion=f"Error {response.status_code}",
                valor_nuevo=mensaje_error[:300],
                usuario=rfc
            )
            return False, mensaje_error, response_data
        except requests.exceptions.Timeout:
            return False, "Tiempo de espera agotado al timbrar CFDI", {}
        except requests.exceptions.ConnectionError:
            return False, "Error de conexión con TimbrarCFDI33", {}
        except Exception as e:
            self._registrar_evento(
                entidad="cfdi_timbrado",
                id_entidad=0,
                accion="Error general",
                valor_nuevo=str(e),
                usuario=rfc
            )
            return False, f"Error inesperado al timbrar CFDI: {str(e)}", {}

    def _parse_response_json(self, response: requests.Response) -> Dict:
        try:
            data = response.json()
            return data if isinstance(data, dict) else {"raw": data}
        except ValueError:
            return {}

    def _build_error_message(self, status_code: int, response_data: Dict, raw_text: str) -> str:
        if response_data:
            mensaje = response_data.get("Mensaje") or response_data.get("MensajeSat") or raw_text
            codigo_sat = response_data.get("CodigoSat")
            codigo = response_data.get("Codigo")
            detalle = []
            if codigo is not None:
                detalle.append(f"Código {codigo}")
            if codigo_sat:
                detalle.append(f"SAT {codigo_sat}")
            prefijo = " | ".join(detalle)
            if prefijo:
                return f"Error {status_code}: {prefijo} - {mensaje}"
            return f"Error {status_code}: {mensaje}"
        return f"Error {status_code}: {raw_text}"

    def _extraer_uuid_xml(self, xml_timbrado: str) -> Optional[str]:
        if not xml_timbrado:
            return None
        try:
            root = ET.fromstring(xml_timbrado)
            for node in root.iter():
                if node.tag.endswith("TimbreFiscalDigital"):
                    return node.attrib.get("UUID")
        except ET.ParseError:
            return None
        return None

    def _registrar_evento(self, entidad: str, id_entidad: int, accion: str,
                         valor_nuevo: str, usuario: str):
        timestamp = datetime.now().isoformat()
        hash_evento = self._generar_hash(entidad, id_entidad, accion, timestamp)

        self.db.execute("""
            INSERT INTO historial_general
            (entidad, id_entidad, accion, valor_nuevo, usuario, timestamp, hash_evento)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (entidad, id_entidad, accion, valor_nuevo, usuario, timestamp, hash_evento))

        self.db.commit()

    def _generar_hash(self, entidad: str, id_entidad: int, accion: str, timestamp: str) -> str:
        import hashlib
        cadena = f"{entidad}{id_entidad}{accion}{timestamp}"
        return hashlib.sha256(cadena.encode()).hexdigest()[:16]
    
    def _registrar_evento(self, entidad: str, id_entidad: int, accion: str, 
                         valor_nuevo: str, usuario: str):
        """Registra evento en historial_general"""
        timestamp = datetime.now().isoformat()
        hash_evento = self._generar_hash(entidad, id_entidad, accion, timestamp)
        
        self.db.execute("""
            INSERT INTO historial_general 
            (entidad, id_entidad, accion, valor_nuevo, usuario, timestamp, hash_evento)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (entidad, id_entidad, accion, valor_nuevo, usuario, timestamp, hash_evento))
        
        self.db.commit()
    
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
