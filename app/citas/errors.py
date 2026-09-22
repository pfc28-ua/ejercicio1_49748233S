"""Errores de negocio del módulo de citas.

Heredan del `ErrorDeNegocio` del módulo de registro, de modo que el manejador
global de la aplicación los traduce al mismo formato uniforme de error sin
necesidad de tocar nada (RF-25, plan.md DT-09).

Trazabilidad: tasks.md T-03.
"""

from __future__ import annotations

from app.errors import ErrorDeNegocio


class CitaNoEncontrada(ErrorDeNegocio):
    """No existe la cita buscada (RF-15)."""

    codigo = "CITA_NO_ENCONTRADA"
    estado_http = 404

    def __init__(self, mensaje: str = "No existe ninguna cita con esos datos.") -> None:
        super().__init__(mensaje)


class HuecoNoDisponible(ErrorDeNegocio):
    """El hueco solicitado no se puede reservar (RF-07, RN-04, RN-13, CL-01)."""

    codigo = "HUECO_NO_DISPONIBLE"
    estado_http = 409

    def __init__(
        self,
        mensaje: str = "Ese hueco ya no está disponible.",
        motivo: str | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.motivo = motivo

    def a_dict(self) -> dict:
        cuerpo = super().a_dict()
        if self.motivo:
            cuerpo["motivo"] = self.motivo
        return cuerpo


class CitaNoModificable(ErrorDeNegocio):
    """La cita no admite cambios: está cancelada, ya pasó o falta poco (RF-14)."""

    codigo = "CITA_NO_MODIFICABLE"
    estado_http = 409


class PacienteYaCitado(ErrorDeNegocio):
    """El paciente ya tiene otra cita que se solapa con la solicitada (RN-05)."""

    codigo = "PACIENTE_YA_CITADO"
    estado_http = 409

    def __init__(
        self,
        mensaje: str = "El paciente ya tiene otra cita a esa hora.",
        codigo_cita: str | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.codigo_cita = codigo_cita

    def a_dict(self) -> dict:
        cuerpo = super().a_dict()
        if self.codigo_cita:
            cuerpo["codigo_cita"] = self.codigo_cita
        return cuerpo


class FranjaConCitas(ErrorDeNegocio):
    """No se puede bloquear una franja que contiene citas reservadas (RF-18).

    Informa de las citas afectadas para que el personal administrativo pueda
    gestionarlas antes de bloquear (ESC-06, CA-23).
    """

    codigo = "FRANJA_CON_CITAS"
    estado_http = 409

    def __init__(self, citas: list[str] | None = None) -> None:
        citas = citas or []
        super().__init__(
            f"No se puede bloquear: hay {len(citas)} cita(s) reservada(s) en esa franja. "
            "Reprográmelas o cancélelas antes de bloquear."
        )
        self.citas = citas

    def a_dict(self) -> dict:
        cuerpo = super().a_dict()
        cuerpo["citas"] = self.citas
        return cuerpo


class EspecialistaNoEncontrado(ErrorDeNegocio):
    """No existe el especialista indicado."""

    codigo = "ESPECIALISTA_NO_ENCONTRADO"
    estado_http = 404

    def __init__(self, mensaje: str = "No existe ningún especialista con ese identificador.") -> None:
        super().__init__(mensaje)


class BloqueoNoEncontrado(ErrorDeNegocio):
    """No existe el bloqueo indicado (RF-19)."""

    codigo = "BLOQUEO_NO_ENCONTRADO"
    estado_http = 404

    def __init__(self, mensaje: str = "No existe ningún bloqueo con ese identificador.") -> None:
        super().__init__(mensaje)
