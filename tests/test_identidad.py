"""Pruebas unitarias del núcleo de identidad (plan.md §7, tasks.md T-11)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from app import identity


# Documento de identidad (RN-04, RN-05, RN-06) ------------------------------

@pytest.mark.parametrize("numero", ["12345678Z", "00000000T", "11111111H"])
def test_dni_valido(numero):
    assert identity.validar_dni(numero)


@pytest.mark.parametrize("numero", ["12345678A", "1234567Z", "123456789Z"])
def test_dni_invalido(numero):
    assert not identity.validar_dni(numero)


@pytest.mark.parametrize("numero", ["X1234567L", "Y0000000Z", "Z0000000M"])
def test_nie_valido(numero):
    assert identity.validar_nie(numero)


@pytest.mark.parametrize("numero", ["X1234567A", "W1234567L"])
def test_nie_invalido(numero):
    assert not identity.validar_nie(numero)


@pytest.mark.parametrize("numero,valido", [("AB123456", True), ("12345", True), ("AB12", False), ("A" * 21, False)])
def test_pasaporte(numero, valido):
    assert identity.validar_pasaporte(numero) is valido


# Normalización (RN-01, RN-09, RN-10, RN-13) --------------------------------

@pytest.mark.parametrize("entrada,esperado", [("  12345678-z  ", "12345678Z"), ("x1234567.l", "X1234567L")])
def test_normalizar_documento(entrada, esperado):
    """CL-01."""
    assert identity.normalizar_documento(entrada) == esperado


def test_normalizar_email():
    """CL-13."""
    assert identity.normalizar_email(" ANA@Mail.COM ") == "ana@mail.com"


def test_normalizar_telefono():
    """CL-14."""
    assert identity.normalizar_telefono("+34 600 11 22 33") == "+34600112233"


# Otras reglas (RN-07, RN-11) ------------------------------------------------

def test_nacido_hoy_es_valido():
    """CL-06."""
    assert identity.validar_fecha_nacimiento(date.today())[0]


def test_fecha_futura_no_es_valida():
    assert not identity.validar_fecha_nacimiento(date.today() + timedelta(days=1))[0]


def test_mas_de_130_anios_no_es_valido():
    """CL-07."""
    assert not identity.validar_fecha_nacimiento(date(date.today().year - 131, 1, 1))[0]


def test_codigo_postal_espanol():
    """CL-11 y CL-12."""
    assert identity.validar_codigo_postal("28013", "España")[0]
    assert not identity.validar_codigo_postal("99999", "España")[0]
    assert identity.validar_codigo_postal("1000-001", "Portugal")[0]


# Identidad (RN-02, RN-03) ---------------------------------------------------

def test_patient_id_es_uuid_v4_unico():
    generados = {identity.generar_patient_id() for _ in range(100)}
    assert len(generados) == 100
    assert all(uuid.UUID(v).version == 4 for v in generados)


def test_formato_del_codigo_de_historia():
    assert identity.formatear_codigo_historia(2026, 1) == "HC-2026-000001"


def test_codigo_de_historia_por_anio():
    """CL-04."""
    assert identity.formatear_codigo_historia(2027, 1) == "HC-2027-000001"


def test_secuencial_agotado():
    """CL-05."""
    with pytest.raises(ValueError):
        identity.formatear_codigo_historia(2026, 1_000_000)


# Buscador de la interfaz (DT-08) -------------------------------------------

@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("hc-2026-000001", ("HISTORIA", "HC-2026-000001")),
        ("1234 5678-z", ("DNI", "12345678Z")),
        ("x1234567l", ("NIE", "X1234567L")),
        ("AB123456", ("PASAPORTE", "AB123456")),
        ("María López", ("DESCONOCIDO", "María López")),
        ("  ", ("VACIO", None)),
    ],
)
def test_detectar_criterio_busqueda(texto, esperado):
    assert identity.detectar_criterio_busqueda(texto) == esperado
