"""El "ahora" del módulo de citas.

Las citas se acuerdan en la **hora local del centro**: cuando un paciente
reserva "el martes a las 09:20", esas son las 09:20 del reloj de la pared de la
consulta. Por eso las reglas de antelación (RN-06, RN-07) tienen que comparar
esas horas con la hora local, no con UTC: si se comparan con UTC, en España el
sistema se adelanta una o dos horas según la estación y llega a aceptar la
reserva de un hueco que ya ha empezado.

Esta función existe para que ese "ahora" esté en un único sitio y sea el mismo
en los servicios, la API y la interfaz web.

Trazabilidad: RN-06, RN-07; citas/plan.md DT-08.
"""

from __future__ import annotations

from datetime import datetime


def ahora() -> datetime:
    """Momento actual en la hora local del centro, sin zona horaria."""
    return datetime.now()
