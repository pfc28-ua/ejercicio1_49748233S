"""API REST del módulo de citas (RF-23).

Solo traduce HTTP a casos de uso: las reglas viven en `services.py`.

Trazabilidad: citas/plan.md §6; tasks.md T-22, T-28, T-34.
"""

from __future__ import annotations

import uuid
from datetime import date, time, timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.citas.models import Cita, Especialista
from app.citas.schemas import (
    AgendaRespuesta,
    IdentificacionPeticion,
    BloqueoPeticion,
    BloqueoRespuesta,
    CentroRespuesta,
    CitaEnAgenda,
    CitaRespuesta,
    DisponibilidadRespuesta,
    DuracionPeticion,
    EspecialidadRespuesta,
    EspecialistaRespuesta,
    HuecoRespuesta,
    PacienteDeCita,
    ReprogramarPeticion,
    ReservaPeticion,
)
from app.citas.services import ServicioCitas
from app.database import obtener_sesion
from app.errors import ErrorDeValidacion
from app.citas.reloj import ahora as ahora_local
from app.schemas import ErrorRespuesta

router = APIRouter(prefix="/api/v1", tags=["Citas"])

ERRORES = {
    404: {"model": ErrorRespuesta, "description": "No encontrado"},
    409: {"model": ErrorRespuesta, "description": "Conflicto de agenda"},
    422: {"model": ErrorRespuesta, "description": "Datos no válidos"},
}


def obtener_servicio(sesion: Session = Depends(obtener_sesion)) -> ServicioCitas:
    return ServicioCitas(sesion)


def _validar_uuid(cita_id: str) -> str:
    """Rechaza un identificador de cita que no sea un UUID (CL-17)."""
    try:
        uuid.UUID(cita_id)
    except ValueError as exc:
        raise ErrorDeValidacion(
            detalles=[{"campo": "cita_id", "mensaje": "El identificador de cita no es un UUID válido."}]
        ) from exc
    return cita_id


def _paciente_de(servicio: ServicioCitas, cita: Cita) -> PacienteDeCita:
    """Obtiene los datos del paciente del módulo de registro (RF-26, CA-28)."""
    paciente = servicio.pacientes.obtener(cita.patient_id)
    return PacienteDeCita(
        patient_id=paciente.patient_id,
        codigo_historia_clinica=paciente.codigo_historia_clinica,
        nombre_completo=paciente.nombre_completo,
    )


def _cita_a_respuesta(servicio: ServicioCitas, cita: Cita) -> CitaRespuesta:
    return CitaRespuesta(
        cita_id=cita.cita_id,
        codigo=cita.codigo,
        estado=cita.estado,
        inicio=cita.inicio,
        fin=cita.fin,
        duracion_min=cita.duracion_min,
        motivo_consulta=cita.motivo_consulta,
        pasada=cita.es_pasada(),
        paciente=_paciente_de(servicio, cita),
        especialista=EspecialistaRespuesta.model_validate(cita.especialista),
    )


# ---------------------------------------------------------------------------
# Catálogo y capacidad A · Reservar
# ---------------------------------------------------------------------------

@router.get("/catalogo/especialidades", response_model=list[EspecialidadRespuesta],
            summary="Especialidades médicas disponibles")
def especialidades(servicio: ServicioCitas = Depends(obtener_servicio)):
    return servicio.especialidades()


@router.get("/catalogo/centros", response_model=list[CentroRespuesta],
            summary="Centros del que dispone la red")
def centros(servicio: ServicioCitas = Depends(obtener_servicio)):
    return servicio.centros()


@router.get(
    "/especialistas",
    response_model=list[EspecialistaRespuesta],
    summary="Buscar especialistas por especialidad y centro",
    description="Primer paso de la reserva: elegir con quién se quiere la cita (RF-01).",
)
def buscar_especialistas(
    especialidad_id: int | None = Query(default=None),
    centro_id: int | None = Query(default=None),
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    return servicio.buscar_especialistas(especialidad_id, centro_id)


@router.get(
    "/especialistas/{especialista_id}/disponibilidad",
    response_model=DisponibilidadRespuesta,
    summary="Huecos libres de un especialista",
    description="La disponibilidad se calcula a partir del horario, la duración de los huecos, "
    "los bloqueos y las citas ya reservadas, por lo que siempre es real (RF-02, RF-03, RF-21).",
    responses=ERRORES,
)
def disponibilidad(
    especialista_id: int,
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    hora_desde: time | None = Query(default=None, description="Primera hora que le viene bien al paciente"),
    hora_hasta: time | None = Query(default=None, description="Última hora a la que puede acudir"),
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    inicio = desde or ahora_local().date()
    fin = hasta or (inicio + timedelta(days=14))
    huecos = servicio.disponibilidad(
        especialista_id, inicio, fin, hora_desde=hora_desde, hora_hasta=hora_hasta
    )
    especialista = servicio.obtener_especialista(especialista_id)

    return DisponibilidadRespuesta(
        especialista_id=especialista_id,
        desde=inicio,
        hasta=fin,
        duracion_cita_min=especialista.duracion_cita_min,
        huecos=[
            HuecoRespuesta(inicio=h.inicio, fin=h.fin, duracion_min=h.duracion_min) for h in huecos
        ],
    )


@router.post(
    "/citas",
    response_model=CitaRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Reservar una cita",
    description="El paciente se identifica con su documento o su código de historia clínica y "
    "reserva un hueco concreto (RF-04 a RF-08).",
    responses=ERRORES,
)
def reservar(peticion: ReservaPeticion, servicio: ServicioCitas = Depends(obtener_servicio)):
    paciente = servicio.identificar_paciente(
        peticion.tipo_documento, peticion.numero_documento, peticion.codigo_historia_clinica
    )
    cita = servicio.reservar(
        patient_id=paciente.patient_id,
        especialista_id=peticion.especialista_id,
        inicio=peticion.inicio,
        motivo_consulta=peticion.motivo_consulta,
    )
    return _cita_a_respuesta(servicio, cita)


# ---------------------------------------------------------------------------
# Capacidad B · Cancelar o reprogramar
# ---------------------------------------------------------------------------

@router.get(
    "/citas",
    response_model=list[CitaRespuesta],
    summary="Citas de un paciente",
    description="Citas del paciente identificado, de la más reciente a la más antigua (RF-09).",
    responses=ERRORES,
)
def citas_de_paciente(
    tipo_documento: str | None = Query(default=None),
    numero_documento: str | None = Query(default=None),
    codigo_historia_clinica: str | None = Query(default=None),
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    paciente = servicio.identificar_paciente(
        tipo_documento, numero_documento, codigo_historia_clinica
    )
    return [_cita_a_respuesta(servicio, c) for c in servicio.citas_de_paciente(paciente.patient_id)]


@router.get(
    "/citas/{codigo}",
    response_model=CitaRespuesta,
    summary="Consultar una cita por su código",
    responses=ERRORES,
)
def cita_por_codigo(codigo: str, servicio: ServicioCitas = Depends(obtener_servicio)):
    return _cita_a_respuesta(servicio, servicio.cita_por_codigo(codigo))


@router.post(
    "/citas/{cita_id}/cancelar",
    response_model=CitaRespuesta,
    summary="Cancelar una cita",
    description="Libera el hueco, que vuelve a ofrecerse a otros pacientes (RF-10, RF-13). "
    "El paciente debe identificarse: solo puede cancelar sus propias citas (CL-13).",
    responses=ERRORES,
)
def cancelar(
    cita_id: str,
    identificacion: IdentificacionPeticion,
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    _validar_uuid(cita_id)
    paciente = servicio.identificar_paciente(
        identificacion.tipo_documento,
        identificacion.numero_documento,
        identificacion.codigo_historia_clinica,
    )
    cita = servicio.cancelar(cita_id, patient_id=paciente.patient_id)
    return _cita_a_respuesta(servicio, cita)


@router.post(
    "/citas/{cita_id}/reprogramar",
    response_model=CitaRespuesta,
    summary="Reprogramar una cita",
    description="Cambia la cita a otro hueco del mismo especialista conservando su identificador "
    "y su código: es la misma cita (RF-11, RF-12). El paciente debe identificarse (CL-13).",
    responses=ERRORES,
)
def reprogramar(
    cita_id: str,
    peticion: ReprogramarPeticion,
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    _validar_uuid(cita_id)
    paciente = servicio.identificar_paciente(
        peticion.tipo_documento, peticion.numero_documento, peticion.codigo_historia_clinica
    )
    cita = servicio.reprogramar(cita_id, peticion.inicio, patient_id=paciente.patient_id)
    return _cita_a_respuesta(servicio, cita)


# ---------------------------------------------------------------------------
# Capacidad C · Gestionar la agenda
# ---------------------------------------------------------------------------

@router.get(
    "/especialistas/{especialista_id}/agenda",
    response_model=AgendaRespuesta,
    summary="Agenda de un especialista",
    description="Horario, bloqueos y citas reservadas del especialista (RF-16).",
    responses=ERRORES,
)
def agenda(
    especialista_id: int,
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    inicio = desde or ahora_local().date()
    fin = hasta or (inicio + timedelta(days=14))
    datos = servicio.agenda(especialista_id, inicio, fin)

    return AgendaRespuesta(
        especialista=EspecialistaRespuesta.model_validate(datos["especialista"]),
        desde=inicio,
        hasta=fin,
        horarios=datos["horarios"],
        bloqueos=datos["bloqueos"],
        citas=[
            CitaEnAgenda(
                codigo=c.codigo,
                inicio=c.inicio,
                fin=c.fin,
                estado=c.estado,
                paciente=_paciente_de(servicio, c),
            )
            for c in datos["citas"]
        ],
    )


@router.post(
    "/especialistas/{especialista_id}/bloqueos",
    response_model=BloqueoRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary="Bloquear una franja de la agenda",
    description="Vacaciones, formación o baja. Se rechaza si la franja contiene citas reservadas, "
    "informando de cuáles son (RF-17, RF-18).",
    responses=ERRORES,
)
def bloquear(
    especialista_id: int,
    peticion: BloqueoPeticion,
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    return servicio.bloquear(
        especialista_id=especialista_id,
        inicio=peticion.inicio,
        fin=peticion.fin,
        motivo=peticion.motivo,
        observaciones=peticion.observaciones,
    )


@router.delete(
    "/bloqueos/{bloqueo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Levantar un bloqueo",
    responses={404: ERRORES[404]},
)
def levantar_bloqueo(bloqueo_id: int, servicio: ServicioCitas = Depends(obtener_servicio)):
    servicio.levantar_bloqueo(bloqueo_id)


@router.patch(
    "/especialistas/{especialista_id}/duracion",
    response_model=EspecialistaRespuesta,
    summary="Ajustar la duración de los huecos",
    description="Afecta a la disponibilidad futura; las citas ya reservadas no cambian (RF-20, RF-22).",
    responses=ERRORES,
)
def ajustar_duracion(
    especialista_id: int,
    peticion: DuracionPeticion,
    servicio: ServicioCitas = Depends(obtener_servicio),
) -> Especialista:
    return servicio.ajustar_duracion(especialista_id, peticion.duracion_cita_min)
