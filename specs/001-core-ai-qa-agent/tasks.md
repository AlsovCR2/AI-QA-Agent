---

description: "Task list template for feature implementation"
---

# Tasks: Core AI QA & Software Engineering Agent

**Input**: Design documents from `/specs/001-core-ai-qa-agent/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Se incluyen tareas de prueba en modo TDD (red → green). Requerido por el
spec (sección "User Scenarios & Testing") y por la constitución (III - Testabilidad).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/qa_agent/`, `tests/` at repository root
- **CLI**: `src/qa_agent/cli/main.py` expuesto como comando `qa-agent`
- Paths reflect the project structure defined in plan.md

> **Ruta base de código**: `src/qa_agent/` | **Ruta base de tests**: `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Setup Python project scaffolding: `pyproject.toml`, `.gitignore`, `src/qa_agent/__init__.py`, `src/qa_agent/py.typed`, `README.md`

**Condition of Done (T001)**:
- [x] `pyproject.toml` existe con: `[project]` (name=`qa-agent`, version, requires-python=">=3.11"), `[build-system]` con setuptools, configuración de `[project.scripts]` en T014.
- [x] `.gitignore` excluye `__pycache__/`, `*.pyc`, `.env`, `dist/`, `.pytest_cache/`, `.venv/`.
- [x] `src/qa_agent/__init__.py` exporta la API pública (`Agent`) sin efectos secundarios.
- [x] `src/qa_agent/py.typed` presente (marcador de tipado PEP 561).
- [x] `python -c "import qa_agent"` funciona desde la raíz con el paquete instalable en editable.

- [x] T002 [P] Create package directory skeleton: `src/qa_agent/{agent,tools,llm,security,cli}/__init__.py` (empty modules with docstrings)

**Condition of Done (T002)**:
- [x] Todos los submódulos `agent/`, `tools/`, `llm/`, `security/`, `cli/` existen con su `__init__.py`.
- [x] `pytest` recoge la suite sin errores de import (ejecutar `pytest --collect-only`).

- [x] T003 [P] Configure dependencies in `pyproject.toml`: `[project.dependencies] = ["openai", "python-dotenv", "pydantic", "typer", "rich", "pathspec"]`, `[project.optional-dependencies] dev = ["pytest"]`, `[tool.pytest.ini_options] testpaths = ["tests"]`

**Condition of Done (T003)**:
- [x] `pip install -e .` instala las dependencias de producción (openai, python-dotenv, pydantic, typer, rich, pathspec) sin error.
- [x] `pip install -e ".[dev]"` instala además pytest sin error.
- [x] `pytest` corre una suite vacía con código de salida 0.
- [x] Las dependencias se declaran en `pyproject.toml` conforme a la decisión D10 (`research.md`).

- [x] T004 [P] Create `tests/conftest.py` with shared fixtures: `fake_llm` (FakeLLM), `proyecto_ejemplo` (temp dir con archivos/código/tests), `redactor` instance

**Condition of Done (T004)**:
- [x] Fixture `proyecto_ejemplo` crea un `tmp_path` determinista con: al menos 1 directorio de código, 1 archivo de prueba `test_main.py` (una prueba que pase y una que falle), y un patrón buscable único (`config()`).
- [x] Fixture `fake_llm` instancia un backend determinista (ver T012) sin red real.
- [x] `pytest` no muestra warnings de fixtures sin usar.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 [P] Create `src/qa_agent/tools/base.py`: clase base `Herramienta` (dataclass/ABC) con `id`, `descripcion`, `esquema_entrada`, `esquema_salida`, `requiere_autorizacion` y método `ejecutar(parametros) -> ResultadoDeHerramienta`

**Condition of Done (T005)** — ver `contracts/tool-contracts.md`:
- [x] `Herramienta` define los campos y el método abstracto `ejecutar`.
- [x] La herramienta NO contiene lógica de agente ni selecciona otras herramientas (principio I).
- [x] Puede instanciarse e importarse sin LLM (III / SC-006).

- [x] T006 [P] Create `src/qa_agent/tools/base.py` validación de contratos: función `validar_resultado(herramienta, resultado) -> bool` que valida salida contra `esquema_salida` (FR-005, VII)

**Condition of Done (T006)**:
- [x] `validar_resultado` devuelve `True` solo si el resultado cumple el esquema de salida.
- [x] Devuelve `False` para resultados con tipo/estructura inválida (sin lanzar excepción de validación de esquema no controlada).
- [x] Es pura y determinística (no LLM) (VI / SC-010).

- [x] T007 [P] Create `src/qa_agent/security/authorization.py`: modelo `AccionSensible` (véase `data-model.md`) y gestor de autorización con estados `pendiente/autorizada/denegada/ejecutada/no_ejecutada`

**Condition of Done (T007)** — ver `data-model.md` (AccionSensible):
- [x] `AccionSensible` tiene campos: `id`, `descripcion`, `estado`, `herramienta_id`.
- [x] Transición de estados respeta el diagrama de `data-model.md` (pendiente→autorizada→ejecutada; pendiente→denegada→no_ejecutada).
- [x] Se impide ejecutar una acción no `autorizada` (FR-016, V).

- [x] T008 [P] Create `src/qa_agent/security/redactor.py`: clase `Redactor` con patrones de detección de secretos (API keys, bearer tokens) y método `redactar(texto/dict) -> str/dict` (FR-021, XI)

**Condition of Done (T008)**:
- [x] `Redactor.redactar` sustituye secretos detectados por `***` en strings y recursivamente dentro de dicts/listas.
- [x] Detecta al menos: tokens `sk-...`, `Bearer <jwt>`, `api_key=...`, genérico `ass?:[a-z0-9]{8,}`.
- [x] No altera texto sin secretos (idempotente y sin falsos positivos en texto normal).
- [x] `Redactor` se aplica SIEMPRE antes de emitir respuesta/historial/logs (SC-008).

- [x] T009 Create `src/qa_agent/tools/allowlist.py`: clase `Allowlist` que restringe rutas autorizadas para mínimo privilegio (FR-025, IV)

**Condition of Done (T009)** — ver `contracts/tool-contracts.md`:
- [x] `Allowlist.__contains__(ruta)` resuelve una ruta solicitada contra la lista de rutas autorizadas.
- [x] Devuelve `False` para rutas fuera del perímetro autorizado.
- [x] Normaliza rutas (resolución de `..`, symlinks cuando aplique) para evitar escapes del perímetro.

- [x] T010 [P] Create `src/qa_agent/llm/backend.py`: interfaz `LLMBackend` (ABC/Protocol) con `interpretar`, `seleccionar_herramienta`, `generar_respuesta` (ver `contracts/llm-backend-contract.md`)

**Condition of Done (T010)**:
- [x] `LLMBackend` define los métodos del contrato con firma estable.
- [x] El núcleo depende solo de esta interfaz, nunca de una implementación concreta (independencia de proveedor).

- [x] T011 [P] Create `src/qa_agent/llm/openai_compatible_backend.py`: `OpenAICompatibleBackend` que implementa `LLMBackend` (Chat Completions); por defecto apunta a **DeepSeek** (`LLM_BASE_URL=https://api.deepseek.com`, `LLM_MODEL=deepseek-v4-flash`), y soporta **NVIDIA NIM / OpenAI** cambiando `LLM_BASE_URL`/`LLM_MODEL`; lee credenciales de variables de entorno vía `python-dotenv` (nunca del código, XI)

**Condition of Done (T011)**:
- [x] `OpenAICompatibleBackend` implementa los 3 métodos del contrato y construye el cliente con `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`.
- [x] Los valores por defecto usan DeepSeek (`https://api.deepseek.com`, `deepseek-v4-flash`).
- [x] Es configurable para NVIDIA NIM (`https://integrate.api.nvidia.com/v1`, `deepseek-ai/deepseek-v4-flash`) y OpenAI (`https://api.openai.com/v1`) solo vía `.env` (ver `contracts/llm-backend-contract.md`).
- [x] La API key se obtiene únicamente de `os.environ` / `.env`; nunca hardcodeada (XI).
- [x] Si falta `LLM_API_KEY` en producción, lanza error explícito (no falla silencioso).

- [x] T012 [P] Create `src/qa_agent/llm/fake_llm.py`: `FakeLLM` determinista (scripted) para pruebas y modo `--demo`, implementando `LLMBackend` sin red (III / SC-006)

**Condition of Done (T012)**:
- [x] `FakeLLM` devuelve selecciones/interpretaciones/configuradas de forma determinista (sin red).
- [x] Soporta scripts por test (selección de herramienta, "ninguna herramienta", respuestas fijas).
- [x] `requiere_proveedor == False`.

- [x] T013 Create `src/qa_agent/cli/main.py` (STUB): función `main()` con `typer` que inicializa la config y delega al REPL (implementación completa en US1)

**Condition of Done (T013)**:
- [x] `main()` se registra en `pyproject.toml` `[project.scripts] qa-agent = "qa_agent.cli.main:app"` (T014).
- [x] `qa-agent --version` imprime la versión sin error.
- [x] Argumentos `--ruta`, `--pregunta`, `--demo` se parsean (ver contrato CLI).

- [x] T014 Update `pyproject.toml` con `[project.scripts] qa-agent = "qa_agent.cli.main:app"` (habilita instalación global sobre otros proyectos)

**Condition of Done (T014)**:
- [x] Tras `pip install .` (o `pipx install .`), el comando `qa-agent` está disponible en el PATH.
- [x] `qa-agent --version` funciona desde cualquier directorio (Opción 1: uso global).
- [x] La instalación no rompe `pip install -e ".[dev]"` para desarrollo.

- [x] T015 Create `src/qa_agent/agent/session.py`: `Sesion` que mantiene el estado por conversación en memoria (sin BD) y el historial visible `List[RegistroDeAccion]` (FR-020, VIII)

**Condition of Done (T015)** — ver `data-model.md` (RegistroDeAccion, RespuestaDelAgente):
- [x] `Sesion` guarda en memoria: solicitudes, resultados, acciones y el historial `RegistroDeAccion` ordenado.
- [x] NO persiste a disco/BD (Storage: N/A, memoria por conversación; XII).
- [x] Expose `agregar_accion(...)` que siempre redacta secretos (via `Redactor`) antes de añadir al historial (SC-008).
- [x] El historial permite reconstruir la secuencia de acciones (orden/intersección por `orden`) (SC-007).

- [x] T016 Create `src/qa_agent/agent/response.py`: `RespuestaDelAgente` con `texto`, `solicitud_id`, `acciones`, `confianza`, `basada_en_herramientas` (ver `data-model.md`)

**Condition of Done (T016)**:
- [x] `RespuestaDelAgente` expone los campos del data-model.
- [x] `acciones` incluye cada herramienta ejecutada y su resultado cuando hubo herramientas (SC-007).
- [x] `confianza` puede ser `sin_informacion` (UC-007).

- [x] T017 [P] Create configuration module `src/qa_agent/config.py`: carga `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY` (DeepSeek por defecto, NVIDIA/OpenAI alternativos), selecciona backend (FakeLLM en `--demo` o sin key), construye `Allowlist` (FR-025)

**Condition of Done (T017)**:
- [x] `config` define los valores por defecto de DeepSeek (`LLM_BASE_URL=https://api.deepseek.com`, `LLM_MODEL=deepseek-v4-flash`).
- [x] `config` decide el backend: real si `LLM_API_KEY` presente, `FakeLLM` en `--demo`/ausencia de key.
- [x] Permite cambiar a NVIDIA NIM / OpenAI vía `.env` (ver `contracts/llm-backend-contract.md`).
- [x] `Allowlist` se construye con la ruta objetivo (`--ruta` o `cwd`).
- [x] No imprime nada de secretos en configuración ni logs.

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - El agente recibe una solicitud y responde usando herramientas (Priority: P1) 🎯 MVP

**Goal**: El agente procesa una solicitud, selecciona/ejecuta herramienta, valida el resultado real y genera una respuesta basada en evidencia, con historial visible (FR-001, FR-002, FR-003, FR-004, FR-005, FR-020).

**Independent Test**: Se envía una solicitud de ejemplo y se verifica que la respuesta se basa en una herramienta real ejecutada y no en información fabricada, mostrando historial visible.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T018 [P] [US1] Unit test del bucle del agente con `FakeLLM` en `tests/unit/test_agent_loop.py` (recibe solicitud → selecciona herramienta → ejecuta → responde)

**Condition of Done (T018)**:
- [x] Test falla antes de implementar `loop.py` (red).
- [x] Verifica: respuesta no vacía para solicitud válida (SC-001).
- [x] Verifica: con solicitud que requiere info del proyecto, se ejecuta una herramienta real y la respuesta se basa en su resultado (FR-003/004).

- [x] T019 [P] [US1] Unit test de `validar_resultado` en `tests/contract/test_tool_contracts.py` (resultado válido vs inválido) (FR-005)

**Condition of Done (T019)**:
- [x] Cubre resultado válido → `True`.
- [x] Cubre resultado inválido (estructura/tipo erróneo) → `False`, y el agente no lo presenta como válido (SC-005).

- [x] T020 [P] [US1] Unit test del historial visible en `tests/unit/test_session.py`: registrar acciones y reconstruir secuencia (FR-020, SC-007)

**Condition of Done (T020)**:
- [x] Tras 2+ acciones, el historial mantiene el orden de `orden`.
- [x] El historial redacta secretos antes de exponerse (SC-008).

### Implementation for User Story 1

- [x] T021 Create `src/qa_agent/agent/loop.py`: bucle `Agent.atender(solicitud)` — interpretar → seleccionar herramienta → ejecutar → validar → autorizar si sensible → generar respuesta con historial visible (FR-001..005, FR-020)

**Condition of Done (T021)**:
- [x] `atender` acepta texto en lenguaje natural y produce respuesta relacionada (FR-001/002).
- [x] Si la solicitud requiere información del proyecto, selecciona y ejecuta herramienta pertinente antes de responder (FR-003).
- [x] Valida el resultado de cada herramienta antes de usarlo (FR-005).
- [x] Basa la respuesta en resultados reales (no fabrica) (FR-004, SC-002).
- [x] Registra en `Sesion` cada herramienta y resultado (historial visible) (FR-020, SC-007).
- [x] Si ninguna herramienta es adecuada → responde notificación + sugerencia, sin forzar ejecución (FR-022/023, SC-009).
- [x] Pasa `T018`, `T019`, `T020`.

- [x] T022 [US1] Integrar autorización en el loop: acciones con `requiere_autorizacion=True` se suspenden y solicitan autorización antes de ejecutar (US1 rail de US6) (FR-015/016)

**Condition of Done (T022)**:
- [x] Ante acción sensible, la ejecución se suspende y se solicita autorización explícita (SC-004).
- [x] No se ejecuta hasta `autorizada`.
- [x] Si `denegada` → no ejecuta y notifica (FR-016).

- [x] T023 [US1] Integrar `Redactor` en respuesta e historial: redactar secretos en salidas de herramientas antes de mostrarlas (FR-021, SC-008)

**Condition of Done (T023)**:
- [x] Toda salida de herramienta pasa por `Redactor` antes de usarse en respuesta/historial.
- [x] Ningún secreto aparece en respuesta, historial visible ni logs (SC-008, XI).

- [x] T024 [US1] Implementar el REPL interactivo y modos CLI en `src/qa_agent/cli/main.py` con `typer`: loop de lectura, `--ruta`, `--pregunta`, `--demo`, y renderizado del historial visible con `rich` (ver contrato CLI, FR-020)

**Condition of Done (T024)**:
- [x] Modo interactivo lee solicitudes de stdin en bucle.
- [x] `--pregunta "<texto>"` procesa una consulta puntual y termina.
- [x] `--ruta` define la raíz del proyecto a analizar (default `cwd`).
- [x] `--demo` fuerza `FakeLLM`.
- [x] Imprime la respuesta y el historial visible.

- [x] T025 [US1] Configurar logging con redacción de secretos en `src/qa_agent/.../logging_config.py` o equivalente (FR-021, VIII)

**Condition of Done (T025)**:
- [x] Los logs estructurados incluyen herramientas y resultados (trazabilidad, VIII).
- [x] Un formatter/`Redactor` evita que secretos aparezcan en logs (SC-008).
- [x] Los logs son deterministas en sus campos (SC-010).

**Checkpoint**: User Story 1 está funcional: el flujo fundamental del agente funciona con historial visible, autorización y redacción de secretos. MVP alcanzado.

---

## Phase 4: User Story 2 - El agente explora la estructura del proyecto (Priority: P1)

**Goal**: Explorar la estructura del proyecto y presentar estructura real (sin inventar) (FR-006, FR-007, FR-008).

**Independent Test**: Ante una petición de estructura, la respuesta refleja archivos/directorios reales del proyecto; una ruta inexistente/no autorizada se informa sin inventar contenido.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T026 [P] [US2] Unit test de `explore` en `tests/unit/test_tools_explore.py`: listar estructura real y rechazar ruta inexistente/no autorizada (FR-006/007/008, UC-002)

**Condition of Done (T026)**:
- [x] Cubre caso con estructura real → devuelve elementos reales (SC-003).
- [x] Cubre ruta inexistente → `existe=False` y el agente informa que no puede acceder (UC-002 alternativo).
- [x] Cubre ruta fuera de allowlist → no accede (no inventa contenido) (SC-002).

### Implementation for User Story 2

- [x] T027 Create `src/qa_agent/tools/explore.py`: herramienta `explore` que recorre el árbol de directorios (con `profundidad_max`) respetando `Allowlist` y devuelve elementos reales (FR-006/007/008)

**Condition of Done (T027)** — ver `contracts/tool-contracts.md` (explore):
- [x] Implementa `ejecutar` con esquema de entrada/salida del contrato.
- [x] Reporta únicamente información real de la estructura existente (FR-008).
- [x] No accede a rutas fuera de la `Allowlist` (FR-025) ni a rutas inexistentes (las marca `existe=False`).
- [x] Determinística (sin LLM) (VI / SC-010).
- [x] Pasa `T026`.

- [x] T028 [US2] Integrar `explore` en el registro de herramientas y en la selección del agente (registro en `src/qa_agent/tools/__init__.py`)

**Condition of Done (T028)**:
- [x] `explore` está disponible para selección por el agente.
- [x] Una consulta "¿cuál es la estructura?" dispara `explore` y la respuesta usa su resultado real (SC-002/003).

- [x] T029 [US2] Agregar caso de honestidad: si `explore` devuelve ruta inexistente/no accesible, el agente informa la imposibilidad sin inventar contenido (rail de UC-007)

**Condition of Done (T029)**:
- [x] Respuesta comunica que no puede acceder, sin fabricar una estructura (SC-002).

**Checkpoint**: User Story 2 funciona independientemente.

---

## Phase 5: User Story 3 - El agente localiza archivos y componentes (Priority: P2)

**Goal**: Localizar archivos, clases, funciones o componentes devolviendo solo coincidencias reales; informar ausencia sin fabricar (FR-007, FR-008).

**Independent Test**: Se aportan búsquedas con coincidencias reales y se verifica que se reportan solo los resultados hallados; una búsqueda sin coincidencias informa la ausencia.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T030 [P] [US3] Unit test de `locate` en `tests/unit/test_tools_locate.py`: con coincidencias reales y sin coincidencias (FR-007/008, UC-003)

**Condition of Done (T030)**:
- [x] Búsqueda con coincidencias → reporta las reales (SC-003).
- [x] Búsqueda sin coincidencias → devuelve lista vacía y el agente informa ausencia sin fabricar (SC-002).

### Implementation for User Story 3

- [x] T031 [P] Create `src/qa_agent/tools/locate.py`: herramienta `locate` que busca archivos/clases/funciones/componentes por patrón dentro de la `Allowlist` (FR-007/008)

**Condition of Done (T031)** — ver `contracts/tool-contracts.md` (locate):
- [x] Implementa `ejecutar` con esquema de entrada/salida del contrato (`patron`, `ruta`, `tipo`).
- [x] Devuelve solo coincidencias reales (FR-008, SC-003).
- [x] Devuelve lista vacía si no hay coincidencias (sin fabricar) (FR-008).
- [x] Respeta `Allowlist` y es determinística (VI / SC-010).
- [x] Pasa `T030`.

- [x] T032 [US3] Integrar `locate` en el registro de herramientas (selección del agente) en `src/qa_agent/tools/__init__.py`

**Condition of Done (T032)**:
- [x] Una petición de localizar dispara `locate` y la respuesta usa resultados reales.
- [x] La ausencia de coincidencias se comunica como tal (SC-002/003).

- [x] T033 [US3] Cubrir el de comportamiento no deseado de US3 (ausencia de coincidencias → no fabricar) con verificación en `tests/unit/test_tools_locate.py`

**Condition of Done (T033)**: Test que asserting que una búsqueda sin resultados produce mensaje de ausencia y no fabrica coincidencias (SC-002).

**Checkpoint**: User Story 3 funciona independientemente.

---

## Phase 6: User Story 4 - El agente revisa y busca patrones en el código (Priority: P2)

**Goal**: Revisar partes del código y buscar patrones, presentando el contenido tal como existe, sin alterarlo (FR-009, FR-010, FR-011).

**Independent Test**: Se compara el fragmento presentado con el código real del proyecto.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T034 [P] [US4] Unit test de `search` en `tests/unit/test_tools_search.py`: ocurrencias reales con contexto, sin alterar el código (FR-009/010/011, UC-004)

**Condition of Done (T034)**:
- [x] Un patrón presente → muestra ocurrencias reales con su contexto (SC-003).
- [x] El contenido citado coincide con el código real (SC-002/011).
- [x] Patrón ausente → informa ausencia sin inventar (SC-002).

### Implementation for User Story 4

- [x] T035 [P] Create `src/qa_agent/tools/search.py`: herramienta `search` que busca patrones regex en el código dentro de la `Allowlist` y devuelve fragmentos reales en contexto (FR-009/010/011)

**Descripción de la herramienta `search`**:
- **Qué hace**: Busca un patrón de expresión regular en el contenido de los archivos del proyecto y devuelve las ocurrencias con su contexto (líneas antes/después). Presenta el código tal como existe, sin alterarlo.
- **Entradas esperadas**:
  - `patron_regex` (string): Expresión regular a buscar en el código
  - `ruta` (string): Raíz del proyecto donde buscar (debe estar dentro de la Allowlist)
  - `contexto_lineas` (integer, 0-20): Número de líneas de contexto antes y después de cada coincidencia
- **Salida**: Array de ocurrencias con `ruta_relativa`, `linea` (número de línea) y `contexto` (fragmento de código con contexto)

**Condition of Done (T035)** — ver `contracts/tool-contracts.md` (search):
- [x] Implementa `ejecutar` con esquema del contrato (`patron_regex`, `ruta`, `contexto_lineas`).
- [x] Devuelve el código tal como existe, sin alterarlo (FR-011).
- [x] Es determinística (VI / SC-010) y respeta la `Allowlist` (FR-025).
- [x] Pasa `T034`.

- [x] T036 [US4] Integrar `search` en el registro de herramientas (selección del agente) en `src/qa_agent/tools/__init__.py`

**Condition of Done (T036)**:
- [x] Una petición de buscar patrón dispara `search` y la respuesta muestra el código real en contexto.

- [x] T037 [US4] Agregar validación de regex inválido: `search` maneja un patrón regex mal formado con error explícito, sin presentarlo como resultado válido (FR-018, UC-007)

**Condition of Done (T037)**:
- [x] Patrón regex inválido → estado `error`, el agente maneja el fallo explícitamente y no presenta resultado como válido (SC-005).

**Checkpoint**: User Story 4 funciona independientemente.

---

## Phase 7: User Story 5 - El agente ejecuta y analiza pruebas automatizadas (Priority: P2)

**Goal**: Ejecutar pruebas sobre conjuntos autorizados y reportar el estado real; los fallos se explican con causa respaldada por evidencia (FR-012, FR-013, FR-014).

**Independent Test**: Se ejecuta contra un proyecto con pruebas conocidas (pasando y fallando) verificando que el agente reporta el estado real.

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T038 [P] [US5] Unit test de `run_tests` en `tests/unit/test_tools_run_tests.py`: sobre conjunto autorizado y sobre fallo de prueba (FR-012/013/014, UC-005)

**Condition of Done (T038)**:
- [x] Conjunto autorizado → reporta pasadas/falladas/errores reales (SC-002/011).
- [x] Prueba fallida → reporta el fallo explícitamente con el error real (FR-014, SC-005).
- [x] Conjunto/acciones no autorizadas → no ejecuta (SC-011).

### Implementation for User Story 5

- [x] T039 [P] Create `src/qa_agent/tools/run_tests.py`: herramienta `run_tests` que ejecuta el comando de pruebas autorizado (allowlist de comandos seguros, p. ej. `pytest`) sobre el conjunto autorizado y analiza la salida (FR-012/013/014)

**Descripción de la herramienta `run_tests`**:
- **Qué hace**: Ejecuta el comando de pruebas autorizado (p. ej. `pytest`) sobre un conjunto de pruebas autorizado y analiza la salida, reportando el estado real de la ejecución (pasadas, falladas, errores, total). Solo ejecuta comandos de una allowlist de comandos seguros predefinida.
- **Entradas esperadas**:
  - `ruta` (string): Raíz del proyecto donde ejecutar las pruebas
  - `conjunto_autorizado` (boolean): Indica si el conjunto de pruebas está autorizado para ejecución
  - `comando_pruebas` (string): Comando autorizado y acotado (p. ej. `pytest`, `pytest -v`, `pytest --tb=short`)
- **Salida**: Objeto con `pasadas`, `falladas`, `errores`, `total`, `estado_global` (exito/fallo/no_ejecutado), y `detalle_fallos` (array con nombre, mensaje_error, ruta_relativa)

**Condition of Done (T039)** — ver `contracts/tool-contracts.md` (run_tests):
- [x] Implementa `ejecutar` con esquema del contrato (`ruta`, `conjunto_autorizado`, `comando_pruebas`).
- [x] Solo ejecuta sobre conjuntos autorizados (FR-012, FR-025) y con comandos de una allowlist de comandos seguros (FR-025, SC-011, IV).
- [x] Reporta el estado real de la ejecución (FR-013).
- [x] No atribuye causas no respaldadas por la evidencia (FR-014, UC-007).
- [x] Si no puede ejecutarse → `estado_global=no_ejecutado` e informa explícitamente (FR-017/018).
- [x] Pasa `T038`. Determinístico: ejecutar el comando es determinista; solo el análisis de causa puede ser asistido por LLM (VI).

- [x] T040 [US5] Integrar `run_tests` en el registro de herramientas (selección del agente) en `src/qa_agent/tools/__init__.py`

**Condition of Done (T040)**:
- [x] Una petición de ejecutar pruebas dispara `run_tests` y la respuesta reporta el estado real (SC-002).

- [x] T041 [US5] Integrar mínimo privilegio para `run_tests`: verificar que solo operan conjuntos de pruebas autorizados y comandos acotados (FR-025, IV, SC-011)

**Condition of Done (T041)**:
- [x] `run_tests` rechaza comandos fuera de la allowlist de comandos seguros (SC-011).
- [x] No ejecuta comandos peligrosos o no autorizados (FR-025).

**Checkpoint**: User Story 5 funciona independientemente.

---

## Phase 7b: QA/Testing Tools (ampliación del conjunto de herramientas)

**Goal**: Ampliar las capacidades QA/Testing del agente con herramientas para
analizar resultados de pruebas, generar casos de prueba y analizar cobertura.
Cada herramienta respeta el contrato de `tools/base.py` (VII), la `Allowlist`
(FR-025) y el desacople Herramienta vs. Skill (ver D8/D9 en `research.md`).

**Independent Test**: Cada herramienta se prueba de forma independiente sin LLM
(donde aplique) y su contrato se valida contra `contracts/tool-contracts.md`.

### Tests for QA/Testing Tools

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T057 [P] [US8] Unit test de `analyze_test_results` en `tests/unit/test_tools_analyze_results.py`: resumen determinista y causas limitadas a la evidencia (FR-013/014/019, UC-007)

**Condition of Done (T057)**:
- [x] Resumen cuantitativo determinista (pasadas/falladas/errores) (SC-010).
- [x] `posible_causa` se limita a la evidencia o "sin evidencia suficiente" (FR-014).
- [x] No inventa fallos ni causas (FR-019) (SC-002).

- [x] T058 [P] [US9] Unit test de `generate_test_cases` en `tests/unit/test_tools_generate_cases.py`: genera casos sugeridos con fuentes de código real (FR-019, IX)

**Condition of Done (T058)**:
- [x] Los casos propuestos citan al menos una `fuente` de código real del proyecto.
- [x] Con objetivo sin código relevante, comunica falta de evidencia sin inventar (SC-002).
- [x] Con `cripticidad` distinta, produce tipos de caso distintos (happy_path/edge_case/negativo).

- [x] T059 [P] [US10] Unit test de `analyze_coverage` en `tests/unit/test_tools_coverage.py`: cobertura real y estado no_ejecutado ante fallo (FR-017/018/019)

**Condition of Done (T059)**:
- [x] Reporta cobertura global y por archivo reales (SC-002).
- [x] Ante fallo de ejecución → `estado == error/no_ejecutado` e informa explícitamente (SC-005).
- [x] Solo usa comandos de cobertura autorizados (SC-011).

### Implementation for QA/Testing Tools

- [x] T060 [US8] Create `src/qa_agent/tools/analyze_test_results.py`: herramienta `analyze_test_results` que analiza la salida real de `run_tests` (resumen determinista + causas limitadas a evidencia)

**Descripción de la herramienta `analyze_test_results`**:
- **Qué hace**: Analiza los resultados de una ejecución de pruebas (salida de `run_tests`) y genera un resumen cuantitativo determinista agrupando fallos por ruta/archivo, limitando las posibles causas a lo que la evidencia sustenta. No inventa fallos ni causas.
- **Entradas esperadas**:
  - `ruta` (string): Raíz del proyecto
  - `resultado_tests` (object): Resultado de `run_tests` con `pasadas`, `falladas`, `errores`, `detalle_fallos`
- **Salida**: Objeto con `resumen` (string cuantitativo) y `fallos_agrupados` (array con `ruta_relativa`, `error_comun`, `posible_causa` - esta última limitada a evidencia o "sin evidencia suficiente")

**Condition of Done (T060)** — ver `contracts/tool-contracts.md` (analyze_test_results):
- [x] Implementa `ejecutar` con esquema de entrada/salida del contrato.
- [x] El resumen/agrupación es determinista (VI / SC-010); las causas se limitan a la evidencia (FR-014).
- [x] No fabruca fallos ni causas (FR-019); respeta `Allowlist` (FR-025).
- [x] Pasa `T057`.

- [x] T061 [P] [US9] Create `src/qa_agent/tools/generate_test_cases.py`: herramienta `generate_test_cases` que identifica código real relevante (`fuentes`) de forma determinista y delega la redacción de casos al `LLMBackend` (VI)

**Descripción de la herramienta `generate_test_cases`**:
- **Qué hace**: Identifica código real relevante del proyecto (`fuentes`) de forma determinista para un objetivo dado, y delega la redacción de casos de prueba en lenguaje natural al `LLMBackend`. Los casos propuestos citan las fuentes reales consultadas. Si no hay código relevante, comunica falta de evidencia sin inventar.
- **Entradas esperadas**:
  - `ruta` (string): Raíz del proyecto
  - `objetivo` (string): Función, componente o escenario a cubrir con tests
  - `cripticidad` (string, enum): Tipo de casos a generar - `happy_path`, `edge_cases`, `usuarios_no_validos`
- **Salida**: Objeto con `casos_propuestos` (array con `descripcion`, `entrada_esperada`, `resultado_esperado`, `tipo`) y `fuentes` (array de rutas de código real consultado)

**Condition of Done (T061)** — ver `contracts/tool-contracts.md` (generate_test_cases):
- [x] Implementa `ejecutar` con esquema del contrato (`ruta`, `objetivo`, `cripticidad`).
- [x] Identificación de `fuentes` determinista y sin LLM (VI).
- [x] Redacción de casos (natural) delegada a `LLMBackend`; los casos citan `fuentes` reales (FR-019).
- [x] Sin código relevante → comunica falta de evidencia sin inventar (SC-002).
- [x] Pasa `T058`.

- [x] T062 [P] [US10] Create `src/qa_agent/tools/analyze_coverage.py`: herramienta `analyze_coverage` que ejecuta el comando de cobertura autorizado (allowlist) y reporta cobertura real (FR-017/018/019, FR-025)

**Descripción de la herramienta `analyze_coverage`**:
- **Qué hace**: Ejecuta un comando de cobertura autorizado (p. ej. `pytest --cov=src`) y reporta la cobertura real global y por archivo, incluyendo líneas faltantes. Solo usa comandos de una allowlist predefinida. Si no puede ejecutarse, reporta estado explícito (error/no_ejecutado).
- **Entradas esperadas**:
  - `ruta` (string): Raíz del proyecto
  - `comando_cobertura` (string): Comando autorizado y acotado (p. ej. `pytest --cov=src`, `pytest --cov=src --cov-report=term-missing`)
- **Salida**: Objeto con `cobertura_global` (number 0-100), `por_archivo` (array con `ruta_relativa`, `cobertura`, `lineas_faltantes`), y `estado` (exito/error/no_ejecutado)

**Condition of Done (T062)** — ver `contracts/tool-contracts.md` (analyze_coverage):
- [x] Implementa `ejecutar` con esquema del contrato (`ruta`, `comando_cobertura`).
- [x] Solo ejecuta comandos de cobertura autorizados (FR-025, SC-011).
- [x] Reporta cobertura real (FR-019); ante fallo → estado explícito (FR-017/018).
- [x] Determinística (VI / SC-010). Pasa `T059`.

- [x] T063 [P] [Ampliación QA] Registrar las 3 herramientas QA/Testing en `src/qa_agent/tools/__init__.py` y verificar selección por el agente (II)

**Condition of Done (T063)**:
- [x] `analyze_test_results`, `generate_test_cases`, `analyze_coverage` están disponibles para selección.
- [x] El registro no rompe el contrato ni la estabilidad de las herramientas existentes (II).
- [x] Las Skills (SKILL.md) NO se cargan desde el código de herramientas (desacople D9).

- [x] T064 [Ampliación QA] Integrar las herramientas QA/Testing en el flujo de agente: nuevas solicitudes disparan la herramienta correcta y la respuesta usa su resultado real (FR-003/004), incluida la redacción de secretos (FR-021)

**Condition of Done (T064)**:
- [x] "analiza estos resultados de prueba" → `analyze_test_results`.
- [x] "genera casos de prueba para X" → `generate_test_cases`.
- [x] "analiza la cobertura" → `analyze_coverage`.
- [x] Las salidas pasan por `Redactor` en respuesta/historial (SC-008).

**Checkpoint**: QA/Testing tools integradas y funcionales de forma independiente.

---

## Phase 7c: Skills de QA/Testing (SKILL.md)

**Goal**: Definir Skills estilo Anthropic/SpecKit (archivos `SKILL.md`) que
documentan **metodologías, criterios y procedimientos** para orientar al agente
sobre cómo usar sus herramientas QA/Testing, **desacopladas** de la
implementación (principio I, D9 en `research.md`).

**Independent Test**: Cada `SKILL.md` es legible y autocontenido; no contiene
implementación de herramientas y sus procedimientos son verificables por
revisión.

### Implementation for Skills QA/Testing

- [x] T065 [P] [US9] Create `.github/skills/qa-test-cases/SKILL.md`: metodología para generar casos de prueba usando `generate_test_cases` (cuándo usarla, criterios de entrada, criterios de aceptación de casos)

**Condition of Done (T065)**:
- [x] `SKILL.md` tiene front-matter yml (`name`, `description`, `metadata`).
- [x] Define: cuándo activar, cómo secuenciar con otras herramientas, criterios de aceptación de los casos.
- [x] **NO contiene** el código/implementación de `generate_test_cases` (desacople D9).
- [x] Está en `.github/skills/qa-test-cases/SKILL.md`.

- [x] T066 [P] [US10] Create `.github/skills/qa-coverage/SKILL.md`: metodología para analizar cobertura usando `analyze_coverage` (interpretación, umbrales, cómo reportar líneas faltantes)

**Condition of Done (T066)**:
- [x] Define metodología y criterios de interpretación de `CoverageReport`.
- [x] **NO contiene** la implementación de `analyze_coverage`.
- [x] En `.github/skills/qa-coverage/SKILL.md`.

- [x] T067 [P] [US8] Create `.github/skills/qa-test-analysis/SKILL.md`: metodología para analizar resultados de pruebas usando `analyze_test_results` y `run_tests` (secuencia esperada, delimitación de causas a la evidencia)

**Condition of Done (T067)**:
- [x] Documenta la secuencia esperada run_tests → analyze_test_results.
- [x] Enfatiza delimitación de causas a la evidencia (FR-014, IX, UC-007).
- [x] **NO contiene** la implementación de las herramientas.
- [x] En `.github/skills/qa-test-analysis/SKILL.md`.

- [x] T068 [P] [Ampliación QA] Create `.github/skills/qa-testing/README.md` o índice: catálogo de Skills de QA/Testing con enlaces y propósito de cada una

**Condition of Done (T068)**:
- [x] Índice que enlaza las skills QA/Testing.
- [x] Documenta la separación Herramienta (ejecución) vs. Skill (procedimiento).

- [x] T069 [Ampliación QA] Verificar que las Skills no se acoplan al código: revisión de que ningún módulo de `src/qa_agent/tools/` importa desde `.github/skills/` (desacople D9, principio I)

**Condition of Done (T069)**:
- [x] `git grep` confirma que las herramientas no referencian `.github/skills/`.
- [x] Las Skills son cargadas por el cliente de IA (opencode/copilot) y no por el código del agente.

**Checkpoint**: Skills de QA/Testing documentadas y desacopladas de las herramientas.

---

## Phase 8: User Story 6 - El agente gestiona operaciones con autorización (human-in-the-loop) (Priority: P3)

**Goal**: Las acciones que puedan modificar/eliminar/afectar información requieren autorización explícita; se suspenden hasta confirmación y no se ejecutan si se deniegan (FR-015, FR-016).

**Independent Test**: Se solicita una acción destructiva y se verifica que el agente se detiene hasta recibir confirmación; la denegación evita la ejecución.

### Tests for User Story 6

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T042 [P] [US6] Unit test de autorización en `tests/unit/test_authorization.py`: acción sensible se suspende, autorización → ejecuta, denegación → no ejecuta (FR-015/016, UC-006)

**Condition of Done (T042)**:
- [x] Acción sensible pendiente → no se ejecuta (FR-016, SC-004).
- [x] Autorizada → se ejecuta (SC-004).
- [x] Denegada → no se ejecuta y se notifica (FR-016).
- [x] Todas las transiciones del state-machine de `AccionSensible` (data-model.md) están cubiertas.

### Implementation for User Story 6

- [x] T043 [US6] Implementar gestor de autorización completo en `src/qa_agent/security/authorization.py` (si T007 fue parcial) o refinar transiciones y notificación (FR-015/016)

**Condition of Done (T043)**:
- [x] El gestor suspende la ejecución mientras `pendiente`.
- [x] Solicita autorización explícita antes de cualquier acción sensible (FR-015).
- [x] Notifica al usuario el resultado de autorización/denegación (FR-016).
- [x] La autonomía del agente nunca supera las políticas de seguridad (V).

- [x] T044 [US6] Integrar la política human-in-the-loop sobre `run_tests`/acciones sensibles y exponer el mecanismo de autorización al usuario en la CLI

**Condition of Done (T044)**:
- [x] La CLI muestra una solicitud de confirmación legible y captura la decisión del usuario (sí/no).
- [x] La acción no se ejecuta hasta confirmación positiva (SC-004).

**Checkpoint**: User Story 6 funciona (transversal).

---

## Phase 9: User Story 7 - El agente informa límites y evita inventar información (Priority: P3)

**Goal**: El agente reconoce falta de información, maneja errores de herramientas explícitamente, no inventa resultados y filtra secretos (FR-017, FR-018, FR-019, FR-021, FR-022, FR-023).

**Independent Test**: Ante preguntas sin respuesta disponible y errores de herramienta, el agente no fabrica datos; ante una herramienta no adecuada informa y sugiere ajustes.

### Tests for User Story 7

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T045 [P] [US7] Unit test de honestidad/límites en `tests/unit/test_honesty.py`: con FakeLLM que devuelve "ninguna herramienta" y con resultados inválidos (FR-017/018/022/023, UC-007)

**Condition of Done (T045)**:
- [x] Sin información disponible → comunica falta de confianza, no inventa (SC-002).
- [x] Resultado inválido/error de herramienta → lo maneja explícitamente y no lo presenta como válido (SC-005).
- [x] Ninguna herramienta adecuada → notifica + sugiere ajuste, sin forzar ejecución (SC-009).
- [x] No se ejecuta herramienta forzada cuando ninguna es adecuada (FR-023).

- [x] T046 [P] [US7] Unit test de redactor en `tests/unit/test_redactor.py`: detecta y oculta secretos en strings y dicts (FR-021, SC-008, XI)

**Condition of Done (T046)**:
- [x] Tokens/api_keys detectados y sustituidos por `***` en strings y estructuras anidadas.
- [x] No descarta texto legítimo sin secretos (sin falsos positivos en código normal).
- [x] Verifica que secretos no aparecen en respuesta/historial/logs (SC-008).

### Implementation for User Story 7

- [x] T047 [US7] Implementar el manejo de "ninguna herramienta adecuada" y la sugerencia de ajuste en `src/qa_agent/agent/loop.py` (si no completo en T021) (FR-022/023)

**Condition of Done (T047)**:
- [x] La respuesta informa que no puede atender la solicitud con las herramientas disponibles.
- [x] Sugiere ajustes a la solicitud (FR-022).
- [x] No se ejecuta ni inventa una ejecución (FR-023, SC-009).

- [x] T048 [US7] Implementar manejo explícito de errores/invalid de resultados en el loop y en `validar_resultado`: nunca presentar un resultado inválido como válido (FR-018, VII)

**Condition of Done (T048)**:
- [x] Un resultado `error`/inválido no se usa como fuente de verdad (FR-018, SC-005).
- [x] El agente comunica el error explícitamente.

- [x] T049 [US7] Asegurar regla transversal de no-invención en todas las herramientas y en el loop (FR-019, SC-002): ninguna herramienta fabrica archivos/coincidencias/resultados

**Condition of Done (T049)**:
- [x] Revisión de código confirma que ninguna herramienta fabrica datos.
- [x] Test de humo: preguntas fuera de alcance no producen datos inventados (SC-002).

**Checkpoint**: User Story 7 funciona (transversal). Todas las user stories implementadas.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T050 [P] Run quickstart.md validation end-to-end contra `tests/fixtures/proyecto_ejemplo` (los 7 escenarios de `quickstart.md`) y documentar resultados

**Condition of Done (T050)**:
- [x] Los 7 escenarios de `quickstart.md` pasan de extremo a extremo.
- [x] Se registran los resultados en el README o un documento de verificación.

- [x] T051 [P] Añadir pruebas de determinismo en `tests/unit/test_determinism.py`: operaciones sin LLM (explore/locate/search/run_tests) producen resultados idénticos ante la misma entrada/estado (FR-024, SC-010, VI)

**Condition of Done (T051)**:
- [x] explore/locate/search (y análisis de run_tests sin LLM) devuelven el mismo resultado en dos ejecuciones con misma entrada (SC-010).
- [x] Verifica que el LLM no interviene en operaciones determinísticas (VI).

- [x] T052 [P] Verificación de cobertura de requisitos: toda respuesta cumple SC-001..SC-014; mapear cada FR (FR-001..FR-031) a su implementación/test y documentar traza en `docs/` o `tasks.md`

**Condition of Done (T052)**:
- [x] Cada FR-001..FR-031 está mapeado a al menos una tarea/implementación.
- [x] Cada SC-001..SC-014 verificado por al menos un test.
- [x] No queda ningún requerimiento funcional ni no funcional sin su correspondiente task/implementación.

- [x] T053 [P] Verificación de mínimo privilegio y seguridad en todas las herramientas (rutas allowlist, comandos acotados, sin comandos peligrosos) (FR-025, IV, SC-011)

**Condition of Done (T053)**:
- [x] Ninguna herramienta ejecuta comandos arbitrarios del usuario.
- [x] Todas las operaciones se ejecutan con el mínimo privilegio necesario (SC-011).

- [x] T054 [P] Verificación final de no-fuga de secretos: escaneo de código, logs y `git grep` de patrones de secretos, y confirmar `.env` en `.gitignore` (FR-021, XI, SC-008)

**Condition of Done (T054)**:
- [x] `git grep -I -n -E "sk-|api[_-]?key|bearer"` (buscando secretos literales) no arroja secretos reales en el código.
- [x] `.env` no está versionado (en `.gitignore`).
- [x] Los tests de redactor pasan (T046).

- [x] T055 [P] Documentación de uso global (Opción 1) en `README.md`: comando `qa-agent --ruta <proyecto>` instalado con `pip install .` / `pipx install .` (alimentado desde plan.md y quickstart.md)

**Condition of Done (T055)**:
- [x] `README.md` documenta cómo instalar globalmente y usar `qa-agent` sobre cualquier proyecto.
- [x] Documenta `--ruta`, `--pregunta`, `--demo`.
- [x] La documentación está alineada con la implementación (constitución XIII).

- [x] T056 Run full suite: `pytest -q` en verde sin errores ni warnings, y `qa-agent --version` OK; validación final de la Constitution Check post-implementación

**Condition of Done (T056)**:
- [x] `pytest -q` pasa al 100%.
- [x] `qa-agent --version` responde correctamente.
- [x] Se registra la conformidad con la constitución (XIV - spec-driven, revisión de cumplimiento).

---

## Phase 11: Ampliación multi-lenguaje (dotnet/maven/gradle) y robustez LLM

**Purpose**: Ampliar `run_tests`/`analyze_coverage` a proyectos C#/.NET y Java
(detectando el runner por marcador), y endurecer el backend LLM ante respuestas
no-JSON de proveedores reales (NVIDIA NIM / nemotron). Alcance adicional a la
spec 001 (constitución XII: evolución incremental) documentado antes de
implementarse.

- [x] T070 Ampliar la allowlist de `run_tests` y sus parsers a runners multi-lenguaje: `dotnet test`, `mvn test`, `gradle test` (variantes fijas sin argumentos libres) con parsing de salida real VSTest/Surefire/Gradle (FR-012/013, FR-025, SC-011)

**Condition of Done (T070)**:
- [x] `dotnet test`, `mvn test`, `gradle test` (y variantes fijas documentadas) están en `_COMANDOS_PERMITIDOS` (`tools/run_tests.py`).
- [x] `_parsear_salida` despacha el parser según el runner: VSTest (`Passed!/Failed! - Failed: X, Passed: Y, Total: Z` + fallos por test con `Error Message`), Surefire (`Tests run: N, Failures: M` + fallos `[ERROR] Clase.test:línea`), Gradle (`N tests completed` + fallos `Clase > test FAILED`).
- [x] Los fallos se reportan con nombre/mensaje reales (FR-014, SC-002); variantes libres (ej. `dotnet test -c Release`) siguen rechazadas (SC-011).
- [x] Tests en `tests/unit/test_tools_run_tests.py` (dotnet/maven/gradle OK y fallo con detalle).

- [x] T071 Ampliar la allowlist de `analyze_coverage` y añadir parsers de informes XML: `dotnet test --collect:"XPlat Code Coverage"` (Cobertura XML) y `mvn test jacoco:report` (JaCoCo XML), con fallback al formato terminal pytest-cov (FR-017/018/019, FR-025, SC-011, SC-014)

**Condition of Done (T071)**:
- [x] Comandos de cobertura multi-lenguaje en `_COMANDOS_COBERTURA_PERMITIDOS` (`tools/analyze_coverage.py`).
- [x] `_parsear_salida` localiza el informe generado en la salida (Cobertura `coverage.cobertura.xml` / JaCoCo `jacoco.xml`) y lo parsea (cobertura global y por archivo, líneas faltantes).
- [x] JaCoCo usa el contador LINE directo de `report`/`class` (no el de `<method>`); cobertura real, nunca inventada.
- [x] Variantes libres rechazadas (SC-011); fallo de parseo → `estado: error` explícito (FR-017/018).
- [x] Tests en `tests/unit/test_tools_coverage.py` (Cobertura XML y JaCoCo XML).

- [x] T072 Detección determinista del runner por marcador del proyecto en `agent/loop.py`: `_detectar_comando_pruebas`/`_detectar_comando_cobertura` eligen el comando según `*.csproj`/`*.sln`/`pom.xml`/`build.gradle` (dotnet/mvn/gradle) o pytest por defecto; `_parametros_para` usa el comando detectado (VI, SC-010)

**Condition of Done (T072)**:
- [x] Marcadores: `*.csproj`/`*.sln`/`*.fsproj`/`*.vbproj` → dotnet; `pom.xml` → maven; `build.gradle`/`settings.gradle` → gradle; sin marcador → pytest.
- [x] `_parametros_para` de `run_tests`/`analyze_coverage` usa el comando detectado (mismo proyecto → mismo comando, VI/SC-010).
- [x] `_resultado_de_pruebas` (encadenado por `analyze_test_results`) usa también el comando detectado.
- [x] Tests en `tests/unit/test_deteccion_runner.py`.

- [x] T073 Robustez del backend LLM ante respuestas no-JSON: `_extraer_json` en `openai_compatible_backend.py` extrae el primer objeto JSON balanceado (tolera prosa, bloques markdown, negativas) y devuelve `{}` en vez de `JSONDecodeError` (FR-017/018, IX)

**Condition of Done (T073)**:
- [x] `_completar_json` nunca lanza `JSONDecodeError`: usa `json.JSONDecoder().raw_decode` desde el primer `{` y devuelve `{}` si no hay JSON válido.
- [x] Cubre: JSON puro, prosa alrededor, bloque ```json```, solo prosa, contenido vacío y llaves no válidas.
- [x] El `Agent` ya trata `{}` como respuesta sin herramienta / sin evidencia (FR-022/023, FR-017) — sin regresión.
- [x] Tests en `tests/unit/test_llm_backend_json.py`.

- [x] T074 Suite completa en verde con la ampliación multi-lenguaje y la robustez LLM; trazabilidad FR/SC actualizada en `docs/trazabilidad.md`

**Condition of Done (T074)**:
- [x] `pytest -q` pasa al 100% (140 tests).
- [x] `docs/trazabilidad.md` refleja la ampliación (FR-025+, parsers dotnet/mvn/gradle, Cobertura/JaCoCo XML).

- [x] T075 Modo recomendación: el agente puede proponer recomendaciones claramente etiquetadas (p. ej. estrategia de pruebas) basadas en la evidencia real observada (estructura, framework, ausencia de tests), sin afirmar hechos inventados (FR-019 / IX); `RespuestaDelAgente.recomendaciones`, prompt de `generar_respuesta`, redacción de recomendaciones y renderizado en CLI

**Condition of Done (T075)**:
- [x] `RespuestaDelAgente` incluye `recomendaciones: list[str]` (opcional, vacía por defecto).
- [x] `generar_respuesta` del backend instruye al LLM a devolver `recomendaciones` etiquetadas como tales cuando la evidencia no responde directamente (FR-019) — nunca como hechos del proyecto.
- [x] El `Agent` propaga las recomendaciones redactadas antes de exponerlas (SC-008).
- [x] El CLI muestra las recomendaciones en un panel etiquetado "Recomendaciones".
- [x] Tener recomendaciones no eleva la confianza (siguen siendo sugerencias, confianza `limitada`/`sin_informacion`).
- [x] Tests en `tests/unit/test_recomendaciones.py` (propagación, redacción, confianza, backend con/sin recomendaciones).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories (MVP core loop)
- **User Story 2 (P1)**: Can start after Foundational - Independent (adds `explore` tool)
- **User Story 3 (P2)**: Can start after Foundational - Independent (adds `locate` tool)
- **User Story 4 (P2)**: Can start after Foundational - Independent (adds `search` tool)
- **User Story 5 (P2)**: Can start after Foundational - Independent (adds `run_tests` tool)
- **User Story 6 (P3)**: Transversal - Its authorization mechanism is integrated into loop (T022) and refined here
- **User Story 7 (P3)**: Transversal - Honesty/redaction rules apply to all; core parts built in US1 (T023) and completed here

> **Nota de órden**: US6 y US7 son transversales. Sus fundamentos (autorización en T007/T022/T043, redacción en T008/T023/T046/T049) se construyen de forma incremental dentro de las fases anteriores y se completan en sus fases propias.

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Models/base contratos before services
- Tool contract (`tools/*.py`) before integration in `tools/__init__.py`
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] (T002-T004) can run in parallel after T001
- All Foundational tasks marked [P] (T005-T012, T017) can run in parallel (within Phase 2)
- Once Foundational completes, all user stories can start in parallel (if team capacity allows)
- Tools (explore/locate/search/run_tests) are independent and can be built in parallel
- Tests for a user story marked [P] can run in parallel
- Polish tasks T050-T055 marked [P] can run in parallel; T056 depends on them

---

## Parallel Example

```bash
# Phase 2 paralelo: infraestructura sin dependencias entre sí
Task: "T005 [P] Create tools/base.py"
Task: "T007 [P] Create security/authorization.py"
Task: "T008 [P] Create security/redactor.py"
Task: "T010 [P] Create llm/backend.py"

# Herramientas (US2-US5) en paralelo tras Phase 2
Task: "T027 Create tools/explore.py"   # US2
Task: "T031 Create tools/locate.py"    # US3
Task: "T035 Create tools/search.py"    # US4
Task: "T039 Create tools/run_tests.py" # US5
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready (CLI funcional con bucle agente + historial, autorización y redacción)

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 (explore) → Test → Demo
4. Add User Story 3 (locate) → Test → Demo
5. Add User Story 4 (search) → Test → Demo
6. Add User Story 5 (run_tests) → Test → Demo
7. Add US6 (autorización plena) y US7 (honestidad/redacción) → Test → Demo
8. Polish & Cross-cutting (T050-T056) → entrega final
9. Cada story añade valor sin romper las anteriores

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (loop core)
   - Developer B: User Story 2 (explore) / User Story 3 (locate)
   - Developer C: User Story 4 (search) / User Story 5 (run_tests)
3. Stories complete and integrate independently
4. US6/US7 completed by whoever integrates authorization/redaction in the loop

---

## Phase 12: Bucle de razonamiento-acción (Agente, no ChatBot)

**Purpose**: Convertir el flujo de una sola pasada en un agente que percibe,
piensa un plan multi-paso, actúa, observa, reflexiona y decide (ReAct). Diseño:
`agent-reasoning-loop.md`. Decisiones del usuario: **autonomía guiada** (las
acciones sensibles siguen requiriendo autorización, SC-004) y **razonamiento
visible por pasos** (FR-035 / SC-015). TDD obligatorio (rojo → verde).

- [x] T076 [US-11] Crear los modelos de razonamiento en `src/qa_agent/agent/reasoning.py`: `Intencion`, `PasoDePlan`, `Plan`, `Observacion`, `EstadoDelAgente` (dataclasses con `pasos_max`, presupuesto opcional), según `data-model.md` §Entidades de razonamiento-acción

**Condition of Done (T076)**:
- [x] Dataclasses `Intencion`, `PasoDePlan`, `Plan`, `Observacion`, `EstadoDelAgente` importables sin LLM (III / SC-006).
- [x] `EstadoDelAgente` mantiene `pasos_ejecutados` y respeta `pasos_max`.
- [x] Tests unitarios de los modelos en `tests/unit/test_reasoning.py`.

- [x] T077 [US-11] Ampliar el contrato LLM con `planificar`, `razonar`, `evaluar`, `responder` en `src/qa_agent/llm/backend.py` y `openai_compatible_backend.py`, y extender `FakeLLM` (determinista, SC-010) para estos métodos en `tests/unit/test_reasoning.py`

**Condition of Done (T077)**:
- [x] `LLMBackend` declara `planificar(intencion, catalogo, contexto) -> Plan`, `razonar(estado) -> PasoDePlan | {"concluir": True}`, `evaluar(estado) -> {"satisfecha": bool, "razon": str}`, `responder(evidencia) -> dict` (con `recomendaciones` opcionales).
- [x] `OpenAICompatibleBackend` implementa cada método con JSON validado (`_extraer_json`) y el sistema prompt de honestidad (FR-019): el plan solo usa herramientas reales del catálogo y rutas permitidas.
- [x] `FakeLLM` soporta los 4 métodos con respuestas configurables (sin red).
- [x] Tests: `planificar` usa solo herramientas del catálogo; `razonar` puede concluir; `evaluar` distingue satisfecha/no; `responder` respeta el contrato.

- [x] T078 [US-11] Reescritura de `Agent.atender` como bucle ReAct en `src/qa_agent/agent/loop.py`: percibir → pensar (plan) → actuar (paso + parámetros validados) → observar (resultado real) → reflexionar (evaluar) → decidir (iterar/concluir), manteniendo autorización (SC-004), allowlist (FR-025) y redacción (SC-008)

**Condition of Done (T078)**:
- [x] `atender` ejecuta el plan multi-paso (no una sola herramienta) cuando la intención lo requiere.
- [x] Cada observación es un resultado REAL de herramienta registrado en el historial (FR-020), nunca fabricado (FR-019).
- [x] La respuesta final se basa en la evidencia acumulada; `RespuestaDelAgente` expone `razonamiento` (pasos+observaciones).
- [x] La suite completa sigue verde (las herramientas no cambian su contrato).

- [x] T079 [US-11] Validación de parámetros propuestos por el LLM: `Agent` rechaza parámetros fuera del esquema de la herramienta o de la allowlist antes de ejecutar (FR-033 / FR-025), notificando sin ejecutar

**Condition of Done (T079)**:
- [x] Parámetros propuestos se validan contra `esquema_entrada` (pydantic/JSON Schema).
- [x] `ruta` fuera de la allowlist → rechazo y notificación (FR-025), sin ejecución. La ruta autorizada se inyecta si el LLM propone un parámetro distinto (`ruta_base`) o escapa dobles backslashes (Windows).
- [x] Test: FakeLLM propone parámetro inválido/fuera de ruta → no se ejecuta y se informa.

- [x] T080 [US-11] Re-planificación ante autorización denegada: si un paso sensible es denegado, el agente elige un paso alternativo no sensible o informa la imposibilidad (FR-036)

**Condition of Done (T080)**:
- [x] Denegación de `run_tests`/`analyze_coverage` no aborta toda la solicitud: el agente re-planifica.
- [x] Si no hay alternativa no sensible, responde con lo obtenido + confianza `limitada` + recomendaciones.
- [x] Test en `tests/unit/test_reasoning.py` con `autorizacion=False`.

- [x] T081 [US-11] Límite de parada `pasos_max` (default 5): el agente no excede el máximo y ante agotamiento responde con la evidencia acumulada y confianza `limitada`/`sin_informacion` (SC-016)

**Condition of Done (T081)**:
- [x] Con FakeLLM que siempre pide más pasos, el bucle termina en `pasos_max` sin bucle infinito.
- [x] La respuesta degradada explica por qué no pudo satisfacer y muestra la evidencia obtenida.
- [x] Test: cuenta de pasos = `pasos_max` y respuesta con confianza `limitada`.

- [x] T082 [US-11] Visibilidad del razonamiento: historial visible con columna "razón" (por qué se ejecuta cada paso) y CLI que renderiza los pasos antes de la respuesta final (FR-035 / SC-015)

**Condition of Done (T082)**:
- [x] `RegistroDeAccion` expone la `razon` de cada paso en el historial visible (FR-020 ampliado).
- [x] `cli/main.py` muestra: intención percibida → plan → pasos (razón+herramienta+parámetros+observación) → respuesta final.
- [x] El razonamiento pasa por el `Redactor` antes de mostrarse (SC-008).
- [x] Tests de renderizado en `tests/unit/test_reasoning.py`.

- [x] T083 [US-11] Honestidad del razonamiento: toda afirmación de la respuesta final se ancla en una observación real registrada; FakeLLM que intenta inventar no produce afirmaciones no ancladas (SC-017 / FR-019)

**Condition of Done (T083)**:
- [x] Test: FakeLLM con `responder` que fabrica datos → la respuesta final no contiene datos sin observación previa (confianza degradada a `limitada`).
- [x] El agente distingue evidencia real de inferencia/recomendación (estas quedan en `recomendaciones`, no en `texto`).
- [x] `docs/trazabilidad.md` añade filas FR-032..036 y SC-015..017.

- [x] T084 [US-11] Caso de uso de demostración: "¿cuáles clases son las más importantes de probar?" ejecuta un plan multi-paso real (explorar → localizar → buscar definiciones → priorizar) y actualiza `docs/use-cases/UC-010.md`

**Condition of Done (T084)**:
- [x] Con el proyecto real (`--ruta`), la pregunta de demostración produce varias observaciones reales y una respuesta priorizada anclada en ellas.
- [x] `docs/use-cases/UC-010.md` documenta el flujo percibir→pensar→actuar con su ejemplo y la ejecución real.
- [x] Suite completa verde (146 + tests de Phase 12).

---

## Phase 13: Agente Conversacional con Memoria y Tareas (Chat Agent)

**Purpose**: Convertir el agente single-shot en un agente conversacional persistente que:
- Mantiene historial de conversación entre turnos (contexto, referencias, decisiones)
- Permite asignar y rastrear tareas con estado (pendiente/en_progreso/completada)
- Persiste sesiones a disco (guardar/cargar) y permite reanudar
- Responde en modo chat natural, no solo análisis QA puntual

Decisiones de diseño:
- **Memoria a corto plazo**: historial de la sesión actual (últimos N turnos + resumen)
- **Memoria a largo plazo**: base de datos/archivos de sesiones previas, hechos aprendidos
- **Gestión de tareas**: lista de tareas con estado, prioridad, asignación, dependencias
- **Interfaz**: CLI interactivo tipo chat + API para integración
- **Compatibilidad**: el bucle ReAct (Phase 12) sigue disponible para análisis QA profundos como "herramienta" del agente conversacional

### Tareas Phase 13

- [x] T085 [US-12] Modelo de conversación: `Conversacion` (turnos, resumen, hechos), `Turno` (usuario, agente, timestamp, herramienta usada), `Memoria` (hechos persistentes, preferencias)
- [x] T086 [US-12] Persistencia de sesión: `SesionManager` guarda/carga `Conversacion` a JSON/BD (archivo por sesión, opción de BD SQLite), con `guardar()`, `cargar(id)`, `listar()`
- [x] T087 [US-12] Gestión de tareas: `GestorTareas` con CRUD (crear, listar, actualizar estado, asignar, prioridad, etiquetas), persistencia ligada a la sesión
- [x] T088 [US-12] Contexto conversacional en el bucle: `AgentConversacional` que inyecta historial reciente + resumen + tareas pendientes en `Intencion.contexto` antes de `planificar`, y actualiza memoria tras cada turno
- [x] T089 [US-12] CLI interactivo tipo chat: REPL con prompt `> `, comandos `/tarea`, `/sesion`, `/memoria`, `/ayuda`, renderizado bonito de respuestas y razonamiento (reutiliza `_renderizar_respuesta`)
- [x] T090 [US-12] Integración Phase 12: el agente conversacional usa el `Agent` ReAct como "herramienta analítica" cuando la intención es análisis QA (delegación), y responde directo para conversación general
- [x] T091 [US-12] Tests: conversación multi-turno con FakeLLM, persistencia/carga de sesión, tareas CRUD, contexto inyectado en planificación
- [x] T092 [US-12] Docs: actualizar `agent-reasoning-loop.md` con sección "Modo Conversacional", nuevo `use-cases/UC-011.md` (chat con tareas), `data-model.md` añadir entidades `Conversacion`, `Turno`, `Memoria`, `TareaAgente`
- [x] T093 [US-12] Ejecución de tareas: `/tarea run <id>` convierte la tarea en una `Intencion` QA, la delega al bucle ReAct, marca `completada` (con evidencia) o `bloqueada` (sin evidencia) y guarda el resultado en `TareaAgente.resultado` (persistido con la sesión)
- [x] T094 [US-12] Calidad de salida del ReAct para análisis de estructura: `explore` excluye directorios de ruido (`.git`, `.vs`, `bin`, `obj`, `packages`, `node_modules`) en cualquier nivel; `_acotar` del backend conserva cabecera y cola (no solo el inicio, que mostraba únicamente `.git`); el render CLI acota las salidas de herramientas en razonamiento e historial (`_acotar_render`). Verificado con LLM real: "analiza la estructura del proyecto" resume las capas reales sin volcar ruido.

---

## Phase 14: Acciones Destructivas (Modificación del Proyecto)

**Purpose**: Permitir al agente **crear, editar y eliminar archivos** del
proyecto de forma segura, con autorización explícita (human-in-the-loop),
respaldo del estado previo (backup) y verificación del resultado real.

Alcance documentado en `spec.md` v1.2 (US-13, FR-042..FR-047, SC-021..SC-024),
`plan.md` §Phase 14 y `docs/use-cases/UC-012.md`. Implementada (T095-T103).

Decisiones de diseño:
- Tres herramientas deterministas de escritura con contrato: `crear_archivo`,
  `editar_archivo`, `eliminar_archivo`.
- `requiere_autorizacion=True` en las tres (SC-004 / FR-015-016).
- Solo dentro de la `Allowlist` (FR-025 / SC-011); conflictos y rutas fuera →
  rechazo sin modificar nada.
- Backup previo del estado original en `.qa-backup/` (FR-045).
- Verificación posterior con evidencia real (FR-047 / FR-019).
- Enrutamiento determinista ampliado en `agent/router.py` y catálogo en
  `config.construir_herramientas` / `loop._parametros_para`.
- Chat: la autorización human-in-the-loop se gestiona también en modo chat
  (`_procesar_mensaje_chat` re-invoca con la decisión; `AgentConversacional.
  atender` acepta `autorizacion` y no registra el turno mientras queda
  pendiente, SC-004 / UC-006).

### Tareas Phase 14

- [x] T095 [US-13] Contrato base para herramientas de escritura: añadir helpers
  de seguridad en `src/qa_agent/tools/base.py` (resolución de rutas dentro del
  perímetro, rechazo de `..`/path traversal) y soporte para herramientas que
  mutan el filesystem (`requiere_autorizacion=True`). Se añadió
  `resolver_archivo_en_perimetro(ruta_raw, archivo_relativo, allowlist)` que
  valida la raíz y el archivo resuelto y devuelve `(archivo, error)`.

**Condition of Done (T095)**:
- [x] Helpers de resolución de rutas seguras disponibles y testeados
  (`tests/unit/test_tools_crear_archivo.py`, `test_tools_editar_archivo.py`,
  `test_tools_eliminar_archivo.py`).
- [x] El catálogo puede registrar herramientas de escritura con autorización.
- [x] Suite verde con los nuevos tests (TDD).

- [x] T096 [US-13] Herramienta `crear_archivo` (`src/qa_agent/tools/crear_archivo.py`):
  crea un archivo nuevo dentro del perímetro; error explícito si ya existe o la
  ruta queda fuera de la `Allowlist`; `requiere_autorizacion=True`.

**Condition of Done (T096)**:
- [x] Crea el archivo real con el contenido indicado (SC-003/FR-042).
- [x] Rechaza crear un archivo existente o fuera del perímetro sin modificar nada.
- [x] Tests deterministas sin LLM (SC-006/SC-010).

- [x] T097 [US-13] Herramienta `editar_archivo` (`src/qa_agent/tools/editar_archivo.py`):
  reemplaza el contenido de un archivo existente dentro del perímetro; backup
  previo; error explícito si no existe o fuera de la `Allowlist`;
  `requiere_autorizacion=True`.

**Condition of Done (T097)**:
- [x] Modifica el contenido real y respalda el original (FR-043/045).
- [x] Rechaza editar un archivo inexistente o fuera del perímetro sin modificar nada.
- [x] Tests deterministas sin LLM.

- [x] T098 [US-13] Herramienta `eliminar_archivo` (`src/qa_agent/tools/eliminar_archivo.py`):
  elimina un archivo dentro del perímetro; backup previo; error explícito si no
  existe o fuera de la `Allowlist`; `requiere_autorizacion=True`.

**Condition of Done (T098)**:
- [x] Elimina el archivo real y respalda el original (FR-044/045).
- [x] Rechaza eliminar un archivo inexistente o fuera del perímetro sin modificar nada.
- [x] Tests deterministas sin LLM.

- [x] T099 [US-13] `BackupManager` (`src/qa_agent/agent/backup.py`): copia el estado
  original (con timestamp) a `.qa-backup/` dentro del proyecto antes de
  modificar/eliminar, y expone `restaurar()` para revertir.

**Condition of Done (T099)**:
- [x] Backup creado antes de editar/eliminar con nombre que preserva la ruta y fecha
  (`.qa-backup/<marca>__<ruta_relativa>`).
- [x] `restaurar()` repone el contenido original.
- [x] Tests: backup + restauración deterministas (`tests/unit/test_backup.py`).

- [x] T100 [US-13] Enrutamiento y catálogo: ampliar `agent/router.py` (palabras clave
  crear/editar/eliminar/borrar/modificar/quitar + `extraer_contenido`), registrar
  las tres herramientas en `config.construir_herramientas` y en `tools/__init__.py`
  e inyectar `ruta`/`archivo_relativo`/`contenido` en `loop._parametros_para`.

**Condition of Done (T100)**:
- [x] El router determina la herramienta destructiva por palabras clave (FR-024).
- [x] `construir_herramientas` incluye `crear_archivo`, `editar_archivo`, `eliminar_archivo`.
- [x] Tests de enrutamiento y catálogo (`test_router.py`, `test_config_tools.py`).

- [x] T101 [US-13] Integración ReAct: las herramientas destructivas respetan validación
  de esquema, allowlist y autorización en `loop._ejecutar_siguiente_paso`; redacción
  de secretos en respuestas/historial (SC-008); re-planificación ante denegación (FR-036);
  autorización en chat (`_procesar_mensaje_chat` + `AgentConversacional.atender`).

**Condition of Done (T101)**:
- [x] Una operación destructiva pendiente/denegada se suspende/omite sin ejecutarse.
- [x] Rutas fuera del perímetro y parámetros inválidos se rechazan antes de ejecutar.
- [x] Tests del flujo ReAct con `FakeLLM` (autorización, denegación, fuera-de-perímetro)
  en `tests/unit/test_phase14_react.py`.

- [x] T102 [US-13] Verificación posterior: tras crear/editar/eliminar, el agente
  confirma el estado real (explore/locate/search) y reporta evidencia de
  éxito/fracaso en la respuesta (FR-047 / SC-024). La herramienta destructiva
  reporta el resultado real (creado/editado/eliminado + backup); el bucle sigue
  el plan con pasos de verificación (leer_archivo/explore) y la respuesta queda
  anclada en observaciones reales (FR-019).

**Condition of Done (T102)**:
- [x] La respuesta cita el estado real verificado tras la operación (evidencia en
  observaciones, SC-017).
- [x] No se afirma un cambio que no ocurrió (honestidad, FR-019).
- [x] Tests: verificación de éxito y de fracaso (`test_phase14_react.py`).

- [x] T103 [US-13] Tests + Docs: suite TDD completa de Phase 14; actualizar
  `docs/use-cases/UC-012.md` con la ejecución real, `docs/trazabilidad.md`
  (FR-042..FR-047, SC-021..SC-024), `data-model.md` (entidad `Backup`),
  `contracts/tool-contracts.md` (tres contratos) y `AGENTS.md` (tabla).

**Condition of Done (T103)**:
- [x] Suite completa verde (272 tests).
- [x] Trazabilidad actualizada con implementación y tests para cada FR/SC nuevo.
- [x] UC-012 refleja el flujo real verificado.

---

## Phase 15: Profundidad de Análisis (lectura de código)

**Purpose**: Permitir al agente **leer el contenido real de archivos**
(`leer_archivo`) y generar **respuestas profundas** al explicar/entender el
código (qué hace cada capa, qué pruebas la cubren), sin depender de regex
amplios que volcaban millones de caracteres y sin historial ruidoso en el CLI.

Alcance documentado en `spec.md` v1.3 (US-14, FR-048..FR-050, SC-025..SC-026) y
`docs/use-cases/UC-013.md`. Implementado en esta fase (T104-T110).

Decisión de diseño:
- `leer_archivo` es una herramienta de **solo lectura**, determinista, con
  contrato (`esquema_entrada`/`esquema_salida`), validación de la allowlist en
  raíz y archivo resuelto (defensa `..`/symlinks) y `requiere_autorizacion=False`.
- `search` acota su salida con `max_ocurrencias` (default 200) y avisa el
  truncado (`nota`) en vez de volcar todas las coincidencias.
- Los prompts del backend obligan a **leer archivos concretos** cuando la
  intención pide explicar/entender el código, y a responder con profundidad
  organizada por capa/módulo citando contenido real.
- `_afirmaciones_no_ancladas` ignora las palabras capitalizadas al **inicio de
  frase** (falsos positivos que degradaban respuestas profundas válidas).
- El CLI oculta el historial por defecto (`--mostrar-historial` para verlo);
  el panel "Razonamiento" sigue trazando cada paso (FR-035).

### Tareas Phase 15

- [x] T104 [US-14] Herramienta `leer_archivo` (`src/qa_agent/tools/leer_archivo.py`):
  lee el contenido real de un archivo dentro del perímetro (raíz + archivo
  relativo validados contra la `Allowlist`), con límite opcional `max_lineas`
  (1..1000, default 200) y aviso explícito de truncado; archivo inexistente →
  `existe=false` (informa ausencia, no inventa); `requiere_autorizacion=False`.

**Condition of Done (T104)**:
- [x] Contenido real tal cual (FR-011/SC-003), con `archivo`, `existe`,
  `contenido`, `total_lineas`, `truncado`.
- [x] Rechaza rutas fuera de la allowlist y escapes `..`/traversal (FR-025).
- [x] Tests deterministas sin LLM (SC-006/SC-010): contenido, ausencia,
  fuera-de-perímetro, truncado.

- [x] T105 [US-14] Enrutamiento y catálogo: patrones de `leer_archivo` en
  `agent/router.py` (leer/abrir/mostrar contenido de archivo, "analiza el
  archivo X", "qué contiene X") + `extraer_nombre_archivo`; registro en
  `config.construir_herramientas` y `tools/__init__.py`; `ruta` + `archivo_relativo`
  inyectados en `loop._parametros_para`.

**Condition of Done (T105)**:
- [x] El router determina `leer_archivo` por palabras clave (FR-024) y gana a
  `explore` cuando se pide el contenido de un archivo.
- [x] `construir_herramientas` incluye `leer_archivo`.
- [x] Tests de enrutado y de `extraer_nombre_archivo`.

- [x] T106 [US-14] Profundidad en el backend: prompts de `planificar`,
  `responder` y `generar_respuesta` (y `evaluar`) exigen leer los archivos
  relevantes y responder con profundidad organizada por capa/módulo, citando
  contenido real y con `confianza` coherente (FR-049 / SC-026).

**Condition of Done (T106)**:
- [x] Un plan para "explica qué hace cada capa / qué pruebas cubre" incluye
  pasos `leer_archivo` sobre archivos concretos.
- [x] La respuesta detalla contenido real observado en vez de repetir nombres.

- [x] T107 [US-14] Honestidad del razonamiento: `_afirmaciones_no_ancladas` no
  degrada respuestas por palabras capitalizadas al inicio de frase (siguen
  anclándose los números y las palabras en medio de la oración).

**Condition of Done (T107)**:
- [x] Respuesta profunda y anclada mantiene `confianza` ALTA.
- [x] Afirmaciones no ancladas siguen degradando la confianza (SC-017).

- [x] T108 [US-14] `search` acotado: parámetro `max_ocurrencias` (default 200,
  1..10000) corta el volcado y añade `nota` de truncado explícita (FR-019).

**Condition of Done (T108)**:
- [x] Con más coincidencias que el límite devuelve `max_ocurrencias` y `nota`.
- [x] Sin límite explícito no cambia el comportamiento en proyectos normales.

- [x] T109 [US-14] CLI: `_renderizar_respuesta` oculta el historial por defecto
  (`mostrar_historial=False`) y se añade `--mostrar-historial` a `main` y `chat`
  (FR-050 / SC-007); el panel "Razonamiento" sigue trazando cada paso (FR-035).

**Condition of Done (T109)**:
- [x] Sin flag, la salida no contiene la tabla "Historial de acciones".
- [x] Con `--mostrar-historial`, la tabla aparece.

- [x] T110 [US-14] Tests + Docs: suite TDD de Phase 15 (unit + ReAct con
  `leer_archivo`); actualizar `docs/use-cases/UC-013.md`, `docs/trazabilidad.md`
  (FR-048..050, SC-025..026) y `AGENTS.md` (tabla de herramientas y nota CLI).

**Condition of Done (T110)**:
- [x] Suite completa verde (226 tests).
- [x] Trazabilidad actualizada con implementación y tests para cada FR/SC nuevo.
- [x] UC-013 refleja el flujo real verificado y AGENTS.md alineado.

- [x] T111 [US-14] Saneo de `leer_archivo` en el path ReAct: `loop._ejecutar_siguiente_paso`
  deriva `archivo_relativo` desde la solicitud (`extraer_nombre_archivo`) cuando el LLM
  propone un placeholder (p. ej. `{{ruta_relativa_archivo_prueba}}`) o un nombre vacío, y
  rechaza el paso (`archivo_no_identificado`) si no puede resolverse (FR-033/FR-048).
  Evita ejecutar lecturas sin sentido que solo reportaban `existe=false` y enlentecian el
  bucle (regresión observada en sesión real con ReservaHotel).

**Condition of Done (T111)**:
- [x] Un placeholder `{{...}}` se sustituye por el archivo real de la solicitud si existe token.
- [x] Sin archivo identificable, el paso se rechaza sin ejecutar y se registra en el historial.
- [x] Tests deterministas sin LLM (placeholder resuelto / placeholder rechazado).

- [x] T112 [US-14] Fin de la rigidez del bucle ante pasos repetidos (regresión observada
  en sesión real con ReservaHotel: `locate` repetido 4 veces): (a) dedup determinista en
  `loop._ejecutar_siguiente_paso` — un paso idéntico (misma herramienta y mismos
  parámetros) ya ejecutado se omite registrando `paso_repetido` (FR-034, SC-016); (b) el
  prompt de `razonar` (`openai_compatible_backend.razonar`) lista la herramienta por
  observación, prohíbe repetir pasos ejecutados y sugiere `leer_archivo`/cambio de
  estrategia para explicar código o ante búsquedas vacías.

**Condition of Done (T112)**:
- [x] Un paso idéntico ya ejecutado no vuelve a llamar a la herramienta (1 llamada, 1 acción EXITO).
- [x] `razonar` recibe en contexto la herramienta de cada observación y prohíbe repetir pasos.
- [x] Los tests de `pasos_max` usan pasos nuevos por iteración (el límite sigue probándose).

- [x] T113 [US-14] Respuestas de conversación general no repetitivas: el prompt de
  `openai_compatible_backend.responder` (rama sin observaciones) exige responder a la
  pregunta concreta del turno, no repetir la respuesta anterior del asistente ni dar
  plantillas, y enumerar capacidades reales si pregunta "qué puedes hacer" (FR-040/041).
  `_responder_directo` (`conversational.py`) ya inyecta el historial (incluida la respuesta
  previa) en la intención para que el LLM pueda evitarla.

**Condition of Done (T113)**:
- [x] La intención directa del 2º turno incluye la pregunta actual y la respuesta anterior.
- [x] El prompt desaconseja repetir la respuesta previa y pide respuesta específica al turno.

- [x] T114 [US-14] Trazabilidad fiel de lo ejecutado + localización inequívoca (regresión
  observada en sesión real con ReservaHotel): (a) `locate.ruta_relativa` ahora es relativa a
  la raíz de la búsqueda (`BLL\ClienteBL.cs`, no `ClienteBL.cs`); (b) `loop._ejecutar_siguiente_paso`
  solo empareja pasos PENDIENTES del plan (un paso ya ejecutado ya no presta su razón/parámetros
  a un paso nuevo del razonamiento) y la observación guarda los parámetros REALMENTE ejecutados
  (sanearizados y con la ruta autorizada inyectada, FR-035); (c) el dedup de pasos idénticos
  (T112) ignora `ruta` para comparar parámetros y por fin detecta repeticiones reales.

**Condition of Done (T114)**:
- [x] `locate` devuelve `ruta_relativa` con el directorio (test en `test_tools_locate.py`).
- [x] Observación del paso razonado tras agotar el plan muestra los parámetros reales y su razón.
- [x] Dedup efectivo aunque el plan y el razonamiento propongan archivos distintos.

- [x] T115 [US-14] Estructura completa sin truncado: los prompts de `planificar` y `razonar`
  (`openai_compatible_backend`) instruyen explorar por directorio/capa (un `explore` por capa)
  en lugar de un único `explore` gigante de todo el árbol, cuyo listado se trunca en el
  contexto (`_acotar`, 1500 chars) y oculta la mayoría de los archivos (causa raíz de que el
  agente "solo viera la primera clase").

**Condition of Done (T115)**:
- [x] `planificar` y `razonar` recomiendan `explore` por capa para la estructura completa.
- [x] Suite completa verde.

- [x] T116 [US-14] Presupuesto de pasos dinámico (decisión de profundidad aprobada para el
  modelo actual): el límite por defecto de `pasos_max` sube de 5 a 12 (`Agent`,
  `AgentConversacional` y `EstadoDelAgente`) y las intenciones de análisis global (detección
  determinista `_es_analisis_global`, sin LLM) amplían el presupuesto a 18
  (`_PRESUPUESTO_ANALISIS_GLOBAL`) para poder recorrer todas las capas. SC-016 se mantiene:
  sigue siendo un límite duro del bucle.

**Condition of Done (T116)**:
- [x] `Agent`, `AgentConversacional` y `EstadoDelAgente` tienen `pasos_max=12` por defecto.
- [x] `_es_analisis_global` detecta análisis global determinísticamente (tests en
      `test_profundidad_analisis.py`).
- [x] Un análisis global ejecuta más pasos que `pasos_max`; una intención puntual corta en él.

- [x] T117 [US-14] Cobertura determinista del análisis global: `loop._enriquecer_plan_analisis_global`
  enriquece el plan del LLM con pasos que recorren las capas REALES del proyecto (detectadas con
  `explore` de la raíz): un `explore` por capa (su listado completo se trunca en el contexto) y
  `leer_archivo` de los archivos de código principales de cada capa. El LLM planifica, pero la
  cobertura mínima la garantiza el agente de forma determinista (FR-024 / VI). El dedup de pasos
  repetidos (T112) ahora compara `ruta` normalizada (vacía → raíz autorizada): dos `explore` de
  capas distintas no son repeticiones.

**Condition of Done (T117)**:
- [x] El análisis global ejecuta `explore` por cada capa de primer nivel real y `leer_archivo`
      de su código principal (test `test_enriquecimiento_anade_explore_y_lectura_por_capa`).
- [x] No duplica capas/archivos ya previstos en el plan.
- [x] Se omite si el catálogo no tiene `explore` o `leer_archivo`.
- [x] Dedup ruta-normalizada: `src` y `tests` con la misma profundidad no colisionan.

- [x] T118 [US-14] Honestidad de cobertura: cuando un análisis global agota el presupuesto de
  pasos, `loop._respuesta_react` añade a la intención del `responder` una nota de cobertura para
  que la respuesta entregue TODO lo observado por capa y declare explícitamente qué quedó sin
  analizar, en vez de recomendar re-preguntar (IX / FR-019). Refuerzo de prompts en
  `openai_compatible_backend`: `planificar` (análisis global debe recorrer cada capa y leer su
  código), `razonar` (no concluir mientras falten capas), `evaluar` (no satisfecha si quedan
  capas sin explorar) y `responder` (desglose completo por capa + cobertura declarada).

**Condition of Done (T118)**:
- [x] Un análisis global que agota el presupuesto recibe la nota de cobertura; una intención
      puntual agotada no la recibe.
- [x] Prompts de `planificar`/`razonar`/`evaluar`/`responder` refuerzan la exhaustividad global.
- [x] Suite completa verde.

- [x] T119 [US-14] Robustez del `responder` y honestidad del error (regresión real observada:
  un análisis global con 13 observaciones de archivos leídos terminaba en "No tengo una
  respuesta basada en evidencia para eso" aunque había evidencia real; la llamada final
  `responder` excedía el contexto del modelo y su excepción se tragaba en silencio). Fix:
  (a) `openai_compatible_backend.responder` acota cada observación a 700 chars
  (`_MAX_CHARS_EVIDENCIA_RESPONDER`) y, ante un fallo de la API, reintenta UNA vez con
  evidencia compacta (solo las 6 observaciones más recientes a 400 chars,
  `_MAX_OBSERVACIONES_RESPONDER`/`_MAX_CHARS_EVIDENCIA_RESPONDER_RETRY`); (b)
  `loop._respuesta_react` ya NO traga la excepción: expone el error real del proveedor en la
  respuesta (honestidad IX/FR-019) con `confianza=sin_informacion`, reservando el fallback
  genérico solo para respuestas vacías sin error.

**Condition of Done (T119)**:
- [x] `responder` acota la evidencia por observación (test `test_responder_acota_cada_observacion`).
- [x] Ante fallo de API reintenta con evidencia compacta; si falla también, propaga el error.
- [x] `_respuesta_react` expone el error real del backend (test `test_respuesta_expone_error_real_del_backend`).
- [x] El fallback original se conserva cuando la respuesta es vacía sin error.
- [x] Suite completa verde.

- [x] T120 [US-14] Amplitud del detector de análisis global (regresión real
  observada en ReservaHotel): al pedir "analiza la estructura del proyecto" el
  agente devolvía solo raíz + WebPortal (plan del flash superficial) porque la
  frase NO estaba en `_FRASES_ANALISIS_GLOBAL` y, por tanto, no se ampliaba el
  presupuesto ni se disparaba `_enriquecer_plan_analisis_global` (el safety net
  determinista por capa). Fix: ampliar las frases a todas las variantes comunes
  ("analiza/explica/describe la estructura", "analiza la arquitectura", "qué
  capas hay", "cuáles son las capas", "cómo está organizado [el proyecto]",
  "organización/distribución por capas", "estructura del proyecto", etc.),
  manteniendo el detector determinista sin LLM (VI/SC-010).

**Condition of Done (T120)**:
- [x] "analiza la estructura del proyecto" (y variantes) dispara el enriquecimiento por capa.
- [x] Consultas puntuales siguen sin tratarse como globales ("explora", "explica
      qué hace X", "analiza estos resultados de prueba", "¿cuáles clases probar?").
- [x] Test de regresión con capas BLL/DAL/UIL + WebPortal (test_analiza_la_estructura_dispara_enriquecimiento).
- [x] Suite completa verde.

- [x] T121 [US-14] Sugerencia de pruebas como análisis exhaustivo (regresión
  real observada en ReservaHotel): al preguntar "¿qué tipo de pruebas podemos
  aplicar al proyecto?" el agente respondía "no conozco la estructura" porque
  la intención no disparaba el presupuesto ampliado ni el enriquecimiento del
  plan (cobertura por capa), y el plan del flash para esa pregunta era
  superficial. Fix: detector determinista `_es_intencion_pruebas`
  (`_FRASES_INTENCION_PRUEBAS`: "qué tipo de pruebas", "qué pruebas podemos/
  aplicar/recomiendas/hacer", "qué casos de prueba", "cómo probar el
  proyecto", "estrategia de pruebas", etc.) + `_es_analisis_exhaustivo`
  (global ∨ pruebas). Estas intenciones ahora: (a) amplían el presupuesto a
  18 (SC-016), (b) reciben la cobertura determinista por capa de
  `_enriquecer_plan_analisis_global` (explore por capa + leer su código
  principal) y (c) `_enriquecer_plan_pruebas` añade `locate` de clases reales
  (`class\s+\w+`) y `generate_test_cases` con el objetivo extraído de la
  solicitud, sin duplicar pasos ya previstos (FR-024 / VI). La nota de
  cobertura al agotar el presupuesto se aplica también a estas intenciones
  (IX / FR-019).

**Condition of Done (T121)**:
- [x] "¿qué pruebas podemos aplicar?" dispara presupuesto + cobertura por capa +
      `locate` + `generate_test_cases`.
- [x] No se confunde con ejecutar pruebas ("ejecuta las pruebas") ni con
      explicar archivos concretos ("explícame qué pruebas hace tests/test_app.py").
- [x] No duplica `locate`/`generate_test_cases` si el plan ya los prevé.
- [x] Nota de cobertura al agotar el presupuesto en intenciones de pruebas.
- [x] Suite completa verde.

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- **Cobertura de requerimientos**: FR-001..FR-031 cubiertos (véase T052); SC-001..SC-014 verificados; principios constitución I..XIV aplicados. Ampliación multi-lenguaje y robustez LLM documentada en Phase 11 (T070-T074). Bucle de razonamiento-acción (agente, no chatbot) definido en Phase 12 (T076-T084) y en `agent-reasoning-loop.md`. Agente conversacional con memoria y tareas (chat) implementado en Phase 13 (T085-T092) y documentado en `agent-reasoning-loop.md` §12 + `use-cases/UC-011.md`. **Acciones destructivas** (crear/editar/eliminar) especificadas e implementadas en Phase 14 (T095-T103) y documentadas en `spec.md` v1.2 (US-13, FR-042..047, SC-021..024), `plan.md` §Phase 14, `use-cases/UC-012.md`, `contracts/tool-contracts.md` y `data-model.md` (entidad `Backup`). **Profundidad de análisis** (lectura de código) especificada e implementada en Phase 15 (T104-T115) y documentada en `spec.md` v1.3 (US-14, FR-048..050, SC-025..026) y `use-cases/UC-013.md`. **Profundidad de análisis optimizada** para el modelo actual (decisión aprobada): presupuesto dinámico + enriquecimiento determinista por capa + nota de cobertura (T116-T118, Phase 15). **Robustez del `responder`** y honestidad del error del proveedor (T119, Phase 15). **Amplitud del detector de análisis global** (T120, Phase 15). **Sugerencia de pruebas como análisis exhaustivo** (T121, Phase 15). No quedan acciones ni requerimientos no funcionales sin su correspondiente task.

## Condiciones de Terminación (Checklists) Consolidado

Cada tarea marcada arriba incluye su **Condition of Done** como checklist verificable.
Verificación final global en **T056** confirma que: pytest verde, CLI operativa,
ninguna fuga de secretos, determinismo comprobado (T051) y cobertura completa de
FR/SC (T052). La ampliación multi-lenguaje y la robustez LLM quedan verificadas
en **T070-T074** (Phase 11).
