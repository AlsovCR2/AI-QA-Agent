# Phase 0: Research — Core AI QA & Software Engineering Agent

Producción del `/speckit-plan` (Phase 0). Resuelve las incógnitas técnicas
(decisiones de Plan/Implementation) que el spec dejó abiertas, y documenta las
decisiones fundamentadas en la constitución.

## Decisiones

### D1: Lenguaje y versión

- **Decision**: Python 3.11+ (compatible con la versión 3.14 instalada).
- **Rationale**: El README fija Python como lenguaje del proyecto. Python
  ofrece entorno REPL/CLI idóneo, stdlib suficiente (pathlib, subprocess,
  dataclasses, logging) y ecosistema de testing maduro (pytest).
- **Alternatives considered**: Node.js/TypeScript, Go. Rechazados por
  contradicción con el README y por la menor madurez del ecosistema LLM
  agnóstico requerido sin justificación adicional.

### D2: Framework de agentes

- **Decision**: Implementar un bucle agente-herramienta propio y mínimo, sin
  framework de agentes externo.
- **Rationale**: El spec fija que el framework de agentes es decisión de Plan,
  y la constitución exige independencia del framework/proveedor. Un bucle propio
  (interpretar → seleccionar → ejecutar → validar → responder) de ~100-200 LOC
  es la opción más simple y controlable, y maximiza determinismo (VI) y
  testabilidad (III) sin acoplar el proyecto a la API de un framework que
  evoluciona rápido.
- **Alternatives considered**: LangChain, CrewAI, AutoGen, OpenAI Agents SDK.
  Rechazados: añaden acoplamiento, complejidad y opacidad sin necesidad
  justificada para el MVP (principio XII), y dificultan el determinismo (VI).

### D3: Proveedor del modelo de lenguaje

- **Decision**: Abstraer el LLM tras la interfaz `LLMBackend` (Strategy) e
  implementar un único `OpenAICompatibleBackend` configurable por variables de
  entorno. **Proveedor por defecto: DeepSeek**; **alternativos opcionales:
  NVIDIA NIM (gratis) y OpenAI**. Para pruebas: `FakeLLM` determinista.
- **Rationale**: El spec deja el proveedor como decisión de Plan. Aislarlo tras
  una interfaz respeta la independencia del proveedor y permite probar el agente
  sin LLM real (principio III, FR-003, SC-006). Se elige **DeepSeek como
  proveedor principal** (ya en uso, coste muy bajo: V4-Flash ~$0.14/$0.28 por 1M
  tokens) y **NVIDIA NIM como alternativa gratuita** (deepseek disponible gratis
  vía NIM, coste cero en free tier), manteniendo OpenAI como opción estándar.
  Como todos exponen API compatible con Chat Completions, basta cambiar
  `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY`.
- **Alternatives considered**: Anthropic, Google Gemini, Ollama local.
  Cualquiera puede implementarse como un `LLMBackend` adicional sin tocar el
  núcleo.

### D4: Conjunto de herramientas (MVP)

- **Decision**: Cuatro herramientas alineadas a los casos de uso:
  - `explore` → explorar estructura del proyecto (UC-002).
  - `locate` → localizar archivos/componentes (UC-003).
  - `search` → revisar/buscar patrones en código (UC-004).
  - `run_tests` → ejecutar y analizar pruebas (UC-005).
- **Rationale**: Cada `UC-002..005` requiere una herramienta con contrato
  claro. El conjunto cubre las tareas de análisis/exploración/validación del
  README y del spec. La modularidad (II) permite añadir más posteriormente.
- **Alternatives considered**: incluir decenas de herramientas (git, lint,
  etc.) desde el inicio. Rechazado por principio XII (evolución incremental).

### D5: Framework de testing

- **Decision**: `pytest`.
- **Rationale**: Estándar de facto en Python, soporta fixtures (FakeLLM,
  proyecto temp), parámetrización y marcado. Permite probar herramientas sin
  LLM (SC-006) y validar contratos.
- **Alternatives considered**: `unittest` (stdlib). Adecuado pero menor
  ergonomía y soporte de fixtures; disponible como respaldo.

### D6: Gestión de secretos y configuración

- **Decision**: Variables de entorno + `python-dotenv` para cargar
  `LLM_API_KEY`; redactor de secretos en el núcleo y logs.
- **Rationale**: La constitución (XI) prohíbe secretos en código. Se usa
  `.env` (no versionado, con `.env.example` como plantilla) y un `Redactor`
  (FR-021, SC-008) que filtra secretos detectados de respuestas, historial y
  logs.
- **Alternatives considered**: gestores de secretos externos (Vault). Exceso de
  infraestructura para el MVP; se deja como evolución.

### D7: Mínimo privilegio

- **Decision**: `allowlist` de rutas autorizadas; las herramientas ejecutan solo
  sobre rutas permitidas y nunca comandos peligrosos arbitrarios.
- **Rationale**: Constitución IV (FR-025, SC-011). `run_tests` solo opera sobre
  conjuntos de pruebas autorizados; ninguna herramienta ejecuta comandos
  peligrosos fuera de un contrato acotado.
- **Alternatives considered**: ejecutar comandos genéricos del usuario.
  Rechazado: viola mínimo privilegio.

## Adecuación de aprendizajes al dominio

- **Bucle agente-herramienta**: en el dominio agentic AI, el patrón
  "reAct"-ligero (razonar → actuar → observar) se implementa aquí como un
  bucle determinista donde la selección de herramienta es la única parte que
  puede requerir el LLM. Esto preserva el determinismo (VI) para todo lo demás.
- **Contrato de herramienta**: se formaliza un esquema JSON de entrada/salida
  validable, alineado con el principio VII. La validación es determinística y no
  depende del LLM.
- **Human-in-the-loop**: se modela como estado de autorización suspendido hasta
  confirmación, alineado con el principio V y los patrones de aprobación de
  herramientas de los frameworks (pero aislado del proveedor).

## Riesgos y mitigaciones

### D8: Extensión QA/Testing del conjunto de herramientas

- **Decision**: Ampliar el MVP con tres herramientas adicionales
  `analyze_test_results`, `generate_test_cases` y `analyze_coverage`,
  como componentes modulares que no alteran las herramientas existentes.
- **Rationale**: Cubren capacidades QA/Testing concretas del dominio (analizar
  resultados, generar casos de prueba, analizar cobertura) alineadas con el
  propósito del proyecto. Se incorporan conforme a la evolución incremental
  (XII) pero con una necesidad funcional justificada por el dominio QA/Testing,
  y documentadas antes de implementarse (XIV). Se mantienen **desacopladas** de
  las Skills (ver D9).
- **Alternatives considered**: ampliar con linting/checkstyle. Rechazado por
  falta de evidencia de necesidad concreta frente a las tres seleccionadas.
- **Separación herramienta/skill**: las herramientas ejecutan; su uso se orienta
  mediante Skills (SKILL.md) separadas (D9). No hay acoplamiento entre ambos.

### D9: Skills de QA/Testing (SKILL.md)

- **Decision**: Definir Skills estilo Anthropic/SpecKit (archivos `SKILL.md`)
  que documentan **metodologías, criterios y procedimientos** sobre cómo el
  agente debe usar sus herramientas QA/Testing.
- **Rationale**: Responden a la necesidad de conocimiento especializado que
  oriente al agente sin mezclarlo con la implementación. Respeta el principio de
  separación de responsabilidades (I): la herramienta es la capacidad ejecutable;
  la skill es el procedimiento/ criterio de uso.
- **Alternatives considered**: incrustar el conocimiento en el código de cada
  herramienta. Rechazado: acopla metodología con implementación y rompe el
  desacople requerido.
- **Nota**: una skill **no contiene** la implementación de una herramienta.
  Define cuándo utilizar cada herramienta, la secuencia esperada de uso y los
  criterios de aceptación de sus resultados.

### D10: Bibliotecas de soporte (no reinventar ruedas)

- **Decision**: Declarar un conjunto de bibliotecas de soporte para zonas
  periféricas sin sustituir el núcleo del agente:
  `openai` (SDK del proveedor), `python-dotenv` (secretos/entorno),
  `pydantic` (validación de contratos), `typer` (CLI), `rich` (salida legible),
  `pathspec` (patrones de rutas/allowlist) y `pytest` (testing).
- **Rationale**: Reducen complejidad y dificultad resolviendo problemas ya
  resueltos (validación, CLI, rendering, coincidencia de rutas), evitando código
  propio propenso a errores. Se mantiene la restricción de **no usar framework
  de agentes** y de **mantener el bucle y las herramientas deterministas en
  Python puro** (principios VI, III): las librerías solo asisten la periferia
  (validación, entrada/salida, UX), no el núcleo de razonamiento del agente.
- **Alternatives considered**: Python puro con stdlib para todo (argparse,
  dataclasses, etc.). Rechazado parcialmente: aumenta boilerplate y riesgo de
  bugs en validación/CLI sin aportar control al núcleo. Se descarta usar un
  framework de agentes completo (D2).
- **Regla de uso**: cada librería queda aislada en su capa; el núcleo
  (`loop.py`, herramientas deterministas, `Redactor`) no depende de ellas.

| Riesgo | Mitigación |
|--------|------------|
| Latencia/variabilidad del LLM | Aislar el LLM tras `LLMBackend`; las respuestas de herramienta son deterministas; el LLM solo afecta interpretación/selección/respuesta. |
| Fuga de secretos | `Redactor` aplicado siempre antes de emitir respuestas, historial visible y logs (FR-021). |
| Acciones destructivas | `authorization.py` suspende hasta autorización explícita (FR-015/016). |
| Comandos peligrosos | Allowlist de rutas y contratos acotados (FR-025). |
| Inventar información | Validación de contratos + regla de honestidad (FR-019); el agente reporta solo resultados reales validados. |

## Resultado

Todas las incógnitas de Technical Context quedan resueltas y documentadas. No
quedan `NEEDS CLARIFICATION` pendientes. El plan puede avanzar a la Fase 1 de
diseño.
