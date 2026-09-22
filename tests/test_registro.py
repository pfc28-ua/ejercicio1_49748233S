"""Capacidad A · Registro e identificación — CA-01 a CA-11 (spec.md §6)."""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

from app.models import Paciente
from tests.conftest import DNI_VALIDO, NIE_VALIDO, paciente_ejemplo, registrar


def test_CA_01_el_alta_asigna_una_identidad_unica(cliente, anio):
    respuesta = cliente.post("/api/v1/pacientes", json=paciente_ejemplo())

    assert respuesta.status_code == 201
    ficha = respuesta.json()
    assert uuid.UUID(ficha["patient_id"]).version == 4
    assert re.fullmatch(rf"HC-{anio}-\d{{6}}", ficha["codigo_historia_clinica"])
    assert ficha["nombre"] == "María"
    assert ficha["numero_poliza"] == "POL-998877"


def test_CA_02_codigo_de_historia_secuencial_y_unico(cliente, anio):
    primero = registrar(cliente)
    segundo = registrar(cliente, tipo_documento="NIE", numero_documento=NIE_VALIDO)

    assert primero["codigo_historia_clinica"] == f"HC-{anio}-000001"
    assert segundo["codigo_historia_clinica"] == f"HC-{anio}-000002"


def test_CA_03_el_usuario_no_puede_imponer_la_identidad(cliente):
    datos = paciente_ejemplo(
        patient_id="00000000-0000-4000-8000-000000000000",
        codigo_historia_clinica="HC-1999-000042",
    )
    ficha = cliente.post("/api/v1/pacientes", json=datos).json()

    assert ficha["patient_id"] != "00000000-0000-4000-8000-000000000000"
    assert ficha["codigo_historia_clinica"] != "HC-1999-000042"


def test_CA_04_se_rechaza_el_alta_duplicada(cliente, sesion):
    existente = registrar(cliente)

    respuesta = cliente.post("/api/v1/pacientes", json=paciente_ejemplo(nombre="Otra"))

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "PACIENTE_DUPLICADO"
    assert respuesta.json()["codigo_historia_clinica"] == existente["codigo_historia_clinica"]
    assert sesion.query(Paciente).count() == 1


def test_CA_05_el_documento_se_normaliza_antes_de_comparar(cliente):
    registrar(cliente)

    respuesta = cliente.post("/api/v1/pacientes", json=paciente_ejemplo(numero_documento=" 12345678-z "))

    assert respuesta.status_code == 409


def test_CA_06_se_rechaza_un_dni_con_letra_incorrecta(cliente):
    respuesta = cliente.post("/api/v1/pacientes", json=paciente_ejemplo(numero_documento="12345678A"))

    assert respuesta.status_code == 422
    assert any(d["campo"] == "numero_documento" for d in respuesta.json()["detalles"])


def test_CA_07_se_acepta_un_nie_valido(cliente):
    ficha = registrar(cliente, tipo_documento="NIE", numero_documento=NIE_VALIDO)
    assert ficha["numero_documento"] == NIE_VALIDO


def test_CA_08_se_acepta_un_pasaporte(cliente):
    ficha = registrar(
        cliente, tipo_documento="PASAPORTE", numero_documento="AB123456",
        direccion_pais="Portugal", direccion_cp="1000-001",
    )
    assert ficha["tipo_documento"] == "PASAPORTE"


def test_CA_09_se_rechaza_una_fecha_de_nacimiento_futura(cliente):
    manana = (date.today() + timedelta(days=1)).isoformat()
    respuesta = cliente.post("/api/v1/pacientes", json=paciente_ejemplo(fecha_nacimiento=manana))

    assert respuesta.status_code == 422
    assert any(d["campo"] == "fecha_nacimiento" for d in respuesta.json()["detalles"])


def test_CA_10_se_exige_el_numero_de_seguro_o_mutua(cliente):
    datos = paciente_ejemplo()
    del datos["entidad_aseguradora"], datos["numero_poliza"]

    respuesta = cliente.post("/api/v1/pacientes", json=datos)

    assert respuesta.status_code == 422
    campos = {d["campo"] for d in respuesta.json()["detalles"]}
    assert {"entidad_aseguradora", "numero_poliza"} <= campos


def test_CA_11_todos_los_errores_se_comunican_a_la_vez(cliente):
    manana = (date.today() + timedelta(days=1)).isoformat()
    respuesta = cliente.post(
        "/api/v1/pacientes",
        json=paciente_ejemplo(nombre="", numero_documento="12345678A", fecha_nacimiento=manana),
    )

    assert respuesta.status_code == 422
    campos = {d["campo"] for d in respuesta.json()["detalles"]}
    assert {"nombre", "numero_documento", "fecha_nacimiento"} <= campos


# Casos límite ---------------------------------------------------------------

def test_CL_08_nombre_de_un_caracter(cliente):
    assert cliente.post("/api/v1/pacientes", json=paciente_ejemplo(nombre="A")).status_code == 422


def test_CL_09_nombres_con_tildes_y_apostrofes(cliente):
    ficha = registrar(cliente, nombre="Núria", primer_apellido="D'Angelo-Núñez")
    assert ficha["primer_apellido"] == "D'Angelo-Núñez"


def test_CL_10_sin_datos_de_contacto(cliente):
    ficha = registrar(
        cliente, telefono=None, email=None, direccion_calle=None,
        direccion_ciudad=None, direccion_cp=None, direccion_provincia=None,
    )
    assert ficha["telefono"] is None and ficha["email"] is None


def test_CL_11_codigo_postal_espanol_inexistente(cliente):
    assert cliente.post("/api/v1/pacientes", json=paciente_ejemplo(direccion_cp="99999")).status_code == 422


def test_CL_13_y_CL_14_normalizacion_de_email_y_telefono(cliente):
    ficha = registrar(cliente, email="MARIA@Example.COM", telefono="+34 600-11-22-33")
    assert ficha["email"] == "maria@example.com"
    assert ficha["telefono"] == "+34600112233"
