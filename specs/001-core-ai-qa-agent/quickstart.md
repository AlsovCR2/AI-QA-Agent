# Quickstart — Core AI QA & Software Engineering Agent

Producción del `/speckit-plan` (Phase 1). Guía de validación de extremo a
extremo que demuestra que el agente funciona según los casos de uso. Referencias
al [data model](data-model.md) y a los [contracts](contracts/) en lugar de
duplicar detalles de implementación.

## Prerrequisitos

- Python 3.11+.
- `pip install -e .` desde la raíz del repositorio (instala `qa_agent` y
  `pytest` como dependencia de desarrollo).
- Un proyecto de ejemplo con archivos, directorios, código y pruebas (p. ej. el
  propio repositorio, o un proyecto de prueba bajo `tests/fixtures/proyecto_ejemplo`).
- Sin API key: el agente arranca en modo demo con `FakeLLM` (para validar el
  flujo). Con `LLM_API_KEY` configurada (`.env`), se usa el backend real
  compatible OpenAI.

## Configuración

```bash
cp .env.example .env       # rellena las credenciales del proveedor
pip install -e ".[dev]"
```

**Proveedor por defecto: DeepSeek** (valores por defecto en `config.py`):

```bash
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_API_KEY=sk-tu_llave_deepseek
```

**Alternativas opcionales** (solo cambiar `.env`, misma instalación):

- *NVIDIA NIM (gratis)*:
  ```bash
  LLM_BASE_URL=https://integrate.api.nvidia.com/v1
  LLM_MODEL=deepseek-ai/deepseek-v4-flash
  LLM_API_KEY=nvapi-tu_llave_nvidia
  ```
- *OpenAI*:
  ```bash
  LLM_BASE_URL=https://api.openai.com/v1
  LLM_MODEL=gpt-4o-mini
  LLM_API_KEY=sk-tu_llave_openai
  ```

Detalles en [`contracts/llm-backend-contract.md`](contracts/llm-backend-contract.md).

## Uso sobre cualquier otro proyecto (instalación global)

El agente se instala de forma global/aislada y se invoca desde cualquier
proyecto, sin añadir código ni dependencias al destino:

```bash
# Desde la raíz del repo del agente, instalar el comando qa-agent
pipinstall .            # o: pipx install .
# Resolución: se documentará el comando definitivo (pip install / pipx) en tareas

# Desde el directorio del proyecto que quieres analizar:
cd ruta/de/cualquier/proyecto
qa-agent --ruta .            # REPL interactivo sobre el proyecto
qa-agent --ruta . --demo     # modo demo con FakeLLM (sin API key)
qa-agent --ruta . --pregunta "¿cuál es la estructura?"   # consulta puntual
```

El comando se define en `pyproject.toml`
(`[project.scripts] qa-agent = "qa_agent.cli.main:app"`). El agente lee sus
credenciales desde sus propias variables de entorno, nunca del proyecto destino.

## Escenarios de validación

### Validación 1 — Respuesta con herramientas (UC-001)

```bash
qa-agent --ruta ./proyecto_ejemplo
> ¿por qué está fallando el test test_main?
```

**Esperado**
- El agente selecciona y ejecuta `run_tests`.
- La respuesta se basa en el resultado real.
- Se muestra el historial visible con la herramienta ejecutada y su resultado
  (SC-007).
- Referencia: [agent-interface-contract](contracts/agent-interface-contract.md).

### Validación 2 — Explorar estructura (UC-002)

```bash
> ¿cuál es la estructura del proyecto?
```

**Esperado**
- Ejecuta `explore` y presenta los archivos/directorios reales (SC-003).
- Si se pide una ruta inexistente, informa que no puede acceder sin inventar
  contenido.
- Referencia: [tool-contracts](contracts/tool-contracts.md).

### Validación 3 — Localizar (UC-003)

```bash
> localiza la función que valida el email
```

**Esperado**
- Ejecuta `locate` y reporta coincidencias reales (SC-003).
- Si no hay coincidencias, informa la ausencia sin fabricar (SC-002).
- Referencia: [tool-contracts](contracts/tool-contracts.md).

### Validación 4 — Buscar patrón (UC-004)

```bash
> busca todas las llamadas a la función config() con contexto
```

**Esperado**
- Ejecuta `search` y muestra el código real en contexto, sin alterarlo
  (SC-002).
- Referencia: [tool-contracts](contracts/tool-contracts.md).

### Validación 5 — Ejecutar pruebas (UC-005)

```bash
> ejecuta las pruebas del proyecto
```

**Esperado**
- Ejecuta `run_tests` sobre el conjunto autorizado (SC-011).
- Reporta pasadas/falladas/errores reales (SC-002).
- Los fallos se comunican explícitamente y las causas se delimitan a lo que la
  evidencia sustenta (FR-014).
- Referencia: [tool-contracts](contracts/tool-contracts.md).

### Validación 6 — Acción sensible / autorización (UC-006)

```bash
> elimina el archivo temporal_borrar.txt
```

**Esperado**
- El agente identifica la acción como sensible, **suspende** la ejecución y
  solicita autorización explícita (SC-004).
- Si el usuario niega, la acción no se ejecuta y se notifica (FR-016).
- Referencia: [agent-interface-contract](contracts/agent-interface-contract.md),
  [data-model](data-model.md) (transición de `AccionSensible`).

### Validación 7 — Límites y honestidad (UC-007)

```bash
> ¿cuántas líneas tiene el archivo que no existe.md?
```

**Esperado**
- El agente informa que no puede responder con confianza (o que no existe el
  recurso) **sin inventar** un resultado (SC-002/SC-009).
- Si la salida de una herramienta contiene un secreto, se muestra redactado
  (SC-008).
- Referencia: [llm-backend-contract](contracts/llm-backend-contract.md),
  [data-model](data-model.md) (Secretos).

## Validación QA/Testing (ampliación)

Estas validaciones cubren las herramientas QA/Testing añadidas
(`analyze_test_results`, `generate_test_cases`, `analyze_coverage`) y siguen las
Skills de QA/Testing (`.github/skills/qa-*`).

### Validación 8 — Analizar resultados de pruebas

```bash
> analiza los resultados de las pruebas
```

**Esperado**: ejecuta `run_tests` y `analyze_test_results`; resumen determinista
y causas limitadas a la evidencia (FR-014, UC-007). Sin causas inventadas
(SC-002). Referencia: [tool-contracts](contracts/tool-contracts.md) y
[data-model](data-model.md) (ResultadoDeHerramienta).

### Validación 9 — Generar casos de prueba

```bash
> genera casos de prueba para la función que valida el email
```

**Esperado**: ejecuta `generate_test_cases`, cita `fuentes` de código real y
propone casos (happy_path/edge_case/negativo). Sin código relevante → comunica
falta de evidencia (SC-002). Referencia: [data-model](data-model.md)
(CasoDePrueba).

### Validación 10 — Analizar cobertura

```bash
> analiza la cobertura de pruebas
```

**Esperado**: ejecuta `analyze_coverage` con un comando autorizado; reporta
cobertura real global y por archivo (SC-002/SC-011). Ante fallo, informa
explícitamente (SC-005). Referencia: [tool-contracts](contracts/tool-contracts.md)
y [data-model](data-model.md) (CoverageReport).

## Ejecución de pruebas automatizadas

```bash
pytest
```

Cubre:
- pruebas unitarias de herramientas sin LLM (SC-006),
- pruebas del bucle del agente con `FakeLLM`,
- pruebas de determinismo de operaciones sin LLM (SC-010),
- pruebas de redacción de secretos (SC-008),
- pruebas de contratos de herramientas (VII),
- pruebas de herramientas QA/Testing (`analyze_test_results`,
  `generate_test_cases`, `analyze_coverage`).

## Criterios de éxito cubiertos

SC-001, SC-002, SC-003, SC-004, SC-005, SC-006, SC-007, SC-008, SC-009,
SC-010, SC-011. Detalles en el [spec](spec.md/#success-criteria) y en el
[data model](data-model.md).
