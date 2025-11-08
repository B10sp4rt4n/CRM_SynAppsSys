from .database import get_connection
from .config_global import AUTH_ROLLBACK_MODE

def registrar_evento(agente_id, accion, descripcion):
    """Registra un evento en la BD (se desactiva en modo rollback)"""
    if AUTH_ROLLBACK_MODE:
        print(f"⚠️ [Modo rollback] Evento no registrado: {accion} - {descripcion}")
        return
    
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO aup_eventos (agente_id, accion, descripcion)
        VALUES (?, ?, ?)
    """, (agente_id, accion, descripcion))
    conn.commit()
    conn.close()

def registrar_historial(entidad, valor_anterior, valor_nuevo, responsable):
    """Registra cambios en el historial (se desactiva en modo rollback)"""
    if AUTH_ROLLBACK_MODE:
        print(f"⚠️ [Modo rollback] Historial no registrado: {entidad}")
        return
    
    conn = get_connection()
    if not conn:
        return
    
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO aup_historial (entidad, valor_anterior, valor_nuevo, responsable)
        VALUES (?, ?, ?, ?)
    """, (entidad, valor_anterior, valor_nuevo, responsable))
    conn.commit()
    conn.close()
