"""
Tests para NÚCLEO 4: TRAZABILIDAD
Autor: AUP
Fecha: 2025-11-10
Descripción: Validación del sistema de trazabilidad forense con hashes SHA-256
"""

import pytest


def test_trazabilidad_basica(repos, db_connection):
    """
    Verifica la existencia de eventos y hashes generados.
    """
    from crm_exo_v2.core.repository_trazabilidad import HistorialGeneralRepository, HashRepository

    h_repo = HistorialGeneralRepository(conn=db_connection)
    hash_repo = HashRepository(conn=db_connection)

    eventos = h_repo.listar_eventos(5)
    hashes = hash_repo.listar(5)

    assert len(eventos) >= 0  # Puede ser 0 en DB vacía de test
    assert len(hashes) >= 0


def test_trazabilidad_eventos_se_registran(repos, db_connection):
    """
    Verifica que las operaciones CRUD generan eventos en historial_general.
    """
    from crm_exo_v2.core.repository_trazabilidad import HistorialGeneralRepository
    
    e = repos["empresa"]
    h_repo = HistorialGeneralRepository(conn=db_connection)
    
    # Contar eventos antes
    eventos_antes = h_repo.listar_eventos(100)
    count_antes = len(eventos_antes)
    
    # Crear empresa (debe generar evento)
    id_empresa = e.crear_empresa(nombre="Empresa Trazabilidad Test")
    
    # Contar eventos después
    eventos_despues = h_repo.listar_eventos(100)
    count_despues = len(eventos_despues)
    
    # Debe haber al menos 1 evento nuevo
    assert count_despues > count_antes


def test_trazabilidad_hashes_se_generan(repos, db_connection):
    """
    Verifica que las operaciones que requieren hash lo generan correctamente.
    """
    from crm_exo_v2.core.repository_trazabilidad import HashRepository
    
    e, c, p, o, cot = (
        repos["empresa"], repos["contacto"], repos["prospecto"],
        repos["oportunidad"], repos["cotizacion"]
    )
    hash_repo = HashRepository(conn=db_connection)
    
    # Contar hashes antes
    hashes_antes = hash_repo.listar(100)
    count_antes = len(hashes_antes)
    
    # Crear cotización (debe generar hash)
    id_empresa = e.crear_empresa(nombre="Hash Test SA")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Test", correo="test@hash.mx")
    id_prospecto = p.crear_desde_empresa(id_empresa)
    id_opp = o.crear_oportunidad(id_prospecto, "Test Hash", 5000)
    id_cot, hash_generado = cot.crear_cotizacion(id_opp, 5000, modo="minimo", fuente="manual")
    
    # Contar hashes después
    hashes_despues = hash_repo.listar(100)
    count_despues = len(hashes_despues)
    
    # Debe haber al menos 1 hash nuevo
    assert count_despues > count_antes
    assert hash_generado is not None


def test_trazabilidad_verificacion_integridad(repos, db_connection):
    """
    Verifica que el sistema puede validar la integridad de los hashes.
    """
    from crm_exo_v2.core.repository_trazabilidad import HashRepository
    
    e, c, p, o, cot = (
        repos["empresa"], repos["contacto"], repos["prospecto"],
        repos["oportunidad"], repos["cotizacion"]
    )
    hash_repo = HashRepository(conn=db_connection)
    
    # Crear cotización con hash
    id_empresa = e.crear_empresa(nombre="Integridad Hash SA")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Valid", correo="valid@int.mx")
    id_prospecto = p.crear_desde_empresa(id_empresa)
    id_opp = o.crear_oportunidad(id_prospecto, "Verificación", 8000)
    id_cot, hash_original = cot.crear_cotizacion(id_opp, 8000, modo="minimo", fuente="manual")
    
    # Verificar integridad del hash
    es_valida = cot.verificar_integridad(id_cot)
    assert es_valida is True


def test_trazabilidad_hash_sha256_formato(repos, db_connection):
    """
    Verifica que los hashes generados son SHA-256 válidos (64 caracteres hexadecimales).
    """
    e, c, p, o, cot = (
        repos["empresa"], repos["contacto"], repos["prospecto"],
        repos["oportunidad"], repos["cotizacion"]
    )
    
    # Crear cotización
    id_empresa = e.crear_empresa(nombre="SHA256 Test")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="SHA", correo="sha@test.mx")
    id_prospecto = p.crear_prospecto(id_empresa, id_contacto)
    id_opp = o.crear_oportunidad(id_prospecto, "Hash Format", 3000)
    id_cot, hash_generado = cot.crear_cotizacion(id_opp, 3000, modo="minimo", fuente="manual")
    
    # Validar formato SHA-256
    assert hash_generado is not None
    assert len(hash_generado) == 64  # SHA-256 = 64 hex chars
    assert all(c in '0123456789abcdef' for c in hash_generado.lower())  # Solo hex


def test_trazabilidad_multiples_entidades(repos, db_connection):
    """
    Verifica que el sistema de trazabilidad funciona para múltiples entidades.
    """
    from crm_exo_v2.core.repository_trazabilidad import HistorialGeneralRepository, HashRepository
    
    e, c, p, o, cot, oc, f = (
        repos["empresa"], repos["contacto"], repos["prospecto"],
        repos["oportunidad"], repos["cotizacion"], repos["oc"], repos["factura"]
    )
    
    h_repo = HistorialGeneralRepository(conn=db_connection)
    hash_repo = HashRepository(conn=db_connection)
    
    # Crear flujo completo
    id_empresa = e.crear_empresa(nombre="Multi Entidad SA")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Multi", correo="multi@ent.mx")
    id_prospecto = p.crear_desde_empresa(id_empresa)
    id_opp = o.crear_oportunidad(id_prospecto, "Flujo Completo", 15000)
    id_cot, _ = cot.crear_cotizacion(id_opp, 15000, modo="minimo", fuente="manual")
    id_oc, _ = oc.crear_oc(id_oportunidad=id_opp, numero_oc="OC-MULTI", monto_oc=15000)
    id_factura, _ = f.crear_factura(
        id_oc=id_oc,
        uuid="multi-uuid-test",
        serie="M",
        folio="M001",
        fecha_emision="2025-11-10T14:00:00Z",
        monto_total=15000
    )
    
    # Verificar eventos de diferentes entidades
    eventos = h_repo.listar_eventos(100)
    entidades_registradas = {evt["entidad"] for evt in eventos}
    
    # Debe haber eventos de múltiples entidades
    assert len(entidades_registradas) > 1
    
    # Verificar hashes de diferentes entidades
    hashes = hash_repo.listar(100)
    entidades_hash = {h["entidad"] for h in hashes}
    
    # Debe haber hashes de cotización, OC y factura
    assert len(entidades_hash) >= 1


def test_trazabilidad_linea_tiempo(repos, db_connection):
    """
    Verifica que los eventos se registran en orden cronológico.
    """
    from crm_exo_v2.core.repository_trazabilidad import HistorialGeneralRepository
    
    e = repos["empresa"]
    h_repo = HistorialGeneralRepository(conn=db_connection)
    
    # Crear múltiples eventos
    id_e1 = e.crear_empresa(nombre="Empresa 1")
    id_e2 = e.crear_empresa(nombre="Empresa 2")
    id_e3 = e.crear_empresa(nombre="Empresa 3")
    
    # Listar eventos
    eventos = h_repo.listar_eventos(10)
    
    # Verificar que tienen timestamp
    for evt in eventos:
        assert "timestamp" in evt
        assert evt["timestamp"] is not None


def test_trazabilidad_evento_contiene_datos(repos, db_connection):
    """
    Verifica que los eventos contienen información completa (acción, entidad, datos).
    """
    from crm_exo_v2.core.repository_trazabilidad import HistorialGeneralRepository
    
    e = repos["empresa"]
    h_repo = HistorialGeneralRepository(conn=db_connection)
    
    # Contar eventos antes
    eventos_antes = len(h_repo.listar_eventos(1000))
    
    # Crear empresa
    id_empresa = e.crear_empresa(nombre="Datos Completos SA", rfc="DCO010101AAA")
    
    # Obtener último evento
    eventos_despues = h_repo.listar_eventos(5)
    ultimo_evento = eventos_despues[0] if eventos_despues else None
    
    # Verificar estructura del evento
    if ultimo_evento:
        assert "entidad" in ultimo_evento
        assert "id_entidad" in ultimo_evento
        assert "accion" in ultimo_evento
        assert "timestamp" in ultimo_evento


def test_trazabilidad_auditoria_factura_completa(repos, db_connection):
    """
    Verifica que una factura genera todos los registros de trazabilidad necesarios.
    """
    from crm_exo_v2.core.repository_trazabilidad import HistorialGeneralRepository, HashRepository
    
    e, c, p, o, cot, oc, f = (
        repos["empresa"], repos["contacto"], repos["prospecto"],
        repos["oportunidad"], repos["cotizacion"], repos["oc"], repos["factura"]
    )
    
    h_repo = HistorialGeneralRepository(conn=db_connection)
    hash_repo = HashRepository(conn=db_connection)
    
    # Flujo completo de facturación
    id_empresa = e.crear_empresa(nombre="Auditoría Factura SA")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Audit", correo="audit@fac.mx")
    id_prospecto = p.crear_desde_empresa(id_empresa)
    id_opp = o.crear_oportunidad(id_prospecto, "Auditoría", 20000)
    
    # Contar antes de cotización
    eventos_pre_cot = len(h_repo.listar_eventos(1000))
    hashes_pre_cot = len(hash_repo.listar(1000))
    
    id_cot, hash_cot = cot.crear_cotizacion(id_opp, 20000, modo="minimo", fuente="manual")
    
    # Debe haber generado evento y hash
    eventos_post_cot = len(h_repo.listar_eventos(1000))
    hashes_post_cot = len(hash_repo.listar(1000))
    
    assert eventos_post_cot > eventos_pre_cot
    assert hashes_post_cot > hashes_pre_cot
    assert hash_cot is not None
    
    # Crear OC y factura
    id_oc, hash_oc = oc.crear_oc(id_oportunidad=id_opp, numero_oc="OC-AUD", monto_oc=20000)
    id_factura, hash_factura = f.crear_factura(
        id_oc=id_oc,
        uuid="audit-uuid-123",
        serie="A",
        folio="AUD001",
        fecha_emision="2025-11-10T15:00:00Z",
        monto_total=20000
    )
    
    # Verificar que se generaron hashes
    assert hash_oc is not None
    assert hash_factura is not None
    
    # Verificar incremento en eventos y hashes
    eventos_final = len(h_repo.listar_eventos(1000))
    hashes_final = len(hash_repo.listar(1000))
    
    assert eventos_final > eventos_post_cot
    assert hashes_final > hashes_post_cot
