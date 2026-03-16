BEGIN;

CREATE OR REPLACE VIEW vw_dashboard_nodos_grafo AS
SELECT
    'entidades_fiscales'::TEXT AS nodo_tipo,
    ef.id_entidad AS nodo_id,
    ef.rfc AS clave_negocio,
    ef.razon_social AS titulo,
    COALESCE(ef.nombre_comercial, ef.tipo_entidad) AS subtitulo,
    CASE WHEN ef.activo = 1 THEN 'activo' ELSE 'inactivo' END AS estado,
    NULL::NUMERIC(18,2) AS monto,
    NULL::TEXT AS moneda,
    ef.creado_en AS fecha_evento,
    ef.creado_en,
    ef.actualizado_en,
    jsonb_build_object(
        'tipo_entidad', ef.tipo_entidad,
        'tipo_persona', ef.tipo_persona,
        'sector', ef.sector,
        'correo_fiscal', ef.correo_fiscal,
        'correo_comercial', ef.correo_comercial
    ) AS payload_json
FROM entidades_fiscales ef

UNION ALL

SELECT
    'prospectos'::TEXT AS nodo_tipo,
    p.id_prospecto AS nodo_id,
    CONCAT('PROS-', p.id_prospecto) AS clave_negocio,
    ef.razon_social AS titulo,
    COALESCE(p.estado, 'sin_estado') AS subtitulo,
    CASE WHEN p.es_cliente = 1 THEN 'convertido' ELSE p.estado END AS estado,
    NULL::NUMERIC(18,2) AS monto,
    NULL::TEXT AS moneda,
    p.creado_en AS fecha_evento,
    p.creado_en,
    p.actualizado_en,
    jsonb_build_object(
        'id_entidad', p.id_entidad,
        'id_contacto', p.id_contacto,
        'origen', p.origen,
        'fuente', p.fuente,
        'es_cliente', p.es_cliente
    ) AS payload_json
FROM prospectos p
JOIN entidades_fiscales ef ON ef.id_entidad = p.id_entidad

UNION ALL

SELECT
    'oportunidades'::TEXT AS nodo_tipo,
    o.id_oportunidad AS nodo_id,
    COALESCE(o.folio_oportunidad, CONCAT('OP-', o.id_oportunidad)) AS clave_negocio,
    o.nombre AS titulo,
    ef.razon_social AS subtitulo,
    CONCAT(o.etapa, ':', o.estado) AS estado,
    o.monto_estimado AS monto,
    o.moneda_estimacion AS moneda,
    COALESCE(o.fecha_estimada_cierre, o.creado_en) AS fecha_evento,
    o.creado_en,
    o.actualizado_en,
    jsonb_build_object(
        'id_entidad', o.id_entidad,
        'id_prospecto', o.id_prospecto,
        'probabilidad', o.probabilidad,
        'oc_recibida', o.oc_recibida,
        'descripcion', o.descripcion
    ) AS payload_json
FROM oportunidades o
JOIN entidades_fiscales ef ON ef.id_entidad = o.id_entidad

UNION ALL

SELECT
    'cotizaciones'::TEXT AS nodo_tipo,
    c.id_cotizacion AS nodo_id,
    c.folio_cotizacion AS clave_negocio,
    c.folio_cotizacion AS titulo,
    o.nombre AS subtitulo,
    c.estado AS estado,
    c.total AS monto,
    c.moneda AS moneda,
    c.fecha_emision AS fecha_evento,
    c.creado_en,
    c.actualizado_en,
    jsonb_build_object(
        'id_oportunidad', c.id_oportunidad,
        'version', c.version,
        'modo', c.modo,
        'fuente', c.fuente,
        'hash_integridad', c.hash_integridad
    ) AS payload_json
FROM cotizaciones c
JOIN oportunidades o ON o.id_oportunidad = c.id_oportunidad

UNION ALL

SELECT
    'ordenes_compra'::TEXT AS nodo_tipo,
    oc.id_oc AS nodo_id,
    oc.numero_oc AS clave_negocio,
    oc.numero_oc AS titulo,
    ef.razon_social AS subtitulo,
    oc.estado AS estado,
    oc.total AS monto,
    oc.moneda AS moneda,
    oc.fecha_oc AS fecha_evento,
    oc.creado_en,
    oc.actualizado_en,
    jsonb_build_object(
        'id_entidad', oc.id_entidad,
        'id_oportunidad', oc.id_oportunidad,
        'archivo_pdf', oc.archivo_pdf,
        'hash_integridad', oc.hash_integridad
    ) AS payload_json
FROM ordenes_compra oc
JOIN entidades_fiscales ef ON ef.id_entidad = oc.id_entidad

UNION ALL

SELECT
    'comprobantes_cfdi'::TEXT AS nodo_tipo,
    c.id_cfdi AS nodo_id,
    c.uuid AS clave_negocio,
    COALESCE(c.serie || c.folio, c.uuid) AS titulo,
    CONCAT(receptor.razon_social, ' / ', c.tipo_comprobante) AS subtitulo,
    c.estado AS estado,
    c.total AS monto,
    c.moneda AS moneda,
    COALESCE(c.fecha_timbrado, c.fecha_emision) AS fecha_evento,
    c.creado_en,
    c.actualizado_en,
    jsonb_build_object(
        'id_emisor', c.id_emisor,
        'id_receptor', c.id_receptor,
        'id_oc', c.id_oc,
        'tipo_comprobante', c.tipo_comprobante,
        'metodo_pago', c.metodo_pago,
        'uso_cfdi', c.uso_cfdi,
        'xml_path', c.xml_path,
        'pdf_path', c.pdf_path,
        'hash_integridad', c.hash_integridad
    ) AS payload_json
FROM comprobantes_cfdi c
JOIN entidades_fiscales receptor ON receptor.id_entidad = c.id_receptor

UNION ALL

SELECT
    'pagos_cfdi'::TEXT AS nodo_tipo,
    p.id_pago AS nodo_id,
    COALESCE(p.folio_pago, CONCAT('PAGO-', p.id_pago)) AS clave_negocio,
    COALESCE(p.folio_pago, CONCAT('PAGO-', p.id_pago)) AS titulo,
    cfdi.uuid AS subtitulo,
    p.estado AS estado,
    p.monto AS monto,
    p.moneda_pago AS moneda,
    p.fecha_pago AS fecha_evento,
    p.creado_en,
    NULL::TIMESTAMPTZ AS actualizado_en,
    jsonb_build_object(
        'id_cfdi', p.id_cfdi,
        'forma_pago', p.forma_pago,
        'num_operacion', p.num_operacion,
        'referencia', p.referencia
    ) AS payload_json
FROM pagos_cfdi p
JOIN comprobantes_cfdi cfdi ON cfdi.id_cfdi = p.id_cfdi;

CREATE OR REPLACE VIEW vw_dashboard_aristas_grafo AS
SELECT
    rg.id_relacion,
    rg.nodo_origen_tipo,
    rg.nodo_origen_id,
    origen.clave_negocio AS origen_clave_negocio,
    origen.titulo AS origen_titulo,
    rg.tipo_relacion,
    rg.nodo_destino_tipo,
    rg.nodo_destino_id,
    destino.clave_negocio AS destino_clave_negocio,
    destino.titulo AS destino_titulo,
    rg.vigente,
    rg.metadata_json,
    rg.creado_en
FROM relaciones_grafo rg
LEFT JOIN vw_dashboard_nodos_grafo origen
    ON origen.nodo_tipo = rg.nodo_origen_tipo
   AND origen.nodo_id = rg.nodo_origen_id
LEFT JOIN vw_dashboard_nodos_grafo destino
    ON destino.nodo_tipo = rg.nodo_destino_tipo
   AND destino.nodo_id = rg.nodo_destino_id;

CREATE OR REPLACE VIEW vw_dashboard_pipeline_comercial AS
SELECT
    o.etapa,
    o.estado,
    COUNT(DISTINCT o.id_oportunidad) AS oportunidades_total,
    COALESCE(SUM(o.monto_estimado), 0)::NUMERIC(18,2) AS monto_pipeline,
    COUNT(DISTINCT c.id_cotizacion) AS cotizaciones_total,
    COUNT(DISTINCT oc.id_oc) AS ordenes_compra_total,
    COUNT(DISTINCT cfdi.id_cfdi) AS cfdi_total,
    AVG(o.probabilidad)::NUMERIC(10,2) AS probabilidad_promedio,
    MIN(o.fecha_estimada_cierre) AS primer_cierre_estimado,
    MAX(o.fecha_estimada_cierre) AS ultimo_cierre_estimado
FROM oportunidades o
LEFT JOIN cotizaciones c ON c.id_oportunidad = o.id_oportunidad
LEFT JOIN ordenes_compra oc ON oc.id_oportunidad = o.id_oportunidad
LEFT JOIN comprobantes_cfdi cfdi ON cfdi.id_oc = oc.id_oc
GROUP BY o.etapa, o.estado
ORDER BY o.etapa, o.estado;

CREATE OR REPLACE VIEW vw_dashboard_cxc_cfdi AS
WITH pagos AS (
    SELECT
        p.id_cfdi,
        COALESCE(SUM(CASE WHEN p.estado <> 'cancelado' THEN p.monto ELSE 0 END), 0)::NUMERIC(18,2) AS total_pagado,
        MAX(CASE WHEN p.estado <> 'cancelado' THEN p.fecha_pago END) AS fecha_ultimo_pago
    FROM pagos_cfdi p
    GROUP BY p.id_cfdi
)
SELECT
    cfdi.id_cfdi,
    cfdi.uuid,
    emisor.rfc AS rfc_emisor,
    emisor.razon_social AS emisor,
    receptor.rfc AS rfc_receptor,
    receptor.razon_social AS receptor,
    cfdi.id_oc,
    oc.numero_oc,
    cfdi.tipo_comprobante,
    cfdi.estado AS estado_cfdi,
    cfdi.moneda,
    cfdi.fecha_emision,
    cfdi.fecha_timbrado,
    cfdi.total::NUMERIC(18,2) AS total_cfdi,
    COALESCE(pagos.total_pagado, 0)::NUMERIC(18,2) AS total_pagado,
    GREATEST(cfdi.total - COALESCE(pagos.total_pagado, 0), 0)::NUMERIC(18,2) AS saldo_pendiente,
    pagos.fecha_ultimo_pago,
    CASE
        WHEN cfdi.estado = 'cancelado' THEN 'cancelado'
        WHEN COALESCE(pagos.total_pagado, 0) >= cfdi.total THEN 'pagado'
        WHEN COALESCE(pagos.total_pagado, 0) > 0 THEN 'parcial'
        WHEN CURRENT_DATE - DATE(cfdi.fecha_emision) > 60 THEN 'vencido_60+'
        WHEN CURRENT_DATE - DATE(cfdi.fecha_emision) > 30 THEN 'vencido_30+'
        ELSE 'vigente'
    END AS estado_cobranza,
    (CURRENT_DATE - DATE(cfdi.fecha_emision)) AS antiguedad_dias
FROM comprobantes_cfdi cfdi
JOIN entidades_fiscales emisor ON emisor.id_entidad = cfdi.id_emisor
JOIN entidades_fiscales receptor ON receptor.id_entidad = cfdi.id_receptor
LEFT JOIN ordenes_compra oc ON oc.id_oc = cfdi.id_oc
LEFT JOIN pagos ON pagos.id_cfdi = cfdi.id_cfdi;

COMMIT;