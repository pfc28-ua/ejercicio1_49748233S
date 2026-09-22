# Registro e Identificación de Pacientes — HIS

Ejercicio 1 · **Spec-Driven Development**

Módulo del Sistema de Información de Gestión Hospitalaria que cubre las tres capacidades del
enunciado:

1. **Registro e identificación** del paciente, con sus datos personales y su número de seguro o
   mutua, y una identidad única reutilizable por el resto de módulos.
2. **Búsqueda y verificación de identidad** por documento de identidad o por código de historia
   clínica.
3. **Modificación y actualización** de los datos personales y de contacto.

## Documentos SDD

| Documento | Contenido |
|-----------|-----------|
| [`spec.md`](spec.md) | Objetivo y contexto, usuarios, escenarios, 23 requisitos funcionales, 13 reglas de negocio, 29 criterios de aceptación, 18 casos límite y fuera de alcance. |
| [`plan.md`](plan.md) | Arquitectura, modelo de datos y decisiones técnicas. |
| [`tasks.md`](tasks.md) | 40 tareas trazadas a su requisito de origen. |

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
uvicorn app.main:app --reload
```

- Interfaz web: http://127.0.0.1:8000
- Documentación de la API: http://127.0.0.1:8000/docs

## Pruebas

```bash
python -m pytest
```

76 pruebas: una por cada uno de los 29 criterios de aceptación, más las de los casos límite y las
unitarias del núcleo de identidad.

## Demostración

Con los datos de ejemplo cargados:

1. **Buscar** `12345678Z` → se abre la ficha de María López con sus datos para verificar la
   identidad.
2. **Buscar** `HC-2026-000003` → ficha de Ana Ferreira.
3. **Buscar** `11111111H` → no existe; se ofrece registrarlo con el DNI ya rellenado.
4. **Registrar** el paciente → el sistema le asigna su código de historia clínica y su `patient_id`.
5. **Registrarlo otra vez** → aviso de documento duplicado con enlace a la ficha existente.
6. **Modificar** su teléfono o completar su email → su identidad no cambia.

## La identidad del paciente

| | `patient_id` | Código de historia clínica |
|---|---|---|
| Formato | UUID v4 | `HC-AAAA-NNNNNN` |
| Uso | Referencia para los demás módulos del HIS | Identificador legible para el paciente |
| Se modifica | Nunca | Nunca |

Otros módulos (citas, historia clínica, facturación) guardarían el `patient_id` y obtendrían el
paciente con `GET /api/v1/pacientes/{patient_id}`.

## API

| Método | Ruta | Capacidad |
|--------|------|-----------|
| `POST` | `/api/v1/pacientes` | Registro |
| `GET` | `/api/v1/pacientes/buscar?tipo_documento=&numero_documento=` | Búsqueda por documento |
| `GET` | `/api/v1/pacientes/buscar?codigo_historia_clinica=` | Búsqueda por código de historia clínica |
| `GET` | `/api/v1/pacientes/{patient_id}` | Recuperación por identidad |
| `PATCH` | `/api/v1/pacientes/{patient_id}` | Modificación |

## Fuera de alcance

Según el enunciado: el resto de módulos del HIS, la gestión de especialidades, centros y permisos,
la integración con aseguradoras o mutuas y el inicio de sesión o control de acceso por rol. Tampoco
se incluye nada que no pidan las tres capacidades (bajas, histórico de cambios, búsqueda por
nombre…); el detalle está en la sección 8 de [`spec.md`](spec.md).
