"""Interfaz web para el personal administrativo (RF-22).

Usa los mismos casos de uso y validaciones que la API: aquí no hay reglas de
negocio (plan.md §1). El flujo es el de admisión: primero se busca y, si el
paciente no existe, se ofrece registrarlo (ESC-01, ESC-02).

Trazabilidad: plan.md §5.1 y DT-08, tasks.md T-34 a T-36.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import identity
from app.database import obtener_sesion
from app.errors import ErrorDeNegocio, PacienteDuplicado
from app.models import Paciente, Sexo, TipoDocumento
from app.schemas import PacienteCrear, PacienteModificar
from app.services import CAMPOS_MODIFICABLES, ServicioPacientes

router = APIRouter(include_in_schema=False)

plantillas = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

ETIQUETAS = {
    "MUJER": "Mujer",
    "HOMBRE": "Hombre",
    "OTRO": "Otro",
    "NO_DECLARA": "No declara",
    "PASAPORTE": "Pasaporte",
}

plantillas.env.filters["tono"] = lambda texto: sum(ord(c) for c in texto or "") % 360
plantillas.env.filters["fecha"] = lambda valor: valor.strftime("%d/%m/%Y") if valor else "—"
plantillas.env.filters["etiqueta"] = lambda valor: ETIQUETAS.get(str(valor), str(valor)) if valor else "—"

LISTAS = {
    "tipos_documento": [t.value for t in TipoDocumento],
    "sexos": [s.value for s in Sexo],
}


def obtener_servicio(sesion: Session = Depends(obtener_sesion)) -> ServicioPacientes:
    return ServicioPacientes(sesion)


def _errores(exc: ErrorDeNegocio) -> dict[str, str]:
    return {d["campo"]: d["mensaje"] for d in exc.detalles}


def _barras(paciente: Paciente) -> list[int]:
    """Anchuras del código de barras decorativo de la pulsera."""
    semilla = paciente.codigo_historia_clinica + paciente.patient_id.replace("-", "")[:18]
    return [(ord(c) % 4) + 1 for c in semilla]


# Capacidad B · Búsqueda ------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def busqueda(
    request: Request,
    b: str | None = None,
    tipo_documento: str | None = None,
    numero_documento: str | None = None,
    servicio: ServicioPacientes = Depends(obtener_servicio),
):
    """Busca por documento o código de historia clínica con una sola caja (RF-10, RF-11).

    También admite ``tipo_documento`` y ``numero_documento`` explícitos.
    """
    if tipo_documento and numero_documento:
        criterio, valor = tipo_documento.upper(), identity.normalizar_documento(numero_documento)
        b = numero_documento
    else:
        criterio, valor = identity.detectar_criterio_busqueda(b)

    paciente = None
    mensaje = None
    try:
        if criterio == "HISTORIA":
            paciente = servicio.buscar_por_codigo_historia(valor)
        elif criterio in {"DNI", "NIE", "PASAPORTE"}:
            paciente = servicio.buscar_por_documento(criterio, valor)
        elif criterio == "DESCONOCIDO":
            mensaje = "Escriba un DNI, NIE, pasaporte o código de historia clínica (HC-AAAA-NNNNNN)."
    except ErrorDeNegocio as exc:
        mensaje = exc.mensaje

    if paciente is not None:
        return RedirectResponse(url=f"/pacientes/{paciente.patient_id}", status_code=303)

    es_documento = criterio in {"DNI", "NIE", "PASAPORTE"}
    return plantillas.TemplateResponse(
        request=request,
        name="busqueda.html",
        context={
            "b": b or "",
            "criterio": criterio,
            "mensaje": mensaje,
            "ofrecer_alta": es_documento or criterio == "HISTORIA",
            "alta_documento": valor if es_documento else "",
            "alta_tipo": criterio if es_documento else "DNI",
            "seccion": "buscar",
        },
    )


# Capacidad A · Registro ------------------------------------------------------

@router.get("/pacientes/nuevo", response_class=HTMLResponse)
def formulario_registro(request: Request, numero_documento: str = "", tipo_documento: str = "DNI"):
    datos = {
        "tipo_documento": tipo_documento,
        "numero_documento": numero_documento,
        "sexo": Sexo.NO_DECLARA.value,
        "direccion_pais": "España",
    }
    return plantillas.TemplateResponse(
        request=request,
        name="alta.html",
        context={"datos": datos, "errores": {}, "mensaje": None, "duplicado": None, "seccion": "nuevo", **LISTAS},
    )


@router.post("/pacientes/nuevo", response_class=HTMLResponse)
async def registrar(request: Request, servicio: ServicioPacientes = Depends(obtener_servicio)):
    formulario = dict(await request.form())
    contexto = {"datos": formulario, "errores": {}, "mensaje": None, "duplicado": None, "seccion": "nuevo", **LISTAS}

    try:
        datos = PacienteCrear(**{k: v for k, v in formulario.items() if v != ""})
        paciente = servicio.registrar(datos)
    except PacienteDuplicado as exc:
        contexto["mensaje"] = exc.mensaje
        contexto["duplicado"] = {"patient_id": exc.patient_id, "codigo_historia_clinica": exc.codigo_historia_clinica}
        return plantillas.TemplateResponse(request=request, name="alta.html", context=contexto, status_code=409)
    except ErrorDeNegocio as exc:
        contexto["mensaje"] = "Revise los datos marcados."
        contexto["errores"] = _errores(exc)
        return plantillas.TemplateResponse(request=request, name="alta.html", context=contexto, status_code=422)

    return RedirectResponse(url=f"/pacientes/{paciente.patient_id}?alta=1", status_code=303)


# Capacidad B · Ficha y verificación -----------------------------------------

@router.get("/pacientes/{patient_id}", response_class=HTMLResponse)
def ficha(request: Request, patient_id: str, alta: int = 0, guardado: int = 0,
          servicio: ServicioPacientes = Depends(obtener_servicio)):
    """Ficha con los datos identificativos para verificar la identidad (RF-13)."""
    paciente = servicio.obtener(patient_id)
    return plantillas.TemplateResponse(
        request=request,
        name="ficha.html",
        context={
            "paciente": paciente,
            "barras": _barras(paciente),
            "recien_creado": bool(alta),
            "guardado": bool(guardado),
            "seccion": "ficha",
        },
    )


# Capacidad C · Modificación -------------------------------------------------

@router.get("/pacientes/{patient_id}/editar", response_class=HTMLResponse)
def formulario_modificacion(request: Request, patient_id: str,
                            servicio: ServicioPacientes = Depends(obtener_servicio)):
    paciente = servicio.obtener(patient_id)
    datos = {}
    for campo in CAMPOS_MODIFICABLES:
        valor = getattr(paciente, campo)
        datos[campo] = valor.isoformat() if isinstance(valor, date) else (valor or "")
    return plantillas.TemplateResponse(
        request=request,
        name="editar.html",
        context={"paciente": paciente, "datos": datos, "errores": {}, "mensaje": None, "seccion": "ficha", **LISTAS},
    )


@router.post("/pacientes/{patient_id}/editar", response_class=HTMLResponse)
async def modificar(request: Request, patient_id: str, servicio: ServicioPacientes = Depends(obtener_servicio)):
    """Guarda la modificación. El formulario envía todos los campos; los vacíos se borran (RF-18)."""
    formulario = dict(await request.form())

    try:
        servicio.modificar(patient_id, PacienteModificar(**formulario))
    except ErrorDeNegocio as exc:
        servicio.sesion.rollback()
        return plantillas.TemplateResponse(
            request=request,
            name="editar.html",
            context={
                "paciente": servicio.obtener(patient_id),
                "datos": formulario,
                "errores": _errores(exc),
                "mensaje": exc.mensaje if isinstance(exc, PacienteDuplicado) else "Revise los datos marcados.",
                "seccion": "ficha",
                **LISTAS,
            },
            status_code=exc.estado_http,
        )

    return RedirectResponse(url=f"/pacientes/{patient_id}?guardado=1", status_code=303)
