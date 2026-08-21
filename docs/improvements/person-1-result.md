# Person 1 — Result: I01 (modularize `agent/loop.py`) and I02 (relocate intent
# phrase/regex tables)

- Branch: `work/person-1`
- Base commit: `561e084` (docs: initialize PERSON 1-6 program execution ledger)
- Scope: `docs/improvements/qa-agent-improvement-backlog.md` items I01, I02;
  `docs/tareas-divididas.md` Person 1 assignment.
- Zone owned: `src/qa_agent/agent/loop.py`, `src/qa_agent/agent/router.py`.

## Items

| Item | Description | Status |
|---|---|---|
| I02 | Reduce/relocate hardcoded intent phrase and regex tables from `loop.py`/`router.py` | COMPLETE |
| I01 | Modularize `agent/loop.py` (incremental, risk-ordered) | COMPLETE (for the scope this ADR defines as done — see below; authorization/execution boundary intentionally deferred) |

## Status

**I02: COMPLETE.** All intent-phrase and layer-detection tables/regex
identified in the backlog (`_FRASES_ANALISIS_GLOBAL`, `_FRASES_INTENCION_PRUEBAS`,
layer verbs/connectors/regex) were moved out of `loop.py` into two focused
modules, with zero semantic change (verified by characterization tests
written before the move, and object-identity assertions after). `router.py`
was inventoried and found to already be a single, focused routing module —
no further extraction was needed there; this is documented as a deliberate
decision, not an oversight.

**I01: COMPLETE for the scope defined in ADR-001.** Four further
low/medium-risk extractions were made (runner detection, response grounding,
plan enrichment, on top of I02's intent/layer detection). The
authorization/execution boundary and its filesystem-rail dependencies were
deliberately **not** extracted — see ADR-001's "What stays and why" and
"Stopping point" sections for the full reasoning. This is not a partial/未
finished result: the task's own acceptance criterion is "you decide when
[cohesion] is reached and record your reasoning," and that reasoning is
recorded in the ADR.

## Implementation completed

### I02 — intent/layer policy extraction

- Inventoried every phrase list, regex, and intent/layer-detection rule in
  `loop.py` and `router.py`.
- Wrote characterization tests (`tests/unit/test_intent_layer_policy_characterization.py`)
  against the *original* `loop.py` code before any extraction, covering:
  global-analysis detection (positive/negative), test-suggestion detection
  (positive/negative), the exhaustive-analysis OR-combinator, layer-analysis
  detection (positive/negative), layer-name extraction (including the T124
  connector-skipping case), and real-filesystem layer resolution
  (case-insensitive match + absence).
- Created `src/qa_agent/agent/intent_policy.py` (global-analysis and
  test-suggestion phrase tables + detectors) and
  `src/qa_agent/agent/layer_policy.py` (layer/folder regex, connectors,
  verbs, extension set, extraction, detection, real-filesystem resolution).
- `loop.py` now **imports** (does not redefine) these names, so every
  existing test that does `from qa_agent.agent.loop import _es_analisis_global`
  (and five sibling names) keeps working unchanged — verified both by the
  full suite and by explicit `is` identity assertions in the
  characterization test.
- No phrase was added, removed, or reworded; no regex semantics changed
  (pure move, Constitution X/XII).
- `router.py` reviewed and left as-is: it is already the single focused
  "routing" module (`_PATRONES_HERRAMIENTAS` + extraction helpers); splitting
  it further would not have improved cohesion.

### I01 — incremental modularization (ADR-001)

Four extractions, one per commit, full suite run after each:

1. **`runner_detection.py`** — project-type marker detection
   (`.csproj`/`.sln`/`pom.xml`/`build.gradle`) and pytest/dotnet/mvn/gradle
   command selection for `run_tests`/`analyze_coverage`. Pure functions, no
   `self` dependency. `loop.py` imports the same names already directly
   imported by `tests/unit/test_deteccion_runner.py`.
2. **`grounding.py`** — `_afirmaciones_no_ancladas`/`_al_inicio_de_frase`
   (SC-017/FR-019 honesty check: the final response text can't claim facts
   absent from real observations). Neither function used `self`; extracted
   verbatim, single call site in `_respuesta_react` updated. New direct unit
   tests added (`tests/unit/test_grounding.py`), isolated from `Agent`/LLM.
3. **`plan_enrichment.py`** — the three deterministic plan-enrichment
   routines (`_enriquecer_plan_analisis_global`, `_enriquecer_plan_pruebas`,
   `_enriquecer_plan_analisis_capa`) plus shared helpers
   (`archivos_codigo_de_capa`, `plan_ya_explora_capa`, `plan_ya_lee_archivo`,
   `presupuesto_pasos`), converted to pure functions taking the tool catalog
   and authorized root path explicitly instead of `self`. `Agent` keeps
   same-named delegator methods, so the ReAct loop's call sites in
   `_atender_react` required zero changes. Regression proof: the pre-existing
   `test_profundidad_analisis.py` / `test_profundidad_capa.py` /
   `test_intencion_pruebas.py` suites (121 tests, written against the
   original `loop.py` behavior) required **zero** changes and stayed green.

Deliberately deferred (documented in ADR-001, not attempted): the
authorization/execution boundary (`_ejecutar_siguiente_paso`,
`_ejecutar_herramienta`, `_parametros_para`, `_resultado_de_pruebas`,
`_validar_y_usar`, `atender`/`_atender_una_pasada`/`_atender_react`) and the
filesystem-rail helpers that feed it (`_resolver_archivo_real`,
`_corregir_escritura`, `_buscar_archivo_por_nombre`,
`_buscar_directorio_por_nombre`, `_resolver_directorio_real`,
`_capas_reales`, `_encolar_explore_capas_reales`). This is the T125/T126
security boundary; extracting it without a dedicated parity-proving
regression suite would trade a line-count improvement for remediation risk,
which the task brief explicitly says not to do.

## Files changed

New modules:
- `src/qa_agent/agent/intent_policy.py`
- `src/qa_agent/agent/layer_policy.py`
- `src/qa_agent/agent/runner_detection.py`
- `src/qa_agent/agent/grounding.py`
- `src/qa_agent/agent/plan_enrichment.py`

Modified:
- `src/qa_agent/agent/loop.py` (1,947 → 1,358 lines; imports/delegates to
  the five modules above instead of defining their logic inline)

New tests:
- `tests/unit/test_intent_layer_policy_characterization.py` (I02
  characterization + module-identity checks)
- `tests/unit/test_grounding.py` (direct unit coverage for the new
  `grounding.py` module)

New docs:
- `docs/adr/ADR-001-loop-modularization.md`
- `docs/improvements/person-1-result.md` (this file)

Not changed: `src/qa_agent/agent/router.py` (reviewed, found already
cohesive — see I02 above), any public contract
(`specs/001-core-ai-qa-agent/contracts/agent-interface-contract.md`
untouched), `pyproject.toml`, any dependency.

## Tests

- Baseline (before any change, base commit `561e084`): **354 passed**.
- Final (`PYTHONPATH="$(pwd)/src" python -m pytest -q`, all commits applied):
  **371 passed, 0 failed**.
- `python -m pip check`: clean (no dependency changes).
- Full suite was run after every commit in the series (see ADR-001 "Testing
  evidence" for the per-commit progression: 354 → 363 → 365 → 371 → 371).
- Focused re-run of the highest-value regression suites together
  (`test_profundidad_analisis.py`, `test_profundidad_capa.py`,
  `test_intencion_pruebas.py`, `test_deteccion_runner.py`,
  `test_grounding.py`, `test_intent_layer_policy_characterization.py`,
  `test_reasoning.py`): **121 passed**.

### Environment note

This worktree's editable `qa-agent` install resolved to a different, stale
checkout during this session. Every test run above used
`PYTHONPATH="$(pwd)/src"` to force pytest to import this worktree's code
instead. Documented in ADR-001; anyone re-running this branch's tests should
do the same until the editable install is repointed.

## Decisions (ADR link)

See `docs/adr/ADR-001-loop-modularization.md` for the full extraction plan,
risk ordering, what stays in `loop.py` and why, rollback approach, and the
explicit reasoning for where I01's "done" line was drawn this pass.

Key decisions:
- I02 before I01, per the task's own internal ordering (`tareas-divididas.md`
  §"Orden interno").
- Re-export-by-import and thin-delegator-method techniques used throughout
  so every extraction is independently revertible via `git revert` without
  touching later commits or any call site outside the moved code.
- `router.py` left unchanged: already a focused single-responsibility module.
- Authorization/execution boundary left in `loop.py`: security-sensitive,
  no dedicated parity regression suite exists yet, task brief explicitly
  permits leaving it if extraction risk isn't justified.

## Dependencies

None. No new external dependency was added (Constitution XI/no new deps
constraint honored). No other person's assigned files
(`allowlist.py`, `redactor.py`, `tool-contracts.md`, CI config, etc.) were
touched. Handoff per `tareas-divididas.md` ("Persona 1 realiza primero las
extracciones; 4 y 5 integran después"): `loop.py`'s remaining internal
boundaries are now: routing (`router.py`, unchanged), intent detection
(`intent_policy.py`), layer detection (`layer_policy.py`), runner detection
(`runner_detection.py`), plan enrichment (`plan_enrichment.py`), response
grounding (`grounding.py`), and the orchestration/authorization/execution
core that remains in `loop.py` itself — Persons 4 and 5 can integrate
against these module boundaries when their own work touches
discovery/exclusion policy or redaction/observability.

## Remaining SDD gate

- I01 and I02 are TECHNICAL DEBT items per the backlog, with "Requires
  future Plan/ADR: YES" (I01) / "DEPENDS" (I02, only if semantics change).
  This ADR satisfies that gate for the extractions actually performed; no
  phrase/regex semantics changed, so no additional Spec/Plan approval was
  triggered for I02.
- The deferred authorization/execution extraction (see ADR-001 "Future
  work") would need its own dedicated regression pass and its own ADR before
  being attempted — not authorized by this document.
- No new FR/SC/US was introduced (Constitution XIV). No public contract
  (`agent-interface-contract.md`) changed. T125–T131 remediation behavior
  was not touched: secrets redaction before LLM calls, authorization gating
  of `run_tests`/`analyze_coverage` (direct and via
  `analyze_test_results`), absence of persistent `.qa_sessions`, and T130
  subprocess-classification semantics are all still enforced by the exact
  same code, now living partly in `plan_enrichment.py`/`runner_detection.py`
  for the non-security-sensitive parts, and unchanged in `loop.py` for the
  security-sensitive parts.

## Risks

- **Editable-install/PYTHONPATH mismatch in this environment** (see above):
  low risk to the delivered code itself (verified correct via explicit
  PYTHONPATH), but a real risk to anyone re-running `python -m pytest`
  without the same override — they could silently test stale code. Flagged
  in both this doc and the ADR.
- **`plan_enrichment.py` is MEDIUM risk by the task's own classification**:
  mitigated by (a) keeping `Agent`'s delegator methods so no call site
  changed, and (b) the extensive pre-existing regression suite (121 tests)
  passing unchanged.
- **Line-ending warnings** (`LF will be replaced by CRLF`) appeared on every
  new file `git add`; this is a pre-existing repo/editor line-ending
  configuration issue, not something introduced by this work, and does not
  affect test behavior.
- **Authorization/execution boundary remains large and untouched** in
  `loop.py` (~900 of the remaining 1,358 lines cover `_atender_una_pasada`,
  `_atender_react`, `_ejecutar_siguiente_paso`, and the filesystem-rail
  helpers together). This is a deliberate, documented risk acceptance per
  ADR-001, not an oversight — a future dedicated pass with its own
  parity-proving regression suite would be needed to go further.
