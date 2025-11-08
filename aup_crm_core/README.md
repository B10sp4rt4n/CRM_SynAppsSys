# SynAppsSys - CRM AUP Core v1.1

Sistema CRM modular basado en el modelo Agente Universal Parametrizable (AUP).

## Descripción
Cada entidad (cliente, producto, oportunidad, factura, evento) se gestiona como un Agente AUP con relaciones vivas y trazabilidad estructurada.

### Características
- Núcleo universal (agentes, relaciones, eventos, historial)
- Registro automático de todas las acciones
- Interfaz Streamlit adaptable
- Base de datos SQLite autogenerable

## Ejecución
```
pip install -r requirements.txt
streamlit run ui/main_app.py
```

## Changelog

### v1.1 (2025-11-08)
- ✅ Se agregaron módulos base funcionales (Clientes, Oportunidades, Productos, Facturación)
- ✅ Se corrigieron rutas absolutas para imports robustos
- ✅ Se añadió creación automática de carpeta `/data`
- ✅ Se mejoró manejo de errores y estabilidad general
- ✅ Ruta de imagen del logo ahora usa Path absoluto

### v1.0
- Versión inicial con núcleo AUP y estructura base

