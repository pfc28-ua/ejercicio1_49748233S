# tasks.md — Desglose de tareas del módulo de Citas

**Módulo:** Programación de citas médicas (ejercicio 2)
**Deriva de:** `citas/plan.md` v1.0, que deriva de `citas/spec.md` v1.0

Cada tarea indica su origen (requisito, regla, decisión técnica o caso límite) y los criterios de
aceptación que permite cumplir.

**Estado:** todas las tareas están completadas. La verificación final (T-45) exige, además, que las
pruebas del ejercicio 1 sigan pasando sin cambios.

---

## Fase 0 — Preparación

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-01 | Crear el paquete `app/citas/` sin tocar el módulo de registro | plan §1, §7 | — |
| T-02 | Configuración de las políticas del centro: antelaciones, horizonte y límite de rango | DT-05, RN-06 a RN-08 | CA-10, CA-17 |
| T-03 | Errores propios que heredan del error de negocio del ejercicio 1 | DT-09, RF-25 | CA-29 |

## Fase 1 — Modelo de datos

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-04 | Entidades de catálogo: `Centro`, `Especialidad`, `Especialista` con su duración de hueco | plan §3.1, RN-02, RN-16 | CA-01 |
| T-05 | Entidad `HorarioConsulta`: plantilla semanal del especialista | plan §3.1, RN-03 | CA-02 |
| T-06 | Entidad `Bloqueo` con motivo | plan §3.1, RN-11 | CA-22 |
| T-07 | Entidad `Cita` con identidad propia, `patient_id`, `inicio`, `duracion_min` y estado | RN-01, RN-09, RF-26 | CA-05, CA-28 |
| T-08 | Restricción única parcial `(especialista, inicio)` sobre las citas reservadas | DT-03, RN-04, CL-01, CL-20 | CA-07 |
| T-09 | Secuencial anual del código de cita | RN-01, CL-19 | CA-06 |
| T-10 | Repositorio: catálogo, horarios, bloqueos y citas | plan §7 | CA-01, CA-13, CA-21 |

## Fase 2 — Disponibilidad

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-11 | Generar los huecos de un tramo horario según la duración, descartando los que no caben | RN-03, CL-02 | CA-02 |
| T-12 | Comprobación de solapamiento por intervalos, reutilizable para citas y bloqueos | DT-02, CL-03 | CA-03, CA-04 |
| T-13 | Filtrar los huecos por bloqueos, citas activas, antelación mínima y horizonte | RN-13, RN-06, RN-08 | CA-03, CA-04, CA-10 |
| T-14 | Calcular la disponibilidad de un rango de fechas, con validación del rango | RF-02, CL-06 a CL-08 | CA-02 |
| T-15 | Instante de referencia inyectable en todo el cálculo | DT-06 | CA-10, CA-17, CA-19 |
| T-16 | Pruebas unitarias del generador de huecos | plan §9 | — |

## Fase 3 — Capacidad A · Reservar una cita online

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-17 | Caso de uso: buscar especialistas por especialidad y centro | RF-01 | CA-01 |
| T-18 | Identificar al paciente reutilizando el servicio del ejercicio 1 | RF-04, DT-07, RN-15 | CA-12 |
| T-19 | Caso de uso de reserva: validar el hueco con el mismo código que la disponibilidad, generar identidad y guardar | RF-05 a RF-08, plan §5 | CA-05, CA-06 |
| T-20 | Comprobar que el paciente no tenga otra cita solapada | RN-05 | CA-11 |
| T-21 | Traducir la violación de unicidad a `HUECO_NO_DISPONIBLE` | DT-03, CL-01 | CA-07 |
| T-22 | Endpoints de catálogo, especialistas, disponibilidad y reserva | RF-23 | CA-01 a CA-12 |
| T-23 | Pruebas CA-01 a CA-12 | plan §9 | — |

## Fase 4 — Capacidad B · Cancelar o reprogramar

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-24 | Caso de uso: citas de un paciente, distinguiendo futuras y pasadas | RF-09, CL-14 | CA-13 |
| T-25 | Caso de uso de cancelación, con la antelación mínima y la comprobación de propiedad de la cita | RF-10, RF-14, RN-07, CL-13 | CA-14, CA-17, CA-18 |
| T-26 | Caso de uso de reprogramación conservando identificador y código | RF-11 a RF-13, DT-04, RN-10, CL-12 | CA-15, CA-16 |
| T-27 | Consulta de una cita por su código | RF-15, CL-18 | CA-20 |
| T-28 | Endpoints de citas del paciente, cancelación y reprogramación | RF-23, CL-17 | CA-19 |
| T-29 | Pruebas CA-13 a CA-20 | plan §9 | — |

## Fase 5 — Capacidad C · Gestionar la agenda

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-30 | Caso de uso: agenda de un especialista (horario, bloqueos y citas) | RF-16 | CA-21 |
| T-31 | Caso de uso de bloqueo, rechazando la franja si contiene citas reservadas | RF-17, RF-18, RN-11, RN-12, CL-04, CL-05, CL-20 | CA-22, CA-23 |
| T-32 | Caso de uso para levantar un bloqueo | RF-19 | CA-24 |
| T-33 | Caso de uso para ajustar la duración, sin tocar las citas ya reservadas | RF-20, RF-22, RN-02, RN-14, CL-16 | CA-25 a CA-27 |
| T-34 | Endpoints de agenda, bloqueos y duración | RF-23 | CA-21 a CA-27 |
| T-35 | Pruebas CA-21 a CA-27 | plan §9 | — |

## Fase 6 — Interfaz web

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-36 | Zona del paciente: identificarse para acceder a sus citas | RF-24, DT-07, DT-10 | CA-30 |
| T-37 | Pantalla de búsqueda de disponibilidad y reserva | RF-01 a RF-08 | CA-30 |
| T-38 | Pantalla "Mis citas" con cancelar y reprogramar | RF-09 a RF-14 | CA-30 |
| T-39 | Zona administrativa: agenda del especialista, bloqueos y duración | RF-16 a RF-20 | CA-30 |
| T-40 | Enlazar ambos módulos en la navegación, manteniendo el diseño del ejercicio 1 | RF-24 | CA-30 |

## Fase 7 — Integración y cierre

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-41 | Montar las rutas del módulo en `app/main.py` | plan §1 | CA-31 |
| T-42 | Datos de ejemplo: centros, especialidades, especialistas y horarios | DT-11, RN-16 | — |
| T-43 | Comprobar que las citas reutilizan el `patient_id` sin duplicar datos del paciente | RF-26, CA-28 | CA-28 |
| T-44 | Pruebas CA-28 a CA-31 | plan §9 | — |
| T-45 | Ejecutar toda la suite: los 32 criterios del ejercicio 2 y las 76 pruebas del ejercicio 1 | plan §9 | Todos |
| T-46 | Empaquetar el proyecto ampliado como `ejercicio2_49748233S.zip` | Enunciado §4 | — |

## Fase 8 — Correcciones tras la revisión

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-47 | Un único reloj con la hora local del centro, en lugar de UTC, en servicios, API, web y modelos | DT-08, RN-06, RN-07 | CA-10, CA-17 |
| T-48 | Códigos de motivo al rechazar un hueco, en lugar de comparar el texto del mensaje | DT-09 | CA-10 |
| T-49 | Exigir identificación para cancelar y reprogramar también por API | CL-13, RF-10, RF-11 | CA-14, CA-15 |
| T-50 | El código de cita lleva el año en que se reserva | RN-01 | CA-06 |
| T-51 | Filtro por franja horaria en la disponibilidad, en la API y en la interfaz web | RF-02, enunciado §3.1 | CA-32 |
| T-52 | Pruebas de regresión de cada corrección | plan §9 | CA-32 |

---

## Matriz de trazabilidad

| Capacidad | Requisitos | Tareas | Pruebas |
|-----------|-----------|--------|---------|
| A · Reservar una cita online | RF-01 a RF-08 | T-04 a T-23, T-51 | `tests/test_citas_reserva.py` |
| B · Cancelar o reprogramar | RF-09 a RF-15 | T-24 a T-29 | `tests/test_citas_cambios.py` |
| C · Gestionar la agenda | RF-16 a RF-22 | T-30 a T-35 | `tests/test_citas_gestion_agenda.py` |
| Aplicación e integración | RF-23 a RF-26 | T-03, T-22, T-28, T-34, T-36 a T-44 | `tests/test_citas_aplicacion.py` |
| Disponibilidad (transversal a A y C) | RF-02, RF-03, RF-21 | T-11 a T-16 | `tests/test_citas_agenda.py` |
