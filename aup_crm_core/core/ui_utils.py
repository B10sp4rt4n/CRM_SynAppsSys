# -*- coding: utf-8 -*-
"""
Utilidades de UI - Componentes visuales reutilizables
Mantiene consistencia visual en toda la aplicación
"""

def badge_estado(estado):
    """
    Retorna el emoji de badge según el estado
    Centraliza la lógica de badges para consistencia visual
    """
    mapa = {
        # Estados de Cliente
        "Activo": "🟢",
        "Suspendido": "🟠",
        "No renovado": "🔴",
        
        # Estados de Prospecto
        "Nuevo": "🆕",
        "En negociación": "💬",
        "Cerrado": "✅",
        "Perdido": "❌",
        
        # Fallback genérico
        "Abierta": "🔵",
        "Ganada": "🟢",
        "Perdida": "🔴"
    }
    return mapa.get(estado, "⚪")


def obtener_valor(atributos, clave):
    """
    Extrae un valor del string de atributos usando regex
    Función compartida entre módulos para parseo consistente
    """
    import re
    match = re.search(rf"{clave}=([^;]+)", atributos or "")
    return match.group(1) if match else "—"


def validar_vigencia(vigencia_str):
    """
    Valida y retorna estado de vigencia
    Retorna: ('vigente'|'vencida'|'próxima', dias_restantes)
    """
    from datetime import datetime, date
    
    try:
        if vigencia_str == "—":
            return "indefinida", None
            
        vigencia_fecha = datetime.fromisoformat(str(vigencia_str)).date()
        hoy = date.today()
        dias_restantes = (vigencia_fecha - hoy).days
        
        if dias_restantes < 0:
            return "vencida", abs(dias_restantes)
        elif dias_restantes <= 30:
            return "próxima", dias_restantes
        else:
            return "vigente", dias_restantes
            
    except:
        return "indefinida", None


def formato_telefono(telefono):
    """
    Formatea número telefónico para visualización consistente
    """
    if not telefono or telefono == "—" or telefono == "Sin teléfono":
        return "—"
    
    # Remover espacios y caracteres especiales
    limpio = ''.join(filter(str.isdigit, telefono))
    
    # Formato: (55) 1234-5678 para números de 10 dígitos
    if len(limpio) == 10:
        return f"({limpio[:2]}) {limpio[2:6]}-{limpio[6:]}"
    
    return telefono  # Retornar original si no es formato esperado
