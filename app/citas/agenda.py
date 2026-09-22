"""Cálculo de la disponibilidad de un especialista.

Es el núcleo del módulo: los huecos **no se almacenan**, se calculan a partir
del horario del especialista, su duración de cita, sus bloqueos y sus citas
(plan.md DT-01 y §5). Así es imposible que la disponibilidad ofrecida se
desincronice de la agenda real (RF-21).

Este fichero es dominio puro: no conoce la base de datos ni HTTP, y se prueba de
forma aislada.

Trazabilidad: RF-02, RF-03, RN-03, RN-06, RN-08, RN-13; tasks.md T-11 a T-15.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.citas.config import (
    ANTELACION_MINIMA_RESERVA_MIN,
    DURACION_MAXIMA_MIN,
    DURACION_MINIMA_MIN,
    DURACION_MULTIPLO_MIN,
    HORIZONTE_RESERVA_DIAS,
)


@dataclass(frozen=True)
class Intervalo:
    """Tramo de tiempo con inicio y fin."""

    inicio: datetime
    fin: datetime

    def solapa(self, otro: "Intervalo") -> bool:
        """Indica si dos intervalos se pisan en algún momento.

        Dos tramos se solapan cuando cada uno empieza antes de que acabe el
        otro. Comparar solo la hora de inicio fallaría en cuanto conviven citas
        de distinta duración, que es justo lo que ocurre tras cambiar la
        duración de los huecos (plan.md DT-02, ESC-07, CL-03).
        """
        return self.inicio < otro.fin and otro.inicio < self.fin


@dataclass(frozen=True)
class Hueco:
    """Tramo libre en el que se puede reservar una cita."""

    inicio: datetime
    duracion_min: int

    @property
    def fin(self) -> datetime:
        return self.inicio + timedelta(minutes=self.duracion_min)

    @property
    def intervalo(self) -> Intervalo:
        return Intervalo(self.inicio, self.fin)


def duracion_valida(minutos: int) -> tuple[bool, str]:
    """Comprueba la duración de los huecos de un especialista (RN-02, CL-16)."""
    if minutos < DURACION_MINIMA_MIN or minutos > DURACION_MAXIMA_MIN:
        return False, (
            f"La duración debe estar entre {DURACION_MINIMA_MIN} y {DURACION_MAXIMA_MIN} minutos."
        )
    if minutos % DURACION_MULTIPLO_MIN != 0:
        return False, f"La duración debe ser múltiplo de {DURACION_MULTIPLO_MIN} minutos."
    return True, ""


def generar_huecos_de_tramo(
    dia: date, hora_inicio: time, hora_fin: time, duracion_min: int
) -> list[Hueco]:
    """Encadena huecos dentro de un tramo horario (RN-03).

    Solo se generan los huecos que **caben enteros** en el tramo: con consulta
    de 09:00 a 10:00 y huecos de 45 minutos, solo sale el de las 09:00 (CL-02).
    """
    huecos: list[Hueco] = []
    momento = datetime.combine(dia, hora_inicio)
    limite = datetime.combine(dia, hora_fin)
    paso = timedelta(minutes=duracion_min)

    while momento + paso <= limite:
        huecos.append(Hueco(inicio=momento, duracion_min=duracion_min))
        momento += paso

    return huecos


#: Motivos por los que un hueco no se puede reservar.
#: Son códigos, no mensajes: quien los recibe decide qué error devolver sin
#: tener que interpretar un texto (citas/plan.md DT-09).
SIN_ANTELACION = "SIN_ANTELACION"
FUERA_DE_HORIZONTE = "FUERA_DE_HORIZONTE"
OCUPADO = "OCUPADO"

MENSAJES = {
    SIN_ANTELACION: (
        f"Las citas deben reservarse con al menos {ANTELACION_MINIMA_RESERVA_MIN} "
        "minutos de antelación."
    ),
    FUERA_DE_HORIZONTE: (
        f"No se pueden reservar citas a más de {HORIZONTE_RESERVA_DIAS} días vista."
    ),
    OCUPADO: "Ese hueco ya está ocupado o bloqueado.",
}


def hueco_reservable(
    hueco: Hueco,
    ocupados: list[Intervalo],
    ahora: datetime,
) -> tuple[bool, str | None]:
    """Decide si un hueco puede reservarse y devuelve el motivo si no.

    Aplica RN-13: el hueco debe estar libre de bloqueos y de citas activas,
    cumplir la antelación mínima (RN-06) y caer dentro del horizonte de reserva
    (RN-08). El motivo es uno de los códigos de arriba, o ``None`` si se puede
    reservar.
    """
    if hueco.inicio < ahora + timedelta(minutes=ANTELACION_MINIMA_RESERVA_MIN):
        return False, SIN_ANTELACION

    if hueco.inicio > ahora + timedelta(days=HORIZONTE_RESERVA_DIAS):
        return False, FUERA_DE_HORIZONTE

    for ocupado in ocupados:
        if hueco.intervalo.solapa(ocupado):
            return False, OCUPADO

    return True, None


def calcular_disponibilidad(
    desde: date,
    hasta: date,
    horarios_por_dia: dict[int, list[tuple[time, time]]],
    duracion_min: int,
    ocupados: list[Intervalo],
    ahora: datetime,
    hora_desde: time | None = None,
    hora_hasta: time | None = None,
) -> list[Hueco]:
    """Devuelve los huecos libres del especialista entre dos fechas, inclusive.

    ``horarios_por_dia`` asocia el día de la semana (0 = lunes) con sus tramos de
    consulta. Un día sin tramos simplemente no aporta huecos (CL-06).

    ``hora_desde`` y ``hora_hasta`` acotan la **disponibilidad horaria del
    paciente**: solo se ofrecen los huecos que empiezan dentro de esa franja
    (RF-02, enunciado §3.1). El hueco debe además terminar dentro de ella, para
    no proponer una cita que se sale de la franja pedida.

    Los huecos salen ordenados por fecha y hora (plan.md §5, paso 4).
    """
    disponibles: list[Hueco] = []
    dia = desde

    while dia <= hasta:
        for hora_inicio, hora_fin in horarios_por_dia.get(dia.weekday(), []):
            for hueco in generar_huecos_de_tramo(dia, hora_inicio, hora_fin, duracion_min):
                if hora_desde is not None and hueco.inicio.time() < hora_desde:
                    continue
                if hora_hasta is not None and hueco.fin.time() > hora_hasta:
                    continue
                reservable, _ = hueco_reservable(hueco, ocupados, ahora)
                if reservable:
                    disponibles.append(hueco)
        dia += timedelta(days=1)

    return sorted(disponibles, key=lambda h: h.inicio)


def pertenece_al_horario(
    inicio: datetime, duracion_min: int, horarios_por_dia: dict[int, list[tuple[time, time]]]
) -> bool:
    """Comprueba que un hueco concreto es uno de los que genera el horario.

    Evita que se reserve a una hora arbitraria "a mano": el hueco tiene que
    coincidir exactamente con uno de los generados por el horario del
    especialista (RF-07, CA-09).
    """
    for hora_inicio, hora_fin in horarios_por_dia.get(inicio.weekday(), []):
        for hueco in generar_huecos_de_tramo(inicio.date(), hora_inicio, hora_fin, duracion_min):
            if hueco.inicio == inicio:
                return True
    return False
