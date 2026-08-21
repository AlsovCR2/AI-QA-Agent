# I06 — Richer deterministic runner metadata (DESIGN ONLY)

## Status

PROPOSED. This document is a design for a **future, versioned** addition to
`specs/001-core-ai-qa-agent/contracts/tool-contracts.md`. It does **not**
change that file, `run_tests.py`, `analyze_coverage.py`, or any tool
contract. Per `docs/tareas-divididas.md` (Persona 3): "I06 puede alimentar
I09, pero I09 no debe acoplarse a campos que todavía no estén aprobados", and
per the backlog: "Requires future Spec: YES" / "Requires future Plan/ADR:
YES". Implementation is blocked on that approval; this document exists to
make the approval decision concrete.

## Problem

`run_tests` and `analyze_coverage` currently expose only aggregate counts
(`pasadas`/`falladas`/`errores`/`total`, `cobertura_global`) and a coarse
state enum (`estado_global` / `estado`: `exito` | `fallo`/`error` |
`no_ejecutado`). Internally, T130 already classifies subprocess outcomes into
seven cases (see "T130 semantics" below) using `returncode` and free-form
stdout/stderr text, but that richer signal is discarded once the tool returns
— callers only see the three-value enum. This makes downstream diagnostics
(why exactly did this fail — timeout vs. spawn failure vs. contradictory
output?), reproducibility (what runner/command actually ran, how long did it
take) and correlation (matching a run to CI/local logs) weaker than the
evidence the tool already computed and then threw away.

## Goals

- Expose the internal classification and process metadata that both tools
  already compute, without inventing new execution behavior.
- Keep the three existing public enums (`estado_global`, `estado`) and every
  currently-required output field **unchanged** — this is an additive,
  backward-compatible contract change.
- Preserve T130's seven-way classification exactly (see below) — the new
  fields describe *why* a state was reached, they do not replace or
  reinterpret the state itself.
- Bound the new stdout/stderr fields so a pathological runner (e.g. an
  infinite-loop test printing megabytes) cannot blow up agent context or
  logs — this is a new honesty/safety property, not present today (today the
  full unbounded `salida_completa` is parsed internally but never returned).

## Non-goals

- Not proposing new tool behavior (no new commands, no new allowlist
  entries, no change to timeout value, no retry logic).
- Not proposing to widen `estado_global`/`estado` beyond their current three
  values.
- Not proposing to make `run_tests`/`analyze_coverage` sandboxed, network-
  isolated, or resource-limited (contract already states "Este contrato no
  ofrece aislamiento de proceso, red, credenciales ni filesystem" — I06 does
  not touch that boundary).
- Not implementing anything in this document. No contract, code, or test
  file is modified by I06 at this stage.

## T130 classification semantics (preserved, not modified)

Authority: `docs/remediation/qa-agent-remediation-log.md` (`## T130`) and
`tests/unit/test_remediation_subprocess_semantics.py`. The internal
classification `run_tests.ejecutar()` and `analyze_coverage.ejecutar()`
already perform, before mapping down to the public 3-value enum, is:

| # | Case | Current internal signal | Current public mapping |
|---|---|---|---|
| 1 | Success | parsed counts consistent, `returncode == 0` | `estado_global="exito"` / `estado="exito"`, `EstadoResultado.EXITO` |
| 2 | Ordinary test failure | parsed failures/errors present, `returncode in {0,1}` (run_tests) | `estado_global="fallo"`, `EstadoResultado.EXITO` (a valid, executed result) |
| 3 | Zero tests (explicit) | output contains an explicit "no tests" marker, `returncode in {0,5}` | `estado_global="no_ejecutado"`, `EstadoResultado.EXITO` |
| 4 | Contradictory output | parsed state doesn't match `returncode` (e.g. returncode says failure but output says success) | `EstadoResultado.ERROR`, `estado_global="no_ejecutado"` |
| 5 | Unsupported/unparseable output | output doesn't match any known runner format | `EstadoResultado.ERROR`, `estado_global="no_ejecutado"` |
| 6 | Spawn failure | `OSError` (executable not found, permission, etc.) | `EstadoResultado.ERROR`, `estado_global="no_ejecutado"` |
| 7 | Timeout | `subprocess.TimeoutExpired` | `EstadoResultado.ERROR`, `estado_global="no_ejecutado"` |

`analyze_coverage` mirrors this with `estado="exito"`, `estado="error"` (its
"ordinary failure" state, since a coverage run failing is itself the
reportable error condition, unlike a test failure which is a valid result),
and `estado="no_ejecutado"`.

**I06 requirement**: every one of these seven cases must remain distinguishable
after the change — cases 4–7 must **not** collapse into one generic "error"
once richer metadata exists; the new `motivo_fallo` field (below) makes them
explicit instead of requiring a caller to re-infer them from `error` free
text, but the existing `EstadoResultado` / `estado_global` / `estado`
mapping in the table above does not change.

## Proposed additive fields

All fields below are proposed as **new, additive** members of the existing
`run_tests` and `analyze_coverage` output schemas (`esquema_salida`), under a
new **contract minor version** (see "Versioning" below). None of the current
fields (`pasadas`, `falladas`, `errores`, `total`, `estado_global`,
`detalle_fallos`, `cobertura_global`, `por_archivo`, `estado`) change type,
name, or meaning.

```json
{
  "exit_code": {
    "type": "integer",
    "nullable": true,
    "description": "Subprocess returncode. null only for spawn failure (case 6), where no process ever ran to produce one."
  },
  "runner": {
    "type": "string",
    "enum": ["pytest", "dotnet", "maven", "gradle", "desconocido"],
    "description": "Runner detected from comando_pruebas/comando_cobertura's own dispatch logic (already implemented today in _parsear_salida's prefix match) — not a new detection mechanism, just surfacing the existing dispatch decision."
  },
  "duration_ms": {
    "type": "integer",
    "minimum": 0,
    "description": "Wall-clock time from subprocess.run() invocation to return, in milliseconds. Present even on timeout (== the configured timeout bound) and on ordinary completion; absent (field omitted) only for spawn failure, where no timed invocation occurred."
  },
  "stdout_truncado": {
    "type": "string",
    "description": "Bounded prefix of captured stdout. Bound: see 'Output bounds' below."
  },
  "stderr_truncado": {
    "type": "string",
    "description": "Bounded prefix of captured stderr. Bound: see 'Output bounds' below."
  },
  "salida_truncada": {
    "type": "boolean",
    "description": "true if either stdout_truncado or stderr_truncado is shorter than the actual captured stream (i.e. a cap was hit). Mirrors the existing 'nota'-on-truncation honesty pattern already used by search's max_ocurrencias (FR-019)."
  },
  "motivo_fallo": {
    "type": "string",
    "nullable": true,
    "enum": [
      null,
      "fallos_de_pruebas",
      "cero_pruebas",
      "salida_contradictoria",
      "salida_no_soportada",
      "fallo_de_arranque",
      "timeout"
    ],
    "description": "Structured reason, present whenever estado_global/estado is not a plain success. One-to-one with T130 cases 2 (partially — only the 'errores' subset, since 2's ordinary-failure-with-passes is not a failure reason) through 7 in the table above. null when estado_global=='exito'/estado=='exito'."
  }
}
```

### Output bounds (bytes/lines)

Bounding rule, applied identically to `run_tests` and `analyze_coverage`,
identically to stdout and stderr:

- **Byte cap**: 32 KiB per stream (`stdout_truncado`, `stderr_truncado`
  each capped independently). Chosen because it comfortably holds a pytest
  summary plus several full tracebacks (T130's existing per-failure message
  truncation already caps each individual failure message at 500 characters
  — see `mensaje_error[:500]` in `run_tests.py`; 32 KiB is roughly 64 such
  messages, generous headroom for the *raw* stream this field exposes,
  distinct from the already-truncated per-failure summaries in
  `detalle_fallos`).
- **Line cap**: 500 lines per stream, applied together with the byte cap
  (whichever limit is hit first wins — this matches the two-dimensional cap
  pattern already used by `explore`'s `profundidad_max` + entry-count
  behavior, i.e. more than one independent honesty bound rather than a
  single one that can be gamed by e.g. one enormous line).
- **Truncation point**: keep the **head** (first N bytes/lines), not the
  tail. Rationale: the head is where spawn/import-time errors and the test
  session header appear; pytest's own failure summary ("short test summary
  info") already gets extracted separately into `detalle_fallos` by the
  existing parser, so losing the tail of a long raw stream does not lose the
  structured failure list. (A future revision could offer head+tail if
  evidence shows the head-only bound hides needed detail — that is
  explicitly deferred, not decided here.)
- **Redaction**: bounded streams pass through the same secret-redaction path
  applied to all other tool-observable text before the LLM ever sees them
  (this must not regress T125 — redaction-before-LLM is unconditional; I06
  adds a size bound, it does not add or remove a redaction step).

### `runner` detection

`run_tests._parsear_salida()` and `analyze_coverage`'s equivalent already
dispatch on a prefix match of the *authorized command string*
(`comando_pruebas`/`comando_cobertura`) to pick a parser: `dotnet` → dotnet,
`mvn` → maven, `gradle`/`gradlew` → gradle, else → pytest. I06 proposes
**reusing exactly this existing dispatch decision** as the `runner` field's
value (adding a `"desconocido"` case only for a future allowlist entry this
dispatch doesn't recognize, which cannot happen today since the allowlist and
the dispatch prefixes are already kept in sync). This is not a new detection
mechanism and does not change what commands are authorized.

### `duration_ms`

Measured as `end - start` around the existing `subprocess.run(...)` call
(`time.monotonic()` before/after). No new subprocess behavior; purely an
observation of the call already made. On timeout, `duration_ms` is reported
as the configured timeout bound (`120_000` for `run_tests`, `180_000` for `analyze_coverage` —
their current respective `subprocess.run(..., timeout=...)` values) since
that is the actual elapsed wall time before `TimeoutExpired` was raised.

## Versioning

`specs/001-core-ai-qa-agent/contracts/tool-contracts.md` has no existing
per-contract version marker (checked as part of this proposal — the file has
no `version:` field on individual tool contracts). I06 proposes:

1. Add a `contract_version` marker (e.g. `"1.1"`, following semver-ish
   minor-bump-for-additive-fields discipline) to the `run_tests` and
   `analyze_coverage` contract sections specifically, the first two contracts
   to need one — **not** a global version bump: this proposal does not touch
   `explore`/`locate`/`search`/other contracts, so only these two sections'
   version markers would move.
2. All seven new fields above are **additive and optional-in-practice for
   any consumer that doesn't know them**: `esquema_salida.required` stays
   exactly as it is today (the four/three currently-required fields); the
   new fields are added to `properties` but not to `required`, so an
   existing consumer validating only against today's required set keeps
   working unchanged. This is what makes the change a minor, not a major,
   version bump.
3. A future major version (a breaking change, e.g. making `motivo_fallo`
   required, or removing a field) is explicitly out of scope for I06.

This document proposes the version-bump *shape*; the actual edit to
`tool-contracts.md` requires its own Plan/ADR approval and is not made here
(the task instructions for I06 are explicit: "do not expand
`specs/001-core-ai-qa-agent/contracts/tool-contracts.md` yourself").

## Compatibility check against T130's regression test

`tests/unit/test_remediation_subprocess_semantics.py` asserts, for both
tools and across the six/seven `(returncode, salida)` combinations it
parametrizes:

- `resultado.estado` (the `EstadoResultado` enum) — **unaffected**: I06 adds
  fields to `resultado.datos`, it does not touch `resultado.estado`.
- `resultado.datos["estado_global"]` / `resultado.datos["estado"]` —
  **unaffected**: these keys keep their current values; I06 only adds
  sibling keys.
- `bool(resultado.error) is (estado_externo == EstadoResultado.ERROR)` —
  **unaffected**: `resultado.error` is a separate field from `datos`, not
  touched by this proposal.

A future implementation of I06 should extend that same test file's
parametrized cases with assertions on `datos["motivo_fallo"]`,
`datos["exit_code"]`, and `datos["runner"]` for each of the seven rows,
rather than adding a separate test file — this keeps the T130 semantics and
the I06 metadata verified in one place, so nobody can regress one without
the existing suite catching it (T130's own regression-test authority
notwithstanding — that file remains T130's, an I06 implementation adds cases
to it, it does not fork it).

## Interaction with I09 (Person 5)

`docs/tareas-divididas.md`: "I09 puede consumir I06" but "I09 no debe
acoplarse a campos que todavía no estén aprobados." Concretely: I09's
telemetry/evidence design may *reference* this document's proposed field
names as a plausible future source, but must not assume they exist, must not
special-case their absence as an error, and must not implement any code path
that reads them until this document — or its successor after Plan/ADR
review — is approved and `tool-contracts.md` is actually amended.

## Required approvals before implementation

Per the backlog and `tareas-divididas.md`, implementing any part of this
document requires, in order:
1. Spec update (new/amended functional requirement covering bounded output
   exposure and structured failure reasons — FR-017/018/019 are the closest
   existing authority but do not yet mention exit codes, runner names, or
   duration).
2. Plan/ADR approval of the versioning approach in this document (or a
   revision of it).
3. Only then: contract edit to `tool-contracts.md`, followed by
   implementation in `run_tests.py` / `analyze_coverage.py` and the test
   extensions described above.

No code, contract, or test file is changed by this document.
