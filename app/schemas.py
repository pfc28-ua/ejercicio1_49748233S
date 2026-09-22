"""Contratos de entrada y salida.

Contienen toda la validación de los datos, de modo que la API y la interfaz web
aplican exactamente las mismas reglas (plan.md DT-04).

Trazabilidad: RF-01 a RF-04, RF-08, RF-09, RF-13, RF-17, RF-18, RF-23;
RN-04 a RN-13; tasks.md T-15 a T-18.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app import identity
from app.errors import ErrorDeValidacion
from app.models import Sexo, TipoDocumento

CAMPOS_TEXTO = (
    "nombre",
    "primer_apellido",
    "segundo_apellido",
    "direccion_calle",
    "direccion_ciudad",
    "direccion_cp",
    "direccion_provincia",
    "direccion_pais",
    "entidad_aseguradora",
    "numero_poliza",
)


class _Normalizacion(BaseModel):
    """Normaliza los datos al recibirlos, antes de validarlos (RN-13, DT-06)."""

    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True)

    @field_validator(*CAMPOS_TEXTO, mode="before", check_fields=False)
    @classmethod
    def _texto(cls, valor: Any) -> Any:
        return identity.normalizar_texto(valor) if isinstance(valor, str) else valor

    @field_validator("numero_documento", mode="before", check_fields=False)
    @classmethod
    def _documento(cls, valor: Any) -> Any:
        return identity.normalizar_documento(valor) if isinstance(valor, str) else valor

    @field_validator("email", mode="before", check_fields=False)
    @classmethod
    def _email(cls, valor: Any) -> Any:
        return identity.normalizar_email(valor) if isinstance(valor, str) else valor

    @field_validator("telefono", mode="before", check_fields=False)
    @classmethod
    def _telefono(cls, valor: Any) -> Any:
        return identity.normalizar_telefono(valor) if isinstance(valor, str) else valor


# --------------------------------------------------------------------------
# Reglas de negocio comunes
# --------------------------------------------------------------------------

def validar_reglas(datos: dict) -> list[dict]:
    """Aplica las reglas de negocio a los datos presentes y acumula los errores.

    Solo comprueba los campos que vienen en ``datos``, por lo que sirve tanto para
    el alta como para una modificación parcial. Devolver todos los errores, y no
    solo el primero, es lo que exige RF-08.
    """
    errores: list[dict] = []

    def error(campo: str, mensaje: str) -> None:
        errores.append({"campo": campo, "mensaje": mensaje})

    if datos.get("numero_documento") and datos.get("tipo_documento"):
        valido, mensaje = identity.validar_documento(
            str(datos["tipo_documento"]), datos["numero_documento"]
        )
        if not valido:
            error("numero_documento", mensaje)

    if isinstance(datos.get("fecha_nacimiento"), date):
        valido, mensaje = identity.validar_fecha_nacimiento(datos["fecha_nacimiento"])
        if not valido:
            error("fecha_nacimiento", mensaje)

    if datos.get("email"):
        valido, mensaje = identity.validar_email(datos["email"])
        if not valido:
            error("email", mensaje)

    if datos.get("telefono"):
        valido, mensaje = identity.validar_telefono(datos["telefono"])
        if not valido:
            error("telefono", mensaje)

    if datos.get("direccion_cp"):
        valido, mensaje = identity.validar_codigo_postal(
            datos["direccion_cp"], datos.get("direccion_pais")
        )
        if not valido:
            error("direccion_cp", mensaje)

    return errores


def _errores_de_pydantic(exc: ValidationError) -> list[dict]:
    """Convierte los errores de Pydantic al formato de detalle por campo."""
    detalles = []
    for e in exc.errors():
        original = e.get("ctx", {}).get("error")
        if isinstance(original, ErrorDeValidacion):
            detalles.extend(original.detalles)
            continue
        campo = ".".join(str(p) for p in e.get("loc", ())) or "cuerpo"
        detalles.append({"campo": campo, "mensaje": _traducir(e)})
    return detalles


def _traducir(error: dict) -> str:
    """Mensajes en español para los errores de formato más habituales."""
    tipo = error.get("type", "")
    ctx = error.get("ctx", {})
    if tipo == "missing":
        return "Este dato es obligatorio."
    if tipo == "string_too_short":
        return f"Debe tener al menos {ctx.get('min_length')} caracteres."
    if tipo == "string_too_long":
        return f"No puede superar {ctx.get('max_length')} caracteres."
    if tipo.startswith("date"):
        return "La fecha no es válida."
    if tipo == "enum":
        return f"Valor no admitido. Opciones: {ctx.get('expected')}."
    return error.get("msg", "Dato no válido.")


def _datos_en_bruto_para_reglas(datos: Any) -> dict:
    """Prepara los datos sin validar para aplicarles las reglas de negocio (DT-04)."""
    if not isinstance(datos, dict):
        return {}

    def texto(clave: str) -> str | None:
        valor = datos.get(clave)
        return valor if isinstance(valor, str) else None

    fecha = datos.get("fecha_nacimiento")
    if isinstance(fecha, str):
        try:
            fecha = date.fromisoformat(fecha.strip())
        except ValueError:
            fecha = None

    return {
        "tipo_documento": texto("tipo_documento"),
        "numero_documento": identity.normalizar_documento(texto("numero_documento")),
        "fecha_nacimiento": fecha if isinstance(fecha, date) else None,
        "email": identity.normalizar_email(texto("email")),
        "telefono": identity.normalizar_telefono(texto("telefono")),
        "direccion_cp": identity.normalizar_texto(texto("direccion_cp")),
        "direccion_pais": identity.normalizar_texto(texto("direccion_pais")),
    }


# --------------------------------------------------------------------------
# Contratos de entrada
# --------------------------------------------------------------------------

class PacienteCrear(_Normalizacion):
    """Datos para registrar un paciente (RF-01 a RF-04).

    No incluye ``patient_id`` ni ``codigo_historia_clinica``: los genera el
    sistema y, si llegan, se ignoran (RF-06).
    """

    # Documento de identidad (RF-02)
    tipo_documento: TipoDocumento
    numero_documento: str = Field(min_length=1, max_length=20)

    # Datos personales (RF-01, RN-08)
    nombre: str = Field(min_length=2, max_length=60)
    primer_apellido: str = Field(min_length=2, max_length=60)
    segundo_apellido: str | None = Field(default=None, max_length=60)
    fecha_nacimiento: date
    sexo: Sexo = Sexo.NO_DECLARA

    # Datos de contacto, opcionales (RF-03)
    telefono: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=120)
    direccion_calle: str | None = Field(default=None, max_length=120)
    direccion_ciudad: str | None = Field(default=None, max_length=80)
    direccion_cp: str | None = Field(default=None, max_length=10)
    direccion_provincia: str | None = Field(default=None, max_length=80)
    direccion_pais: str | None = Field(default="España", max_length=80)

    # Seguro o mutua, obligatorio (RF-04, RN-12)
    entidad_aseguradora: str = Field(min_length=1, max_length=120)
    numero_poliza: str = Field(min_length=1, max_length=60)

    @model_validator(mode="wrap")
    @classmethod
    def _todos_los_errores(cls, datos: Any, validar):
        """Devuelve juntos los errores de formato y los de reglas de negocio (RF-08).

        Si un campo falla el formato, Pydantic no llega a aplicar las reglas de
        negocio; aquí se aplican igualmente sobre los datos en bruto para no
        perder ningún error (DT-04, CA-11).
        """
        try:
            paciente = validar(datos)
        except ValidationError as exc:
            detalles = _errores_de_pydantic(exc)
            ya_indicados = {d["campo"] for d in detalles}
            detalles += [
                d for d in validar_reglas(_datos_en_bruto_para_reglas(datos))
                if d["campo"] not in ya_indicados
            ]
            raise ErrorDeValidacion(detalles=detalles) from exc

        errores = validar_reglas(paciente.model_dump())
        if errores:
            raise ErrorDeValidacion(detalles=errores)
        return paciente


class PacienteModificar(_Normalizacion):
    """Datos para modificar un paciente (RF-15 a RF-18).

    Todos los campos son opcionales: solo se modifican los que se envían
    (RF-17). Un dato opcional enviado vacío se borra (RF-18). Los campos de
    identidad no existen en este contrato, así que si llegan se ignoran (RF-20).
    """

    model_config = ConfigDict(str_strip_whitespace=True, use_enum_values=True, extra="ignore")

    tipo_documento: TipoDocumento | None = None
    numero_documento: str | None = Field(default=None, max_length=20)

    nombre: str | None = Field(default=None, max_length=60)
    primer_apellido: str | None = Field(default=None, max_length=60)
    segundo_apellido: str | None = Field(default=None, max_length=60)
    fecha_nacimiento: date | None = None
    sexo: Sexo | None = None

    telefono: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=120)
    direccion_calle: str | None = Field(default=None, max_length=120)
    direccion_ciudad: str | None = Field(default=None, max_length=80)
    direccion_cp: str | None = Field(default=None, max_length=10)
    direccion_provincia: str | None = Field(default=None, max_length=80)
    direccion_pais: str | None = Field(default=None, max_length=80)

    entidad_aseguradora: str | None = Field(default=None, max_length=120)
    numero_poliza: str | None = Field(default=None, max_length=60)

    def cambios(self) -> dict[str, Any]:
        """Solo los campos enviados (RF-17, DT-03)."""
        return self.model_dump(exclude_unset=True)


# --------------------------------------------------------------------------
# Contratos de salida
# --------------------------------------------------------------------------

class PacienteRespuesta(BaseModel):
    """Ficha del paciente con su identidad (RF-09, RF-13, RF-14)."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    codigo_historia_clinica: str

    tipo_documento: str
    numero_documento: str

    nombre: str
    primer_apellido: str
    segundo_apellido: str | None
    fecha_nacimiento: date
    sexo: str

    telefono: str | None
    email: str | None
    direccion_calle: str | None
    direccion_ciudad: str | None
    direccion_cp: str | None
    direccion_provincia: str | None
    direccion_pais: str | None

    entidad_aseguradora: str
    numero_poliza: str

    fecha_alta: datetime


class DetalleError(BaseModel):
    """Error de un campo concreto (RF-23)."""

    campo: str
    mensaje: str


class ErrorRespuesta(BaseModel):
    """Formato uniforme de error (RF-23)."""

    codigo: str
    mensaje: str
    detalles: list[DetalleError] | None = None
    codigo_historia_clinica: str | None = None
    patient_id: str | None = None
