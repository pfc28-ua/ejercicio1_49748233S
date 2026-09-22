"""Requisitos de la aplicación — CA-27 a CA-29 (spec.md §6)."""

from __future__ import annotations

from tests.conftest import DNI_VALIDO, paciente_ejemplo, registrar


def test_CA_27_formato_uniforme_de_error(cliente):
    validacion = cliente.post("/api/v1/pacientes", json=paciente_ejemplo(numero_documento="12345678A")).json()
    assert validacion["codigo"] == "VALIDACION"
    assert validacion["mensaje"]
    assert all({"campo", "mensaje"} <= set(d) for d in validacion["detalles"])

    no_encontrado = cliente.get("/api/v1/pacientes/11111111-1111-4111-8111-111111111111").json()
    assert no_encontrado["codigo"] == "PACIENTE_NO_ENCONTRADO"
    assert no_encontrado["mensaje"]

    registrar(cliente)
    duplicado = cliente.post("/api/v1/pacientes", json=paciente_ejemplo()).json()
    assert duplicado["codigo"] == "PACIENTE_DUPLICADO"
    assert duplicado["mensaje"]


def test_CA_28_interfaz_web(cliente):
    # Busca: no existe, y se ofrece registrarlo con el documento ya puesto.
    busqueda = cliente.get("/", params={"b": DNI_VALIDO})
    assert "Registrar paciente nuevo" in busqueda.text
    assert f"numero_documento={DNI_VALIDO}" in busqueda.text

    # Registra.
    alta = cliente.post("/pacientes/nuevo", data=paciente_ejemplo(), follow_redirects=False)
    assert alta.status_code == 303
    url_ficha = alta.headers["location"]
    ficha = cliente.get(url_ficha).text
    assert "Paciente registrado correctamente" in ficha
    assert "María López García" in ficha
    patient_id = url_ficha.split("/pacientes/")[1].split("?")[0]

    # Busca de nuevo, por documento y por código de historia clínica: lleva a la ficha.
    por_documento = cliente.get("/", params={"b": "1234 5678-z"}, follow_redirects=False)
    assert por_documento.headers["location"] == f"/pacientes/{patient_id}"

    codigo = cliente.get(f"/api/v1/pacientes/{patient_id}").json()["codigo_historia_clinica"]
    por_codigo = cliente.get("/", params={"b": codigo.lower()}, follow_redirects=False)
    assert por_codigo.headers["location"] == f"/pacientes/{patient_id}"

    # La ficha muestra los datos para verificar la identidad.
    assert "Verificar identidad" in ficha and "12/03/1985" in ficha

    # Modifica los datos.
    assert cliente.get(f"/pacientes/{patient_id}/editar").status_code == 200
    edicion = cliente.post(
        f"/pacientes/{patient_id}/editar", data=paciente_ejemplo(telefono="644556677"), follow_redirects=False
    )
    assert edicion.status_code == 303
    assert "644556677" in cliente.get(f"/pacientes/{patient_id}").text


def test_CA_28_la_interfaz_web_avisa_del_duplicado(cliente):
    ficha = registrar(cliente)

    respuesta = cliente.post("/pacientes/nuevo", data=paciente_ejemplo())

    assert respuesta.status_code == 409
    assert ficha["codigo_historia_clinica"] in respuesta.text
    assert "Ir a la ficha existente" in respuesta.text


def test_CA_28_la_interfaz_web_muestra_los_errores_por_campo(cliente):
    respuesta = cliente.post("/pacientes/nuevo", data=paciente_ejemplo(numero_documento="12345678A"))

    assert respuesta.status_code == 422
    assert "letra de control" in respuesta.text


def test_CA_29_api_rest_documentada(cliente):
    rutas = cliente.get("/openapi.json").json()["paths"]

    assert "post" in rutas["/api/v1/pacientes"]
    assert "get" in rutas["/api/v1/pacientes/buscar"]
    assert {"get", "patch"} <= set(rutas["/api/v1/pacientes/{patient_id}"])


def test_la_web_marca_los_errores_de_formato_al_modificar(cliente):
    """Un dato con formato imposible debe marcar el campo, no romper la página.

    La interfaz de edición devolvía un error del servidor cuando el fallo lo
    detectaba el contrato (nombre larguísimo, fecha inventada, sexo inexistente)
    en lugar de una regla de negocio.
    """
    ficha = registrar(cliente)
    ruta = f"/pacientes/{ficha['patient_id']}/editar"

    for datos in (
        paciente_ejemplo(nombre="A" * 70),
        paciente_ejemplo(fecha_nacimiento="32/13/2020"),
        paciente_ejemplo(sexo="MARCIANO"),
        paciente_ejemplo(telefono="123"),
    ):
        respuesta = cliente.post(ruta, data=datos)
        assert respuesta.status_code == 422, f"debería marcar el campo: {datos['nombre']}"
        assert "campo-error" in respuesta.text

    # Y el paciente no se ha modificado por el camino.
    assert cliente.get(f"/api/v1/pacientes/{ficha['patient_id']}").json()["nombre"] == "María"


def test_los_errores_de_la_web_son_paginas_y_los_de_la_api_json(cliente):
    """RF-23: mismo error, dos formas según quién pregunte."""
    inexistente = "11111111-1111-4111-8111-111111111111"

    pagina = cliente.get(f"/pacientes/{inexistente}")
    assert pagina.status_code == 404
    assert "text/html" in pagina.headers["content-type"]
    assert "No lo hemos encontrado" in pagina.text
    assert "Buscar un paciente" in pagina.text  # la página ofrece salida

    api = cliente.get(f"/api/v1/pacientes/{inexistente}")
    assert api.status_code == 404
    assert api.json()["codigo"] == "PACIENTE_NO_ENCONTRADO"
