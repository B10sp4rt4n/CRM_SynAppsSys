"""
Tests para NÚCLEO 1: IDENTIDAD - REGLA R1
Autor: AUP
Fecha: 2025-11-10
Descripción: Validación de REGLA R1 - Un prospecto requiere una empresa y contacto asociado
"""

import pytest


def test_r1_prospecto_sin_empresa_falla(repos):
    """
    REGLA R1: Un prospecto sin empresa debe fallar.
    Valida que la FK id_empresa sea obligatoria.
    """
    p = repos["prospecto"]
    
    with pytest.raises(Exception):
        # Intentar crear prospecto sin empresa (id_empresa inexistente)
        p.crear_prospecto(id_empresa=99999, id_contacto=1)


def test_r1_prospecto_requiere_contacto(repos):
    """
    REGLA R1: Un prospecto debe estar vinculado a un contacto.
    """
    e = repos["empresa"]
    c = repos["contacto"]
    p = repos["prospecto"]
    
    # Crear empresa
    id_empresa = e.crear_empresa(nombre="Empresa Test R1")
    assert id_empresa > 0
    
    # Crear contacto
    id_contacto = c.crear_contacto(
        id_empresa=id_empresa,
        nombre="Juan Pérez",
        correo="juan.perez@test.mx"
    )
    assert id_contacto > 0
    
    # Crear prospecto válido
    id_prospecto = p.crear_prospecto(id_empresa, id_contacto)
    assert id_prospecto > 0
    
    # Verificar que el prospecto se creó correctamente
    prospecto = p.obtener_por_id(id_prospecto)
    assert prospecto is not None
    assert prospecto["id_empresa"] == id_empresa


def test_r1_flujo_completo_identidad(repos):
    """
    REGLA R1: Flujo completo de creación de identidad.
    Empresa → Contacto → Prospecto
    """
    e, c, p = repos["empresa"], repos["contacto"], repos["prospecto"]
    
    # 1. Crear empresa
    id_empresa = e.crear_empresa(
        nombre="Tech Solutions SA",
        rfc="TSO010101AAA",
        direccion="Av. Innovación 123",
        telefono="555-1234"
    )
    assert id_empresa > 0
    
    # 2. Crear contacto principal
    id_contacto = c.crear_contacto(
        id_empresa=id_empresa,
        nombre="María González",
        correo="maria.gonzalez@techsolutions.mx",
        telefono="555-5678",
        puesto="Directora de TI"
    )
    assert id_contacto > 0
    
    # 3. Crear prospecto vinculado
    id_prospecto = p.crear_prospecto(id_empresa, id_contacto)
    assert id_prospecto > 0
    
    # 4. Verificar relaciones
    prospecto = p.obtener_por_id(id_prospecto)
    assert prospecto["id_empresa"] == id_empresa
    assert prospecto["estado"] == "nuevo"
    
    # 5. Verificar que la empresa existe
    empresa = e.obtener_por_id(id_empresa)
    assert empresa["nombre"] == "Tech Solutions SA"
    assert empresa["rfc"] == "TSO010101AAA"
    
    # 6. Verificar que el contacto existe
    contacto = c.obtener_por_id(id_contacto)
    assert contacto["nombre"] == "María González"
    assert contacto["id_empresa"] == id_empresa


def test_r1_empresa_unica_por_prospecto(repos):
    """
    REGLA R1: Un prospecto solo puede tener una empresa asociada (UNIQUE constraint).
    """
    e = repos["empresa"]
    c = repos["contacto"]
    p = repos["prospecto"]
    
    # Crear primera empresa y prospecto
    id_empresa_1 = e.crear_empresa(nombre="Empresa A")
    id_contacto_1 = c.crear_contacto(id_empresa=id_empresa_1, nombre="Ana", correo="ana@a.mx")
    id_prospecto_1 = p.crear_prospecto(id_empresa_1, id_contacto_1)
    assert id_prospecto_1 > 0
    
    # Intentar crear otro prospecto con la misma empresa debe fallar (UNIQUE id_empresa)
    with pytest.raises(Exception):
        p.crear_prospecto(id_empresa_1, id_contacto_1)


def test_r1_contacto_pertenece_a_empresa(repos):
    """
    REGLA R1: Un contacto debe pertenecer a una empresa válida (FK).
    """
    c = repos["contacto"]
    
    # Intentar crear contacto sin empresa válida
    with pytest.raises(Exception):
        c.crear_contacto(
            id_empresa=99999,  # Empresa inexistente
            nombre="Contacto Inválido",
            correo="invalido@test.mx"
        )
