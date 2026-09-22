"""Interfaz web del módulo de citas (RF-24).

Dos zonas, sin control de acceso entre ellas (plan.md DT-10):

- ``/citas``  → zona del paciente: identificarse, buscar, reservar, cancelar y
  reprogramar.
- ``/agenda`` → zona del personal administrativo: bloqueos y duración de huecos.

El paciente se arrastra en el parámetro ``b`` (su documento o su código de
historia clínica). No es una sesión: es el dato con el que se identifica en cada
pantalla (spec §2.1).

Trazabilidad: citas/plan.md §6.1; tasks.md T-36 a T-40.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.citas.models import MotivoBloqueo
from app.citas.services import ServicioCitas
from app.database import obtener_sesion
from app.errors import ErrorDeNegocio
from app.citas.reloj import ahora as ahora_local

router = APIRouter(include_in_schema=False)

# Las plantillas del módulo, más las del ejercicio 1 para poder heredar de su
# plantilla base y mantener el mismo diseño.
_AQUI = Path(__file__).resolve().parent
plantillas = Jinja2Templates(
    directory=[str(_AQUI / "templates"), str(_AQUI.parent / "web" / "templates")]
)

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
#: Franjas horarias entre las que puede elegir el paciente (enunciado §3.1).
FRANJAS = {
    "MANANA": (time(0, 0), time(14, 0)),
    "TARDE": (time(14, 0), time(23, 59)),
}
FRANJAS_TEXTO = {"": "Cualquier hora", "MANANA": "Solo por la mañana", "TARDE": "Solo por la tarde"}

MOTIVOS = {
    "VACACIONES": "Vacaciones",
    "FORMACION": "Formación",
    "BAJA": "Baja",
    "OTRO": "Otro",
}

plantillas.env.filters["tono"] = lambda texto: sum(ord(c) for c in texto or "") % 360
plantillas.env.filters["dia"] = lambda n: DIAS[n] if 0 <= n < 7 else "—"
plantillas.env.filters["hora"] = lambda v: v.strftime("%H:%M") if v else "—"
plantillas.env.filters["fecha"] = lambda v: v.strftime("%d/%m/%Y") if v else "—"
plantillas.env.filters["fechahora"] = lambda v: v.strftime("%d/%m/%Y · %H:%M") if v else "—"
plantillas.env.filters["motivo"] = lambda v: MOTIVOS.get(str(v), str(v))


def obtener_servicio(sesion: Session = Depends(obtener_sesion)) -> ServicioCitas:
    return ServicioCitas(sesion)


def _identificar(servicio: ServicioCitas, b: str | None):
    """Resuelve al paciente a partir del texto escrito por él (DT-07)."""
    from app import identity

    criterio, valor = identity.detectar_criterio_busqueda(b)
    if criterio == "HISTORIA":
        return servicio.identificar_paciente(codigo_historia_clinica=valor)
    if criterio in {"DNI", "NIE", "PASAPORTE"}:
        return servicio.identificar_paciente(tipo_documento=criterio, numero_documento=valor)
    return None


# ---------------------------------------------------------------------------
# Zona del paciente
# ---------------------------------------------------------------------------

@router.get("/citas", response_class=HTMLResponse)
def identificarse(
    request: Request, b: str | None = None, servicio: ServicioCitas = Depends(obtener_servicio)
):
    """Punto de entrada del paciente: se identifica para ver o pedir sus citas."""
    mensaje = None
    if b:
        try:
            paciente = _identificar(servicio, b)
            if paciente is not None:
                return RedirectResponse(url=f"/citas/mias?b={b}", status_code=303)
            mensaje = "Escriba su DNI, NIE, pasaporte o su código de historia clínica."
        except ErrorDeNegocio as exc:
            mensaje = exc.mensaje

    return plantillas.TemplateResponse(
        request=request,
        name="citas_identificarse.html",
        context={"b": b or "", "mensaje": mensaje, "seccion": "citas"},
    )


@router.get("/citas/mias", response_class=HTMLResponse)
def mis_citas(
    request: Request,
    b: str,
    nueva: str | None = None,
    aviso: str | None = None,
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    """Citas del paciente, con las acciones de cancelar y reprogramar (RF-09)."""
    paciente = _identificar(servicio, b)
    if paciente is None:
        return RedirectResponse(url="/citas", status_code=303)

    ahora = ahora_local()
    citas = servicio.citas_de_paciente(paciente.patient_id)
    return plantillas.TemplateResponse(
        request=request,
        name="citas_mias.html",
        context={
            "b": b,
            "paciente": paciente,
            "futuras": [c for c in citas if not c.es_pasada(ahora)],
            "pasadas": [c for c in citas if c.es_pasada(ahora)],
            "nueva": nueva,
            "aviso": aviso,
            "seccion": "citas",
        },
    )


@router.get("/citas/buscar", response_class=HTMLResponse)
def buscar_cita(
    request: Request,
    b: str,
    especialidad_id: int | None = None,
    centro_id: int | None = None,
    especialista_id: int | None = None,
    desde: date | None = None,
    franja: str | None = None,
    reprogramar: str | None = None,
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    """Búsqueda de disponibilidad y elección de hueco (RF-01 a RF-03).

    La misma pantalla sirve para reservar y para reprogramar: si llega el
    parámetro ``reprogramar`` con el identificador de una cita, el hueco elegido
    se aplica a esa cita en lugar de crear una nueva.
    """
    paciente = _identificar(servicio, b)
    if paciente is None:
        return RedirectResponse(url="/citas", status_code=303)

    inicio = desde or ahora_local().date()
    especialistas = servicio.buscar_especialistas(especialidad_id, centro_id)
    huecos, elegido, mensaje = [], None, None

    # Disponibilidad horaria del paciente (enunciado §3.1).
    hora_desde, hora_hasta = FRANJAS.get(franja or "", (None, None))

    if especialista_id:
        try:
            elegido = servicio.obtener_especialista(especialista_id)
            huecos = servicio.disponibilidad(
                especialista_id, inicio, inicio + timedelta(days=13),
                hora_desde=hora_desde, hora_hasta=hora_hasta,
            )
            if not huecos:
                mensaje = (
                    "No hay huecos libres en las próximas dos semanas"
                    + (" en esa franja horaria." if franja else ".")
                )
        except ErrorDeNegocio as exc:
            mensaje = exc.mensaje

    # Los huecos se agrupan por día para que la pantalla sea legible.
    por_dia: dict[date, list] = {}
    for hueco in huecos:
        por_dia.setdefault(hueco.inicio.date(), []).append(hueco)

    return plantillas.TemplateResponse(
        request=request,
        name="citas_buscar.html",
        context={
            "b": b,
            "paciente": paciente,
            "especialidades": servicio.especialidades(),
            "centros": servicio.centros(),
            "especialistas": especialistas,
            "especialidad_id": especialidad_id,
            "centro_id": centro_id,
            "elegido": elegido,
            "por_dia": por_dia,
            "desde": inicio,
            "franja": franja or "",
            "franjas": FRANJAS_TEXTO,
            "mensaje": mensaje,
            "reprogramar": reprogramar,
            "seccion": "citas",
        },
    )


@router.post("/citas/reservar", response_class=HTMLResponse)
def reservar(
    b: str = Form(...),
    especialista_id: int = Form(...),
    inicio: datetime = Form(...),
    motivo_consulta: str = Form(default=""),
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    """Confirma la reserva del hueco elegido (RF-05)."""
    paciente = _identificar(servicio, b)
    if paciente is None:
        return RedirectResponse(url="/citas", status_code=303)

    try:
        cita = servicio.reservar(
            patient_id=paciente.patient_id,
            especialista_id=especialista_id,
            inicio=inicio,
            motivo_consulta=motivo_consulta,
        )
    except ErrorDeNegocio as exc:
        return RedirectResponse(
            url=f"/citas/buscar?b={b}&especialista_id={especialista_id}&aviso={exc.mensaje}",
            status_code=303,
        )

    return RedirectResponse(url=f"/citas/mias?b={b}&nueva={cita.codigo}", status_code=303)


@router.post("/citas/{cita_id}/cancelar", response_class=HTMLResponse)
def cancelar(
    cita_id: str, b: str = Form(...), servicio: ServicioCitas = Depends(obtener_servicio)
):
    """Cancela una cita del paciente identificado (RF-10)."""
    paciente = _identificar(servicio, b)
    if paciente is None:
        return RedirectResponse(url="/citas", status_code=303)

    try:
        cita = servicio.cancelar(cita_id, patient_id=paciente.patient_id)
        aviso = f"Cita {cita.codigo} cancelada."
    except ErrorDeNegocio as exc:
        aviso = exc.mensaje

    return RedirectResponse(url=f"/citas/mias?b={b}&aviso={aviso}", status_code=303)


@router.post("/citas/{cita_id}/reprogramar", response_class=HTMLResponse)
def reprogramar(
    cita_id: str,
    b: str = Form(...),
    inicio: datetime = Form(...),
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    """Mueve la cita al hueco elegido, conservando su código (RF-11, RF-12)."""
    paciente = _identificar(servicio, b)
    if paciente is None:
        return RedirectResponse(url="/citas", status_code=303)

    try:
        cita = servicio.reprogramar(cita_id, inicio, patient_id=paciente.patient_id)
        aviso = f"Cita {cita.codigo} reprogramada."
    except ErrorDeNegocio as exc:
        aviso = exc.mensaje

    return RedirectResponse(url=f"/citas/mias?b={b}&aviso={aviso}", status_code=303)


# ---------------------------------------------------------------------------
# Zona del personal administrativo
# ---------------------------------------------------------------------------

@router.get("/agenda", response_class=HTMLResponse)
def elegir_especialista(request: Request, servicio: ServicioCitas = Depends(obtener_servicio)):
    """Lista de especialistas para entrar en su agenda (RF-16)."""
    return plantillas.TemplateResponse(
        request=request,
        name="agenda_lista.html",
        context={"especialistas": servicio.buscar_especialistas(), "seccion": "agenda"},
    )


@router.get("/agenda/{especialista_id}", response_class=HTMLResponse)
def ver_agenda(
    request: Request,
    especialista_id: int,
    desde: date | None = None,
    aviso: str | None = None,
    error: str | None = None,
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    """Agenda del especialista: horario, bloqueos y citas (RF-16)."""
    inicio = desde or ahora_local().date()
    datos = servicio.agenda(especialista_id, inicio, inicio + timedelta(days=13))

    pacientes = {
        cita.codigo: servicio.pacientes.obtener(cita.patient_id) for cita in datos["citas"]
    }

    return plantillas.TemplateResponse(
        request=request,
        name="agenda_detalle.html",
        context={
            "especialista": datos["especialista"],
            "horarios": datos["horarios"],
            "bloqueos": datos["bloqueos"],
            "citas": datos["citas"],
            "pacientes": pacientes,
            "desde": inicio,
            "hasta": inicio + timedelta(days=13),
            "motivos": MOTIVOS,
            "aviso": aviso,
            "error": error,
            "seccion": "agenda",
        },
    )


@router.post("/agenda/{especialista_id}/bloqueos")
def crear_bloqueo(
    especialista_id: int,
    inicio: datetime = Form(...),
    fin: datetime = Form(...),
    motivo: str = Form(default=MotivoBloqueo.OTRO.value),
    observaciones: str = Form(default=""),
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    """Bloquea una franja de la agenda (RF-17, RF-18)."""
    try:
        servicio.bloquear(especialista_id, inicio, fin, motivo, observaciones)
        destino = f"/agenda/{especialista_id}?aviso=Franja bloqueada."
    except ErrorDeNegocio as exc:
        detalle = "; ".join(d["mensaje"] for d in exc.detalles) or exc.mensaje
        destino = f"/agenda/{especialista_id}?error={detalle}"

    return RedirectResponse(url=destino, status_code=303)


@router.post("/agenda/{especialista_id}/bloqueos/{bloqueo_id}/levantar")
def levantar_bloqueo(
    especialista_id: int, bloqueo_id: int, servicio: ServicioCitas = Depends(obtener_servicio)
):
    """Levanta un bloqueo y devuelve esos huecos a la disponibilidad (RF-19)."""
    try:
        servicio.levantar_bloqueo(bloqueo_id)
        destino = f"/agenda/{especialista_id}?aviso=Bloqueo levantado."
    except ErrorDeNegocio as exc:
        destino = f"/agenda/{especialista_id}?error={exc.mensaje}"

    return RedirectResponse(url=destino, status_code=303)


@router.post("/agenda/{especialista_id}/duracion")
def cambiar_duracion(
    especialista_id: int,
    duracion_cita_min: int = Form(...),
    servicio: ServicioCitas = Depends(obtener_servicio),
):
    """Ajusta la duración de los huecos del especialista (RF-20)."""
    try:
        especialista = servicio.ajustar_duracion(especialista_id, duracion_cita_min)
        destino = (
            f"/agenda/{especialista_id}?aviso=Duración ajustada a "
            f"{especialista.duracion_cita_min} minutos."
        )
    except ErrorDeNegocio as exc:
        detalle = "; ".join(d["mensaje"] for d in exc.detalles) or exc.mensaje
        destino = f"/agenda/{especialista_id}?error={detalle}"

    return RedirectResponse(url=destino, status_code=303)
