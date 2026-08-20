# Feature Specification: Core AI QA & Software Engineering Agent

**Feature Branch**: `001-core-ai-qa-agent`

**Created**: 2026-08-11

**Version**: 1.4

**Status**: Draft

**Input**: User description: "Desarrollar el agente de inteligencia artificial especializado en asistir a desarrolladores y profesionales de QA en tareas de análisis, exploración y validación de proyectos de software, orientado a herramientas, controlado y verificable."

## Change Log

- **1.1 (2026-08-11)** — Ampliación QA/Testing (constitución XII). Se incorporan al
  alcance tres capacidades adicionales sus herramientas y Skills asociadas, con su
  User Story, requisitos funcionales (FR-026..FR-031) y criterios de éxito
  (SC-012..SC-014):
  - **US-8** — Analizar resultados de pruebas (`analyze_test_results`).
  - **US-9** — Generar casos de prueba sugeridos (`generate_test_cases`).
  - **US-10** — Analizar la cobertura de código (`analyze_coverage`).
  Trazabilidad ampliada: UC-008 y UC-009 añadidos en `docs/use-cases/`; tareas
  QA/Testing (T057-T069) re-etiquetadas con su US correcta en `tasks.md`.
- **1.2 (2026-08-13)** — Ampliación Acciones Destructivas (Phase 14). Se incorpora
  al alcance la capacidad de **modificar el proyecto** (crear, editar y eliminar
  archivos) de forma segura, con su User Story, requisitos funcionales
  (FR-042..FR-047) y criterios de éxito (SC-021..SC-024):
  - **US-13** — El agente realiza acciones destructivas seguras (crear, editar,
    eliminar) con autorización, backup y verificación.
  Herramientas de escritura propuestas: `crear_archivo`, `editar_archivo`,
  `eliminar_archivo`. Trazabilidad ampliada: `UC-012` añadido en
  `docs/use-cases/`; tareas Phase 14 (T095-T103) en `tasks.md`. Alcance solo
  documentado (spec-first); la implementación se realiza en Phase 14.
- **1.3 (2026-08-14)** — Ampliación Profundidad de Análisis (lectura de código).
  Se incorpora al alcance la capacidad del agente de **leer el contenido real
  de archivos** y de generar respuestas **profundas** al explicar/entender el
  código, con su User Story, requisitos funcionales (FR-048..FR-050) y
  criterios de éxito (SC-025..SC-026):
  - **US-14** — El agente explica con profundidad qué hace cada capa/módulo y
    qué pruebas lo cubren, leyendo los archivos reales (`leer_archivo`).
  Nueva herramienta `leer_archivo`; `search` se acota con `max_ocurrencias`
  para evitar volcados gigantes; el historial visible del CLI pasa a ser
  opcional (`--mostrar-historial`). Trazabilidad ampliada: `UC-013` añadido en
  `docs/use-cases/`; tareas Phase 15 (T104-T110) en `tasks.md`. Implementado en
  Phase 15.
- **1.4 (2026-08-20)** — Reconciliación SDD. Se formaliza como comportamiento
  aprobado el bucle de razonamiento-acción de **US-11** (FR-032..FR-036 y
  SC-015..SC-017). Se explicita que el MVP opera únicamente sobre repositorios
  de confianza y no ofrece aislamiento de procesos ni de red. La conversación
  persistente, memoria, tareas y `.qa_sessions` (US-12, FR-037..FR-041 y
  SC-018..SC-020) quedan diferidas y no forman parte del alcance aprobado.

## Clarifications

### Session 2026-08-11

- Q: ¿Cómo debe ser visible para el usuario el registro de las acciones que el agente realiza (qué herramientas usó y qué resultados obtuvo)? → A: El agente muestra en la conversación un historial visible de cada herramienta ejecutada y su resultado.
- Q: ¿Cómo debe manejar el agente los secretos (API keys, tokens, credenciales) que puedan aparecer en sus respuestas o en el registro de acciones? → A: El agente filtra u oculta cualquier secreto detectado antes de mostrarlo en la conversación, el historial visible o los logs.
- Q: ¿Qué debe hacer el agente cuando ninguna de sus herramientas es adecuada para atender la solicitud del usuario? → A: El agente informa que no puede atender la solicitud con las herramientas disponibles y sugiere ajustes.

## User Scenarios & Testing *(mandatory)*

> **Nota de formato (EARS).** Cada historia de usuario se expresa mediante
> declaraciones de requisito en formato EARS (Easy Approach to Requirements
> Syntax), cuyo operador se indica entre corchetes:
>
> - `[Ubiquitous] ... SHALL ...`: el agente siempre cumple la acción.
> - `[Estado] While <estado>, ... SHALL ...`: la acción se cumple mientras
>   persiste un estado.
> - `[Evento] When <disparador>, ... SHALL ...`: la acción se cumple ante un
>   evento que activa un estímulo.
> - `[Comportamiento no deseado] If <condición>, then ... SHALL ...`: la acción
>   se cumple ante una posible condición de fallo.
> - `[Opcional] Where <característica>, ... SHALL ...`: la acción se cumple solo
>   cuando la característica está presente.

---

### User Story 1 - El agente recibe una solicitud y responde usando herramientas (Priority: P1)

**Descripción.** Como desarrollador o profesional de QA, quiero enviar una
solicitud en lenguaje natural sobre mi proyecto (por ejemplo, "¿por qué está
fallando este test?") y que el agente seleccione la o las herramientas
adecuadas, ejecute las operaciones necesarias, analice los resultados reales y
me entregue una respuesta comprensiva.

**Requisito EARS (Ubiquitous).**
- `[Ubiquitous]` El agente SHALL recibir una solicitud del usuario en lenguaje
  natural y SHALL producir una respuesta relacionada con dicha solicitud.

**Requisito EARS (Evento).**
- `[Evento] When` el usuario envía una solicitud que requiere información del
  proyecto, `then` el agente SHALL identificar y ejecutar la herramienta
  pertinente para obtener dicha información antes de responder.

**Why this priority**: Sin este flujo el proyecto no entrega valor: es la
capacidad fundamental del agente asistente descrita en el README.

**Independent Test**: Se valida suministrando una solicitud de ejemplo y
verificando que la respuesta del agente se basa en una herramienta real
ejecutada y no en información fabricada.

**Acceptance Scenarios**:

1. **Given** una solicitud válida del usuario, **When** el agente la procesa,
   **Then** entrega una respuesta que directamente aborda la solicitud.
2. **Given** una solicitud que requiere datos del proyecto, **When** el agente
   la procesa, **Then** ejecuta al menos una herramienta real y base su respuesta
   en el resultado obtenido.

---

### User Story 2 - El agente explora la estructura del proyecto (Priority: P1)

**Descripción.** Como profesional de QA, quiero que el agente pueda explorar la
estructura de un proyecto de software (archivos, directorios, componentes) para
que yo comprenda su organización sin recorrerlo manualmente.

**Requisito EARS (Evento).**
- `[Evento] When` el usuario solicita comprender la estructura del proyecto,
  `then` el agente SHALL explorar el proyecto y SHALL presentar la información
  estructural obtenida.

**Requisito EARS (Estado).**
- `[Estado] While` el agente explora el proyecto, `then` la herramienta de
  exploración SHALL reportar únicamente información real de la estructura
  existente.

**Why this priority**: Explorar es la base para localizar archivos y ejecutar
las demás tareas de análisis y validación.

**Independent Test**: Se valida que, ante una petición de estructura, la
respuesta refleja los archivos y directorios reales del proyecto.

**Acceptance Scenarios**:

1. **Given** un proyecto con archivos y directorios, **When** el usuario pide
   explorar su estructura, **Then** la respuesta incluye los elementos
   estructurales reales localizados.
2. **Given** una ruta inexistente o no autorizada, **When** el agente intenta
   explorarla, **Then** informa que no puede acceder en lugar de inventar
   contenido.

---

### User Story 3 - El agente localiza archivos y componentes (Priority: P2)

**Descripción.** Como profesional de QA, quiero que el agente localice archivos,
clases, funciones o componentes específicos para encontrar rápidamente el código
relevante.

**Requisito EARS (Evento).**
- `[Evento] When` el usuario solicita localizar un archivo, clase, función o
  componente, `then` el agente SHALL buscar en el proyecto y SHALL devolver las
  coincidencias reales encontradas.

**Requisito EARS (Comportamiento no deseado).**
- `[Comportamiento no deseado] If` no se encuentran coincidencias, `then` el
  agente SHALL informar la ausencia de resultados y NO SHALL fabricar
  concordancias ficticias.

**Why this priority**: La localización rapida es central para el análisis de
errores y la revisión de código.

**Independent Test**: Se valida aportando búsquedas con coincidencias reales y
verificando que se reportan solo los resultados verdaderamente hallados.

**Acceptance Scenarios**:

1. **Given** una búsqueda con coincidencias existentes, **When** el agente la
   ejecuta, **Then** reporta las coincidencias reales.
2. **Given** una búsqueda sin coincidencias, **When** el agente la ejecuta,
   **Then** informa la ausencia de resultados sin inventar coincidencias.

---

### User Story 4 - El agente revisa y busca patrones en el código (Priority: P2)

**Descripción.** Como profesional de QA, quiero que el agente revise partes del
código y busque patrones específicos para comprender el funcionamiento y detectar
relevancia en el análisis.

**Requisito EARS (Evento).**
- `[Evento] When` el usuario solicita revisar o buscar un patrón en el código,
  `then` el agente SHALL ejecutar la búsqueda correspondiente y SHALL presentar
  los resultados reales en contexto.

**Requisito EARS (Estado).**
- `[Estado] While` se presenta contenido de código, `then` el agente SHALL
  citar el código real del proyecto sin alterarlo.

**Why this priority**: Revisar y buscar patrones habilita el análisis de
errores y la generación de casos de prueba.

**Independent Test**: Se valida comparando el fragmento presentado con el código
real del proyecto.

**Acceptance Scenarios**:

1. **Given** un patrón presente en el código, **When** el agente lo busca,
   **Then** muestra las ocurrencias reales con su contexto.
2. **Given** una revisión de código solicitada, **When** el agente la presenta,
   **Then** el contenido citado coincide con el proyecto real.

---

### User Story 5 - El agente ejecuta y analiza pruebas automatizadas (Priority: P2)

**Descripción.** Como profesional de QA, quiero que el agente ejecute pruebas
automatizadas del proyecto y revise sus resultados para investigar fallos y sus
posibles causas.

**Requisito EARS (Evento).**
- `[Evento] When` el usuario solicita ejecutar o analizar pruebas automatizadas,
  `then` el agente SHALL ejecutar la operación sobre el conjunto de pruebas
  autorizado y SHALL reportar los resultados reales obtenidos.

**Requisito EARS (Comportamiento no deseado).**
- `[Comportamiento no deseado] If` una prueba falla o no puede ejecutarse, `then`
  el agente SHALL reportar el fallo de forma explícita y NO SHALL atribuir una
  causa no respaldada por la evidencia.

**Why this priority**: Ejecutar y analizar pruebas es una tarea central de
validación de QA descrita en el README.

**Independent Test**: Se valida contra un proyecto con pruebas conocidas
(pasando y fallando) verificando que el agente reporta el estado real.

**Acceptance Scenarios**:

1. **Given** un conjunto de pruebas autorizado, **When** el usuario pide
   ejecutarlas, **Then** el agente reporta el resultado real de la ejecución.
2. **Given** una prueba fallida, **When** el agente la analiza, **Then** presenta
   el error real y delimita la causa a lo que la evidencia sustenta.

---

### User Story 6 - El agente gestiona operaciones con autorización (human-in-the-loop) (Priority: P3)

**Descripción.** Como profesional de QA, quiero que las acciones que puedan
modificar, eliminar o afectar información del proyecto requieran mi autorización
explícita, para mantener el control sobre los cambios.

**Requisito EARS (Evento).**
- `[Evento] When` el agente determina que una acción puede modificar, eliminar o
  afectar información del proyecto, `then` el agente SHALL solicitar autorización
  explícita antes de ejecutarla.

**Requisito EARS (Estado).**
- `[Estado] While` una acción sensata pendiente de autorización, `then` el agente
  SHALL suspender su ejecución y SHALL informar al usuario.

**Requisito EARS (Comportamiento no deseado).**
- `[Comportamiento no deseado] If` el usuario deniega la autorización, `then` el
  agente SHALL abstenerse de ejecutar la acción y SHALL notificar el resultado.

**Why this priority**: Protege la integridad del proyecto y la autonomía del
agente queda subordinada a las políticas de seguridad.

**Independent Test**: Se valida solicitando una acción destructiva y verificando
que el agente se detiene hasta recibir confirmación.

**Acceptance Scenarios**:

1. **Given** una acción con potencial de modificar información, **When** el
   agente la encuentra, **Then** solicita autorización antes de ejecutarla.
2. **Given** una denegación de autorización, **When** el usuario la emite,
   **Then** la acción no se ejecuta y el usuario es notificado.

---

### User Story 7 - El agente informa límites y evita inventar información (Priority: P3)

**Descripción.** Como usuario, quiero que el agente reconozca cuándo no tiene
suficiente información y nunca invente resultados, para confiar en sus
respuestas.

**Requisito EARS (Evento).**
- `[Evento] When` el agente carece de información suficiente o no puede
  obtenerla, `then` el agente SHALL informar su falta de confianza o de datos y
  NO SHALL inventar resultados.

**Requisito EARS (Comportamiento no deseado).**
- `[Comportamiento no deseado] If` una herramienta devuelve un error o un
  resultado inválido, `then` el agente SHALL manejarlo explícitamente y NO SHALL
  presentar el resultado como válido.

**Why this priority**: La honestidad sobre lo desconocido es un requisito de
confianza innegociable de la constitución.

**Independent Test**: Se valida ante preguntas sin respuesta disponible y
errores de herramienta, verificando que el agente no fabrica datos.

**Acceptance Scenarios**:

1. **Given** una solicitud sin información disponible, **When** el agente la
   procesa, **Then** comunica que no puede responder con confianza.
2. **Given** un resultado de herramienta inválido o un error, **When** el agente
   lo recibe, **Then** lo maneja explícitamente y no lo presenta como válido.

---

## Ampliación QA/Testing

> **Nota de alcance (constitución XII).** Las capacidades de esta ampliación se
> incorporan por una necesidad funcional concreta del dominio QA/Testing y se
> documentan aquí antes de implementarse (constitución XIV). Las herramientas
> asociadas se añaden como componentes modulares (principio II) sin alterar el
> contrato ni la estabilidad de las herramientas existentes (`explore`, `locate`,
> `search`, `run_tests`).

### User Story 8 - El agente analiza los resultados de pruebas (Priority: P2)

**Descripción.** Como profesional de QA, quiero que el agente analice los
resultados de una ejecución de pruebas y agrupe fallos/errores, para
comprender rápidamente qué pruebas fallan y qué evidencia respalda una posible
causa común.

**Requisito EARS (Evento).**
- `[Evento] When` el usuario solicita analizar resultados de pruebas, `then` el
  agente SHALL ejecutar la herramienta `analyze_test_results` y SHALL reportar
  un resumen real con causas delimitadas a la evidencia.

**Requisito EARS (Estado).**
- `[Estado] While` se presenta un análisis de fallos, `then` el agente SHALL
  citar solo datos reales de la ejecución y SHALL marcar como "sin evidencia
  suficiente" cualquier causa no respaldada.

**Why this priority**: Acelera la investigación de fallos en suites de pruebas.

**Independent Test**: Se valida con un resultado de ejecución conocido,
verificando que el resumen es determinista y que las causas se limitan a la
evidencia.

**Acceptance Scenarios**:

1. **Given** un resultado real de pruebas, **When** el agente lo analiza,
   **Then** presenta un resumen determinista y agrupa fallos por evidencia
   real (FR-013/014).
2. **Given** fallos sin causa clara, **When** el agente los describe,
   **Then** marca "sin evidencia suficiente" sin atribuir causa (UC-007).

---

### User Story 9 - El agente genera casos de prueba sugeridos (Priority: P2)

**Descripción.** Como profesional de QA, quiero que el agente genere casos de
prueba sugeridos (happy path, edge cases, negativos) para una función o
componente, basados en el código real del proyecto, para identificar escenarios
de prueba que podrían estar faltando.

**Requisito EARS (Evento).**
- `[Evento] When` el usuario solicita generar casos de prueba, `then` el agente
  SHALL identificar el código real relevante y SHALL proponer casos citando esas
  fuentes.

**Requisito EARS (Comportamiento no deseado).**
- `[Comportamiento no deseado] If` no existe código relevante, `then` el agente
  SHALL comunicar la falta de evidencia y NO SHALL inventar casos ni fuentes.

**Why this priority**: La generación de casos de prueba es una oportunidad clave
descrita en el README.

**Independent Test**: Se valida con una función real, verificando que los casos
propuestos citan código real y que, sin código, se comunica la falta de
evidencia.

**Acceptance Scenarios**:

1. **Given** una función/componente real, **When** el agente genera casos,
   **Then** propone casos sugeridos que citan fuentes reales del proyecto
   (FR-019, IX).
2. **Given** un objetivo sin código relevante, **When** el agente genera casos,
   **Then** comunica la falta de evidencia sin inventar (UC-007).

---

### User Story 10 - El agente analiza la cobertura de código (Priority: P3)

**Descripción.** Como profesional de QA, quiero que el agente analice la
cobertura de código de las pruebas para identificar archivos/líneas sin cubrir
y poder priorizar más pruebas.

**Requisito EARS (Evento).**
- `[Evento] When` el usuario solicita analizar cobertura, `then` el agente SHALL
  ejecutar `analyze_coverage` sobre un comando autorizado y SHALL reportar la
  cobertura real global y por archivo.

**Requisito EARS (Comportamiento no deseado).**
- `[Comportamiento no deseado] If` la ejecución de cobertura falla o no está
  disponible, `then` el agente SHALL reportar el estado de forma explícita y NO
  SHALL presentar cobertura inventada.

**Why this priority**: La cobertura apoya la validación y priorización de QA.

**Independent Test**: Se valida contra un proyecto con cobertura conocida,
verificando que se reporta cobertura real y que un fallo se comunica
explícitamente.

**Acceptance Scenarios**:

1. **Given** un proyecto con cobertura medible, **When** el agente la analiza,
   **Then** reporta cobertura real global y por archivo (FR-019, SC-011).
2. **Given** un fallo o ausencia de la herramienta de cobertura, **When** el
   agente intenta analizarla, **Then** informa el estado explícitamente sin
   inventar cobertura (FR-017/018, UC-007).

---

### User Story 11 - El agente razona y actúa en varios pasos (Priority: P2)

**Descripción.** Como profesional de QA, quiero que el agente planifique y
ejecute análisis de varios pasos, mostrando el motivo, la herramienta y la
observación real de cada paso, para poder auditar cómo llegó a su respuesta.

**Requisito EARS (Evento).**
- `[Evento] When` una solicitud requiere varias herramientas, `then` el agente
  SHALL crear un plan con criterio de éxito antes de ejecutar, validar cada
  acción y continuar hasta alcanzar el criterio, el límite de pasos o la falta
  de evidencia.

**Requisito EARS (Comportamiento no deseado).**
- `[Comportamiento no deseado] If` una acción requiere autorización y esta es
  denegada o queda pendiente, `then` el agente SHALL abstenerse de ejecutarla,
  replantear una alternativa no sensible cuando exista o explicar la
  imposibilidad.

**Independent Test**: Se valida con una solicitud que requiere al menos dos
herramientas, comprobando que el historial contiene razones, parámetros y
observaciones reales y que nunca supera el límite configurado.

**Acceptance Scenarios**:

1. **Given** una solicitud multietapa, **When** el agente la atiende, **Then**
   genera un plan explícito y cada afirmación factual final queda anclada en una
   observación real.
2. **Given** una acción sensible denegada, **When** el agente intenta continuar,
   **Then** no ejecuta la acción y replantea o informa la limitación.
3. **Given** un límite de pasos configurado, **When** no se alcanza antes el
   criterio de éxito, **Then** el agente se detiene en dicho límite.

---

## Ampliación Acciones Destructivas

> **Nota de alcance (constitución XII / XIV).** Esta ampliación incorpora al
> alcance la **modificación del proyecto** (crear, editar y eliminar archivos).
> Se documenta antes de implementarse (spec-first) y se apoya en los mecanismos
> ya existentes de autorización (SC-004 / FR-015-016), mínimo privilegio
> (FR-025 / SC-011) y honestidad (FR-019 / SC-002). Las herramientas asociadas
> (`crear_archivo`, `editar_archivo`, `eliminar_archivo`) se añaden como
> componentes modulares (principio II) sin alterar el contrato ni la estabilidad
> de las herramientas existentes.

### User Story 13 - El agente realiza acciones destructivas seguras (crear, editar, eliminar archivos) (Priority: P2)

**Descripción.** Como desarrollador o profesional de QA, quiero que el agente
pueda crear, editar y eliminar archivos del proyecto de forma segura (con
autorización explícita, respaldo del estado previo y verificación del resultado
real), para automatizar cambios de código y configuración manteniendo el
control y la trazabilidad.

**Requisito EARS (Evento).**
- `[Evento] When` el usuario solicita crear, editar o eliminar un archivo del
  proyecto, `then` el agente SHALL ejecutar la operación SOLO dentro de la ruta
  autorizada y SHALL solicitar autorización explícita antes de modificar el
  filesystem.

**Requisito EARS (Estado).**
- `[Estado] While` una operación destructiva está pendiente de autorización,
  `then` el agente SHALL suspender su ejecución y SHALL informar al usuario
  (aligns FR-015/016).

**Requisito EARS (Comportamiento no deseado).**
- `[Comportamiento no deseado] If` la operación intenta actuar fuera del
  perímetro autorizado, sobre un archivo en conflicto (crear uno existente,
  editar/eliminar uno inexistente) o tras una denegación, `then` el agente SHALL
  rechazarla o informarla explícitamente y NO SHALL modificar nada.

**Why this priority**: habilita tareas de cambio y refactor automatizados sobre
el proyecto, de alto valor, pero exige las máximas garantías de seguridad
(autorización, backup, mínimo privilegio).

**Independent Test**: se valida pidiendo crear/editar/eliminar un archivo y
verificando que el agente requiere autorización, respalda el estado previo,
actúa solo dentro del perímetro y reporta el resultado con evidencia real.

**Acceptance Scenarios**:

1. **Given** un archivo dentro del perímetro autorizado, **When** el usuario
   pide editarlo y autoriza la operación, **Then** el archivo se modifica, el
   estado original queda respaldado y el agente reporta el cambio real.
2. **Given** una ruta fuera del perímetro o un archivo inexistente (o existente
   en caso de creación), **When** el agente intenta la operación, **Then** la
   rechaza sin modificar nada.
3. **Given** una denegación de autorización, **When** el usuario la emite,
   **Then** la operación no se ejecuta, se notifica y el bucle re-planifica si
   existe un paso alternativo.

---

## Ampliación Profundidad de Análisis (lectura de código)

> **Nota de alcance (constitución XII / XIV).** Esta ampliación incorpora al
> alcance la capacidad del agente de **leer el contenido real de archivos**
> (`leer_archivo`) y de generar **respuestas profundas** al explicar o entender
> el código del proyecto. Se apoya en los mecanismos existentes de mínimo
> privilegio (FR-025 / SC-011), honestidad (FR-019 / SC-002) y trazabilidad
> (FR-020 / SC-007). `leer_archivo` es una herramienta de **solo lectura**
> (no requiere autorización) y el historial visible del CLI pasa a ser
> **opcional** (`--mostrar-historial`), manteniendo la trazabilidad de cada paso
> en el panel "Razonamiento" (FR-035).

### User Story 14 - El agente explica con profundidad qué hace cada capa y qué pruebas la cubren (Priority: P2)

**Descripción.** Como desarrollador o profesional de QA, quiero que el agente
explique **con profundidad** qué hace cada capa o módulo del proyecto y qué
pruebas lo cubren, leyendo el contenido real de los archivos (no solo sus
nombres), para entender el código y priorizar la validación sin inventar nada.

**Requisito EARS (Evento).**
- `[Evento] When` el usuario pide explicar o entender el código (qué hace una
  capa, qué pruebas cubre un módulo, cómo funciona un archivo), `then` el agente
  SHALL leer el contenido real de los archivos relevantes con `leer_archivo` y
  SHALL basar su explicación en ese contenido.

**Requisito EARS (Comportamiento no deseado).**
- `[Comportamiento no deseado] If` un archivo no existe, queda fuera del
  perímetro autorizado o no puede leerse, `then` el agente SHALL informarlo de
  forma explícita y NO SHALL fabricar su contenido.

**Requisito EARS (Comportamiento no deseado).**
- `[Comportamiento no deseado] If` la evidencia no permite responder la
  intención, `then` el agente SHALL responder con honestidad (`confianza`
  `limitada` o `sin_informacion`) y NO SHALL presentar una hipótesis como hecho.

**Why this priority**: respuestas útiles y confiables al explicar el código,
evitando respuestas superficiales ("no encuentro el código") que degradan la
confianza del usuario (regresión reportada: "explícame qué pruebas hace cada
capa" → respuesta sin contenido).

**Independent Test**: se valida pidiendo al agente que explique qué hace cada
capa o qué pruebas cubre un archivo en un proyecto real (con FakeLLM o LLM
real), verificando que planifica pasos `leer_archivo` sobre archivos concretos
y que la respuesta describe el contenido real leído (clases, funciones, tests)
con `confianza` coherente.

**Acceptance Scenarios**:

1. **Given** un proyecto con capas y tests reales, **When** el usuario pide
   explicar qué hace cada capa o qué pruebas la cubren, **Then** el agente lee
   los archivos relevantes y explica su contenido real organizado por
   capa/módulo (FR-048/049).
2. **Given** un archivo inexistente, fuera del perímetro o ilegible, **When** el
   agente intenta leerlo, **Then** informa la ausencia/fuera-de-perímetro sin
   inventar contenido (FR-019 / FR-025).
3. **Given** una sesión CLI, **When** el agente responde, **Then** el historial
   de acciones NO se muestra por defecto (el razonamiento por paso sigue
   visible, FR-035) y aparece solo con `--mostrar-historial` (FR-050).

---

### Edge Cases

- ¿Qué ocurre cuando el agente no encuentra ninguna herramienta adecuada para
  la solicitud? Debe informarlo y sugerir ajustar la solicitud.
- ¿Cómo se maneja una ruta o archivo inexistente? El agente informa la ausencia
  sin inventar contenido.
- ¿Qué ocurre ante una operación que intenta modificar o eliminar información?
  Se detiene y solicita autorización explícita.
- ¿Cómo se comporta cuando una herramienta devuelve un error o resultados
  inválidos? Maneja el fallo explícitamente y no lo presenta como válido.
- ¿Qué sucede cuando el usuario pide ejecutar un comando potencialmente
  peligroso o no autorizado? El agente lo rechaza o lo restringe según la
  política de mínimo privilegio.
- ¿Qué ocurre cuando un resultado de herramienta contiene secretos o
  credenciales? El agente los filtra u oculta antes de mostrarlos en la
  respuesta, el historial visible o los logs.
- ¿Qué ocurre cuando el usuario pide crear/editar/eliminar un archivo fuera del
  perímetro autorizado? El agente lo rechaza sin modificar nada.
- ¿Qué ocurre ante un conflicto destructivo (crear un archivo que ya existe,
  editar o eliminar un archivo inexistente)? El agente informa el conflicto sin
  modificar nada.
- ¿Qué ocurre si el usuario deniega la autorización de una operación
  destructiva? La operación no se ejecuta, se notifica y, en el bucle ReAct, se
  re-planifica con un paso alternativo si existe (FR-036).
- ¿Qué ocurre si una operación destructiva autorizada falla a mitad de camino?
  El agente reporta el fallo explícitamente y mantiene disponible el backup del
  estado previo para restauración.
- ¿Qué ocurre cuando el agente debe explicar el código de un archivo que no
  existe o queda fuera del perímetro autorizado? Informa la ausencia o el
  rechazo sin fabricar contenido (FR-048/049, FR-025).
- ¿Qué ocurre cuando la búsqueda produce demasiadas coincidencias? `search`
  limita las ocurrencias devueltas (`max_ocurrencias`) y lo avisa explícitamente
  (FR-019, honestidad).
- ¿Qué ocurre cuando una búsqueda con regex amplio volcaría millones de
  caracteres a la observación del LLM? `search` acota el resultado y el agente
  prefiere `leer_archivo` sobre archivos concretos (FR-049).

## Requirements *(mandatory)*

### Functional Requirements

**A. Recepción y generación de respuestas**

- **FR-001**: El agente SHALL aceptar una solicitud del usuario en lenguaje
  natural.
- **FR-002**: El agente SHALL generar una respuesta relacionada directamente con
  la solicitud recibida.

**B. Interacción con herramientas**

- **FR-003**: El agente SHALL seleccionar y ejecutar una herramienta cuando la
  solicitud lo requiera.
- **FR-004**: El agente SHALL basar su respuesta en los resultados reales de las
  herramientas ejecutadas.
- **FR-005**: El agente SHALL validar los resultados de cada herramienta antes de
  usarlos en su razonamiento.
- **FR-020**: El agente SHALL mostrar en la conversación un historial visible de
  cada herramienta ejecutada y del resultado obtenido, para permitir
  trazabilidad, debugging y auditoría.

**C. Exploración y localización**

- **FR-006**: El agente SHALL poder explorar la estructura del proyecto.
- **FR-007**: El agente SHALL poder localizar archivos, clases, funciones o
  componentes mediante búsqueda.
- **FR-008**: El agente SHALL reportar únicamente coincidencias y datos reales
  existentes en el proyecto.

**D. Revisión y análisis de código**

- **FR-009**: El agente SHALL poder revisar partes del código del proyecto.
- **FR-010**: El agente SHALL poder buscar patrones específicos dentro del
  código.
- **FR-011**: El agente SHALL presentar el contenido de código tal como existe en
  el proyecto, sin alterarlo.

**E. Pruebas automatizadas**

- **FR-012**: El agente SHALL poder ejecutar operaciones sobre conjuntos de
  pruebas autorizados.
- **FR-013**: El agente SHALL reportar el estado real de las pruebas ejecutadas.
- **FR-014**: El agente SHALL informar explícitamente los fallos de pruebas y sus
  causas únicamente cuando estén respaldadas por la evidencia.

**F. Autorización (human-in-the-loop)**

- **FR-015**: El agente SHALL solicitar autorización explícita antes de ejecutar
  acciones que puedan modificar, eliminar o afectar información del proyecto.
- **FR-016**: El agente SHALL abstenerse de ejecutar una acción denegada o
  pendiente de autorización y SHALL notificarlo.

**G. Manejo seguro de errores y honestidad**

- **FR-017**: El agente SHALL informar cuando no posee suficiente información
  para responder con confianza.
- **FR-018**: El agente SHALL tratar los errores de las herramientas de forma
  explícita y no continuar como si el resultado fuera válido.
- **FR-019**: El agente SHALL evitar inventar resultados, archivos, pruebas o
  información del proyecto.
- **FR-021**: El agente SHALL filtrar u ocultar cualquier secreto detectado
  (tokens, API keys, credenciales) en los resultados de las herramientas antes de
  mostrarlos en la respuesta, el historial visible o los logs.
- **FR-022**: El agente SHALL informar al usuario cuando ninguna herramienta
  disponible puede atender su solicitud y SHALL sugerir ajustes a la solicitud.
- **FR-023**: El agente SHALL abstenerse de responder con herramientas cuando
  ninguna es adecuada, en lugar de inventar o forzar una ejecución.

**H. Determinismo y mínimo privilegio**

- **FR-024**: El agente SHALL resolver mediante lógica determinística las
  operaciones que no requieren inteligencia artificial, sin depender del modelo
  de lenguaje para dichas operaciones.
- **FR-025**: El agente SHALL ejecutar cada operación bajo el mínimo privilegio
  necesario y SHALL evitar ejecutar comandos peligrosos o no autorizados.

**I. Ampliación QA/Testing**

- **FR-026**: El agente SHALL analizar los resultados de una ejecución de pruebas
  y SHALL reportar un resumen determinista, agrupando fallos únicamente por
  evidencia real (herramienta `analyze_test_results`).
- **FR-027**: El agente SHALL marcar explícitamente como "sin evidencia
  suficiente" cualquier causa de fallo no respaldada por los datos reales de la
  ejecución (aligns FR-014).
- **FR-028**: El agente SHALL poder generar casos de prueba sugeridos (happy
  path, edge cases, negativos) para una función o componente, citando como
  fuente el código real del proyecto (herramienta `generate_test_cases`).
- **FR-029**: El agente SHALL abstenerse de inventar casos o fuentes cuando no
  existe código relevante y SHALL comunicar la falta de evidencia (aligns
  FR-019).
- **FR-030**: El agente SHALL poder analizar la cobertura de código de las
  pruebas, ejecutando el comando autorizado de cobertura y reportando la
  cobertura real global y por archivo (herramienta `analyze_coverage`).
- **FR-031**: El agente SHALL reportar de forma explícita cuando la ejecución de
  cobertura falla o no está disponible, sin presentar cobertura inventada
  (aligns FR-017/FR-018).

**J. Bucle de razonamiento-acción**

- **FR-032**: Cuando una solicitud requiera varias herramientas, el agente SHALL
  crear antes de ejecutar un plan explícito con pasos y criterio de éxito.
- **FR-033**: El agente SHALL seleccionar la herramienta y los parámetros de cada
  paso mediante razonamiento, validándolos contra el esquema y la allowlist
  aplicables antes de ejecutar.
- **FR-034**: El agente SHALL iterar hasta alcanzar el criterio de éxito, el
  límite configurado de pasos o determinar que no existe evidencia suficiente.
- **FR-035**: El agente SHALL conservar trazabilidad por paso con motivo,
  herramienta, parámetros validados y observación real; no SHALL presentar una
  inferencia como si fuera una observación.
- **FR-036**: Si una acción requiere autorización y esta es denegada o queda
  pendiente, el agente SHALL abstenerse de ejecutarla y SHALL replantear una
  alternativa no sensible cuando exista o reportar la imposibilidad.

**K. Acciones destructivas (modificación del proyecto)**

- **FR-042**: El agente SHALL poder crear archivos nuevos dentro del perímetro
  autorizado, rechazando la creación si el archivo ya existe o la ruta queda
  fuera del perímetro (herramienta `crear_archivo`).
- **FR-043**: El agente SHALL poder modificar el contenido de archivos existentes
  dentro del perímetro autorizado, rechazando la edición si el archivo no existe
  o la ruta queda fuera del perímetro (herramienta `editar_archivo`).
- **FR-044**: El agente SHALL poder eliminar archivos existentes dentro del
  perímetro autorizado, rechazando la eliminación si el archivo no existe o la
  ruta queda fuera del perímetro (herramienta `eliminar_archivo`).
- **FR-045**: El agente SHALL respaldar el estado previo (backup) antes de
  modificar o eliminar un archivo, de forma que permita restaurar el original.
- **FR-046**: El agente SHALL solicitar autorización explícita antes de cualquier
  operación que cree, modifique o elimine archivos, y SHALL abstenerse de
  ejecutarla si es denegada o queda pendiente (aligns FR-015/FR-016).
- **FR-047**: El agente SHALL verificar el estado real tras una operación
  destructiva (crear/editar/eliminar) y SHALL reportar el resultado
  (éxito/fracaso) basado en evidencia real, sin afirmar cambios que no ocurrieron
  (aligns FR-019).

**L. Profundidad de análisis (lectura de código)**

- **FR-048**: El agente SHALL poder leer el contenido real de un archivo del
  proyecto dentro del perímetro autorizado, reportando el contenido tal como
  existe, con límite opcional de líneas y aviso explícito de truncado
  (herramienta `leer_archivo`; aligns FR-019/FR-025/SC-011).
- **FR-049**: El agente SHALL, cuando se le pide explicar o entender el código
  (qué hace una capa, qué pruebas cubre un módulo, cómo funciona un archivo),
  planificar pasos que LEAN los archivos relevantes y SHALL responder con
  profundidad organizada por capa/módulo, describiendo el contenido real
  observado y citando los archivos concretos; ante evidencia insuficiente,
  SHALL responder con honestidad y `confianza` coherente (aligns FR-019/SC-002).
- **FR-050**: El agente SHALL poder ocultar el historial visible de acciones en
  el CLI por defecto (manteniendo la trazabilidad por paso en el panel
  "Razonamiento", FR-035) y SHALL mostrarlo explícitamente con la opción
  `--mostrar-historial` (aligns FR-020/SC-007).

### Key Entities

- **Solicitud del usuario**: expresión en lenguaje natural que inicia el flujo
  del agente.
- **Herramienta**: capacidad ejecutable con un contrato definido de entrada y
  salida; no contiene lógica del agente. (El conjunto concreto se determina en
  Plan.)
- **Resultado de herramienta**: salida validable devuelta por una herramienta,
  fuente de verdad para el razonamiento del agente.
- **Respuesta del agente**: respuesta final hacia el usuario, basada en los
  resultados reales obtenidos.
- **Acción sensible**: operación que puede modificar, eliminar o afectar
  información del proyecto y requiere autorización explícita.
- **Backup**: copia del estado original de un archivo (con timestamp) creada antes
  de una operación de modificación o eliminación, que permite restaurar el
  contenido previo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El usuario recibe una respuesta para el 100% de las solicitudes
  válidas procesadas.
- **SC-002**: El 100% de las respuestas basadas en herramientas reflejan solo
  información real del proyecto, sin contenido inventado.
- **SC-003**: Una búsqueda o localización con coincidencias existentes devuelve
  el 100% de las coincidencias reales pertinentes.
- **SC-004**: El 100% de las acciones que pueden modificar o eliminar
  información del proyecto requieren autorización explícita antes de ejecutarse.
- **SC-005**: El 100% de los errores o fallos de herramientas se comunican
  explícitamente y nunca se presentan como resultados válidos.
- **SC-006**: Las herramientas pueden probarse en un 100% de los casos sin
  depender de un modelo de lenguaje real.
- **SC-007**: El 100% de las solicitudes que usan herramientas muestran un
  historial visible de las herramientas ejecutadas y sus resultados, permitiendo
  reconstruir la secuencia de acciones.
- **SC-008**: El 100% de los secretos detectados en resultados de herramientas se
  ocultan o filtran antes de aparecer en respuestas, historial o logs.
- **SC-009**: El 100% de las solicitudes sin herramienta adecuada se resuelven
  con una notificación explícita y una sugerencia de ajuste, sin inventar una
  ejecución o resultados.
- **SC-010**: El 100% de las operaciones que no requieren inteligencia artificial
  producen resultados determinísticos, independientes del modelo de lenguaje.
- **SC-011**: El 100% de las operaciones se ejecutan con el mínimo privilegio
  necesario y ninguna ejecuta comandos no autorizados o peligrosos.
- **SC-012**: El 100% de los análisis de resultados de pruebas producen un
  resumen determinista basado solo en evidencia real, y ninguna causa sin
  evidencia se presenta como un hecho (FR-026/027).
- **SC-013**: El 100% de los casos de prueba generados citan código real del
  proyecto, y ninguna generación se produce sin evidencia (FR-028/029).
- **SC-014**: El 100% de los análisis de cobertura reportan cobertura real
  (global y por archivo) o, ante fallo, informan el estado explícitamente sin
  inventar cobertura (FR-030/031).
- **SC-015**: El 100% de las solicitudes multietapa conservan un historial de
  pasos con motivo, herramienta, parámetros y observaciones reales (FR-032..035).
- **SC-016**: Ninguna ejecución del bucle supera el límite `pasos_max`
  configurado (FR-034).
- **SC-017**: El 100% de las afirmaciones factuales de la respuesta final quedan
  ancladas en observaciones reales; las inferencias se distinguen explícitamente
  (FR-035).
- **SC-021**: El 100% de las operaciones que crean, modifican o eliminan archivos
  requieren autorización explícita antes de ejecutarse (FR-046, aligns SC-004).
- **SC-022**: El 100% de las operaciones destructivas operan SOLO dentro del
  perímetro autorizado; ninguna actúa fuera de la allowlist (FR-042..044,
  aligns SC-011).
- **SC-023**: El 100% de las operaciones de modificación/eliminación se respaldan
  (backup) antes de ejecutarse y verifican el estado real después (FR-045/047).
- **SC-024**: El 100% de los resultados de operaciones destructivas se reportan
  con evidencia real, sin afirmar cambios que no ocurrieron (FR-047, aligns
  SC-002).
- **SC-025**: El 100% de las lecturas de archivos devuelven el contenido real tal
  como existe (o informan explícitamente la ausencia/rechazo), sin contenido
  inventado ni lecturas fuera del perímetro (FR-048, aligns SC-002/SC-011).
- **SC-026**: El 100% de las solicitudes de explicar/entender el código que
  pueden responderse con lectura de archivos producen respuestas profundas
  ancladas en el contenido real (organizadas por capa/módulo y citando archivos
  concretos); las que no pueden responderse se comunican con honestidad y
  `confianza` no alta (FR-049, aligns SC-002).

## Assumptions

- El agente es un asistente controlado orientado a herramientas que apoya al
  desarrollador o profesional de QA, sin reemplazarlo.
- El alcance del MVP se limita a las tareas de análisis, exploración y
  validación descritas; capacidades como multi-agente, RAG, memoria de largo
  plazo o MCP quedan fuera del alcance inicial.
- La conversación persistente, la memoria y gestión de tareas entre sesiones,
  y el almacenamiento `.qa_sessions` quedan diferidos; US-12, FR-037..FR-041 y
  SC-018..SC-020 no son requisitos aprobados de este MVP.
- El agente opera únicamente sobre proyectos de software de confianza a los que
  se le otorga acceso explícito y autorizado.
- Las pruebas y la cobertura autorizadas pueden ejecutar código del proyecto
  directamente en el host. El MVP no garantiza aislamiento de procesos, red,
  credenciales ni sistema de archivos; el usuario debe autorizar estas
  operaciones únicamente para repositorios de confianza.
- El conjunto concreto de herramientas, el proveedor del modelo de lenguaje y el
  framework de agentes son decisiones de Plan/Implementation y no se fijan en
  esta especificación.
- La ejecución de pruebas se limita a conjuntos autorizados por el usuario o por
  la configuración del entorno.
- Contar con un entorno de ejecución de pruebas disponible cuando el usuario
  solicita ejecutar pruebas.
