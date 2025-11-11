# 🚀 Guía de Integración del Módulo CFDI en CRM-EXO v2

## 📍 Integración en `app_crm_exo_v2.py`

### 1. Agregar imports al inicio del archivo

```python
# Agregar después de los imports existentes
import sys
from pathlib import Path

# Agregar path del core para módulo CFDI
CORE_PATH = Path(__file__).parent / "crm_exo_v2" / "core"
sys.path.insert(0, str(CORE_PATH))

# Import del módulo CFDI
from facturacion.cfdi_emisor import validar_configuracion_cfdi
```

### 2. Agregar opción en el menú principal

Busca la sección donde defines el menú lateral (sidebar) y agrega:

```python
# En la sección de menú
menu_options = [
    "🏠 Dashboard",
    "🏢 Empresas",
    "👤 Contactos",
    "🎯 Prospectos",
    "💰 Oportunidades",
    "📄 Cotizaciones",
    "👥 Clientes",
    "📋 Transacciones",
    "🧾 Facturación",
    "💼 Configuración CFDI",  # ← NUEVO
    "🔍 Trazabilidad",
    "👨‍💼 Usuarios",
    "⚙️ Configuración"
]

menu_seleccionado = st.sidebar.selectbox("Navegar", menu_options)
```

### 3. Agregar la ruta al módulo

Después de los bloques `if menu_seleccionado == ...` existentes, agrega:

```python
# ============================================================
# 💼 CONFIGURACIÓN CFDI
# ============================================================
elif menu_seleccionado == "💼 Configuración CFDI":
    import sys
    from pathlib import Path
    
    # Agregar UI path
    UI_PATH = Path(__file__).parent / "crm_exo_v2" / "ui"
    sys.path.insert(0, str(UI_PATH))
    
    from ui_cfdi_emisor import ui_registro_emisor
    
    # Renderizar interfaz
    ui_registro_emisor()
```

### 4. (Opcional) Agregar widget de estado en Dashboard

En la sección del Dashboard, después de las métricas principales:

```python
if menu_seleccionado == "🏠 Dashboard":
    st.title("📊 Dashboard CRM-EXO v2")
    
    # ... tus métricas existentes ...
    
    # Widget de estado CFDI
    st.divider()
    st.subheader("💼 Estado de Facturación Electrónica")
    
    valido, mensaje = validar_configuracion_cfdi()
    if valido:
        st.success(f"✅ {mensaje}")
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.warning(f"⚠️ {mensaje}")
        with col2:
            if st.button("⚙️ Configurar"):
                st.session_state.menu_activo = "💼 Configuración CFDI"
                st.rerun()
```

## 📝 Ejemplo de Uso Completo

```python
# ================================================================
#  app_crm_exo_v2.py  |  CRM-EXO v2  (Aplicación Principal)
# ================================================================

import streamlit as st
import sqlite3
import hashlib
from datetime import datetime, date
import pandas as pd
from pathlib import Path
from decimal import Decimal
import sys

# Configurar paths
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "crm_exo_v2" / "data" / "crm_exo_v2.sqlite"
CORE_PATH = BASE_DIR / "crm_exo_v2" / "core"
UI_PATH = BASE_DIR / "crm_exo_v2" / "ui"

sys.path.insert(0, str(CORE_PATH))
sys.path.insert(0, str(UI_PATH))

# ... código existente ...

# Configurar Streamlit
st.set_page_config(
    page_title="CRM-EXO v2 - Sistema Completo",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar BD y migraciones
inicializar_db()
aplicar_migraciones()

# ... CSS y menú ...

# ============================================================
# NAVEGACIÓN
# ============================================================
menu_options = [
    "🏠 Dashboard",
    "🏢 Empresas",
    "👤 Contactos",
    "🎯 Prospectos",
    "💰 Oportunidades",
    "📄 Cotizaciones",
    "👥 Clientes",
    "📋 Transacciones",
    "🧾 Facturación",
    "💼 Configuración CFDI",  # ← NUEVO
    "🔍 Trazabilidad",
    "👨‍💼 Usuarios"
]

menu_seleccionado = st.sidebar.selectbox("Navegar", menu_options)

# ... código existente para cada sección ...

# ============================================================
# 💼 CONFIGURACIÓN CFDI (NUEVO)
# ============================================================
elif menu_seleccionado == "💼 Configuración CFDI":
    from ui_cfdi_emisor import ui_registro_emisor
    ui_registro_emisor()
```

## 🔧 Testing del Módulo

### Probar importación

```bash
cd /workspaces/CRM_SynAppsSys
python3 -c "
import sys
sys.path.insert(0, 'crm_exo_v2/core')
from facturacion.cfdi_emisor import validar_configuracion_cfdi
print(validar_configuracion_cfdi())
"
```

### Probar interfaz

```bash
cd /workspaces/CRM_SynAppsSys
streamlit run crm_exo_v2/ui/ui_cfdi_emisor.py
```

## 📦 Verificar Dependencias

```bash
pip install -r requirements.txt
```

## ✅ Checklist de Integración

- [ ] Agregar imports en `app_crm_exo_v2.py`
- [ ] Agregar opción "💼 Configuración CFDI" al menú
- [ ] Agregar bloque `elif` para la ruta
- [ ] (Opcional) Agregar widget de estado en Dashboard
- [ ] Probar navegación al módulo
- [ ] Verificar que las tablas se crean en BD
- [ ] Probar registro de emisor en modo pruebas
- [ ] Verificar eventos en historial_general

## 🎯 Próximos Pasos

1. **Integrar en menú** (5 minutos)
2. **Probar registro** en modo pruebas (10 minutos)
3. **Obtener token** de TimbrarCFDI33 (registro en su sitio)
4. **Descargar CSD** del portal del SAT
5. **Configurar emisor** de prueba
6. **Implementar timbrado** (próximo módulo)

## 📞 Soporte

Si encuentras errores:
1. Verifica los logs en stderr (Streamlit Cloud)
2. Revisa eventos en `historial_general`
3. Consulta README_CFDI.md para troubleshooting
