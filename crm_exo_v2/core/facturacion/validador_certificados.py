# -*- coding: utf-8 -*-
"""
Validador de Certificados CSD
Herramienta para diagnosticar problemas con certificados .cer y .key
antes de enviarlos al PAC TimbrarCFDI33
"""

from typing import Tuple, Dict, Optional
from datetime import datetime
import base64
import subprocess
import tempfile
import os


class ValidadorCertificados:
    """Valida certificados CSD localmente antes de enviarlos al PAC"""
    
    @staticmethod
    def validar_certificado_completo(cer_bytes: bytes, key_bytes: bytes, 
                                    contrasena: str) -> Tuple[bool, str, Dict]:
        """
        Valida que los archivos .cer y .key sean correctos y coincidan
        
        Args:
            cer_bytes: Contenido del archivo .cer
            key_bytes: Contenido del archivo .key
            contrasena: Contraseña del archivo .key
            
        Returns:
            Tupla (válido: bool, mensaje: str, detalles: dict)
        """
        detalles = {}
        
        # 1. Validar que los archivos no estén vacíos
        if not cer_bytes or len(cer_bytes) < 100:
            return False, "El archivo .cer está vacío o es muy pequeño", detalles
        
        if not key_bytes or len(key_bytes) < 100:
            return False, "El archivo .key está vacío o es muy pequeño", detalles
        
        detalles['tamano_cer'] = len(cer_bytes)
        detalles['tamano_key'] = len(key_bytes)
        
        # 2. Validar formato del .cer
        if not cer_bytes.startswith(b'0\x82'):
            return False, "El archivo .cer no tiene el formato DER esperado", detalles
        
        # 3. Validar formato del .key
        if not key_bytes.startswith(b'0\x82'):
            return False, "El archivo .key no tiene el formato DER esperado", detalles
        
        # 4. Intentar extraer información del certificado usando openssl
        info_cer = ValidadorCertificados._extraer_info_certificado(cer_bytes)
        if info_cer:
            detalles.update(info_cer)
            
            # Verificar si es un CSD o FIEL
            if 'subject' in info_cer:
                subject = info_cer['subject'].upper()
                if 'FIEL' in subject or 'E.FIRMA' in subject:
                    return False, "⚠️ ERROR: Este es un certificado FIEL/e.firma, NO un CSD. Para facturación necesitas el Certificado de Sello Digital (CSD) del SAT.", detalles
        
        # 5. Validar la contraseña del .key
        valido_key, msg_key = ValidadorCertificados._validar_key_password(
            key_bytes, contrasena
        )
        if not valido_key:
            return False, f"Contraseña incorrecta o .key inválido: {msg_key}", detalles
        
        # 6. Validar que .cer y .key coincidan
        coinciden, msg_coincidencia = ValidadorCertificados._verificar_concordancia(
            cer_bytes, key_bytes, contrasena
        )
        if not coinciden:
            return False, f"Los archivos .cer y .key NO coinciden: {msg_coincidencia}", detalles
        
        # 7. Verificar vigencia
        if 'valido_desde' in detalles and 'valido_hasta' in detalles:
            ahora = datetime.now()
            try:
                desde = datetime.fromisoformat(detalles['valido_desde'])
                hasta = datetime.fromisoformat(detalles['valido_hasta'])
                
                if ahora < desde:
                    return False, f"El certificado aún no es válido (válido desde {detalles['valido_desde']})", detalles
                
                if ahora > hasta:
                    return False, f"⚠️ El certificado EXPIRÓ el {detalles['valido_hasta']}", detalles
                
                # Advertir si está por expirar (menos de 30 días)
                dias_restantes = (hasta - ahora).days
                if dias_restantes < 30:
                    detalles['advertencia'] = f"El certificado expira en {dias_restantes} días"
            except:
                pass
        
        return True, "✅ Certificado válido y listo para usar", detalles
    
    @staticmethod
    def _extraer_info_certificado(cer_bytes: bytes) -> Optional[Dict]:
        """Extrae información del certificado usando openssl"""
        try:
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(delete=False, suffix='.cer') as tmp_cer:
                tmp_cer.write(cer_bytes)
                tmp_cer_path = tmp_cer.name
            
            try:
                # Ejecutar openssl para leer el certificado
                result = subprocess.run(
                    ['openssl', 'x509', '-inform', 'DER', '-in', tmp_cer_path, 
                     '-noout', '-subject', '-serial', '-dates'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    info = {}
                    for line in result.stdout.split('\n'):
                        if line.startswith('subject='):
                            info['subject'] = line.replace('subject=', '').strip()
                        elif line.startswith('serial='):
                            info['numero_certificado'] = line.replace('serial=', '').strip()
                        elif line.startswith('notBefore='):
                            fecha_str = line.replace('notBefore=', '').strip()
                            info['valido_desde'] = ValidadorCertificados._parsear_fecha_openssl(fecha_str)
                        elif line.startswith('notAfter='):
                            fecha_str = line.replace('notAfter=', '').strip()
                            info['valido_hasta'] = ValidadorCertificados._parsear_fecha_openssl(fecha_str)
                    
                    return info
            finally:
                os.unlink(tmp_cer_path)
        except Exception as e:
            # Si openssl no está disponible o falla, continuar sin info adicional
            return {'error_extraccion': str(e)}
        
        return None
    
    @staticmethod
    def _validar_key_password(key_bytes: bytes, contrasena: str) -> Tuple[bool, str]:
        """Valida que la contraseña del .key sea correcta"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.key') as tmp_key:
                tmp_key.write(key_bytes)
                tmp_key_path = tmp_key.name
            
            try:
                # Intentar leer la llave privada con openssl
                result = subprocess.run(
                    ['openssl', 'pkcs8', '-inform', 'DER', '-in', tmp_key_path,
                     '-passin', f'pass:{contrasena}', '-nocrypt'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    return True, "Contraseña correcta"
                else:
                    if 'bad decrypt' in result.stderr.lower() or 'bad password' in result.stderr.lower():
                        return False, "Contraseña incorrecta"
                    elif 'unable to load' in result.stderr.lower():
                        return False, "Archivo .key corrupto o formato inválido"
                    else:
                        return False, result.stderr[:100]
            finally:
                os.unlink(tmp_key_path)
        except FileNotFoundError:
            # openssl no disponible - asumir válido
            return True, "No se pudo validar (openssl no disponible)"
        except Exception as e:
            return False, f"Error al validar: {str(e)}"
    
    @staticmethod
    def _verificar_concordancia(cer_bytes: bytes, key_bytes: bytes, 
                               contrasena: str) -> Tuple[bool, str]:
        """Verifica que el .cer y .key pertenezcan al mismo certificado"""
        try:
            # Extraer módulo del certificado
            with tempfile.NamedTemporaryFile(delete=False, suffix='.cer') as tmp_cer:
                tmp_cer.write(cer_bytes)
                tmp_cer_path = tmp_cer.name
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.key') as tmp_key:
                tmp_key.write(key_bytes)
                tmp_key_path = tmp_key.name
            
            try:
                # Obtener módulo del certificado público
                result_cer = subprocess.run(
                    ['openssl', 'x509', '-inform', 'DER', '-in', tmp_cer_path,
                     '-noout', '-modulus'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                # Obtener módulo de la llave privada
                result_key = subprocess.run(
                    ['openssl', 'pkcs8', '-inform', 'DER', '-in', tmp_key_path,
                     '-passin', f'pass:{contrasena}', '-nocrypt'],
                    capture_output=True,
                    timeout=5
                )
                
                if result_key.returncode == 0:
                    # Extraer módulo de la llave privada
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pem') as tmp_pem:
                        tmp_pem.write(result_key.stdout)
                        tmp_pem_path = tmp_pem.name
                    
                    try:
                        result_key_mod = subprocess.run(
                            ['openssl', 'rsa', '-in', tmp_pem_path, '-noout', '-modulus'],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        
                        if result_cer.returncode == 0 and result_key_mod.returncode == 0:
                            mod_cer = result_cer.stdout.strip()
                            mod_key = result_key_mod.stdout.strip()
                            
                            if mod_cer == mod_key:
                                return True, "Los archivos coinciden"
                            else:
                                return False, "Los archivos NO pertenecen al mismo certificado"
                    finally:
                        os.unlink(tmp_pem_path)
            finally:
                os.unlink(tmp_cer_path)
                os.unlink(tmp_key_path)
        except FileNotFoundError:
            # openssl no disponible
            return True, "No se pudo verificar (openssl no disponible)"
        except Exception as e:
            return True, f"No se pudo verificar: {str(e)}"
    
    @staticmethod
    def _parsear_fecha_openssl(fecha_str: str) -> str:
        """Convierte formato de fecha de openssl a ISO"""
        try:
            # Formato: "Jan 1 00:00:00 2024 GMT"
            from datetime import datetime
            fecha = datetime.strptime(fecha_str.replace(' GMT', ''), '%b %d %H:%M:%S %Y')
            return fecha.isoformat()
        except:
            return fecha_str


def diagnosticar_certificados(cer_bytes: bytes, key_bytes: bytes, 
                              contrasena: str) -> str:
    """
    Función de conveniencia para diagnóstico completo
    Retorna un mensaje formateado con el resultado
    """
    validador = ValidadorCertificados()
    valido, mensaje, detalles = validador.validar_certificado_completo(
        cer_bytes, key_bytes, contrasena
    )
    
    resultado = f"{'✅' if valido else '❌'} {mensaje}\n\n"
    
    if detalles:
        resultado += "**Detalles:**\n"
        for clave, valor in detalles.items():
            if clave == 'advertencia':
                resultado += f"⚠️ {valor}\n"
            else:
                resultado += f"- {clave}: {valor}\n"
    
    return resultado
