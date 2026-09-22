"""Punto de entrada de la aplicación.

Monta la API REST (RF-21) y la interfaz web (RF-22) y aplica el formato uniforme
de error (RF-23, plan.md DT-05).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_pacientes import router as router_api
from app.citas.api_routes import router as router_api_citas
from app.citas.web_routes import router as router_web_citas
from app.database import crear_esquema
from app.errors import ErrorDeNegocio
from app.schemas import _traducir
from app.web.routes_web import router as router_web


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    """Crea las tablas al arrancar si no existen.

    Se importan también las entidades del módulo de citas (ejercicio 2) para que
    sus tablas formen parte del esquema.
    """
    from app.citas import models as _modelos_citas  # noqa: F401

    crear_esquema()
    yield


app = FastAPI(
    title="HIS · Registro e Identificación de Pacientes",
    description="Registro, búsqueda y verificación, y modificación de los datos del paciente, "
    "con una identidad única reutilizable por el resto de módulos del HIS.",
    version="1.0.0",
    lifespan=ciclo_de_vida,
)

app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")
app.include_router(router_api)
app.include_router(router_web)
# Módulo de citas (ejercicio 2), que amplía el de registro sin modificarlo.
app.include_router(router_api_citas)
app.include_router(router_web_citas)


TITULOS_ERROR = {
    404: "No lo hemos encontrado",
    409: "No se puede hacer",
    422: "Datos no válidos",
}


def _es_peticion_web(peticion: Request) -> bool:
    """Distingue una pantalla de la aplicación de una llamada a la API."""
    return not peticion.url.path.startswith("/api/")


def _respuesta_de_error(peticion: Request, estado: int, cuerpo: dict):
    """Devuelve el error como página o como JSON, según quién pregunte (RF-23).

    La API contesta siempre en el formato uniforme. La interfaz web muestra una
    página con el diseño de la aplicación, en lugar del JSON en crudo.
    """
    if _es_peticion_web(peticion):
        from app.web.routes_web import plantillas

        return plantillas.TemplateResponse(
            request=peticion,
            name="error.html",
            context={
                "estado": estado,
                "titulo": TITULOS_ERROR.get(estado, "Algo no ha salido bien"),
                "mensaje": cuerpo.get("mensaje", ""),
                "detalles": cuerpo.get("detalles"),
                "seccion": None,
            },
            status_code=estado,
        )
    return JSONResponse(status_code=estado, content=cuerpo)


@app.exception_handler(ErrorDeNegocio)
async def _error_de_negocio(peticion: Request, exc: ErrorDeNegocio):
    """Errores de negocio con su código HTTP y el formato uniforme (RF-23)."""
    return _respuesta_de_error(peticion, exc.estado_http, exc.a_dict())


@app.exception_handler(RequestValidationError)
async def _error_de_formato(peticion: Request, exc: RequestValidationError):
    """Errores de formato de la petición con el mismo formato uniforme (RF-23)."""
    detalles = []
    for error in exc.errors():
        partes = [str(p) for p in error.get("loc", ()) if p not in ("body", "query", "path")]
        detalles.append({"campo": ".".join(partes) or "cuerpo", "mensaje": _traducir(error)})
    return _respuesta_de_error(
        peticion,
        422,
        {"codigo": "VALIDACION", "mensaje": "Los datos enviados no son válidos.", "detalles": detalles},
    )
