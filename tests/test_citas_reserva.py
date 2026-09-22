"""Capacidad A · Reservar una cita online — CA-01 a CA-12 (citas/spec.md §6)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.citas.models import Cita
from tests.conftest import DNI_VALIDO, hueco, registrar, reservar_cita


@pytest.fixture()
def paciente(cliente):
    return registrar(cliente)


def test_CA_01_busqueda_de_especialistas_por_especialidad_y_centro(cliente, catalogo):
    todos = cliente.get("/api/v1/especialistas").json()
    assert len(todos) == 2

    filtrados = cliente.get("/api/v1/especialistas", params={
        "especialidad_id": catalogo["dermatologia"], "centro_id": catalogo["centro_norte"]
    }).json()

    assert len(filtrados) == 1
    assert filtrados[0]["id"] == catalogo["dermatologa"]
    assert filtrados[0]["especialidad"]["nombre"] == "Dermatología"
    assert filtrados[0]["centro"]["nombre"] == "Clínica Norte"

    # Una combinación sin especialistas devuelve una lista vacía, no un error.
    vacio = cliente.get("/api/v1/especialistas", params={
        "especialidad_id": catalogo["dermatologia"], "centro_id": catalogo["centro_sur"]
    }).json()
    assert vacio == []


def test_CA_02_consulta_de_disponibilidad(cliente, catalogo, dia_consulta):
    """De 09:00 a 11:00 con huecos de 20 minutos salen seis huecos."""
    respuesta = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": dia_consulta.isoformat()},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["duracion_cita_min"] == 20
    horas = [h["inicio"][11:16] for h in cuerpo["huecos"]]
    assert horas == ["09:00", "09:20", "09:40", "10:00", "10:20", "10:40"]


def test_CA_03_la_disponibilidad_descuenta_las_citas_reservadas(cliente, catalogo, paciente, dia_consulta):
    reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 20)

    huecos = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": dia_consulta.isoformat()},
    ).json()["huecos"]

    horas = [h["inicio"][11:16] for h in huecos]
    assert "09:20" not in horas
    assert "09:00" in horas and "09:40" in horas


def test_CA_04_la_disponibilidad_descuenta_los_bloqueos(cliente, catalogo, dia_consulta):
    cliente.post(f"/api/v1/especialistas/{catalogo['dermatologa']}/bloqueos", json={
        "inicio": hueco(dia_consulta, 10, 0).isoformat(),
        "fin": hueco(dia_consulta, 11, 0).isoformat(),
        "motivo": "FORMACION",
    })

    huecos = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": dia_consulta.isoformat()},
    ).json()["huecos"]

    horas = [h["inicio"][11:16] for h in huecos]
    assert horas == ["09:00", "09:20", "09:40"]


def test_CA_05_reserva_correcta(cliente, catalogo, paciente, dia_consulta):
    respuesta = cliente.post("/api/v1/citas", json={
        "tipo_documento": "DNI",
        "numero_documento": DNI_VALIDO,
        "especialista_id": catalogo["dermatologa"],
        "inicio": hueco(dia_consulta, 9, 40).isoformat(),
        "motivo_consulta": "Revisión de un lunar",
    })

    assert respuesta.status_code == 201
    cita = respuesta.json()
    assert cita["estado"] == "RESERVADA"
    assert cita["codigo"].startswith("CITA-")
    assert cita["duracion_min"] == 20
    assert cita["paciente"]["patient_id"] == paciente["patient_id"]
    assert cita["motivo_consulta"] == "Revisión de un lunar"

    # El hueco deja de ofrecerse.
    huecos = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": dia_consulta.isoformat()},
    ).json()["huecos"]
    assert "09:40" not in [h["inicio"][11:16] for h in huecos]


def test_CA_06_codigo_de_cita_secuencial_y_unico(cliente, catalogo, paciente, dia_consulta):
    primera = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)
    segunda = reservar_cita(cliente, catalogo, paciente, dia_consulta, 10, 0)

    anio = dia_consulta.year
    assert primera["codigo"] == f"CITA-{anio}-000001"
    assert segunda["codigo"] == f"CITA-{anio}-000002"


def test_CA_07_no_se_puede_reservar_un_hueco_ocupado(cliente, catalogo, paciente, dia_consulta, sesion):
    reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)
    otro = registrar(cliente, numero_documento="00000000T", nombre="Juan", primer_apellido="Martín")

    respuesta = cliente.post("/api/v1/citas", json={
        "tipo_documento": "DNI",
        "numero_documento": "00000000T",
        "especialista_id": catalogo["dermatologa"],
        "inicio": hueco(dia_consulta, 9, 0).isoformat(),
    })

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "HUECO_NO_DISPONIBLE"
    assert sesion.query(Cita).count() == 1


def test_CA_08_no_se_puede_reservar_sobre_un_bloqueo(cliente, catalogo, paciente, dia_consulta):
    cliente.post(f"/api/v1/especialistas/{catalogo['dermatologa']}/bloqueos", json={
        "inicio": hueco(dia_consulta, 9, 0).isoformat(),
        "fin": hueco(dia_consulta, 10, 0).isoformat(),
        "motivo": "BAJA",
    })

    respuesta = cliente.post("/api/v1/citas", json={
        "tipo_documento": "DNI", "numero_documento": DNI_VALIDO,
        "especialista_id": catalogo["dermatologa"],
        "inicio": hueco(dia_consulta, 9, 20).isoformat(),
    })

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "HUECO_NO_DISPONIBLE"


def test_CA_09_no_se_puede_reservar_fuera_del_horario(cliente, catalogo, paciente, dia_consulta):
    respuesta = cliente.post("/api/v1/citas", json={
        "tipo_documento": "DNI", "numero_documento": DNI_VALIDO,
        "especialista_id": catalogo["dermatologa"],
        "inicio": hueco(dia_consulta, 17, 0).isoformat(),  # la dermatóloga no pasa consulta
    })

    assert respuesta.status_code == 409
    assert respuesta.json()["motivo"] == "FUERA_DE_HORARIO"


def test_CA_10_no_se_puede_reservar_en_el_pasado(cliente, catalogo, paciente):
    from datetime import date, timedelta

    ayer = date.today() - timedelta(days=7)
    while ayer.weekday() > 4:
        ayer -= timedelta(days=1)

    respuesta = cliente.post("/api/v1/citas", json={
        "tipo_documento": "DNI", "numero_documento": DNI_VALIDO,
        "especialista_id": catalogo["dermatologa"],
        "inicio": hueco(ayer, 9, 0).isoformat(),
    })

    assert respuesta.status_code == 422
    assert any("antelación" in d["mensaje"] for d in respuesta.json()["detalles"])


def test_CA_11_un_paciente_no_puede_tener_dos_citas_solapadas(
    cliente, catalogo, paciente, dia_consulta, servicio_citas
):
    """El traumatólogo pasa consulta por la tarde: se fuerza el solapamiento a mano."""
    primera = reservar_cita(cliente, catalogo, paciente, dia_consulta, 9, 0)

    from app.citas.errors import PacienteYaCitado
    from app.citas.models import Especialista

    # Se da al traumatólogo el mismo horario de mañana para provocar el choque.
    from datetime import time

    from app.citas.models import HorarioConsulta

    servicio_citas.sesion.add(HorarioConsulta(
        especialista_id=catalogo["traumatologo"], dia_semana=dia_consulta.weekday(),
        hora_inicio=time(9, 0), hora_fin=time(11, 0),
    ))
    servicio_citas.sesion.commit()

    with pytest.raises(PacienteYaCitado) as error:
        servicio_citas.reservar(
            patient_id=paciente["patient_id"],
            especialista_id=catalogo["traumatologo"],
            inicio=hueco(dia_consulta, 9, 0),
        )

    assert error.value.codigo_cita == primera["codigo"]


def test_CA_12_solo_se_reservan_citas_para_pacientes_registrados(cliente, catalogo, dia_consulta):
    respuesta = cliente.post("/api/v1/citas", json={
        "tipo_documento": "DNI", "numero_documento": "00000000T",
        "especialista_id": catalogo["dermatologa"],
        "inicio": hueco(dia_consulta, 9, 0).isoformat(),
    })

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "PACIENTE_NO_ENCONTRADO"


# Casos límite ---------------------------------------------------------------

def test_CL_07_rango_de_fechas_invertido(cliente, catalogo, dia_consulta):
    respuesta = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": (dia_consulta - timedelta(days=3)).isoformat()},
    )
    assert respuesta.status_code == 422


def test_CL_08_rango_de_fechas_excesivo(cliente, catalogo, dia_consulta):
    respuesta = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": (dia_consulta + timedelta(days=90)).isoformat()},
    )
    assert respuesta.status_code == 422


def test_CL_11_cita_mas_alla_del_horizonte(cliente, catalogo, paciente):
    from datetime import date, timedelta

    lejos = date.today() + timedelta(days=200)
    while lejos.weekday() > 4:
        lejos += timedelta(days=1)

    respuesta = cliente.post("/api/v1/citas", json={
        "tipo_documento": "DNI", "numero_documento": DNI_VALIDO,
        "especialista_id": catalogo["dermatologa"],
        "inicio": hueco(lejos, 9, 0).isoformat(),
    })
    assert respuesta.status_code == 422


def test_especialista_inexistente(cliente, catalogo):
    respuesta = cliente.get("/api/v1/especialistas/999/disponibilidad")
    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "ESPECIALISTA_NO_ENCONTRADO"


def test_CA_32_busqueda_acotada_a_la_disponibilidad_horaria_del_paciente(
    cliente, catalogo, dia_consulta
):
    """CA-32: el paciente solo puede por la tarde (enunciado §3.1)."""
    manana = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": dia_consulta.isoformat(),
                "hora_desde": "00:00", "hora_hasta": "14:00"},
    ).json()["huecos"]
    assert len(manana) == 6

    tarde = cliente.get(
        f"/api/v1/especialistas/{catalogo['dermatologa']}/disponibilidad",
        params={"desde": dia_consulta.isoformat(), "hasta": dia_consulta.isoformat(),
                "hora_desde": "14:00", "hora_hasta": "23:59"},
    ).json()["huecos"]
    assert tarde == []  # la dermatóloga solo pasa consulta por la mañana


def test_CA_32_la_franja_horaria_tambien_en_la_interfaz_web(cliente, catalogo, paciente, dia_consulta):
    pagina = cliente.get("/citas/buscar", params={
        "b": DNI_VALIDO, "especialista_id": catalogo["dermatologa"],
        "desde": dia_consulta.isoformat(), "franja": "TARDE",
    })
    assert "Solo por la tarde" in pagina.text
    assert "en esa franja horaria" in pagina.text
