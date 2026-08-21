# ADR-008: Harness de evaluación conductual (T217–T218, T221)

- Status: Accepted
- Date: 2026-08-21
- Related: `specs/002-production-readiness/spec.md` (FR-114–117),
  `src/qa_agent/evaluacion/`, `evals/`, `src/qa_agent/cli/evaluacion.py`,
  `tests/unit/test_evaluacion.py`
- Principios: VI (determinismo), XII (no añadir dependencias sin justificarlas),
  FR-019 (nada de auto-juicio del modelo)

## Contexto

La suite tiene 704 tests en verde y aun así no responde a la única pregunta que
importa en un agente: *¿se comportó bien?* Un agente puede pasar todos los tests
unitarios y sin embargo elegir la herramienta equivocada, responder sin haber
mirado el proyecto, o ejecutar algo sensible sin pedir permiso. Esos tres
fallos no son excepciones: son salidas bien formadas.

## Decisión

Un harness que ejecuta tareas declaradas contra proyectos de referencia
versionados y puntúa con cinco métricas calculadas **sobre la traza** de
ADR-007: acierto de herramienta, anclaje en evidencia, cumplimiento de
seguridad, eficiencia de pasos y latencia.

## Ruling: motor dentro del paquete, datos fuera

El motor (`src/qa_agent/evaluacion/`) es código instalable y con pruebas. El
conjunto de tareas y los proyectos de referencia viven en `evals/`, fuera del
paquete.

Motivo: son datos de verificación. Meterlos en el paquete los haría viajar en la
distribución —proyectos Go, Node y Python completos— y ampliaría la superficie
de importación con módulos que solo existen para ser analizados, no ejecutados.
`raiz_de_evals()` los localiza buscando hacia arriba, para que el harness
funcione desde la raíz, desde un subdirectorio o desde una instalación editable.

## Ruling: JSON, no YAML

`tasks.json` en vez de `tasks.yaml`, pese a que el plan original decía YAML.

PyYAML sería una dependencia nueva en tiempo de ejecución a cambio de comas y
comillas. El principio XII pide justificar cada dependencia por lo que aporta;
aquí no aporta nada que el formato no resuelva ya. La tarea T217 se cumple en su
intención —conjunto de tareas declarativo y versionado— y se desvía en el
formato por una razón explícita.

## Ruling: nada de LLM-as-judge

Ninguna métrica consulta al modelo para puntuar al modelo. Todas se derivan de
evidencia observable: qué herramientas se ejecutaron con éxito (traza), si se
pidió autorización (traza), si la respuesta cita evidencia real del proyecto,
cuántos pasos se usaron frente al óptimo declarado.

Usar un LLM como juez introduce exactamente la circularidad que el proyecto
evita en FR-019: el mismo sistema cuyo sesgo se quiere medir produce la medida.
Un agente que alucina una respuesta convincente tiende a juzgarla convincente.

## Ruling: `acierto_de_herramienta` no exige exclusividad

Se puntúa 1.0 si la herramienta esperada llegó a ejecutarse, aunque se hayan
ejecutado otras. Un agente que explora antes de leer está razonando bien, no
fallando; penalizar los pasos extra ahí sería premiar la adivinación. El coste
de los pasos de más ya lo captura `eficiencia_de_pasos`, que es la métrica cuyo
trabajo es ese.

Simétricamente, `eficiencia_de_pasos` no puntúa por encima de 1.0 cuando se usan
MENOS pasos que el óptimo: resolver con menos evidencia de la esperada es un
problema, no una virtud, y lo penaliza `anclaje_evidencia`.

## Ruling: `--eval`, no un subcomando `eval`

T221 pedía literalmente "exponer `qa-agent eval`". Se implementó como bandera
`qa-agent --eval [--json]`.

Motivo: `cli/main.py` es una app Typer de **un solo** `@app.command()`. Añadir
un segundo comando convierte a Typer en una app multi-comando, y entonces
`qa-agent "analiza mi proyecto"` deja de funcionar — pasa a exigir un
subcomando. Eso rompería el contrato de CLI que cubre T129 y, más importante,
la forma en que se usa el agente. Una bandera cumple la intención de la tarea
(la evaluación es invocable y emite JSON) sin ese coste.

El puente vive en `cli/evaluacion.py` con importación diferida, para que el
arranque normal no pague el coste de importar el harness. Devuelve código de
salida 1 por debajo de `UMBRAL_APROBACION` (0.75) y 2 si no encuentra el
conjunto, de modo que sirva de gate de CI sin envolverlo en un script.

## Ruling: un agente nuevo por tarea

`_construir_agente_de_evaluacion` estrena agente en cada tarea. Compartirlo
dejaría que el historial de sesión de una tarea influyera en la siguiente, y las
puntuaciones dependerían del orden del archivo (VI).

## Consecuencias

- Con `FakeLLM`, dos corridas dan métricas idénticas salvo latencia (SC-105).
- `qa-agent --eval --json` expone el resultado como dato, no como texto.
- Añadir un ecosistema a la evaluación es añadir un proyecto en `evals/datasets/`
  y una fila en `tasks.json`; no se toca el motor.
- Las métricas miden comportamiento observable. Lo que **no** miden es la
  calidad redaccional de la respuesta — deliberadamente, porque medir eso sin
  un juez humano exigiría el LLM-as-judge que este ADR descarta.
