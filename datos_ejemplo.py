"""Pacientes de ejemplo para la demostración (tasks.md T-39).

Uso:  python datos_ejemplo.py
"""

from __future__ import annotations

from app.database import FabricaSesion, crear_esquema
from app.errors import PacienteDuplicado
from app.schemas import PacienteCrear
from app.services import ServicioPacientes

PACIENTES = [
    {
        "tipo_documento": "DNI", "numero_documento": "12345678Z",
        "nombre": "María", "primer_apellido": "López", "segundo_apellido": "García",
        "fecha_nacimiento": "1985-03-12", "sexo": "MUJER",
        "telefono": "+34 600 11 22 33", "email": "maria.lopez@example.com",
        "direccion_calle": "Calle Mayor 3", "direccion_ciudad": "Madrid",
        "direccion_cp": "28013", "direccion_provincia": "Madrid",
        "entidad_aseguradora": "Mutua Sanitaria", "numero_poliza": "POL-998877",
    },
    {
        "tipo_documento": "DNI", "numero_documento": "00000000T",
        "nombre": "Juan", "primer_apellido": "Martín", "segundo_apellido": "Ruiz",
        "fecha_nacimiento": "1972-11-30", "sexo": "HOMBRE",
        "telefono": "611223344", "direccion_ciudad": "Alcalá de Henares", "direccion_cp": "28801",
        "entidad_aseguradora": "Sistema Nacional de Salud", "numero_poliza": "BBBB1234567890",
    },
    {
        "tipo_documento": "NIE", "numero_documento": "X1234567L",
        "nombre": "Ana", "primer_apellido": "Ferreira",
        "fecha_nacimiento": "1998-07-04", "sexo": "MUJER",
        "email": "ana.ferreira@example.com",
        "entidad_aseguradora": "Seguros Salud", "numero_poliza": "SP-445566",
    },
]


def main() -> None:
    crear_esquema()
    with FabricaSesion() as sesion:
        servicio = ServicioPacientes(sesion)
        for datos in PACIENTES:
            try:
                paciente = servicio.registrar(PacienteCrear(**datos))
                print(f"  registrado: {paciente.nombre_completo} -> {paciente.codigo_historia_clinica}")
            except PacienteDuplicado as exc:
                print(f"  ya existía: {datos['numero_documento']} -> {exc.codigo_historia_clinica}")
    print("\nArranque la aplicación con: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
