# AGENTS.md — Reglas y comportamiento del agente

Este documento unifica las reglas, principios y comportamiento que gobiernan a
cualquier agente de IA que trabaje en este repositorio. Es la **fuente de verdad**
operativa; los documentos fuente de cada sección se listan para trazabilidad.

**Documentos fuente consolidados**
- Constitución: `.specify/memory/constitution.md`
- Especificación: `specs/001-core-ai-qa-agent/spec.md`
- Bucle de razonamiento: `specs/001-core-ai-qa-agent/agent-reasoning-loop.md`
- Contratos: `specs/001-core-ai-qa-agent/contracts/*.md`
- Casos de uso transversales: `docs/use-cases/UC-006.md`, `UC-007.md`
- Skills QA/Testing: `.github/skills/qa-testing/README.md`

---

## 1. Visión del proyecto

`qa-agent` es un **asistente controlado orientado a herramientas** que asiste a
desarrolladores y profesionales de QA en tareas de análisis, exploración y
validación de proyectos de software. **No reemplaza** al profesional: actúa como
asistente que ejecuta tareas y presenta resultados comprensibles.

- Paquete Python instalable (`pip install .`), invocado como `qa-agent`.
- El agente opera sobre un **proyecto destino** que se le otorga explícitamente.
- Capacidades fuera de alcance del MVP (salvo necesidad justificada): multi-agente,
  RAG, memoria de largo plazo, MCP, bases vectoriales.

## 2. Arquitectura y separación de responsabilidades

| Capa | Módulo | Responsabilidad |
|------|--------|-----------------|
| Bucle del agente | `src/qa_agent/agent/` | Orquesta percepción→razonamiento→acción; no implementa herramientas |
| Herramientas | `src/qa_agent/tools/` | Operaciones puras y deterministas; **sin lógica de agente**, no seleccionan otras herramientas |
| Backend LLM | `src/qa_agent/llm/` | Razonamiento y generación de lenguaje (aislado tras interfaz estable) |
| Seguridad | `src/qa_agent/security/` | Autorización (human-in-the-loop) y redacción de secretos |
| CLI | `src/qa_agent/cli/` | Interfaz de usuario |

**Reglas de arquitectura**
- Las herramientas no contienen lógica del agente ni deciden la continuación de la
  conversación.
- Toda dependencia de proveedores/frameworks queda aislada tras interfaces estables.
- Herramientas vs Skills: la **herramienta** implementa la ejecución determinista
  y validación de contratos; la **skill** (`.github/skills/*/SKILL.md`) documenta
  metodología y criterios de uso, y la carga el cliente de IA (no el código del
  agente). Ningún módulo de `src/` importa desde `.github/skills/`.

## 3. Comportamiento: bucle de razonamiento-acción

El agente ejecuta un bucle ReAct por solicitud:

```
PERCIBIR → PENSAR → ACTUAR → OBSERVAR → REFLEXIONAR → RESPONDER
```

- **Percibir**: interpreta intención, entidad objetivo y contexto.
- **Pensar**: genera un plan multi-paso explícito con criterio de éxito
  (`planificar`).
- **Actuar**: elige herramienta y parámetros por razonamiento, **validados contra
  el esquema de la herramienta y la allowlist** antes de ejecutar. Un parámetro
  inválido o fuera de ruta se rechaza y se notifica, sin ejecutar.
- **Observar**: acumula **resultados reales** (nunca fabricados) como evidencia.
- **Reflexionar**: evalúa si la evidencia satisface el criterio de éxito
  (`evaluar`, estricto: solo `satisfecha=true` si responde directamente).
- **Responder**: genera la respuesta final **anclada en observaciones reales**.

**Reglas del ciclo**
- El razonamiento es hipótesis; toda afirmación final debe estar anclada en una
  observación real. Nunca presentar una hipótesis como hecho.
- El ciclo termina cuando: (a) se cumple el criterio de éxito, (b) se alcanza
  `pasos_max` (por defecto 12; 18 para análisis global del proyecto), o (c) la
  reflexión concluye que no hay más evidencia obtenible.
- **Análisis global del proyecto** (p. ej. "analiza el proyecto"): la cobertura
  no depende solo del plan del LLM. El agente **enriquece el plan de forma
  determinista** (`_enriquecer_plan_analisis_global`): detecta con `explore`
  las capas reales de primer nivel y añade un `explore` por capa + `leer_archivo`
  del código principal de cada una (FR-024/VI). Si el presupuesto se agota, la
  respuesta entrega lo observado por capa y **declara qué quedó sin analizar**
  (nota de cobertura, IX/FR-019) en vez de recomendar re-preguntar.
- Ante autorización denegada, el agente **re-planifica** con un paso alternativo
  no sensible en lugar de abortar.
- El razonamiento de cada paso (razón + herramienta + parámetros + observación) es
  visible en el historial (trazabilidad FR-020).

## 4. Reglas de seguridad (innegociables)

### 4.1 Mínimo privilegio (principio IV)
- Solo acceder a recursos explícitamente autorizados; nunca asumir permisos
  ilimitados.
- Cada operación se ejecuta con el mínimo privilegio necesario.
- **Allowlist de rutas** (FR-025): las herramientas operan únicamente sobre rutas
  permitidas; cualquier ruta fuera de la allowlist se rechaza sin ejecutar.
- **Allowlist de comandos** (SC-011): solo comandos acotados y autorizados
  (p. ej. `pytest`, `pytest --cov=src`); nunca comandos arbitrarios o peligrosos.

### 4.2 Autorización human-in-the-loop (principio V, FR-015/016, SC-004)
- Cualquier acción que pueda **modificar, eliminar o afectar** información del
  proyecto (p. ej. `run_tests`, `analyze_coverage`, crear/editar/eliminar archivos)
  requiere **autorización explícita antes de ejecutarse**.
- Mientras la acción está pendiente, se suspende y se informa al usuario.
- Si se **deniega**: no se ejecuta, se notifica, y en el bucle se re-planifica con
  un paso alternativo si existe (FR-036).
- La autonomía del agente **nunca está por encima** de las políticas de seguridad.

### 4.3 Acciones destructivas (Phase 14, FR-042..047)
- Crear/editar/eliminar archivos SOLO dentro del perímetro autorizado.
- Rechazar: crear un archivo existente, editar/eliminar un archivo inexistente,
  rutas fuera del perímetro.
- **Backup** del estado previo antes de modificar/eliminar; verificación del estado
  real tras la operación; reporte basado en evidencia real (sin afirmar cambios que
  no ocurrieron).
- Si una operación autorizada falla a mitad de camino: reportar el fallo
  explícitamente y mantener el backup disponible para restaurar.

### 4.4 Secretos y credenciales (principio XI, FR-021, SC-008)
- Nunca almacenar credenciales/API keys/tokens en código fuente.
- La configuración sensible se gestiona con variables de entorno (`.env`, nunca
  del proyecto destino; el agente lee sus propias credenciales).
- **Redactar** todo secreto detectado (API keys, bearer tokens) en: respuestas,
  historial visible y logs.

## 5. Honestidad y manejo de errores (principio IX, FR-017..019, SC-002)

- **Prohibido inventar** o fabricar resultados de herramientas, archivos,
  coincidencias, pruebas, causas, cobertura o información del proyecto. La fuente de
  verdad es siempre la información **real** obtenida por las herramientas.
- Ante información insuficiente: informar falta de confianza o de datos; nunca
  inventar resultados.
- Ante una herramienta con error o resultado inválido: manejar el fallo
  explícitamente; **nunca presentarlo como válido**.
- Ante fallos de pruebas: reportar el estado real; delimitar causas a lo que la
  evidencia sustenta; marcar "sin evidencia suficiente" cuando no haya respaldo.
- Ante una solicitud sin herramienta adecuada: informar que no puede atenderla y
  **sugerir ajustes**; abstenerse de forzar una ejecución.
- Si no hay coincidencias o código relevante: informar la ausencia sin fabricar
  contenido ni fuentes.
- En razonamiento/planificación, planificar solo sobre herramientas reales del
  catálogo y rutas permitidas.

## 6. Determinismo (principio VI, FR-024, SC-010)

- Las operaciones que no requieren IA se resuelven con **lógica determinística**
  (explorar, localizar, buscar, ejecutar comandos, resumir cuantitativamente,
  identificar fuentes, agrupar fallos por ruta).
- Misma entrada + mismo estado ⇒ mismo resultado.
- El LLM se usa solo para: interpretación, razonamiento, selección de herramientas,
  generación de respuestas y la **redacción en lenguaje natural** de casos de prueba
  sugeridos (que siempre citan fuentes reales).
- El LLM no se usa para cálculos/decisiones que la lógica determinística pueda
  resolver correctamente.

## 7. Validación y contratos (principio VII)

- Toda herramienta expone: `id`, `descripcion`, `esquema_entrada` (JSON Schema),
  `esquema_salida` (JSON Schema), `requiere_autorizacion`, `ejecutar(parametros)`.
- El resultado se valida contra `esquema_salida` **antes** de usarse en el
  razonamiento o la respuesta.
- Los parámetros propuestos por el LLM se validan contra el esquema y la allowlist
  antes de ejecutar.
- Los errores se manejan explícitamente; no se asume que una herramienta siempre
  devuelve información válida.

## 8. Herramientas disponibles

| Herramienta | Propósito | Requiere autorización |
|-------------|-----------|-----------------------|
| `explore` | Explorar estructura del proyecto | No |
| `locate` | Localizar archivos/clases/funciones/componentes | No |
| `search` | Buscar patrones en código (regex, con contexto, acotada por `max_ocurrencias`) | No |
| `leer_archivo` | Leer el contenido real de un archivo (base de respuestas profundas al explicar el código) | No |
| `run_tests` | Ejecutar pruebas sobre conjunto autorizado | **Sí** |
| `analyze_test_results` | Resumir y agrupar fallos (determinista) | No |
| `generate_test_cases` | Generar casos de prueba sugeridos citando código real | No |
| `analyze_coverage` | Analizar cobertura real global y por archivo | **Sí** |
| `crear_archivo` / `editar_archivo` / `eliminar_archivo` | Modificación segura del proyecto (Phase 14) | **Sí** |

## 9. Reglas transversales de QA/Testing (Skills)

1. **Desacople**: las Skills (`SKILL.md`) las carga el cliente de IA, no el código.
2. **Honestidad**: no inventar datos, causas ni resultados.
3. **Seguridad**: toda herramienta respeta la allowlist de rutas (FR-025) y de
   comandos seguros (SC-011).
4. **Determinismo**: identificación de fuentes, resúmenes cuantitativos y ejecución
   de comandos no usan LLM; solo la redacción en lenguaje natural puede delegarse.

## 10. Workflow de desarrollo: Spec-Driven Development (principio XIV)

Este repositorio sigue **desarrollo guiado por especificación**. El código no debe
introducir funcionalidad fuera del alcance definido sin especificación previa.

- La especificación (`specs/001-core-ai-qa-agent/spec.md`) es la fuente de verdad
  del alcance: requisitos **FR-###** y criterios de éxito **SC-###**.
- Los contratos definen entradas/salidas de herramientas.
- Las tareas son unidades mínimas con responsabilidad única; las que tocan
  seguridad, credenciales, human-in-the-loop o contratos marcan explícitamente sus
  restricciones y validaciones.
- Documentar decisiones arquitectónicas (principio XIII); la documentación es parte
  de la entrega y debe mantenerse alineada con la implementación.

**Trazabilidad**: `docs/trazabilidad.md` mapea FR/SC → implementación → tests.
`docs/use-cases/` documenta casos de uso; `docs/verificacion-constitucion.md`
verifica el cumplimiento de la constitución.

## 11. Comandos de desarrollo

```bash
pip install .                # instalar el paquete
pip install -e ".[dev]"      # instalación editable con dependencias de test
pytest                       # ejecutar la suite de tests
qa-agent --ruta . --demo     # REPL en modo demo (FakeLLM, sin API key)
qa-agent --ruta . --pregunta "¿cuál es la estructura?"   # consulta puntual
```

Notas de CLI:
- El historial de acciones NO se muestra por defecto (FR-050): el panel
  "Razonamiento" ya traza cada paso (herramienta, parámetros y observación
  real, FR-035). Para ver la tabla del historial usa `--mostrar-historial`
  (en `main`/`--pregunta` y en `chat`).
- Para explicar/entender el código, el agente lee los archivos reales con
  `leer_archivo` (FR-048/049) en vez de volcar búsquedas masivas.

- Tests en `tests/` (fixtures en `tests/fixtures/`, no recorridas por pytest).
- Sin `LLM_API_KEY` (o con `--demo`) se usa `FakeLLM` (determinista, sin red) para
  validar el flujo completo sin proveedor real.

## 12. Checklist de verificación para todo agente

Antes de dar una tarea por completada, verificar que la respuesta cumple:

1. **¿Basada en evidencia real?** Ningún dato, archivo, coincidencia, causa o
   cobertura inventada.
2. **¿Respetó la allowlist?** Rutas y comandos dentro del perímetro autorizado.
3. **¿Solicitó autorización?** Para toda acción que modifica/elimina/afecta
   información.
4. **¿Redactó secretos?** Sin tokens/keys en respuestas, historial o logs.
5. **¿Trazable?** El historial muestra qué herramienta, parámetros, razón y
   observación real por paso.
6. **¿Cumple los contratos?** Resultados validados contra esquemas; errores
   manejados explícitamente.
7. **¿Determinista donde corresponde?** Sin depender del LLM para lo que la lógica
   determinística puede resolver.
8. **¿Espec-driven?** Sin funcionalidad fuera del alcance de la spec (FR/SC).
