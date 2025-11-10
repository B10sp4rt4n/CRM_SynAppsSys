"""
Tests para NÚCLEO 3: FACTURACIÓN - REGLAS R4, R5
Autor: AUP
Fecha: 2025-11-10
Descripción: Validación de REGLAS R4 (Cotización con hash) y R5 (Factura requiere OC)
"""

import pytest


def test_r4_cotizacion_genera_hash(repos):
    """
    REGLA R4: Toda cotización debe generar un hash SHA-256 para integridad.
    """
    e, c, p, o, cot = (
        repos["empresa"], repos["contacto"], repos["prospecto"],
        repos["oportunidad"], repos["cotizacion"]
    )
    
    # Crear flujo hasta oportunidad
    id_empresa = e.crear_empresa(nombre="Cliente Hash")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Julia", correo="julia@hash.mx")
    id_prospecto = p.crear_desde_empresa(id_empresa)
    id_opp = o.crear_oportunidad(id_prospecto, "Venta con Cotización", 25000)
    
    # Crear cotización (debe generar hash)
    id_cotizacion, hash_generado = cot.crear_cotizacion(
        id_oportunidad=id_opp,
        monto_total=25000,
        modo="minimo",
        fuente="manual"
    )
    
    assert id_cotizacion > 0
    assert hash_generado is not None
    assert len(hash_generado) == 64  # SHA-256 produce 64 caracteres hexadecimales
    
    # Verificar que el hash se guardó en la base de datos
    cotizacion = cot.obtener_por_id(id_cotizacion)
    assert cotizacion["hash_cotizacion"] == hash_generado


def test_r4_modos_cotizacion(repos):
    """
    REGLA R4: Validar los tres modos de cotización (minimo, generico, externo).
    """
    e, c, p, o, cot = (
        repos["empresa"], repos["contacto"], repos["prospecto"],
        repos["oportunidad"], repos["cotizacion"]
    )
    
    # Preparar oportunidad
    id_empresa = e.crear_empresa(nombre="Multi Modos SA")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Pedro", correo="pedro@modos.mx")
    id_prospecto = p.crear_desde_empresa(id_empresa)
    id_opp = o.crear_oportunidad(id_prospecto, "Cotización Multi-Modo", 30000)
    
    # Modo 1: Mínimo
    id_cot1, hash1 = cot.crear_cotizacion(id_opp, 30000, modo="minimo", fuente="manual")
    cot1 = cot.obtener_por_id(id_cot1)
    assert cot1["modo"] == "minimo"
    assert hash1 is not None
    
    # Modo 2: Genérico
    id_cot2, hash2 = cot.crear_cotizacion(id_opp, 30000, modo="generico", fuente="plantilla")
    cot2 = cot.obtener_por_id(id_cot2)
    assert cot2["modo"] == "generico"
    assert hash2 is not None
    
    # Modo 3: Externo
    id_cot3, hash3 = cot.crear_cotizacion(id_opp, 30000, modo="externo", fuente="proveedor")
    cot3 = cot.obtener_por_id(id_cot3)
    assert cot3["modo"] == "externo"
    assert hash3 is not None
    
    # Verificar que todos los hashes son únicos
    assert hash1 != hash2 != hash3


def test_r4_verificar_integridad_cotizacion(repos):
    """
    REGLA R4: Verificar integridad del hash de una cotización.
    """
    e, c, p, o, cot = (
        repos["empresa"], repos["contacto"], repos["prospecto"],
        repos["oportunidad"], repos["cotizacion"]
    )
    
    # Crear cotización
    id_empresa = e.crear_empresa(nombre="Integridad SA")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Laura", correo="laura@int.mx")
    id_prospecto = p.crear_desde_empresa(id_empresa)
    id_opp = o.crear_oportunidad(id_prospecto, "Cotización Integridad", 40000)
    id_cot, hash_original = cot.crear_cotizacion(id_opp, 40000, modo="minimo", fuente="manual")
    
    # Verificar integridad
    es_valida = cot.verificar_integridad(id_cot)
    assert es_valida is True


def test_r5_factura_requiere_oc(repos):
    """
    REGLA R5: Una factura SOLO puede emitirse si existe una Orden de Compra.
    """
    e, c, p, o, cot, oc, f = (
        repos["empresa"], repos["contacto"], repos["prospecto"],
        repos["oportunidad"], repos["cotizacion"], repos["oc"], repos["factura"]
    )
    
    # Crear flujo completo hasta OC
    id_empresa = e.crear_empresa(nombre="Cliente Factura")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Miguel", correo="miguel@fac.mx")
    id_prospecto = p.crear_desde_empresa(id_empresa)
    id_opp = o.crear_oportunidad(id_prospecto, "Venta con Factura", 50000)
    id_cot, _ = cot.crear_cotizacion(id_opp, 50000, modo="minimo", fuente="manual")
    
    # Crear Orden de Compra
    id_oc, hash_oc = oc.crear_oc(
        id_oportunidad=id_opp,
        numero_oc="OC-2025-001",
        monto_oc=50000
    )
    assert id_oc > 0
    assert hash_oc is not None
    
    # Crear Factura (debe permitir porque existe OC)
    id_factura, hash_factura = f.crear_factura(
        id_oc=id_oc,
        uuid="550e8400-e29b-41d4-a716-446655440000",
        serie="A",
        folio="001",
        fecha_emision="2025-11-10T10:00:00Z",
        monto_total=50000
    )
    
    assert id_factura > 0
    assert hash_factura is not None
    
    # Verificar que la factura se creó correctamente
    factura = f.obtener_por_id(id_factura)
    assert factura["id_oc"] == id_oc
    assert factura["uuid"] == "550e8400-e29b-41d4-a716-446655440000"
    assert factura["estado"] == "activa"


def test_r5_factura_sin_oc_falla(repos):
    """
    REGLA R5: Intentar crear factura sin OC válida debe fallar.
    """
    f = repos["factura"]
    
    with pytest.raises(Exception):
        f.crear_factura(
            id_oc=99999,  # OC inexistente
            uuid="invalid-uuid",
            serie="X",
            folio="999",
            fecha_emision="2025-11-10T00:00:00Z",
            monto_total=10000
        )


def test_r4_r5_facturacion_completa(repos):
    """
    REGLA R4 + R5: Flujo completo de facturación.
    Cotización (R4) → OC → Factura (R5)
    
    Este es el test solicitado por el usuario.
    """
    e, c, p, o, cot, oc, f = (
        repos["empresa"], repos["contacto"], repos["prospecto"],
        repos["oportunidad"], repos["cotizacion"], repos["oc"], repos["factura"]
    )

    # 1. Crear identidad
    id_empresa = e.crear_empresa(nombre="Cliente A")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Ana", correo="ana@cliente.mx")
    id_prospecto = p.crear_desde_empresa(id_empresa)
    
    # 2. Crear oportunidad
    id_opp = o.crear_oportunidad(id_prospecto, "Licencias ThreatDown", 10000)
    
    # 3. Crear cotización (R4: genera hash)
    id_cot, hash_cot = cot.crear_cotizacion(id_opp, 10000, modo="minimo", fuente="manual")
    assert id_cot > 0
    assert hash_cot is not None
    assert len(hash_cot) == 64  # SHA-256
    
    # 4. Crear Orden de Compra
    id_oc, hash_oc = oc.crear_oc(id_oportunidad=id_opp, numero_oc="OC-001", monto_oc=10000)
    assert id_oc > 0
    assert hash_oc is not None
    
    # 5. Crear Factura (R5: requiere OC)
    id_factura, hash_factura = f.crear_factura(
        id_oc=id_oc,
        uuid="123e4567-e89b-12d3-a456-426614174000",
        serie="A",
        folio="001",
        fecha_emision="2025-11-09T00:00:00Z",
        monto_total=10000
    )
    assert id_factura > 0
    assert hash_factura is not None
    
    # 6. Verificar cadena completa
    cotizacion = cot.obtener_por_id(id_cot)
    assert cotizacion["id_oportunidad"] == id_opp
    assert cotizacion["hash_cotizacion"] == hash_cot
    
    orden_compra = oc.obtener_por_id(id_oc)
    assert orden_compra["id_oportunidad"] == id_opp
    assert orden_compra["numero_oc"] == "OC-001"
    assert orden_compra["hash_oc"] == hash_oc
    
    factura = f.obtener_por_id(id_factura)
    assert factura["id_oc"] == id_oc
    assert factura["uuid"] == "123e4567-e89b-12d3-a456-426614174000"
    assert factura["hash_factura"] == hash_factura
    assert factura["estado"] == "activa"


def test_r4_cotizacion_sin_oportunidad_falla(repos):
    """
    REGLA R4: Una cotización requiere una oportunidad válida.
    """
    cot = repos["cotizacion"]
    
    with pytest.raises(Exception):
        cot.crear_cotizacion(
            id_oportunidad=99999,  # Oportunidad inexistente
            monto_total=10000,
            modo="minimo",
            fuente="manual"
        )


def test_r5_factura_actualiza_estado_oc(repos):
    """
    REGLA R5: Al crear factura, el estado de la OC cambia a 'facturada'.
    """
    e, c, p, o, oc, f = (
        repos["empresa"], repos["contacto"], repos["prospecto"],
        repos["oportunidad"], repos["oc"], repos["factura"]
    )
    
    # Preparar flujo
    id_empresa = e.crear_empresa(nombre="Estado OC Test")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="José", correo="jose@test.mx")
    id_prospecto = p.crear_desde_empresa(id_empresa)
    id_opp = o.crear_oportunidad(id_prospecto, "Test Estado", 20000)
    
    # Crear OC
    id_oc, _ = oc.crear_oc(id_oportunidad=id_opp, numero_oc="OC-TEST", monto_oc=20000)
    
    # Verificar estado inicial
    oc_antes = oc.obtener_por_id(id_oc)
    assert oc_antes["estado"] == "pendiente"
    
    # Crear factura
    f.crear_factura(
        id_oc=id_oc,
        uuid="test-uuid-1234",
        serie="T",
        folio="T001",
        fecha_emision="2025-11-10T12:00:00Z",
        monto_total=20000
    )
    
    # Verificar que OC cambió a 'facturada'
    oc_despues = oc.obtener_por_id(id_oc)
    assert oc_despues["estado"] == "facturada"
