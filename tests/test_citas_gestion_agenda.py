"""Capacidad C · Gestionar la agenda — CA-21 a CA-27 (citas/spec.md §6)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from tests.conftest import hueco, identificacion, registrar, reservar_cita


@pytest.fixture()
def paciente(cliente):
    return registrar(cliente)


def _bloquear(cliente, especialista_id, inicio, fin, motivo="VACACIONES"):
    return cliente.post(f"/api/v1/especialistas/{especialista_id}/bloqueos", json={
        "inicio": inicio.isoformat(), "fin": fin.isoformat(), "motivo": motivo
    })


def test_CA_21_consulta_de_la_agenda(cliente, catalogo, paciente, dia_consulta):
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)
    _bloquear(cliente, catalogo["dermatologa"], hueco(dia_consulta, 10, 0), hueco(dia_consulta, 11, 0))

    respuesta = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/agenda",
        params={"desde": dia_consulta.isoformat(), "hasta": dia_consulta.isoformat()},
    )

    assert respuesta.status_code == 200
    agenda = respuesta.json()
    assert len(agenda["horarios"]) == 5
    assert len(agenda["bloqueos"]) == 1
    assert [c["codigo"] for c in agenda["citas"]] == [cita["codigo"]]
    assert agenda["citas"][0]["paciente"]["nombre_completo"] == "María López García"


def test_CA_22_bloqueo_de_una_franja(cliente, catalogo, dia_consulta):
    fin = dia_consulta + timedelta(days=3)

    respuesta = _bloquear(cliente, catalogo["dermatologa"], hueco(dia_consulta, 0, 0), hueco(fin, 23, 59))

    assert respuesta.status_code == 201
    assert respuesta.json()["motivo"] == "VACACIONES"

    huecos = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": dia_consulta.isoformat()},
    ).json()["huecos"]
    assert huecos == []


def test_CA_23_no_se_puede_bloquear_sobre_citas_reservadas(cliente, catalogo, paciente, dia_consulta):
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 20)

    respuesta = _bloquear(
        cliente, catalogo["dermatologa"], hueco(dia_consulta, 9, 0), hueco(dia_consulta, 11, 0), "BAJA"
    )

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "FRANJA_CON_CITAS"
    assert cuerpo["citas"] == [cita["codigo"]]

    # No se ha creado el bloqueo.
    agenda = cliente.get(f"/api/v1/especialistas/{catalogo['dermatologa']}/agenda").json()
    assert agenda["bloqueos"] == []


def test_CA_24_levantar_un_bloqueo(cliente, catalogo, dia_consulta):
    bloqueo = _bloquear(
        cliente, catalogo["dermatologa"], hueco(dia_consulta, 9, 0), hueco(dia_consulta, 11, 0)
    ).json()

    respuesta = cliente.delete(f"/api/v1/bloqueos/{bloqueo['id']}")

    assert respuesta.status_code == 204
    huecos = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": dia_consulta.isoformat()},
    ).json()["huecos"]
    assert len(huecos) == 6


def test_CA_25_ajuste_de_la_duracion_de_los_huecos(cliente, catalogo, dia_consulta):
    respuesta = cliente.patch(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/duracion", json={"duracion_cita_min": 30}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["duracion_cita_min"] == 30

    huecos = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": dia_consulta.isoformat()},
    ).json()["huecos"]
    assert [h["inicio"][11:16] for h in huecos] == ["09:00", "09:30", "10:00", "10:30"]


@pytest.mark.parametrize("minutos", [7, 0, 300])
def test_CA_26_la_duracion_debe_ser_valida(cliente, catalogo, minutos):
    respuesta = cliente.patch(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/duracion",
        json={"duracion_cita_min": minutos},
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["detalles"][0]["campo"] == "duracion_cita_min"


def test_CA_27_cambiar_la_duracion_no_altera_las_citas_reservadas(cliente, catalogo, paciente, dia_consulta):
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 20)

    cliente.patch(f"/api/v1/especialistas/{catalogo['dermatologa']}/duracion", json={"duracion_cita_min": 30})

    sin_cambios = cliente.get(f"/api/v1/citas/{cita['codigo']}").json()
    assert sin_cambios["duracion_min"] == 20
    assert sin_cambios["inicio"] == cita["inicio"]


# Casos límite ---------------------------------------------------------------

def test_CL_05_bloqueo_con_fin_anterior_al_inicio(cliente, catalogo, dia_consulta):
    respuesta = _bloquear(
        cliente, catalogo["dermatologa"], hueco(dia_consulta, 11, 0), hueco(dia_consulta, 9, 0)
    )
    assert respuesta.status_code == 422


def test_bloqueo_enteramente_pasado_se_rechaza(cliente, catalogo):
    from datetime import date

    ayer = date.today() - timedelta(days=10)
    respuesta = _bloquear(cliente, catalogo["dermatologa"], hueco(ayer, 9, 0), hueco(ayer, 11, 0))
    assert respuesta.status_code == 422


def test_motivo_de_bloqueo_no_admitido(cliente, catalogo, dia_consulta):
    respuesta = _bloquear(
        cliente, catalogo["dermatologa"], hueco(dia_consulta, 9, 0), hueco(dia_consulta, 11, 0), "SIESTA"
    )
    assert respuesta.status_code == 422


def test_CL_20_un_bloqueo_puede_solapar_una_cita_cancelada(cliente, catalogo, paciente, dia_consulta):
    cita = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 20)
    cliente.post(f"/api/v1/citas/{cita['cita_id']}/cancelar", json=identificacion(paciente))

    respuesta = _bloquear(
        cliente, catalogo["dermatologa"], hueco(dia_consulta, 9, 0), hueco(dia_consulta, 11, 0)
    )

    assert respuesta.status_code == 201


def test_levantar_un_bloqueo_inexistente(cliente, catalogo):
    respuesta = cliente.delete("/api/v1/bloqueos/999")
    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "BLOQUEO_NO_ENCONTRADO"
