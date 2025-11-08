import streamlit as st
from core.database import get_connection
from core.event_logger import registrar_evento

def show():
    st.subheader("👤 Ingreso y Registro de Usuarios")

    with st.form("form_usuario"):
        nombre = st.text_input("Nombre completo")
        correo = st.text_input("Correo electrónico")
        rol = st.selectbox("Rol", ["Administrador", "Vendedor", "Soporte", "Invitado"])
        submit = st.form_submit_button("Registrar usuario")

    if submit:
        if nombre and correo:
            conn = get_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO aup_agentes (tipo, nombre, atributos)
                    VALUES (?, ?, ?)
                """, ("usuario", nombre, f"correo={correo};rol={rol}"))
                conn.commit()
                usuario_id = cur.lastrowid
                conn.close()

                registrar_evento(usuario_id, "Alta usuario", f"Usuario {nombre} ({rol}) registrado.")
                st.success(f"✅ Usuario '{nombre}' agregado correctamente.")
            else:
                st.error("❌ Error al conectar con la base de datos.")
        else:
            st.warning("⚠️ Por favor llena todos los campos.")
    
    st.divider()
    st.write("### Usuarios registrados")
    conn = get_connection()
    if conn:
        usuarios = conn.execute("SELECT * FROM aup_agentes WHERE tipo='usuario'").fetchall()
        conn.close()

        if usuarios:
            for u in usuarios:
                st.write(f"• **{u['nombre']}** — {u['atributos']} _(ID: {u['id']})_")
        else:
            st.info("No hay usuarios registrados todavía.")
    else:
        st.error("❌ Error al conectar con la base de datos.")
