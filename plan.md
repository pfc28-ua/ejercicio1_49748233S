# plan.md — Plan técnico

**Módulo:** Registro e Identificación del Paciente (HIS)
**Deriva de:** `spec.md` v1.0
**Versión:** 1.0

Este documento traduce la especificación a decisiones técnicas. Cada decisión cita el requisito
(RF), la regla de negocio (RN) o el caso límite (CL) del que procede.

---

## 1. Arquitectura

Aplicación web en Python con dos puntos de entrada sobre un mismo núcleo:

- una **API REST** (`/api/v1`), vía de reutilización de la identidad por otros módulos (RF-21);
- una **interfaz web** para el personal administrativo (RF-22).

Ambas usan los mismos casos de uso y las mismas validaciones: **no hay lógica duplicada**.

```
 Personal administrativo              Otros módulos del HIS
          │ interfaz web                      │ API REST /api/v1
          └─────────────────┬─────────────────┘
                            ▼
 ┌──────────────────────────────────────────────────────────┐
 │ Presentación (FastAPI)                                    │
 │   app/web/routes_web.py    app/api/routes_pacientes.py    │
 │   Traduce HTTP ↔ casos de uso. Sin reglas de negocio.     │
 ├──────────────────────────────────────────────────────────┤
 │ Dominio                                                   │
 │   app/services.py   Casos de uso de las capacidades A, B y C │
 │   app/identity.py   Identidad, validaciones, normalización │
 │   app/schemas.py    Contratos de entrada y salida         │
 │   app/errors.py     Errores de negocio                    │
 ├──────────────────────────────────────────────────────────┤
 │ Persistencia                                              │
 │   app/repository.py  Acceso a datos                       │
 │   app/models.py      Entidades                            │
 │   app/database.py    Conexión                             │
 └──────────────────────────────┬───────────────────────────┘
                                ▼
                         SQLite (fichero)
```

---

## 2. Stack tecnológico

| Elemento | Elección | Motivo |
|----------|----------|--------|
| Lenguaje | Python 3.11+ | Desarrollo rápido y legible. |
| Framework | FastAPI | Validación declarativa (RF-08), API REST con documentación automática (RF-21, CA-29) y plantillas para la interfaz web. |
| Validación | Pydantic v2 | Los contratos de la spec se expresan como esquemas. |
| Persistencia | SQLAlchemy 2.0 + SQLite | Restricciones de unicidad y transacciones (RN-01, CL-02, CL-03). SQLite no requiere instalación; el acceso está aislado en `repository.py`, así que cambiar de motor no afecta al dominio. |
| Interfaz | Jinja2 + CSS + JavaScript mínimo | Páginas generadas en el servidor, sin compilación de frontend. |
| Pruebas | pytest | Una prueba por criterio de aceptación, con su identificador en el nombre. |

---

## 3. Modelo de datos

### 3.1 Tabla `pacientes`

| Columna | Tipo | Nulo | Regla |
|---------|------|------|-------|
| `patient_id` | TEXT(36) | No | **Clave primaria.** UUID v4 generado en el dominio (RN-02). Inmutable (RF-06, RF-20). |
| `codigo_historia_clinica` | TEXT(15) | No | **Único.** `HC-AAAA-NNNNNN` (RN-03). Inmutable. |
| `tipo_documento` | TEXT | No | `DNI`, `NIE` o `PASAPORTE` (RF-02). |
| `numero_documento` | TEXT(20) | No | Normalizado (RN-01, RN-13). |
| `nombre` | TEXT(60) | No | RN-08. |
| `primer_apellido` | TEXT(60) | No | RN-08. |
| `segundo_apellido` | TEXT(60) | Sí | RF-01. |
| `fecha_nacimiento` | DATE | No | RN-07. |
| `sexo` | TEXT | No | `MUJER`, `HOMBRE`, `OTRO` o `NO_DECLARA` (RF-01). |
| `telefono` | TEXT(20) | Sí | RN-10. |
| `email` | TEXT(120) | Sí | RN-09. |
| `direccion_calle` | TEXT(120) | Sí | RF-03. |
| `direccion_ciudad` | TEXT(80) | Sí | RF-03. |
| `direccion_cp` | TEXT(10) | Sí | RN-11. |
| `direccion_provincia` | TEXT(80) | Sí | RF-03. |
| `direccion_pais` | TEXT(80) | Sí | RF-03. |
| `entidad_aseguradora` | TEXT(120) | No | Seguro o mutua (RF-04, RN-12). |
| `numero_poliza` | TEXT(60) | No | Número de seguro o mutua (RF-04, RN-12). |
| `fecha_alta` | DATETIME | No | Momento del registro; determina el año del código de historia clínica (RN-03). |

**Restricción única** sobre `(tipo_documento, numero_documento)`: garantiza RN-01 en la propia
base de datos (CL-02).

### 3.2 Tabla `secuencia_historia`

| Columna | Tipo | Regla |
|---------|------|-------|
| `anio` | INTEGER | Clave primaria. |
| `ultimo_valor` | INTEGER | Último secuencial asignado ese año. |

Una fila por año. El secuencial se incrementa dentro de la transacción del alta, de modo que dos
altas simultáneas nunca reciben el mismo código (CL-03) y el contador vuelve a empezar cada año
(CL-04).

---

## 4. Decisiones técnicas

### DT-01 — Identidad doble: técnica y legible
Un solo identificador no sirve para las dos necesidades. El **`patient_id`** (UUID v4) es opaco y
estable: es lo que guardarán citas, historia clínica o facturación. El **código de historia
clínica** es legible y se comunica al paciente. Ambos son inmutables (RN-02, RN-03, RF-20).

El `patient_id` se genera en el dominio y no como autonumérico de la base de datos, para que la
identidad no dependa del motor ni de la base de datos concreta. Así queda reutilizable por otros
módulos aunque estos no se implementen (criterio de evaluación del enunciado).

### DT-02 — Unicidad garantizada por la base de datos
Comprobar si el documento existe antes de insertar no basta: entre la comprobación y la inserción
puede producirse otra alta. La restricción única de la tabla es la garantía real; el servicio
captura su violación y la convierte en `PACIENTE_DUPLICADO` (CL-02). La comprobación previa se
mantiene para poder informar del código de historia clínica existente (RF-07).

### DT-03 — Actualización parcial: "no enviado" frente a "vacío"
RF-17 y RF-18 piden distinguir un dato que no se modifica de uno que se vacía. El contrato de
actualización usa `model_dump(exclude_unset=True)`: un campo omitido no se toca y un campo enviado
vacío se guarda como nulo. Los campos obligatorios no pueden vaciarse.

### DT-04 — Validación completa y en un solo paso
Pydantic valida tipos y longitudes; `identity.py` valida las reglas de negocio (RN-04 a RN-12).
Para cumplir RF-08, cuando falla la validación de algún campo también se aplican las reglas de
negocio sobre el resto de datos, y se devuelven todos los errores juntos (CA-11).

### DT-05 — Formato único de error
Un manejador global convierte cualquier error al formato de RF-23:

```json
{
  "codigo": "VALIDACION",
  "mensaje": "Los datos enviados no son válidos.",
  "detalles": [{ "campo": "numero_documento", "mensaje": "La letra de control del DNI no es correcta." }]
}
```

Códigos: `VALIDACION` (422), `PACIENTE_NO_ENCONTRADO` (404), `PACIENTE_DUPLICADO` (409).

### DT-06 — Normalización centralizada
Las normalizaciones de documento, email, teléfono y textos están en `identity.py` y se aplican al
recibir los datos, antes de validar, comparar o buscar. Por eso ` 12345678-z ` se reconoce como
`12345678Z` sin ningún tratamiento especial en el servicio (CA-05, CL-01).

### DT-07 — Verificación de identidad
La verificación de RF-13 la realiza el administrativo: la búsqueda muestra los datos
identificativos del paciente para contrastarlos con la persona presente. La interfaz los agrupa de
forma destacada en la ficha.

### DT-08 — Interfaz web
- **Buscador único:** una sola caja admite un documento de identidad o un código de historia
  clínica, y la aplicación deduce cuál es (`identity.detectar_criterio_busqueda`) para aplicar RF-10
  o RF-11.
- **Buscar antes de registrar:** si el paciente no existe, la propia búsqueda ofrece registrarlo con
  el documento ya rellenado (ESC-01, ESC-02).
- **La identidad como pulsera hospitalaria:** la ficha presenta el código de historia clínica, el
  `patient_id` y los datos identificativos con la forma de la pulsera del paciente (RF-13).
- **Formulario compartido** entre alta y modificación, para que ambos flujos manejen los mismos
  datos.
- **Ayuda al escribir el documento:** indica si la letra de control del DNI o NIE es correcta. Es
  solo una comodidad; el servidor lo vuelve a validar todo.

---

## 5. Contrato de la API

| Método | Ruta | Requisitos | Respuesta correcta | Errores |
|--------|------|-----------|--------------------|---------|
| `POST` | `/api/v1/pacientes` | RF-01 a RF-09 | `201` y ficha | `409`, `422` |
| `GET` | `/api/v1/pacientes/buscar?tipo_documento=&numero_documento=` | RF-10, RF-12, RF-13 | `200` y ficha | `404`, `422` |
| `GET` | `/api/v1/pacientes/buscar?codigo_historia_clinica=` | RF-11, RF-12, RF-13 | `200` y ficha | `404`, `422` |
| `GET` | `/api/v1/pacientes/{patient_id}` | RF-14 | `200` y ficha | `404`, `422` |
| `PATCH` | `/api/v1/pacientes/{patient_id}` | RF-15 a RF-20 | `200` y ficha | `404`, `409`, `422` |

La documentación interactiva se genera en `/docs` (CA-29).

### 5.1 Pantallas de la interfaz web

| Ruta | Pantalla | Capacidad |
|------|----------|-----------|
| `GET /` | Búsqueda por documento o código de historia clínica | B |
| `GET /pacientes/nuevo` · `POST /pacientes/nuevo` | Registro | A |
| `GET /pacientes/{id}` | Ficha con los datos para verificar la identidad | B |
| `GET /pacientes/{id}/editar` · `POST /pacientes/{id}/editar` | Modificación | C |

---

## 6. Estructura del proyecto

```
ejercicio1_49748233S/
├── spec.md · plan.md · tasks.md · README.md
├── requirements.txt
├── datos_ejemplo.py              Pacientes de muestra para la demostración
├── app/
│   ├── main.py                   Aplicación y manejo de errores
│   ├── config.py                 Configuración
│   ├── database.py               Conexión
│   ├── models.py                 Entidades
│   ├── schemas.py                Contratos
│   ├── identity.py               Identidad y reglas de validación
│   ├── errors.py                 Errores de negocio
│   ├── repository.py             Acceso a datos
│   ├── services.py               Casos de uso
│   ├── api/routes_pacientes.py   API REST
│   ├── web/routes_web.py         Interfaz web
│   ├── web/templates/            Plantillas
│   └── static/                   Estilos y JavaScript
└── tests/
    ├── test_identidad.py         Reglas de identidad (unitarias)
    ├── test_registro.py          CA-01 a CA-11
    ├── test_busqueda.py          CA-12 a CA-16
    ├── test_modificacion.py      CA-17 a CA-26
    └── test_aplicacion.py        CA-27 a CA-29
```

---

## 7. Estrategia de pruebas

- **Unitarias:** validación de documentos, normalizaciones y generación de la identidad, sin base de
  datos.
- **De integración:** una prueba por criterio de aceptación contra la aplicación real, con una base
  de datos en memoria nueva en cada prueba.
- **Criterio de terminación:** los 29 criterios de aceptación de la spec tienen su prueba y pasan.
