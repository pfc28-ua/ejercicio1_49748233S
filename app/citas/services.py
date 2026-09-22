"""Casos de uso del módulo de citas.

Implementan las tres capacidades de `citas/spec.md`:

- A · Reservar una cita online   → ``buscar_especialistas``, ``disponibilidad``, ``reservar``
- B · Cancelar o reprogramar     → ``citas_de_paciente``, ``cancelar``, ``reprogramar``
- C · Gestionar la agenda        → ``agenda``, ``bloquear``, ``levantar_bloqueo``, ``ajustar_duracion``

El instante de referencia (``ahora``) es un parámetro opcional de todas las
operaciones que dependen del tiempo, para poder verificar las reglas de
antelación sin esperas (plan.md DT-06).

Trazabilidad: RF-01 a RF-22; tasks.md T-17 a T-21, T-24 a T-27, T-30 a T-33.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.citas import config
from app.citas.agenda import (
    FUERA_DE_HORIZONTE,
    MENSAJES,
    OCUPADO,
    SIN_ANTELACION,
    Hueco,
    Intervalo,
    calcular_disponibilidad,
    duracion_valida,
    hueco_reservable,
    pertenece_al_horario,
)
from app.citas.reloj import ahora as ahora_local
from app.citas.errors import (
    BloqueoNoEncontrado,
    CitaNoEncontrada,
    CitaNoModificable,
    EspecialistaNoEncontrado,
    FranjaConCitas,
    HuecoNoDisponible,
    PacienteYaCitado,
)
from app.citas.models import Bloqueo, Cita, Especialista, EstadoCita, MotivoBloqueo
from app.citas.repository import RepositorioCitas
from app.errors import ErrorDeValidacion
from app.models import Paciente
from app.services import ServicioPacientes

PREFIJO_CITA = "CITA"
ANCHURA_SECUENCIAL = 6
SECUENCIAL_MAXIMO = 10**ANCHURA_SECUENCIAL - 1
_PATRON_CODIGO = re.compile(r"^CITA-\d{4}-\d{6}$")


def formatear_codigo_cita(anio: int, secuencial: int) -> str:
    """Compone el código de cita ``CITA-AAAA-NNNNNN`` (RN-01)."""
    if secuencial > SECUENCIAL_MAXIMO:
        raise ValueError(f"Secuencial de citas agotado para el año {anio}.")
    return f"{PREFIJO_CITA}-{anio:04d}-{secuencial:0{ANCHURA_SECUENCIAL}d}"


def es_codigo_cita_valido(codigo: str | None) -> bool:
    """Indica si el texto tiene formato de código de cita (RN-01, CL-18)."""
    return bool(_PATRON_CODIGO.match((codigo or "").strip().upper()))


class ServicioCitas:
    """Casos de uso de la programación de citas."""

    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion
        self.repo = RepositorioCitas(sesion)
        # El módulo de citas se apoya en el de registro para todo lo relativo al
        # paciente: no duplica sus datos (RF-26, plan.md DT-07).
        self.pacientes = ServicioPacientes(sesion)

    # ------------------------------------------------------------------
    # Catálogo (apoyo a la capacidad A)
    # ------------------------------------------------------------------

    def especialidades(self):
        return self.repo.especialidades()

    def centros(self):
        return self.repo.centros()

    def buscar_especialistas(
        self, especialidad_id: int | None = None, centro_id: int | None = None
    ) -> list[Especialista]:
        """Busca especialistas por especialidad y centro (RF-01, CA-01)."""
        return self.repo.buscar_especialistas(especialidad_id, centro_id)

    def obtener_especialista(self, especialista_id: int) -> Especialista:
        especialista = self.repo.especialista(especialista_id)
        if especialista is None:
            raise EspecialistaNoEncontrado()
        return especialista

    # ------------------------------------------------------------------
    # Capacidad A · Reservar una cita online
    # ------------------------------------------------------------------

    def disponibilidad(
        self,
        especialista_id: int,
        desde: date,
        hasta: date,
        ahora: datetime | None = None,
        hora_desde: time | None = None,
        hora_hasta: time | None = None,
    ) -> list[Hueco]:
        """Huecos libres de un especialista entre dos fechas (RF-02, RF-03).

        ``hora_desde`` y ``hora_hasta`` acotan la disponibilidad horaria del
        paciente, que el enunciado (§3.1) pide poder tener en cuenta.

        La disponibilidad se calcula: nunca se almacena (plan.md DT-01), de modo
        que refleja siempre los bloqueos, las citas y la duración vigentes
        (RF-21).
        """
        momento = ahora or ahora_local()
        especialista = self.obtener_especialista(especialista_id)
        self._validar_rango(desde, hasta)

        return calcular_disponibilidad(
            desde=desde,
            hasta=hasta,
            horarios_por_dia=self._horarios_por_dia(especialista),
            duracion_min=especialista.duracion_cita_min,
            ocupados=self._ocupados(
                especialista_id,
                datetime.combine(desde, time.min),
                datetime.combine(hasta + timedelta(days=1), time.min),
            ),
            ahora=momento,
            hora_desde=hora_desde,
            hora_hasta=hora_hasta,
        )

    def identificar_paciente(
        self,
        tipo_documento: str | None = None,
        numero_documento: str | None = None,
        codigo_historia_clinica: str | None = None,
    ) -> Paciente:
        """Resuelve al paciente por su documento o su código de historia clínica.

        Reutiliza el módulo de registro (`registro/RF-10`, `registro/RF-11`). No
        es autenticación: no hay contraseña ni sesión (spec §2.1, plan.md DT-07).
        """
        if codigo_historia_clinica:
            return self.pacientes.buscar_por_codigo_historia(codigo_historia_clinica)
        if tipo_documento and numero_documento:
            return self.pacientes.buscar_por_documento(tipo_documento, numero_documento)
        raise ErrorDeValidacion(
            mensaje="Indique un documento de identidad o un código de historia clínica.",
            detalles=[{
                "campo": "identificacion",
                "mensaje": "Envíe tipo_documento y numero_documento, o bien codigo_historia_clinica.",
            }],
        )

    def reservar(
        self,
        patient_id: str,
        especialista_id: int,
        inicio: datetime,
        motivo_consulta: str | None = None,
        ahora: datetime | None = None,
    ) -> Cita:
        """Reserva un hueco para un paciente (RF-05 a RF-08).

        Comprueba el hueco con **el mismo código** que usa la disponibilidad, así
        que no puede ocurrir que se ofrezca un hueco que luego se rechace
        (plan.md §5).
        """
        momento = ahora or ahora_local()
        especialista = self.obtener_especialista(especialista_id)
        paciente = self.pacientes.obtener(patient_id)  # 404 si no existe (RN-15)

        duracion = especialista.duracion_cita_min
        hueco = Hueco(inicio=inicio, duracion_min=duracion)

        # El hueco debe ser uno de los que genera el horario del especialista.
        if not pertenece_al_horario(inicio, duracion, self._horarios_por_dia(especialista)):
            raise HuecoNoDisponible(
                "Ese hueco no existe en la agenda del especialista.",
                motivo="FUERA_DE_HORARIO",
            )

        reservable, motivo = hueco_reservable(
            hueco,
            self._ocupados(especialista_id, hueco.inicio, hueco.fin),
            momento,
        )
        if not reservable:
            self._rechazar_hueco(motivo)

        self._comprobar_sin_solape_del_paciente(paciente.patient_id, hueco.intervalo)

        cita = Cita(
            cita_id=str(uuid.uuid4()),
            codigo=self.repo.siguiente_codigo_cita(momento.year),
            patient_id=paciente.patient_id,
            especialista_id=especialista_id,
            inicio=hueco.inicio,
            duracion_min=duracion,
            estado=EstadoCita.RESERVADA.value,
            motivo_consulta=(motivo_consulta or "").strip() or None,
            fecha_reserva=momento,
            fecha_modificacion=momento,
        )
        self.repo.anadir(cita)

        try:
            self.sesion.commit()
        except IntegrityError as exc:
            # Otra reserva se adelantó por milésimas (CL-01, ESC-08).
            self.sesion.rollback()
            raise HuecoNoDisponible(
                "Ese hueco acaba de ser reservado por otro paciente.", motivo="OCUPADO"
            ) from exc

        self.sesion.refresh(cita)
        return cita

    # ------------------------------------------------------------------
    # Capacidad B · Cancelar o reprogramar
    # ------------------------------------------------------------------

    def citas_de_paciente(self, patient_id: str) -> list[Cita]:
        """Citas de un paciente, de la más reciente a la más antigua (RF-09, CL-14)."""
        return self.repo.citas_de_paciente(patient_id)

    def obtener_cita(self, cita_id: str) -> Cita:
        cita = self.repo.cita_por_id(cita_id)
        if cita is None:
            raise CitaNoEncontrada(f"No existe ninguna cita con el identificador {cita_id}.")
        return cita

    def cita_por_codigo(self, codigo: str) -> Cita:
        """Cita por su código legible (RF-15, CL-18)."""
        if not es_codigo_cita_valido(codigo):
            raise ErrorDeValidacion(
                detalles=[{
                    "campo": "codigo",
                    "mensaje": "El código de cita debe tener el formato CITA-AAAA-NNNNNN.",
                }]
            )
        cita = self.repo.cita_por_codigo(codigo)
        if cita is None:
            raise CitaNoEncontrada(f"No existe ninguna cita con el código {codigo.upper()}.")
        return cita

    def cancelar(
        self, cita_id: str, patient_id: str | None = None, ahora: datetime | None = None
    ) -> Cita:
        """Cancela una cita futura (RF-10, RF-13, RF-14).

        El hueco se libera solo, porque la disponibilidad se calcula (DT-01).
        """
        momento = ahora or ahora_local()
        cita = self.obtener_cita(cita_id)
        self._comprobar_propiedad(cita, patient_id)
        self._comprobar_modificable(cita, momento)

        cita.estado = EstadoCita.CANCELADA.value
        cita.fecha_modificacion = momento
        self.sesion.commit()
        self.sesion.refresh(cita)
        return cita

    def reprogramar(
        self,
        cita_id: str,
        nuevo_inicio: datetime,
        patient_id: str | None = None,
        ahora: datetime | None = None,
    ) -> Cita:
        """Cambia la cita a otro hueco del mismo especialista (RF-11 a RF-13).

        La cita **conserva su identificador y su código**: es la misma cita
        (RN-10, plan.md DT-04, ESC-02).
        """
        momento = ahora or ahora_local()
        cita = self.obtener_cita(cita_id)
        self._comprobar_propiedad(cita, patient_id)
        self._comprobar_modificable(cita, momento)

        if cita.inicio == nuevo_inicio:
            # Reprogramar al mismo hueco no cambia nada (CL-12).
            return cita

        especialista = self.obtener_especialista(cita.especialista_id)
        duracion = especialista.duracion_cita_min
        hueco = Hueco(inicio=nuevo_inicio, duracion_min=duracion)

        if not pertenece_al_horario(nuevo_inicio, duracion, self._horarios_por_dia(especialista)):
            raise HuecoNoDisponible(
                "Ese hueco no existe en la agenda del especialista.", motivo="FUERA_DE_HORARIO"
            )

        reservable, motivo = hueco_reservable(
            hueco,
            self._ocupados(cita.especialista_id, hueco.inicio, hueco.fin, excluir_cita=cita.cita_id),
            momento,
        )
        if not reservable:
            self._rechazar_hueco(motivo)

        self._comprobar_sin_solape_del_paciente(
            cita.patient_id, hueco.intervalo, excluir_cita=cita.cita_id
        )

        cita.inicio = hueco.inicio
        cita.duracion_min = duracion
        cita.fecha_modificacion = momento

        try:
            self.sesion.commit()
        except IntegrityError as exc:
            self.sesion.rollback()
            raise HuecoNoDisponible(
                "Ese hueco acaba de ser reservado por otro paciente.", motivo="OCUPADO"
            ) from exc

        self.sesion.refresh(cita)
        return cita

    # ------------------------------------------------------------------
    # Capacidad C · Gestionar la agenda
    # ------------------------------------------------------------------

    def agenda(self, especialista_id: int, desde: date, hasta: date) -> dict:
        """Horario, bloqueos y citas de un especialista en un periodo (RF-16)."""
        especialista = self.obtener_especialista(especialista_id)
        self._validar_rango(desde, hasta)
        inicio = datetime.combine(desde, time.min)
        fin = datetime.combine(hasta + timedelta(days=1), time.min)

        return {
            "especialista": especialista,
            "horarios": sorted(especialista.horarios, key=lambda h: (h.dia_semana, h.hora_inicio)),
            "bloqueos": self.repo.bloqueos(especialista_id, inicio, fin),
            "citas": self.repo.citas_de_especialista(especialista_id, inicio, fin),
        }

    def bloquear(
        self,
        especialista_id: int,
        inicio: datetime,
        fin: datetime,
        motivo: str,
        observaciones: str | None = None,
        ahora: datetime | None = None,
    ) -> Bloqueo:
        """Bloquea una franja de la agenda (RF-17, RF-18, RN-11, RN-12).

        Si la franja contiene citas reservadas se rechaza y se informa de cuáles
        son, para que el administrativo las gestione antes (ESC-06, CA-23).
        """
        momento = ahora or ahora_local()
        self.obtener_especialista(especialista_id)

        errores = []
        if fin <= inicio:
            errores.append({"campo": "fin", "mensaje": "El fin debe ser posterior al inicio."})
        if fin <= momento:
            errores.append({"campo": "inicio", "mensaje": "No se puede bloquear una franja ya pasada."})
        if motivo not in {m.value for m in MotivoBloqueo}:
            errores.append({
                "campo": "motivo",
                "mensaje": "El motivo debe ser VACACIONES, FORMACION, BAJA u OTRO.",
            })
        if errores:
            raise ErrorDeValidacion(detalles=errores)

        franja = Intervalo(inicio, fin)
        afectadas = [
            cita.codigo
            for cita in self.repo.citas_de_especialista(especialista_id, solo_activas=True)
            if Intervalo(cita.inicio, cita.fin).solapa(franja)
        ]
        if afectadas:
            raise FranjaConCitas(sorted(afectadas))

        bloqueo = Bloqueo(
            especialista_id=especialista_id,
            inicio=inicio,
            fin=fin,
            motivo=motivo,
            observaciones=(observaciones or "").strip() or None,
        )
        self.repo.anadir(bloqueo)
        self.sesion.commit()
        self.sesion.refresh(bloqueo)
        return bloqueo

    def levantar_bloqueo(self, bloqueo_id: int) -> None:
        """Elimina un bloqueo, devolviendo esos huecos a la disponibilidad (RF-19)."""
        bloqueo = self.repo.bloqueo(bloqueo_id)
        if bloqueo is None:
            raise BloqueoNoEncontrado()
        self.repo.eliminar(bloqueo)
        self.sesion.commit()

    def ajustar_duracion(self, especialista_id: int, minutos: int) -> Especialista:
        """Cambia la duración de los huecos del especialista (RF-20, RN-02).

        No toca las citas ya reservadas, que guardan su propia duración
        (RF-22, RN-14, CA-27).
        """
        especialista = self.obtener_especialista(especialista_id)

        valida, mensaje = duracion_valida(minutos)
        if not valida:
            raise ErrorDeValidacion(detalles=[{"campo": "duracion_cita_min", "mensaje": mensaje}])

        especialista.duracion_cita_min = minutos
        self.sesion.commit()
        self.sesion.refresh(especialista)
        return especialista

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    @staticmethod
    def _horarios_por_dia(especialista: Especialista) -> dict[int, list[tuple[time, time]]]:
        """Horario semanal del especialista agrupado por día (RN-03)."""
        horarios: dict[int, list[tuple[time, time]]] = {}
        for tramo in especialista.horarios:
            horarios.setdefault(tramo.dia_semana, []).append((tramo.hora_inicio, tramo.hora_fin))
        for tramos in horarios.values():
            tramos.sort()
        return horarios

    def _ocupados(
        self,
        especialista_id: int,
        desde: datetime,
        hasta: datetime,
        excluir_cita: str | None = None,
    ) -> list[Intervalo]:
        """Intervalos ocupados del especialista: bloqueos y citas activas (RN-13)."""
        ocupados = [
            Intervalo(bloqueo.inicio, bloqueo.fin)
            for bloqueo in self.repo.bloqueos(especialista_id, desde, hasta)
        ]
        ocupados += [
            Intervalo(cita.inicio, cita.fin)
            for cita in self.repo.citas_de_especialista(especialista_id, solo_activas=True)
            if cita.cita_id != excluir_cita and cita.fin > desde and cita.inicio < hasta
        ]
        return ocupados

    def _comprobar_sin_solape_del_paciente(
        self, patient_id: str, intervalo: Intervalo, excluir_cita: str | None = None
    ) -> None:
        """Un paciente no puede tener dos citas a la vez (RN-05, CA-11)."""
        for cita in self.repo.citas_activas_de_paciente(patient_id):
            if cita.cita_id == excluir_cita:
                continue
            if Intervalo(cita.inicio, cita.fin).solapa(intervalo):
                raise PacienteYaCitado(
                    "El paciente ya tiene otra cita que se solapa con esa hora.",
                    codigo_cita=cita.codigo,
                )

    @staticmethod
    def _rechazar_hueco(motivo: str | None) -> None:
        """Traduce el motivo del rechazo al error que corresponde (DT-09).

        Un hueco fuera de plazo es un dato mal enviado (422); uno ocupado o
        bloqueado es un conflicto con el estado de la agenda (409).
        """
        mensaje = MENSAJES.get(motivo, "Ese hueco no está disponible.")
        if motivo in (SIN_ANTELACION, FUERA_DE_HORIZONTE):
            raise ErrorDeValidacion(detalles=[{"campo": "inicio", "mensaje": mensaje}])
        raise HuecoNoDisponible(mensaje, motivo=OCUPADO)

    @staticmethod
    def _comprobar_propiedad(cita: Cita, patient_id: str | None) -> None:
        """La cita debe pertenecer al paciente que se ha identificado (CL-13)."""
        if patient_id is not None and cita.patient_id != patient_id:
            raise CitaNoEncontrada("Esa cita no pertenece al paciente indicado.")

    @staticmethod
    def _comprobar_modificable(cita: Cita, ahora: datetime) -> None:
        """Estado y antelación necesarios para cancelar o reprogramar (RF-14, RN-07, RN-09)."""
        if not cita.activa:
            raise CitaNoModificable("La cita ya está cancelada.")
        if cita.inicio <= ahora:
            raise CitaNoModificable("La cita ya ha pasado.")
        if cita.inicio - ahora < timedelta(hours=config.ANTELACION_MINIMA_CAMBIO_H):
            raise CitaNoModificable(
                f"Las citas deben cancelarse o reprogramarse con al menos "
                f"{config.ANTELACION_MINIMA_CAMBIO_H} horas de antelación."
            )

    @staticmethod
    def _validar_rango(desde: date, hasta: date) -> None:
        """Rango de fechas de una consulta de disponibilidad (CL-07, CL-08)."""
        if hasta < desde:
            raise ErrorDeValidacion(
                detalles=[{"campo": "hasta", "mensaje": "La fecha final no puede ser anterior a la inicial."}]
            )
        if (hasta - desde).days > config.RANGO_MAXIMO_CONSULTA_DIAS:
            raise ErrorDeValidacion(
                detalles=[{
                    "campo": "hasta",
                    "mensaje": f"El rango no puede superar {config.RANGO_MAXIMO_CONSULTA_DIAS} días.",
                }]
            )
