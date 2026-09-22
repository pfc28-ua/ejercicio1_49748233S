"""Acceso a datos.

Aísla la base de datos de los casos de uso (plan.md §1, tasks.md T-13 y T-14).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import identity
from app.models import Paciente, SecuenciaHistoria


class RepositorioPacientes:
    """Operaciones de persistencia sobre pacientes."""

    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion

    def anadir(self, paciente: Paciente) -> Paciente:
        """Añade un paciente a la transacción en curso."""
        self.sesion.add(paciente)
        return paciente

    def siguiente_codigo_historia(self, anio: int | None = None) -> str:
        """Reserva el siguiente código de historia clínica del año (RN-03).

        Se ejecuta dentro de la transacción del alta: si el alta falla, el número
        no se consume, y dos altas simultáneas no comparten número (CL-03). Cada
        año empieza en 1 (CL-04).
        """
        anio_actual = anio or date.today().year
        fila = self.sesion.get(SecuenciaHistoria, anio_actual, with_for_update=True)
        if fila is None:
            fila = SecuenciaHistoria(anio=anio_actual, ultimo_valor=0)
            self.sesion.add(fila)
        fila.ultimo_valor += 1
        self.sesion.flush()
        return identity.formatear_codigo_historia(anio_actual, fila.ultimo_valor)

    def obtener_por_id(self, patient_id: str) -> Paciente | None:
        """Paciente por su identificador interno (RF-14)."""
        return self.sesion.get(Paciente, patient_id)

    def obtener_por_documento(self, tipo_documento: str, numero_documento: str) -> Paciente | None:
        """Paciente por su documento de identidad, ya normalizado (RF-10, RN-01)."""
        consulta = select(Paciente).where(
            Paciente.tipo_documento == str(tipo_documento).upper(),
            Paciente.numero_documento == identity.normalizar_documento(numero_documento),
        )
        return self.sesion.scalars(consulta).first()

    def obtener_por_codigo_historia(self, codigo: str) -> Paciente | None:
        """Paciente por su código de historia clínica (RF-11)."""
        consulta = select(Paciente).where(
            Paciente.codigo_historia_clinica == identity.normalizar_codigo_historia(codigo)
        )
        return self.sesion.scalars(consulta).first()
