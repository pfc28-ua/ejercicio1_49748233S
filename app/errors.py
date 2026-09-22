"""Errores de negocio.

El dominio no conoce HTTP: lanza estos errores y la capa de presentación los
traduce al formato uniforme de error (RF-23, plan.md DT-05).
"""

from __future__ import annotations


class ErrorDeNegocio(Exception):
    """Raíz de los errores de negocio del módulo."""

    codigo = "ERROR_NEGOCIO"
    estado_http = 400

    def __init__(self, mensaje: str, detalles: list[dict] | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalles = detalles or []

    def a_dict(self) -> dict:
        """Representación conforme al formato uniforme de error (RF-23)."""
        cuerpo: dict = {"codigo": self.codigo, "mensaje": self.mensaje}
        if self.detalles:
            cuerpo["detalles"] = self.detalles
        return cuerpo


class PacienteNoEncontrado(ErrorDeNegocio):
    """No existe ningún paciente con el dato buscado (RF-12)."""

    codigo = "PACIENTE_NO_ENCONTRADO"
    estado_http = 404

    def __init__(self, mensaje: str = "No existe ningún paciente con esos datos.") -> None:
        super().__init__(mensaje)


class PacienteDuplicado(ErrorDeNegocio):
    """El documento de identidad ya pertenece a un paciente (RF-07, RF-19, RN-01).

    Incluye el código de historia clínica del paciente existente para poder ir
    directamente a su ficha (ESC-03).
    """

    codigo = "PACIENTE_DUPLICADO"
    estado_http = 409

    def __init__(
        self,
        mensaje: str = "Ya existe un paciente registrado con ese documento de identidad.",
        codigo_historia_clinica: str | None = None,
        patient_id: str | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.codigo_historia_clinica = codigo_historia_clinica
        self.patient_id = patient_id

    def a_dict(self) -> dict:
        cuerpo = super().a_dict()
        if self.codigo_historia_clinica:
            cuerpo["codigo_historia_clinica"] = self.codigo_historia_clinica
        if self.patient_id:
            cuerpo["patient_id"] = self.patient_id
        return cuerpo


class ErrorDeValidacion(ErrorDeNegocio):
    """Los datos no cumplen alguna regla de negocio (RF-08)."""

    codigo = "VALIDACION"
    estado_http = 422

    def __init__(
        self,
        mensaje: str = "Los datos enviados no son válidos.",
        detalles: list[dict] | None = None,
    ) -> None:
        super().__init__(mensaje, detalles)
