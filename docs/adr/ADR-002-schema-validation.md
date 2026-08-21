# ADR-002: Tool schema validation strategy (I03)

- Status: Accepted
- Date: 2026-08-20
- Owner: Person 2 (`work/person-2`)
- Related: `specs/001-core-ai-qa-agent/contracts/tool-contracts.md`,
  `src/qa_agent/tools/base.py`, `tests/contract/test_schema_validator_compat.py`,
  `tests/contract/test_tool_contracts.py`
- Constitution principles engaged: III (testability), VI (determinism),
  VII (validation and contracts), X (code quality, no needless abstraction),
  XII (incremental evolution — no complexity without a concrete need)

## Context

`src/qa_agent/tools/base.py` implements a small, hand-written partial JSON
Schema validator (`_esquema_cumple` / `validar_resultado_esquema`) supporting
`type`, `properties`, `required`, `items`, `enum`, `minimum`, `maximum`. It is
used in two places:

1. `Herramienta.validar_resultado` / the module-level `validar_resultado` —
   validates a tool's **output** (`datos`) against `esquema_salida` before the
   agent trusts it (FR-005, VII).
2. `AgentLoop._invocar_herramienta` in `src/qa_agent/agent/loop.py` (owned by
   Person 1 in this wave, not modified here) — validates the LLM-proposed
   **input parameters** against `esquema_entrada` before a tool executes
   (FR-033).

I03 asks whether this hand-written validator should be strengthened,
replaced by Pydantic (already a dependency), or replaced by a standards-
compliant JSON Schema library (a new dependency).

## Method

Before touching any validator behavior, a compatibility suite was added at
`tests/contract/test_schema_validator_compat.py` (92 test cases across 24
parametrized/plain tests) exercising `validar_resultado_esquema` against the
**actual** `esquema_entrada`/`esquema_salida` declared by all 11 registered
tools (`explore`, `locate`, `search`, `run_tests`, `analyze_test_results`,
`generate_test_cases`, `analyze_coverage`, `leer_archivo`, `crear_archivo`,
`editar_archivo`, `eliminar_archivo`), covering every category required by
I03:

- valid objects for every tool's entrada and salida schema;
- missing top-level, nested, and array-item `required` fields;
- invalid types (string/int/bool/number/array/object mismatches, including
  the `bool` vs `integer`/`number` distinction);
- arrays/`items`, including two levels of nesting actually used
  (`analyze_coverage.por_archivo[].lineas_faltantes[]`);
- nested object structures actually used
  (`analyze_test_results.entrada.resultado_tests`);
- `enum` at top level and nested inside array items;
- `minimum`/`maximum` boundaries (inclusive) for every field that declares
  them (`profundidad_max`, `max_lineas`, `contexto_lineas`);
- determinism: identical input validated 5× produces the same result, key
  order in the input dict does not change the result, and validation never
  mutates `datos`/`esquema` (VI);
- robustness: malformed schema shapes (`None`, non-dict, non-dict
  `properties`, non-iterable `required`) never raise — they return `False`.

### Finding

**91 of 92 cases passed against the validator unmodified.** Every schema
shape actually declared by a tool in this codebase (matching
`tool-contracts.md`) is handled correctly and deterministically by the
existing partial validator. No demonstrated correctness problem exists for
real usage.

One case failed: a malformed `esquema["properties"]` that is not a dict
(e.g. a string) raised an uncaught `AttributeError` in `_esquema_cumple`,
instead of returning `False` as `validar_resultado_esquema`'s own docstring
promises ("sin lanzar excepción de validación de esquema no controlada").
This never occurs with any real tool schema — every tool declares
`properties` as a dict literal in Python source, not from untrusted input —
but it is a genuine violation of the function's own documented contract
(FR-005 / SC-010), reachable in principle if a future schema is malformed.

## Decision

**Option A — keep the existing partial validator, harden it minimally, add
the missing test coverage.**

Concretely:
1. Add `tests/contract/test_schema_validator_compat.py` (permanent
   regression coverage; freezes the validator's behavior against every real
   contract).
2. Widen the existing `except (TypeError, ValueError, KeyError)` in
   `validar_resultado_esquema` to also catch `AttributeError`, closing the
   one demonstrated gap (malformed `properties`) so the function's own "no
   uncontrolled exception" contract holds unconditionally. This is a
   one-line, behavior-preserving change: every case that previously returned
   `True`/`False` still does; the only observable change is that a
   previously-crashing malformed-schema input now returns `False` instead of
   raising.

No other changes to `base.py`, to any tool's `esquema_entrada`/
`esquema_salida`, or to the public signature of `validar_resultado_esquema`
(both callers — `Herramienta.validar_resultado` and
`AgentLoop._invocar_herramienta` — depend on it returning a plain `bool`).

## Alternatives considered

### Option B — Pydantic-based validation

`pydantic` is already a runtime dependency (`pyproject.toml`), so it carries
no new-dependency cost. It was rejected for I03 anyway because:

- The tool contracts are expressed as **data** (JSON-Schema-shaped dicts
  attached to each `Herramienta` subclass as class attributes), not as
  Python types. Adopting Pydantic properly would mean either (a) hand-writing
  a `BaseModel` per tool per direction (22 models for 11 tools × entrada/
  salida) that must be kept in sync with the dict schemas already in
  `tool-contracts.md` and the tool source — doubling the source of truth and
  directly risking the "no silently broaden a public schema" constraint — or
  (b) dynamically building Pydantic models from the existing dicts at
  runtime (`pydantic.create_model` / `TypeAdapter` over a JSON-Schema-like
  dict), which re-introduces a schema interpreter of comparable complexity
  to the one being replaced, for a library not designed to consume
  JSON Schema as input in the first place.
- The compatibility suite demonstrated no correctness gap that Pydantic
  would close. Its main draws — coercion, richer error messages, `Field`
  constraints — are not needed: this validator is intentionally a pass/fail
  gate (`bool`), not a coercion layer (coercing LLM-proposed tool arguments
  would silently change what the agent asked for, which cuts against VII
  and IX — no fabricating/altering what was actually requested).
- Principle XII: no complexity without a concrete, demonstrated need. None
  was found.

### Option C — standards-compliant JSON Schema library (e.g. `jsonschema`)

Would be a **new** dependency. Cost/benefit:

- Cost: new third-party dependency to vet, pin, and keep patched; pulls in
  its own transitive dependencies; the project currently has zero JSON
  Schema libraries and a deliberately small dependency surface
  (`pyproject.toml`: openai, pathspec, pydantic, python-dotenv, rich,
  typer).
- Benefit: full JSON Schema draft support (`oneOf`/`anyOf`/`patternProperties`/
  `additionalProperties`/`format`/…) — **none of which any tool contract
  uses today**. The 7 keywords the current validator supports
  (`type`, `properties`, `required`, `items`, `enum`, `minimum`, `maximum`)
  are exactly the 7 keywords every contract in `tool-contracts.md` uses.
- Rejected: no demonstrated problem justifies the new dependency (I03 rules
  this out explicitly: "Do not add a dependency just because it's
  theoretically cleaner").

## Consequences

- Positive: the validator's real-world behavior is now pinned by an
  executable, per-tool compatibility suite (92 cases) that will fail loudly
  if a future change to `base.py` or to any tool's schema silently narrows
  or breaks validation. The one-line `AttributeError` fix makes the
  function's documented robustness guarantee actually hold.
- Positive: zero new dependencies; zero risk to the immutable T125–T131
  remediation behaviors (this ADR touches only schema validation, not
  authorization, redaction, session persistence, `generate_test_cases`'s
  two-argument contract, the CLI surface, or subprocess result
  classification).
- Negative / accepted limitation: the validator remains a **partial**
  JSON Schema implementation. It does not support `oneOf`/`anyOf`,
  `patternProperties`, `additionalProperties: false`, `format`, tuple-typed
  `items` (array of schemas), or schema `$ref`. If a future tool contract
  needs any of these, this ADR's conclusion should be revisited — the
  compatibility suite is exactly the artifact to re-run against the new
  contract to decide whether Option A still holds.
- No public schema was broadened: no optional/required field was added to
  any tool's `esquema_entrada`/`esquema_salida`, and no type was relaxed.

## Verification

- `tests/contract/test_schema_validator_compat.py` — 92/92 passing after the
  fix (91/92 before, isolating the one real gap).
- `tests/contract/test_tool_contracts.py` — unchanged, still passing.
- Full suite: `python -m pytest -q` — 446 passed (354 baseline + 92 new),
  0 failed, same warnings profile as baseline.
- `python -m pip check` — clean (no dependency changes made).
