# Implementation Plan: Production Readiness del agente QA

**Branch**: `002-production-readiness` (sobre `john-branch`) | **Date**: 2026-08-21
**Spec**: `specs/002-production-readiness/spec.md`

## Summary

Cerrar la brecha entre lo declarado y lo verificable: primero devolver el
pipeline a verde y hacer el agente portable, luego convertir los ocho ítems
"design complete" en código, empezando por los que desbloquean a los demás.

## Technical Context

**Language/Version**: Python ≥3.11 (verificado también en 3.12; CI amplía a macOS)
**Primary Dependencies**: sin altas nuevas de runtime. Dev: `mypy` opcional.
**Storage**: ficheros JSONL para trazas; fixtures versionados para evaluación.
**Testing**: pytest; suites de seguridad T125–T130 como gate inamovible.
**Target Platform**: Linux, macOS, Windows.
**Project Type**: single project (CLI + librería).
**Performance Goals**: la instrumentación no debe añadir latencia perceptible
(objetivo: <2 % sobre el tiempo de una solicitud en modo demo).
**Constraints**: retrocompatibilidad de esquemas (FR-109); ningún cambio en la
frontera de autorización T125/T126.

## Constitution Check

| Principio | Impacto | Cómo se respeta |
|---|---|---|
| I. Separación | Nuevos módulos de traza y evaluación | La traza es un observador pasivo; no decide nada. El harness vive fuera de `src/`, consume la CLI/API pública. |
| II. Modularidad | Runners nuevos | Detección por manifiesto en un registro extensible; añadir un ecosistema es una entrada de datos, no un `if` más. |
| III. Testabilidad | Todo lo nuevo | Metadatos y trazas se prueban sin LLM real; la detección de runner se prueba sin el runner instalado. |
| IV. Mínimo privilegio | Comandos nuevos | Toda entrada nueva pasa por la allowlist y `shell=False`. Sin excepciones. |
| V. Human-in-the-loop | `--dry-run`, `--json` | `--dry-run` no ejecuta acciones sensibles; `--json` no puede auto-autorizar. |
| VI. Determinismo | Métricas y trazas | Campos temporales aislados y excluidos de las comparaciones de determinismo. |
| VII. Contratos | Ampliación de esquemas | Campos nuevos aditivos; los contratos existentes se actualizan en `contracts/`. |
| VIII. Observabilidad | US3 completa | Este es el principio que hoy queda incumplido; la US3 lo cierra. |
| IX. Errores | `causa_no_ejecutado` | Cada modo de fallo tiene causa explícita; nunca se inventa un resultado. |
| X. Calidad | Ruff limpio | Se eliminan los per-file-ignores de los archivos que este trabajo toca. |
| XI. Credenciales | Trazas y colas de salida | `stdout_tail`/`stderr_tail`/trazas pasan por `Redactor` antes de persistirse. |
| XII. Incremental | Alcance | No se introduce `PolicyEngine` ni framework de orquestación: I16 concluyó KEEP CURRENT LOOP y nada aquí lo contradice. |
| XIII. Documentación | ADR | Cada decisión no obvia queda en un ADR nuevo (ADR-006…). |
| XIV. SDD | Este documento | Ninguna tarea sin requisito; ningún requisito sin criterio de aceptación. |

**Veredicto**: sin violaciones. La única complejidad añadida (harness de
evaluación) está justificada por SC-105 y por la brecha explícita del informe.

## Project Structure

### Documentation (this feature)

```
specs/002-production-readiness/
├── spec.md
├── plan.md
└── tasks.md
docs/adr/
├── ADR-006-execution-metadata.md
├── ADR-007-structured-tracing.md
├── ADR-008-evaluation-harness.md
└── ADR-009-runner-registry.md
```

### Source Code (repository root)

```
src/qa_agent/
├── agent/
│   ├── loop.py                 # instrumentación de traza (mínima, no lógica nueva)
│   └── tracing.py              # NUEVO: EventoDeTraza + emisores
├── tools/
│   ├── base.py                 # validador de esquemas ampliado
│   ├── run_tests.py            # metadatos de ejecución
│   ├── analyze_coverage.py     # metadatos + fix de rutas
│   ├── ejecucion.py            # NUEVO: subproceso portable + metadatos comunes
│   └── runner_registry.py      # NUEVO: detección por manifiesto (Py/.NET/JVM/JS/Go/Rust)
├── security/redactor.py        # patrones Google/Azure
└── cli/main.py                 # banderas nuevas + subcomando eval

evals/                          # NUEVO
├── datasets/
├── tasks.yaml
├── metrics.py
└── run_eval.py
```

**Structure Decision**: `evals/` fuera de `src/` porque es herramienta de
verificación, no producto: no debe entrar en el paquete instalado ni añadir
superficie de importación al agente.

## Fases de ejecución

| Ola | Contenido | Desbloquea |
|---|---|---|
| 0 | Portabilidad + CI verde (US1) | todo lo demás: sin gate fiable no hay evidencia |
| 1 | Metadatos de ejecución (US2) + deuda transversal | US3 y US4 necesitan señal de éxito fiable |
| 2 | Observabilidad (US3) | US4 consume los eventos para métricas |
| 3 | Harness de evaluación (US4) + CLI (US5) | cierra "benchmark readiness" |
| 4 | Ecosistemas (US6) + calidad (mypy, ruff sin ignores) | amplía cobertura |

Cada ola termina con: suite completa verde en macOS local, suites T125–T130
verdes, `ruff check .` limpio.

## Complexity Tracking

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Registro de runners por manifiesto | Cadena de `if` por ecosistema | Añadir Go/Rust/JS con `if` triplicaría la rama que ya era frágil; el registro hace que un ecosistema nuevo sea una fila de datos. |
| Traza JSONL a fichero | Backend de telemetría (OTel) | Dependencia nueva y servidor externo para un CLI local. Constitución XII. El formato JSONL es analizable con las herramientas que ya existen. |
| Harness propio | pytest-benchmark / framework de evals externo | Las métricas requeridas (acierto de herramienta, autorización solicitada) son específicas del dominio; ningún framework las aporta. |
| Validador propio ampliado | `jsonschema` | ADR-002 ya evaluó y rechazó la dependencia con una suite de 92 casos. Se amplía lo propio manteniendo esa decisión. |
| No `PolicyEngine` | Motor central de políticas | I16 concluyó KEEP CURRENT LOOP; la frontera T125/T126 tiene regresión y moverla es riesgo sin beneficio medible. |
