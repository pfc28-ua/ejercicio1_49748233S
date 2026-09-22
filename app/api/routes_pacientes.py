"""API REST del módulo (RF-21).

Es la vía por la que otros módulos del HIS reutilizarán la identidad del
paciente. Solo traduce HTTP a casos de uso: no contiene reglas de negocio.

Trazabilidad: plan.md §5, tasks.md T-21, T-26 y T-31.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import obtener_sesion
from app.errors import ErrorDeValidacion
from app.models import TipoDocumento
from app.schemas import ErrorRespuesta, PacienteCrear, PacienteModificar, PacienteRespuesta
from app.services import ServicioPacientes

router = APIRouter(prefix="/api/v1/pacientes", tags=["Pacientes"])

ERRORES = {
    404: {"model": ErrorRespuesta, "description": "Paciente no encontrado"},
    409: {"model": ErrorRespuesta, "description": "Documento de identidad ya registrado"},
    422: {"model": ErrorRespuesta, "description": "Datos no válidos"},
}


def obtener_servicio(sesion: Session = Depends(obtener_sesion)) -> ServicioPacientes:
    return ServicioPacientes(sesion)


def _validar_uuid(patient_id: str) -> str:
    """Rechaza un identificador que no es un UUID (CL-17)."""
    try:
        uuid.UUID(patient_id)
    except ValueError as exc:
        raise ErrorDeValidacion(
            detalles=[{"campo": "patient_id", "mensaje": "El identificador de paciente no es un UUID válido."}]
        ) from exc
    return patient_id


# Capacidad A · Registro e identificación ------------------------------------

@router.post(
    "",
    response_model=PacienteRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un paciente",
    description="Registra un paciente con sus datos personales y su número de seguro o mutua, "
    "y le asocia su identidad única: `patient_id` y código de historia clínica (RF-01 a RF-09).",
    responses={409: ERRORES[409], 422: ERRORES[422]},
)
def registrar_paciente(
    datos: PacienteCrear, servicio: ServicioPacientes = Depends(obtener_servicio)
) -> PacienteRespuesta:
    return PacienteRespuesta.model_validate(servicio.registrar(datos))


# Capacidad B · Búsqueda y verificación --------------------------------------

@router.get(
    "/buscar",
    response_model=PacienteRespuesta,
    summary="Buscar un paciente por documento o por código de historia clínica",
    description="Devuelve la ficha del paciente con sus datos identificativos, para verificar su "
    "identidad (RF-10 a RF-13). Indique `tipo_documento` y `numero_documento`, o bien "
    "`codigo_historia_clinica`.",
    responses=ERRORES,
)
def buscar_paciente(
    tipo_documento: TipoDocumento | None = Query(default=None),
    numero_documento: str | None = Query(default=None),
    codigo_historia_clinica: str | None = Query(default=None),
    servicio: ServicioPacientes = Depends(obtener_servicio),
) -> PacienteRespuesta:
    if codigo_historia_clinica:
        paciente = servicio.buscar_por_codigo_historia(codigo_historia_clinica)
    elif tipo_documento and numero_documento:
        paciente = servicio.buscar_por_documento(tipo_documento.value, numero_documento)
    else:
        # CL-16
        raise ErrorDeValidacion(
            mensaje="Indique un documento de identidad o un código de historia clínica.",
            detalles=[{
                "campo": "criterio",
                "mensaje": "Envíe tipo_documento y numero_documento, o bien codigo_historia_clinica.",
            }],
        )
    return PacienteRespuesta.model_validate(paciente)


@router.get(
    "/{patient_id}",
    response_model=PacienteRespuesta,
    summary="Recuperar un paciente por su identificador interno",
    description="Permite a otros módulos del HIS obtener el paciente a partir del `patient_id` "
    "que guardan como referencia (RF-14).",
    responses={404: ERRORES[404], 422: ERRORES[422]},
)
def obtener_paciente(
    patient_id: str, servicio: ServicioPacientes = Depends(obtener_servicio)
) -> PacienteRespuesta:
    return PacienteRespuesta.model_validate(servicio.obtener(_validar_uuid(patient_id)))


# Capacidad C · Modificación y actualización ----------------------------------

@router.patch(
    "/{patient_id}",
    response_model=PacienteRespuesta,
    summary="Modificar o completar los datos de un paciente",
    description="Modificación parcial: solo cambian los datos enviados, y un dato opcional enviado "
    "vacío se borra. La identidad del paciente no cambia (RF-15 a RF-20).",
    responses=ERRORES,
)
def modificar_paciente(
    patient_id: str,
    datos: PacienteModificar,
    servicio: ServicioPacientes = Depends(obtener_servicio),
) -> PacienteRespuesta:
    return PacienteRespuesta.model_validate(servicio.modificar(_validar_uuid(patient_id), datos))
