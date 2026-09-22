"""Capacidad C · Modificación y actualización de datos — CA-17 a CA-26 (spec.md §6)."""

from __future__ import annotations

from tests.conftest import DNI_VALIDO, NIE_VALIDO, registrar


def _modificar(cliente, id_paciente, **datos):
    return cliente.patch(f"/api/v1/pacientes/{id_paciente}", json=datos)


def test_CA_17_modificacion_de_datos_de_contacto(cliente):
    ficha = registrar(cliente)

    respuesta = _modificar(cliente, ficha["patient_id"], telefono="611223344", direccion_calle="Avenida del Parque 12")

    assert respuesta.status_code == 200
    assert respuesta.json()["telefono"] == "611223344"
    assert respuesta.json()["direccion_calle"] == "Avenida del Parque 12"


def test_CA_18_la_actualizacion_es_parcial(cliente):
    ficha = registrar(cliente)

    nueva = _modificar(cliente, ficha["patient_id"], email="nuevo@example.com").json()

    assert nueva["email"] == "nuevo@example.com"
    for campo in ("nombre", "primer_apellido", "telefono", "direccion_calle", "numero_poliza"):
        assert nueva[campo] == ficha[campo]


def test_CA_19_completar_un_dato_vacio(cliente):
    ficha = registrar(cliente, email=None)
    assert ficha["email"] is None

    nueva = _modificar(cliente, ficha["patient_id"], email="LUIS@Example.COM").json()

    assert nueva["email"] == "luis@example.com"


def test_CA_20_vaciar_un_dato_opcional(cliente):
    ficha = registrar(cliente)

    nueva = _modificar(cliente, ficha["patient_id"], segundo_apellido="").json()

    assert nueva["segundo_apellido"] is None


def test_CA_21_modificacion_de_datos_personales(cliente):
    ficha = registrar(cliente)

    nueva = _modificar(cliente, ficha["patient_id"], nombre="Mariana", numero_poliza="POL-111222").json()

    assert nueva["nombre"] == "Mariana"
    assert nueva["numero_poliza"] == "POL-111222"


def test_CA_22_la_identidad_no_cambia(cliente):
    ficha = registrar(cliente)

    nueva = _modificar(
        cliente, ficha["patient_id"], telefono="699887766",
        patient_id="00000000-0000-4000-8000-000000000000", codigo_historia_clinica="HC-1999-000042",
    ).json()

    assert nueva["patient_id"] == ficha["patient_id"]
    assert nueva["codigo_historia_clinica"] == ficha["codigo_historia_clinica"]


def test_CA_23_correccion_del_documento_de_identidad(cliente):
    ficha = registrar(cliente, tipo_documento="NIE", numero_documento=NIE_VALIDO)

    respuesta = _modificar(cliente, ficha["patient_id"], tipo_documento="DNI", numero_documento=DNI_VALIDO)

    assert respuesta.status_code == 200
    assert respuesta.json()["tipo_documento"] == "DNI"
    assert respuesta.json()["numero_documento"] == DNI_VALIDO


def test_CA_24_no_se_puede_usar_el_documento_de_otro_paciente(cliente):
    registrar(cliente)
    paciente_b = registrar(cliente, tipo_documento="NIE", numero_documento=NIE_VALIDO)

    respuesta = _modificar(cliente, paciente_b["patient_id"], tipo_documento="DNI", numero_documento=DNI_VALIDO)

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "PACIENTE_DUPLICADO"
    assert cliente.get(f"/api/v1/pacientes/{paciente_b['patient_id']}").json()["numero_documento"] == NIE_VALIDO


def test_CA_25_se_rechazan_datos_invalidos_al_modificar(cliente):
    ficha = registrar(cliente)

    respuesta = _modificar(cliente, ficha["patient_id"], email="esto-no-es-un-email")

    assert respuesta.status_code == 422
    assert any(d["campo"] == "email" for d in respuesta.json()["detalles"])
    assert cliente.get(f"/api/v1/pacientes/{ficha['patient_id']}").json()["email"] == ficha["email"]


def test_CA_26_modificar_un_paciente_inexistente(cliente):
    respuesta = _modificar(cliente, "11111111-1111-4111-8111-111111111111", telefono="600112233")

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "PACIENTE_NO_ENCONTRADO"


# Casos límite ---------------------------------------------------------------

def test_CL_18_modificacion_sin_datos(cliente):
    ficha = registrar(cliente)
    assert _modificar(cliente, ficha["patient_id"]).status_code == 422


def test_no_se_puede_vaciar_un_dato_obligatorio(cliente):
    """RF-18 solo permite vaciar datos opcionales."""
    ficha = registrar(cliente)
    respuesta = _modificar(cliente, ficha["patient_id"], numero_poliza="")
    assert respuesta.status_code == 422
    assert respuesta.json()["detalles"][0]["campo"] == "numero_poliza"


def test_cambiar_solo_el_numero_valida_con_el_tipo_guardado(cliente):
    """Un DNI nuevo con letra incorrecta se rechaza aunque no se envíe el tipo."""
    ficha = registrar(cliente)
    respuesta = _modificar(cliente, ficha["patient_id"], numero_documento="00000000A")
    assert respuesta.status_code == 422
