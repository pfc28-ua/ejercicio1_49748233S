# spec.md — Registro e Identificación de Pacientes

**Sistema:** Sistema de Información de Gestión Hospitalaria (HIS)
**Módulo:** Registro e Identificación del Paciente (módulo fundacional)
**Versión:** 1.0
**Estado:** Aprobada — redactada antes de escribir código
**Metodología:** Spec-Driven Development (SDD)

---

## 1. Objetivo y contexto de negocio

### 1.1 Contexto

El HIS da soporte a la actividad asistencial y administrativa de un centro médico de tamaño
medio (un hospital con varias especialidades o una red de clínicas ambulatorias). Su alcance
completo cubre el ciclo de vida del paciente: registro, citas, historia clínica, prescripción,
facturación y notificaciones.

Todos esos módulos descansan sobre una pieza fundacional: **la identidad del paciente**. Sin un
registro fiable y una identidad única, ningún otro módulo puede funcionar correctamente: un mismo
paciente registrado dos veces tendría dos historias clínicas parciales y citas y facturas
repartidas entre dos fichas.

### 1.2 Objetivo

Construir el módulo que **registra, identifica y mantiene** los datos de cada paciente dentro del
HIS, asignándole una identidad única que el resto de módulos pueda reutilizar para referirse a él
sin ambigüedad.

El módulo cubre exactamente las tres capacidades del enunciado:

| Capacidad | Descripción |
|-----------|-------------|
| **A · Registro e identificación** | Registrar un paciente nuevo con sus datos personales y su número de seguro o mutua, y asociarle una identidad única. |
| **B · Búsqueda y verificación de identidad** | Buscar y verificar a un paciente ya registrado a partir de su documento de identidad o de su código de historia clínica, para reconocerlo en lugar de duplicarlo. |
| **C · Modificación y actualización de datos** | Modificar o completar los datos personales y de contacto de un paciente ya registrado. |

### 1.3 Objetivos de negocio medibles

| ID | Objetivo | Indicador |
|----|----------|-----------|
| OBJ-01 | Evitar el registro duplicado de pacientes | 0 pacientes con el mismo documento de identidad |
| OBJ-02 | Dar a cada paciente una identidad única y reutilizable | 100 % de pacientes con identificador interno y código de historia clínica únicos e inmutables |
| OBJ-03 | Reconocer a un paciente ya existente | Localización por documento o código de historia clínica en una única operación |
| OBJ-04 | Mantener los datos actualizados sin perder la identidad | Ninguna actualización modifica el identificador ni el código de historia clínica |

---

## 2. Usuarios

### 2.1 Usuario del módulo

| Perfil | Descripción | Qué hace en este módulo |
|--------|-------------|-------------------------|
| **Personal administrativo** | Único perfil contemplado en esta práctica. Trabaja en admisión. | Registra pacientes, los busca y verifica su identidad, y modifica o completa sus datos. |

Conforme al enunciado, **no hay inicio de sesión ni control de acceso por rol**: se asume un
único perfil de usuario administrativo que gestiona el registro.

### 2.2 Consumidores de la identidad (fuera del alcance)

Los módulos de citas, historia clínica, prescripción y facturación no se implementan, pero
condicionan el diseño: necesitan una **identidad del paciente única, estable y consultable** que
puedan guardar como referencia al paciente.

---

## 3. Escenarios de usuario

### ESC-01 — Alta de un paciente que nunca ha estado en el centro
María llega a admisión por primera vez. El administrativo busca su DNI: no hay resultados. Registra
sus datos personales, de contacto y su número de seguro o mutua. El sistema le asigna un
identificador interno y un código de historia clínica, por ejemplo `HC-2026-000001`.

### ESC-02 — El paciente ya existe y se reconoce
Juan vuelve al centro. El administrativo busca por su DNI, el sistema devuelve su ficha y la
admisión continúa sobre ella. No se crea un segundo registro.

### ESC-03 — Intento de alta duplicada
El administrativo intenta registrar a Juan como paciente nuevo. El sistema rechaza el alta,
indica que ese documento ya está registrado e informa del código de historia clínica existente.

### ESC-04 — Verificación de identidad por código de historia clínica
Un paciente se presenta con su código de historia clínica. El administrativo lo busca y el sistema
muestra sus datos identificativos (nombre, apellidos, fecha de nacimiento y documento), que el
administrativo contrasta con la persona que tiene delante.

### ESC-05 — Cambio de domicilio y de teléfono
Ana se ha mudado y ha cambiado de móvil. El administrativo localiza su ficha y actualiza dirección
y teléfono. Su identidad no cambia.

### ESC-06 — Completar un dato que quedó vacío
En el alta de Luis no se recogió el email. En una visita posterior se añade sin tocar el resto de
la ficha.

### ESC-07 — Paciente extranjero sin DNI español
Una paciente se identifica con pasaporte. El sistema acepta el registro validando el formato de
pasaporte en lugar de la letra del DNI.

### ESC-08 — Corrección de un documento mal tecleado
Se detecta que el NIE de un paciente se introdujo con un error. El administrativo lo corrige; el
sistema comprueba que el nuevo documento no pertenezca ya a otro paciente.

---

## 4. Requisitos funcionales

### 4.1 Capacidad A — Registro e identificación del paciente

| ID | Requisito |
|----|-----------|
| RF-01 | El sistema debe permitir registrar un paciente nuevo capturando sus **datos personales**: nombre, primer apellido, segundo apellido (opcional), fecha de nacimiento y sexo. |
| RF-02 | El sistema debe capturar el **documento de identidad** del paciente: tipo (`DNI`, `NIE` o `PASAPORTE`) y número. |
| RF-03 | El sistema debe capturar los **datos de contacto**: teléfono, email y dirección postal (calle, ciudad, código postal, provincia y país). Todos son opcionales. |
| RF-04 | El sistema debe capturar el **número de seguro o mutua** del paciente, junto con el nombre de la entidad (seguro o mutua) a la que pertenece. |
| RF-05 | Al registrar un paciente, el sistema debe asociarle una **identidad única**: un identificador interno (`patient_id`) y un **código de historia clínica** legible. |
| RF-06 | La identidad la genera el sistema: el usuario no puede proporcionarla ni modificarla. |
| RF-07 | El sistema debe rechazar el alta si el documento de identidad ya está registrado, indicando el código de historia clínica del paciente existente. |
| RF-08 | El sistema debe validar los datos antes de guardar nada y comunicar todos los errores detectados a la vez. |
| RF-09 | Tras un alta correcta, el sistema debe devolver la ficha del paciente con su identidad asignada. |

### 4.2 Capacidad B — Búsqueda y verificación de identidad

| ID | Requisito |
|----|-----------|
| RF-10 | El sistema debe permitir **buscar un paciente por su documento de identidad** (tipo y número). |
| RF-11 | El sistema debe permitir **buscar un paciente por su código de historia clínica**. |
| RF-12 | El sistema debe indicar de forma inequívoca cuándo **no existe** ningún paciente con el dato buscado, de modo que se pueda proceder a su registro. |
| RF-13 | El resultado de la búsqueda debe mostrar los **datos identificativos** del paciente (nombre, apellidos, fecha de nacimiento, documento y código de historia clínica), para que el administrativo **verifique** que corresponden a la persona que tiene delante. |
| RF-14 | El sistema debe permitir **recuperar un paciente a partir de su identificador interno**, de modo que otros módulos del HIS puedan reutilizar la identidad. |

### 4.3 Capacidad C — Modificación y actualización de datos

| ID | Requisito |
|----|-----------|
| RF-15 | El sistema debe permitir **modificar los datos personales** de un paciente registrado, incluidos su documento de identidad y su número de seguro o mutua. |
| RF-16 | El sistema debe permitir **modificar o completar los datos de contacto** (teléfono, email y dirección). |
| RF-17 | La actualización debe ser **parcial**: los datos que no se modifican conservan su valor. |
| RF-18 | Un dato opcional puede **dejarse vacío** al modificarlo. |
| RF-19 | Al corregir el documento de identidad, el sistema debe comprobar que el nuevo documento no pertenezca ya a otro paciente. |
| RF-20 | Ninguna modificación puede alterar la identidad del paciente (`patient_id` y código de historia clínica). |

### 4.4 Requisitos de la aplicación

| ID | Requisito |
|----|-----------|
| RF-21 | Las tres capacidades deben estar disponibles como **API REST**, que es la vía por la que otros módulos del HIS reutilizarán la identidad del paciente. |
| RF-22 | Las tres capacidades deben estar disponibles en una **interfaz web** para el personal administrativo. |
| RF-23 | Los errores deben comunicarse con un **formato uniforme**: código de error, mensaje y detalle por campo. |

---

## 5. Reglas de negocio

| ID | Regla |
|----|-------|
| RN-01 | **Unicidad.** No pueden existir dos pacientes con el mismo documento de identidad (tipo y número). El número se normaliza antes de comparar: sin espacios, guiones ni puntos y en mayúsculas. |
| RN-02 | **Identificador interno.** El `patient_id` es un UUID v4 generado por el sistema. Es la referencia que los demás módulos del HIS guardarán del paciente. Es inmutable. |
| RN-03 | **Código de historia clínica.** Formato `HC-AAAA-NNNNNN`: año de alta y secuencial de 6 dígitos que se reinicia cada año. Es único e inmutable. |
| RN-04 | **DNI.** 8 dígitos y una letra de control, que debe ser la que corresponde al resto de dividir el número entre 23 según la tabla `TRWAGMYFPDXBNJZSQVHLCKE`. |
| RN-05 | **NIE.** Letra `X`, `Y` o `Z`, 7 dígitos y letra de control, calculada sustituyendo la letra inicial por `0`, `1` o `2` y aplicando RN-04. |
| RN-06 | **Pasaporte.** Entre 5 y 20 caracteres alfanuméricos. |
| RN-07 | **Fecha de nacimiento.** Obligatoria, no futura y sin superar los 130 años de edad. |
| RN-08 | **Nombre y primer apellido.** Obligatorios, de 2 a 60 caracteres. |
| RN-09 | **Email.** Opcional; si se informa, con formato válido. Se guarda en minúsculas. |
| RN-10 | **Teléfono.** Opcional; si se informa, entre 9 y 15 dígitos, con prefijo `+` y separadores admitidos, que se eliminan al guardar. |
| RN-11 | **Código postal.** Si el país es España, 5 dígitos cuyos dos primeros estén entre `01` y `52`. |
| RN-12 | **Seguro o mutua.** La entidad y el número son obligatorios. El número se guarda como dato del paciente, sin validarlo contra ninguna aseguradora. |
| RN-13 | **Normalización.** Se eliminan los espacios sobrantes de los textos; el documento se guarda en mayúsculas y sin separadores. |

---

## 6. Criterios de aceptación

Formato *Dado / Cuando / Entonces*. Cada criterio se verifica con una prueba automática.

### Capacidad A — Registro e identificación

**CA-01 — El alta asigna una identidad única** *(RF-01 a RF-05, RF-09, RN-02, RN-03)*
- **Dado** que no existe ningún paciente con el DNI `12345678Z`
- **Cuando** se registra un paciente con datos válidos y ese DNI
- **Entonces** se crea el paciente y se devuelve su ficha con un `patient_id` en formato UUID y un código de historia clínica con formato `HC-AAAA-NNNNNN`.

**CA-02 — El código de historia clínica es secuencial y único** *(RN-03)*
- **Dado** que el primer paciente del año recibió `HC-AAAA-000001`
- **Cuando** se registra un segundo paciente ese año
- **Entonces** recibe `HC-AAAA-000002`.

**CA-03 — El usuario no puede imponer la identidad** *(RF-06)*
- **Cuando** se registra un paciente enviando un `patient_id` y un código de historia clínica propios
- **Entonces** se ignoran y el sistema asigna los suyos.

**CA-04 — Se rechaza el alta duplicada** *(RF-07, RN-01)*
- **Dado** un paciente registrado con DNI `12345678Z`
- **Cuando** se intenta registrar otro paciente con ese DNI
- **Entonces** se rechaza con el código `PACIENTE_DUPLICADO`, se informa del código de historia clínica existente y no se crea ningún registro.

**CA-05 — El documento se normaliza antes de comparar** *(RN-01, RN-13)*
- **Dado** un paciente registrado con DNI `12345678Z`
- **Cuando** se intenta registrar otro con ` 12345678-z `
- **Entonces** se detecta como duplicado.

**CA-06 — Se rechaza un DNI con letra incorrecta** *(RN-04)*
- **Cuando** se intenta registrar un paciente con DNI `12345678A`
- **Entonces** se rechaza con un error en `numero_documento`.

**CA-07 — Se acepta un NIE válido** *(RN-05)*
- **Cuando** se registra un paciente con NIE `X1234567L`
- **Entonces** el alta se realiza.

**CA-08 — Se acepta un pasaporte** *(RN-06, ESC-07)*
- **Cuando** se registra un paciente con pasaporte `AB123456`
- **Entonces** el alta se realiza.

**CA-09 — Se rechaza una fecha de nacimiento futura** *(RN-07)*
- **Cuando** se intenta registrar un paciente nacido mañana
- **Entonces** se rechaza con un error en `fecha_nacimiento`.

**CA-10 — Se exige el número de seguro o mutua** *(RF-04, RN-12)*
- **Cuando** se intenta registrar un paciente sin entidad ni número de seguro o mutua
- **Entonces** se rechaza con errores en `entidad_aseguradora` y `numero_poliza`.

**CA-11 — Todos los errores se comunican a la vez** *(RF-08)*
- **Cuando** se envía un alta con el nombre vacío, un DNI inválido y una fecha futura
- **Entonces** la respuesta incluye los tres errores, cada uno asociado a su campo.

### Capacidad B — Búsqueda y verificación de identidad

**CA-12 — Búsqueda por documento de identidad** *(RF-10)*
- **Dado** un paciente con DNI `12345678Z`
- **Cuando** se busca por tipo `DNI` y número `12345678Z`
- **Entonces** se devuelve la ficha de ese paciente.

**CA-13 — Búsqueda por código de historia clínica** *(RF-11)*
- **Dado** un paciente con código `HC-AAAA-000001`
- **Cuando** se busca por ese código
- **Entonces** se devuelve la ficha de ese paciente.

**CA-14 — Paciente inexistente** *(RF-12)*
- **Cuando** se busca un documento o un código de historia clínica que no está registrado
- **Entonces** se responde con el código `PACIENTE_NO_ENCONTRADO`.

**CA-15 — La búsqueda devuelve los datos para verificar la identidad** *(RF-13, ESC-04)*
- **Cuando** se encuentra a un paciente
- **Entonces** la respuesta incluye su nombre, apellidos, fecha de nacimiento, documento, código de historia clínica y `patient_id`.

**CA-16 — Recuperación por identificador interno** *(RF-14)*
- **Dado** un paciente registrado
- **Cuando** se solicita por su `patient_id`
- **Entonces** se devuelve su ficha.

### Capacidad C — Modificación y actualización de datos

**CA-17 — Modificación de datos de contacto** *(RF-16, ESC-05)*
- **Cuando** se modifican el teléfono y la dirección de un paciente
- **Entonces** la ficha refleja los nuevos valores.

**CA-18 — La actualización es parcial** *(RF-17)*
- **Cuando** se modifica solo el email
- **Entonces** el resto de datos conserva su valor.

**CA-19 — Completar un dato vacío** *(RF-16, ESC-06)*
- **Dado** un paciente registrado sin email
- **Cuando** se informa su email
- **Entonces** la ficha pasa a tenerlo, en minúsculas.

**CA-20 — Vaciar un dato opcional** *(RF-18)*
- **Cuando** se envía el segundo apellido vacío
- **Entonces** el dato queda vacío en la ficha.

**CA-21 — Modificación de datos personales** *(RF-15)*
- **Cuando** se modifican el nombre y el número de seguro o mutua de un paciente
- **Entonces** la ficha refleja los nuevos valores.

**CA-22 — La identidad no cambia** *(RF-20)*
- **Cuando** se modifica un paciente, incluso enviando otro `patient_id` y otro código de historia clínica
- **Entonces** su `patient_id` y su código de historia clínica siguen siendo los mismos.

**CA-23 — Corrección del documento de identidad** *(RF-15, RF-19, ESC-08)*
- **Cuando** se corrige el documento de un paciente por uno válido que no está registrado
- **Entonces** la ficha refleja el nuevo documento.

**CA-24 — No se puede usar el documento de otro paciente** *(RF-19, RN-01)*
- **Dado** dos pacientes A y B
- **Cuando** se intenta poner en B el documento de A
- **Entonces** se rechaza con `PACIENTE_DUPLICADO` y B no cambia.

**CA-25 — Se rechazan datos inválidos al modificar** *(RF-08, RN-09)*
- **Cuando** se modifica el email con un formato incorrecto
- **Entonces** se rechaza con un error en `email` y la ficha no cambia.

**CA-26 — Modificar un paciente inexistente** *(RF-12)*
- **Cuando** se intenta modificar un `patient_id` que no existe
- **Entonces** se responde con `PACIENTE_NO_ENCONTRADO`.

### Requisitos de la aplicación

**CA-27 — Formato uniforme de error** *(RF-23)*
- **Cuando** se produce un error de validación, de duplicado o de paciente no encontrado
- **Entonces** la respuesta contiene `codigo`, `mensaje` y, si procede, `detalles` con `campo` y `mensaje`.

**CA-28 — Interfaz web** *(RF-22)*
- **Cuando** el administrativo usa la aplicación web
- **Entonces** puede buscar un paciente, registrarlo y modificar sus datos sin usar la API.

**CA-29 — API REST** *(RF-21)*
- **Cuando** se consulta la documentación de la API
- **Entonces** incluye las operaciones de registro, búsqueda, recuperación por identificador y modificación.

---

## 7. Casos límite

| ID | Caso | Comportamiento esperado |
|----|------|-------------------------|
| CL-01 | Documento con espacios, guiones, puntos o minúsculas | Se normaliza antes de validar, comparar y buscar (RN-01, RN-13). |
| CL-02 | Dos altas simultáneas con el mismo documento | Una restricción de unicidad en la base de datos impide la segunda, que se rechaza como duplicada. |
| CL-03 | Dos altas simultáneas (código de historia clínica) | El secuencial se obtiene dentro de la transacción del alta; nunca se repite un código. |
| CL-04 | Cambio de año | El secuencial del código de historia clínica vuelve a empezar en `000001`. |
| CL-05 | Más de 999 999 altas en un año | Se produce un error explícito en lugar de generar un código con formato inválido. |
| CL-06 | Paciente nacido hoy | Se acepta: solo se rechazan las fechas futuras. |
| CL-07 | Fecha de nacimiento de hace más de 130 años | Se rechaza (RN-07). |
| CL-08 | Nombre de un solo carácter | Se rechaza (RN-08). |
| CL-09 | Nombres con tildes, ñ, apóstrofes o guiones | Se aceptan. |
| CL-10 | Paciente sin ningún dato de contacto | Se acepta: son opcionales (RF-03). |
| CL-11 | Código postal `99999` con país España | Se rechaza (RN-11). |
| CL-12 | Código postal extranjero | Se acepta sin aplicar el formato español (RN-11). |
| CL-13 | Email en mayúsculas | Se guarda en minúsculas (RN-09). |
| CL-14 | Teléfono con prefijo internacional y separadores | Se guarda como dígitos con su prefijo (RN-10). |
| CL-15 | Búsqueda por un código de historia clínica con formato incorrecto | Se rechaza como error de validación. |
| CL-16 | Búsqueda sin indicar documento ni código de historia clínica | Se rechaza como error de validación. |
| CL-17 | `patient_id` con formato que no es UUID | Se rechaza como error de validación. |
| CL-18 | Modificación sin ningún dato | Se rechaza como error de validación. |

---

## 8. Fuera de alcance

Conforme al apartado 5 del enunciado:

1. **El resto de módulos del HIS:** citas, historia clínica, prescripción, facturación y
   notificaciones. Solo se deja la identidad del paciente preparada para que puedan reutilizarla.
2. **La gestión de especialidades, centros o permisos**, responsabilidad del administrador del
   sistema.
3. **Cualquier integración real con aseguradoras o mutuas:** el número de seguro o mutua se
   captura como dato del paciente.
4. **Inicio de sesión y control de acceso por rol:** se asume un único perfil administrativo.

Tampoco forman parte de las tres capacidades pedidas, y por tanto quedan fuera:

5. **Baja o eliminación de pacientes.**
6. **Histórico o auditoría de cambios.** La trazabilidad y el resto del cumplimiento normativo
   (RGPD) son requisitos transversales de todo el HIS, no de este módulo.
7. **Búsqueda por nombre, listados y estadísticas de pacientes.** La búsqueda se hace por
   documento de identidad o por código de historia clínica.
8. **Fusión de fichas duplicadas** ya existentes.

---

## 9. Trazabilidad

| Capacidad del enunciado | Requisitos | Criterios de aceptación |
|-------------------------|-----------|-------------------------|
| 3.1 Registro e identificación | RF-01 a RF-09 | CA-01 a CA-11 |
| 3.2 Búsqueda y verificación | RF-10 a RF-14 | CA-12 a CA-16 |
| 3.3 Modificación y actualización | RF-15 a RF-20 | CA-17 a CA-26 |
| Aplicación (API e interfaz) | RF-21 a RF-23 | CA-27 a CA-29 |

---

## 10. Glosario

| Término | Definición |
|---------|------------|
| **HIS** | Sistema de información hospitalaria. |
| **`patient_id`** | Identificador interno del paciente (UUID v4), inmutable. Referencia que usan los demás módulos. |
| **Código de historia clínica** | Identificador legible del paciente, con formato `HC-AAAA-NNNNNN`. |
| **Documento de identidad** | Tipo (DNI, NIE o pasaporte) y número con los que se identifica al paciente. |
| **Seguro o mutua** | Entidad que cubre la asistencia del paciente y su número de póliza o afiliación. |
