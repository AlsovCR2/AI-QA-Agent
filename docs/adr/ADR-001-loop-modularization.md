# ADR-001: Modularize `agent/loop.py`

- Status: Accepted (partially executed — see "Stopping point" below)
- Date: 2026-08-20
- Owner: Person 1 (`work/person-1`)
- Backlog items: I01 (modularize `loop.py`), I02 (relocate hardcoded intent
  phrase/regex tables) — `docs/improvements/qa-agent-improvement-backlog.md`,
  `docs/tareas-divididas.md`
- Authority: advisory backlog only. Does not modify the Constitution, Spec,
  Plan, contracts, or `tasks.md`. Does not introduce new FR/SC/US (XIV). The
  immutable T125–T131 remediation behavior is a hard constraint on every
  extraction in this ADR, not a goal to be traded off against line count.

## Problem

`src/qa_agent/agent/loop.py` started at 1,947 physical lines and mixed:

1. Hardcoded intent-phrase tables and regexes (global-analysis detection,
   test-suggestion detection, layer/folder detection) — I02.
2. Project-type/runner detection (marker files → pytest/dotnet/mvn/gradle
   commands).
3. Deterministic plan enrichment (explore-by-layer, locate+generate for test
   suggestions, exhaustive layer reads) that compensates for LLM plans that
   don't see the real filesystem tree.
4. Response-grounding honesty checks (SC-017 / FR-019: don't let the LLM's
   final text claim facts absent from real observations).
5. Parameter/path preparation for each tool.
6. Authorization + execution of the ReAct loop (T125/T126 security boundary).
7. Filesystem "rail" correction (resolving LLM-proposed paths/layers against
   the real tree before authorization/execution).
8. The `atender`/`_atender_una_pasada`/`_atender_react` orchestration entry
   points themselves.

That's at least eight distinct responsibilities in one file/class, which
raises regression surface and makes it hard to unit-test any one heuristic
without spinning up the whole `Agent`.

## Extraction plan and risk ordering

Per the task brief: extract low-risk pure-logic pieces first, one
responsibility per commit, run the focused tests plus the full suite after
each; leave the T125/T126 authorization/execution boundary in `loop.py`
unless extraction risk is clearly justified by a regression test proving
parity. `loop.py` remains the lifecycle/orchestration entry point — success
is cohesion of responsibilities, not a specific line count.

| Order | Extraction | New module | Risk | Rationale |
|---|---|---|---|---|
| 1 | Intent-phrase tables (I02): global-analysis phrases, test-suggestion phrases | `agent/intent_policy.py` | LOW | Pure string matching, no `self`, already had characterization tests written before the move |
| 1 | Layer/folder detection (I02): connectors, verbs, regex, real-filesystem resolution | `agent/layer_policy.py` | LOW | Same as above; `_resolver_capa_real` takes `base`/`capa` as plain args already |
| 2 | Runner/coverage command detection | `agent/runner_detection.py` | LOW | Pure marker-file lookup, no `self`, already directly imported by `tests/unit/test_deteccion_runner.py` |
| 3 | Response-grounding honesty check | `agent/grounding.py` | LOW | Neither function used `self`; single call site in `_respuesta_react` |
| 4 | Deterministic plan enrichment (3 `_enriquecer_plan_*` routines + shared helpers) | `agent/plan_enrichment.py` | MEDIUM | Mutates the `Plan` object and reads the tool catalog; kept as pure functions taking `herramientas`/`ruta_base` explicitly instead of `self`, backed by the pre-existing `test_profundidad_analisis.py` / `test_profundidad_capa.py` / `test_intencion_pruebas.py` suites (121 tests) that exercise this exact logic end-to-end through `Agent.atender` |
| — | Authorization/execution boundary (`_ejecutar_siguiente_paso`, `_atender_react`, `_atender_una_pasada`, `_parametros_para`, `_resultado_de_pruebas`) and filesystem rail helpers (`_resolver_archivo_real`, `_corregir_escritura`, `_buscar_archivo_por_nombre`, `_buscar_directorio_por_nombre`, `_resolver_directorio_real`, `_capas_reales`, `_encolar_explore_capas_reales`) | *(stays in `loop.py`)* | HIGH | Deliberately **not extracted** — see "What stays and why" |

Each extraction is its own commit:

1. `test: characterize loop.py intent/layer detection before I02 extraction`
2. `refactor: centralize deterministic intent policy (I02)`
3. `refactor: extract runner/coverage command detection from agent loop (I01)`
4. `refactor: extract response-grounding honesty check from agent loop (I01)`
5. `refactor: extract plan enrichment from agent loop (I01)`

## Extraction technique: import, don't reimplement; delegate, don't rewire

Two techniques kept every extraction low-risk and independently revertible:

- **Re-export by import** (`intent_policy.py`, `layer_policy.py`,
  `runner_detection.py`): `loop.py` imports the exact function object from
  the new module under its original private name (e.g.
  `from qa_agent.agent.intent_policy import _es_analisis_global`). Existing
  test files that do
  `from qa_agent.agent.loop import _es_analisis_global` keep working
  unchanged — Python binds the same function object, so
  `loop._es_analisis_global is intent_policy._es_analisis_global` holds
  (asserted directly in
  `tests/unit/test_intent_layer_policy_characterization.py`).
- **Thin delegator methods** (`plan_enrichment.py`): `Agent` keeps
  same-named, same-signature methods (`_enriquecer_plan_analisis_global`,
  etc.) that just forward to the module-level function with `self._herramientas`
  and `self._ruta_base()` supplied explicitly. This means the ReAct loop's
  call sites in `_atender_react` needed **zero** changes — the extraction is
  invisible to every other part of `loop.py`.

Both techniques mean a single extraction can be reverted with
`git revert <commit>` without touching any other commit in the series: the
public names and call sites loop.py exposes never moved, only their
implementation did.

## What stays in `loop.py` and why

After the four extractions above, `loop.py` (1,358 lines, down from 1,947)
retains:

- **`Agent.__init__`, `sesion`, `_registrar_accion`, `_seleccionar_herramienta`,
  `_ruta_base`, `_tiene_evidencia_real`** — core object state and the
  deterministic-routing-then-LLM-fallback entry point (VI/III). Small,
  cohesive, genuinely orchestration.
- **`atender`, `_atender_una_pasada`, `_atender_react`** — the lifecycle
  entry points themselves. This is what "loop.py stays the
  lifecycle/orchestration entry point" means concretely: these functions
  decide single-pass vs. ReAct, drive the percieve→plan→act→observe→reflect
  cycle, and are the seam every external caller (`Agent.atender`, the public
  contract in `agent-interface-contract.md`) depends on. Splitting them
  further would fragment control flow across modules for no cohesion gain.
- **`_ejecutar_siguiente_paso`, `_ejecutar_herramienta`, `_parametros_para`,
  `_resultado_de_pruebas`, `_validar_y_usar`** — the T125/T126 boundary:
  this is where parameters are validated against schema, the allowlist is
  consulted (FR-025), authorization is created/checked/denied
  (`GestorDeAutorizacion`), and the tool is actually invoked. `_resultado_de_pruebas`
  in particular runs `run_tests` as a side effect and writes to `self._sesion`
  — moving it out would require passing a session-mutation callback across a
  module boundary, which increases risk without a clear cohesion win. Per
  the task's explicit constraint, this cluster is not extracted "purely to
  hit a line-count target" — doing so would need a dedicated regression
  suite proving zero drift in the exact classification semantics T130 froze
  (success / ordinary failure / zero tests / contradictory output /
  unsupported output / spawn failure / timeout) and in the "pending/denied
  authorization ⇒ zero target subprocess calls" invariant (T126). That is a
  larger, security-focused effort that deserves its own ADR/session rather
  than being folded into this pass.
- **Filesystem "rail" helpers** (`_resolver_archivo_real`, `_corregir_escritura`,
  `_buscar_archivo_por_nombre`, `_buscar_directorio_por_nombre`,
  `_resolver_directorio_real`, `_capas_reales`, `_encolar_explore_capas_reales`)
  — these resolve LLM-proposed paths/layers against the *real* filesystem
  immediately before authorization/execution (FR-019/FR-025), so they sit
  directly on the same security-sensitive path as the T125/T126 boundary
  above. Same reasoning: left in place.
- **`_respuesta_react`, `_recomendaciones_redactadas`** — final response
  assembly; small, already delegates the actual honesty check to
  `grounding._afirmaciones_no_ancladas`.

This matches Constitution X (no needless abstraction) and XII (incremental
evolution): the remaining code is cohesively "decide/authorize/execute/
respond", which is what an agent loop's orchestration layer is supposed to
contain. Cohesion, not line count, is the success criterion the task brief
sets, and that criterion is met — every extracted module now has a single,
nameable responsibility (intent detection, layer detection, runner
detection, plan enrichment, response grounding), and every remaining
`loop.py` responsibility is one of: public entry point, authorization/
execution boundary, or the filesystem rails that feed that boundary.

## Rollback

Each commit is self-contained and revertible independently:

- Reverting an "import, don't reimplement" commit (`intent_policy.py`,
  `layer_policy.py`, `runner_detection.py`) removes the new module and
  restores the original in-`loop.py` definitions verbatim (they were moved,
  not edited), because `loop.py`'s call sites reference the same private
  names throughout.
- Reverting the `plan_enrichment.py` commit restores the original method
  bodies on `Agent` verbatim; no other file needs to change because nothing
  outside `loop.py` calls `plan_enrichment` directly (it's an internal
  collaborator, not part of the public contract).
- No commit changes `specs/001-core-ai-qa-agent/contracts/agent-interface-contract.md`
  or any other public contract — `Agent.atender`'s signature and behavior
  are unchanged throughout.

## Testing evidence

- Baseline before any change: 354 passed (`python -m pytest -q`).
- Characterization tests added *before* the I02 move
  (`tests/unit/test_intent_layer_policy_characterization.py`), confirmed
  green against the original `loop.py` code, then confirmed green again
  (via re-export) after the move — plus two identity assertions
  (`is`) proving the re-exported names are the same function objects, not
  reimplementations.
- New direct-unit coverage for the newly extracted modules:
  `tests/unit/test_grounding.py` (grounding.py, isolated from `Agent`/LLM).
  `runner_detection.py` and `plan_enrichment.py` are covered end-to-end by
  the pre-existing `test_deteccion_runner.py` / `test_profundidad_analisis.py`
  / `test_profundidad_capa.py` / `test_intencion_pruebas.py` suites, which
  were written against `loop.py`'s original behavior and required **zero**
  changes to keep passing after each extraction — the strongest available
  evidence of behavior parity.
- Full suite after every commit: 354 → 363 (I02 characterization) → 365
  (runner_detection) → 371 (grounding) → 371 (plan_enrichment, no new
  tests added in that commit; regression proven by the existing 121-test
  `test_profundidad_*`/`test_intencion_pruebas` suites staying green).
  Final: **371 passed**, 0 failed.
- `python -m pip check`: clean (unchanged; no new dependency was added).

## Note on this environment's editable install

While executing this ADR's extractions, `pip show qa-agent` resolved to a
different, stale checkout (`C:\Users\<user>\qa-agent`) rather than this
worktree. Every `pytest` invocation in this branch's history was run with
`PYTHONPATH` pointing at this worktree's `src/` to guarantee the tests
exercised the code actually being changed here. Anyone re-running the suite
against this branch should do the same
(`PYTHONPATH="$(pwd)/src" python -m pytest -q`) until the editable install
is repointed at this worktree.

## Stopping point for I01

I01 is **not** "fully flattened" — and that is the intended outcome, not an
unfinished task. The task brief's own success criterion is: "I01 is done
when remaining `loop.py` responsibilities are justifiably orchestration-related
— you decide when that point is reached and record your reasoning." That
point has been reached: five extractions removed ~590 lines of non-orchestration
logic (intent detection ×2, runner detection, response grounding, plan
enrichment) into five single-responsibility modules, each independently
testable without `Agent` or an LLM backend (Constitution III). What remains
in `loop.py` is the lifecycle entry point plus the T125/T126 authorization/
execution boundary and its immediate filesystem-rail dependencies — exactly
the security-sensitive cluster the task brief says to extract "last, and
only if you have time and confidence" backed by a parity-proving regression
test, and explicitly permits leaving in place if "extraction risk isn't
justified." Given the MVP's zero-tolerance for T125/T126 regressions and the
absence of a dedicated regression suite proving classification-semantics
parity for that cluster, leaving it in `loop.py` is the documented, deliberate
choice for this pass.

## Future work (not started here)

A future iteration could extract the authorization/execution boundary into
its own module, but only with:

1. A dedicated characterization-test pass on the exact T126 invariant
   (pending/denied authorization ⇒ zero target subprocess calls) and the
   T130 classification semantics, written *before* any code moves.
2. Explicit sign-off that this is still "moving code, not changing scope"
   under Constitution XIV (no new FR/SC/US).
3. Its own ADR, since it touches the security boundary this ADR explicitly
   declined to touch.
