# -*- coding: utf-8 -*-# -*- coding: utf-8 -*-

"""import streamlit as st

Módulo de Prospectos - Gestión Relacional AUPfrom core.database import get_connection

Manejo de estados, vigencias y conversionesfrom core.event_logger import registrar_evento

"""

def ensure_relaciones_table():

import streamlit as st    """Crea la tabla de relaciones si no existe"""

from datetime import date, timedelta    conn = get_connection()

from core.database import get_connection    if conn:

from core.event_logger import registrar_evento        cur = conn.cursor()

        cur.execute("""

def show():        CREATE TABLE IF NOT EXISTS aup_relaciones (

    st.header("🎯 Gestión de Prospectos")            id INTEGER PRIMARY KEY AUTOINCREMENT,

                agente_origen INTEGER,

    # Crear nuevo prospecto            agente_destino INTEGER,

    with st.expander("➕ Registrar nuevo prospecto"):            tipo_relacion TEXT,

        with st.form("form_nuevo_prospecto"):            fecha TEXT DEFAULT CURRENT_TIMESTAMP

            nombre = st.text_input("Nombre del prospecto o empresa")        )

            col1, col2 = st.columns(2)        """)

            with col1:        conn.commit()

                sector = st.text_input("Sector o giro")        conn.close()

                telefono = st.text_input("Teléfono")

            with col2:

                estado = st.selectbox("Estado inicial", ["Nuevo", "En negociación", "Cerrado", "Perdido"])def show():

                vigencia = st.date_input("Vigente hasta", value=date.today() + timedelta(days=90))    # Asegurar que exista la tabla de relaciones

                ensure_relaciones_table()

            submit = st.form_submit_button("💾 Guardar prospecto", use_container_width=True)    

                st.subheader("🎯 Gestión de Prospectos")

            if submit and nombre:    

                conn = get_connection()    # --- Indicadores básicos ---

                cur = conn.cursor()    conn = get_connection()

                atributos = f"sector={sector};telefono={telefono};estado={estado};vigencia={vigencia}"    if conn:

                cur.execute("""        cur = conn.cursor()

                    INSERT INTO aup_agentes (tipo, nombre, atributos, activo)        cur.execute("SELECT COUNT(*) AS total FROM aup_agentes WHERE tipo='prospecto'")

                    VALUES (?, ?, ?, ?)        total = cur.fetchone()["total"]

                """, ("prospecto", nombre, atributos, 1))        cur.execute("""

                prospecto_id = cur.lastrowid            SELECT COUNT(DISTINCT agente_origen) AS convertidos

                conn.commit()            FROM aup_relaciones WHERE tipo_relacion='convertido_en'

                conn.close()        """)

                        convertidos = cur.fetchone()["convertidos"]

                registrar_evento(prospecto_id, "Alta prospecto", f"Prospecto '{nombre}' creado en estado '{estado}'")        conn.close()

                st.success(f"✅ Prospecto '{nombre}' registrado correctamente")

                st.rerun()        st.info(f"📊 Prospectos totales: {total} | Convertidos a clientes: {convertidos}")

        st.divider()

    st.divider()

        # --- Alta de prospecto ---

    # Listado de prospectos    with st.form("form_prospecto"):

    st.subheader("📋 Listado de Prospectos")        nombre = st.text_input("Nombre del prospecto o empresa")

            sector = st.text_input("Sector o giro")

    conn = get_connection()        telefono = st.text_input("Teléfono principal (opcional)")

    cur = conn.cursor()        estado = st.selectbox("Estado del prospecto", ["Nuevo", "En negociación", "Cerrado", "Perdido"])

    cur.execute("""        submit = st.form_submit_button("Agregar prospecto")

        SELECT * FROM aup_agentes 

        WHERE tipo='prospecto'     if submit and nombre:

        ORDER BY fecha_creacion DESC        conn = get_connection()

    """)        if conn:

    prospectos = cur.fetchall()            cur = conn.cursor()

    conn.close()            atributos = f"sector={sector};telefono={telefono};estado={estado}" if telefono else f"sector={sector};estado={estado}"

                cur.execute("""

    if not prospectos:                INSERT INTO aup_agentes (tipo, nombre, atributos)

        st.info("No hay prospectos registrados aún.")                VALUES ('prospecto', ?, ?)

        return            """, (nombre, atributos))

                prospecto_id = cur.lastrowid

    # Filtros            conn.commit()

    col1, col2 = st.columns(2)            conn.close()

    with col1:            registrar_evento(prospecto_id, "Alta prospecto", f"Prospecto '{nombre}' agregado.")

        filtro_estado = st.multiselect(            st.success(f"✅ Prospecto '{nombre}' registrado.")

            "Filtrar por estado",            st.balloons()

            ["Nuevo", "En negociación", "Cerrado", "Perdido"],

            default=["Nuevo", "En negociación"]    st.divider()

        )

    with col2:    # --- Listado de prospectos ---

        mostrar_inactivos = st.checkbox("Mostrar inactivos", value=False)    conn = get_connection()

        if not conn:

    # Aplicar filtros        st.error("❌ Error al conectar con la base de datos.")

    prospectos_filtrados = []        return

    for p in prospectos:    

        # Parsear estado    cur = conn.cursor()

        atributos = p["atributos"] or ""    cur.execute("SELECT * FROM aup_agentes WHERE tipo='prospecto' ORDER BY fecha_creacion DESC")

        estado = "Nuevo"    prospectos = cur.fetchall()

        if "estado=" in atributos:    conn.close()

            estado = atributos.split("estado=")[1].split(";")[0]

            if not prospectos:

        # Aplicar filtros        st.info("Aún no hay prospectos registrados.")

        if estado not in filtro_estado:        return

            continue

        if not mostrar_inactivos and not p["activo"]:    st.write("### Prospectos actuales")

            continue    for p in prospectos:

                with st.expander(f"📄 {p['nombre']} — ID: {p['id']}"):

        prospectos_filtrados.append(p)            st.write(f"**Atributos:** {p['atributos']}")

                st.write(f"**Fecha registro:** {p['fecha_creacion']}")

    st.caption(f"Mostrando {len(prospectos_filtrados)} de {len(prospectos)} prospectos")            

                # Mostrar contactos asociados

    # Mostrar prospectos            conn = get_connection()

    for p in prospectos_filtrados:            if conn:

        atributos = p["atributos"] or ""                cur = conn.cursor()

                        cur.execute("""

        # Parsear atributos                    SELECT a.* FROM aup_agentes a

        attrs = {}                    INNER JOIN aup_relaciones r ON a.id = r.agente_destino

        for attr in atributos.split(";"):                    WHERE r.agente_origen = ? AND r.tipo_relacion = 'tiene_contacto'

            if "=" in attr:                """, (p['id'],))

                key, value = attr.split("=", 1)                contactos = cur.fetchall()

                attrs[key] = value                conn.close()

                        

        estado = attrs.get("estado", "Nuevo")                if contactos:

        sector = attrs.get("sector", "N/A")                    st.write("**Contactos asociados:**")

        telefono = attrs.get("telefono", "N/A")                    for c in contactos:

        vigencia = attrs.get("vigencia", "N/A")                        st.write(f"  • {c['nombre']} — {c['atributos']}")

                    

        # Badge de estado            # Ver eventos del prospecto

        estado_emoji = {            if st.button(f"📜 Ver eventos", key=f"evt_{p['id']}"):

            "Nuevo": "🆕",                mostrar_eventos(p['id'])

            "En negociación": "💬",            

            "Cerrado": "✅",            col1, col2, col3 = st.columns(3)

            "Perdido": "❌"

        }            # Editar prospecto

                    with col1:

        estado_color = {                if st.button(f"✏️ Editar", key=f"edit_{p['id']}"):

            "Nuevo": "🔵",                    st.session_state["editar_prospecto"] = p["id"]

            "En negociación": "🟡",                    st.session_state["editar_prospecto_nombre"] = p["nombre"]

            "Cerrado": "🟢",                    st.session_state["editar_prospecto_atributos"] = p["atributos"]

            "Perdido": "🔴"                    st.rerun()

        }

                    # Agregar contacto

        with st.container(border=True):            with col2:

            col1, col2, col3 = st.columns([3, 1, 1])                if st.button(f"➕ Agregar contacto", key=f"contacto_{p['id']}"):

                                st.session_state["prospecto_seleccionado"] = p["id"]

            with col1:                    st.session_state["prospecto_nombre"] = p["nombre"]

                st.markdown(f"### {estado_emoji.get(estado, '📋')} {p['nombre']}")                    st.rerun()

                st.caption(f"**Sector:** {sector} | **Tel:** {telefono}")

                st.caption(f"{estado_color.get(estado, '⚪')} **Estado:** {estado} | **Vigencia:** {vigencia}")            # Convertir a cliente

                if not p["activo"]:            with col3:

                    st.warning("⚠️ Prospecto inactivo")                if st.button(f"💼 Convertir a cliente", key=f"conv_{p['id']}"):

                                convertir_a_cliente(p["id"], p["nombre"], p["atributos"])

            with col2:                    st.rerun()

                st.caption(f"ID: {p['id']}")

                st.caption(f"📅 {p['fecha_creacion'][:10]}")    # Formulario de editar prospecto (si hay prospecto a editar)

                if "editar_prospecto" in st.session_state:

            with col3:        st.divider()

                if p["activo"]:        editar_prospecto(

                    st.success("✅ Vigente")            st.session_state["editar_prospecto"],

                else:            st.session_state.get("editar_prospecto_nombre", ""),

                    st.error("❌ Inactivo")            st.session_state.get("editar_prospecto_atributos", "")

                    )

            # Botones de acción

            col1, col2, col3, col4 = st.columns(4)    # Formulario de agregar contacto (si hay prospecto seleccionado)

                if "prospecto_seleccionado" in st.session_state:

            with col1:        st.divider()

                if st.button(f"✏️ Editar", key=f"edit_{p['id']}", use_container_width=True):        agregar_contacto(

                    st.session_state["editar_prospecto"] = p["id"]            st.session_state["prospecto_seleccionado"], 

                    st.rerun()            st.session_state.get("prospecto_nombre", "")

                    )

            with col2:

                if st.button(f"👤 Contactos", key=f"cont_{p['id']}", use_container_width=True):

                    st.session_state["contactos_prospecto"] = p["id"]def agregar_contacto(prospecto_id, prospecto_nombre):

                    st.session_state["contactos_prospecto_nombre"] = p["nombre"]    st.subheader(f"👤 Nuevo contacto para: {prospecto_nombre}")

                    st.rerun()    

                with st.form("form_contacto", clear_on_submit=True):

            with col3:        nombre = st.text_input("Nombre del contacto")

                if st.button(f"🔄 Convertir", key=f"conv_{p['id']}", use_container_width=True):        telefono = st.text_input("Teléfono")

                    convertir_a_cliente(p["id"], p["nombre"])        correo = st.text_input("Correo electrónico")

                    st.rerun()        cargo = st.text_input("Cargo o puesto")

                    col1, col2 = st.columns(2)

            with col4:        with col1:

                texto_btn = "❌ Desactivar" if p["activo"] else "✅ Activar"            submit = st.form_submit_button("💾 Guardar contacto", use_container_width=True)

                if st.button(texto_btn, key=f"toggle_{p['id']}", type="secondary", use_container_width=True):        with col2:

                    toggle_activo(p["id"], p["nombre"], p["activo"])            cancel = st.form_submit_button("❌ Cancelar", use_container_width=True)

                    st.rerun()

        if cancel:

    # Formulario de edición (si hay prospecto seleccionado)        if "prospecto_seleccionado" in st.session_state:

    if "editar_prospecto" in st.session_state:            del st.session_state["prospecto_seleccionado"]

        st.divider()            del st.session_state["prospecto_nombre"]

        editar_prospecto(st.session_state["editar_prospecto"])        st.rerun()

    

    # Gestión de contactos (si hay prospecto seleccionado)    if submit and nombre:

    if "contactos_prospecto" in st.session_state:        conn = get_connection()

        st.divider()        if conn:

        gestionar_contactos(            cur = conn.cursor()

            st.session_state["contactos_prospecto"],            atributos = f"telefono={telefono};correo={correo};cargo={cargo}"

            st.session_state.get("contactos_prospecto_nombre", "")            cur.execute("""

        )                INSERT INTO aup_agentes (tipo, nombre, atributos)

                VALUES ('contacto', ?, ?)

            """, (nombre, atributos))

def editar_prospecto(prospecto_id):            contacto_id = cur.lastrowid

    """Editar datos de un prospecto existente"""

    conn = get_connection()            cur.execute("""

    cur = conn.cursor()                INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)

    cur.execute("SELECT * FROM aup_agentes WHERE id=?", (prospecto_id,))                VALUES (?, ?, ?)

    p = cur.fetchone()            """, (prospecto_id, contacto_id, "tiene_contacto"))

    conn.close()            

                # Crear relación inversa (contacto → prospecto)

    if not p:            cur.execute("""

        st.error("❌ Prospecto no encontrado.")                INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)

        return                VALUES (?, ?, ?)

                """, (contacto_id, prospecto_id, "contacto_de"))

    st.subheader(f"✏️ Editar prospecto: {p['nombre']}")            

                conn.commit()

    # Parsear atributos actuales            conn.close()

    atributos = p["atributos"] or ""

    attrs = {}            registrar_evento(contacto_id, "Alta contacto", f"Contacto '{nombre}' agregado al prospecto ID {prospecto_id}.")

    for attr in atributos.split(";"):            st.success(f"✅ Contacto '{nombre}' vinculado al prospecto.")

        if "=" in attr:            

            key, value = attr.split("=", 1)            # Limpiar session state

            attrs[key] = value            if "prospecto_seleccionado" in st.session_state:

                    del st.session_state["prospecto_seleccionado"]

    with st.form("form_editar_prospecto"):                del st.session_state["prospecto_nombre"]

        nombre = st.text_input("Nombre", value=p["nombre"])            st.rerun()

        

        col1, col2 = st.columns(2)

        with col1:def convertir_a_cliente(prospecto_id, nombre, atributos):

            sector = st.text_input("Sector", value=attrs.get("sector", ""))    """Convierte un prospecto en cliente y crea la relación"""

            telefono = st.text_input("Teléfono", value=attrs.get("telefono", ""))    conn = get_connection()

        with col2:    if not conn:

            estado_actual = attrs.get("estado", "Nuevo")        st.error("❌ Error al conectar con la base de datos.")

            estado = st.selectbox(        return

                "Estado",    

                ["Nuevo", "En negociación", "Cerrado", "Perdido"],    cur = conn.cursor()

                index=["Nuevo", "En negociación", "Cerrado", "Perdido"].index(estado_actual) if estado_actual in ["Nuevo", "En negociación", "Cerrado", "Perdido"] else 0    

            )    # Verificar si ya fue convertido

            activo = st.checkbox("Vigente", value=bool(p["activo"]))    cur.execute("""

                SELECT * FROM aup_relaciones 

        col1, col2 = st.columns(2)        WHERE agente_origen = ? AND tipo_relacion = 'convertido_en'

        with col1:    """, (prospecto_id,))

            submit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)    

        with col2:    if cur.fetchone():

            cancel = st.form_submit_button("❌ Cancelar", use_container_width=True)        st.warning("⚠️ Este prospecto ya fue convertido a cliente.")

            conn.close()

    if cancel:        return

        del st.session_state["editar_prospecto"]    

        st.rerun()    # Crear nuevo agente tipo cliente

        cur.execute("""

    if submit:        INSERT INTO aup_agentes (tipo, nombre, atributos)

        nuevos_atributos = f"sector={sector};telefono={telefono};estado={estado};vigencia={attrs.get('vigencia', date.today())}"        VALUES ('cliente', ?, ?)

            """, (nombre, atributos))

        conn = get_connection()    cliente_id = cur.lastrowid

        cur = conn.cursor()

        cur.execute("""    # Crear relación de conversión

            UPDATE aup_agentes SET nombre=?, atributos=?, activo=? WHERE id=?    cur.execute("""

        """, (nombre, nuevos_atributos, 1 if activo else 0, prospecto_id))        INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)

        conn.commit()        VALUES (?, ?, ?)

        conn.close()    """, (prospecto_id, cliente_id, "convertido_en"))

            

        registrar_evento(prospecto_id, "Actualización", f"Prospecto '{nombre}' actualizado. Estado: {estado}")    # Copiar contactos al cliente

        st.success("✅ Prospecto actualizado correctamente.")    cur.execute("""

        del st.session_state["editar_prospecto"]        SELECT agente_destino FROM aup_relaciones 

        st.rerun()        WHERE agente_origen = ? AND tipo_relacion = 'tiene_contacto'

    """, (prospecto_id,))

    contactos = cur.fetchall()

def gestionar_contactos(prospecto_id, prospecto_nombre):    

    """Gestión de contactos asociados a un prospecto"""    for contacto in contactos:

    st.subheader(f"👥 Contactos de: {prospecto_nombre}")        cur.execute("""

                INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)

    # Listar contactos existentes            VALUES (?, ?, ?)

    conn = get_connection()        """, (cliente_id, contacto['agente_destino'], "contacto_principal"))

    cur = conn.cursor()    

    cur.execute("""    conn.commit()

        SELECT a.* FROM aup_agentes a    conn.close()

        INNER JOIN aup_relaciones r ON a.id = r.agente_destino

        WHERE r.agente_origen = ? AND r.tipo_relacion = 'tiene_contacto'    registrar_evento(cliente_id, "Conversión", f"Prospecto '{nombre}' convertido a cliente (ID: {cliente_id}).")

        ORDER BY a.fecha_creacion DESC    st.success(f"🎉 ¡Prospecto '{nombre}' ahora es cliente! (ID: {cliente_id})")

    """, (prospecto_id,))    st.balloons()

    contactos = cur.fetchall()

    conn.close()

    def editar_prospecto(prospecto_id, nombre_actual, atributos_actuales):

    if contactos:    """Editar los datos de un prospecto existente"""

        for c in contactos:    st.subheader(f"✏️ Editar prospecto: {nombre_actual}")

            col1, col2, col3 = st.columns([3, 1, 1])    

            with col1:    # Parsear atributos actuales

                st.write(f"**{c['nombre']}**")    atributos_dict = {}

            with col2:    if atributos_actuales:

                if c["activo"]:        for attr in atributos_actuales.split(";"):

                    st.success("✅ Activo")            if "=" in attr:

                else:                key, value = attr.split("=", 1)

                    st.error("❌ Inactivo")                atributos_dict[key] = value

            with col3:    

                if st.button(f"✏️ Editar", key=f"edit_c_{c['id']}"):    with st.form("form_editar_prospecto", clear_on_submit=True):

                    st.session_state["editar_contacto"] = c["id"]        nombre = st.text_input("Nombre del prospecto o empresa", value=nombre_actual)

                    st.rerun()        sector = st.text_input("Sector o giro", value=atributos_dict.get("sector", ""))

    else:        telefono = st.text_input("Teléfono principal", value=atributos_dict.get("telefono", ""))

        st.info("No hay contactos registrados para este prospecto.")        estado = st.selectbox(

                "Estado del prospecto", 

    # Agregar nuevo contacto            ["Nuevo", "En negociación", "Cerrado", "Perdido"],

    with st.form("form_nuevo_contacto"):            index=["Nuevo", "En negociación", "Cerrado", "Perdido"].index(atributos_dict.get("estado", "Nuevo"))

        st.write("➕ Agregar nuevo contacto")        )

        nombre_contacto = st.text_input("Nombre del contacto")        

        submit = st.form_submit_button("💾 Guardar contacto", use_container_width=True)        col1, col2 = st.columns(2)

                with col1:

        if submit and nombre_contacto:            submit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)

            conn = get_connection()        with col2:

            cur = conn.cursor()            cancel = st.form_submit_button("❌ Cancelar", use_container_width=True)

            cur.execute("""    

                INSERT INTO aup_agentes (tipo, nombre, atributos, activo)    if cancel:

                VALUES (?, ?, ?, ?)        if "editar_prospecto" in st.session_state:

            """, ("contacto", nombre_contacto, "", 1))            del st.session_state["editar_prospecto"]

            contacto_id = cur.lastrowid            del st.session_state["editar_prospecto_nombre"]

                        del st.session_state["editar_prospecto_atributos"]

            cur.execute("""        st.rerun()

                INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)    

                VALUES (?, ?, ?)    if submit and nombre:

            """, (prospecto_id, contacto_id, "tiene_contacto"))        conn = get_connection()

                    if conn:

            conn.commit()            cur = conn.cursor()

            conn.close()            atributos = f"sector={sector};telefono={telefono};estado={estado}"

                        cur.execute("""

            registrar_evento(prospecto_id, "Contacto agregado", f"Contacto '{nombre_contacto}' asociado al prospecto")                UPDATE aup_agentes 

            st.success(f"✅ Contacto '{nombre_contacto}' agregado")                SET nombre = ?, atributos = ?

            st.rerun()                WHERE id = ?

                """, (nombre, atributos, prospecto_id))

    if st.button("← Volver al listado", use_container_width=True):            conn.commit()

        del st.session_state["contactos_prospecto"]            conn.close()

        if "contactos_prospecto_nombre" in st.session_state:            

            del st.session_state["contactos_prospecto_nombre"]            registrar_evento(prospecto_id, "Actualización", f"Prospecto '{nombre}' actualizado.")

        st.rerun()            st.success(f"✅ Prospecto '{nombre}' actualizado correctamente.")

            

            # Limpiar session state

def convertir_a_cliente(prospecto_id, nombre):            if "editar_prospecto" in st.session_state:

    """Convierte un prospecto en cliente"""                del st.session_state["editar_prospecto"]

    conn = get_connection()                del st.session_state["editar_prospecto_nombre"]

    cur = conn.cursor()                del st.session_state["editar_prospecto_atributos"]

                st.rerun()

    # Cambiar tipo a cliente

    cur.execute("UPDATE aup_agentes SET tipo='cliente' WHERE id=?", (prospecto_id,))

    def mostrar_eventos(agente_id):

    # Registrar relación de conversión    """Muestra los eventos registrados para un prospecto o contacto"""

    cur.execute("""    conn = get_connection()

        INSERT INTO aup_relaciones (agente_origen, agente_destino, tipo_relacion)    if not conn:

        VALUES (?, ?, ?)        st.error("❌ Error al conectar con la base de datos.")

    """, (prospecto_id, prospecto_id, "convertido_en_cliente"))        return

    

    conn.commit()    cur = conn.cursor()

    conn.close()    cur.execute("SELECT * FROM aup_eventos WHERE agente_id=? ORDER BY fecha DESC", (agente_id,))

        eventos = cur.fetchall()

    registrar_evento(prospecto_id, "Conversión", f"Prospecto '{nombre}' convertido en cliente")    conn.close()

    st.success(f"🎉 ¡Prospecto '{nombre}' convertido en cliente exitosamente!")

    if eventos:

        st.write("### 🕒 Historial de eventos")

def toggle_activo(prospecto_id, nombre, activo_actual):        for e in eventos:

    """Activa o desactiva un prospecto"""            st.markdown(f"- **[{e['fecha']}]** {e['accion']}: {e['descripcion']}")

    nuevo_estado = 0 if activo_actual else 1    else:

            st.info("Sin eventos registrados para este agente.")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE aup_agentes SET activo=? WHERE id=?", (nuevo_estado, prospecto_id))
    conn.commit()
    conn.close()
    
    accion = "activado" if nuevo_estado else "desactivado"
    registrar_evento(prospecto_id, "Cambio estado", f"Prospecto '{nombre}' {accion}")
    st.success(f"✅ Prospecto '{nombre}' {accion}")
