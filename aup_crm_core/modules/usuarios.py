import streamlit as st
from core.database import get_connection
from core.event_logger import registrar_evento
from modules.auth import hash_password

def show():
    st.subheader("👤 Ingreso y Registro de Usuarios")

    with st.form("form_usuario"):
        nombre = st.text_input("Nombre completo")
        correo = st.text_input("Correo electrónico")
        password = st.text_input("Contraseña", type="password")
        password_confirm = st.text_input("Confirmar contraseña", type="password")
        rol = st.selectbox("Rol", ["Administrador", "Vendedor", "Soporte", "Invitado"])
        submit = st.form_submit_button("Registrar usuario")

    if submit:
        if nombre and correo and password and password_confirm:
            if password != password_confirm:
                st.error("❌ Las contraseñas no coinciden.")
            elif len(password) < 6:
                st.warning("⚠️ La contraseña debe tener al menos 6 caracteres.")
            else:
                conn = get_connection()
                if conn:
                    # Verificar si el correo ya existe
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM aup_agentes WHERE tipo='usuario' AND atributos LIKE ?", 
                               (f"%correo={correo}%",))
                    existe = cur.fetchone()
                    
                    if existe:
                        st.error(f"❌ El correo '{correo}' ya está registrado.")
                    else:
                        password_hash = hash_password(password)
                        cur.execute("""
                            INSERT INTO aup_agentes (tipo, nombre, atributos, password_hash, activo)
                            VALUES (?, ?, ?, ?, ?)
                        """, ("usuario", nombre, f"correo={correo};rol={rol}", password_hash, 1))
                        conn.commit()
                        usuario_id = cur.lastrowid
                        conn.close()

                        registrar_evento(usuario_id, "Alta usuario", f"Usuario {nombre} ({rol}) registrado.")
                        st.success(f"✅ Usuario '{nombre}' agregado correctamente.")
                        st.balloons()
                else:
                    st.error("❌ Error al conectar con la base de datos.")
        else:
            st.warning("⚠️ Por favor llena todos los campos.")
    
    st.divider()
    st.write("### Usuarios registrados")
    conn = get_connection()
    if conn:
        usuarios = conn.execute("SELECT * FROM aup_agentes WHERE tipo='usuario' ORDER BY fecha_creacion DESC").fetchall()
        conn.close()

        if usuarios:
            for u in usuarios:
                estado = "🟢 Activo" if u['activo'] == 1 else "🔴 Inactivo"
                st.write(f"• **{u['nombre']}** — {u['atributos']} — {estado} _(ID: {u['id']})_")
        else:
            st.info("No hay usuarios registrados todavía.")
    else:
        st.error("❌ Error al conectar con la base de datos.")
