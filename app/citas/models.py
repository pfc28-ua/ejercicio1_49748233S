"""Entidades de persistencia del módulo de citas.

Comparten la base declarativa y la base de datos del módulo de registro, pero
viven en sus propias tablas: el ejercicio 1 no se modifica (plan.md §1).

Trazabilidad: citas/plan.md §3, tasks.md T-04 a T-09.
"""

from __future__ import annotations

import enum
from datetime import datetime, time, timedelta

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.citas.config import DURACION_POR_DEFECTO_MIN
from app.citas.reloj import ahora as ahora_local
from app.database import Base


class EstadoCita(str, enum.Enum):
    """Estados de una cita (RN-09)."""

    RESERVADA = "RESERVADA"
    CANCELADA = "CANCELADA"


class MotivoBloqueo(str, enum.Enum):
    """Motivos por los que se bloquea la agenda de un especialista (RN-11)."""

    VACACIONES = "VACACIONES"
    FORMACION = "FORMACION"
    BAJA = "BAJA"
    OTRO = "OTRO"


class Centro(Base):
    """Centro en el que se pasa consulta. Catálogo (RN-16)."""

    __tablename__ = "centros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    direccion: Mapped[str | None] = mapped_column(String(160))
    ciudad: Mapped[str | None] = mapped_column(String(80))


class Especialidad(Base):
    """Especialidad médica. Catálogo (RN-16)."""

    __tablename__ = "especialidades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)


class Especialista(Base):
    """Profesional que pasa consulta en un centro y una especialidad.

    La duración de sus huecos es una propiedad suya y se puede ajustar desde la
    gestión de agenda (RF-20, RN-02).
    """

    __tablename__ = "especialistas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(120), nullable=False)
    especialidad_id: Mapped[int] = mapped_column(ForeignKey("especialidades.id"), nullable=False)
    centro_id: Mapped[int] = mapped_column(ForeignKey("centros.id"), nullable=False)
    duracion_cita_min: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DURACION_POR_DEFECTO_MIN
    )

    especialidad: Mapped[Especialidad] = relationship(lazy="joined")
    centro: Mapped[Centro] = relationship(lazy="joined")
    horarios: Mapped[list["HorarioConsulta"]] = relationship(
        back_populates="especialista", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellidos}"


class HorarioConsulta(Base):
    """Tramo semanal en el que un especialista pasa consulta.

    Es la plantilla a partir de la cual se generan los huecos (RN-03). Forma
    parte del catálogo: se carga con los datos de ejemplo y no se gestiona desde
    la aplicación (spec §8.5).
    """

    __tablename__ = "horarios_consulta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    especialista_id: Mapped[int] = mapped_column(ForeignKey("especialistas.id"), nullable=False)
    #: 0 = lunes … 6 = domingo, como `datetime.weekday()`.
    dia_semana: Mapped[int] = mapped_column(Integer, nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)

    especialista: Mapped[Especialista] = relationship(back_populates="horarios")

    __table_args__ = (
        UniqueConstraint("especialista_id", "dia_semana", "hora_inicio", name="uq_horario_tramo"),
    )


class Bloqueo(Base):
    """Periodo en el que el especialista no pasa consulta (RF-17, RN-11)."""

    __tablename__ = "bloqueos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    especialista_id: Mapped[int] = mapped_column(
        ForeignKey("especialistas.id"), nullable=False, index=True
    )
    inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    motivo: Mapped[str] = mapped_column(String(20), nullable=False)
    observaciones: Mapped[str | None] = mapped_column(String(200))

    especialista: Mapped[Especialista] = relationship(lazy="joined")


class Cita(Base):
    """Cita de un paciente con un especialista.

    La identidad de la cita (``cita_id`` y ``codigo``) es inmutable: al
    reprogramar cambia la hora, pero sigue siendo la misma cita (RN-01, RN-10,
    RF-12).

    La cita guarda el ``patient_id`` del módulo de registro y **no copia ningún
    dato personal** del paciente (RF-26, CA-28).

    ``duracion_min`` se guarda en la propia cita para que cambiar la duración de
    los huecos del especialista no altere las citas ya reservadas (RF-22, RN-14).
    """

    __tablename__ = "citas"

    cita_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)

    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pacientes.patient_id"), nullable=False, index=True
    )
    especialista_id: Mapped[int] = mapped_column(
        ForeignKey("especialistas.id"), nullable=False, index=True
    )

    inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duracion_min: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(12), nullable=False, default=EstadoCita.RESERVADA.value)
    motivo_consulta: Mapped[str | None] = mapped_column(String(300))

    fecha_reserva: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=ahora_local)
    fecha_modificacion: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=ahora_local)

    especialista: Mapped[Especialista] = relationship(lazy="joined")

    @property
    def fin(self) -> datetime:
        """Momento en el que termina la cita (plan.md §3.2)."""
        return self.inicio + timedelta(minutes=self.duracion_min)

    @property
    def activa(self) -> bool:
        return self.estado == EstadoCita.RESERVADA.value

    def es_pasada(self, ahora: datetime | None = None) -> bool:
        return self.inicio < (ahora or ahora_local())


# Dos pacientes no pueden ocupar el mismo hueco del mismo especialista (RN-04,
# DT-03). El índice es parcial: solo alcanza a las citas reservadas, de modo que
# una cita cancelada libera su hueco (CL-20).
Index(
    "ux_citas_hueco_reservado",
    Cita.especialista_id,
    Cita.inicio,
    unique=True,
    sqlite_where=text("estado = 'RESERVADA'"),
    postgresql_where=text("estado = 'RESERVADA'"),
)


class SecuenciaCita(Base):
    """Secuencial anual del código de cita (RN-01, CL-19).

    Mismo mecanismo que el código de historia clínica del ejercicio 1: se
    incrementa dentro de la transacción de la reserva.
    """

    __tablename__ = "secuencia_cita"

    anio: Mapped[int] = mapped_column(Integer, primary_key=True)
    ultimo_valor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
