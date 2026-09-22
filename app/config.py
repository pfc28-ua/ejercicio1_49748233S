"""Configuración de la aplicación (tasks.md T-03)."""

from __future__ import annotations

import os
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

# Ruta de la base de datos. Configurable por entorno para poder usar otra
# base de datos sin tocar el código (plan.md §2).
URL_BASE_DATOS = os.getenv(
    "HIS_DATABASE_URL",
    f"sqlite:///{RAIZ_PROYECTO / 'his_registro.db'}",
)
