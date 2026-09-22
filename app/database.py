"""Motor y sesión de base de datos.

Aísla la tecnología de persistencia del resto de la aplicación: cambiar SQLite
por PostgreSQL es cambiar la URL de conexión (plan.md §2, tasks.md T-03).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import URL_BASE_DATOS


class Base(DeclarativeBase):
    """Clase base declarativa de las entidades."""


def crear_motor(url: str = URL_BASE_DATOS):
    """Crea el motor de SQLAlchemy con los ajustes propios de SQLite."""
    argumentos: dict = {}
    if url.startswith("sqlite"):
        # FastAPI atiende peticiones en varios hilos; SQLite lo exige.
        argumentos["connect_args"] = {"check_same_thread": False}
    return create_engine(url, future=True, **argumentos)


motor = crear_motor()


@event.listens_for(motor, "connect")
def _activar_claves_foraneas(conexion, _registro) -> None:
    """SQLite no aplica las claves foráneas si no se piden explícitamente."""
    cursor = conexion.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


FabricaSesion = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False, future=True)


def crear_esquema(motor_destino=None) -> None:
    """Crea las tablas si no existen (tasks.md T-03)."""
    from app import models  # noqa: F401  (registra las entidades en los metadatos)

    Base.metadata.create_all(bind=motor_destino or motor)


def obtener_sesion() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición."""
    sesion = FabricaSesion()
    try:
        yield sesion
    finally:
        sesion.close()
