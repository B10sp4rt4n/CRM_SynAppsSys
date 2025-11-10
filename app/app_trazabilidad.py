# ================================================================
#  app/app_trazabilidad.py  |  CRM-EXO v2
#  ---------------------------------------------------------------
#  Interfaz Streamlit del Núcleo 4: Trazabilidad
#  
#  PROPÓSITO:
#    Tablero forense visual para auditoría del ledger completo
#    del sistema CRM-EXO v2.
#
#  CARACTERÍSTICAS:
#    - Visualización de eventos en tiempo real
#    - Exploración de hashes SHA-256
#    - Verificación cruzada de integridad
#    - Detalle completo de eventos
#    - Estadísticas de auditoría
#    - Línea de tiempo por entidad
#
#  USO:
#    streamlit run app/app_trazabilidad.py
# ================================================================

import sys
from pathlib import Path

# Ajuste de rutas
APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
CORE_DIR = ROOT_DIR / "crm_exo_v2" / "core"

if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import streamlit as st
from repository_trazabilidad import HistorialGeneralRepository, HashRepository
from datetime import datetime
import pandas as pd

# ================================================================
#  Configuración base
# ================================================================
st.set_page_config(
    page_title="CRM-EXO v2 - Trazabilidad Forense",
    page_icon="🧩",
    layout="wide"
)

# ================================================================
#  Header
# ================================================================
st.title("🧩 Trazabilidad Forense - CRM-EXO v2")
st.caption("**Núcleo 4: Ledger de Auditoría** | Visualizador de historial de eventos, hashes y validación de integridad estructural")

# ================================================================
#  Sidebar - Controles
# ================================================================
with st.sidebar:
    st.header("⚙️ Configuración")
    usuario_actual = st.text_input("👤 Usuario auditor:", "demo")
    limite = st.number_input(
        "🔢 Límite de registros", 
        min_value=5, 
        max_value=100, 
        value=25, 
        step=5
    )
    
    st.divider()
    
    st.header("📊 Estadísticas Rápidas")
    
    # Inicializar repositorios
    repo_hist = HistorialGeneralRepository(usuario=usuario_actual)
    repo_hash = HashRepository(usuario=usuario_actual)
    
    # Obtener estadísticas
    try:
        stats_h = repo_hist.estadisticas()
        stats_hash = repo_hash.estadisticas()
        
        st.metric("Total Eventos", stats_h.get('total_eventos', 0))
        st.metric("Total Hashes", stats_hash.get('total_hashes', 0))
        
        # Auditoría rápida
        if st.button("🔍 Auditoría Completa"):
            with st.spinner("Verificando integridad..."):
                auditoria = repo_hash.auditoria_completa()
                st.success(f"✅ OK: {auditoria['integridad_ok']}")
                if auditoria['integridad_error'] > 0:
                    st.error(f"❌ Errores: {auditoria['integridad_error']}")
                if auditoria['sin_datos'] > 0:
                    st.warning(f"⚠️ Sin datos: {auditoria['sin_datos']}")
    except Exception as e:
        st.error(f"Error al cargar estadísticas: {e}")

# ================================================================
#  Tab Navigation
# ================================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📜 Eventos", 
    "🔐 Hashes", 
    "🧮 Verificación", 
    "📅 Línea de Tiempo",
    "📊 Estadísticas"
])

# ================================================================
#  TAB 1: Historial de Eventos
# ================================================================
with tab1:
    st.subheader("📜 Historial de Eventos Recientes")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        busqueda = st.text_input(
            "🔍 Buscar por entidad, usuario o acción", 
            "",
            placeholder="Ejemplo: factura, demo, CREAR..."
        )
    
    with col2:
        filtro_entidad = st.selectbox(
            "Filtrar por entidad",
            ["Todas"] + list(stats_h.get('por_entidad', {}).keys())
        )
    
    try:
        if busqueda:
            eventos = repo_hist.buscar(busqueda, limite)
        elif filtro_entidad != "Todas":
            eventos = repo_hist.listar_eventos(limite, entidad=filtro_entidad)
        else:
            eventos = repo_hist.listar_eventos(limite)
        
        if not eventos:
            st.warning("No hay eventos registrados aún.")
        else:
            st.info(f"📋 Mostrando {len(eventos)} eventos")
            
            # Convertir a DataFrame para mejor visualización
            df_eventos = pd.DataFrame(eventos)
            
            # Configurar columnas
            st.dataframe(
                df_eventos,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id_evento": st.column_config.NumberColumn("ID", width="small"),
                    "entidad": st.column_config.TextColumn("Entidad", width="medium"),
                    "id_entidad": st.column_config.NumberColumn("ID Entidad", width="small"),
                    "accion": st.column_config.TextColumn("Acción", width="medium"),
                    "usuario": st.column_config.TextColumn("Usuario", width="small"),
                    "timestamp": st.column_config.DatetimeColumn("Fecha/Hora", format="YYYY-MM-DD HH:mm:ss"),
                    "hash_corto": st.column_config.TextColumn("Hash (16)", width="medium"),
                }
            )
            
            # Detalle de evento seleccionado
            st.divider()
            st.subheader("🔍 Detalle de Evento")
            
            id_evento_seleccionado = st.number_input(
                "Seleccionar ID de evento para ver detalle completo",
                min_value=1,
                max_value=max([e['id_evento'] for e in eventos]),
                value=eventos[0]['id_evento'],
                step=1
            )
            
            if st.button("Ver Detalle Completo"):
                try:
                    detalle = repo_hist.detalle_evento(id_evento_seleccionado)
                    st.json(detalle, expanded=True)
                except ValueError as e:
                    st.error(str(e))
    
    except Exception as e:
        st.error(f"Error al cargar eventos: {e}")

# ================================================================
#  TAB 2: Hashes Estructurales
# ================================================================
with tab2:
    st.subheader("🔐 Hashes Estructurales Recientes")
    
    filtro_tabla = st.selectbox(
        "Filtrar por tabla origen",
        ["Todas"] + list(stats_hash.get('por_tabla', {}).keys())
    )
    
    try:
        if filtro_tabla != "Todas":
            hashes = repo_hash.listar(limite, tabla_origen=filtro_tabla)
        else:
            hashes = repo_hash.listar(limite)
        
        if not hashes:
            st.info("Aún no hay hashes registrados.")
        else:
            st.info(f"🔐 Mostrando {len(hashes)} hashes")
            
            df_hashes = pd.DataFrame(hashes)
            
            st.dataframe(
                df_hashes,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id_hash": st.column_config.NumberColumn("ID", width="small"),
                    "tabla_origen": st.column_config.TextColumn("Tabla Origen", width="medium"),
                    "id_registro": st.column_config.NumberColumn("ID Registro", width="small"),
                    "hash_corto": st.column_config.TextColumn("Hash (16)", width="medium"),
                    "timestamp": st.column_config.DatetimeColumn("Fecha/Hora", format="YYYY-MM-DD HH:mm:ss"),
                }
            )
            
            # Mostrar hash completo seleccionado
            st.divider()
            st.subheader("🔍 Hash Completo")
            
            if len(hashes) > 0:
                id_hash_seleccionado = st.selectbox(
                    "Seleccionar hash para ver completo",
                    options=range(len(hashes)),
                    format_func=lambda x: f"ID {hashes[x]['id_hash']} - {hashes[x]['tabla_origen']}[{hashes[x]['id_registro']}]"
                )
                
                hash_completo = hashes[id_hash_seleccionado].get('hash_sha256', 'No disponible')
                st.code(hash_completo, language="text")
    
    except Exception as e:
        st.error(f"Error al cargar hashes: {e}")

# ================================================================
#  TAB 3: Verificación Cruzada
# ================================================================
with tab3:
    st.subheader("🧮 Verificación Cruzada de Integridad")
    
    st.markdown("""
    Esta herramienta compara los hashes almacenados en `hash_registros` con los 
    hashes del `historial_general` para detectar posibles modificaciones no autorizadas.
    """)
    
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        tabla_origen = st.text_input(
            "Tabla origen", 
            "factura",
            help="Nombre de la tabla a verificar (ej: factura, cotizacion, oportunidad)"
        )
    
    with col_b:
        id_registro = st.number_input(
            "ID de registro", 
            min_value=1, 
            step=1,
            help="ID del registro específico a verificar"
        )
    
    with col_c:
        st.write("")  # Espaciado
        st.write("")
        verificar_btn = st.button("🔍 Verificar Integridad", type="primary", use_container_width=True)
    
    if verificar_btn:
        try:
            with st.spinner("Verificando integridad..."):
                resultado = repo_hash.verificar_integridad_cruzada(tabla_origen, id_registro)
            
            if resultado.get("resultado") == "sin_datos":
                st.warning("⚠️ No se encontraron datos suficientes para verificar.")
            else:
                if resultado["integridad_ok"]:
                    st.success("✅ **INTEGRIDAD VERIFICADA** - Los hashes coinciden")
                else:
                    st.error("❌ **ALERTA DE INTEGRIDAD** - Los hashes NO coinciden")
                
                # Mostrar detalles
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Tabla", resultado['tabla_origen'])
                    st.metric("ID Registro", resultado['id_registro'])
                
                with col2:
                    st.metric(
                        "Estado", 
                        "OK" if resultado['integridad_ok'] else "ERROR",
                        delta="Verificado" if resultado['integridad_ok'] else "Inconsistencia detectada",
                        delta_color="normal" if resultado['integridad_ok'] else "inverse"
                    )
                
                # Hash completo
                with st.expander("🔐 Ver Hashes Completos"):
                    st.code(f"Hash Registro: {resultado['hash_completo_registro']}", language="text")
                    st.code(f"Hash Evento:   {resultado['hash_completo_evento']}", language="text")
        
        except Exception as e:
            st.error(f"❌ Error al verificar: {e}")
    
    # Auditoría masiva
    st.divider()
    st.subheader("🔍 Auditoría Masiva")
    
    if st.button("Ejecutar Auditoría Completa del Sistema", type="secondary"):
        with st.spinner("Auditando todos los registros..."):
            try:
                auditoria = repo_hash.auditoria_completa()
                
                # Métricas principales
                col1, col2, col3, col4 = st.columns(4)
                
                col1.metric("Total Verificados", auditoria['total_verificados'])
                col2.metric("✅ Integridad OK", auditoria['integridad_ok'])
                col3.metric("❌ Errores", auditoria['integridad_error'])
                col4.metric("⚠️ Sin Datos", auditoria['sin_datos'])
                
                # Detalles de errores
                if auditoria['integridad_error'] > 0:
                    st.error("🚨 Se encontraron inconsistencias de integridad:")
                    for detalle in auditoria['detalles']:
                        with st.expander(f"❌ {detalle['tabla_origen']}[{detalle['id_registro']}]"):
                            st.json(detalle)
                else:
                    st.success("✅ Todos los registros tienen integridad verificada")
            
            except Exception as e:
                st.error(f"Error en auditoría: {e}")

# ================================================================
#  TAB 4: Línea de Tiempo
# ================================================================
with tab4:
    st.subheader("📅 Línea de Tiempo de Entidad")
    
    st.markdown("""
    Reconstruye la historia completa de un registro específico, 
    mostrando todos los eventos en orden cronológico.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        entidad_lt = st.text_input(
            "Entidad (tabla)", 
            "empresas",
            help="Nombre de la tabla (ej: empresas, oportunidades, facturas)"
        )
    
    with col2:
        id_entidad_lt = st.number_input(
            "ID de la entidad", 
            min_value=1, 
            step=1,
            help="ID del registro a rastrear"
        )
    
    if st.button("📅 Generar Línea de Tiempo", type="primary"):
        try:
            with st.spinner("Reconstruyendo historia..."):
                linea = repo_hist.linea_tiempo(entidad_lt, id_entidad_lt)
            
            if not linea:
                st.warning(f"No hay eventos registrados para {entidad_lt}[{id_entidad_lt}]")
            else:
                st.success(f"📅 {len(linea)} eventos encontrados")
                
                # Mostrar línea de tiempo
                for i, evento in enumerate(linea):
                    with st.container():
                        col_tiempo, col_evento = st.columns([1, 4])
                        
                        with col_tiempo:
                            st.caption(evento['timestamp'][:19])
                            st.caption(f"ID: {evento['id_evento']}")
                        
                        with col_evento:
                            st.markdown(f"**{evento['accion']}** por `{evento['usuario']}`")
                            
                            if evento.get('valor_nuevo'):
                                with st.expander("Ver cambios"):
                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        st.caption("Valor Anterior:")
                                        st.code(evento.get('valor_anterior', 'N/A'), language="json")
                                    with col_b:
                                        st.caption("Valor Nuevo:")
                                        st.code(evento.get('valor_nuevo', 'N/A'), language="json")
                        
                        if i < len(linea) - 1:
                            st.markdown("---")
        
        except Exception as e:
            st.error(f"Error al generar línea de tiempo: {e}")

# ================================================================
#  TAB 5: Estadísticas
# ================================================================
with tab5:
    st.subheader("📊 Estadísticas de Auditoría")
    
    try:
        stats_h = repo_hist.estadisticas()
        stats_hash = repo_hash.estadisticas()
        
        # Métricas principales
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Total de Eventos", stats_h.get('total_eventos', 0))
        
        with col2:
            st.metric("Total de Hashes", stats_hash.get('total_hashes', 0))
        
        st.divider()
        
        # Gráficos
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.subheader("Eventos por Entidad")
            if stats_h.get('por_entidad'):
                df_entidad = pd.DataFrame(
                    list(stats_h['por_entidad'].items()),
                    columns=['Entidad', 'Eventos']
                ).sort_values('Eventos', ascending=False)
                st.bar_chart(df_entidad.set_index('Entidad'))
            else:
                st.info("Sin datos")
        
        with col_b:
            st.subheader("Eventos por Acción")
            if stats_h.get('por_accion'):
                df_accion = pd.DataFrame(
                    list(stats_h['por_accion'].items()),
                    columns=['Acción', 'Eventos']
                ).sort_values('Eventos', ascending=False)
                st.bar_chart(df_accion.set_index('Acción'))
            else:
                st.info("Sin datos")
        
        st.divider()
        
        # Top usuarios
        st.subheader("Top Usuarios por Actividad")
        if stats_h.get('top_usuarios'):
            df_usuarios = pd.DataFrame(
                list(stats_h['top_usuarios'].items()),
                columns=['Usuario', 'Eventos']
            ).sort_values('Eventos', ascending=False)
            st.dataframe(df_usuarios, use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos de usuarios")
        
        # Hashes por tabla
        st.divider()
        st.subheader("Hashes por Tabla Origen")
        if stats_hash.get('por_tabla'):
            df_tabla = pd.DataFrame(
                list(stats_hash['por_tabla'].items()),
                columns=['Tabla', 'Hashes']
            ).sort_values('Hashes', ascending=False)
            st.dataframe(df_tabla, use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos de hashes")
    
    except Exception as e:
        st.error(f"Error al cargar estadísticas: {e}")

# ================================================================
#  Footer
# ================================================================
st.divider()
st.caption(f"""
📘 **CRM-EXO v2** | Núcleo 4 - Trazabilidad Estructural  
🔐 Auditoría forense con verificación SHA-256  
⏰ Última actualización: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
""")
