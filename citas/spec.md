# spec.md — Programación de Citas Médicas

**Sistema:** Sistema de Información de Gestión Hospitalaria (HIS)
**Módulo:** Programación de citas (ejercicio 2)
**Amplía:** el módulo de Registro e Identificación de Pacientes (ejercicio 1)
**Versión:** 1.0
**Estado:** Aprobada — redactada antes de escribir código
**Metodología:** Spec-Driven Development (SDD)

> Los identificadores `RF`, `RN`, `CA` y `CL` de este documento pertenecen al módulo de citas.
> Cuando se cite un requisito del módulo de registro se indicará como `registro/RF-xx`.

---

## 1. Objetivo y contexto de negocio

### 1.1 Contexto

El HIS da soporte a la actividad asistencial y administrativa de un centro médico de tamaño medio.
Sobre la identidad del paciente, que construyó el ejercicio 1, se apoya el resto del sistema. La
primera pieza que se apoya en ella es la **programación de citas**: sin cita no hay consulta, y sin
consulta no hay historia clínica, prescripción ni facturación.

Hoy la agenda es el punto de fricción del centro: el paciente llama por teléfono para pedir hora,
el administrativo consulta la disponibilidad a mano, y cuando un especialista se va de vacaciones o
causa baja hay que rehacer citas una por una. El resultado son huecos que se ofrecen y ya no
existen, pacientes citados con un especialista ausente y tiempo de mostrador gastado en tareas que
el propio paciente podría resolver.

### 1.2 Objetivo

Construir el módulo que permite **reservar, cancelar y reprogramar citas** y **mantener la agenda
de cada especialista**, de modo que la disponibilidad que ve el paciente sea siempre real.

El módulo cubre exactamente las tres capacidades del enunciado:

| Capacidad | Descripción |
|-----------|-------------|
| **A · Reservar una cita online** | El paciente busca un especialista por especialidad, centro y disponibilidad horaria, y reserva la cita. |
| **B · Cancelar o reprogramar** | El paciente cancela o cambia la fecha de una cita ya reservada, sin repetir toda la búsqueda. |
| **C · Gestionar la agenda** | El personal administrativo bloquea franjas de un especialista y ajusta la duración de sus huecos. |

### 1.3 Objetivos de negocio medibles

| ID | Objetivo | Indicador |
|----|----------|-----------|
| OBJ-01 | Que la disponibilidad ofrecida sea real | 0 citas reservadas sobre franjas bloqueadas o ya ocupadas |
| OBJ-02 | Evitar el solapamiento de citas | 0 pares de citas activas del mismo especialista que se solapen |
| OBJ-03 | Que el paciente resuelva su cita sin llamar al centro | Reserva, cancelación y reprogramación disponibles desde la aplicación |
| OBJ-04 | Que reprogramar no obligue a empezar de cero | La cita reprogramada conserva su identificador y su código |
| OBJ-05 | Reutilizar la identidad del paciente | 100 % de las citas asociadas a un `patient_id` existente, sin duplicar sus datos |

### 1.4 Relación con el módulo de registro (ejercicio 1)

Este módulo **no vuelve a modelar al paciente**. Cada cita guarda el `patient_id` del módulo de
registro (`registro/RN-02`) y obtiene de él los datos del paciente cuando los necesita. Es la
demostración práctica de que aquella identidad es reutilizable.

---

## 2. Usuarios

| Perfil | Qué hace en este módulo |
|--------|-------------------------|
| **Paciente** | Consulta la disponibilidad, reserva su cita, y cancela o reprograma las que ya tiene. |
| **Personal administrativo** | Mantiene la agenda de cada especialista: bloquea franjas por vacaciones, formación o baja, y ajusta la duración de los huecos. |

### 2.1 Supuesto sobre el acceso

El enunciado excluye el **inicio de sesión y el control de acceso por rol**. Este módulo lo respeta:
no hay contraseñas, ni sesiones, ni permisos.

Ahora bien, el paciente necesita saber cuáles son *sus* citas. Para eso se usa la **identificación**,
que es una capacidad ya construida en el ejercicio 1 (`registro/RF-10`, `registro/RF-11`): el
paciente indica su documento de identidad o su código de historia clínica y el sistema resuelve de
quién se trata.

**Esto es identificación, no autenticación:** el sistema no comprueba que quien escribe el documento
sea realmente esa persona. En un HIS real esta zona estaría detrás del portal del paciente, con sus
credenciales. Queda fuera del alcance de esta práctica y así se declara (§8).

---

## 3. Escenarios de usuario

### ESC-01 — Reserva de una primera cita
Ana necesita ver a un dermatólogo. Entra en la aplicación, se identifica con su DNI, elige la
especialidad *Dermatología* y el centro más cercano, y ve los huecos libres de los próximos días.
Elige el martes a las 10:20 y reserva. El sistema le devuelve su cita con un código, `CITA-2026-000001`.

### ESC-02 — Un imprevisto: reprogramar
A Ana le surge un viaje y no puede acudir el martes. Entra en "Mis citas", pulsa *Reprogramar* y
elige otro hueco del mismo especialista. La cita sigue siendo la misma —mismo código— pero ahora es
el jueves a las 11:00. El hueco del martes vuelve a quedar libre para otro paciente.

### ESC-03 — Cancelación
Juan ya no necesita la consulta y la cancela desde la aplicación. La cita queda cancelada y su hueco
se libera.

### ESC-04 — Cancelación fuera de plazo
Luis intenta cancelar una cita que es dentro de dos horas. El sistema no se lo permite y le indica
que debe avisar con al menos 24 horas de antelación, según la política del centro.

### ESC-05 — Vacaciones de un especialista
El administrativo bloquea la agenda de la doctora Ruiz del 1 al 15 de agosto por vacaciones. A
partir de ese momento, ningún paciente ve huecos suyos en esas fechas.

### ESC-06 — Baja de última hora con citas ya dadas
El doctor Alonso causa baja mañana y ya tiene pacientes citados. El administrativo intenta bloquear
el día y el sistema le avisa de que hay 4 citas reservadas en esa franja: debe reprogramarlas o
cancelarlas antes de bloquear, para que ningún paciente se presente a una consulta que no existe.

### ESC-07 — Consultas más largas
La doctora Ruiz pasa a dedicar 30 minutos a cada paciente en lugar de 20. El administrativo cambia
la duración de sus huecos y, desde ese momento, la disponibilidad se ofrece en tramos de 30 minutos.
Las citas ya reservadas no se alteran.

### ESC-08 — Dos pacientes, el mismo hueco
Dos pacientes intentan reservar el mismo hueco casi a la vez. El primero lo consigue; al segundo se
le informa de que ese hueco acaba de ocuparse y se le muestran los que siguen libres.

---

## 4. Requisitos funcionales

### 4.1 Capacidad A — Reservar una cita online

| ID | Requisito |
|----|-----------|
| RF-01 | El sistema debe permitir **buscar especialistas** filtrando por especialidad médica y por centro. |
| RF-02 | El sistema debe mostrar la **disponibilidad** de un especialista: los huecos libres dentro de un rango de fechas, pudiendo acotarlos a la **franja horaria** que le venga bien al paciente. |
| RF-03 | Los huecos se calculan a partir del **horario de consulta** del especialista y de la **duración** configurada para sus citas, descontando las franjas bloqueadas y las citas ya reservadas. |
| RF-04 | El paciente debe **identificarse** con su documento de identidad o su código de historia clínica, reutilizando el módulo de registro. |
| RF-05 | El sistema debe permitir **reservar** un hueco concreto, creando una cita asociada al `patient_id` del paciente. |
| RF-06 | Cada cita debe recibir un **identificador propio** y un **código de cita** legible. |
| RF-07 | El sistema debe **rechazar la reserva** de un hueco que ya esté ocupado, bloqueado, fuera del horario del especialista o en el pasado. |
| RF-08 | Tras reservar, el sistema debe devolver los **datos de la cita**: paciente, especialista, especialidad, centro, fecha, hora, duración y código. |

### 4.2 Capacidad B — Cancelar o reprogramar una cita

| ID | Requisito |
|----|-----------|
| RF-09 | El sistema debe permitir a un paciente identificado **consultar sus citas**, distinguiendo las futuras de las pasadas. |
| RF-10 | El sistema debe permitir **cancelar** una cita futura. |
| RF-11 | El sistema debe permitir **reprogramar** una cita: cambiarla a otro hueco disponible del mismo especialista. |
| RF-12 | Al reprogramar, la cita debe **conservar su identificador y su código**: es la misma cita, no una nueva (ESC-02). |
| RF-13 | Al cancelar o reprogramar, el **hueco anterior debe quedar disponible** de nuevo. |
| RF-14 | El sistema debe **rechazar** la cancelación o reprogramación de una cita ya cancelada, ya pasada o fuera del plazo de antelación. |
| RF-15 | El sistema debe permitir al paciente consultar el **detalle de una cita** por su código. |

### 4.3 Capacidad C — Gestionar la agenda de un especialista

| ID | Requisito |
|----|-----------|
| RF-16 | El sistema debe permitir al personal administrativo **consultar la agenda** de un especialista: su horario, sus bloqueos y sus citas. |
| RF-17 | El sistema debe permitir **bloquear una franja** de la agenda indicando inicio, fin y motivo (vacaciones, formación, baja u otro). |
| RF-18 | El sistema debe **impedir bloquear una franja que contenga citas reservadas**, informando de cuántas y cuáles son, para que se gestionen antes (ESC-06). |
| RF-19 | El sistema debe permitir **levantar un bloqueo**. |
| RF-20 | El sistema debe permitir **ajustar la duración de los huecos** de un especialista. |
| RF-21 | Los cambios de agenda deben **reflejarse de inmediato** en la disponibilidad que ve el paciente. |
| RF-22 | Cambiar la duración de los huecos **no debe alterar las citas ya reservadas**. |

### 4.4 Requisitos de la aplicación

| ID | Requisito |
|----|-----------|
| RF-23 | Las tres capacidades deben estar disponibles como **API REST**. |
| RF-24 | Las tres capacidades deben estar disponibles en la **interfaz web**, con una zona para el paciente y otra para el personal administrativo. |
| RF-25 | Los errores deben usar el **mismo formato uniforme** que el módulo de registro (`registro/RF-23`). |
| RF-26 | Las citas deben asociarse al **`patient_id`** del módulo de registro, sin duplicar los datos personales del paciente. |

---

## 5. Reglas de negocio

| ID | Regla |
|----|-------|
| RN-01 | **Identidad de la cita.** Cada cita tiene un identificador interno (UUID v4) y un código legible `CITA-AAAA-NNNNNN`, con el año y un secuencial que se reinicia cada año. Ambos son inmutables, también al reprogramar. |
| RN-02 | **Duración de los huecos.** Es una propiedad del especialista, entre 5 y 120 minutos y múltiplo de 5. Por defecto, 20 minutos. |
| RN-03 | **Generación de huecos.** Los huecos de un día se generan desde el inicio de cada tramo del horario del especialista, encadenados según su duración, y solo se ofrecen los que caben enteros dentro del tramo. |
| RN-04 | **Sin solapamiento por especialista.** Un especialista no puede tener dos citas activas que se solapen. |
| RN-05 | **Sin solapamiento por paciente.** Un paciente no puede tener dos citas activas que se solapen, aunque sean de especialistas distintos. |
| RN-06 | **Antelación mínima para reservar.** No se puede reservar una cita en el pasado ni con menos de 1 hora de antelación. Las horas se manejan en la **hora local del centro**, que es la que el paciente y el profesional ven en el reloj. |
| RN-07 | **Antelación mínima para cancelar o reprogramar.** 24 horas antes del comienzo de la cita. Es política del centro y está centralizada en la configuración. |
| RN-08 | **Horizonte de reserva.** No se pueden reservar citas a más de 6 meses vista. |
| RN-09 | **Estados de la cita.** `RESERVADA` y `CANCELADA`. Una cita cancelada no vuelve a estar activa: si el paciente la quiere recuperar, reserva una nueva. Una cita cuya hora ya pasó sigue estando `RESERVADA`, pero se considera pasada y no admite cambios. |
| RN-10 | **Reprogramar.** Cambia la fecha y la hora de la cita dentro de la agenda del **mismo especialista**, conservando identificador y código (RF-12). El nuevo hueco debe cumplir las mismas reglas que una reserva nueva. |
| RN-11 | **Bloqueos.** Tienen inicio, fin y motivo obligatorio. El fin debe ser posterior al inicio y no pueden crearse enteramente en el pasado. |
| RN-12 | **Bloqueo con citas dentro.** No se puede crear un bloqueo que solape con citas reservadas; el sistema informa de cuáles son. |
| RN-13 | **Disponibilidad real.** Un hueco se ofrece solo si está dentro del horario del especialista, no solapa ningún bloqueo, no solapa ninguna cita activa y cumple la antelación mínima. |
| RN-14 | **Cambio de duración.** Afecta a la disponibilidad futura, nunca a las citas ya reservadas (RF-22). |
| RN-15 | **Paciente existente.** Solo se pueden reservar citas para un paciente registrado en el módulo de registro. |
| RN-16 | **Catálogo fijo.** Centros, especialidades y especialistas son datos de referencia del sistema; su gestión corresponde al administrador y queda fuera de alcance (§8). |
| RN-17 | **Motivo de consulta.** Opcional al reservar, con un máximo de 300 caracteres. Es un dato de la cita, no de la historia clínica. |

---

## 6. Criterios de aceptación

Formato *Dado / Cuando / Entonces*. Cada criterio se verifica con una prueba automática.

### Capacidad A — Reservar una cita online

**CA-01 — Búsqueda de especialistas por especialidad y centro** *(RF-01)*
- **Dado** un catálogo con especialistas de varias especialidades y centros
- **Cuando** se buscan los de *Dermatología* en el centro *Clínica Norte*
- **Entonces** se devuelven solo los especialistas que cumplen ambos criterios.

**CA-02 — Consulta de disponibilidad** *(RF-02, RF-03, RN-03)*
- **Dado** un especialista que pasa consulta de 09:00 a 11:00 con huecos de 20 minutos
- **Cuando** se consulta su disponibilidad para ese día
- **Entonces** se devuelven los huecos 09:00, 09:20, 09:40, 10:00, 10:20 y 10:40.

**CA-03 — La disponibilidad descuenta las citas ya reservadas** *(RF-03, RN-13)*
- **Dado** el especialista anterior con una cita reservada a las 09:20
- **Cuando** se consulta su disponibilidad
- **Entonces** el hueco de las 09:20 no aparece y los demás sí.

**CA-04 — La disponibilidad descuenta las franjas bloqueadas** *(RF-03, RN-13, ESC-05)*
- **Dado** un bloqueo de 10:00 a 11:00 en la agenda del especialista
- **Cuando** se consulta su disponibilidad de ese día
- **Entonces** solo se ofrecen los huecos anteriores a las 10:00.

**CA-05 — Reserva correcta** *(RF-04 a RF-08, RN-01)*
- **Dado** un paciente registrado y un hueco libre
- **Cuando** el paciente reserva ese hueco
- **Entonces** se crea una cita en estado `RESERVADA`, con identificador propio y código `CITA-AAAA-NNNNNN`, asociada a su `patient_id`, y el hueco deja de estar disponible.

**CA-06 — El código de cita es secuencial y único** *(RN-01)*
- **Cuando** se reservan dos citas
- **Entonces** reciben `CITA-AAAA-000001` y `CITA-AAAA-000002`.

**CA-07 — No se puede reservar un hueco ocupado** *(RF-07, RN-04, ESC-08)*
- **Dado** un hueco ya reservado por otro paciente
- **Cuando** se intenta reservar ese mismo hueco
- **Entonces** se rechaza con el código `HUECO_NO_DISPONIBLE` y no se crea ninguna cita.

**CA-08 — No se puede reservar sobre una franja bloqueada** *(RF-07, RN-13)*
- **Cuando** se intenta reservar un hueco que cae dentro de un bloqueo
- **Entonces** se rechaza con `HUECO_NO_DISPONIBLE`.

**CA-09 — No se puede reservar fuera del horario del especialista** *(RF-07, RN-13)*
- **Cuando** se intenta reservar a una hora en la que el especialista no pasa consulta
- **Entonces** se rechaza con `HUECO_NO_DISPONIBLE`.

**CA-10 — No se puede reservar en el pasado ni sin antelación** *(RF-07, RN-06)*
- **Cuando** se intenta reservar una cita cuya hora ya pasó, o que empieza dentro de menos de 1 hora
- **Entonces** se rechaza con un error de validación.

**CA-11 — Un paciente no puede tener dos citas solapadas** *(RN-05)*
- **Dado** un paciente con una cita el martes a las 10:00
- **Cuando** intenta reservar otra cita que se solapa con esa, con otro especialista
- **Entonces** se rechaza con el código `PACIENTE_YA_CITADO`.

**CA-12 — Solo se reservan citas para pacientes registrados** *(RF-04, RN-15)*
- **Cuando** se intenta reservar indicando un documento que no corresponde a ningún paciente
- **Entonces** se responde con `PACIENTE_NO_ENCONTRADO`.

**CA-32 — La búsqueda se acota a la disponibilidad horaria del paciente** *(RF-02, enunciado §3.1)*
- **Dado** un especialista que pasa consulta de 09:00 a 11:00
- **Cuando** el paciente busca indicando que solo puede por la tarde
- **Entonces** no se le ofrece ningún hueco de ese especialista, y al pedir la franja de mañana se le ofrecen los seis.

### Capacidad B — Cancelar o reprogramar

**CA-13 — Consulta de las citas del paciente** *(RF-09)*
- **Dado** un paciente con una cita futura y otra pasada
- **Cuando** consulta sus citas identificándose
- **Entonces** se devuelven ambas, indicando cuál es futura y cuál pasada.

**CA-14 — Cancelación** *(RF-10, RF-13, ESC-03)*
- **Dado** un paciente con una cita futura
- **Cuando** la cancela
- **Entonces** la cita queda en estado `CANCELADA` y su hueco vuelve a ofrecerse como disponible.

**CA-15 — Reprogramación** *(RF-11, RF-12, RF-13, RN-10, ESC-02)*
- **Dado** un paciente con una cita el martes a las 10:20
- **Cuando** la reprograma al jueves a las 11:00
- **Entonces** la cita conserva su identificador y su código, pasa a ser el jueves a las 11:00, el hueco del martes vuelve a estar libre y el del jueves deja de estarlo.

**CA-16 — No se puede reprogramar a un hueco ocupado** *(RF-11, RN-04)*
- **Cuando** se reprograma una cita a un hueco que ya está reservado
- **Entonces** se rechaza con `HUECO_NO_DISPONIBLE` y la cita mantiene su fecha original.

**CA-17 — No se puede cancelar fuera de plazo** *(RF-14, RN-07, ESC-04)*
- **Dado** una cita que empieza dentro de 2 horas
- **Cuando** el paciente intenta cancelarla
- **Entonces** se rechaza indicando la antelación mínima exigida.

**CA-18 — No se puede cancelar dos veces** *(RF-14, RN-09)*
- **Dado** una cita ya cancelada
- **Cuando** se intenta cancelar de nuevo
- **Entonces** se rechaza con `CITA_NO_MODIFICABLE`.

**CA-19 — No se puede modificar una cita pasada** *(RF-14, RN-09)*
- **Dado** una cita cuya hora ya pasó
- **Cuando** se intenta cancelar o reprogramar
- **Entonces** se rechaza con `CITA_NO_MODIFICABLE`.

**CA-20 — Consulta de una cita por su código** *(RF-15)*
- **Dado** una cita con código `CITA-AAAA-000001`
- **Cuando** se consulta por ese código
- **Entonces** se devuelven sus datos, incluidos el paciente, el especialista y el centro.

### Capacidad C — Gestionar la agenda

**CA-21 — Consulta de la agenda de un especialista** *(RF-16)*
- **Cuando** el administrativo consulta la agenda de un especialista para un rango de fechas
- **Entonces** se devuelven su horario, sus bloqueos y sus citas reservadas.

**CA-22 — Bloqueo de una franja** *(RF-17, RF-21, RN-11, ESC-05)*
- **Cuando** el administrativo bloquea del 1 al 15 de agosto por vacaciones
- **Entonces** el bloqueo queda registrado y esas fechas dejan de ofrecerse al paciente.

**CA-23 — No se puede bloquear sobre citas reservadas** *(RF-18, RN-12, ESC-06)*
- **Dado** un especialista con citas reservadas el jueves
- **Cuando** se intenta bloquear el jueves completo
- **Entonces** se rechaza con `FRANJA_CON_CITAS`, se informa de los códigos de las citas afectadas y no se crea el bloqueo.

**CA-24 — Levantar un bloqueo** *(RF-19, RF-21)*
- **Dado** una franja bloqueada
- **Cuando** se levanta el bloqueo
- **Entonces** esos huecos vuelven a ofrecerse.

**CA-25 — Ajuste de la duración de los huecos** *(RF-20, RF-21, RN-02, ESC-07)*
- **Dado** un especialista con huecos de 20 minutos y consulta de 09:00 a 10:00
- **Cuando** se cambia su duración a 30 minutos
- **Entonces** su disponibilidad pasa a ofrecer 09:00 y 09:30.

**CA-26 — La duración debe ser válida** *(RN-02)*
- **Cuando** se intenta fijar una duración de 7 minutos o de 300 minutos
- **Entonces** se rechaza con un error de validación.

**CA-27 — Cambiar la duración no altera las citas reservadas** *(RF-22, RN-14, ESC-07)*
- **Dado** una cita reservada de 20 minutos
- **Cuando** se cambia la duración de los huecos del especialista a 30
- **Entonces** la cita reservada sigue siendo de 20 minutos y a su misma hora.

### Requisitos de la aplicación

**CA-28 — Las citas reutilizan la identidad del paciente** *(RF-26, OBJ-05)*
- **Cuando** se consulta una cita
- **Entonces** incluye el `patient_id` y el código de historia clínica del paciente, obtenidos del módulo de registro, y los datos personales no están duplicados en la cita.

**CA-29 — Formato uniforme de error** *(RF-25)*
- **Cuando** se produce cualquier error de este módulo
- **Entonces** la respuesta tiene la misma forma que en el módulo de registro: `codigo`, `mensaje` y, si procede, `detalles`.

**CA-30 — Interfaz web** *(RF-24)*
- **Cuando** se usa la aplicación web
- **Entonces** un paciente puede identificarse, buscar disponibilidad, reservar, cancelar y reprogramar, y el personal administrativo puede bloquear franjas y cambiar la duración de los huecos.

**CA-31 — API REST** *(RF-23)*
- **Cuando** se consulta la documentación de la API
- **Entonces** incluye las operaciones de búsqueda de especialistas, disponibilidad, reserva, cancelación, reprogramación y gestión de agenda.

---

## 7. Casos límite

| ID | Caso | Comportamiento esperado |
|----|------|-------------------------|
| CL-01 | Dos reservas simultáneas del mismo hueco | Una restricción de unicidad en la base de datos impide la segunda, que se rechaza con `HUECO_NO_DISPONIBLE` (ESC-08). |
| CL-02 | Hueco que no cabe entero en el tramo horario | No se ofrece: con consulta de 09:00 a 10:00 y huecos de 45 minutos, solo se ofrece el de 09:00 (RN-03). |
| CL-03 | Bloqueo que solapa parcialmente un hueco | El hueco no se ofrece: basta con que el bloqueo toque cualquier parte del hueco. |
| CL-04 | Bloqueo que empieza en el pasado y termina en el futuro | Se acepta: lo que se rechaza es el bloqueo enteramente pasado (RN-11). |
| CL-05 | Bloqueo con fin anterior al inicio | Se rechaza. |
| CL-06 | Día sin horario de consulta (fin de semana) | La disponibilidad de ese día es una lista vacía, no un error. |
| CL-07 | Rango de fechas invertido al consultar disponibilidad | Se rechaza con un error de validación. |
| CL-08 | Rango de fechas excesivo (más de 60 días) | Se rechaza, para no generar una respuesta desmedida. |
| CL-09 | Reserva justo en el límite de la antelación mínima | Se acepta si falta exactamente 1 hora o más (RN-06). |
| CL-10 | Cancelación justo en el límite de las 24 horas | Se acepta si faltan exactamente 24 horas o más (RN-07). |
| CL-11 | Cita a más de 6 meses vista | Se rechaza (RN-08). |
| CL-12 | Reprogramar al mismo hueco que ya ocupa la cita | Se acepta y no cambia nada: la cita ya está ahí. |
| CL-13 | Cancelar la cita de otro paciente | Se rechaza: la cita debe pertenecer al paciente que se ha identificado. |
| CL-14 | Paciente sin ninguna cita | "Mis citas" devuelve una lista vacía, no un error. |
| CL-15 | Especialista sin horario configurado | No ofrece ningún hueco; la búsqueda lo indica en lugar de fallar. |
| CL-16 | Duración que no es múltiplo de 5 | Se rechaza (RN-02, CA-26). |
| CL-17 | Identificador de cita con formato que no es UUID | Se rechaza como error de validación. |
| CL-18 | Código de cita con formato incorrecto | Se rechaza como error de validación. |
| CL-19 | Cambio de año | El secuencial del código de cita vuelve a empezar en `000001` (RN-01). |
| CL-20 | Bloqueo que solapa con una cita ya cancelada | Se permite: las citas canceladas no ocupan agenda. |

---

## 8. Fuera de alcance

Conforme al apartado 5 del enunciado:

1. **El resto de módulos del HIS:** historia clínica, prescripción, facturación y notificaciones. En
   particular, **no se envían avisos** al paciente ni al personal (ni email, ni SMS, ni push), aunque
   el HIS los contemple como módulo transversal.
2. **La gestión de especialidades, centros y permisos**, responsabilidad del administrador del
   sistema. Este módulo los usa como catálogo de datos ya existente (RN-16).
3. **Cualquier integración real con aseguradoras o mutuas.**
4. **Inicio de sesión y control de acceso por rol.** El paciente se identifica con un dato que
   conoce, sin contraseña, y el sistema no comprueba su identidad real (§2.1). Tampoco se separan
   técnicamente los permisos del paciente y del personal administrativo: son dos zonas distintas de
   la misma aplicación.

Tampoco forman parte de las tres capacidades pedidas, y quedan fuera:

5. **Alta y edición de especialistas, y definición de su horario semanal desde la aplicación.** El
   horario forma parte del catálogo; lo que sí se gestiona son los bloqueos y la duración de los
   huecos, que es lo que pide el 3.3.
6. **Listas de espera y adelanto de citas** cuando se libera un hueco.
7. **Consultas sin cita previa (urgencias) y citas de grupo.**
8. **Gestión de la sala, el box o los recursos** en los que se pasa la consulta.
9. **Confirmación de asistencia, registro de la consulta o marcado de ausencias**, que corresponden
   al módulo de historia clínica.
10. **Histórico y auditoría de los cambios de agenda**, que es un requisito transversal del HIS.

---

## 9. Trazabilidad

| Capacidad del enunciado | Requisitos | Criterios de aceptación |
|-------------------------|-----------|-------------------------|
| 3.1 Reservar una cita online | RF-01 a RF-08 | CA-01 a CA-12 y CA-32 |
| 3.2 Cancelar o reprogramar | RF-09 a RF-15 | CA-13 a CA-20 |
| 3.3 Gestionar la agenda | RF-16 a RF-22 | CA-21 a CA-27 |
| Aplicación e integración | RF-23 a RF-26 | CA-28 a CA-31 |

---

## 10. Glosario

| Término | Definición |
|---------|------------|
| **Cita** | Reserva de un tramo de la agenda de un especialista para atender a un paciente. |
| **Hueco** | Tramo libre de la agenda de un especialista en el que se puede reservar una cita. |
| **Horario de consulta** | Tramos semanales en los que un especialista pasa consulta en un centro. |
| **Bloqueo** | Periodo en el que un especialista no pasa consulta: vacaciones, formación, baja u otro motivo. |
| **Duración de hueco** | Minutos que ocupa cada cita de un especialista. |
| **Reprogramar** | Cambiar una cita a otro hueco conservando su identidad. |
| **`patient_id`** | Identificador del paciente creado por el módulo de registro (ejercicio 1) y reutilizado aquí. |
