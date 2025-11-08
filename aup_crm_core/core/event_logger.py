from .database import get_connection

def registrar_evento(agente_id, accion, descripcion):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO aup_eventos (agente_id, accion, descripcion)
        VALUES (?, ?, ?)
    """, (agente_id, accion, descripcion))
    conn.commit()
    conn.close()

def registrar_historial(entidad, valor_anterior, valor_nuevo, responsable):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO aup_historial (entidad, valor_anterior, valor_nuevo, responsable)
        VALUES (?, ?, ?, ?)
    """, (entidad, valor_anterior, valor_nuevo, responsable))
    conn.commit()
    conn.close()
