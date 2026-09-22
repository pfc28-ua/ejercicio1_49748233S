"""Núcleo de identidad del paciente.

Genera la identidad única del paciente y valida y normaliza los datos con los
que se construye. Es dominio puro: no depende del framework ni de la base de
datos, y se prueba de forma aislada.

Trazabilidad: spec.md RN-01 a RN-11 y RN-13; plan.md DT-01, DT-06, DT-08;
tasks.md T-04 a T-10.
"""

from __future__ import annotations

import re
import uuid
from datetime import date

#: Tabla oficial de letras de control del DNI (RN-04).
LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"

#: Equivalencia numérica de la letra inicial del NIE (RN-05).
PREFIJOS_NIE = {"X": "0", "Y": "1", "Z": "2"}

#: Edad máxima admitida (RN-07).
EDAD_MAXIMA_ANIOS = 130

#: Formato del código de historia clínica (RN-03).
PREFIJO_HISTORIA = "HC"
ANCHURA_SECUENCIAL = 6
SECUENCIAL_MAXIMO = 10**ANCHURA_SECUENCIAL - 1

_PATRON_DNI = re.compile(r"^\d{8}[A-Z]$")
_PATRON_NIE = re.compile(r"^[XYZ]\d{7}[A-Z]$")
_PATRON_PASAPORTE = re.compile(r"^[A-Z0-9]{5,20}$")
_PATRON_CODIGO_HISTORIA = re.compile(r"^HC-\d{4}-\d{6}$")
_PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_PATRON_CP_ESPANIA = re.compile(r"^\d{5}$")


# --------------------------------------------------------------------------
# Normalización (RN-13, DT-06)
# --------------------------------------------------------------------------

def normalizar_texto(valor: str | None) -> str | None:
    """Elimina los espacios sobrantes. Un texto vacío se convierte en ``None``."""
    if valor is None:
        return None
    limpio = " ".join(valor.split())
    return limpio or None


def normalizar_documento(valor: str | None) -> str | None:
    """Pasa el documento a mayúsculas y le quita espacios, guiones y puntos.

    Gracias a esto ``  12345678-z  `` y ``12345678Z`` son el mismo documento
    (RN-01, CL-01).
    """
    if valor is None:
        return None
    limpio = re.sub(r"[\s\-.]", "", valor).upper()
    return limpio or None


def normalizar_email(valor: str | None) -> str | None:
    """Recorta y pasa el email a minúsculas (RN-09, CL-13)."""
    if valor is None:
        return None
    limpio = valor.strip().lower()
    return limpio or None


def normalizar_telefono(valor: str | None) -> str | None:
    """Deja solo los dígitos del teléfono, conservando el prefijo ``+`` (RN-10, CL-14)."""
    if valor is None:
        return None
    limpio = valor.strip()
    if not limpio:
        return None
    prefijo = "+" if limpio.startswith("+") else ""
    digitos = re.sub(r"\D", "", limpio)
    return f"{prefijo}{digitos}" if digitos else None


def normalizar_codigo_historia(codigo: str | None) -> str | None:
    """Normaliza un código de historia clínica para buscarlo (RF-11)."""
    if codigo is None:
        return None
    limpio = codigo.strip().upper()
    return limpio or None


# --------------------------------------------------------------------------
# Documento de identidad (RN-04, RN-05, RN-06)
# --------------------------------------------------------------------------

def _letra_control(numero: int) -> str:
    return LETRAS_DNI[numero % 23]


def validar_dni(numero: str) -> bool:
    """DNI: 8 dígitos y letra de control correcta (RN-04)."""
    return bool(_PATRON_DNI.match(numero)) and numero[-1] == _letra_control(int(numero[:8]))


def validar_nie(numero: str) -> bool:
    """NIE: X/Y/Z sustituida por 0/1/2, 7 dígitos y letra de control (RN-05)."""
    if not _PATRON_NIE.match(numero):
        return False
    return numero[-1] == _letra_control(int(PREFIJOS_NIE[numero[0]] + numero[1:8]))


def validar_pasaporte(numero: str) -> bool:
    """Pasaporte: entre 5 y 20 caracteres alfanuméricos (RN-06)."""
    return bool(_PATRON_PASAPORTE.match(numero))


def validar_documento(tipo_documento: str, numero_documento: str) -> tuple[bool, str]:
    """Valida un documento según su tipo. Devuelve ``(es_valido, mensaje)``."""
    tipo = (tipo_documento or "").upper()
    numero = numero_documento or ""

    if tipo == "DNI":
        if not _PATRON_DNI.match(numero):
            return False, "El DNI debe tener 8 dígitos seguidos de una letra."
        if not validar_dni(numero):
            return False, "La letra de control del DNI no es correcta."
        return True, ""

    if tipo == "NIE":
        if not _PATRON_NIE.match(numero):
            return False, "El NIE debe empezar por X, Y o Z, seguido de 7 dígitos y una letra."
        if not validar_nie(numero):
            return False, "La letra de control del NIE no es correcta."
        return True, ""

    if tipo == "PASAPORTE":
        if not validar_pasaporte(numero):
            return False, "El pasaporte debe tener entre 5 y 20 caracteres alfanuméricos."
        return True, ""

    return False, "El tipo de documento debe ser DNI, NIE o PASAPORTE."


# --------------------------------------------------------------------------
# Otras reglas de validación
# --------------------------------------------------------------------------

def validar_fecha_nacimiento(fecha: date, hoy: date | None = None) -> tuple[bool, str]:
    """No futura y edad no superior a 130 años (RN-07). Nacido hoy es válido (CL-06)."""
    referencia = hoy or date.today()
    if fecha > referencia:
        return False, "La fecha de nacimiento no puede ser futura."
    if fecha.year < referencia.year - EDAD_MAXIMA_ANIOS:
        return False, f"La fecha de nacimiento implica una edad superior a {EDAD_MAXIMA_ANIOS} años."
    return True, ""


def validar_email(valor: str) -> tuple[bool, str]:
    """Formato de email (RN-09)."""
    if not _PATRON_EMAIL.match(valor):
        return False, "El email no tiene un formato válido."
    return True, ""


def validar_telefono(valor: str) -> tuple[bool, str]:
    """Entre 9 y 15 dígitos (RN-10)."""
    if not 9 <= len(re.sub(r"\D", "", valor)) <= 15:
        return False, "El teléfono debe tener entre 9 y 15 dígitos."
    return True, ""


def validar_codigo_postal(codigo: str, pais: str | None) -> tuple[bool, str]:
    """Formato español solo si el país es España (RN-11, CL-11, CL-12)."""
    if pais and pais.strip().lower() not in {"españa", "espana", "spain", "es"}:
        return True, ""
    if not _PATRON_CP_ESPANIA.match(codigo):
        return False, "El código postal español debe tener 5 dígitos."
    if not 1 <= int(codigo[:2]) <= 52:
        return False, "Los dos primeros dígitos del código postal no corresponden a ninguna provincia."
    return True, ""


# --------------------------------------------------------------------------
# Identidad (RN-02, RN-03, DT-01)
# --------------------------------------------------------------------------

def generar_patient_id() -> str:
    """Genera el identificador interno del paciente: un UUID v4 (RN-02).

    Se crea en el dominio y no como autonumérico de la base de datos, para que
    la identidad no dependa del motor y sea reutilizable por otros módulos
    (DT-01).
    """
    return str(uuid.uuid4())


def formatear_codigo_historia(anio: int, secuencial: int) -> str:
    """Compone el código ``HC-AAAA-NNNNNN`` (RN-03).

    Si el secuencial no cabe en 6 dígitos lanza ``ValueError`` en lugar de
    generar un código con formato inválido (CL-05).
    """
    if secuencial > SECUENCIAL_MAXIMO:
        raise ValueError(
            f"Secuencial de historia clínica agotado para el año {anio}: máximo {SECUENCIAL_MAXIMO}."
        )
    return f"{PREFIJO_HISTORIA}-{anio:04d}-{secuencial:0{ANCHURA_SECUENCIAL}d}"


def es_codigo_historia_valido(codigo: str | None) -> bool:
    """Indica si el texto tiene formato de código de historia clínica (RN-03)."""
    return bool(_PATRON_CODIGO_HISTORIA.match((codigo or "").strip().upper()))


# --------------------------------------------------------------------------
# Buscador de la interfaz web (plan.md DT-08)
# --------------------------------------------------------------------------

def detectar_criterio_busqueda(texto: str | None) -> tuple[str, str | None]:
    """Deduce si el texto del buscador es un código de historia clínica o un documento.

    Devuelve ``(criterio, valor_normalizado)``, con ``criterio`` igual a
    ``HISTORIA``, ``DNI``, ``NIE``, ``PASAPORTE``, ``DESCONOCIDO`` o ``VACIO``.
    Solo reconoce los dos datos por los que la spec permite buscar (RF-10, RF-11).
    """
    if texto is None or not texto.strip():
        return "VACIO", None

    if es_codigo_historia_valido(texto):
        return "HISTORIA", normalizar_codigo_historia(texto)

    documento = normalizar_documento(texto) or ""
    if _PATRON_DNI.match(documento):
        return "DNI", documento
    if _PATRON_NIE.match(documento):
        return "NIE", documento
    if any(c.isdigit() for c in documento) and _PATRON_PASAPORTE.match(documento):
        return "PASAPORTE", documento

    return "DESCONOCIDO", texto.strip()
