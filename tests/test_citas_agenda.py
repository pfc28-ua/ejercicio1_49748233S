"""Pruebas unitarias del cálculo de disponibilidad.

Sin base de datos ni HTTP: solo el dominio (citas/plan.md §5 y §9,
tasks.md T-16).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from app.citas.agenda import (
    FUERA_DE_HORIZONTE,
    OCUPADO,
    SIN_ANTELACION,
    Hueco,
    Intervalo,
    calcular_disponibilidad,
    duracion_valida,
    generar_huecos_de_tramo,
    hueco_reservable,
    pertenece_al_horario,
)

DIA = date(2026, 10, 5)  # lunes
AHORA = datetime(2026, 10, 1, 8, 0)


# Generación de huecos (RN-03) ----------------------------------------------

def test_los_huecos_encadenan_la_duracion():
    huecos = generar_huecos_de_tramo(DIA, time(9, 0), time(11, 0), 20)
    assert [h.inicio.strftime("%H:%M") for h in huecos] == [
        "09:00", "09:20", "09:40", "10:00", "10:20", "10:40"
    ]


def test_solo_se_ofrecen_los_huecos_que_caben_enteros():
    """CL-02: de 09:00 a 10:00 con huecos de 45 minutos solo cabe uno."""
    huecos = generar_huecos_de_tramo(DIA, time(9, 0), time(10, 0), 45)
    assert len(huecos) == 1
    assert huecos[0].inicio.strftime("%H:%M") == "09:00"


def test_tramo_sin_espacio_no_genera_huecos():
    assert generar_huecos_de_tramo(DIA, time(9, 0), time(9, 10), 20) == []


# Solapamiento (DT-02) -------------------------------------------------------

@pytest.mark.parametrize(
    "inicio_b,fin_b,esperado",
    [
        ((9, 30), (9, 50), True),    # dentro
        ((8, 50), (9, 10), True),    # pisa el principio
        ((9, 50), (10, 30), True),   # pisa el final
        ((10, 0), (10, 30), False),  # justo después
        ((8, 0), (9, 0), False),     # justo antes
    ],
)
def test_solapamiento_por_intervalos(inicio_b, fin_b, esperado):
    a = Intervalo(datetime.combine(DIA, time(9, 0)), datetime.combine(DIA, time(10, 0)))
    b = Intervalo(datetime.combine(DIA, time(*inicio_b)), datetime.combine(DIA, time(*fin_b)))
    assert a.solapa(b) is esperado
    assert b.solapa(a) is esperado


# Filtrado de huecos (RN-13) -------------------------------------------------

def test_un_hueco_ocupado_no_es_reservable():
    h = Hueco(datetime.combine(DIA, time(9, 0)), 20)
    ocupado = Intervalo(datetime.combine(DIA, time(9, 10)), datetime.combine(DIA, time(9, 30)))
    reservable, motivo = hueco_reservable(h, [ocupado], AHORA)
    assert not reservable
    assert motivo == OCUPADO


def test_no_se_puede_reservar_sin_la_antelacion_minima():
    """RN-06."""
    h = Hueco(AHORA + timedelta(minutes=30), 20)
    reservable, motivo = hueco_reservable(h, [], AHORA)
    assert not reservable
    assert motivo == SIN_ANTELACION


def test_no_se_puede_reservar_mas_alla_del_horizonte():
    """RN-08, CL-11."""
    h = Hueco(AHORA + timedelta(days=200), 20)
    reservable, motivo = hueco_reservable(h, [], AHORA)
    assert not reservable
    assert motivo == FUERA_DE_HORIZONTE


def test_hueco_justo_en_el_limite_de_antelacion():
    """CL-09: con exactamente una hora por delante, se acepta."""
    h = Hueco(AHORA + timedelta(minutes=60), 20)
    assert hueco_reservable(h, [], AHORA)[0]


# Disponibilidad de un rango -------------------------------------------------

def test_disponibilidad_de_varios_dias():
    horarios = {0: [(time(9, 0), time(10, 0))], 2: [(time(9, 0), time(10, 0))]}
    huecos = calcular_disponibilidad(DIA, DIA + timedelta(days=6), horarios, 30, [], AHORA)
    dias = {h.inicio.date() for h in huecos}
    assert dias == {DIA, DIA + timedelta(days=2)}
    assert len(huecos) == 4


def test_dia_sin_horario_no_aporta_huecos():
    """CL-06."""
    huecos = calcular_disponibilidad(DIA, DIA, {}, 20, [], AHORA)
    assert huecos == []


def test_los_huecos_salen_ordenados():
    horarios = {0: [(time(12, 0), time(13, 0)), (time(9, 0), time(10, 0))]}
    huecos = calcular_disponibilidad(DIA, DIA, horarios, 30, [], AHORA)
    assert [h.inicio for h in huecos] == sorted(h.inicio for h in huecos)


# Pertenencia al horario (RF-07) --------------------------------------------

def test_solo_pertenece_al_horario_un_hueco_generado():
    horarios = {0: [(time(9, 0), time(10, 0))]}
    assert pertenece_al_horario(datetime.combine(DIA, time(9, 20)), 20, horarios)
    # Una hora "a mano" que no coincide con ningún hueco generado.
    assert not pertenece_al_horario(datetime.combine(DIA, time(9, 25)), 20, horarios)
    # Fuera del horario de consulta.
    assert not pertenece_al_horario(datetime.combine(DIA, time(17, 0)), 20, horarios)


# Duración (RN-02) -----------------------------------------------------------

@pytest.mark.parametrize("minutos,valida", [(5, True), (20, True), (120, True), (7, False), (0, False), (300, False)])
def test_validacion_de_la_duracion(minutos, valida):
    assert duracion_valida(minutos)[0] is valida


# El reloj del módulo (RN-06, RN-07) ----------------------------------------

def test_el_modulo_usa_la_hora_local_del_centro():
    """Las citas se acuerdan en hora local; comparar con UTC adelantaba el reloj.

    Con UTC, en España el sistema llegaba a aceptar la reserva de un hueco que
    ya había empezado.
    """
    from app.citas.reloj import ahora as ahora_local

    assert abs((ahora_local() - datetime.now()).total_seconds()) < 5


def test_un_hueco_que_ya_ha_empezado_no_es_reservable_con_el_reloj_real():
    """RN-06 comprobado contra la hora real, no contra una fecha de laboratorio."""
    from app.citas.reloj import ahora as ahora_local

    ahora = ahora_local()
    h = Hueco(ahora - timedelta(minutes=10), 20)
    reservable, motivo = hueco_reservable(h, [], ahora)
    assert not reservable
    assert motivo == SIN_ANTELACION


# Franja horaria del paciente (enunciado §3.1) -------------------------------

def test_la_disponibilidad_se_puede_acotar_a_una_franja_horaria():
    horarios = {0: [(time(9, 0), time(11, 0)), (time(16, 0), time(18, 0))]}

    manana = calcular_disponibilidad(
        DIA, DIA, horarios, 30, [], AHORA, hora_desde=time(0, 0), hora_hasta=time(14, 0)
    )
    tarde = calcular_disponibilidad(
        DIA, DIA, horarios, 30, [], AHORA, hora_desde=time(14, 0), hora_hasta=time(23, 59)
    )

    assert [h.inicio.strftime("%H:%M") for h in manana] == ["09:00", "09:30", "10:00", "10:30"]
    assert [h.inicio.strftime("%H:%M") for h in tarde] == ["16:00", "16:30", "17:00", "17:30"]


def test_la_franja_excluye_los_huecos_que_terminan_fuera_de_ella():
    """Un hueco que empieza dentro pero acaba fuera no se ofrece."""
    horarios = {0: [(time(13, 30), time(15, 0))]}
    huecos = calcular_disponibilidad(
        DIA, DIA, horarios, 30, [], AHORA, hora_desde=time(0, 0), hora_hasta=time(14, 0)
    )
    assert [h.inicio.strftime("%H:%M") for h in huecos] == ["13:30"]
