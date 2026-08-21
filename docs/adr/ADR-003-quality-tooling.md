# ADR-003 — Development quality tooling (I05)

## Status

ACCEPTED (scoped). Ruff (lint), coverage.py and pip-audit are adopted with the
scope described below. Ruff's formatter and static type checking (mypy /
pyright) are evaluated and explicitly deferred; they are not wired into CI.

## Context

`docs/improvements/qa-agent-improvement-backlog.md` (I05) observes that
`pyproject.toml` configures pytest but no lint, formatting, type-checking or
coverage tooling. `docs/tareas-divididas.md` assigns I05 to Person 3, gated on
this ADR, and requires: "I05 no introduce miles de cambios de formato
mezclados con lógica" and "T131 debe usar solo validación ya configurada" (the
remediation gate T125–T131 is immutable and out of scope here).

Constitution XII (incremental evolution) forbids imposing thresholds or tools
without justification. Constitution X (code quality) motivates evaluating
tooling. The instruction for this item is explicit: do not blindly install
every candidate, do not mass-reformat, and adopt only what has a baseline
small enough to configure without an edit storm.

Environment note: this evaluation ran in a git worktree
(`work/person-3`, base `561e084`) whose editable install
(`pip show qa-agent`) resolves to a sibling clone
(`C:\Users\AbrahamVillalobosUga\qa-agent`) rather than the worktree itself.
This is a local development-environment artifact only — a CI runner does a
fresh checkout and `pip install -e ".[dev]"` in one place, so it does not
apply there. It did affect one config choice (see Coverage below).

## Candidates evaluated

### 1. Ruff (lint) — ADOPTED (scoped)

- **Purpose**: fast linter for correctness-class issues (unused
  imports/variables, redefinitions, misplaced imports, syntax-level errors).
- **Chosen version**: `ruff>=0.16,<0.17` (pinned major/minor; installed and
  tested at 0.16.4).
- **Config**: `pyproject.toml` `[tool.ruff]` / `[tool.ruff.lint]` /
  `[tool.ruff.lint.per-file-ignores]`.
- **Local command**: `python -m ruff check .`
- **CI command**: `python -m ruff check .` (job `quality` in
  `.github/workflows/ci.yml`).
- **Baseline outcome — what actually happened when run against this
  codebase**:
  - `ruff check` with **no rule selection** (Ruff's full default rule set in
    this installed version) reported **178 findings** across 22 rule
    categories, including `RUF012` (62), `F401` (29), `I001` (13, import
    sorting), `RUF015` (10), `ISC004` (9), plus `TRY004`, `DTZ005`, `BLE001`,
    `PLW1510`, `S110`, `SIM*`, `UP*`, `PIE810`, `FURB188`, `PLR1730`. Adopting
    this broad set as-is would require edits far outside I04/I05 scope
    (behavior-adjacent changes in exception handling, datetime handling,
    string concatenation style) and was rejected as too broad for this item.
  - Narrowing to a **deliberately small, high-signal selection** —
    `select = ["E4", "E7", "E9", "F"]` (pyflakes correctness rules +
    pycodestyle error/runtime classes; this mirrors Ruff's historical default
    selection) — reduced the baseline to **41 findings across 21 files**:
    29× `F401` (unused import), 7× `F841` (unused local variable), 3× `E402`
    (import not at top of file), 2× `F811` (redefinition of an unused test
    function — i.e. two same-named test functions in
    `tests/unit/test_reasoning.py` silently shadow each other; flagged here,
    left for that file's owner to resolve since fixing it changes which test
    body actually runs).
  - None of the 41 findings are in files this wave is allowed to touch for
    behavior changes: `src/qa_agent/agent/loop.py` (0 findings — clean) is
    frozen for Person 1 this wave, but `src/qa_agent/agent/router.py` (1
    `F401` finding) is also frozen and appears in the baseline. The remaining
    ~20 files span `src/qa_agent/agent`, `src/qa_agent/security`,
    `src/qa_agent/tools` and several `tests/unit/*` files that are inside
    other people's declared work areas this wave (e.g. `test_reasoning.py` /
    `test_redactor.py`).
  - **Decision**: adopt Ruff and gate CI on it (new code must pass), but do
    **not** fix the 41 pre-existing findings as part of this item — that
    would be an edit storm across files this item does not own, exactly what
    the instructions for I05 warn against. Instead, `pyproject.toml` records
    each file's exact pre-existing codes in
    `[tool.ruff.lint.per-file-ignores]`, with a comment explaining the
    baseline is dated 2026-08-20 and should shrink opportunistically as each
    file is next touched by its owner — this is the "ignore baseline file"
    option named in the task instructions. `router.py` keeps its ignore
    entry rather than being edited, consistent with the loop.py/router.py
    freeze.
  - Verified: `python -m ruff check .` reports `All checks passed!` after
    this config (no source files were modified to reach this state).

### 2. `ruff format` — DEFERRED (documented, not run in CI)

- **Purpose**: opinionated code formatter (Black-compatible).
- **Baseline outcome**: `python -m ruff format --check --isolated .` reports
  **77 of 145 files would be reformatted** (68 already formatted). This is a
  repo-wide formatting churn far beyond this item's scope and would bury any
  future `git blame`/review history under a single mechanical commit touching
  most of the codebase, including files owned by every other person this
  wave.
- **Decision**: **defer**, undocumented as a "maybe later" — flagged here
  prominently for the coordinator. If adopted later, it should land as one
  clearly-labeled, review-isolated formatting-only commit (no logic changes
  in the same commit), proposed separately from I05's CI wiring, after every
  in-flight worktree for this wave has merged (to avoid every other person's
  diff conflicting with a whole-repo reformat).
- Not wired into `.github/workflows/ci.yml`.

### 3. Static type checking (mypy or pyright) — DEFERRED

- **Purpose**: catch type errors ahead of runtime.
- **mypy**: `mypy>=2.3,<3` tested at 2.3.1 with
  `mypy src/qa_agent --ignore-missing-imports`. **Baseline: 45 errors in 16
  files.** Representative failures: `Allowlist` constructors typed to accept
  `list[Path | str]` but called with `list[str]`/`list[Path]` across
  `search.py`, `locate.py`, `analyze_test_results.py`, `analyze_coverage.py`,
  `config.py` (list invariance — mypy explicitly suggests switching those
  signatures to `Sequence`); `Optional`/`None`-handling gaps in
  `agent/loop.py` (4 errors: `Plan | None`, `dict.get` on
  `Any | None`), `crear_archivo.py` (`Path | None`); missing local variable
  annotations in `locate.py` and `openai_compatible_backend.py`.
- **pyright**: `pyright==1.1.411` tested with `pyright src/qa_agent`.
  **Baseline: 41 errors**, the same root causes (the `Allowlist` list
  invariance issue recurs in `locate.py`, `run_tests.py`, `search.py`, and
  `agent/loop.py` has `Optional`-handling errors at the same line numbers as
  mypy reported).
- **Decision**: **defer both**. Every fix requires an actual code change
  (annotate a parameter as `Sequence[Path | str]`, add an `if plan is None:
  raise` guard, add a local variable annotation) — none of this is
  config-only or auto-fixable, and a meaningful share of the errors are in
  `agent/loop.py`, which this wave's ownership rules forbid this person from
  editing. Adopting a type checker now would either (a) fail CI on files this
  item cannot fix, or (b) require a code-behavior-adjacent cleanup pass that
  is out of scope for "wire in CI." This is recorded as a **future,
  separately-scoped item**: pick one tool (mypy is the more common default
  for this kind of codebase and integrates directly via `pyproject.toml`),
  fix the `Allowlist`/`Sequence` variance issue first since it recurs across
  5 files and is genuinely one root cause, then let `agent/loop.py`'s owner
  add the `Optional` guards it needs during a wave where that file is not
  frozen.
- Not wired into `.github/workflows/ci.yml`. No `[tool.mypy]` /
  `pyrightconfig.json` was added.

### 4. Coverage (coverage.py) — ADOPTED (informational, no threshold)

- **Purpose**: measure which lines/branches the test suite exercises.
- **Chosen version**: `coverage>=7.15,<8` (installed and tested at 7.15.4).
- **Config**: `pyproject.toml` `[tool.coverage.run]` (`source = ["qa_agent"]`,
  `branch = true`), `[tool.coverage.report]` (`skip_empty = true`).
  `source` is set to the **module name** `qa_agent`, not the file path
  `src/qa_agent`: in this evaluation's worktree, the editable install
  resolves to a different on-disk path than the worktree's own `src/`
  (see Context), so path-based `source` produced a false
  `No data was collected` / 0% result while module-name-based `source`
  correctly reported real coverage regardless of which physical path the
  interpreter actually imports from. This makes the config robust to both
  ordinary (`pip install -e .` from the same directory) and worktree-style
  installs.
- **Local command**:
  `python -m coverage run -m pytest -q && python -m coverage report`
- **CI command**: same, run as the `Coverage report` step in the `quality`
  job — explicitly **not gated on a threshold**.
- **Baseline outcome**: 354 tests pass under coverage instrumentation
  (matching the ungated baseline); **84% branch coverage** overall
  (`TOTAL 2959 391 1010 167 84%`). No `fail_under` is configured: Constitution
  XII forbids imposing an arbitrary threshold without separate justification,
  and no such justification (an agreed target, an owner, an enforcement
  policy) exists yet. Coverage is reported for visibility only; a future item
  may propose a threshold with its own rationale.

### 5. pip-audit — ADOPTED

- **Purpose**: check installed dependencies against known vulnerability
  advisories (dependency/security audit, matching the item's explicit
  example).
- **Chosen version**: `pip-audit>=2.10,<3` (installed and tested at 2.10.1).
- **Config**: none needed; it audits the active environment's installed
  distributions.
- **Local command**: `python -m pip_audit`
- **CI command**: `python -m pip_audit` (job `quality`).
- **Baseline outcome**: **no known vulnerabilities found** for this project's
  dependencies (`openai`, `python-dotenv`, `pydantic`, `typer`, `rich`,
  `pathspec`, `pytest`, `ruff`, `coverage`, `pip-audit`, and their
  transitives). One package (`personal-ai-assistant`) was skipped in this
  local run because it is an unrelated project also editable-installed into
  this machine's shared interpreter — it is not a qa-agent dependency and
  will not appear on a clean CI runner, where only `pip install -e ".[dev]"`
  is run.
- Gated: a future vulnerability finding fails the `quality` job. This does
  not require an arbitrary threshold decision — "no known vulnerabilities in
  declared dependencies" is the tool's stated purpose, not an invented bar.

## Decision summary

| Tool | Purpose | Adopted? | CI step | Threshold/gate |
|---|---|---|---|---|
| Ruff (lint) | correctness lint | Yes, scoped rule set + per-file baseline | `quality` job | Fails on any non-baselined finding |
| Ruff (format) | formatting | No — deferred, documented | none | n/a |
| mypy / pyright | static types | No — deferred, documented | none | n/a |
| coverage.py | coverage measurement | Yes | `quality` job | None (report only) |
| pip-audit | dependency vuln audit | Yes | `quality` job | Fails on a known vulnerability |

## Consequences

- `pyproject.toml`'s `dev` extra gains `ruff`, `coverage`, `pip-audit`
  (Person 3 coordinates dependency additions per `tareas-divididas.md`).
- `.github/workflows/ci.yml` gains a `quality` job (I04's `test` job is
  unchanged and still reproduces exactly `python -m pytest -q` and
  `python -m pip check`).
- No source file under `src/` or `tests/` was modified to reach a clean Ruff
  run; the pre-existing findings are recorded as a per-file baseline in
  `pyproject.toml` instead. This keeps I05's diff to `pyproject.toml`,
  `.gitignore`, `.github/workflows/ci.yml` and this document.
- `agent/loop.py` and `agent/router.py` remain untouched, as required.
- A future item should: (a) shrink the Ruff per-file-ignore baseline as files
  are next touched by their owners, (b) decide whether/when to run
  `ruff format` as an isolated formatting commit, (c) pick and adopt one type
  checker once the `Allowlist`/`Sequence` variance issue and `loop.py`'s
  `Optional` handling can be fixed by their respective owners.

## Rejected alternatives

- **Enabling Ruff's full default rule set immediately**: rejected — 178
  findings, many behavior-adjacent (exception handling, datetime awareness),
  is exactly the "edit storm" this item is instructed to avoid.
- **`ruff format --fix` as part of this item**: rejected — 77/145 files would
  change; not this item's scope and not reviewable as a scoped change.
- **Fixing all 41 narrow-Ruff-baseline findings now**: rejected — most of the
  affected files are outside `src/qa_agent/agent`'s CI/tooling area and
  inside other people's declared work areas this wave (per
  `docs/tareas-divididas.md`); one affected file (`router.py`) is explicitly
  frozen this wave.
- **Adopting mypy or pyright now with a broad `# type: ignore` baseline**:
  rejected — unlike Ruff's per-file-ignore (which suppresses a named rule
  code, a config-only change), silencing 45/41 type errors would need either
  inline `# type: ignore` comments in the same forbidden/other-owned files as
  above, or such a permissive mypy config that the tool would add little
  value. Deferred instead of half-adopted.
