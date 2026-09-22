"""Catálogo y agenda de ejemplo para el módulo de citas (tasks.md T-42).

Centros, especialidades, especialistas y horarios son datos de referencia cuya
gestión queda fuera del alcance del enunciado (RN-16, spec §8.2), así que se
cargan desde aquí.

Uso:  python datos_ejemplo_citas.py
"""

from __future__ import annotations

from datetime import time

from sqlalchemy import select

from app.citas.models import Centro, Especialidad, Especialista, HorarioConsulta
from app.database import FabricaSesion, crear_esquema

CENTROS = [
    {"nombre": "Clínica Norte", "direccion": "Avenida de la Estación 14", "ciudad": "Alicante"},
    {"nombre": "Centro Médico Sur", "direccion": "Calle del Mar 3", "ciudad": "Elche"},
]

ESPECIALIDADES = ["Medicina de familia", "Dermatología", "Traumatología", "Pediatría"]

#: (nombre, apellidos, especialidad, centro, duración, horario semanal)
#: El horario es una lista de (día, hora inicio, hora fin), con 0 = lunes.
ESPECIALISTAS = [
    (
        "Elena", "Ruiz Navarro", "Dermatología", "Clínica Norte", 20,
        [(0, time(9, 0), time(13, 0)), (2, time(9, 0), time(13, 0)), (4, time(9, 0), time(12, 0))],
    ),
    (
        "Carlos", "Alonso Prieto", "Traumatología", "Clínica Norte", 30,
        [(1, time(16, 0), time(20, 0)), (3, time(16, 0), time(20, 0))],
    ),
    (
        "Marta", "Gil Serrano", "Medicina de familia", "Clínica Norte", 15,
        [(d, time(8, 0), time(14, 0)) for d in range(5)],
    ),
    (
        "Javier", "Peña Lorca", "Pediatría", "Centro Médico Sur", 20,
        [(0, time(10, 0), time(14, 0)), (3, time(10, 0), time(14, 0))],
    ),
    (
        "Lucía", "Sáez Moreno", "Dermatología", "Centro Médico Sur", 20,
        [(1, time(9, 0), time(13, 0)), (4, time(9, 0), time(13, 0))],
    ),
]


def main() -> None:
    from app.citas import models as _modelos  # noqa: F401  (registra las tablas)

    crear_esquema()

    with FabricaSesion() as sesion:
        if sesion.scalars(select(Especialista)).first() is not None:
            print("  El catálogo de citas ya estaba cargado.")
            return

        centros = {}
        for datos in CENTROS:
            centro = Centro(**datos)
            sesion.add(centro)
            centros[datos["nombre"]] = centro

        especialidades = {}
        for nombre in ESPECIALIDADES:
            especialidad = Especialidad(nombre=nombre)
            sesion.add(especialidad)
            especialidades[nombre] = especialidad

        sesion.flush()

        for nombre, apellidos, especialidad, centro, duracion, horario in ESPECIALISTAS:
            especialista = Especialista(
                nombre=nombre,
                apellidos=apellidos,
                especialidad_id=especialidades[especialidad].id,
                centro_id=centros[centro].id,
                duracion_cita_min=duracion,
            )
            sesion.add(especialista)
            sesion.flush()
            for dia, inicio, fin in horario:
                sesion.add(
                    HorarioConsulta(
                        especialista_id=especialista.id,
                        dia_semana=dia,
                        hora_inicio=inicio,
                        hora_fin=fin,
                    )
                )
            print(f"  {especialista.nombre_completo} - {especialidad} ({centro}), {duracion} min")

        sesion.commit()

    print("\nCatálogo de citas cargado. Arranque con: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
