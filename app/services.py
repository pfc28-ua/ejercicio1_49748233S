"""Casos de uso del módulo.

Implementan las tres capacidades de la especificación:

- A · Registro e identificación  → :meth:`ServicioPacientes.registrar`
- B · Búsqueda y verificación    → ``buscar_por_documento``, ``buscar_por_codigo_historia``, ``obtener``
- C · Modificación               → :meth:`ServicioPacientes.modificar`

No dependen de HTTP: reciben contratos y lanzan errores de negocio (plan.md §1).

Trazabilidad: RF-05 a RF-20; tasks.md T-19, T-20, T-23 a T-25, T-28 a T-30.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import identity
from app.errors import ErrorDeValidacion, PacienteDuplicado, PacienteNoEncontrado
from app.models import Paciente, ahora_utc
from app.repository import RepositorioPacientes
from app.schemas import PacienteCrear, PacienteModificar, validar_reglas

#: Campos que pueden modificarse. La identidad no está: es inmutable (RF-20).
CAMPOS_MODIFICABLES = (
    "tipo_documento",
    "numero_documento",
    "nombre",
    "primer_apellido",
    "segundo_apellido",
    "fecha_nacimiento",
    "sexo",
    "telefono",
    "email",
    "direccion_calle",
    "direccion_ciudad",
    "direccion_cp",
    "direccion_provincia",
    "direccion_pais",
    "entidad_aseguradora",
    "numero_poliza",
)

#: Campos obligatorios: no pueden quedar vacíos al modificar (RF-18, RN-08, RN-12).
CAMPOS_OBLIGATORIOS = (
    "tipo_documento",
    "numero_documento",
    "nombre",
    "primer_apellido",
    "fecha_nacimiento",
    "sexo",
    "entidad_aseguradora",
    "numero_poliza",
)


class ServicioPacientes:
    """Casos de uso del registro e identificación de pacientes."""

    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion
        self.repo = RepositorioPacientes(sesion)

    # ------------------------------------------------------------------
    # Capacidad A · Registro e identificación
    # ------------------------------------------------------------------

    def registrar(self, datos: PacienteCrear) -> Paciente:
        """Registra un paciente y le asocia su identidad única (RF-05 a RF-09).

        1. Comprueba que el documento no esté ya registrado (RF-07).
        2. Genera el ``patient_id`` y el código de historia clínica (RF-05).
        3. Guarda todo en una única transacción.

        La comprobación del paso 1 permite informar del código de historia
        clínica existente; la garantía de unicidad la da la base de datos (DT-02).
        """
        existente = self.repo.obtener_por_documento(datos.tipo_documento, datos.numero_documento)
        if existente is not None:
            raise PacienteDuplicado(
                mensaje=(
                    f"Ya existe un paciente con el documento "
                    f"{datos.tipo_documento} {datos.numero_documento}."
                ),
                codigo_historia_clinica=existente.codigo_historia_clinica,
                patient_id=existente.patient_id,
            )

        paciente = Paciente(
            patient_id=identity.generar_patient_id(),
            codigo_historia_clinica=self.repo.siguiente_codigo_historia(),
            fecha_alta=ahora_utc(),
            **datos.model_dump(),
        )
        self.repo.anadir(paciente)

        try:
            self.sesion.commit()
        except IntegrityError as exc:
            # Otra alta con el mismo documento se ha adelantado (CL-02).
            self.sesion.rollback()
            raise PacienteDuplicado() from exc

        self.sesion.refresh(paciente)
        return paciente

    # ------------------------------------------------------------------
    # Capacidad B · Búsqueda y verificación de identidad
    # ------------------------------------------------------------------

    def buscar_por_documento(self, tipo_documento: str, numero_documento: str) -> Paciente:
        """Busca un paciente por su documento de identidad (RF-10, RF-12)."""
        paciente = self.repo.obtener_por_documento(tipo_documento, numero_documento)
        if paciente is None:
            raise PacienteNoEncontrado(
                f"No existe ningún paciente con el documento {str(tipo_documento).upper()} "
                f"{identity.normalizar_documento(numero_documento)}."
            )
        return paciente

    def buscar_por_codigo_historia(self, codigo: str) -> Paciente:
        """Busca un paciente por su código de historia clínica (RF-11, RF-12, CL-15)."""
        if not identity.es_codigo_historia_valido(codigo):
            raise ErrorDeValidacion(
                detalles=[{
                    "campo": "codigo_historia_clinica",
                    "mensaje": "El código de historia clínica debe tener el formato HC-AAAA-NNNNNN.",
                }]
            )
        paciente = self.repo.obtener_por_codigo_historia(codigo)
        if paciente is None:
            raise PacienteNoEncontrado(
                f"No existe ningún paciente con el código de historia clínica "
                f"{identity.normalizar_codigo_historia(codigo)}."
            )
        return paciente

    def obtener(self, patient_id: str) -> Paciente:
        """Recupera un paciente por su identificador interno (RF-14).

        Es la operación con la que otros módulos del HIS reutilizarán la identidad.
        """
        paciente = self.repo.obtener_por_id(patient_id)
        if paciente is None:
            raise PacienteNoEncontrado(f"No existe ningún paciente con el identificador {patient_id}.")
        return paciente

    # ------------------------------------------------------------------
    # Capacidad C · Modificación y actualización de datos
    # ------------------------------------------------------------------

    def modificar(self, patient_id: str, datos: PacienteModificar) -> Paciente:
        """Modifica o completa los datos de un paciente (RF-15 a RF-20).

        Solo cambian los datos enviados (RF-17); un dato opcional enviado vacío
        se borra (RF-18). La identidad no se toca nunca (RF-20).
        """
        paciente = self.obtener(patient_id)
        cambios = datos.cambios()

        if not cambios:
            raise ErrorDeValidacion(
                mensaje="No se ha indicado ningún dato para modificar.",
                detalles=[{"campo": "cuerpo", "mensaje": "Envíe al menos un dato."}],
            )

        # Valores resultantes: "" o None en un campo opcional significa vaciarlo.
        nuevos: dict = {}
        errores: list[dict] = []
        for campo, valor in cambios.items():
            if campo not in CAMPOS_MODIFICABLES:
                continue
            if valor is None or (isinstance(valor, str) and not valor.strip()):
                if campo in CAMPOS_OBLIGATORIOS:
                    errores.append({"campo": campo, "mensaje": "Este dato es obligatorio."})
                    continue
                valor = None
            nuevos[campo] = valor

        for campo in ("nombre", "primer_apellido"):
            if nuevos.get(campo) is not None and len(nuevos[campo]) < 2:
                errores.append({"campo": campo, "mensaje": "Debe tener al menos 2 caracteres."})

        # Las reglas se aplican sobre la ficha tal como quedaría (por ejemplo,
        # un número de documento nuevo se valida con el tipo ya guardado).
        resultado = {c: getattr(paciente, c) for c in CAMPOS_MODIFICABLES} | nuevos
        a_validar = {c: resultado[c] for c in nuevos}
        if "numero_documento" in nuevos or "tipo_documento" in nuevos:
            a_validar["tipo_documento"] = resultado["tipo_documento"]
            a_validar["numero_documento"] = resultado["numero_documento"]
        if "direccion_cp" in nuevos or "direccion_pais" in nuevos:
            a_validar["direccion_cp"] = resultado["direccion_cp"]
            a_validar["direccion_pais"] = resultado["direccion_pais"]
        errores += [e for e in validar_reglas(a_validar) if e["campo"] not in {x["campo"] for x in errores}]

        if errores:
            raise ErrorDeValidacion(detalles=errores)

        # Corrección del documento: no puede pertenecer a otro paciente (RF-19).
        if "tipo_documento" in nuevos or "numero_documento" in nuevos:
            otro = self.repo.obtener_por_documento(resultado["tipo_documento"], resultado["numero_documento"])
            if otro is not None and otro.patient_id != paciente.patient_id:
                raise PacienteDuplicado(
                    mensaje="Ese documento de identidad ya pertenece a otro paciente.",
                    codigo_historia_clinica=otro.codigo_historia_clinica,
                    patient_id=otro.patient_id,
                )

        for campo, valor in nuevos.items():
            setattr(paciente, campo, valor)

        try:
            self.sesion.commit()
        except IntegrityError as exc:
            self.sesion.rollback()
            raise PacienteDuplicado("Ese documento de identidad ya pertenece a otro paciente.") from exc

        self.sesion.refresh(paciente)
        return paciente
