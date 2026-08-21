# Feature Specification: Production Readiness del agente QA

**Feature Branch**: `002-production-readiness` (implementada sobre `john-branch`)
**Created**: 2026-08-21
**Status**: Draft
**Input**: Auditoría externa (informe de evaluación Copilot, 2026-08-20) + acta de
verificación independiente (2026-08-21) sobre `abraham-full-tasks-branch@8695466`.

## Contexto y autoridad

El programa I01–I16 cerró los tres hallazgos P0 de seguridad y dejó 8 ítems como
"design complete" (propuesta escrita, cero código). La verificación independiente
encontró además tres defectos no reportados: CI en rojo desde su creación,
intérprete `python` hardcodeado (el agente no puede ejecutar pruebas en macOS ni
en distribuciones sin alias `python`), y verificación realizada en una sola
plataforma.

Orden de autoridad aplicado: Constitución → esta especificación → plan →
contratos → tasks. Las propuestas `docs/proposals/I06,I09,I10,I11,I12,I13,I14`
son **entrada de diseño**, no autoridad: donde esta especificación difiera de
ellas, manda esta especificación.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - La verificación es creíble en cualquier máquina (Priority: P1)

Como responsable del proyecto, necesito que la suite completa y el pipeline de CI
pasen en Linux, macOS y Windows, para que "505 passed" signifique lo mismo
independientemente de quién lo ejecute.

**Why this priority**: mientras el CI esté rojo, ninguna garantía del programa
I01–I16 es verificable por un tercero. Bloquea todo lo demás.

**Acceptance Scenarios**

1. **Given** un checkout limpio en Linux, **When** se ejecuta `pytest`,
   **Then** la suite pasa sin fallos.
2. **Given** un checkout limpio en macOS sin alias `python`, **When** el agente
   ejecuta `run_tests` sobre un proyecto pytest real, **Then** las pruebas se
   ejecutan y se reportan resultados reales (no `no_ejecutado`).
3. **Given** un reporte JaCoCo generado por Maven en Linux, **When**
   `analyze_coverage` lo procesa, **Then** devuelve cobertura real.
4. **Given** un push a cualquier rama, **When** corre el workflow de CI,
   **Then** los jobs `test` y `quality` terminan en verde.

### User Story 2 - El agente explica por qué no pudo ejecutar (Priority: P1)

Como usuario de QA, cuando el agente no logra ejecutar pruebas o cobertura,
necesito saber la causa exacta (runner ausente, sin tests, fallo de colección,
timeout) en vez de un `no_ejecutado` opaco.

**Why this priority**: es el fallo más común de un agente QA y hoy es
indistinguible. Además es prerrequisito de la observabilidad (US3) y del harness
de evaluación (US4), que necesitan una señal de éxito/fracaso fiable.

**Acceptance Scenarios**

1. **Given** un proyecto sin runner instalado, **When** se ejecuta `run_tests`,
   **Then** el resultado incluye `causa_no_ejecutado = "runner_no_disponible"`.
2. **Given** un proyecto sin archivos de prueba, **When** se ejecuta `run_tests`,
   **Then** `causa_no_ejecutado = "sin_pruebas"` y `estado_global = "no_ejecutado"`.
3. **Given** cualquier ejecución, **When** termina, **Then** el resultado incluye
   `exit_code`, `runner_detectado` y `duracion_ms` reales.
4. **Given** una ejecución con salida, **When** termina, **Then** `stdout_tail` y
   `stderr_tail` contienen la cola real de la salida, ya redactada.

### User Story 3 - Cada solicitud deja una traza auditable (Priority: P2)

Como responsable de calidad, necesito una traza estructurada por solicitud
(herramienta, duración, decisión de autorización, evidencia, razón de parada)
para diagnosticar respuestas incompletas, que no lanzan excepción.

**Why this priority**: el principio VIII de la constitución exige observabilidad
y trazabilidad; hoy solo hay logging de texto. Sin esto, los fallos silenciosos
del agente son invisibles.

**Acceptance Scenarios**

1. **Given** `--trace-file traza.jsonl`, **When** se procesa una solicitud,
   **Then** se escribe un evento JSONL por paso con `solicitud_id`,
   `herramienta`, `duracion_ms`, `estado` y `autorizacion`.
2. **Given** una traza escrita, **When** se inspecciona, **Then** no contiene
   ningún secreto (misma redacción que la respuesta visible).
3. **Given** dos ejecuciones idénticas en modo demo, **When** se comparan las
   trazas ignorando duraciones y marcas de tiempo, **Then** son idénticas.

### User Story 4 - El agente es medible (Priority: P2)

Como responsable técnico, necesito ejecutar un conjunto fijo de tareas contra
proyectos de referencia y obtener métricas comparables entre ejecuciones y entre
proveedores de modelo.

**Why this priority**: es la brecha señalada como más grave en la evaluación
externa ("benchmark readiness 5.5/10") y la única forma de detectar regresiones
de comportamiento, que los tests unitarios no capturan.

**Acceptance Scenarios**

1. **Given** el harness instalado, **When** se ejecuta `qa-agent eval`,
   **Then** reporta por tarea: herramienta elegida, anclaje en evidencia,
   seguridad (autorización solicitada cuando correspondía), pasos y latencia.
2. **Given** dos ejecuciones en modo demo, **When** se comparan los resultados,
   **Then** las métricas no relacionadas con tiempo son idénticas.
3. **Given** `--json`, **When** se ejecuta la evaluación, **Then** la salida es
   JSON válido apto para CI.

### User Story 5 - La CLI sirve en automatización (Priority: P3)

Como ingeniero de plataforma, necesito ejecutar el agente desde CI con salida
machine-readable, sin color, con presupuesto de pasos acotado y sin efectos
secundarios cuando solo quiero inspeccionar el plan.

**Acceptance Scenarios**

1. **Given** `--json`, **When** se hace una pregunta, **Then** la salida es JSON
   válido y no contiene secuencias de escape ANSI.
2. **Given** `--dry-run`, **When** la solicitud implica una acción sensible,
   **Then** se reporta lo que se haría y **no** se ejecuta.
3. **Given** `--max-steps N`, **When** el agente razona, **Then** nunca ejecuta
   más de N pasos.

### User Story 6 - El agente cubre los ecosistemas del equipo (Priority: P3)

Como usuario con repositorios JS/TS, Go y Rust, necesito que el agente detecte el
runner correcto y ejecute pruebas y cobertura en esos proyectos.

**Acceptance Scenarios**

1. **Given** un proyecto con `package.json` y script `test`, **When** el agente
   detecta el runner, **Then** propone el comando npm correspondiente.
2. **Given** un proyecto con `go.mod`, **Then** propone `go test ./...`.
3. **Given** un proyecto con `Cargo.toml`, **Then** propone `cargo test`.
4. **Given** cualquiera de ellos, **When** se ejecuta, **Then** el comando pasa
   por la allowlist de comandos y `shell=False` (sin excepción al principio IV).

### Edge Cases

- Runner detectado pero binario ausente en el PATH → `runner_no_disponible`, no
  excepción, no invención de resultados.
- Reporte de cobertura referenciado en stdout pero inexistente en disco → se
  distingue de "el comando falló" (`causa_no_ejecutado` distinto).
- Traza a un archivo sin permisos de escritura → la solicitud continúa y se
  reporta el fallo de traza; la observabilidad nunca rompe la función principal.
- `--json` combinado con una acción que requiere autorización interactiva → se
  reporta `pendiente_autorizacion` en JSON sin bloquear esperando stdin.
- Esquema con `oneOf`/`pattern` que ninguna herramienta actual usa → el validador
  lo soporta sin cambiar el veredicto de los esquemas existentes.

## Requirements *(mandatory)*

### Functional Requirements

**Portabilidad y verificación (US1)**

- **FR-101**: Toda invocación de un intérprete de Python en subproceso DEBE usar
  el intérprete actual (`sys.executable`), nunca el literal `python`.
- **FR-102**: La resolución de rutas de reportes de cobertura DEBE ser correcta
  en POSIX y Windows; no se permite conversión incondicional de separadores.
- **FR-103**: Los tests que dependan del ancho de terminal DEBEN fijarlo
  explícitamente, no heredarlo del entorno.
- **FR-104**: El pipeline de CI DEBE terminar en verde en Linux para las
  versiones de Python soportadas.

**Metadatos de ejecución (US2)**

- **FR-105**: `run_tests` DEBE devolver `exit_code`, `runner_detectado`,
  `duracion_ms`, `stdout_tail`, `stderr_tail` y `causa_no_ejecutado`.
- **FR-106**: `causa_no_ejecutado` DEBE distinguir al menos:
  `runner_no_disponible`, `sin_pruebas`, `fallo_de_coleccion`, `timeout`,
  `comando_no_permitido`, `salida_no_parseable`, y vacío cuando sí se ejecutó.
- **FR-107**: `analyze_coverage` DEBE devolver los mismos metadatos de ejecución
  y distinguir "el comando falló" de "no se encontró reporte".
- **FR-108**: `stdout_tail`/`stderr_tail` DEBEN pasar por el `Redactor` antes de
  incorporarse al resultado (principio XI).
- **FR-109**: La ampliación de esquema DEBE ser retrocompatible: los campos
  preexistentes conservan nombre, tipo y semántica.

**Observabilidad (US3)**

- **FR-110**: El agente DEBE emitir eventos estructurados por paso con
  `solicitud_id` correlacionable, herramienta, duración, estado y decisión de
  autorización.
- **FR-111**: Los eventos DEBEN escribirse en JSONL cuando se solicite un
  archivo de traza, y nunca contener secretos.
- **FR-112**: Un fallo de escritura de traza NUNCA debe abortar la solicitud.
- **FR-113**: La traza DEBE registrar la razón de parada del bucle
  (`presupuesto_agotado`, `evidencia_suficiente`, `sin_herramienta`, `error`).

**Evaluación (US4)**

- **FR-114**: DEBE existir un harness que ejecute un conjunto declarado de tareas
  contra proyectos de referencia versionados en el repositorio.
- **FR-115**: El harness DEBE calcular al menos: acierto de herramienta, anclaje
  en evidencia, seguridad (autorización), eficiencia en pasos y latencia.
- **FR-116**: Con `FakeLLM`, las métricas no temporales DEBEN ser deterministas.
- **FR-117**: El harness DEBE exponerse como subcomando de la CLI y emitir JSON.

**CLI (US5)**

- **FR-118**: La CLI DEBE ofrecer `--json`, `--no-color`, `--max-steps`,
  `--model`, `--base-url`, `--dry-run` y `--trace-file`.
- **FR-119**: `--dry-run` NUNCA debe ejecutar una herramienta que requiera
  autorización ni modificar el proyecto.
- **FR-120**: `--json` DEBE producir JSON válido en stdout sin ANSI.
- **FR-121**: Las opciones documentadas DEBEN seguir siendo verificables por el
  test de contrato de CLI (T129) tras la ampliación.

**Ecosistemas (US6)**

- **FR-122**: La detección de runner DEBE cubrir JS/TS (npm/yarn/pnpm), Go y
  Rust, además de los existentes.
- **FR-123**: Todo comando nuevo DEBE pasar por la allowlist de comandos y
  ejecutarse con `shell=False`.
- **FR-124**: La detección DEBE basarse en manifiestos reales presentes en disco,
  nunca en suposición por extensión de archivo.

**Deuda transversal**

- **FR-125**: El `Redactor` DEBE cubrir claves de Google (`AIza…`) y tokens de
  Azure/Entra.
- **FR-126**: La política de exclusión DEBE incluir `htmlcov` y `coverage`, y
  `explore` DEBE podar por descendiente los directorios de artefactos.
- **FR-127**: El validador de esquemas DEBE soportar `additionalProperties`,
  `pattern`, `oneOf`/`anyOf` y `minLength`/`maxLength`, y DEBE poder explicar el
  motivo del rechazo sin cambiar el veredicto de los esquemas existentes.
- **FR-128**: Las tablas de intención DEBEN admitir configuración declarativa y
  cobertura de tests parametrizados.

### Key Entities

- **EventoDeTraza**: `solicitud_id`, `secuencia`, `momento`, `tipo`,
  `herramienta`, `duracion_ms`, `estado`, `autorizacion`, `detalle` (redactado).
- **MetadatosDeEjecucion**: `exit_code`, `runner_detectado`, `duracion_ms`,
  `stdout_tail`, `stderr_tail`, `causa_no_ejecutado`.
- **TareaDeEvaluacion**: `id`, `proyecto`, `solicitud`, `herramienta_esperada`,
  `debe_pedir_autorizacion`, `evidencia_esperada`, `pasos_optimos`.
- **ResultadoDeEvaluacion**: métricas por tarea y agregado reproducible.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-101**: La suite completa pasa en Linux, macOS y Windows: 0 fallos.
- **SC-102**: El workflow de CI termina en verde en un push real.
- **SC-103**: `run_tests` y `analyze_coverage` reportan causa explícita en el
  100 % de los modos de fallo enumerados en FR-106.
- **SC-104**: Una solicitud completa produce una traza JSONL con al menos un
  evento por paso ejecutado y cero secretos.
- **SC-105**: `qa-agent eval` produce métricas idénticas en dos corridas
  consecutivas en modo demo (excepto latencia).
- **SC-106**: Las siete banderas de FR-118 aparecen en `--help` y están cubiertas
  por tests de contrato.
- **SC-107**: Un proyecto JS/TS, uno Go y uno Rust obtienen el runner correcto.
- **SC-108**: `ruff check .` sin hallazgos y `pip check` limpio.
- **SC-109**: Ningún test preexistente cambia de veredicto por regresión: las
  suites de seguridad T125–T130 siguen en verde.

## Assumptions

- El entorno de CI seguirá siendo GitHub Actions sobre `ubuntu-latest`; la
  paridad con macOS/Windows se garantiza por diseño del código, y se añade macOS
  a la matriz para probarlo de forma continua.
- Los proyectos de referencia del harness son fixtures pequeños versionados en el
  repositorio; no se descargan proyectos externos en tiempo de evaluación.
- Go y Rust pueden no estar instalados en CI: la detección de runner se prueba
  sin ejecutar el runner real (FR-124 permite verificar detección por manifiesto).
- No se adopta ninguna dependencia nueva salvo que un requisito la exija de forma
  irreducible (principio XII). `mypy` se evalúa como herramienta de desarrollo,
  no como dependencia de ejecución.
