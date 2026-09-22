"""Acceso a datos del módulo de citas (tasks.md T-10)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.citas.models import (
    Bloqueo,
    Centro,
    Cita,
    Especialidad,
    Especialista,
    EstadoCita,
    SecuenciaCita,
)


class RepositorioCitas:
    """Operaciones de persistencia del catálogo, la agenda y las citas."""

    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion

    # -- Catálogo (RN-16) ---------------------------------------------------

    def especialidades(self) -> list[Especialidad]:
        return list(self.sesion.scalars(select(Especialidad).order_by(Especialidad.nombre)).all())

    def centros(self) -> list[Centro]:
        return list(self.sesion.scalars(select(Centro).order_by(Centro.nombre)).all())

    def especialista(self, especialista_id: int) -> Especialista | None:
        return self.sesion.get(Especialista, especialista_id)

    def buscar_especialistas(
        self, especialidad_id: int | None = None, centro_id: int | None = None
    ) -> list[Especialista]:
        """Especialistas filtrados por especialidad y centro (RF-01)."""
        consulta = select(Especialista)
        if especialidad_id is not None:
            consulta = consulta.where(Especialista.especialidad_id == especialidad_id)
        if centro_id is not None:
            consulta = consulta.where(Especialista.centro_id == centro_id)
        consulta = consulta.order_by(Especialista.apellidos, Especialista.nombre)
        return list(self.sesion.scalars(consulta).all())

    # -- Agenda -------------------------------------------------------------

    def bloqueos(
        self, especialista_id: int, desde: datetime | None = None, hasta: datetime | None = None
    ) -> list[Bloqueo]:
        """Bloqueos del especialista que tocan el periodo indicado (RF-16)."""
        consulta = select(Bloqueo).where(Bloqueo.especialista_id == especialista_id)
        if desde is not None:
            consulta = consulta.where(Bloqueo.fin > desde)
        if hasta is not None:
            consulta = consulta.where(Bloqueo.inicio < hasta)
        return list(self.sesion.scalars(consulta.order_by(Bloqueo.inicio)).all())

    def bloqueo(self, bloqueo_id: int) -> Bloqueo | None:
        return self.sesion.get(Bloqueo, bloqueo_id)

    def anadir(self, entidad):
        self.sesion.add(entidad)
        return entidad

    def eliminar(self, entidad) -> None:
        self.sesion.delete(entidad)

    # -- Citas --------------------------------------------------------------

    def citas_de_especialista(
        self,
        especialista_id: int,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        solo_activas: bool = True,
    ) -> list[Cita]:
        """Citas del especialista dentro del periodo (RF-16, RN-13)."""
        consulta = select(Cita).where(Cita.especialista_id == especialista_id)
        if solo_activas:
            consulta = consulta.where(Cita.estado == EstadoCita.RESERVADA.value)
        if desde is not None:
            consulta = consulta.where(Cita.inicio >= desde)
        if hasta is not None:
            consulta = consulta.where(Cita.inicio < hasta)
        return list(self.sesion.scalars(consulta.order_by(Cita.inicio)).all())

    def citas_de_paciente(self, patient_id: str) -> list[Cita]:
        """Todas las citas de un paciente, de la más próxima a la más antigua (RF-09)."""
        consulta = (
            select(Cita).where(Cita.patient_id == patient_id).order_by(Cita.inicio.desc())
        )
        return list(self.sesion.scalars(consulta).all())

    def citas_activas_de_paciente(self, patient_id: str) -> list[Cita]:
        """Citas activas del paciente, para comprobar solapamientos (RN-05)."""
        consulta = select(Cita).where(
            Cita.patient_id == patient_id, Cita.estado == EstadoCita.RESERVADA.value
        )
        return list(self.sesion.scalars(consulta).all())

    def cita_por_id(self, cita_id: str) -> Cita | None:
        return self.sesion.get(Cita, cita_id)

    def cita_por_codigo(self, codigo: str) -> Cita | None:
        """Cita por su código legible (RF-15)."""
        consulta = select(Cita).where(Cita.codigo == (codigo or "").strip().upper())
        return self.sesion.scalars(consulta).first()

    def siguiente_codigo_cita(self, anio: int | None = None) -> str:
        """Reserva el siguiente código de cita del año (RN-01, CL-19).

        Se incrementa dentro de la transacción de la reserva, igual que el
        código de historia clínica del ejercicio 1.
        """
        from app.citas.services import formatear_codigo_cita

        anio_actual = anio or date.today().year
        fila = self.sesion.get(SecuenciaCita, anio_actual, with_for_update=True)
        if fila is None:
            fila = SecuenciaCita(anio=anio_actual, ultimo_valor=0)
            self.sesion.add(fila)
        fila.ultimo_valor += 1
        self.sesion.flush()
        return formatear_codigo_cita(anio_actual, fila.ultimo_valor)
