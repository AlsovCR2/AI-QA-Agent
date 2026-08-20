# Implementation Plan: Core AI QA & Software Engineering Agent

**Branch**: `001-core-ai-qa-agent` | **Date**: 2026-08-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-core-ai-qa-agent/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Desarrollar un agente de inteligencia artificial especializado en asistir a
desarrolladores y profesionales de QA en tareas de **análisis, exploración y
validación** de proyectos de software, orientado a herramientas, controlado y
verificable. El agente recibe solicitudes en lenguaje natural, selecciona y
ejecuta herramientas, valida los resultados reales obtenidos y genera una
respuesta basada exclusivamente en esa evidencia, manteniendo un historial
visible de sus acciones (trazabilidad), solicitando autorización para acciones
sensibles (human-in-the-loop) y evitando inventar información (honestidad).

El MVP se limita a las tareas de análisis/exploración/validación definidas en el
spec y a una configuración sencilla de herramientas. Quedan fuera del alcance
las capacidades avanzadas (multi-agente, RAG, memoria de largo plazo, MCP,
observabilidad distribuida).

## Technical Context

**Language/Version**: Python 3.11+ (se garantiza compatibilidad con la versión
instalada 3.14 del entorno; el código objetivo es 3.11+). El README establece
explícitamente Python como lenguaje del proyecto.

**Primary Dependencies**:
- **Framework de agentes**: propio y mínimo, sin dependencia de frameworks
  externos de agentes. El núcleo implementa el bucle agente-herramienta
  (interpretar → seleccionar herramienta → ejecutar → validar → responder).
  Esto mantiene el principo de independencia del proveedor/framework de la
  constitución. El **bucle y las herramientas deterministas** se mantienen en
  Python puro (stdlib): no sustituir por librerías, por determinismo (VI) y
  testabilidad (III).
- **LLM**: proveedor aislado tras una interfaz `LLMBackend` (Strategy). Se usa
  un único `OpenAICompatibleBackend` configurable por variables de entorno,
  que soporta **DeepSeek como proveedor por defecto** y **NVIDIA NIM / OpenAI**
  como alternativas (ver `contracts/llm-backend-contract.md`). El núcleo no
  depende de ningún proveedor concreto. En pruebas se usa un `FakeLLM`
  determinista.

**Bibliotecas de soporte** (para no reinventar ruedas en zonas periféricas; no
sustituyen el núcleo del agente):

| Librería | Problema que ya resuelve | Dónde se usa |
|----------|--------------------------|--------------|
| `openai` | SDK oficial de APIs OpenAI-compatibles (DeepSeek/NVIDIA/OpenAI) | `OpenAICompatibleBackend` (`src/qa_agent/llm/openai_compatible_backend.py`) |
| `python-dotenv` | Carga de variables de entorno para secretos (XI) | Configuración (`src/qa_agent/config.py`) |
| `pydantic` | Validación robusta de contratos y datos (VII) | Validación de esquemas de entrada/salida de herramientas y entidades |
| `typer` | Construcción CLI con menos boilerplate que `argparse` | CLI (`src/qa_agent/cli/main.py`) |
| `rich` | Salida legible en terminal (historial visible) | REPL y renderizado del historial (FR-020) |
| `pathspec` | Coincidencia de patrones de rutas (gitignore-like) para allowlist | `Allowlist` y herramientas `explore`/`locate` (FR-025) |
| `pytest` | Framework de testing (dev) | Suite de tests |

> **Regla de uso**: se usan librerías solo donde aportan valor sin reemplazar
> el bucle del agente ni las herramientas deterministas, y sin comprometer el
> determinismo (VI) ni la testabilidad (III). El núcleo (`loop.py`, herramientas
> de exploración/búsqueda/cobertura, `Redactor`, estado en memoria) se mantiene
> Sin dependencias externas.

**Configuración/secretos**: `python-dotenv` para variables de entorno; los
secretos **nunca** en código fuente.

**Validación de contratos**: `pydantic` (validación estricta) sobre
`dataclasses` (stdlib) para estructuras base. Cumple el principio VII y SC-006.

**Observabilidad**: `logging` (stdlib) con redacción de secretos por defecto, y
`rich` para el historial visible al usuario (FR-020).

**Storage**: N/A (estado en memoria por conversación; sin persistencia en el
MVP). No se incorporan bases de datos ni memoria de largo plazo (principio XII).

**Testing**: `pytest`. Las herramientas se prueban de forma independiente sin
LLM real (principio III / SC-006). El agente se prueba con `FakeLLM` para
validar selección de herramientas, validación de resultados, autorización y
honestidad.

**Target Platform**: CLI interactiva (terminal) multiplataforma, orientada a
Windows/Linux/macOS. Sin interfaz web en el MVP.

**Project Type**: CLI + librería (el proyecto expone un punto de entrada de
línea de comandos y una API de librería reutilizable para el núcleo del agente).

**Performance Goals**: Respuesta interactiva < 2s para operaciones
determinísticas (sin contar latencia del LLM). Búsquedas/exploración de
proyectos medianos (< 100k archivos) en tiempo submáximo perceptible.

**Constraints**:
- Operaciones determinísticas sin LLM (principio VI, FR-024, SC-010).
- Cero secretos en código/logs (principio XI, FR-021, SC-008).
- Ninguna operación destructiva sin autorización explícita (principio V,
  FR-015/016, SC-004).
- Mínimo privilegio en toda operación (principio IV, FR-025, SC-011).
- No inventar información (principio IX, FR-019, SC-002).
- Herramientas probables sin LLM real (principio III, SC-006).

**Scale/Scope**: MVP de agente asistente de análisis/QA. Alcance limitado al
spec 001 (UC-001 a UC-007). Proyectos de software pequeños/medianos con acceso
explícito autorizado.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

A continuación se listan los principios de la constitución que condicionan el
plan y su estado de cumplimiento.

| # | Principio | Requisitos que satisface | Estado |
|---|-----------|--------------------------|--------|
| I | Separación de responsabilidades | Núcleo del agente, herramientas, LLM backend y CLI se implementan como capas aisladas. | ✅ Cumple |
| II | Modularidad y extensibilidad | Herramientas se registran como componentes con contrato entrada/salida; añadir herramienta no toca el núcleo. | ✅ Cumple |
| III | Testabilidad | Herramientas testeadas sin LLM (SC-006); agente con FakeLLM. | ✅ Cumple |
| IV | Seguridad y mínimo privilegio | Cada herramienta opera sobre rutas autorizadas; comandos peligrosos restringidos (FR-025). | ✅ Cumple |
| V | Human-in-the-loop | Acciones sensibles requieren autorización antes de ejecutarse (FR-015/016). | ✅ Cumple |
| VI | Determinismo | Operaciones no-LLM con lógica determinística (FR-024). | ✅ Cumple |
| VII | Validación y contratos | Contratos de herramienta con entrada/salida validables; toda herramienta ejecuta validación de su resultado. | ✅ Cumple |
| VIII | Observabilidad y trazabilidad | Historial visible de herramientas y resultados (FR-020); logs estructurados. | ✅ Cumple |
| IX | Manejo seguro de errores | Errores de herramienta tratados explícitamente; prohibido inventar (FR-017/018/019). | ✅ Cumple |
| X | Calidad del código | SOLID, código simple y comprensible. | ✅ Cumple |
| XI | Seguridad de información | Secretos fuera del código y redactados en logs/respuestas (FR-021). | ✅ Cumple |
| XII | Evolución incremental | MVP acotado; no se incorporan RAG/MCP/multi-agente sin necesidad. | ✅ Cumple |
| XIII | Documentación | Decisiones arquitectónicas y técnicas documentadas y alineadas con la implementación (spec/plan/tasks/quickstart). | ✅ Cumple |
| XIV | Spec-Driven Development | Implementación guiada por spec 001; sin funcionalidad fuera de alcance. | ✅ Cumple |

**Resultado del gate**: APROBADO. No se detectan violaciones de principios que
requieran justificación vía complejidad. La arquitectura (una librería + CLI,
con interfaces de herramienta y LLM) es la opción más simple que satisface los
requisitos; no se requiere multi-proyecto ni patrones adicionales.

## Project Structure

### Documentation (this feature)

```text
specs/001-core-ai-qa-agent/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── tool-contracts.md
│   ├── llm-backend-contract.md
│   └── agent-interface-contract.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/qa_agent/                    # Paquete principal (librería del agente)
├── __init__.py                  # Exports públicos del paquete
├── agent/
│   ├── __init__.py
│   ├── loop.py                  # Bucle agente-herramienta (interpretar→seleccionar→ejecutar→validar→responder)
│   ├── session.py               # Estado de conversación y historial visible de acciones
│   └── response.py              # Generación de respuesta final
├── tools/
│   ├── __init__.py              # Registro y selección de herramientas
│   ├── base.py                  # Contrato base de herramienta (nombre, descripción, entrada/salida)
│   ├── explore.py               # Herramienta: explorar estructura del proyecto (UC-002)
│   ├── locate.py                # Herramienta: localizar archivos/componentes (UC-003)
│   ├── search.py                # Herramienta: revisar/buscar patrones en código (UC-004)
│   ├── run_tests.py             # Herramienta: ejecutar y analizar pruebas (UC-005)
│   ├── analyze_test_results.py  # Herramienta: analizar resultados de pruebas (QA/Testing)
│   ├── generate_test_cases.py   # Herramienta: generar casos de prueba sugeridos (QA/Testing)
│   ├── analyze_coverage.py      # Herramienta: analizar cobertura de código (QA/Testing)
│   └── allowlist.py             # Gestión de acceso/rutas autorizadas y mínimo privilegio
├── llm/
│   ├── __init__.py
│   ├── backend.py               # Interfaz LLMBackend (Strategy) — abstracción del proveedor
│   ├── openai_compatible_backend.py  # Backend compatible OpenAI (DeepSeek por defecto; NVIDIA/OpenAI alternativos)
│   └── fake_llm.py              # Backend determinista para pruebas y modo --demo
├── security/
│   ├── __init__.py
│   ├── redactor.py              # Detección y redacción de secretos (FR-021)
│   └── authorization.py         # Solicitud/gestión de autorización human-in-the-loop (UC-006)
├── cli/
│   ├── __init__.py
│   └── main.py                  # Punto de entrada CLI interactiva
└── py.typed                     # Marcador de tipado estático

tests/
├── conftest.py                  # Fixtures: FakeLLM, proyecto temp, redactor
├── unit/
│   ├── test_tools_explore.py
│   ├── test_tools_locate.py
│   ├── test_tools_search.py
│   ├── test_tools_run_tests.py
│   ├── test_allowlist.py
│   ├── test_redactor.py
│   ├── test_authorization.py
│   └── test_determinism.py      # SC-010: operaciones sin LLM son determinísticas
├── integration/
│   └── test_agent_loop.py       # Flujo completo con FakeLLM
└── contract/
    └── test_tool_contracts.py   # Validación de contratos de herramientas

pyproject.toml                   # Definición del proyecto, dependencias, pytest
.env.example                     # Plantilla de variables de entorno (sin secretos)
README.md                        # Documentación del proyecto (raíz)
```

### Uso del agente en otros proyectos (CLI global)

El agente se publica e instala como un **paquete Python instalable** que expone
el comando `qa-agent`. Esto permite usar el agente terminado sobre **cualquier
proyecto**, sin incluir nada en el proyecto destino:

```bash
# Instalación global (una sola vez): instala el comando qa-agent
pip install .          # desde la raíz del repo del agente
# o, aislado del sistema en un entorno propio:
pipx install .

# Uso desde cualquier otro proyecto, apuntando a su raíz:
cd ruta/del/proyecto/a/analizar
qa-agent --ruta .
```

El entry point se declara en `pyproject.toml`:

```toml
[project.scripts]
qa-agent = "qa_agent.cli.main:app"
```

Detalles de la interfaz CLI en
[`contracts/agent-interface-contract.md`](contracts/agent-interface-contract.md).

**Structure Decision**: Se adopta la **Opción 1 - Proyecto único** (librería
`src/qa_agent` + CLI). El proyecto es un asistente de terminal sin frontend/API
web, por lo que no aplican las opciones 2 ni 3. La separación `agent/`
(núcleo), `tools/` (herramientas), `llm/` (backend de lenguaje), `security/`
(redacción y autorización) y `cli/` (interfaz) refleja el principio I de
separación de responsabilidades y la independencia del proveedor (la capa LLM
queda aislada tras `LLMBackend`). Las pruebas se organizan en `unit/`,
`integration/` y `contract/` para cubrir testabilidad (principio III, SC-006).

## Phase 0: Research (resumen)

Consultar [`research.md`](research.md) para el detalle completo. Decisiones
clave:

- **Lenguaje/framework**: Python puro, sin framework de agentes externo. El
  bucle agente-herramienta se implementa a medida (~100-200 LOC) para mantener
  control, determinismo y testabilidad (principios VI, III).
- **LLM**: abstracción `LLMBackend` con implementación OpenAI opcional y
  `FakeLLM` para pruebas. El núcleo nunca depende del proveedor concreto.
- **Herramientas**: `explore`, `locate`, `search`, `run_tests` con contrato
  formalizado y allowlist de rutas para mínimo privilegio.
- **Testing**: `pytest`; determinismo garantizado por diseño de contrato.

## Phase 1: Design (resumen)

### Data model

Consultar [`data-model.md`](data-model.md). Entidades principales:
`Solicitud`, `Herramienta`, `ResultadoDeHerramienta`, `RespuestaDelAgente`,
`AccionSensible`, `RegistroDeAccion` (historial visible), `Secretos`. Ampliación
QA/Testing: `CasoDePrueba` y `CoverageReport`.

### Contracts

Consultar el directorio [`contracts/`](contracts/):
- [tool-contracts.md](contracts/tool-contracts.md) — contrato general de
  herramienta + contratos específicos de `explore`, `locate`, `search`,
  `run_tests` y de las herramientas QA/Testing (`analyze_test_results`,
  `generate_test_cases`, `analyze_coverage`).
- [llm-backend-contract.md](contracts/llm-backend-contract.md) — interfaz
  `LLMBackend` (Strategy).
- [agent-interface-contract.md](contracts/agent-interface-contract.md) — API
  pública del agente y del historial visible.

### Quickstart

Consultar [`quickstart.md`](quickstart.md) para guía de validación ejecutable
de extremo a extremo.

## Re-check Constitution Check (post-design)

Se re-evalúa el gate tras la fase de diseño:

- Los contratos mantienen la **separación de responsabilidades** (I) y
  **modularidad** (II): añadir una herramienta requiere solo registrar un
  nuevo módulo en `tools/` conforme al contrato.
- La **testabilidad** (III) queda garantizada vía `FakeLLM` y fixtures
  (`conftest.py`), cumpliendo SC-006.
- La **seguridad** (IV) y **human-in-the-loop** (V) se materializan en
  `security/authorization.py` y `tools/allowlist.py`.
- El **determinismo** (VI) se garantiza porque las herramientas son funciones
  puras sobre el filesystem con contratos validados; el LLM solo interviene en
  interpretación/selección/respuesta.
- La **observabilidad** (VIII) se materializa en `agent/session.py` (historial
  visible, FR-020) y la **redacción de secretos** (XI) en `security/redactor.py`.

**Resultado**: APROBADO. El diseño no introduce complejidad injustificada.

## Phase 14: Acciones destructivas (modificación del proyecto)

Ampliación documentada en `spec.md` v1.2 (US-13, FR-042..FR-047, SC-021..SC-024)
y en `docs/use-cases/UC-012.md`. Decisiones de diseño previstas (spec-first; la
implementación se realiza en las tareas Phase 14 de `tasks.md`):
**Implementada** (T095-T103, suite 272 tests verde).

- **Tres herramientas deterministas de escritura** bajo el contrato de
  `tools/base.py`: `crear_archivo`, `editar_archivo`, `eliminar_archivo` en
  `src/qa_agent/tools/`. Mantienen el determinismo (VI / SC-010): la operación
  sobre el filesystem no depende del LLM.
- **Autorización obligatoria (human-in-the-loop)**: las tres herramientas se
  registran con `requiere_autorizacion=True` → SC-004 / FR-015-016, reutilizando
  `security/authorization.py` y el rail de `loop.py`.
- **Mínimo privilegio**: operan exclusivamente dentro de la `Allowlist`
  (FR-025 / SC-011); rutas fuera del perímetro o conflictos (crear existente,
  editar/eliminar inexistente) se rechazan sin modificar nada.
- **Backup previo**: un `BackupManager` copia el estado original (con timestamp)
  a `.qa-backup/` dentro del proyecto antes de modificar o eliminar (FR-045).
- **Verificación posterior**: tras la operación, el agente confirma el estado
  real (explore/locate/search) y reporta evidencia de éxito/fracaso (FR-047 /
  FR-019 / SC-002).
- **Enrutamiento determinista** ampliado en `agent/router.py` (crear/editar/
  eliminar/borrar/modificar...) y catálogo en `config.construir_herramientas` y
  `loop._parametros_para`.
- **Redacción transversal**: secretos redactados en respuestas, historial y logs
  (FR-021 / SC-008) como en el resto del agente.

**Constitution Check (Phase 14)**: los principios IV (seguridad/mínimo
privilegio) y V (human-in-the-loop) se refuerzan (toda escritura exige
autorización y respeta el perímetro); II (modularidad) se conserva (nuevas
herramientas sin tocar el núcleo); VI (determinismo) y IX (honestidad) aplican
igual que en el resto de herramientas. Sin violaciones de principios.

## Phase 15: Profundidad de análisis (lectura de código)

Ampliación documentada e implementada en `spec.md` v1.3 (US-14, FR-048..FR-050,
SC-025..SC-026), `docs/use-cases/UC-013.md` y las tareas Phase 15 de `tasks.md`
(T104-T110). Decisiones de diseño:

- **Herramienta `leer_archivo`** (solo lectura, determinista) en
  `src/qa_agent/tools/leer_archivo.py`: lee el contenido real de un archivo
  dentro del perímetro (valida raíz y archivo resuelto contra la `Allowlist`,
  rechaza `..`/traversal), con límite opcional `max_lineas` y aviso explícito de
  truncado; archivo inexistente → `existe=false` (informa ausencia, no inventa).
  Se registra con `requiere_autorizacion=False` (no es acción sensible).
- **Profundidad en el backend**: los prompts de `planificar`, `responder`,
  `generar_respuesta` y `evaluar` obligan a **leer los archivos relevantes**
  cuando la intención pide explicar/entender el código, y a responder con
  profundidad organizada por capa/módulo citando contenido real y con
  `confianza` coherente (FR-049 / SC-026).
- **`search` acotado**: `max_ocurrencias` (default 200) corta los volcados
  masivos que saturaban la observación del LLM y añade `nota` de truncado
  explícita (honestidad, FR-019).
- **Falsos positivos de anclaje**: `_afirmaciones_no_ancladas` ignora las
  palabras capitalizadas al inicio de frase (no son afirmaciones de datos); los
  números y las palabras en medio de la oración siguen anclándose (SC-017).
- **CLI sin ruido**: el historial de acciones se oculta por defecto
  (`--mostrar-historial` para verlo); la trazabilidad de cada paso permanece en
  el panel "Razonamiento" (FR-035 / FR-050).
- **Profundidad del análisis global (T116-T118, decisión aprobada para el
  modelo actual)**: el análisis del proyecto entero no depende solo del plan
  del LLM (flash, planifica corto). Se añaden, de forma determinista (VI):
  (a) **presupuesto dinámico**: `pasos_max` por defecto 5 → 12 y 18 para
  intenciones de análisis global (detección `_es_analisis_global` por frases,
  sin LLM; SC-016 sigue siendo límite duro); (b) **enriquecimiento del plan**:
  `loop._enriquecer_plan_analisis_global` detecta con `explore` las capas
  reales de primer nivel y añade un `explore` por capa + `leer_archivo` del
  código principal de cada una (el dedup de pasos repetidos compara `ruta`
  normalizada para no colisionar entre capas); (c) **honestidad de cobertura**:
  si el presupuesto se agota, `_respuesta_react` añade la nota de cobertura a
  la intención del `responder` para que entregue lo observado por capa y
  declare lo que quedó sin analizar (IX / FR-019); los prompts de
  `planificar`/`razonar`/`evaluar`/`responder` refuerzan la exhaustividad
  global.
- **Robustez del `responder` (T119, regresión real)**: un análisis global con
  muchas lecturas de archivos terminaba en "No tengo una respuesta basada en
  evidencia para eso": la llamada final `responder` (toda la evidencia, ~13
  observaciones × 1500 chars) excedía el contexto del modelo y su excepción se
  tragaba en silencio. Se acota la evidencia por observación a 700 chars y, ante
  un fallo de la API, `responder` reintenta una vez con evidencia compacta (6
  observaciones más recientes a 400 chars); `_respuesta_react` ya no oculta la
  excepción: expone el error real del proveedor con `confianza=sin_informacion`
  (honestidad, IX).
- **Amplitud del detector de análisis global (T120, regresión real en
  ReservaHotel)**: "analiza la estructura del proyecto" devolvía solo raíz +
  WebPortal porque esa frase no estaba en `_FRASES_ANALISIS_GLOBAL` y, por
  tanto, no se ampliaba el presupuesto ni se disparaba el enriquecimiento
  determinista por capa. Se amplían las frases a las variantes comunes
  ("analiza/explica/describe la estructura [del proyecto]", "analiza la
  arquitectura", "qué capas hay", "cuáles son las capas", "cómo está
  organizado [el proyecto]", "organización/distribución por capas", etc.),
  conservando la detección determinista sin LLM (VI/SC-010); las consultas
  puntuales siguen sin tratarse como globales.
- **Sugerencia de pruebas como análisis exhaustivo (T121, regresión real en
  ReservaHotel)**: "¿qué tipo de pruebas podemos aplicar al proyecto?"
  respondía "no conozco la estructura" porque esa intención no disparaba
  presupuesto ampliado ni enriquecimiento. `_es_intencion_pruebas`
  (`_FRASES_INTENCION_PRUEBAS`) la detecta de forma determinista y
  `_es_analisis_exhaustivo` (global ∨ pruebas) amplía el presupuesto a 18 y
  activa la cobertura por capa. `_enriquecer_plan_pruebas` añade además
  `locate` de clases reales y `generate_test_cases` (objetivo extraído de la
  solicitud), sin duplicar pasos ya previstos. La nota de cobertura al agotar
  el presupuesto se aplica también a estas intenciones (IX / FR-019).

**Constitution Check (Phase 15)**: IX (honestidad) se refuerza (contenido real
tal cual, truncado explícito, ausencias informadas); IV (mínimo privilegio) se
conserva (lecturas solo dentro del perímetro); VI (determinismo) y III
(testabilidad sin LLM) aplican; II (modularidad) se respeta (nueva herramienta
sin tocar el núcleo). Sin violaciones de principios.

## Complexity Tracking

> No se requieren justificaciones: la Constitution Check del diseño no arroja
> violaciones. La arquitectura de capas y contratos es la solución más simple
> que satisface los requisitos del spec.
>
> **Phase 14 (acciones destructivas)**: se añade por necesidad funcional
> (constitución XII), manteniendo los mismos patrones (herramientas con
> contrato, autorización, allowlist, determinismo). No introduce complejidad
> injustificada ni dependencias nuevas.
>
> **Phase 15 (profundidad de análisis)**: se añade por necesidad funcional
> (respuestas superficiales al explicar el código, regresión reportada por el
> usuario) y reutiliza los patrones existentes (herramienta con contrato,
> allowlist, determinismo, honestidad, trazabilidad). No introduce complejidad
> injustificada ni dependencias nuevas.
>
> **T116-T118 (optimización de profundidad)**: se añade por decisión aprobada
> (el análisis global era superficial con el modelo actual). Reutiliza
> patrones existentes: determinismo para la cobertura por capa (VI), límite
> duro de pasos (SC-016), honestidad de cobertura (IX), prompts del backend.
> No añade dependencias; el costo es un `explore` extra de raíz + por capa en
> el planificado del análisis global, determinista y dentro del presupuesto.
>
> **T119 (robustez del `responder`)**: se añade por regresión real reportada
> (respuesta genérica falsa pese a tener evidencia). Solución de menor
> complejidad: acotar la evidencia + reintento compacto + exponer el error.
> No añade dependencias ni cambia contratos.
>
> **T120 (amplitud del detector de análisis global)**: se añade por regresión
> real reportada (respuesta superficial). Solución de menor complejidad:
> ampliar las frases del detector determinista existente. No añade dependencias
> ni cambia contratos; es un refinamiento de T116 sin cambio de arquitectura.
>
> **T121 (sugerencia de pruebas como análisis exhaustivo)**: se añade por
> regresión real reportada ("no conozco la estructura" pese a que sí se analizó
> antes). Solución de menor complejidad: detector determinista de frases de
> sugerencia de pruebas + reutilización del enriquecimiento por capa + pasos
> `locate`/`generate_test_cases` condicionados a herramientas presentes. No
> añade dependencias ni cambia contratos.
