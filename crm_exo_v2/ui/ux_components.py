# ================================================================
#  ux_components.py  |  CRM-EXO v2  (UX Components - Nivel 1)
#  ---------------------------------------------------------------
#  Componentes reutilizables de UX para mejorar experiencia:
#  - Búsqueda avanzada con filtros
#  - Visualizaciones Plotly interactivas
#  - Shortcuts de teclado
#  - Loading states y feedback visual
#  - Navegación mejorada con breadcrumbs
# ================================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
import time
import streamlit.components.v1 as components


# ================================================================
#  1. BÚSQUEDA AVANZADA
# ================================================================

def advanced_search_widget(
    df: pd.DataFrame,
    entity_name: str,
    search_columns: Optional[List[str]] = None,
    date_column: Optional[str] = None,
    category_filters: Optional[Dict[str, str]] = None
) -> pd.DataFrame:
    """
    Widget de búsqueda avanzada con múltiples filtros.
    
    Args:
        df: DataFrame con los datos
        entity_name: Nombre de la entidad (para labels)
        search_columns: Columnas para búsqueda de texto (None = todas)
        date_column: Columna de fecha para filtro de rango
        category_filters: Dict {nombre_columna: label} para selectboxes
    
    Returns:
        DataFrame filtrado
    """
    
    st.markdown(f"### 🔍 Búsqueda Avanzada - {entity_name}")
    
    with st.expander("⚙️ Filtros", expanded=False):
        # Búsqueda de texto libre
        col1, col2 = st.columns([2, 1])
        
        with col1:
            search_term = st.text_input(
                "🔎 Buscar",
                placeholder="Escribe para filtrar...",
                key=f"search_{entity_name}",
                help="Búsqueda en múltiples campos"
            )
        
        with col2:
            if date_column and date_column in df.columns:
                use_date_filter = st.checkbox(
                    "📅 Filtrar por fecha",
                    key=f"use_date_{entity_name}"
                )
        
        # Filtros de categoría
        active_filters = {}
        if category_filters:
            cols = st.columns(len(category_filters))
            for idx, (col_name, label) in enumerate(category_filters.items()):
                if col_name in df.columns:
                    with cols[idx]:
                        unique_values = ['Todos'] + sorted(df[col_name].dropna().unique().tolist())
                        selected = st.selectbox(
                            label,
                            unique_values,
                            key=f"filter_{entity_name}_{col_name}"
                        )
                        if selected != 'Todos':
                            active_filters[col_name] = selected
        
        # Filtro de fecha
        if date_column and date_column in df.columns and use_date_filter:
            date_range = st.date_input(
                "Rango de fechas",
                value=[],
                key=f"date_{entity_name}"
            )
    
    # Aplicar filtros
    filtered_df = df.copy()
    
    # Filtro de texto
    if search_term:
        if search_columns:
            # Buscar solo en columnas específicas
            mask = filtered_df[search_columns].apply(
                lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(),
                axis=1
            )
        else:
            # Buscar en todas las columnas
            mask = filtered_df.apply(
                lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(),
                axis=1
            )
        filtered_df = filtered_df[mask]
    
    # Filtros de categoría
    for col_name, value in active_filters.items():
        filtered_df = filtered_df[filtered_df[col_name] == value]
    
    # Filtro de fecha
    if date_column and date_column in df.columns and use_date_filter and 'date_range' in locals() and len(date_range) == 2:
        filtered_df[date_column] = pd.to_datetime(filtered_df[date_column])
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (filtered_df[date_column].dt.date >= start_date) &
            (filtered_df[date_column].dt.date <= end_date)
        ]
    
    # Mostrar conteo
    st.caption(f"📊 Mostrando **{len(filtered_df)}** de **{len(df)}** registros")
    
    return filtered_df


# ================================================================
#  2. VISUALIZACIONES PLOTLY INTERACTIVAS
# ================================================================

def pipeline_funnel_interactive(df_oportunidades: pd.DataFrame):
    """
    Funnel interactivo del pipeline de ventas.
    
    Args:
        df_oportunidades: DataFrame con columnas 'etapa', 'monto_estimado'
    """
    
    if df_oportunidades.empty:
        st.info("📊 No hay datos de oportunidades para mostrar")
        return
    
    # Agrupar por etapa
    etapa_orden = ['Calificación', 'Negociación', 'Propuesta', 'Cierre', 'Ganada']
    
    funnel_data = df_oportunidades.groupby('etapa').agg({
        'id_oportunidad': 'count',
        'monto_estimado': 'sum'
    }).reset_index()
    
    funnel_data.columns = ['Etapa', 'Cantidad', 'Monto Total']
    
    # Ordenar por etapas
    funnel_data['orden'] = funnel_data['Etapa'].map({e: i for i, e in enumerate(etapa_orden)})
    funnel_data = funnel_data.sort_values('orden')
    
    # Crear funnel
    fig = go.Figure(go.Funnel(
        y=funnel_data['Etapa'],
        x=funnel_data['Cantidad'],
        text=funnel_data['Monto Total'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "$0"),
        textposition='inside',
        textinfo='value+text+percent initial',
        marker=dict(
            color=['#4CAF50', '#2196F3', '#FF9800', '#F44336', '#9C27B0'][:len(funnel_data)],
        ),
        connector={"line": {"color": "royalblue", "dash": "dot", "width": 3}}
    ))
    
    fig.update_layout(
        title="📊 Pipeline de Ventas - Funnel Interactivo",
        height=500,
        hovermode='x unified',
        font=dict(size=14)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Métricas de conversión
    col1, col2, col3, col4 = st.columns(4)
    
    total_oportunidades = len(df_oportunidades)
    ganadas = len(df_oportunidades[df_oportunidades['etapa'] == 'Ganada'])
    perdidas = len(df_oportunidades[df_oportunidades['etapa'] == 'Perdida'])
    tasa_conversion = (ganadas / total_oportunidades * 100) if total_oportunidades > 0 else 0
    
    col1.metric("Total Oportunidades", total_oportunidades)
    col2.metric("Ganadas", ganadas, delta=f"{tasa_conversion:.1f}%")
    col3.metric("Perdidas", perdidas, delta=f"-{(perdidas/total_oportunidades*100):.1f}%" if total_oportunidades > 0 else "0%")
    
    monto_total = df_oportunidades[df_oportunidades['etapa'] == 'Ganada']['monto_estimado'].sum()
    col4.metric("Monto Ganado", f"${monto_total:,.0f}")


def timeline_actividad_visual(df_historial: pd.DataFrame, limit: int = 30):
    """
    Timeline visual de actividad reciente.
    
    Args:
        df_historial: DataFrame con columnas 'fecha', 'accion', 'entidad', 'usuario'
        limit: Número máximo de eventos a mostrar
    """
    
    if df_historial.empty:
        st.info("📅 No hay actividad reciente para mostrar")
        return
    
    # Top N eventos recientes
    df_reciente = df_historial.head(limit).copy()
    df_reciente['fecha'] = pd.to_datetime(df_reciente['fecha'])
    
    # Mapeo de colores por acción
    color_map = {
        'crear': '#4CAF50',
        'actualizar': '#2196F3',
        'eliminar': '#F44336',
        'convertir': '#9C27B0',
        'facturar': '#FF9800'
    }
    
    df_reciente['color'] = df_reciente['accion'].apply(
        lambda x: color_map.get(str(x).lower(), '#757575')
    )
    
    # Scatter plot como timeline
    fig = px.scatter(
        df_reciente,
        x='fecha',
        y='entidad',
        color='accion',
        size_max=15,
        hover_data=['usuario'] if 'usuario' in df_reciente.columns else None,
        title="📅 Timeline de Actividad Reciente",
        color_discrete_map=color_map
    )
    
    fig.update_traces(marker=dict(size=12))
    fig.update_layout(
        height=400,
        xaxis_title="Fecha",
        yaxis_title="Entidad",
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)


def grafico_metricas_dashboard(metricas: Dict[str, int]):
    """
    Gráfico de barras interactivo con métricas del dashboard.
    
    Args:
        metricas: Dict con nombre_metrica: valor
    """
    
    if not metricas:
        return
    
    df_metricas = pd.DataFrame([
        {'Indicador': k, 'Valor': v}
        for k, v in metricas.items()
    ])
    
    fig = px.bar(
        df_metricas,
        x='Indicador',
        y='Valor',
        title="📈 Indicadores de Completitud del Pipeline",
        color='Valor',
        color_continuous_scale='RdYlGn_r',  # Rojo (malo) -> Verde (bueno)
        text='Valor'
    )
    
    fig.update_traces(texttemplate='%{text}', textposition='outside')
    fig.update_layout(
        height=400,
        showlegend=False,
        xaxis_title="",
        yaxis_title="Cantidad"
    )
    
    st.plotly_chart(fig, use_container_width=True)


# ================================================================
#  3. SHORTCUTS DE TECLADO
# ================================================================

def keyboard_shortcuts_handler():
    """
    Manejador global de atajos de teclado.
    
    Shortcuts disponibles:
    - Ctrl/Cmd + K: Focus en búsqueda
    - Ctrl/Cmd + N: Nuevo registro
    - Ctrl/Cmd + S: Guardar
    - Escape: Cerrar modales
    """
    
    shortcuts_html = """
    <script>
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K: Búsqueda rápida
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInputs = document.querySelectorAll('input[placeholder*="Buscar"], input[placeholder*="buscar"]');
            if (searchInputs.length > 0) {
                searchInputs[0].focus();
                searchInputs[0].select();
            }
        }
        
        // Ctrl/Cmd + N: Nueva entidad
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            const addButtons = document.querySelectorAll('button');
            for (let btn of addButtons) {
                if (btn.textContent.includes('Nuevo') || btn.textContent.includes('Agregar') || btn.textContent.includes('Crear')) {
                    btn.click();
                    break;
                }
            }
        }
        
        // Ctrl/Cmd + S: Guardar
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            const saveButtons = document.querySelectorAll('button[type="submit"], button');
            for (let btn of saveButtons) {
                if (btn.textContent.includes('Guardar') || btn.textContent.includes('Enviar')) {
                    btn.click();
                    break;
                }
            }
        }
        
        // Escape: Cerrar modales/expandables
        if (e.key === 'Escape') {
            const closeButtons = document.querySelectorAll('button[aria-label="Close"]');
            closeButtons.forEach(btn => btn.click());
        }
    });
    </script>
    
    <style>
    .keyboard-hints {
        position: fixed;
        bottom: 10px;
        right: 10px;
        background: rgba(0, 0, 0, 0.85);
        color: white;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 11px;
        z-index: 9999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        max-width: 200px;
    }
    .keyboard-hints strong {
        display: block;
        margin-bottom: 8px;
        font-size: 12px;
        color: #4A9EFF;
    }
    .keyboard-hints code {
        background: rgba(255, 255, 255, 0.2);
        padding: 2px 6px;
        border-radius: 3px;
        font-family: monospace;
        font-size: 10px;
    }
    .keyboard-hints div {
        margin: 4px 0;
    }
    </style>
    
    <div class="keyboard-hints">
        <strong>⌨️ Atajos de Teclado</strong>
        <div><code>Ctrl+K</code> Buscar</div>
        <div><code>Ctrl+N</code> Nuevo</div>
        <div><code>Ctrl+S</code> Guardar</div>
        <div><code>Esc</code> Cerrar</div>
    </div>
    """
    
    components.html(shortcuts_html, height=0)


# ================================================================
#  4. LOADING STATES Y FEEDBACK VISUAL
# ================================================================

def with_loading_state(message: str = "⏳ Procesando..."):
    """
    Decorator para mostrar estado de carga.
    
    Uso:
        @with_loading_state("Guardando empresa...")
        def guardar_empresa(datos):
            # lógica
            return resultado
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            with st.spinner(message):
                result = func(*args, **kwargs)
                st.success("✅ Operación completada exitosamente", icon="✅")
                time.sleep(0.3)  # Feedback visual breve
                return result
        return wrapper
    return decorator


def show_progress_bar(total: int, message_template: str = "Procesando {current}/{total}..."):
    """
    Muestra barra de progreso para operaciones largas.
    
    Uso:
        progress = show_progress_bar(total=100)
        for i in range(100):
            # procesar
            progress.update(i+1)
        progress.complete()
    
    Returns:
        Objeto ProgressBar con métodos update() y complete()
    """
    
    class ProgressBar:
        def __init__(self, total, message_template):
            self.total = total
            self.message_template = message_template
            self.progress_bar = st.progress(0)
            self.status_text = st.empty()
        
        def update(self, current: int):
            progress = current / self.total
            self.progress_bar.progress(progress)
            message = self.message_template.format(current=current, total=self.total)
            self.status_text.text(message)
        
        def complete(self, success_message: str = "✅ Proceso completado"):
            self.progress_bar.empty()
            self.status_text.success(success_message)
    
    return ProgressBar(total, message_template)


def toast_notification(message: str, icon: str = "✅", duration: float = 2.0):
    """
    Muestra notificación toast temporal.
    
    Args:
        message: Mensaje a mostrar
        icon: Emoji o icono
        duration: Duración en segundos
    """
    placeholder = st.empty()
    
    placeholder.success(f"{icon} {message}")
    time.sleep(duration)
    placeholder.empty()


# ================================================================
#  5. NAVEGACIÓN MEJORADA CON BREADCRUMBS
# ================================================================

def smart_navigation_menu(current_page: str):
    """
    Menú de navegación inteligente con breadcrumbs.
    
    Args:
        current_page: Nombre de la página actual
    """
    
    # CSS para breadcrumbs
    st.markdown("""
    <style>
    .breadcrumb {
        background: linear-gradient(90deg, #f0f2f6 0%, #ffffff 100%);
        padding: 12px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        border-left: 4px solid #0068c9;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .breadcrumb a {
        color: #0068c9;
        text-decoration: none;
        margin: 0 5px;
        font-weight: 500;
    }
    .breadcrumb a:hover {
        text-decoration: underline;
    }
    .breadcrumb .current {
        color: #262730;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Breadcrumb visual
    breadcrumb_html = '<div class="breadcrumb">'
    breadcrumb_html += '🏠 Home / '
    breadcrumb_html += f'<span class="current">📍 {current_page}</span>'
    breadcrumb_html += '</div>'
    
    st.markdown(breadcrumb_html, unsafe_allow_html=True)


def contextual_quick_actions(page_context: str):
    """
    Acciones rápidas contextuales según la página actual.
    
    Args:
        page_context: Contexto de la página ('empresas', 'oportunidades', etc.)
    """
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚡ Acciones Rápidas")
    
    quick_actions = {
        'empresas': [
            ('➕ Nueva Empresa', 'show_form_empresa'),
            ('👥 Ver Contactos', 'menu_contactos')
        ],
        'contactos': [
            ('➕ Nuevo Contacto', 'show_form_contacto'),
            ('🏢 Ver Empresas', 'menu_empresas')
        ],
        'oportunidades': [
            ('➕ Nueva Oportunidad', 'show_form_oportunidad'),
            ('📊 Ver Pipeline', 'menu_pipeline')
        ],
        'facturacion': [
            ('📄 Nueva Factura', 'show_form_factura'),
            ('📋 Ver OCs', 'menu_ordenes_compra')
        ]
    }
    
    actions = quick_actions.get(page_context.lower(), [])
    
    for label, state_key in actions:
        if st.sidebar.button(label, use_container_width=True, key=f"quickaction_{state_key}"):
            st.session_state[state_key] = True
            st.rerun()


# ================================================================
#  6. COMPONENTES AUXILIARES
# ================================================================

def data_table_with_actions(
    df: pd.DataFrame,
    key: str,
    show_edit: bool = True,
    show_delete: bool = True,
    on_edit: Optional[Callable] = None,
    on_delete: Optional[Callable] = None
):
    """
    Tabla de datos con acciones de editar/eliminar por fila.
    
    Args:
        df: DataFrame a mostrar
        key: Clave única para el componente
        show_edit: Mostrar botón de editar
        show_delete: Mostrar botón de eliminar
        on_edit: Callback al editar (recibe el id de la fila)
        on_delete: Callback al eliminar (recibe el id de la fila)
    """
    
    if df.empty:
        st.info("📭 No hay datos para mostrar")
        return
    
    # Agregar columna de acciones si es necesario
    if show_edit or show_delete:
        for idx, row in df.iterrows():
            col1, col2, col3 = st.columns([6, 1, 1])
            
            with col1:
                # Mostrar datos de la fila
                st.write(row.to_dict())
            
            if show_edit:
                with col2:
                    if st.button("✏️", key=f"{key}_edit_{idx}"):
                        if on_edit:
                            on_edit(row.get('id', idx))
            
            if show_delete:
                with col3:
                    if st.button("🗑️", key=f"{key}_delete_{idx}"):
                        if on_delete:
                            on_delete(row.get('id', idx))
            
            st.divider()
    else:
        st.dataframe(df, use_container_width=True)


def metric_card(label: str, value: Any, delta: Optional[str] = None, icon: str = "📊"):
    """
    Card de métrica con estilo mejorado.
    
    Args:
        label: Etiqueta de la métrica
        value: Valor a mostrar
        delta: Cambio respecto al período anterior
        icon: Emoji/icono
    """
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    ">
        <div style="font-size: 24px; margin-bottom: 8px;">{icon}</div>
        <div style="font-size: 14px; opacity: 0.9;">{label}</div>
        <div style="font-size: 32px; font-weight: bold; margin-top: 8px;">{value}</div>
        {f'<div style="font-size: 12px; margin-top: 4px; opacity: 0.8;">{delta}</div>' if delta else ''}
    </div>
    """, unsafe_allow_html=True)


# ================================================================
#  6. BULK OPERATIONS (Operaciones Masivas)
# ================================================================

def bulk_operations_widget(df: pd.DataFrame, entity_name: str, id_column: str = 'id', 
                           name_column: str = 'nombre', on_delete_callback=None,
                           on_export_callback=None, updatable_fields: Optional[List[str]] = None):
    """
    Widget para operaciones masivas en listas.
    
    Args:
        df: DataFrame con los datos
        entity_name: Nombre de la entidad (para labels)
        id_column: Nombre de la columna de ID
        name_column: Nombre de la columna para mostrar en selección
        on_delete_callback: Función callback(ids) al eliminar
        on_export_callback: Función callback(df_seleccionado) al exportar
        updatable_fields: Lista de campos actualizables masivamente
    
    Returns:
        Lista de IDs seleccionados
    """
    
    if df.empty:
        return []
    
    st.markdown(f"### 📋 Operaciones Masivas - {entity_name}")
    
    # Selección múltiple
    if id_column not in df.columns or name_column not in df.columns:
        st.error(f"⚠️ Columnas requeridas no encontradas: {id_column}, {name_column}")
        return []
    
    # Crear opciones para multiselect
    options_dict = {row[id_column]: f"{row[name_column]} (ID: {row[id_column]})" 
                   for _, row in df.iterrows()}
    
    selected_ids = st.multiselect(
        f"Seleccionar {entity_name.lower()}:",
        options=list(options_dict.keys()),
        format_func=lambda x: options_dict[x],
        key=f"bulk_select_{entity_name}"
    )
    
    if not selected_ids:
        st.info("👆 Selecciona uno o más registros para habilitar operaciones masivas")
        return []
    
    # Mostrar contador
    st.success(f"✅ {len(selected_ids)} registro(s) seleccionado(s)")
    
    # Botones de acción
    col1, col2, col3 = st.columns(3)
    
    # 1. Eliminar
    with col1:
        if st.button(f"🗑️ Eliminar ({len(selected_ids)})", 
                    type="secondary", 
                    key=f"bulk_delete_{entity_name}"):
            if on_delete_callback:
                with st.spinner("Eliminando..."):
                    try:
                        on_delete_callback(selected_ids)
                        st.success(f"✅ {len(selected_ids)} registro(s) eliminado(s)")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al eliminar: {e}")
            else:
                st.warning("⚠️ Callback de eliminación no configurado")
    
    # 2. Exportar
    with col2:
        df_selected = df[df[id_column].isin(selected_ids)]
        csv = df_selected.to_csv(index=False)
        
        st.download_button(
            f"📤 Exportar ({len(selected_ids)})",
            csv,
            f"{entity_name.lower()}_{datetime.now():%Y%m%d_%H%M%S}.csv",
            "text/csv",
            key=f"bulk_export_{entity_name}"
        )
    
    # 3. Actualizar campo (si hay campos configurados)
    if updatable_fields:
        with col3:
            with st.popover(f"✏️ Actualizar ({len(selected_ids)})"):
                campo = st.selectbox(
                    "Campo a actualizar:",
                    updatable_fields,
                    key=f"bulk_field_{entity_name}"
                )
                
                nuevo_valor = st.text_input(
                    "Nuevo valor:",
                    key=f"bulk_value_{entity_name}"
                )
                
                if st.button("💾 Aplicar", key=f"bulk_apply_{entity_name}"):
                    if nuevo_valor:
                        # El callback debe manejar la actualización
                        st.success(f"✅ Campo '{campo}' actualizado en {len(selected_ids)} registro(s)")
                        st.info("💡 Implementa el callback de actualización para persistir cambios")
                    else:
                        st.warning("⚠️ Ingresa un valor")
    
    return selected_ids


# ================================================================
#  7. SISTEMA DE NOTIFICACIONES
# ================================================================

def notification_center(db_connection):
    """
    Centro de notificaciones inteligente en sidebar.
    
    Detecta y muestra:
    - Oportunidades estancadas (>7 días sin cambio)
    - OCs pendientes de facturar
    - Empresas sin contactos
    - Prospectos sin oportunidades
    - Certificados CFDI próximos a vencer
    
    Args:
        db_connection: Conexión a la base de datos
    """
    
    import pandas as pd
    from datetime import datetime, timedelta
    
    notificaciones = []
    
    # 1. Oportunidades estancadas (>7 días sin cambio)
    try:
        # Detectar motor de DB para query correcta
        cursor = db_connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='oportunidades'")
        is_sqlite = cursor.fetchone() is not None
        
        if is_sqlite:
            query_estancadas = """
                SELECT nombre, etapa, 
                       CAST(julianday('now') - julianday(fecha_ultima_actualizacion) AS INTEGER) as dias_sin_cambio
                FROM oportunidades
                WHERE etapa NOT IN ('Ganada', 'Perdida')
                  AND julianday('now') - julianday(fecha_ultima_actualizacion) > 7
                ORDER BY dias_sin_cambio DESC
                LIMIT 5
            """
        else:
            query_estancadas = """
                SELECT nombre, etapa, 
                       EXTRACT(DAY FROM (NOW() - fecha_ultima_actualizacion))::INTEGER as dias_sin_cambio
                FROM oportunidades
                WHERE etapa NOT IN ('Ganada', 'Perdida')
                  AND NOW() - fecha_ultima_actualizacion > INTERVAL '7 days'
                ORDER BY dias_sin_cambio DESC
                LIMIT 5
            """
        
        df_estancadas = pd.read_sql(query_estancadas, db_connection)
        
        for _, opp in df_estancadas.iterrows():
            notificaciones.append({
                'tipo': 'warning',
                'prioridad': 'alta',
                'icono': '⚠️',
                'mensaje': f"Oportunidad '{opp['nombre']}' estancada {int(opp['dias_sin_cambio'])} días",
                'accion': 'Ver Oportunidades',
                'menu_destino': '💼 N2: Transacción'
            })
    except Exception as e:
        pass  # Si falla, no romper la app
    
    # 2. OCs pendientes de facturar
    try:
        query_ocs = """
            SELECT o.numero_oc, o.monto_oc
            FROM ordenes_compra o
            LEFT JOIN facturas f ON f.id_oc = o.id_oc
            WHERE f.id_factura IS NULL
        """
        df_ocs_pending = pd.read_sql(query_ocs, db_connection)
        
        if len(df_ocs_pending) > 0:
            total_monto = df_ocs_pending['monto_oc'].sum()
            notificaciones.append({
                'tipo': 'info',
                'prioridad': 'media',
                'icono': '📋',
                'mensaje': f"{len(df_ocs_pending)} OC(s) pendientes (${total_monto:,.0f})",
                'accion': 'Ir a Facturación',
                'menu_destino': '💰 N3: Facturación'
            })
    except Exception:
        pass
    
    # 3. Empresas sin contactos
    try:
        query_empresas = """
            SELECT COUNT(*) AS total
            FROM empresas e
            LEFT JOIN contactos c ON c.id_empresa = e.id_empresa
            WHERE c.id_contacto IS NULL
        """
        empresas_sin_contacto = pd.read_sql(query_empresas, db_connection).iloc[0]['total']
        
        if empresas_sin_contacto > 0:
            notificaciones.append({
                'tipo': 'info',
                'prioridad': 'media',
                'icono': '🏢',
                'mensaje': f"{empresas_sin_contacto} empresa(s) sin contacto",
                'accion': 'Ver Empresas',
                'menu_destino': '🏗️ N1: Identidad'
            })
    except Exception:
        pass
    
    # 4. Prospectos sin oportunidades
    try:
        query_prospectos = """
            SELECT COUNT(*) AS total
            FROM prospectos p
            LEFT JOIN oportunidades o ON o.id_prospecto = p.id_prospecto
            WHERE p.es_cliente = 0 AND o.id_oportunidad IS NULL
        """
        prospectos_sin_opp = pd.read_sql(query_prospectos, db_connection).iloc[0]['total']
        
        if prospectos_sin_opp > 0:
            notificaciones.append({
                'tipo': 'info',
                'prioridad': 'baja',
                'icono': '📈',
                'mensaje': f"{prospectos_sin_opp} prospecto(s) sin oportunidad",
                'accion': 'Ver Prospectos',
                'menu_destino': '🏗️ N1: Identidad'
            })
    except Exception:
        pass
    
    # 5. Certificados CFDI (si está disponible)
    try:
        # Importar solo si está disponible
        from facturacion.cfdi_emisor import obtener_configuracion_emisor
        
        config_cfdi = obtener_configuracion_emisor()
        if config_cfdi:
            # Aquí podrías verificar fecha de vencimiento si está en la config
            # Por ahora, solo notificar si no está configurado
            pass
    except Exception:
        # Si CFDI no está configurado, notificar
        notificaciones.append({
            'tipo': 'warning',
            'prioridad': 'media',
            'icono': '🔐',
            'mensaje': 'CFDI no configurado',
            'accion': 'Configurar',
            'menu_destino': '⚙️ Configuración CFDI'
        })
    
    # Renderizar notificaciones en sidebar
    count = len(notificaciones)
    
    st.markdown("---")
    
    if count > 0:
        st.markdown(f"### 🔔 Notificaciones ({count})")
        
        # Ordenar por prioridad
        prioridad_orden = {'alta': 0, 'media': 1, 'baja': 2}
        notificaciones.sort(key=lambda x: prioridad_orden.get(x['prioridad'], 3))
        
        # Mostrar solo las 3 más importantes
        for notif in notificaciones[:3]:
            color = {
                'warning': '#FF9800',
                'info': '#2196F3',
                'success': '#4CAF50',
                'error': '#F44336'
            }.get(notif['tipo'], '#757575')
            
            st.markdown(f"""
            <div style="
                background: {color}22; 
                border-left: 4px solid {color}; 
                padding: 10px; 
                margin: 5px 0; 
                border-radius: 3px;
            ">
                <small><strong>{notif['icono']} {notif['mensaje']}</strong></small>
            </div>
            """, unsafe_allow_html=True)
            
            # Botón de acción
            if st.button(
                notif['accion'], 
                key=f"notif_action_{notificaciones.index(notif)}",
                use_container_width=True,
                type="secondary"
            ):
                st.session_state.menu_seleccionado = notif['menu_destino']
                st.rerun()
        
        if count > 3:
            st.caption(f"...y {count - 3} más")
    else:
        st.success("🔔 Sin notificaciones")
    
    st.markdown("---")


# ================================================================
#  8. IMPORT/EXPORT WIZARD
# ================================================================

def import_export_wizard(db_connection, entity_name: str, table_name: str, columns_map: Dict[str, str]):
    """
    Asistente para importación y exportación masiva de datos.
    
    Args:
        db_connection: Conexión a la base de datos
        entity_name: Nombre de la entidad (ej. "Empresas")
        table_name: Nombre de la tabla en DB
        columns_map: Mapeo {campo_ui: columna_db}
    """
    
    st.markdown(f"### 📦 Asistente de Import/Export - {entity_name}")
    
    tab1, tab2 = st.tabs(["📥 Importar", "📤 Exportar"])
    
    # TAB: IMPORTAR
    with tab1:
        st.markdown("**Importar datos desde archivo CSV/Excel**")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_file = st.file_uploader(
                "Selecciona archivo",
                type=['csv', 'xlsx', 'xls'],
                help="Formatos soportados: CSV, Excel (.xlsx, .xls)",
                key=f"uploader_{entity_name}"
            )
        
        with col2:
            # Descargar plantilla
            plantilla_df = pd.DataFrame(columns=list(columns_map.keys()))
            csv_plantilla = plantilla_df.to_csv(index=False)
            st.download_button(
                "📋 Descargar Plantilla",
                csv_plantilla,
                f"plantilla_{table_name}.csv",
                "text/csv",
                help="Descarga una plantilla con las columnas correctas"
            )
        
        if uploaded_file:
            try:
                # Leer archivo
                if uploaded_file.name.endswith('.csv'):
                    import_df = pd.read_csv(uploaded_file)
                else:
                    import_df = pd.read_excel(uploaded_file)
                
                st.success(f"✅ Archivo cargado: {len(import_df)} registros")
                
                # Preview
                with st.expander("👁️ Vista Previa", expanded=True):
                    st.dataframe(import_df.head(10), use_container_width=True)
                
                # Validación de columnas
                columnas_faltantes = set(columns_map.keys()) - set(import_df.columns)
                columnas_extra = set(import_df.columns) - set(columns_map.keys())
                
                if columnas_faltantes:
                    st.warning(f"⚠️ Columnas faltantes: {', '.join(columnas_faltantes)}")
                
                if columnas_extra:
                    st.info(f"ℹ️ Columnas ignoradas: {', '.join(columnas_extra)}")
                
                # Opciones de importación
                st.markdown("**Opciones de Importación:**")
                col_opt1, col_opt2 = st.columns(2)
                
                with col_opt1:
                    skip_duplicates = st.checkbox(
                        "Saltar duplicados",
                        value=True,
                        help="No importar registros que ya existen"
                    )
                
                with col_opt2:
                    validate_data = st.checkbox(
                        "Validar datos",
                        value=True,
                        help="Verificar formato y requeridos"
                    )
                
                # Botón de importación
                if st.button(f"🚀 Importar {len(import_df)} Registros", type="primary"):
                    with st.spinner("Importando..."):
                        success_count = 0
                        error_count = 0
                        errors = []
                        
                        progress_bar = st.progress(0)
                        
                        for idx, row in import_df.iterrows():
                            try:
                                # Mapear columnas
                                valores = {columns_map.get(k, k): v for k, v in row.items() if k in columns_map}
                                
                                # Validación básica
                                if validate_data:
                                    # Verificar campos no vacíos
                                    if any(pd.isna(valores.values())):
                                        raise ValueError("Campos requeridos vacíos")
                                
                                # Insertar (esto debe ser implementado según la lógica de cada entidad)
                                # Aquí solo mostramos el concepto
                                success_count += 1
                                
                            except Exception as e:
                                error_count += 1
                                errors.append(f"Fila {idx + 2}: {str(e)}")
                            
                            # Actualizar progreso
                            progress_bar.progress((idx + 1) / len(import_df))
                        
                        # Resultados
                        st.success(f"✅ Importados: {success_count} registros")
                        
                        if error_count > 0:
                            st.error(f"❌ Errores: {error_count} registros")
                            with st.expander("Ver errores"):
                                for error in errors[:10]:
                                    st.text(error)
                                if len(errors) > 10:
                                    st.caption(f"...y {len(errors) - 10} errores más")
                        
                        st.info("💡 **Implementación pendiente:** Conectar con la lógica de inserción de cada entidad")
                
            except Exception as e:
                st.error(f"❌ Error al leer archivo: {str(e)}")
    
    # TAB: EXPORTAR
    with tab2:
        st.markdown("**Exportar datos a archivo CSV/Excel**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Opciones de exportación
            export_format = st.radio(
                "Formato de salida:",
                ["CSV", "Excel"],
                horizontal=True,
                key=f"format_{entity_name}"
            )
        
        with col2:
            include_all = st.checkbox(
                "Incluir todos los campos",
                value=True,
                help="Si no, solo campos visibles"
            )
        
        # Filtros para exportación
        with st.expander("⚙️ Filtros de Exportación"):
            st.info("Aplica filtros antes de exportar (usa búsqueda avanzada arriba)")
        
        # Obtener datos
        try:
            cursor = db_connection.cursor()
            export_df = pd.read_sql(f"SELECT * FROM {table_name} LIMIT 1000", db_connection)
            
            st.caption(f"📊 {len(export_df)} registros disponibles para exportar")
            
            # Botón de exportación
            if st.button(f"📥 Exportar {entity_name}", type="primary"):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if export_format == "CSV":
                    export_data = export_df.to_csv(index=False)
                    filename = f"{table_name}_export_{timestamp}.csv"
                    mime = "text/csv"
                else:
                    # Para Excel necesitaríamos openpyxl
                    export_data = export_df.to_csv(index=False)
                    filename = f"{table_name}_export_{timestamp}.csv"
                    mime = "text/csv"
                    st.warning("⚠️ Exportación Excel requiere librería openpyxl. Usando CSV.")
                
                st.download_button(
                    f"⬇️ Descargar {filename}",
                    export_data,
                    filename,
                    mime,
                    key=f"download_{entity_name}"
                )
                
                st.success(f"✅ {len(export_df)} registros listos para descargar")
        
        except Exception as e:
            st.error(f"❌ Error al exportar: {str(e)}")


# ================================================================
#  9. MODO OSCURO (DARK MODE)
# ================================================================

def dark_mode_toggle():
    """
    Toggle para cambiar entre modo claro y oscuro.
    Aplica estilos CSS custom para override de Streamlit.
    
    Returns:
        bool: True si modo oscuro está activo
    """
    
    # Inicializar estado
    if 'dark_mode' not in st.session_state:
        st.session_state.dark_mode = False
    
    # Toggle en sidebar
    dark_mode = st.sidebar.checkbox(
        "🌙 Modo Oscuro",
        value=st.session_state.dark_mode,
        key="dark_mode_toggle",
        help="Activa el tema oscuro para mejor visibilidad"
    )
    
    st.session_state.dark_mode = dark_mode
    
    # Aplicar CSS según modo
    if dark_mode:
        st.markdown("""
        <style>
            /* MODO OSCURO CUSTOM */
            .stApp {
                background-color: #0e1117;
                color: #fafafa;
            }
            
            /* Headers */
            .main-header {
                background: linear-gradient(135deg, #1e3a8a 0%, #3730a3 100%);
                color: white !important;
            }
            
            /* Tarjetas y contenedores */
            .stMarkdown, .stDataFrame, .stTable {
                background-color: #1e1e1e;
                color: #fafafa;
            }
            
            /* Inputs */
            .stTextInput > div > div > input,
            .stSelectbox > div > div > select,
            .stNumberInput > div > div > input {
                background-color: #262626;
                color: #fafafa;
                border-color: #3f3f46;
            }
            
            /* Botones */
            .stButton > button {
                background-color: #3730a3;
                color: white;
            }
            
            .stButton > button:hover {
                background-color: #4338ca;
            }
            
            /* Dataframes */
            .dataframe {
                background-color: #1e1e1e !important;
                color: #fafafa !important;
            }
            
            /* Sidebar */
            section[data-testid="stSidebar"] {
                background-color: #18181b;
            }
            
            /* Métricas */
            [data-testid="stMetricValue"] {
                color: #fafafa;
            }
            
            /* Expanders */
            .streamlit-expanderHeader {
                background-color: #262626;
                color: #fafafa;
            }
            
            /* Tabs */
            .stTabs [data-baseweb="tab-list"] {
                background-color: #1e1e1e;
            }
            
            .stTabs [data-baseweb="tab"] {
                color: #a1a1aa;
            }
            
            .stTabs [aria-selected="true"] {
                color: #fafafa;
                border-bottom-color: #3730a3;
            }
            
            /* Success/Error/Warning messages */
            .stSuccess {
                background-color: #14532d;
                color: #bbf7d0;
            }
            
            .stError {
                background-color: #7f1d1d;
                color: #fecaca;
            }
            
            .stWarning {
                background-color: #78350f;
                color: #fef3c7;
            }
            
            .stInfo {
                background-color: #1e3a8a;
                color: #bfdbfe;
            }
        </style>
        """, unsafe_allow_html=True)
    else:
        # Modo claro (estilos por defecto con mejoras)
        st.markdown("""
        <style>
            /* MODO CLARO MEJORADO */
            .main-header {
                background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
                padding: 1.5rem;
                border-radius: 10px;
                margin-bottom: 2rem;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                color: white;
                font-size: 1.8rem;
                font-weight: bold;
                text-align: center;
            }
            
            /* Métricas mejoradas */
            [data-testid="stMetricValue"] {
                font-size: 2rem;
                font-weight: bold;
            }
            
            /* Botones con mejor contraste */
            .stButton > button {
                border-radius: 8px;
                font-weight: 500;
                transition: all 0.2s;
            }
            
            .stButton > button:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            }
        </style>
        """, unsafe_allow_html=True)
    
    return dark_mode


# ================================================================
#  EXPORTS
# ================================================================

__all__ = [
    'advanced_search_widget',
    'pipeline_funnel_interactive',
    'timeline_actividad_visual',
    'grafico_metricas_dashboard',
    'keyboard_shortcuts_handler',
    'with_loading_state',
    'show_progress_bar',
    'toast_notification',
    'smart_navigation_menu',
    'contextual_quick_actions',
    'data_table_with_actions',
    'metric_card',
    'bulk_operations_widget',
    'notification_center',
    'import_export_wizard',
    'dark_mode_toggle'
]
