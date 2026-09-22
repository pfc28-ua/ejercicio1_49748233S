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
from app.database import crear_esquema
from app.errors import ErrorDeNegocio
from app.schemas import _traducir
from app.web.routes_web import router as router_web


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    """Crea las tablas al arrancar si no existen."""
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


@app.exception_handler(ErrorDeNegocio)
async def _error_de_negocio(_peticion: Request, exc: ErrorDeNegocio) -> JSONResponse:
    """Errores de negocio con su código HTTP y el formato uniforme (RF-23)."""
    return JSONResponse(status_code=exc.estado_http, content=exc.a_dict())


@app.exception_handler(RequestValidationError)
async def _error_de_formato(_peticion: Request, exc: RequestValidationError) -> JSONResponse:
    """Errores de formato de la petición con el mismo formato uniforme (RF-23)."""
    detalles = []
    for error in exc.errors():
        partes = [str(p) for p in error.get("loc", ()) if p not in ("body", "query", "path")]
        detalles.append({"campo": ".".join(partes) or "cuerpo", "mensaje": _traducir(error)})
    return JSONResponse(
        status_code=422,
        content={"codigo": "VALIDACION", "mensaje": "Los datos enviados no son válidos.", "detalles": detalles},
    )
