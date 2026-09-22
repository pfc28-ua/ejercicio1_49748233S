"""Capacidad B · Búsqueda y verificación de identidad — CA-12 a CA-16 (spec.md §6)."""

from __future__ import annotations

from tests.conftest import DNI_VALIDO, registrar


def test_CA_12_busqueda_por_documento_de_identidad(cliente):
    ficha = registrar(cliente)

    respuesta = cliente.get(
        "/api/v1/pacientes/buscar", params={"tipo_documento": "DNI", "numero_documento": DNI_VALIDO}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["patient_id"] == ficha["patient_id"]


def test_CA_13_busqueda_por_codigo_de_historia_clinica(cliente):
    ficha = registrar(cliente)

    respuesta = cliente.get(
        "/api/v1/pacientes/buscar", params={"codigo_historia_clinica": ficha["codigo_historia_clinica"]}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["patient_id"] == ficha["patient_id"]


def test_CA_14_paciente_inexistente(cliente, anio):
    por_documento = cliente.get(
        "/api/v1/pacientes/buscar", params={"tipo_documento": "DNI", "numero_documento": "00000000T"}
    )
    por_codigo = cliente.get(
        "/api/v1/pacientes/buscar", params={"codigo_historia_clinica": f"HC-{anio}-999999"}
    )

    for respuesta in (por_documento, por_codigo):
        assert respuesta.status_code == 404
        assert respuesta.json()["codigo"] == "PACIENTE_NO_ENCONTRADO"


def test_CA_15_la_busqueda_devuelve_los_datos_para_verificar(cliente):
    ficha = registrar(cliente)

    datos = cliente.get(
        "/api/v1/pacientes/buscar", params={"codigo_historia_clinica": ficha["codigo_historia_clinica"]}
    ).json()

    assert datos["nombre"] == "María"
    assert datos["primer_apellido"] == "López"
    assert datos["segundo_apellido"] == "García"
    assert datos["fecha_nacimiento"] == "1985-03-12"
    assert datos["tipo_documento"] == "DNI"
    assert datos["numero_documento"] == DNI_VALIDO
    assert datos["codigo_historia_clinica"] == ficha["codigo_historia_clinica"]
    assert datos["patient_id"] == ficha["patient_id"]


def test_CA_16_recuperacion_por_identificador_interno(cliente):
    ficha = registrar(cliente)

    respuesta = cliente.get(f"/api/v1/pacientes/{ficha['patient_id']}")

    assert respuesta.status_code == 200
    assert respuesta.json()["codigo_historia_clinica"] == ficha["codigo_historia_clinica"]


# Casos límite ---------------------------------------------------------------

def test_CL_01_busqueda_con_documento_sin_normalizar(cliente):
    ficha = registrar(cliente)
    respuesta = cliente.get(
        "/api/v1/pacientes/buscar", params={"tipo_documento": "DNI", "numero_documento": "1234 5678-z"}
    )
    assert respuesta.json()["patient_id"] == ficha["patient_id"]


def test_CL_15_codigo_de_historia_con_formato_incorrecto(cliente):
    respuesta = cliente.get("/api/v1/pacientes/buscar", params={"codigo_historia_clinica": "2026-1"})
    assert respuesta.status_code == 422


def test_CL_16_busqueda_sin_criterio(cliente):
    assert cliente.get("/api/v1/pacientes/buscar").status_code == 422


def test_CL_17_patient_id_que_no_es_uuid(cliente):
    respuesta = cliente.get("/api/v1/pacientes/no-es-un-uuid")
    assert respuesta.status_code == 422
    assert respuesta.json()["detalles"][0]["campo"] == "patient_id"
