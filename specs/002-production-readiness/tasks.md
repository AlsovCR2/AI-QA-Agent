# Tasks: Production Readiness del agente QA

**Input**: `specs/002-production-readiness/spec.md`, `plan.md`
**Format**: `[ID] [P?] [Story] Descripción` — `[P]` = paralelizable.

Toda tarea marcada 🔒 toca seguridad, credenciales, human-in-the-loop o
contratos: requiere test explícito y no puede reducir el perímetro existente.

## Phase 0: Portabilidad y gate verde (US1) 🎯 BLOQUEANTE

- [x] **T201** [US1] 🔒 Reemplazar el literal `python` por `sys.executable` en
  `run_tests.py` y `analyze_coverage.py`. Test: el comando construido usa el
  intérprete actual.
- [x] **T202** [US1] Corregir la resolución de ruta de JaCoCo: derivarla del
  manifiesto/estructura del proyecto en vez de reescribir separadores del stdout.
  Test: el fixture Maven pasa en POSIX.
- [x] **T203** [P] [US1] Fijar el ancho de terminal en el test de contrato de CLI
  (T129) para que no dependa del entorno.
- [x] **T204** [US1] Añadir `macos-latest` a la matriz de CI.
- [x] **T205** [US1] Verificar suite completa verde en macOS local.

## Phase 1: Metadatos de ejecución y deuda transversal (US2)

- [x] **T206** [US2] Crear `tools/ejecucion.py`: ejecución de subproceso portable
  que devuelve `MetadatosDeEjecucion` (exit_code, duración, colas redactadas).
- [x] **T207** [US2] 🔒 Ampliar `esquema_salida` de `run_tests` con los campos de
  FR-105 de forma aditiva; actualizar `contracts/tool-contracts.md`.
- [x] **T208** [US2] Implementar la taxonomía `causa_no_ejecutado` de FR-106.
- [x] **T209** [US2] 🔒 Aplicar lo mismo a `analyze_coverage`, distinguiendo
  "comando falló" de "reporte no encontrado".
- [x] **T210** [P] [US2] 🔒 Añadir patrones Google (`AIza…`) y Azure al `Redactor`,
  con test positivo y de falso positivo cada uno.
- [x] **T211** [P] [US2] Añadir `htmlcov`/`coverage` a la política de exclusión y
  podar artefactos por descendiente en `explore`.
- [x] **T212** [US2] Ampliar el validador de esquemas con `additionalProperties`,
  `pattern`, `oneOf`/`anyOf`, `minLength`/`maxLength` y motivo de rechazo, sin
  cambiar el veredicto de los 92 casos de compatibilidad existentes.

## Phase 2: Observabilidad (US3)

- [x] **T213** [US3] Crear `agent/tracing.py` con `EventoDeTraza` y un emisor
  JSONL que redacta antes de escribir.
- [x] **T214** [US3] 🔒 Instrumentar el bucle: un evento por paso con duración,
  estado y decisión de autorización, sin alterar la lógica de decisión.
- [x] **T215** [US3] Registrar la razón de parada del bucle (FR-113).
- [x] **T216** [US3] Garantizar que un fallo de escritura de traza no aborta la
  solicitud, y probarlo con un destino no escribible.

## Phase 3: Evaluación y CLI (US4, US5)

- [x] **T217** [US4] Crear `evals/` con proyectos de referencia, `tasks.yaml`,
  `metrics.py` y `run_eval.py`.
- [x] **T218** [US4] Implementar las cinco métricas de FR-115.
- [x] **T219** [US5] 🔒 Añadir `--json`, `--no-color`, `--max-steps`, `--model`,
  `--base-url`, `--dry-run`, `--trace-file`.
- [x] **T220** [US5] 🔒 `--dry-run` no ejecuta acciones sensibles; test de que una
  solicitud destructiva no toca el disco.
- [x] **T221** [US4] Exponer `qa-agent eval` y su salida JSON.
  **Desviación:** implementado como bandera `qa-agent --eval [--json]`, no como
  subcomando. `cli/main.py` es una app Typer de un solo `@app.command()`; añadir
  un segundo comando obligaría a `qa-agent <subcomando> ...` y rompería el
  contrato de CLI de T129. Justificado en ADR-008.
- [x] **T222** [US5] Extender el test de contrato de CLI a las banderas nuevas.

## Phase 4: Ecosistemas y calidad (US6)

- [x] **T223** [US6] Crear `tools/runner_registry.py` con detección por
  manifiesto para Python, .NET, Maven, Gradle, JS/TS, Go y Rust.
- [x] **T224** [US6] 🔒 Extender la allowlist de comandos a los runners nuevos,
  manteniendo `shell=False`.
- [x] **T225** [US6] Cablear `runner_detection.py` del agente al registro.
- [x] **T226** [P] Externalizar las tablas de intención a configuración
  declarativa con tests parametrizados.
- [x] **T227** Eliminar los per-file-ignores de Ruff de los archivos tocados.
- [x] **T228** Evaluar y adoptar `mypy` en alcance acotado.
  Verificado 2026-08-21 con mypy 1.20.2: "Success: no issues found in 7 source
  files". Declarado en las extras `dev` y añadido como paso del job `quality`
  SOLO tras verlo pasar en local.

## Phase 5: Cierre

- [x] **T229** ADR-006…ADR-009 para las decisiones no obvias.
  ADR-006 (metadatos de ejecución), ADR-007 (traza estructurada), ADR-008
  (harness de evaluación), ADR-009 (registro de ecosistemas).
- [x] **T230** Gate final: suite completa, T125–T130, `ruff check .`, `pip check`,
  y CI verde en un push real.

## Dependencies & Execution Order

- Phase 0 bloquea todo: sin gate fiable no hay evidencia de nada.
- T206 bloquea T207/T209 (fuente común de metadatos).
- T213 bloquea T214/T215/T216.
- T217/T218 dependen de T213 (las métricas leen eventos) y de T208 (señal de
  éxito fiable).
- T223 bloquea T224/T225.
- T210, T211, T226 son independientes: paralelizables en cualquier momento.

## Evidencia de verificación (2026-08-21, macOS 27.0.0 / Python 3.14.7)

Lo que se ejecutó de verdad, no lo que se supone:

| Comprobación | Resultado |
|---|---|
| `python -m pytest -q` | 707 passed |
| `python -m ruff check .` | All checks passed |
| `python -m mypy` | Success: no issues found in 7 source files |
| `python -m pip check` | No broken requirements found |
| `qa-agent --eval --demo` | 6/6 tareas, puntuación global 1.00, exit 0 |

`ruff format` sigue SIN adoptarse (99/198 archivos se reformatearían). Es la
misma deferral de ADR-003 y no forma parte del gate; no se ha añadido un paso
de CI para ella.

**Poder discriminante del harness (verificado, no asumido):** una corrida con
expectativas deliberadamente mutadas —herramienta que el agente no usa,
evidencia inexistente, autorización exigida donde no toca— baja las métricas
correspondientes a 0.00 y la global a 0.875. El 1.00 de la corrida real es un
aprobado, no un banco que aprueba cualquier cosa.

## Hallazgos del primer push a CI (run 32508477617)

Los 6 jobs de test pasaron en ubuntu/macos/windows × Python 3.11/3.12, y el
paso de mypy añadido por T228 pasó en CI. Falló `pip-audit`, y el fallo era
real: setuptools 79.0.1 —el preinstalado del runner— arrastra
PYSEC-2026-3447, corregido en 83.0.0.

Corregido subiendo el suelo de `[build-system].requires` a `setuptools>=83` y
actualizando el setuptools del entorno antes de auditar. **No** se usó
`--ignore-vuln`: un audit que silencia lo que encuentra no es un audit.

Aparte, se cerró un hueco de cobertura encontrado al revisar T215:
`presupuesto_agotado` era la única de las cinco razones de parada de FR-113 sin
ningún test. `test_razon_de_parada_presupuesto_agotado` la cubre fijando el
borde por los dos lados (con presupuesto justo y con uno más), para que una
implementación que devolviera esa razón siempre tampoco pasara.

## Defecto encontrado probando con modelo real (2026-08-21)

Ejecutando el agente contra Gemini (`gemini-3.5-flash-lite`, sin `--demo`)
apareció un fallo en la razón de parada de FR-113 que ningún test detectaba:
una solicitud que se completaba con éxito y confianza alta se reportaba como
`pendiente_autorizacion`.

Causa: `respuesta.acciones` es el historial visible de la sesión ENTERA, no el
de la solicitud actual. `_razon_de_parada` clasificaba sobre ese acumulado, así
que una acción pendiente arrastrada marcaba a todas las solicitudes
posteriores. Se manifiesta en el flujo interactivo de la CLI, que llama a
`atender()` dos veces sobre el mismo agente —sin decisión y luego con ella—,
que es exactamente el camino de toda acción sensible autorizada.

Ningún test lo cogía porque todos estrenaban agente por caso, y con agente
fresco la clasificación es correcta.

Arreglado marcando el corte del historial al empezar la solicitud y
clasificando solo lo posterior. Cubierto por dos tests que fallan si se
neutraliza el arreglo (comprobado). Verificado de nuevo contra Gemini: el
evento de cierre pasa de `pendiente_autorizacion` a `evidencia_suficiente`.

## Fiabilidad de la edición asistida (medido 2026-08-21)

Tarea: "corrige la función `mediana`" sobre un módulo real de 50 líneas, con
Gemini 3.5 Flash Lite. Se cuenta como éxito solo si la corrección se aplica Y
las 21 pruebas del proyecto siguen pasando.

| Estado del código | Resultado |
|---|---|
| Reescritura de archivo completo | ~1 de 4; el resto DESTRUÍA el módulo |
| + validación de sintaxis previa a escribir | 0 destrozos; ~1 de 4 aplicaba |
| + `funciones` (localización por `ast`) | 4-6/10 por CLI, 5/5 por API |
| + reutilización del plan aprobado | **20/20** |

Los tres saltos vienen de defectos reales, no de reescribir el prompt:

1. El planificador reventaba con cualquier parámetro de tipo lista
   (`unhashable type: 'list'`), dejando la solicitud sin ningún paso.
2. La CLI resolvía UNA sola ronda de autorización; con dos acciones sensibles
   la segunda quedaba suspendida en silencio.
3. Al autorizar se replanificaba desde cero, así que el permiso concedido para
   una acción podía ejecutar otra distinta.

**Nota de método:** las dos primeras tandas dieron 9/10 y 5/10. Los seis fallos
eran 429 del proveedor, no del modelo: el arnés lanzaba corridas seguidas y
agotaba la cuota por minuto. Con 45 s entre corridas, 20/20. Que esos 429 fueran
diagnosticables se debe al arreglo de la misma sesión que dejó de tragarse los
errores del proveedor durante la planificación; antes se habrían contado como
fallos del modelo.
