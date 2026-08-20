# Casos de Uso

Este directorio define los **casos de uso** del proyecto **AI QA & Software
Engineering Agent**. Cada caso de uso documenta una interacción completa entre
los actores y el sistema, con el detalle necesario para guiar su
implementación, testing y verificación.

Los casos de uso se derivan de:

- El **README** del proyecto, que define el propósito y el flujo fundamental del
  agente.
- La **Feature Specification** (`specs/001-core-ai-qa-agent/spec.md`), que
  define las historias de usuario, requisitos funcionales y criterios de éxito.
- La **Constitución** (`.specify/memory/constitution.md`), que establece los
  principios de seguridad, mínimo privilegio, human-in-the-loop, determinismo y
  honestidad que condicionan el comportamiento del sistema.

## Formato

Cada caso de uso sigue el **formato UML completo**, que incluye:

- **ID e historial**: identificador único, título, estado y versión.
- **Actores**: quién inicia y participa en la interacción.
- **Descripción**: contexto y objetivo del caso de uso.
- **Disparador**: evento que inicia la interacción.
- **Precondiciones**: condiciones que deben cumplirse antes de que el flujo
  principal pueda iniciarse.
- **Flujo principal**: secuencia numerada de pasos que conducen al resultado
  esperado.
- **Flujos alternativos**: variaciones válidas con un resultado correcto pero
  distinto.
- **Flujos de excepción**: caminos que gestionan condiciones de fallo o
  comportamiento no deseado de forma segura.
- **Postcondiciones**: estado garantizado del sistema al finalizar el caso de
  uso.
- **Trazabilidad**: mapeo a historias de usuario, requisitos funcionales (FR) y
  principios de la constitución.

Cada caso de uso cuenta con un **diagrama en formato mermaid** en la subcarpeta
[`diagramas/`](diagramas/). El
[diagrama general](diagramas/diagrama-general.md) muestra el sistema completo con
sus actores, casos de uso y relaciones.

## Índice

| ID | Caso de uso | Prioridad | Estado |
|----|-------------|-----------|--------|
| [UC-001](UC-001.md) | El agente recibe una solicitud y responde usando herramientas | P1 | Aprobado |
| [UC-002](UC-002.md) | El agente explora la estructura del proyecto | P1 | Aprobado |
| [UC-003](UC-003.md) | El agente localiza archivos y componentes | P2 | Aprobado |
| [UC-004](UC-004.md) | El agente revisa y busca patrones en el código | P2 | Aprobado |
| [UC-005](UC-005.md) | El agente ejecuta y analiza pruebas automatizadas | P2 | Aprobado |
| [UC-006](UC-006.md) | El agente gestiona operaciones con autorización (human-in-the-loop) | P3 | Aprobado |
| [UC-007](UC-007.md) | El agente informa límites y evita inventar información | P3 | Aprobado |
| [UC-008](UC-008.md) | El agente analiza la cobertura de código de las pruebas | P3 | Aprobado |
| [UC-009](UC-009.md) | El agente genera casos de prueba sugeridos | P2 | Aprobado |
| [UC-010](UC-010.md) | El agente planifica y ejecuta una tarea de análisis multi-paso | P1 | Aprobado |
| [UC-011](UC-011.md) | Chat conversacional con memoria, tareas y persistencia de sesión | P1 | Aprobado |
| [UC-012](UC-012.md) | El agente realiza acciones destructivas sobre el proyecto (crear, editar, eliminar archivos) | P2 | Aprobado |
| [UC-013](UC-013.md) | El agente explica con profundidad qué hace cada capa y qué pruebas la cubren (lectura de código) | P2 | Aprobado |

## Trazabilidad general

| Caso de uso | User Story (spec) | Requisitos funcionales |
|-------------|-------------------|------------------------|
| UC-001 | US-1 | FR-001, FR-002, FR-003, FR-004, FR-005, FR-020 |
| UC-002 | US-2 | FR-006, FR-007, FR-008 |
| UC-003 | US-3 | FR-007, FR-008 |
| UC-004 | US-4 | FR-009, FR-010, FR-011 |
| UC-005 | US-5 | FR-012, FR-013, FR-014 |
| UC-006 | US-6 | FR-015, FR-016, FR-025 |
| UC-007 | US-7 | FR-017, FR-018, FR-019, FR-021, FR-022, FR-023 |
| UC-008 | US-10 | FR-030, FR-031 |
| UC-009 | US-9 | FR-028, FR-029 |
| UC-010 | US-11 | FR-032, FR-033, FR-034, FR-035, FR-036 |
| UC-011 | US-12 | FR-037, FR-038, FR-039, FR-040, FR-041 |
| UC-012 | US-13 | FR-042, FR-043, FR-044, FR-045, FR-046, FR-047 |
| UC-013 | US-14 | FR-048, FR-049, FR-050 |

> Nota: UC-006 y UC-007 son casos de uso transversales. Sus reglas aplican como
> restricciones sobre los demás casos de uso en lugar de ser interacciones
> independientes del usuario. En particular, UC-006 (autorización
> human-in-the-loop) condiciona UC-012 (acciones destructivas).

## Diagramas

Los diagramas en formato mermaid para cada caso de uso están en la subcarpeta
[`diagramas/`](diagramas/):

| Diagrama | Descripción |
|----------|-------------|
| [diagrama-general.md](diagramas/diagrama-general.md) | Sistema completo: actores, casos de uso y relaciones (includes / restricciones). |
| [UC-001.md](diagramas/UC-001.md) | Flujo del UC-001 — solicitud, ejecución de herramienta y respuesta. |
| [UC-002.md](diagramas/UC-002.md) | Flujo del UC-002 — exploración de la estructura del proyecto. |
| [UC-003.md](diagramas/UC-003.md) | Flujo del UC-003 — localización de archivos y componentes. |
| [UC-004.md](diagramas/UC-004.md) | Flujo del UC-004 — revisión y búsqueda de patrones en el código. |
| [UC-005.md](diagramas/UC-005.md) | Flujo del UC-005 — ejecución y análisis de pruebas automatizadas. |
| [UC-006.md](diagramas/UC-006.md) | Flujo del UC-006 — autorización human-in-the-loop. |
| [UC-007.md](diagramas/UC-007.md) | Flujo del UC-007 — información de límites y manejo de secretos.
| [UC-008.md](diagramas/UC-008.md) | Flujo del UC-008 — análisis de cobertura de código. |
| [UC-009.md](diagramas/UC-009.md) | Flujo del UC-009 — generación de casos de prueba sugeridos. |
| [UC-010.md](diagramas/UC-010.md) | Flujo del UC-010 — planificación y ejecución multi-paso. |

> **Nota**: UC-011 y UC-012 no disponen aún de diagrama standalone; su flujo se
> refleja en el [diagrama general](diagramas/diagrama-general.md). UC-013 se
> apoya en el diagrama de UC-010 (planificación multi-paso del bucle ReAct) y en
> el contrato `leer_archivo`.
