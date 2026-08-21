# Person 2 — Result (I03 + I10)

- Branch: `work/person-2`
- Base commit: `561e084` (`abraham-full-tasks-branch`)
- Head commit: `25a9491`
- Range: `561e084..25a9491` (3 commits: `2edfed0`, `bbb2fae`, `25a9491`)
- Status: **DONE**

## Items

| Item | Classification | Status |
|---|---|---|
| I03 | TECHNICAL DEBT — strengthen tool schema validation | Implemented |
| I10 | POST-MVP — evaluation harness | Designed (no code) |

## Implementation completed (I03)

1. **Inventoried** every `esquema_entrada`/`esquema_salida` actually declared
   by the 11 registered tools (`src/qa_agent/tools/*.py`:
   `explore`, `locate`, `search`, `run_tests`, `analyze_test_results`,
   `generate_test_cases`, `analyze_coverage`, `leer_archivo`, `crear_archivo`,
   `editar_archivo`, `eliminar_archivo`), cross-checked against
   `specs/001-core-ai-qa-agent/contracts/tool-contracts.md`. Confirmed the
   only JSON-Schema-like keywords in use are exactly the 7 the current
   partial validator supports: `type`, `properties`, `required`, `items`,
   `enum`, `minimum`, `maximum`.
2. **Added a compatibility suite** (`tests/contract/test_schema_validator_compat.py`,
   92 test cases) covering, per the task's required categories: valid
   objects (one entrada + one salida per tool, 22 cases), missing required
   fields (top-level, nested, and inside array items), invalid types
   (including the `bool` vs `integer`/`number` distinction), arrays/`items`
   including two levels of real nesting
   (`analyze_coverage.por_archivo[].lineas_faltantes[]`), nested object
   structures (`analyze_test_results.entrada.resultado_tests`), `enum`
   (top-level and nested in array items), `minimum`/`maximum` boundaries,
   deterministic-result behavior (same input validated 5×, dict key order
   independence, no mutation of inputs), and malformed-schema robustness.
3. **Compared options in an ADR** (`docs/adr/ADR-002-schema-validation.md`):
   A) keep the partial validator, B) Pydantic (already a dependency),
   C) a standards-compliant JSON Schema library (new dependency).
4. **Result**: 91/92 compatibility cases passed against the **unmodified**
   validator — no correctness gap exists for any schema actually in use.
   One case exposed a real but narrow gap: a malformed `properties` value
   (never produced by any real tool schema) raised an uncaught
   `AttributeError` instead of returning `False`, violating the function's
   own documented "never raises an uncontrolled exception" contract
   (FR-005/SC-010).
5. **Implemented the ADR-approved outcome (Option A)**: kept the existing
   partial validator; widened its `except (TypeError, ValueError, KeyError)`
   to also catch `AttributeError` in `validar_resultado_esquema`
   (`src/qa_agent/tools/base.py`) — a one-line, behavior-preserving fix. No
   public schema was broadened (no field added/removed, no type relaxed) on
   any tool.

## Design completed (I10)

Wrote `docs/proposals/I10-evaluation-harness.md`, a design-only proposal
(no executable code, no new dependency) specifying:

- Versioned corpus/fixtures directory layout, manifest, and content-hash
  pinning for reproducibility.
- Golden expectations JSON format (`expected_terminal_state`,
  `expected_tool_sequence` with exact/subset modes and tool equivalence
  classes, `step_budget`, `expected_evidence`, `safety_expectations`, and a
  `semantic_rubric` slot reserved for I15).
- Five deterministic metrics (tool-selection accuracy, step efficiency,
  grounding score, completion score, safety score) with exact formulas,
  grounded in the existing `PasoDePlan`/`Observacion`/`EstadoDelAgente`
  data-model entities — versus LLM-variable metrics (response quality,
  causal-analysis quality), explicitly deferred to I15, with the
  distinction (scorer type, not trace variability) made explicit.
- Latency/token/cost measurement approach, including how to handle
  providers that don't report token usage (flagged `"estimated": true`,
  never silently mixed with measured figures) and versioned price tables.
- Provider/model comparison methodology (`compare_runs`, a pure diff over
  two immutable `report.json` files) with a versioned tolerances file
  distinguishing gate-eligible metrics (correctness/safety) from
  advisory-only ones (latency/tokens/cost); `safety_score` gets a
  non-configurable zero-tolerance floor to stay aligned with the immutable
  T125/T126 guarantees.
- Reproducibility requirements: pinned provider/model/params/corpus-hash/
  git-commit, fixture reset before mutating cases, and a `replicate_count`
  (default 3) with median/mode aggregation to make LLM-sampling variance a
  reported quantity instead of a hidden one.
- How this could connect to CI (I04, Person 3) — referenced only: an
  optional smoke-test job with a stubbed `LLMBackend` (deterministic,
  gate-eligible) and a separate, always-optional, non-blocking scheduled
  job against a real provider. Nothing implemented; I04 remains Person 3's
  scope entirely.
- A concrete consumable interface for I14/I15: `run_evaluation()` /
  `compare_runs()` Python signatures, the future `qa-agent eval run|report|
  compare` CLI shape with exit codes, and exact JSON schemas for
  `run.json`/`report.json`/trace files, including the `semantic_evaluation`
  reserved slot I15 fills additively without mutating I10's deterministic
  report.

## Files changed

- `tests/contract/test_schema_validator_compat.py` (new — 92 tests)
- `src/qa_agent/tools/base.py` (one-line robustness fix: except clause)
- `docs/adr/ADR-002-schema-validation.md` (new)
- `docs/proposals/I10-evaluation-harness.md` (new)
- `docs/improvements/person-2-result.md` (this file)

## Tests

- Baseline (base commit `561e084`, unmodified worktree code):
  `python -m pytest -q` → **354 passed**.
- After I03: `python -m pytest -q` → **446 passed** (354 + 92 new), 0
  failed, same warning profile as baseline.
- `python -m pip check` → clean, both before and after (no dependency
  changes).
- **Environment note (read before re-running)**: this machine has a
  *global* editable install of `qa-agent` pointing at an unrelated
  checkout (`C:\Users\AbrahamVillalobosUga\qa-agent`, a separate clone on
  `main`), not at this worktree. Running plain `python -m pytest` from the
  worktree silently imports `qa_agent` from that other checkout instead of
  this worktree's `src/`, which would make source edits here invisible to
  the test run. All test runs for this work were executed with
  `PYTHONPATH=<this worktree>/src` prepended so `qa_agent` resolves to this
  worktree's code; the 354/446 figures above are from that correctly-scoped
  run. Anyone re-verifying this branch should do the same:
  `PYTHONPATH="$(pwd)/src" python -m pytest -q` from the worktree root.

## Decisions (ADR link)

- `docs/adr/ADR-002-schema-validation.md` — **Decision: Option A** (keep the
  existing partial validator; add compatibility tests; one-line robustness
  fix). Rejected Option B (Pydantic: no demonstrated need, would require
  either duplicating the dict-based schemas as `BaseModel`s or
  runtime-building models from them — comparable complexity to what it
  replaces, plus coercion semantics that would risk silently altering
  LLM-proposed tool arguments, cutting against VII/IX). Rejected Option C
  (new JSON Schema dependency: no demonstrated need; every contract in
  `tool-contracts.md` uses exactly the 7 keywords already supported).

## Dependencies

- I03: **no new dependency**. `pydantic` (already present) was considered
  and explicitly not adopted — see ADR-002.
- I10: **no new dependency**, and no executable code of any kind (design
  document only, per the I10 task constraint).

## Remaining SDD gate

- I10 requires explicit approval of this design (per
  `docs/tareas-divididas.md`'s "no construir el harness sin esa aprobación")
  before Person 6 (I14/I15) or anyone else builds `eval/`,
  `qa_agent.evaluation`, or `qa-agent eval` against it. Nothing is built yet;
  that gate is open, not closed, by this deliverable.
- I03's ADR-002 flags one accepted limitation for future revisit: the
  validator remains partial (no `oneOf`/`anyOf`/`patternProperties`/
  `additionalProperties: false`/`format`/`$ref`). If a future tool contract
  needs any of these, re-run `tests/contract/test_schema_validator_compat.py`
  against the new contract before deciding whether Option A still holds —
  that suite is the reusable artifact for that future decision.

## Risks

- **Environment risk (not introduced by this work, but affects verifying it)**:
  the global editable install pointing outside the worktree (see Tests
  section) means any teammate or CI step that runs bare `pytest` without
  setting `PYTHONPATH` to the worktree's `src/` will silently test the
  wrong source tree and report a false baseline. This is worth flagging to
  Person 3 (I04/CI owner) so the CI job doesn't inherit this trap.
- **I03**: minimal risk. The change is additive tests plus a one-line
  exception-handling widening; both are covered by the new suite and the
  full suite stayed green (446/446) with no regressions from the 354
  baseline.
- **I10**: no execution risk (no code shipped). The main design risk is
  scope drift if I14/I15 diverge from this contract during implementation —
  mitigated by making the JSON schemas and function signatures explicit
  enough (§5 of the proposal) that deviations should be visible as a
  conscious choice, not an accident.
