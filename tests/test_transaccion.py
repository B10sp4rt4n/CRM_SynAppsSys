"""
Tests para NÚCLEO 2: TRANSACCIÓN - REGLAS R2, R3
Autor: AUP
Fecha: 2025-11-10
Descripción: Validación de REGLAS R2 (Oportunidad desde Prospecto) y R3 (Conversión a Cliente)
"""

import pytest


def test_r2_oportunidad_requiere_prospecto(repos):
    """
    REGLA R2: Una oportunidad debe crearse desde un prospecto válido.
    """
    e, c, p, o = repos["empresa"], repos["contacto"], repos["prospecto"], repos["oportunidad"]
    
    # Crear prospecto válido
    id_empresa = e.crear_empresa(nombre="Empresa Oportunidad")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Carlos", correo="carlos@opp.mx")
    id_prospecto = p.crear_prospecto(id_empresa, id_contacto)
    
    # Crear oportunidad desde prospecto
    id_opp = o.crear_oportunidad(
        id_prospecto=id_prospecto,
        titulo="Venta de Licencias",
        monto=50000
    )
    assert id_opp > 0
    
    # Verificar que la oportunidad se creó correctamente
    oportunidad = o.obtener_por_id(id_opp)
    assert oportunidad is not None
    assert oportunidad["id_prospecto"] == id_prospecto
    assert oportunidad["titulo"] == "Venta de Licencias"
    assert oportunidad["monto"] == 50000
    assert oportunidad["estado"] == "abierta"


def test_r2_oportunidad_prospecto_invalido_falla(repos):
    """
    REGLA R2: Intentar crear oportunidad con prospecto inexistente debe fallar.
    """
    o = repos["oportunidad"]
    
    with pytest.raises(Exception):
        o.crear_oportunidad(
            id_prospecto=99999,  # Prospecto inexistente
            titulo="Oportunidad Inválida",
            monto=10000
        )


def test_r3_conversion_prospecto_a_cliente(repos):
    """
    REGLA R3: Al ganar una oportunidad, el prospecto se convierte en cliente.
    La empresa cambia su tipo_cliente de 'prospecto' a 'cliente'.
    """
    e, c, p, o = repos["empresa"], repos["contacto"], repos["prospecto"], repos["oportunidad"]
    
    # 1. Crear prospecto
    id_empresa = e.crear_empresa(nombre="Prospecto a Convertir", tipo_cliente="prospecto")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Luis", correo="luis@convert.mx")
    id_prospecto = p.crear_prospecto(id_empresa, id_contacto)
    
    # Verificar que es prospecto
    empresa_antes = e.obtener_por_id(id_empresa)
    assert empresa_antes["tipo_cliente"] == "prospecto"
    
    # 2. Crear oportunidad
    id_opp = o.crear_oportunidad(id_prospecto, "Proyecto Estratégico", 100000)
    
    # 3. Marcar oportunidad como ganada (ejecuta R3)
    resultado = o.marcar_ganada_y_convertir(id_opp)
    assert resultado is True
    
    # 4. Verificar conversión a cliente
    empresa_despues = e.obtener_por_id(id_empresa)
    assert empresa_despues["tipo_cliente"] == "cliente"
    
    # 5. Verificar que la oportunidad ahora tiene id_cliente
    oportunidad = o.obtener_por_id(id_opp)
    assert oportunidad["estado"] == "ganada"
    assert oportunidad["id_cliente"] == id_empresa
    
    # 6. Verificar que el prospecto cambió de estado
    prospecto = p.obtener_por_id(id_prospecto)
    assert prospecto["estado"] == "convertido"


def test_r3_flujo_completo_transaccion(repos):
    """
    REGLA R2 + R3: Flujo completo desde prospecto hasta cliente.
    Prospecto → Oportunidad → Ganada → Cliente
    """
    e, c, p, o = repos["empresa"], repos["contacto"], repos["prospecto"], repos["oportunidad"]
    
    # Fase 1: IDENTIDAD (Prospecto)
    id_empresa = e.crear_empresa(nombre="GlobalTech Inc", tipo_cliente="prospecto")
    id_contacto = c.crear_contacto(
        id_empresa=id_empresa,
        nombre="Roberto Sánchez",
        correo="roberto@globaltech.com",
        puesto="CTO"
    )
    id_prospecto = p.crear_prospecto(id_empresa, id_contacto)
    
    # Fase 2: TRANSACCIÓN (Oportunidad)
    id_opp = o.crear_oportunidad(
        id_prospecto=id_prospecto,
        titulo="Migración a Cloud",
        monto=250000,
        probabilidad=75,
        etapa="negociacion"
    )
    
    # Verificar estado inicial
    opp_antes = o.obtener_por_id(id_opp)
    assert opp_antes["estado"] == "abierta"
    assert opp_antes["id_cliente"] is None
    
    # Fase 3: CONVERSIÓN (Ganada)
    o.marcar_ganada_y_convertir(id_opp)
    
    # Verificar conversión completa
    opp_despues = o.obtener_por_id(id_opp)
    assert opp_despues["estado"] == "ganada"
    assert opp_despues["id_cliente"] == id_empresa
    
    empresa_final = e.obtener_por_id(id_empresa)
    assert empresa_final["tipo_cliente"] == "cliente"
    
    prospecto_final = p.obtener_por_id(id_prospecto)
    assert prospecto_final["estado"] == "convertido"


def test_r2_multiples_oportunidades_mismo_prospecto(repos):
    """
    REGLA R2: Un prospecto puede tener múltiples oportunidades activas.
    """
    e, c, p, o = repos["empresa"], repos["contacto"], repos["prospecto"], repos["oportunidad"]
    
    # Crear prospecto
    id_empresa = e.crear_empresa(nombre="Multi Oportunidades SA")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Ana", correo="ana@multi.mx")
    id_prospecto = p.crear_prospecto(id_empresa, id_contacto)
    
    # Crear múltiples oportunidades
    id_opp1 = o.crear_oportunidad(id_prospecto, "Oportunidad 1", 10000)
    id_opp2 = o.crear_oportunidad(id_prospecto, "Oportunidad 2", 20000)
    id_opp3 = o.crear_oportunidad(id_prospecto, "Oportunidad 3", 30000)
    
    assert id_opp1 > 0
    assert id_opp2 > 0
    assert id_opp3 > 0
    assert id_opp1 != id_opp2 != id_opp3


def test_r3_conversion_solo_cuando_ganada(repos):
    """
    REGLA R3: La conversión a cliente solo ocurre cuando se marca como 'ganada'.
    Oportunidades perdidas o cerradas no deben convertir el prospecto.
    """
    e, c, p, o = repos["empresa"], repos["contacto"], repos["prospecto"], repos["oportunidad"]
    
    # Crear prospecto
    id_empresa = e.crear_empresa(nombre="Test No Conversión", tipo_cliente="prospecto")
    id_contacto = c.crear_contacto(id_empresa=id_empresa, nombre="Pedro", correo="pedro@noconv.mx")
    id_prospecto = p.crear_prospecto(id_empresa, id_contacto)
    
    # Crear oportunidad
    id_opp = o.crear_oportunidad(id_prospecto, "Oportunidad Perdida", 15000)
    
    # Marcar como perdida (no debe convertir)
    conn = o.conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE oportunidades 
        SET estado = 'perdida'
        WHERE id_oportunidad = ?
    """, (id_opp,))
    conn.commit()
    
    # Verificar que sigue siendo prospecto
    empresa = e.obtener_por_id(id_empresa)
    assert empresa["tipo_cliente"] == "prospecto"
    
    prospecto = p.obtener_por_id(id_prospecto)
    assert prospecto["estado"] != "convertido"
