# Design: Agente de Razonamiento-Acción (percibir → pensar → actuar)

**Feature Branch**: `001-core-ai-qa-agent`

**Status**: Draft

**Decisiones de diseño (confirmadas con el usuario)**
- **Autonomía guiada**: el agente planifica, razona y ejecuta varios pasos
  libremente; las acciones sensibles (ejecutar tests, comandos) siguen
  requiriendo autorización por acción (SC-004).
- **Razonamiento visible por pasos**: el usuario ve, para cada paso, qué pensó
  el agente, qué herramienta ejecutó y por qué, antes de la respuesta final.

## 1. Problema

Hoy el flujo de `Agent.atender` (`src/qa_agent/agent/loop.py:285`) es de **una
sola pasada**: se elige una única herramienta (router determinista o LLM) → se
ejecuta → se responde. Los parámetros se derivan con reglas fijas del loop
(`_parametros_para`, `loop.py:150`). El resultado es un comportamiento de
"chatbot orientado a herramientas", no de agente: no razona, no planifica, no
itera, no reflexiona.

Ejemplo observado: al preguntar *"¿cuáles clases son las más importantes de
probar?"*, el agente ejecutó `explore` (que solo lista nombres de
archivos/directorios) y no llegó a leer el contenido de las clases, porque la
selección de herramienta y sus parámetros son rígidos.

## 2. Objetivo

Convertir el bucle en un **agente de razonamiento-acción (bucle ReAct)** que:

1. **Percibe** la intención real de la solicitud y su entidad objetivo.
2. **Piensa** un plan multi-paso explícito con criterio de éxito.
3. **Actúa** eligiendo herramienta y parámetros por razonamiento.
4. **Observa** los resultados reales y los acumula como evidencia.
5. **Reflexiona** si la evidencia satisface la intención.
6. **Decide** iterar (nuevo paso) o concluir, dentro de límites de parada.

Sin romper las garantías vigentes: no inventar información (FR-019 / SC-002),
redactar secretos (SC-008 / FR-021), autorizar acciones sensibles (SC-004 /
FR-015/016), respetar la allowlist (FR-025) y mantener trazabilidad (FR-020).

## 3. El ciclo de razonamiento-acción

```
solicitud del usuario
      │
      ▼
┌─────────────────┐
│ 1. PERCIBIR     │  interpretar intención + entidad objetivo + contexto
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. PENSAR       │  generar plan multi-paso con criterio de éxito
└────────┬────────┘        (usar intención, catálogo de herramientas, contexto)
         ▼
   ┌─────────────►  iterar ──────────────┐
   │                                      │
┌─────────────────┐              ┌─────────────────┐
│ 3. ACTUAR       │              │ 5. REFLEXIONAR  │
│ elegir paso →   │   observación│ evaluar         │
│ herramienta +   │────────────► │ evidencia vs    │
│ parámetros      │              │ criterio de     │
└────────┬────────┘              │ éxito           │
         ▼                       └────────┬────────┘
┌─────────────────┐                       │
│ 4. OBSERVAR     │  acumular resultado   │ decidir
└─────────────────┘  real en el estado    ▼
                                   ┌─────────────────┐
                                   │ 6. RESPONDER    │  respuesta final basada
                                   └─────────────────┘  en la evidencia real
```

**Reglas del ciclo**
- Cada paso es una **observación real** registrada en el historial visible
  (FR-020): qué pensó, qué herramienta ejecutó, qué parámetros usó, qué obtuvo.
- El razonamiento es **hipótesis**: puede proponer qué buscar o qué probar,
  pero toda afirmación de la respuesta final debe estar **anclada en una
  observación real** (SC-002). Nunca se presenta una hipótesis como hecho
  (FR-019).
- El ciclo termina cuando: (a) el criterio de éxito se cumple, (b) se alcanza
  el límite de pasos (`pasos_max`), (c) el presupuesto de tokens se agota, o
  (d) la reflexión concluye que no hay más evidencia obtenible.

## 4. Modelos de datos (ampliación de `data-model.md`)

```python
@dataclass
class Intencion:
    texto: str                      # solicitud normalizada
    objetivo: str                   # qué pregunta/acciona el usuario
    entidad: str                    # qué objeto real del proyecto (clases, archivos, ...)
    contexto: dict                  # ruta base, historial de sesión

@dataclass
class PasoDePlan:
    orden: int
    razon: str                      # por qué se hace este paso (visible)
    herramienta: str                # id de la herramienta
    parametros: dict                # argumentos concretos decididos por razonamiento
    criterio_salida: str            # qué evidencia debe producir este paso

@dataclass
class Plan:
    objetivo: str
    criterio_exito: str             # cómo saber que la intención está satisfecha
    pasos: list[PasoDePlan]
    pendientes: list[PasoDePlan]

@dataclass
class Observacion:
    paso: PasoDePlan
    resultado: ResultadoDeHerramienta   # resultado REAL, no fabricado
    evaluacion: str                 # reflexión sobre qué aporta este resultado

@dataclass
class EstadoDelAgente:
    intencion: Intencion
    plan: Plan | None
    observaciones: list[Observacion]
    pasos_ejecutados: int
    pasos_max: int                  # límite de parada (p.ej. 5)
    presupuesto_tokens: int | None  # límite opcional
```

## 5. Contrato ampliado del backend LLM (`contracts/llm-backend-contract.md`)

El backend pasa de `seleccionar_herramienta` + `generar_respuesta` a un
contrato de razonamiento. Cada operación recibe JSON y devuelve JSON, con
esquemas validados (JSON Schema) y reglas de honestidad:

| Operación | Entrada | Salida | Honestidad |
|---|---|---|---|
| `planificar(intencion, catalogo, contexto)` | intención + descripciones de herramientas + contexto | `Plan` (objetivo, criterio de éxito, pasos con herramienta, parámetros y razón) | Solo planifica sobre herramientas reales del catálogo y rutas permitidas. |
| `razonar(estado)` | intención + plan pendiente + observaciones previas | `PasoDePlan` (siguiente paso) o `{"concluir": true}` | No inventa resultados; usa observaciones reales previas. |
| `evaluar(estado)` | intención + observaciones | `{"satisfecha": bool, "razon": str}` | Distingue evidencia real de inferencia; si duda, `satisfecha=False`. |
| `responder(evidencia)` | intención + observaciones reales | texto final + confianza + `recomendaciones` | Toda afirmación anclada en una observación (SC-002). |

**Restricciones de la selección de parámetros**: el backend propone parámetros
(`ruta`, `patron`, `objetivo`, `profundidad_max`...), pero el `Agent` los
**valida contra el esquema de la herramienta** y contra la allowlist antes de
ejecutar. Un parámetro inválido o fuera de ruta se rechaza y se notifica, sin
ejecutar (FR-025).

## 6. Política de autonomía (autonomía guiada)

- El agente decide libremente **qué paso ejecutar** y con **qué parámetros**,
  siempre dentro de la allowlist (FR-025).
- Las acciones **sensibles** (`requiere_autorizacion=True`, p.ej. `run_tests`,
  `analyze_coverage`) continúan pasando por `GestorDeAutorizacion` (FR-015/016,
  SC-004): se suspende el paso y se pide autorización al usuario antes de
  ejecutar. Si se deniega, el agente **re-planifica** (elige otro paso no
  sensible) en lugar de abortar todo.
- El número máximo de pasos por solicitud (`pasos_max`, p.ej. 5) se configura
  al construir el `Agent` y se documenta. Evita bucles infinitos.

### Ejecución eficiente del plan (optimización de llamadas LLM)

- Mientras el plan tenga pasos **pendientes**, el bucle los ejecuta en orden
  **directamente** (sin otra llamada LLM): el plan ya define qué hacer. Esto
  reduce la latencia: para un plan de N pasos, la única llamada de decisión
  intermedia es `evaluar()` al final, no `razonar()+evaluar()` por cada paso.
- `razonar()` solo se invoca cuando el plan se **agota** y la evidencia aún no
  satisface el criterio (re-planificación adaptativa o decisión de concluir).
- Las observaciones que se envían al LLM en `razonar`/`evaluar`/`responder` se
  **acotan** (las exploraciones/búsquedas pueden ser extensas); el historial y
  la respuesta final siguen basándose en los datos reales completos, no en el
  prompt.

### Calidad del plan y del cierre (comportamiento de agente, no de bot)

- `planificar()` recibe el **catálogo con sus esquemas de entrada** (nombres y
  tipos de parámetros), no solo `id: descripción`: el LLM sabe qué herramientas
  existen y cómo invocarlas (p.ej. `search`/`locate` para definir clases). Se
  **deduplican pasos idénticos** (misma herramienta + parámetros) para no repetir
  observaciones.
- `evaluar()` es estricto: `satisfecha=true` solo si la evidencia responde
  **directamente** a la intención (p.ej. "clases a probar" exige la lista real de
  clases, no solo la estructura de carpetas). Si falta información, el bucle
  re-planifica o responde con confianza `limitada`/`sin_informacion`.
- `responder()` recibe la **intención del usuario**: la respuesta la atiende
  directamente (prioriza las clases reales observadas por capa) en lugar de
  describir la evidencia cruda.

## 7. Visibilidad del razonamiento (razonamiento visible por pasos)

- Cada `PasoDePlan` muestra al usuario: **razón** (por qué se hace), **herramienta**,
  **parámetros**, y **observación** (resultado real).
- El razonamiento (la "razón") pasa por el `Redactor` antes de mostrarse
  (SC-008): puede contener secretos citados del contexto.
- El historial visible (FR-020) gana una columna de "razón" para cada acción.
- La respuesta final se renderiza al final, tras el historial de pasos.

## 8. Límites de parada y seguridad

| Límite | Valor por defecto | Garantía |
|---|---|---|
| `pasos_max` | 5 | No hay bucles infinitos; el agente responde con la evidencia acumulada. |
| Presupuesto de tokens | opcional (backend) | Evita gasto excesivo. |
| Convergencia | `evaluar()` decide | Si no satisface tras `pasos_max`, responde con lo obtenido + confianza `limitada`/`sin_informacion` + recomendaciones. |

## 9. Requisitos nuevos propuestos

### FR (funcionales)
- **FR-032** El agente SHALL generar un plan multi-paso explícito para
  solicitudes que requieran más de una herramienta, antes de ejecutar.
- **FR-033** El agente SHALL elegir la herramienta y sus parámetros por
  razonamiento, validados contra el esquema y la allowlist.
- **FR-034** El agente SHALL iterar ejecutando pasos hasta satisfacer el
  criterio de éxito, agotar `pasos_max` o no poder obtener más evidencia.
- **FR-035** El agente SHALL mostrar el razonamiento de cada paso
  (razón + herramienta + parámetros + observación) en el historial visible.
- **FR-036** Ante una autorización denegada, el agente SHALL re-planificar con
  un paso alternativo no sensible o informar la imposibilidad.

### SC (criterios de éxito)
- **SC-015** Tras una solicitud, el historial visible muestra los pasos con su
  razón y sus observaciones reales (verificable por test).
- **SC-016** El agente no supera `pasos_max` pasos por solicitud (verificable
  con FakeLLM que siempre pide más pasos).
- **SC-017** Toda afirmación de la respuesta final se ancla en una observación
  real registrada (verificable por test con FakeLLM que intenta inventar).

## 10. Impacto en documentos y tareas

- `data-model.md`: añadir los modelos de §4.
- `contracts/llm-backend-contract.md`: sustituir la sección de selección por el
  contrato de razonamiento (§5).
- `contracts/agent-interface-contract.md`: documentar el nuevo ciclo y la
  configuración `pasos_max`.
- `spec.md`: incorporar FR-032..036 y SC-015..017 con User Stories y escenarios
  de aceptación (US-11).
- `tasks.md`: **Phase 12 (T076+)** — implementación TDD del bucle:
  - T076 modelos `Intencion/Plan/PasoDePlan/Observacion/EstadoDelAgente`.
  - T077 contrato backend `planificar/razonar/evaluar/responder` + FakeLLM
    determinista para razonamiento.
  - T078 reescritura de `atender` como bucle ReAct (percibir→pensar→actuar→
    observar→reflexionar→decidir), manteniendo autorización y allowlist.
  - T079 validación de parámetros propuestos por el LLM contra esquema +
    allowlist (FR-033).
  - T080 re-planificación ante denegación de autorización (FR-036).
  - T081 límite `pasos_max` y respuesta degradada con confianza limitada
    (SC-016).
  - T082 visibilidad del razonamiento en historial y CLI (FR-035 / SC-015).
  - T083 honestidad: afirmaciones finales ancladas en observaciones reales
    (SC-017).
  - T084 trazabilidad FR/SC en `docs/trazabilidad.md`.
- `docs/use-cases/UC-010.md`: caso de uso "el agente planifica y ejecuta una
  tarea de análisis multi-paso" (p.ej. priorizar clases a probar).

## 11. Migración y compatibilidad

- El router determinista (`router.py`) se mantiene como **primera pasada de
  percepción** para solicitudes simples de una sola herramienta (no añade
  valor razonar cuando la intención es inequívoca). Para intenciones que
  sugieren varias herramientas o parámetros no triviales, se delega en el
  bucle de razonamiento.
- `FakeLLM` se extiende (no se rompe) para soportar los nuevos métodos con
  respuestas deterministas configurables.
- Las herramientas existentes NO cambian su contrato: solo cambia el bucle
  que las orquesta.

## 12. Modo Conversacional (Phase 13 / US-12)

El `AgentConversacional` (`src/qa_agent/agent/conversational.py`) envuelve al
`Agent` ReAct como **herramienta analítica interna** y añade continuidad:

```
Usuario ─► AgentConversacional
              │  detecta intención QA (enrutador + vocabulario QA)
              │      ├─ sí ──► Agent ReAct (planificar/actuar/observar) ─► respuesta
              │      └─ no ──► LLM directo (conversación general)
              └─► registra Turno (usuario, agente, herramientas, razonamiento_ref)
              └─► aprende hechos y actualiza resumen (Memoria)
              └─► tareas (GestorTareas) y persistencia (SesionManager)
```

### 12.1 Memoria corta (in-sesión)

Antes de `planificar`, se inyecta en `Intencion.contexto` (ver §4/§7) el
**historial conversacional** del agente (`_contexto_conversacional`):
- `historial`: últimos 5 turnos `{usuario, agente}`.
- `resumen`: resumen evolutivo de la conversación.
- `tareas_pendientes`: tareas abiertas asignadas al agente.
- `hechos`: hechos aprendidos (memoria larga).

Así el LLM planifica con la memoria de la sesión, no como un single-shot.

### 12.2 Delegación vs conversación directa (T090)

- **Análisis QA** (explorar, localizar, buscar, cobertura, pruebas, clases…):
  el `Agent` ReAct se usa como herramienta de análisis profundo; su
  `razonamiento` queda referenciado en el `Turno` (`razonamiento_ref`).
- **Conversación general** (saludos, preguntas conceptuales): el LLM responde
  directo (`responder` sin observaciones), sin delegar ni ejecutar herramientas.
- Heurística previa determinista (`_es_intencion_qa`): el enrutador capta
  solicitudes QA; si no, se buscan términos QA en el texto. Sin ambigüedad se
  responde directo (evita llamadas LLM innecesarias).

### 12.3 Memoria larga y persistencia (T086/T088)

- `Memoria` guarda hechos, preferencias y proyectos conocidos entre sesiones.
- `SesionManager` persiste la `Conversacion` (JSON por sesión o SQLite) con
  `guardar()/cargar(id)/listar()/borrar()`; permite reanudar contexto previo.
- `GestorTareas` mantiene CRUD de tareas ligado a la sesión (estado,
  prioridad, etiquetas, dependencias, asignación).

### 12.4 CLI de chat (T089)

`qa-agent chat --ruta <proyecto> [--demo] [--sesion-dir <dir>]` abre un REPL con
prompt `> `, comandos `/tarea`, `/sesion`, `/memoria`, `/ayuda`, y renderizado
de razonamiento/respuesta reutilizando `_renderizar_respuesta`.

### 12.6 Ejecución de tareas (`/tarea run <id>`, T093)

Una tarea no solo se rastrea: **se ejecuta**. `ejecutar_tarea` en
`AgentConversacional`:

1. Toma la tarea pendiente/en_progreso por su id.
2. Convierte `titulo + descripcion` en una `Intencion` QA con el contexto
   conversacional inyectado.
3. La delega al `Agent` ReAct (mismas herramientas reales, autorización,
   allowlist y redacción que cualquier análisis QA).
4. Al terminar:
   - con evidencia real (`basada_en_herramientas`) → `estado=completada` y
     `resultado` = texto de la respuesta anclada en observaciones.
   - sin evidencia → `estado=bloqueada` con el motivo guardado.
5. El turno y el resultado quedan en la `Conversacion` y se persisten con
   `/sesion save` (SC-020).

### 12.5 Implementación (Phase 13 / tasks.md T085-T092)

- `src/qa_agent/agent/reasoning.py`: entidades `Conversacion`, `Turno`,
  `Memoria`, `TareaAgente` (+ `EstadoTarea`).
- `src/qa_agent/agent/session_manager.py`: `SesionManager`.
- `src/qa_agent/agent/gestor_tareas.py`: `GestorTareas`.
- `src/qa_agent/agent/conversational.py`: `AgentConversacional`.
- `src/qa_agent/agent/loop.py`: `Agent.atender(..., contexto)` inyecta memoria.
- `src/qa_agent/cli/main.py`: comando `chat` y procesamiento de `/comandos`.
- `docs/use-cases/UC-011.md`: caso de uso del chat con memoria y tareas.
- `data-model.md` §Entidades conversacionales: ER de `Conversacion/Turno/
  Memoria/TareaAgente`.