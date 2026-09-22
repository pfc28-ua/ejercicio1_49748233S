"""Entidades de persistencia.

Trazabilidad: plan.md §3 (modelo de datos), tasks.md T-12 y T-13.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def ahora_utc() -> datetime:
    """Momento actual en UTC, sin zona horaria."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TipoDocumento(str, enum.Enum):
    """Tipos de documento de identidad (RF-02)."""

    DNI = "DNI"
    NIE = "NIE"
    PASAPORTE = "PASAPORTE"


class Sexo(str, enum.Enum):
    """Sexo del paciente (RF-01)."""

    MUJER = "MUJER"
    HOMBRE = "HOMBRE"
    OTRO = "OTRO"
    NO_DECLARA = "NO_DECLARA"


class Paciente(Base):
    """Paciente registrado y su identidad única en el HIS.

    La identidad es doble (plan.md DT-01):

    - ``patient_id``: UUID v4 inmutable. Es la referencia que guardarán el resto
      de módulos del HIS (RN-02).
    - ``codigo_historia_clinica``: código legible ``HC-AAAA-NNNNNN`` que se
      comunica al paciente (RN-03).

    Ninguno de los dos cambia una vez asignado (RF-06, RF-20).
    """

    __tablename__ = "pacientes"
    __table_args__ = (
        # Unicidad del documento garantizada por la base de datos (RN-01, DT-02).
        UniqueConstraint("tipo_documento", "numero_documento", name="uq_pacientes_documento"),
    )

    # Identidad
    patient_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    codigo_historia_clinica: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)

    # Documento de identidad (RF-02)
    tipo_documento: Mapped[str] = mapped_column(String(12), nullable=False)
    numero_documento: Mapped[str] = mapped_column(String(20), nullable=False)

    # Datos personales (RF-01)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    primer_apellido: Mapped[str] = mapped_column(String(60), nullable=False)
    segundo_apellido: Mapped[str | None] = mapped_column(String(60))
    fecha_nacimiento: Mapped[date] = mapped_column(Date, nullable=False)
    sexo: Mapped[str] = mapped_column(String(12), nullable=False)

    # Datos de contacto (RF-03)
    telefono: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(120))
    direccion_calle: Mapped[str | None] = mapped_column(String(120))
    direccion_ciudad: Mapped[str | None] = mapped_column(String(80))
    direccion_cp: Mapped[str | None] = mapped_column(String(10))
    direccion_provincia: Mapped[str | None] = mapped_column(String(80))
    direccion_pais: Mapped[str | None] = mapped_column(String(80))

    # Seguro o mutua (RF-04, RN-12)
    entidad_aseguradora: Mapped[str] = mapped_column(String(120), nullable=False)
    numero_poliza: Mapped[str] = mapped_column(String(60), nullable=False)

    # Momento del registro: determina el año del código de historia clínica.
    fecha_alta: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=ahora_utc)

    @property
    def nombre_completo(self) -> str:
        """Nombre y apellidos en una sola cadena."""
        return " ".join(p for p in (self.nombre, self.primer_apellido, self.segundo_apellido) if p)

    def edad(self, hoy: date | None = None) -> int:
        """Edad en años cumplidos."""
        referencia = hoy or date.today()
        nacimiento = self.fecha_nacimiento
        return referencia.year - nacimiento.year - (
            (referencia.month, referencia.day) < (nacimiento.month, nacimiento.day)
        )


class SecuenciaHistoria(Base):
    """Secuencial anual del código de historia clínica (RN-03, plan.md §3.2).

    El incremento se hace dentro de la transacción del alta, por lo que dos altas
    simultáneas nunca obtienen el mismo número (CL-03). Cada año tiene su propia
    fila y su contador empieza en 1 (CL-04).
    """

    __tablename__ = "secuencia_historia"

    anio: Mapped[int] = mapped_column(Integer, primary_key=True)
    ultimo_valor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
