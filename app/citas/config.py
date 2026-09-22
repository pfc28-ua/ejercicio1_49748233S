"""Políticas del centro para la programación de citas.

Están centralizadas aquí porque son decisiones de negocio que el centro puede
cambiar, no constantes técnicas repartidas por el código (plan.md DT-05).

Trazabilidad: RN-02, RN-06, RN-07, RN-08; tasks.md T-02.
"""

from __future__ import annotations

#: Antelación mínima para reservar una cita, en minutos (RN-06).
ANTELACION_MINIMA_RESERVA_MIN = 60

#: Antelación mínima para cancelar o reprogramar, en horas (RN-07).
ANTELACION_MINIMA_CAMBIO_H = 24

#: Horizonte máximo de reserva, en días (RN-08).
HORIZONTE_RESERVA_DIAS = 180

#: Máximo de días que puede abarcar una consulta de disponibilidad (CL-08).
RANGO_MAXIMO_CONSULTA_DIAS = 60

#: Límites de la duración de los huecos, en minutos (RN-02).
DURACION_MINIMA_MIN = 5
DURACION_MAXIMA_MIN = 120
DURACION_MULTIPLO_MIN = 5
DURACION_POR_DEFECTO_MIN = 20

#: Longitud máxima del motivo de consulta (RN-17).
MOTIVO_CONSULTA_MAXIMO = 300
