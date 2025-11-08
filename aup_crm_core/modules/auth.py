import hashlib
import streamlit as st
from core.database import get_connection

def hash_password(password):
    """Genera un hash SHA-256 de la contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()

def verificar_credenciales(correo, password):
    """Verifica si las credenciales son correctas y retorna el usuario si es válido"""
    conn = get_connection()
    if not conn:
        return None
    
    password_hash = hash_password(password)
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM aup_agentes 
        WHERE tipo='usuario' 
        AND atributos LIKE ? 
        AND password_hash=? 
        AND activo=1
    """, (f"%correo={correo}%", password_hash))
    
    usuario = cur.fetchone()
    conn.close()
    return usuario

def iniciar_sesion(correo, password):
    """Inicia sesión y guarda el usuario en session_state"""
    usuario = verificar_credenciales(correo, password)
    if usuario:
        st.session_state['logged_in'] = True
        st.session_state['user_id'] = usuario['id']
        st.session_state['user_name'] = usuario['nombre']
        # Extraer rol de atributos
        atributos = usuario['atributos']
        rol = "Usuario"
        if "rol=" in atributos:
            rol_part = atributos.split("rol=")[1].split(";")[0]
            rol = rol_part
        st.session_state['user_role'] = rol
        return True
    return False

def cerrar_sesion():
    """Cierra la sesión actual"""
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = None
    st.session_state['user_name'] = None
    st.session_state['user_role'] = None

def esta_autenticado():
    """Verifica si hay una sesión activa"""
    return st.session_state.get('logged_in', False)

def obtener_usuario_actual():
    """Retorna información del usuario actual"""
    if esta_autenticado():
        return {
            'id': st.session_state.get('user_id'),
            'nombre': st.session_state.get('user_name'),
            'rol': st.session_state.get('user_role')
        }
    return None
