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


# --------------------------------------------------------------------------
# Módulo de citas (ejercicio 2)
# --------------------------------------------------------------------------

def _proximo_dia_laborable(dias_minimos: int = 7):
    """Primer día laborable a partir de hoy + `dias_minimos`.

    Las pruebas trabajan siempre sobre fechas futuras, para no chocar con la
    antelación mínima de reserva (RN-06).
    """
    from datetime import timedelta

    dia = date.today() + timedelta(days=dias_minimos)
    while dia.weekday() > 4:
        dia += timedelta(days=1)
    return dia


@pytest.fixture()
def catalogo(sesion):
    """Catálogo de ejemplo: dos centros, dos especialidades y dos especialistas.

    - `dermatologa`: lunes a viernes de 09:00 a 11:00, huecos de 20 minutos.
    - `traumatologo`: los mismos días de 16:00 a 18:00, huecos de 30 minutos.
    """
    from datetime import time

    from app.citas.models import Centro, Especialidad, Especialista, HorarioConsulta

    norte = Centro(nombre="Clínica Norte", ciudad="Alicante")
    sur = Centro(nombre="Centro Médico Sur", ciudad="Elche")
    dermatologia = Especialidad(nombre="Dermatología")
    traumatologia = Especialidad(nombre="Traumatología")
    sesion.add_all([norte, sur, dermatologia, traumatologia])
    sesion.flush()

    dermatologa = Especialista(
        nombre="Elena", apellidos="Ruiz Navarro",
        especialidad_id=dermatologia.id, centro_id=norte.id, duracion_cita_min=20,
    )
    traumatologo = Especialista(
        nombre="Carlos", apellidos="Alonso Prieto",
        especialidad_id=traumatologia.id, centro_id=sur.id, duracion_cita_min=30,
    )
    sesion.add_all([dermatologa, traumatologo])
    sesion.flush()

    for dia in range(5):
        sesion.add(HorarioConsulta(
            especialista_id=dermatologa.id, dia_semana=dia,
            hora_inicio=time(9, 0), hora_fin=time(11, 0),
        ))
        sesion.add(HorarioConsulta(
            especialista_id=traumatologo.id, dia_semana=dia,
            hora_inicio=time(16, 0), hora_fin=time(18, 0),
        ))
    sesion.commit()

    return {
        "centro_norte": norte.id,
        "centro_sur": sur.id,
        "dermatologia": dermatologia.id,
        "traumatologia": traumatologia.id,
        "dermatologa": dermatologa.id,
        "traumatologo": traumatologo.id,
    }


@pytest.fixture()
def servicio_citas(sesion):
    from app.citas.services import ServicioCitas

    return ServicioCitas(sesion)


@pytest.fixture()
def dia_consulta():
    """Día laborable futuro sobre el que trabajan las pruebas."""
    return _proximo_dia_laborable()


def hueco(dia, hora: int, minuto: int = 0):
    """Instante concreto dentro de la agenda, en formato ISO."""
    from datetime import datetime, time

    return datetime.combine(dia, time(hora, minuto))


def reservar_cita(cliente, catalogo, paciente, dia, hora=9, minuto=0, especialista=None):
    """Reserva una cita por la API y devuelve su ficha."""
    respuesta = cliente.post("/api/v1/citas", json={
        "tipo_documento": paciente["tipo_documento"],
        "numero_documento": paciente["numero_documento"],
        "especialista_id": especialista or catalogo["dermatologa"],
        "inicio": hueco(dia, hora, minuto).isoformat(),
    })
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def identificacion(paciente: dict) -> dict:
    """Cuerpo de identificación del paciente para las operaciones sobre sus citas."""
    return {
        "tipo_documento": paciente["tipo_documento"],
        "numero_documento": paciente["numero_documento"],
    }
