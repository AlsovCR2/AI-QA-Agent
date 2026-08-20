# Contrato: API pública del Agente — Core AI QA & Software Engineering Agent

Producción del `/speckit-plan` (Phase 1). Define la interfaz pública reutilizable
del agente (librería) y la estructura del historial visible, alineada con
FR-020 / principio VIII.

## Entrada pública: `Agent`

```
class Agent:
    def __init__(backend: LLMBackend, herramientas: list[Herramienta],
                 allowlist: Allowlist, redactor: Redactor) -> None

    def atender(solicitud_texto: str) -> RespuestaDelAgente
        # Ejecuta el bucle: interpretar -> seleccionar -> ejecutar(validar) ->
        # autorizar si es sensible -> responder. Nunca inventa información
        # (FR-019). Muestra historial visible (FR-020).
```

**Reglas**
- `atender` es el único punto de entrada para procesar una solicitud.
- Retorna una `RespuestaDelAgente` con su historial de acciones (SC-007).
- Si ninguna herramienta es adecuada, se responde con notificación + sugerencia
  (FR-022/023, SC-009).
- Si la solicitud busca información del proyecto, se ejecuta herramienta real y
  se basa en su resultado (FR-003/004).

## Historial visible

La `RespuestaDelAgente` incluye una lista ordenada de `RegistroDeAccion`, cada
una con `orden`, `herramienta_id`, `entrada` (sin secretos), `salida` (redactada)
y `estado`. Esto permite reconstruir la secuencia de acciones para debug y
auditoría (VIII / FR-020 / SC-007).

## Autorización (human-in-the-loop)

- `Agent` expone un mecanismo de autorización para `AccionSensible`
  (UC-006 / FR-015/016). Antes de ejecutar una acción sensible, el agente
  suspende la ejecución y solicita `autorizada`. Si `denegada`, no ejecuta y
  notifica (SC-004).
- Toda operación que ejecute código objetivo (`run_tests` y
  `analyze_coverage`) es sensible y debe atravesar esta autorización, incluso
  cuando otra ruta de análisis la invoque indirectamente. El contrato exige el
  comportamiento no el uso de una clase gateway concreta.

## Redacción de secretos

- Toda salida pública (respuesta, historial, logs) atraviesa el `Redactor`
  (FR-021 / SC-008 / XI).

## Contrato de CLI

Punto de entrada instalable `qa-agent` vía `pyproject.toml`
(`[project.scripts] qa-agent = "qa_agent.cli.main:app"`). Se instala de forma
global con `pip install .` (o `pipx install .`) y se invoca desde **cualquier**
directorio de proyecto, apuntando a la raíz del proyecto sobre el que se trabaja.

**Flujo**:
- Lee solicitudes desde stdin en un bucle REPL (interactivo), o
  `--pregunta "..."` para una consulta puntual (útil en scripts/CI).
- Toma `--ruta <directorio>` para fijar la raíz del proyecto a analizar
  (por defecto, el directorio de trabajo actual `cwd`).
- Configura `LLMBackend` desde variables de entorno (`LLM_BASE_URL`,
  `LLM_MODEL`, `LLM_API_KEY` — DeepSeek por defecto, NVIDIA NIM / OpenAI
  alternativos): `FakeLLM` en modo demo/tests si no hay API key. Detalles en
  [`llm-backend-contract.md`](llm-backend-contract.md).
- Inicializa `Allowlist` con la ruta del proyecto autorizado (mínimo privilegio,
  FR-025).
- Imprime respuesta + historial visible (FR-020).

**Argumentos** (interfaz de línea de comandos)

| Flag | Descripción |
|------|-------------|
| `--ruta <dir>` | Raíz del proyecto a analizar (default: `cwd`). |
| `--pregunta "<texto>"` | Consulta puntual; omite el REPL y salta a respuesta (modo no interactivo). |
| `--demo` | Fuerza `FakeLLM` sin API key (validación sin LLM real). |
| `--mostrar-historial` | Muestra la tabla del historial de acciones; permanece oculta por defecto (FR-050). |
| `--version` | Muestra la versión instalada. |

El punto de entrada aprobado no registra subcomandos. En particular,
`qa-agent chat` no forma parte del MVP: la conversación persistente, memoria,
tareas y `.qa_sessions` pertenecen a US-12, que permanece diferida. El modo
interactivo vigente se inicia directamente con `qa-agent --ruta <dir>` y
mantiene únicamente estado efímero durante el proceso.
