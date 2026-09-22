# plan.md — Plan técnico del módulo de Citas

**Módulo:** Programación de citas médicas (ejercicio 2)
**Deriva de:** `citas/spec.md` v1.0
**Amplía:** el proyecto del ejercicio 1 (Registro e Identificación de Pacientes)
**Versión:** 1.0

---

## 1. Principio de ampliación

El ejercicio 2 **amplía** el proyecto anterior, no lo sustituye. De ahí tres decisiones de partida:

1. El módulo de registro **no se modifica**. Su código, sus documentos y sus pruebas quedan
   intactos, salvo un punto de enganche en `app/main.py` para montar las rutas nuevas.
2. El módulo de citas vive en su propio paquete, `app/citas/`, y reutiliza lo que ya existe:
   la conexión a base de datos, el formato de error, la validación de documentos y, sobre todo,
   la **identidad del paciente**.
3. Las citas **no copian datos del paciente**: guardan su `patient_id` y consultan al módulo de
   registro cuando necesitan sus datos (RF-26, CA-28).

```
 Paciente                       Personal administrativo
 (zona de citas)                (agenda y registro)
        │                              │
        └──────────────┬───────────────┘
                       ▼
        ┌──────────────────────────────┐
        │ app/main.py                  │  monta ambos módulos
        └───────┬──────────────┬───────┘
                ▼              ▼
   ┌────────────────────┐  ┌────────────────────────────┐
   │ Registro (ej. 1)   │  │ Citas (ej. 2)              │
   │ app/               │◄─┤ app/citas/                 │
   │  services.py       │  │  services.py (casos de uso)│
   │  models.Paciente   │  │  agenda.py (disponibilidad)│
   └─────────┬──────────┘  │  models.py · schemas.py    │
             │             │  repository.py             │
             │             └─────────────┬──────────────┘
             └───────────────┬───────────┘
                             ▼
                      SQLite (una sola base de datos)
```

El sentido de la flecha importa: **citas depende de registro, y registro no sabe que existen las
citas**. Así el módulo fundacional sigue siendo autocontenido.

---

## 2. Stack

El mismo del ejercicio 1: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 sobre SQLite, Jinja2
para las páginas y pytest para las pruebas. No se añade ninguna dependencia nueva: las fechas y
horas se manejan con `datetime` de la biblioteca estándar.

---

## 3. Modelo de datos

### 3.1 Entidades nuevas

```
  centros            especialidades
     │ 1                   │ 1
     │                     │
     └───────┬─────────────┘
             │ N
      ┌──────────────┐ 1      N ┌──────────────────┐
      │ especialistas│──────────│ horarios_consulta│  (plantilla semanal)
      └──────┬───────┘          └──────────────────┘
             │ 1
     ┌───────┼────────────┐
     │ N                  │ N
┌─────────┐        ┌──────────────┐
│  citas  │        │  bloqueos    │
└────┬────┘        └──────────────┘
     │ patient_id (sin clave foránea dura: referencia lógica al módulo de registro)
     ▼
  pacientes (ejercicio 1)
```

| Tabla | Columnas principales | Reglas |
|-------|----------------------|--------|
| `centros` | `id`, `nombre`, `direccion`, `ciudad` | Catálogo (RN-16) |
| `especialidades` | `id`, `nombre` | Catálogo (RN-16) |
| `especialistas` | `id`, `nombre`, `apellidos`, `especialidad_id`, `centro_id`, `duracion_cita_min` | La duración es propiedad del especialista (RN-02) y se puede ajustar (RF-20) |
| `horarios_consulta` | `id`, `especialista_id`, `dia_semana` (0=lunes), `hora_inicio`, `hora_fin` | Plantilla semanal a partir de la cual se generan los huecos (RN-03) |
| `bloqueos` | `id`, `especialista_id`, `inicio`, `fin`, `motivo` | Vacaciones, formación, baja u otro (RN-11) |
| `citas` | `cita_id` (UUID), `codigo` (`CITA-AAAA-NNNNNN`), `patient_id`, `especialista_id`, `inicio`, `duracion_min`, `estado`, `motivo_consulta`, `fecha_reserva`, `fecha_modificacion` | Identidad inmutable, también al reprogramar (RN-01, RN-10) |
| `secuencia_cita` | `anio`, `ultimo_valor` | Secuencial anual del código de cita, como el del ejercicio 1 |

### 3.2 Decisiones del modelo

- **`duracion_min` se guarda en la propia cita**, no se deduce del especialista. Es lo que permite
  cumplir RF-22: cambiar la duración de los huecos no altera las citas ya reservadas.
- **`inicio` es un `datetime` y la cita no guarda `fin`**, que se calcula como `inicio + duracion`.
  Un solo dato que mantener coherente.
- **`patient_id` es una referencia lógica**, con clave foránea a `pacientes`. El módulo de citas lee
  al paciente a través del servicio del ejercicio 1, nunca copiando sus datos personales.
- **Restricción única parcial** sobre `(especialista_id, inicio)` limitada a las citas en estado
  `RESERVADA`: dos pacientes no pueden ocupar el mismo hueco (RN-04, CL-01), pero una cita cancelada
  deja el hueco libre para otra nueva (CL-20).

---

## 4. Decisiones técnicas

### DT-01 — La disponibilidad se calcula, no se almacena
No hay una tabla de "huecos". Los huecos se generan al vuelo a partir del horario semanal del
especialista y su duración, y se filtran descontando bloqueos y citas activas (RN-03, RN-13).

Guardar los huecos en base de datos obligaría a regenerarlos cada vez que cambia un horario, un
bloqueo o una duración, y cualquier fallo en esa regeneración dejaría huecos fantasma: justo el
problema que el módulo viene a resolver. Calcularlos hace imposible que la disponibilidad se
desincronice de la agenda (RF-21).

El coste es recalcular en cada consulta, aceptable para el volumen de un centro de tamaño medio y
acotado por el límite de 60 días del rango (CL-08).

### DT-02 — El solapamiento se comprueba por intervalos, no por igualdad de hora
Dos citas se solapan si `inicio_a < fin_b` y `inicio_b < fin_a`. Comparar solo la hora de inicio
fallaría en cuanto conviven citas de distinta duración, que es exactamente lo que ocurre tras
cambiar la duración de los huecos (ESC-07). El mismo criterio se aplica a los bloqueos (CL-03).

### DT-03 — La unicidad la garantiza la base de datos
Entre comprobar que un hueco está libre y guardar la cita cabe otra reserva. Por eso, además de la
comprobación, hay una **restricción única parcial** `(especialista_id, inicio)` sobre las citas
reservadas: el segundo intento falla en el motor y el servicio traduce ese fallo a
`HUECO_NO_DISPONIBLE` (CL-01, ESC-08). Es la misma estrategia que el ejercicio 1 usa para el
documento del paciente.

### DT-04 — Reprogramar modifica la cita, no crea otra
RF-12 pide que la cita siga siendo la misma. Reprogramar cambia `inicio` y `fecha_modificacion`
dejando intactos `cita_id` y `codigo`. El hueco antiguo se libera solo, porque la disponibilidad se
calcula (DT-01), sin ningún paso de "liberar" que pudiera olvidarse.

### DT-05 — Las políticas del centro viven en la configuración
Antelación mínima para reservar (1 h), para cancelar o reprogramar (24 h), horizonte máximo de
reserva (6 meses) y límite del rango de consulta (60 días) están en `app/citas/config.py`, no
repartidas por el código. Son decisiones de negocio del centro y deben poder cambiarse en un sitio.

### DT-06 — El "ahora" es inyectable
Las reglas de antelación dependen de la hora actual, y una prueba no puede esperar a que pasen 24
horas. Los servicios reciben el instante de referencia como parámetro opcional, con el valor real
por defecto. Esto hace verificables CA-10, CA-17 y CA-19 sin trucos ni esperas.

### DT-07 — Identificación del paciente reutilizando el ejercicio 1
Para saber de quién son las citas, el módulo llama a `ServicioPacientes.buscar_por_documento` o
`buscar_por_codigo_historia` (`registro/RF-10`, `registro/RF-11`) y se queda con el `patient_id`.
No hay tabla de usuarios, ni contraseñas, ni sesiones (§2.1 y §8.4 de la spec).

### DT-08 — El "ahora" es la hora local del centro
Una cita "el martes a las 09:20" son las 09:20 del reloj de la consulta. Si las reglas de
antelación (RN-06, RN-07) comparan esas horas con UTC, en España el sistema se adelanta una o dos
horas según la estación y llega a aceptar la reserva de un hueco que ya ha empezado. Por eso el
módulo tiene un único reloj, `app/citas/reloj.py`, que devuelve la hora local, y ningún fichero del
módulo usa UTC.

### DT-09 — Errores propios que encajan en el formato común
`app/citas/errors.py` define `HuecoNoDisponible` (409), `CitaNoEncontrada` (404),
`CitaNoModificable` (409), `PacienteYaCitado` (409) y `FranjaConCitas` (409), todos heredando del
`ErrorDeNegocio` del ejercicio 1. Así reutilizan el manejador global y el formato uniforme de error
sin tocar nada (RF-25, CA-29).

Cuando un hueco no se puede reservar, el cálculo devuelve un **código de motivo**
(`SIN_ANTELACION`, `FUERA_DE_HORIZONTE`, `OCUPADO`), no un mensaje: quien lo recibe decide el error
sin tener que interpretar un texto que cualquiera podría reescribir.

### DT-10 — Dos zonas en la interfaz, sin control de acceso
La web tendrá `/citas` (zona del paciente) y `/agenda` (zona administrativa), separadas para que
cada una muestre lo suyo, pero **sin permisos**: cualquiera puede abrir ambas. Es una separación de
navegación, no de seguridad, coherente con el apartado 5 del enunciado.

### DT-11 — Catálogo por datos de ejemplo
Centros, especialidades, especialistas y sus horarios se crean con un script de datos de ejemplo
(`datos_ejemplo_citas.py`). No hay pantallas para gestionarlos, porque el enunciado lo excluye
(RN-16, §8.2). Sí se pueden consultar, porque hacen falta para buscar.

---

## 5. Algoritmo de disponibilidad

Es el núcleo del módulo (RF-03, RN-03, RN-13). Para cada día del rango solicitado:

1. Tomar los **tramos del horario** del especialista para ese día de la semana. Si no hay, el día no
   ofrece huecos (CL-06).
2. Desde el inicio de cada tramo, **encadenar huecos** de `duracion_cita_min` minutos mientras
   quepan enteros dentro del tramo (CL-02).
3. **Descartar** los huecos que:
   - solapen un bloqueo del especialista (DT-02, CL-03);
   - solapen una cita en estado `RESERVADA`;
   - empiecen antes de "ahora + antelación mínima" (RN-06);
   - caigan más allá del horizonte de reserva (RN-08).
4. Devolver los restantes, ordenados por fecha y hora.

Si el paciente indica su franja horaria, los huecos que empiecen antes o terminen después de esa
franja se descartan en el paso 2 (RF-02, enunciado §3.1).

Reservar un hueco concreto ejecuta esas mismas comprobaciones sobre ese hueco: la disponibilidad y
la validación de la reserva **comparten código**, así que es imposible que una ofrezca lo que la
otra rechaza.

---

## 6. Contrato de la API

Base: `/api/v1`. Se añade al contrato del ejercicio 1, que no cambia.

| Método | Ruta | Capacidad | Requisitos |
|--------|------|-----------|-----------|
| `GET` | `/catalogo/especialidades` | Apoyo a A | RF-01 |
| `GET` | `/catalogo/centros` | Apoyo a A | RF-01 |
| `GET` | `/especialistas?especialidad_id=&centro_id=` | A | RF-01 |
| `GET` | `/especialistas/{id}/disponibilidad?desde=&hasta=&hora_desde=&hora_hasta=` | A | RF-02, RF-03 |
| `POST` | `/citas` | A | RF-04 a RF-08 |
| `GET` | `/citas?tipo_documento=&numero_documento=` o `?codigo_historia_clinica=` | B | RF-09 |
| `GET` | `/citas/{codigo}` | B | RF-15 |
| `POST` | `/citas/{cita_id}/cancelar` | B | RF-10, RF-13, RF-14, CL-13 |
| `POST` | `/citas/{cita_id}/reprogramar` | B | RF-11 a RF-14 |
| `GET` | `/especialistas/{id}/agenda?desde=&hasta=` | C | RF-16 |
| `POST` | `/especialistas/{id}/bloqueos` | C | RF-17, RF-18 |
| `DELETE` | `/bloqueos/{id}` | C | RF-19 |
| `PATCH` | `/especialistas/{id}/duracion` | C | RF-20, RF-22 |

### 6.1 Pantallas de la interfaz web

| Ruta | Pantalla | Capacidad |
|------|----------|-----------|
| `GET /citas` | Zona del paciente: identificarse | B, entrada a A |
| `GET /citas/buscar` | Elegir especialidad, centro y fechas; ver huecos | A |
| `POST /citas/reservar` | Confirmar la reserva | A |
| `GET /citas/mias` | Mis citas, con cancelar y reprogramar | B |
| `GET /citas/{codigo}` | Detalle de una cita | B |
| `GET /agenda` | Zona administrativa: elegir especialista | C |
| `GET /agenda/{id}` | Agenda: horario, bloqueos y citas | C |
| `POST /agenda/{id}/bloqueos` · `POST /agenda/bloqueos/{id}/levantar` | Bloquear y desbloquear | C |
| `POST /agenda/{id}/duracion` | Ajustar la duración de los huecos | C |

---

## 7. Estructura de ficheros

Lo que se añade al proyecto del ejercicio 1:

```
ejercicio1_49748233S/
├── spec.md · plan.md · tasks.md        (ejercicio 1, sin cambios)
├── app/                                 (ejercicio 1, sin cambios salvo main.py)
│   ├── main.py                          + monta las rutas de citas
│   └── citas/
│       ├── config.py                    Políticas del centro (DT-05)
│       ├── reloj.py                     La hora local del centro (DT-08)
│       ├── models.py                    Centro, Especialidad, Especialista,
│       │                                HorarioConsulta, Bloqueo, Cita, SecuenciaCita
│       ├── schemas.py                   Contratos de entrada y salida
│       ├── errors.py                    Errores propios (DT-08)
│       ├── agenda.py                    Cálculo de disponibilidad (§5)
│       ├── repository.py                Acceso a datos
│       ├── services.py                  Casos de uso de A, B y C
│       ├── api_routes.py                API REST
│       ├── web_routes.py                Interfaz web
│       └── templates/                   Plantillas del módulo
├── citas/                               Documentos SDD de este ejercicio
│   ├── spec.md · plan.md · tasks.md
├── datos_ejemplo_citas.py               Catálogo y agenda de ejemplo (DT-10)
└── tests/
    ├── test_citas_agenda.py             Disponibilidad (unitarias)
    ├── test_citas_reserva.py            CA-01 a CA-12
    ├── test_citas_cambios.py            CA-13 a CA-20
    ├── test_citas_gestion_agenda.py     CA-21 a CA-27
    └── test_citas_aplicacion.py         CA-28 a CA-31
```

---

## 8. Riesgos

| Riesgo | Mitigación |
|--------|-----------|
| Dos pacientes reservan el mismo hueco a la vez | Restricción única en la base de datos, no solo comprobación previa (DT-03) |
| La disponibilidad deja de reflejar la agenda real | La disponibilidad se calcula, nunca se almacena (DT-01) |
| Cambiar la duración descoloca citas existentes | La duración se guarda en cada cita (§3.2, RF-22) |
| Bloquear un día deja pacientes citados con un especialista ausente | El bloqueo se rechaza si hay citas dentro, informando de cuáles (RF-18, CA-23) |
| Las reglas de antelación son difíciles de probar | El instante de referencia es inyectable (DT-06) |
| El módulo de citas acopla o rompe el de registro | Dependencia en un solo sentido; el ejercicio 1 no se modifica (§1) |
| Confundir la hora local con UTC en las reglas de antelación | Un único reloj para todo el módulo (DT-08), con prueba que lo verifica |
| Que alguien opere sobre la cita de otro paciente | Toda operación sobre una cita exige identificarse, también por API (CL-13) |

---

## 9. Estrategia de pruebas

- **Unitarias** del generador de huecos: tramos, duraciones, bloqueos y casos límite, sin base de
  datos ni HTTP.
- **De integración** contra la aplicación real, con base de datos en memoria, una por cada criterio
  de aceptación, nombradas `test_CA_xx_...`.
- Las pruebas del ejercicio 1 **deben seguir pasando sin cambios**: es la comprobación de que el
  módulo se ha ampliado sin romper lo anterior.
- **De regresión:** cada fallo detectado en una revisión deja tras de sí una prueba que lo habría
  cazado (el reloj local, la propiedad de la cita en la API y la franja horaria).
- **Criterio de terminación:** los 32 criterios de aceptación de `citas/spec.md` tienen prueba en
  verde, y las 76 pruebas del ejercicio 1 siguen en verde.
