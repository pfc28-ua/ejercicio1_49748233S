# HIS — Registro de Pacientes y Programación de Citas

**Spec-Driven Development** · Ejercicios 1 y 2

Proyecto del Sistema de Información de Gestión Hospitalaria con dos módulos. El del ejercicio 2
amplía el del ejercicio 1 y reutiliza su identidad del paciente.

## Ejercicio 1 · Registro e Identificación de Pacientes

Cubre las tres capacidades de su enunciado:

1. **Registro e identificación** del paciente, con sus datos personales y su número de seguro o
   mutua, y una identidad única reutilizable por el resto de módulos.
2. **Búsqueda y verificación de identidad** por documento de identidad o por código de historia
   clínica.
3. **Modificación y actualización** de los datos personales y de contacto.

## Ejercicio 2 · Programación de Citas Médicas

Amplía el proyecto anterior con:

1. **Reservar una cita online** — el paciente busca por especialidad, centro y disponibilidad, y
   reserva su hueco.
2. **Cancelar o reprogramar** — sin perder la cita ni repetir la búsqueda: al reprogramar conserva
   su código.
3. **Gestionar la agenda** — el personal administrativo bloquea franjas (vacaciones, formación,
   baja) y ajusta la duración de los huecos.

## Documentos SDD

| Ejercicio | Documentos |
|-----------|-----------|
| 1 · Registro | [`spec.md`](spec.md), [`plan.md`](plan.md), [`tasks.md`](tasks.md) — 23 requisitos, 13 reglas, 29 criterios de aceptación y 18 casos límite. |
| 2 · Citas | [`citas/spec.md`](citas/spec.md), [`citas/plan.md`](citas/plan.md), [`citas/tasks.md`](citas/tasks.md) — 26 requisitos, 17 reglas, 32 criterios de aceptación y 20 casos límite. |

El código cita en sus comentarios el requisito (`RF`), la regla (`RN`), la decisión técnica (`DT`)
o el caso límite (`CL`) que implementa. Cada prueba lleva en su nombre el criterio de aceptación
que verifica (`test_CA_01_...`).

## Ejecución

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

python datos_ejemplo.py         # opcional: pacientes de ejemplo
python datos_ejemplo_citas.py   # opcional: centros, especialidades y especialistas
uvicorn app.main:app --reload
```

| Dirección | Zona |
|-----------|------|
| http://127.0.0.1:8000 | Registro de pacientes (personal administrativo) |
| http://127.0.0.1:8000/citas | Citas del paciente: pedir, cancelar y reprogramar |
| http://127.0.0.1:8000/agenda | Agenda de los especialistas (personal administrativo) |
| http://127.0.0.1:8000/docs | Documentación de la API |

## Pruebas

```bash
python -m pytest
```

157 pruebas: una por cada uno de los 29 criterios del ejercicio 1 y de los 32 del ejercicio 2, más
las de casos límite y las unitarias del núcleo de identidad y del cálculo de disponibilidad.

## Demostración

### Registro de pacientes (ejercicio 1)

Con los datos de ejemplo cargados:

1. **Buscar** `12345678Z` → se abre la ficha de María López con sus datos para verificar la
   identidad.
2. **Buscar** `HC-2026-000003` → ficha de Ana Ferreira.
3. **Buscar** `11111111H` → no existe; se ofrece registrarlo con el DNI ya rellenado.
4. **Registrar** el paciente → el sistema le asigna su código de historia clínica y su `patient_id`.
5. **Registrarlo otra vez** → aviso de documento duplicado con enlace a la ficha existente.
6. **Modificar** su teléfono o completar su email → su identidad no cambia.

### Citas (ejercicio 2)

1. En **Citas**, identifícate con `12345678Z`.
2. **Pedir cita nueva** → elige *Dermatología* y un hueco de Elena Ruiz Navarro.
3. En **Mis citas**, prueba a **reprogramar**: la cita mantiene su código.
4. En **Agenda**, entra en esa especialista y bloquea la franja de esa cita: el sistema lo impide e
   indica qué cita lo impide.
5. Cambia su duración de 20 a 30 minutos: los huecos futuros cambian, la cita reservada no.

## La identidad del paciente

| | `patient_id` | Código de historia clínica |
|---|---|---|
| Formato | UUID v4 | `HC-AAAA-NNNNNN` |
| Uso | Referencia para los demás módulos del HIS | Identificador legible para el paciente |
| Se modifica | Nunca | Nunca |

El módulo de citas es la demostración de que esa identidad es reutilizable: cada cita guarda el
`patient_id` y **no copia ningún dato personal** del paciente. Si se corrige el nombre de un
paciente, sus citas lo reflejan al instante.

## API

| Método | Ruta | Capacidad |
|--------|------|-----------|
| `POST` | `/api/v1/pacientes` | Registro |
| `GET` | `/api/v1/pacientes/buscar?tipo_documento=&numero_documento=` | Búsqueda por documento |
| `GET` | `/api/v1/pacientes/buscar?codigo_historia_clinica=` | Búsqueda por código de historia clínica |
| `GET` | `/api/v1/pacientes/{patient_id}` | Recuperación por identidad |
| `PATCH` | `/api/v1/pacientes/{patient_id}` | Modificación |
| `GET` | `/api/v1/especialistas` | Buscar especialistas |
| `GET` | `/api/v1/especialistas/{id}/disponibilidad` | Huecos libres |
| `POST` | `/api/v1/citas` | Reservar |
| `POST` | `/api/v1/citas/{id}/cancelar` · `/reprogramar` | Cancelar o reprogramar |
| `GET` | `/api/v1/especialistas/{id}/agenda` | Agenda del especialista |
| `POST` | `/api/v1/especialistas/{id}/bloqueos` | Bloquear una franja |
| `PATCH` | `/api/v1/especialistas/{id}/duracion` | Duración de los huecos |

## Fuera de alcance

Según el enunciado: el resto de módulos del HIS, la gestión de especialidades, centros y permisos,
la integración con aseguradoras o mutuas y el inicio de sesión o control de acceso por rol. Tampoco
se incluye nada que no pidan las tres capacidades (bajas, histórico de cambios, búsqueda por
nombre…); el detalle está en la sección 8 de cada especificación.

En el ejercicio 2, el paciente **se identifica** con su documento o su código de historia clínica
para ver sus citas, pero no hay contraseñas, sesiones ni permisos: es identificación, no
autenticación (ver `citas/spec.md` §2.1).
