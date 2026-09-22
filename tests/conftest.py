"""Configuración común de las pruebas.

Cada prueba usa una base de datos en memoria nueva, de modo que los códigos de
historia clínica son predecibles (plan.md §7).
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, obtener_sesion
from app.main import app

#: DNI válido: 12345678 % 23 = 14 → letra Z.
DNI_VALIDO = "12345678Z"
#: NIE válido: X1234567 → 01234567 % 23 = 21 → letra L.
NIE_VALIDO = "X1234567L"


@pytest.fixture()
def sesion():
    motor = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True
    )
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=motor)
    Fabrica = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False, future=True)
    with Fabrica() as s:
        yield s
    motor.dispose()


@pytest.fixture()
def cliente(sesion):
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def anio() -> int:
    return date.today().year


def paciente_ejemplo(**cambios) -> dict:
    """Datos de alta válidos, con los cambios indicados."""
    datos = {
        "tipo_documento": "DNI",
        "numero_documento": DNI_VALIDO,
        "nombre": "María",
        "primer_apellido": "López",
        "segundo_apellido": "García",
        "fecha_nacimiento": "1985-03-12",
        "sexo": "MUJER",
        "telefono": "+34 600 11 22 33",
        "email": "maria.lopez@example.com",
        "direccion_calle": "Calle Mayor 3",
        "direccion_ciudad": "Madrid",
        "direccion_cp": "28013",
        "direccion_provincia": "Madrid",
        "direccion_pais": "España",
        "entidad_aseguradora": "Mutua Sanitaria",
        "numero_poliza": "POL-998877",
    }
    datos.update(cambios)
    return {k: v for k, v in datos.items() if v is not None}


def registrar(cliente, **cambios) -> dict:
    """Registra un paciente por la API y devuelve su ficha."""
    respuesta = cliente.post("/api/v1/pacientes", json=paciente_ejemplo(**cambios))
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()
