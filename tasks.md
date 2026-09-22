# tasks.md — Desglose de tareas

**Módulo:** Registro e Identificación del Paciente (HIS)
**Deriva de:** `plan.md` v1.0, que deriva de `spec.md` v1.0

Cada tarea indica su origen (requisito, regla, decisión técnica o caso límite) y los criterios de
aceptación que permite cumplir.

**Estado:** todas las tareas están completadas. La verificación final (T-38) es la suite de pruebas
en verde.

---

## Fase 0 — Preparación

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-01 | Crear la estructura del proyecto | plan §6 | — |
| T-02 | Declarar las dependencias en `requirements.txt` | plan §2 | — |
| T-03 | Configurar la conexión a la base de datos | plan §2 | — |

## Fase 1 — Núcleo de identidad

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-04 | Validar DNI: formato y letra de control | RN-04 | CA-06 |
| T-05 | Validar NIE: formato y letra de control | RN-05 | CA-07 |
| T-06 | Validar pasaporte | RN-06 | CA-08 |
| T-07 | Normalizar documento, email, teléfono y textos | RN-01, RN-09, RN-10, RN-13, DT-06 | CA-05 |
| T-08 | Validar fecha de nacimiento, email, teléfono y código postal | RN-07, RN-09 a RN-11 | CA-09 |
| T-09 | Generar el `patient_id` como UUID v4 | RN-02, DT-01 | CA-01 |
| T-10 | Componer el código de historia clínica `HC-AAAA-NNNNNN` | RN-03, CL-04, CL-05 | CA-01, CA-02 |
| T-11 | Pruebas unitarias del núcleo de identidad | plan §7 | — |

## Fase 2 — Persistencia

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-12 | Entidad `Paciente` con restricción única sobre el documento | plan §3.1, RN-01, DT-02 | CA-04 |
| T-13 | Entidad `SecuenciaHistoria` e incremento transaccional | plan §3.2, CL-03 | CA-02 |
| T-14 | Repositorio: crear, obtener por `patient_id`, por documento y por código de historia clínica | RF-10, RF-11, RF-14 | CA-12, CA-13, CA-16 |

## Fase 3 — Contratos

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-15 | Contrato de alta con todas las validaciones y acumulación de errores | RF-01 a RF-04, RF-08, DT-04 | CA-10, CA-11 |
| T-16 | Contrato de modificación parcial | RF-17, RF-18, DT-03 | CA-18, CA-20 |
| T-17 | Contrato de la ficha del paciente | RF-09, RF-13 | CA-15 |
| T-18 | Contrato uniforme de error | RF-23, DT-05 | CA-27 |

## Fase 4 — Capacidad A · Registro e identificación

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-19 | Caso de uso de registro: comprobar duplicado, generar identidad y guardar en una transacción | RF-05 a RF-07, RF-09 | CA-01 a CA-05 |
| T-20 | Convertir la violación de unicidad en `PACIENTE_DUPLICADO` | DT-02, CL-02 | CA-04 |
| T-21 | Endpoint `POST /api/v1/pacientes` | RF-21 | CA-01 a CA-11 |
| T-22 | Pruebas CA-01 a CA-11 | plan §7 | — |

## Fase 5 — Capacidad B · Búsqueda y verificación

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-23 | Casos de uso de búsqueda por documento y por código de historia clínica | RF-10, RF-11 | CA-12, CA-13 |
| T-24 | Caso de uso de recuperación por `patient_id` | RF-14 | CA-16 |
| T-25 | Respuesta `PACIENTE_NO_ENCONTRADO` | RF-12 | CA-14 |
| T-26 | Endpoints `GET /api/v1/pacientes/buscar` y `GET /api/v1/pacientes/{patient_id}` | RF-21, CL-15 a CL-17 | CA-15 |
| T-27 | Pruebas CA-12 a CA-16 | plan §7 | — |

## Fase 6 — Capacidad C · Modificación y actualización

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-28 | Caso de uso de modificación parcial, con vaciado de datos opcionales | RF-15 a RF-18 | CA-17 a CA-21 |
| T-29 | Proteger la identidad frente a cualquier modificación | RF-20 | CA-22 |
| T-30 | Corrección del documento con comprobación de unicidad | RF-19 | CA-23, CA-24 |
| T-31 | Endpoint `PATCH /api/v1/pacientes/{patient_id}` | RF-21, CL-18 | CA-25, CA-26 |
| T-32 | Pruebas CA-17 a CA-26 | plan §7 | — |

## Fase 7 — Interfaz web y aplicación

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-33 | Manejador global de errores con el formato uniforme | RF-23, DT-05 | CA-27 |
| T-34 | Pantalla de búsqueda con buscador único y acceso al registro | RF-10 a RF-12, DT-08 | CA-28 |
| T-35 | Formulario compartido de registro y modificación, con los errores por campo | RF-01 a RF-04, RF-15 a RF-18, DT-08 | CA-28 |
| T-36 | Ficha del paciente con los datos para verificar la identidad | RF-13, DT-07, DT-08 | CA-28 |
| T-37 | Pruebas CA-27 a CA-29 | plan §7 | — |

## Fase 8 — Cierre

| # | Tarea | Origen | Habilita |
|---|-------|--------|----------|
| T-38 | Ejecutar la suite completa y comprobar que cubre los 29 criterios de aceptación | plan §7 | Todos |
| T-39 | Datos de ejemplo para la demostración | — | — |
| T-40 | Empaquetar el proyecto como `ejercicio1_49748233S.zip` | Enunciado §4 | — |

---

## Matriz de trazabilidad

| Capacidad | Requisitos | Tareas | Pruebas |
|-----------|-----------|--------|---------|
| A · Registro e identificación | RF-01 a RF-09 | T-04 a T-13, T-15, T-17, T-19 a T-22 | `tests/test_registro.py` |
| B · Búsqueda y verificación | RF-10 a RF-14 | T-14, T-17, T-23 a T-27 | `tests/test_busqueda.py` |
| C · Modificación y actualización | RF-15 a RF-20 | T-16, T-28 a T-32 | `tests/test_modificacion.py` |
| Aplicación | RF-21 a RF-23 | T-18, T-33 a T-37 | `tests/test_aplicacion.py` |
