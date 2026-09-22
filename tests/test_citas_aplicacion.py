"""Aplicación e integración con el ejercicio 1 — CA-28 a CA-31 (citas/spec.md §6)."""

from __future__ import annotations

import pytest

from app.citas.models import Cita
from tests.conftest import DNI_VALIDO, hueco, registrar, reservar_cita


@pytest.fixture()
def paciente(cliente):
    return registrar(cliente)


def test_CA_28_las_citas_reutilizan_la_identidad_del_paciente(
    cliente, catalogo, paciente, dia_consulta, sesion
):
    """La cita guarda el `patient_id` y no copia los datos personales (RF-26)."""
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)

    # La respuesta trae la identidad del paciente, resuelta desde el ejercicio 1.
    assert cita["paciente"]["patient_id"] == paciente["patient_id"]
    assert cita["paciente"]["codigo_historia_clinica"] == paciente["codigo_historia_clinica"]
    assert cita["paciente"]["nombre_completo"] == "María López García"

    # Pero en la tabla de citas solo está la referencia: ni nombre, ni documento,
    # ni datos de contacto duplicados.
    fila = sesion.get(Cita, cita["cita_id"])
    columnas = {c.name for c in Cita.__table__.columns}
    assert "patient_id" in columnas
    assert columnas.isdisjoint({"nombre", "primer_apellido", "numero_documento", "email", "telefono"})
    assert fila.patient_id == paciente["patient_id"]


def test_CA_28_al_cambiar_los_datos_del_paciente_la_cita_los_refleja(
    cliente, catalogo, paciente, dia_consulta
):
    """Consecuencia de no duplicar: la cita siempre muestra el dato vigente."""
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)

    cliente.patch(f"/api/v1/pacientes/{paciente['patient_id']}", json={"nombre": "Mariana"})

    assert cliente.get(f"/api/v1/citas/{cita['codigo']}").json()["paciente"][
        "nombre_completo"
    ] == "Mariana López García"


def test_CA_29_formato_uniforme_de_error(cliente, catalogo, paciente, dia_consulta):
    """Los errores del módulo de citas tienen la misma forma que los del ejercicio 1."""
    reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)
    registrar(cliente, numero_documento="00000000T", nombre="Juan", primer_apellido="Martín")

    conflicto = cliente.post("/api/v1/citas", json={
        "tipo_documento": "DNI", "numero_documento": "00000000T",
        "especialista_id": catalogo["dermatologa"],
        "inicio": hueco(dia_consulta, 9, 0).isoformat(),
    }).json()
    assert conflicto["codigo"] == "HUECO_NO_DISPONIBLE"
    assert conflicto["mensaje"]

    no_encontrado = cliente.get("/api/v1/especialistas/999/agenda").json()
    assert no_encontrado["codigo"] == "ESPECIALISTA_NO_ENCONTRADO"

    validacion = cliente.patch(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/duracion", json={"duracion_cita_min": 7}
    ).json()
    assert validacion["codigo"] == "VALIDACION"
    assert all({"campo", "mensaje"} <= set(d) for d in validacion["detalles"])


def test_CA_30_interfaz_web_del_paciente(cliente, catalogo, paciente, dia_consulta):
    """Identificarse, buscar, reservar, reprogramar y cancelar desde la web."""
    # 1. Identificarse lleva a "Mis citas".
    entrada = cliente.get("/citas", params={"b": DNI_VALIDO}, follow_redirects=False)
    assert entrada.status_code == 303
    assert entrada.headers["location"] == f"/citas/mias?b={DNI_VALIDO}"

    mias = cliente.get("/citas/mias", params={"b": DNI_VALIDO})
    assert "María López García" in mias.text
    assert "No tienes citas próximas" in mias.text

    # 2. Buscar disponibilidad muestra los huecos del especialista.
    busqueda = cliente.get("/citas/buscar", params={
        "b": DNI_VALIDO, "especialista_id": catalogo["dermatologa"], "desde": dia_consulta.isoformat()
    })
    assert "Ruiz Navarro" in busqueda.text
    assert "09:00" in busqueda.text

    # 3. Reservar.
    reserva = cliente.post("/citas/reservar", data={
        "b": DNI_VALIDO,
        "especialista_id": catalogo["dermatologa"],
        "inicio": hueco(dia_consulta, 9, 0).isoformat(),
        "motivo_consulta": "Revisión",
    }, follow_redirects=False)
    assert reserva.status_code == 303
    assert "nueva=CITA-" in reserva.headers["location"]

    # Se sigue la redirección, que lleva a "Mis citas" con la confirmación.
    ficha = cliente.get(reserva.headers["location"]).text
    assert "Cita confirmada" in ficha
    assert "Dermatología" in ficha

    cita_id = cliente.get("/api/v1/citas", params={
        "tipo_documento": "DNI", "numero_documento": DNI_VALIDO
    }).json()[0]["cita_id"]

    # 4. Reprogramar desde la web.
    reprogramada = cliente.post(f"/citas/{cita_id}/reprogramar", data={
        "b": DNI_VALIDO, "inicio": hueco(dia_consulta, 10, 20).isoformat()
    }, follow_redirects=False)
    assert reprogramada.status_code == 303
    assert "reprogramada" in reprogramada.headers["location"]

    # 5. Cancelar desde la web.
    cancelada = cliente.post(
        f"/citas/{cita_id}/cancelar", data={"b": DNI_VALIDO}, follow_redirects=False
    )
    assert cancelada.status_code == 303
    assert "cancelada" in cancelada.headers["location"].lower()


def test_CA_30_interfaz_web_de_la_agenda(cliente, catalogo, dia_consulta):
    """Bloquear una franja y ajustar la duración desde la zona administrativa."""
    lista = cliente.get("/agenda")
    assert "Ruiz Navarro" in lista.text

    agenda = cliente.get(f"/agenda/{catalogo['dermatologa']}")
    assert "Horario de consulta" in agenda.text
    assert "Bloquear una franja" in agenda.text

    bloqueo = cliente.post(f"/agenda/{catalogo['dermatologa']}/bloqueos", data={
        "inicio": hueco(dia_consulta, 9, 0).isoformat(),
        "fin": hueco(dia_consulta, 11, 0).isoformat(),
        "motivo": "VACACIONES",
        "observaciones": "",
    }, follow_redirects=False)
    assert bloqueo.status_code == 303
    assert "aviso" in bloqueo.headers["location"]

    duracion = cliente.post(
        f"/agenda/{catalogo['dermatologa']}/duracion",
        data={"duracion_cita_min": 30},
        follow_redirects=False,
    )
    assert duracion.status_code == 303
    assert "30" in cliente.get(f"/agenda/{catalogo['dermatologa']}").text


def test_CA_30_la_web_avisa_si_no_puede_bloquear(cliente, catalogo, paciente, dia_consulta):
    reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 20)

    respuesta = cliente.post(f"/agenda/{catalogo['dermatologa']}/bloqueos", data={
        "inicio": hueco(dia_consulta, 9, 0).isoformat(),
        "fin": hueco(dia_consulta, 11, 0).isoformat(),
        "motivo": "BAJA",
        "observaciones": "",
    }, follow_redirects=False)

    assert "error" in respuesta.headers["location"]
    assert "cita" in respuesta.headers["location"].lower()


def test_CA_31_api_rest_documentada(cliente):
    rutas = cliente.get("/openapi.json").json()["paths"]

    assert "get" in rutas["/api/v1/especialistas"]
    assert "get" in rutas["/api/v1/especialistas/{especialista_id}/disponibilidad"]
    assert "post" in rutas["/api/v1/citas"]
    assert "post" in rutas["/api/v1/citas/{cita_id}/cancelar"]
    assert "post" in rutas["/api/v1/citas/{cita_id}/reprogramar"]
    assert "get" in rutas["/api/v1/especialistas/{especialista_id}/agenda"]
    assert "post" in rutas["/api/v1/especialistas/{especialista_id}/bloqueos"]
    assert "patch" in rutas["/api/v1/especialistas/{especialista_id}/duracion"]

    # Y las del ejercicio 1 siguen ahí: el proyecto se ha ampliado, no sustituido.
    assert "post" in rutas["/api/v1/pacientes"]
    assert "get" in rutas["/api/v1/pacientes/buscar"]
