"""Contratos de entrada y salida del módulo de citas (tasks.md T-22, T-28, T-34)."""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.citas.config import MOTIVO_CONSULTA_MAXIMO


# --------------------------------------------------------------------------
# Catálogo
# --------------------------------------------------------------------------

class EspecialidadRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str


class CentroRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    direccion: str | None = None
    ciudad: str | None = None


class EspecialistaRespuesta(BaseModel):
    """Especialista con su especialidad, su centro y su duración de cita (RF-01)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    apellidos: str
    duracion_cita_min: int
    especialidad: EspecialidadRespuesta
    centro: CentroRespuesta


# --------------------------------------------------------------------------
# Capacidad A · Disponibilidad y reserva
# --------------------------------------------------------------------------

class HuecoRespuesta(BaseModel):
    """Hueco libre ofrecido al paciente (RF-02)."""

    inicio: datetime
    fin: datetime
    duracion_min: int


class DisponibilidadRespuesta(BaseModel):
    especialista_id: int
    desde: date
    hasta: date
    duracion_cita_min: int
    huecos: list[HuecoRespuesta]


class ReservaPeticion(BaseModel):
    """Petición de reserva (RF-04, RF-05).

    El paciente se identifica con su documento o su código de historia clínica,
    reutilizando el módulo de registro (spec §2.1).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    tipo_documento: str | None = None
    numero_documento: str | None = None
    codigo_historia_clinica: str | None = None

    especialista_id: int
    inicio: datetime
    motivo_consulta: str | None = Field(default=None, max_length=MOTIVO_CONSULTA_MAXIMO)


class PacienteDeCita(BaseModel):
    """Identidad del paciente dentro de una cita.

    Son los datos que el módulo de citas obtiene del de registro: la cita solo
    guarda el `patient_id` (RF-26, CA-28).
    """

    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    codigo_historia_clinica: str
    nombre_completo: str


class CitaRespuesta(BaseModel):
    """Datos de una cita (RF-08, RF-15)."""

    cita_id: str
    codigo: str
    estado: str
    inicio: datetime
    fin: datetime
    duracion_min: int
    motivo_consulta: str | None
    pasada: bool

    paciente: PacienteDeCita
    especialista: EspecialistaRespuesta


class ReprogramarPeticion(BaseModel):
    """Nueva fecha y hora de una cita (RF-11).

    Incluye la identificación del paciente, porque solo puede reprogramar sus
    propias citas (CL-13).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    inicio: datetime

    tipo_documento: str | None = None
    numero_documento: str | None = None
    codigo_historia_clinica: str | None = None


class IdentificacionPeticion(BaseModel):
    """Identificación del paciente para operar sobre sus citas (RF-09, RF-10)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    tipo_documento: str | None = None
    numero_documento: str | None = None
    codigo_historia_clinica: str | None = None


# --------------------------------------------------------------------------
# Capacidad C · Agenda
# --------------------------------------------------------------------------

class HorarioRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dia_semana: int
    hora_inicio: time
    hora_fin: time


class BloqueoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inicio: datetime
    fin: datetime
    motivo: str
    observaciones: str | None = None


class CitaEnAgenda(BaseModel):
    """Cita tal como la ve el personal administrativo en la agenda (RF-16)."""

    codigo: str
    inicio: datetime
    fin: datetime
    estado: str
    paciente: PacienteDeCita


class AgendaRespuesta(BaseModel):
    especialista: EspecialistaRespuesta
    desde: date
    hasta: date
    horarios: list[HorarioRespuesta]
    bloqueos: list[BloqueoRespuesta]
    citas: list[CitaEnAgenda]


class BloqueoPeticion(BaseModel):
    """Franja que se quiere bloquear (RF-17)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    inicio: datetime
    fin: datetime
    motivo: str = "OTRO"
    observaciones: str | None = Field(default=None, max_length=200)


class DuracionPeticion(BaseModel):
    """Nueva duración de los huecos del especialista (RF-20)."""

    duracion_cita_min: int
