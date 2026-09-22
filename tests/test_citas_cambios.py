"""Capacidad B · Cancelar o reprogramar — CA-13 a CA-20 (citas/spec.md §6)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.citas.errors import CitaNoModificable
from app.citas.models import Cita, EstadoCita
from tests.conftest import DNI_VALIDO, hueco, identificacion, registrar, reservar_cita


@pytest.fixture()
def paciente(cliente):
    return registrar(cliente)


def _citas_del_paciente(cliente):
    return cliente.get("/api/v1/citas", params={
        "tipo_documento": "DNI", "numero_documento": DNI_VALIDO
    })


def test_CA_13_consulta_de_las_citas_del_paciente(cliente, catalogo, paciente, dia_consulta, sesion):
    futura = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)

    # Una cita pasada se crea directamente en la base de datos: reservarla por la
    # API sería imposible, porque no se puede reservar en el pasado (RN-06).
    pasada = Cita(
        cita_id="11111111-1111-4111-8111-111111111111",
        codigo="CITA-2020-000001",
        patient_id=paciente["patient_id"],
        especialista_id=catalogo["dermatologa"],
        inicio=datetime.now() - timedelta(days=30),
        duracion_min=20,
        estado=EstadoCita.RESERVADA.value,
    )
    sesion.add(pasada)
    sesion.commit()

    citas = _citas_del_paciente(cliente).json()

    assert len(citas) == 2
    por_codigo = {c["codigo"]: c for c in citas}
    assert por_codigo[futura["codigo"]]["pasada"] is False
    assert por_codigo["CITA-2020-000001"]["pasada"] is True


def test_CA_14_cancelacion(cliente, catalogo, paciente, dia_consulta):
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)

    respuesta = cliente.post(f"/api/v1/citas/{cita['cita_id']}/cancelar", json=identificacion(paciente))

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "CANCELADA"

    # El hueco vuelve a ofrecerse (RF-13).
    huecos = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": dia_consulta.isoformat()},
    ).json()["huecos"]
    assert "09:00" in [h["inicio"][11:16] for h in huecos]


def test_CA_15_reprogramacion(cliente, catalogo, paciente, dia_consulta):
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 20)
    nuevo = hueco(dia_consulta + timedelta(days=2), 10, 0)
    while nuevo.weekday() > 4:
        nuevo += timedelta(days=1)

    respuesta = cliente.post(
        f"/api/v1/citas/{cita['cita_id']}/reprogramar",
        json={"inicio": nuevo.isoformat(), **identificacion(paciente)},
    )

    assert respuesta.status_code == 200
    movida = respuesta.json()
    # Es la misma cita: identificador y código no cambian (RF-12).
    assert movida["cita_id"] == cita["cita_id"]
    assert movida["codigo"] == cita["codigo"]
    assert movida["inicio"][:16] == nuevo.isoformat()[:16]

    # El hueco antiguo vuelve a estar libre y el nuevo ya no lo está.
    libres = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": dia_consulta.isoformat()},
    ).json()["huecos"]
    assert "09:20" in [h["inicio"][11:16] for h in libres]

    ocupados = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": nuevo.date().isoformat(), "hasta": nuevo.date().isoformat()},
    ).json()["huecos"]
    assert "10:00" not in [h["inicio"][11:16] for h in ocupados]


def test_CA_16_no_se_puede_reprogramar_a_un_hueco_ocupado(cliente, catalogo, paciente, dia_consulta):
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)
    registrar(cliente, numero_documento="00000000T", nombre="Juan", primer_apellido="Martín")
    cliente.post("/api/v1/citas", json={
        "tipo_documento": "DNI", "numero_documento": "00000000T",
        "especialista_id": catalogo["dermatologa"],
        "inicio": hueco(dia_consulta, 10, 0).isoformat(),
    })

    respuesta = cliente.post(f"/api/v1/citas/{cita['cita_id']}/reprogramar", json={
        "inicio": hueco(dia_consulta, 10, 0).isoformat(), **identificacion(paciente)
    })

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "HUECO_NO_DISPONIBLE"

    sin_cambios = cliente.get(f"/api/v1/citas/{cita['codigo']}").json()
    assert sin_cambios["inicio"] == cita["inicio"]


def test_CA_17_no_se_puede_cancelar_fuera_de_plazo(servicio_citas, cliente, catalogo, paciente, dia_consulta):
    """RN-07: el instante de referencia se inyecta para no tener que esperar (DT-06)."""
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)
    dos_horas_antes = hueco(dia_consulta, 7, 0)

    with pytest.raises(CitaNoModificable) as error:
        servicio_citas.cancelar(cita["cita_id"], ahora=dos_horas_antes)

    assert "24 horas" in str(error.value)


def test_CA_18_no_se_puede_cancelar_dos_veces(cliente, catalogo, paciente, dia_consulta):
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)
    cliente.post(f"/api/v1/citas/{cita['cita_id']}/cancelar", json=identificacion(paciente))

    respuesta = cliente.post(f"/api/v1/citas/{cita['cita_id']}/cancelar", json=identificacion(paciente))

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "CITA_NO_MODIFICABLE"


def test_CA_19_no_se_puede_modificar_una_cita_pasada(servicio_citas, cliente, catalogo, paciente, dia_consulta):
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)
    despues = hueco(dia_consulta, 12, 0)

    with pytest.raises(CitaNoModificable) as error:
        servicio_citas.cancelar(cita["cita_id"], ahora=despues)

    assert "pasado" in str(error.value)


def test_CA_20_consulta_de_una_cita_por_su_codigo(cliente, catalogo, paciente, dia_consulta):
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)

    respuesta = cliente.get(f"/api/v1/citas/{cita['codigo']}")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["paciente"]["nombre_completo"] == "María López García"
    assert datos["especialista"]["apellidos"] == "Ruiz Navarro"
    assert datos["especialista"]["centro"]["nombre"] == "Clínica Norte"


# Casos límite ---------------------------------------------------------------

def test_CL_12_reprogramar_al_mismo_hueco_no_cambia_nada(cliente, catalogo, paciente, dia_consulta):
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)

    respuesta = cliente.post(f"/api/v1/citas/{cita['cita_id']}/reprogramar", json={
        "inicio": hueco(dia_consulta, 9, 0).isoformat(), **identificacion(paciente)
    })

    assert respuesta.status_code == 200
    assert respuesta.json()["inicio"] == cita["inicio"]


def test_CL_13_no_se_puede_tocar_la_cita_de_otro_paciente(servicio_citas, cliente, catalogo, paciente, dia_consulta):
    from app.citas.errors import CitaNoEncontrada

    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)
    otro = registrar(cliente, numero_documento="00000000T", nombre="Juan", primer_apellido="Martín")

    with pytest.raises(CitaNoEncontrada):
        servicio_citas.cancelar(cita["cita_id"], patient_id=otro["patient_id"])


def test_CL_14_paciente_sin_citas(cliente, catalogo, paciente):
    assert _citas_del_paciente(cliente).json() == []


def test_CL_17_identificador_de_cita_invalido(cliente, catalogo):
    respuesta = cliente.post("/api/v1/citas/no-es-uuid/cancelar",
                             json={"tipo_documento": "DNI", "numero_documento": DNI_VALIDO})
    assert respuesta.status_code == 422


def test_CL_18_codigo_de_cita_con_formato_incorrecto(cliente, catalogo):
    respuesta = cliente.get("/api/v1/citas/2026-1")
    assert respuesta.status_code == 422


def test_cita_inexistente(cliente, catalogo, anio):
    respuesta = cliente.get(f"/api/v1/citas/CITA-{anio}-999999")
    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "CITA_NO_ENCONTRADA"


def test_la_api_no_deja_cancelar_la_cita_de_otro_paciente(cliente, catalogo, paciente, dia_consulta):
    """CL-13 también por API: antes solo lo comprobaba la interfaz web."""
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)
    otro = registrar(cliente, numero_documento="00000000T", nombre="Juan", primer_apellido="Martín")

    respuesta = cliente.post(f"/api/v1/citas/{cita['cita_id']}/cancelar", json=identificacion(otro))

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "CITA_NO_ENCONTRADA"
    assert cliente.get(f"/api/v1/citas/{cita['codigo']}").json()["estado"] == "RESERVADA"


def test_la_api_exige_identificarse_para_cancelar(cliente, catalogo, paciente, dia_consulta):
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)

    respuesta = cliente.post(f"/api/v1/citas/{cita['cita_id']}/cancelar", json={})

    assert respuesta.status_code == 422
    assert respuesta.json()["detalles"][0]["campo"] == "identificacion"
