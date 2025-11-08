# SynAppsSys - CRM AUP Core v1

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
