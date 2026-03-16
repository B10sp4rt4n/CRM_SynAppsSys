# Integracion CRM_SynAppsSys -> fradma_dashboard3

Este documento define una estrategia de integracion para conectar este CRM con fradma_dashboard3 sin romper la semantica del grafo canonico.

## Objetivo

Permitir que fradma_dashboard3 consuma datos comerciales, fiscales y de cobranza desde una capa estable de lectura, sin acoplarse a tablas operativas ni reimplementar reglas de negocio.

## Principio rector

La fuente de verdad sigue siendo este repositorio.

- El dominio vive en el esquema canonico.
- Las relaciones viven en relaciones_grafo.
- Las llaves de interoperabilidad son RFC, UUID e id_oc o numero_oc.
- El dashboard externo consume vistas y no escribe directo sobre tablas de negocio.

## Contrato de integracion propuesto

La integracion inicial queda definida por estas vistas PostgreSQL:

- vw_dashboard_nodos_grafo
- vw_dashboard_aristas_grafo
- vw_dashboard_pipeline_comercial
- vw_dashboard_cxc_cfdi

La migracion se encuentra en [db/migrations/002_views_integracion_fradma_dashboard3.sql](db/migrations/002_views_integracion_fradma_dashboard3.sql).

## Que resuelve cada vista

### vw_dashboard_nodos_grafo

Expone una representacion uniforme de nodos para visualizacion, exploracion de red y joins de consumo analitico.

Columnas clave:

- nodo_tipo
- nodo_id
- clave_negocio
- titulo
- subtitulo
- estado
- monto
- moneda
- fecha_evento
- payload_json

Nodos incluidos en la primera fase:

- entidades_fiscales
- prospectos
- oportunidades
- cotizaciones
- ordenes_compra
- comprobantes_cfdi
- pagos_cfdi

### vw_dashboard_aristas_grafo

Expone relaciones explicitas listas para una red o para recorridos semanticos. Se apoya en relaciones_grafo y enriquece con claves y titulos de origen y destino.

Uso recomendado en fradma_dashboard3:

- grafos interactivos
- arboles de trazabilidad
- consultas de navegacion bidireccional

### vw_dashboard_pipeline_comercial

Resume el embudo por etapa y estado, incluyendo cobertura documental aguas abajo.

Metricas principales:

- oportunidades_total
- monto_pipeline
- cotizaciones_total
- ordenes_compra_total
- cfdi_total
- probabilidad_promedio

Uso recomendado en fradma_dashboard3:

- KPIs ejecutivos
- funnel comercial
- seguimiento de conversion operativa a facturacion

### vw_dashboard_cxc_cfdi

Une CFDI, pagos y OC para una vista de cobranza orientada a dashboard.

Metricas principales:

- total_cfdi
- total_pagado
- saldo_pendiente
- estado_cobranza
- antiguedad_dias

Uso recomendado en fradma_dashboard3:

- score de salud CxC
- aging
- semaforos de riesgo
- detalle por cliente o por UUID

## Mapeo conceptual con fradma_dashboard3

Tomando como base la arquitectura observada del repo externo:

- los modulos de main deben consumir datasets ya normalizados
- los helpers de utils deben operar sobre nombres estables de columnas
- la app externa debe concentrarse en visualizacion y analitica, no en reconciliar semantica del CRM

Por eso se recomienda un adaptador de acceso en fradma_dashboard3 con funciones del tipo:

```python
def cargar_nodos_grafo(conn) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM vw_dashboard_nodos_grafo", conn)


def cargar_aristas_grafo(conn) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM vw_dashboard_aristas_grafo WHERE vigente = 1", conn)


def cargar_pipeline(conn) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM vw_dashboard_pipeline_comercial", conn)


def cargar_cxc_cfdi(conn) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM vw_dashboard_cxc_cfdi", conn)
```

## Reglas de integracion

Estas reglas son importantes para no degradar el modelo:

1. fradma_dashboard3 no debe escribir directo en entidades_fiscales, oportunidades, ordenes_compra ni comprobantes_cfdi.
2. Cualquier accion de escritura futura debe pasar por un servicio de aplicacion en este repo.
3. El dashboard no debe redefinir etapas, estados o tipos_relacion por su cuenta.
4. Si el dashboard necesita etiquetas diferentes para UI, debe traducirlas en su propia capa de presentacion.
5. RFC y UUID deben tratarse como llaves de negocio inmutables para integracion.

## Flujo recomendado por fases

### Fase 1: lectura estable

- aplicar migraciones canonicas en PostgreSQL
- aplicar la migracion de vistas de integracion
- conectar fradma_dashboard3 por DATABASE_URL en solo lectura
- validar dashboards de pipeline y CxC

### Fase 2: navegacion de grafo

- renderizar nodos y aristas
- agregar drill-down RFC -> oportunidad -> OC -> CFDI -> pago
- agregar drill-back UUID -> OC -> oportunidad -> entidad

### Fase 3: acciones controladas

- exponer servicios de aplicacion para mutaciones
- registrar eventos_auditoria y hashes_integridad
- refrescar vistas o consultas derivadas

## Conexion sugerida

La conexion a PostgreSQL o Neon ya esta documentada en [docs/CONFIG_POSTGRES_NEON.md](docs/CONFIG_POSTGRES_NEON.md).

Para la app externa, la recomendacion operativa es:

- usar DATABASE_URL desde entorno o secrets
- usar credenciales de solo lectura para dashboards
- evitar que el dashboard conozca tablas internas fuera del contrato

## Consulta minima de validacion

Una vez aplicadas las vistas, estas consultas deben responder:

```sql
SELECT COUNT(*) FROM vw_dashboard_nodos_grafo;
SELECT COUNT(*) FROM vw_dashboard_aristas_grafo WHERE vigente = 1;
SELECT * FROM vw_dashboard_pipeline_comercial ORDER BY monto_pipeline DESC;
SELECT * FROM vw_dashboard_cxc_cfdi ORDER BY saldo_pendiente DESC LIMIT 20;
```

## Decision arquitectonica

La integracion correcta entre ambos repos no es fusionar apps Streamlit. Es estabilizar una capa canonica de lectura sobre el grafo y hacer que fradma_dashboard3 consuma esa capa.