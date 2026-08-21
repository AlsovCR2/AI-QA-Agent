# Person 3 result — I04, I05, I06

Branch: `work/person-3`, from `abraham-full-tasks-branch` @ `561e084`
(the shared PERSON 1–6 program base; see
`docs/improvements/all-persons-progress.md`).

## Items

- I04 — Add continuous integration (TECHNICAL DEBT)
- I05 — Add development quality tooling (TECHNICAL DEBT)
- I06 — Add richer deterministic runner metadata (POST-MVP, design only)

## Status

| Item | Status |
|---|---|
| I04 | IMPLEMENTED |
| I05 | IMPLEMENTED (scoped adoption; two candidates deferred, documented) |
| I06 | DESIGNED (no contract/code change — approval gate still open) |

## Implementation completed (I04, I05)

### I04 — CI

`.github/workflows/ci.yml`, two jobs:

- `test` (matrix Python 3.11 / 3.12, justified by `pyproject.toml`'s
  `requires-python = ">=3.11"` — the floor plus the next minor, no invented
  version): `pip install -e ".[dev]"`, `python -m pytest -q`,
  `python -m pip check`. This reproduces exactly the two verified local
  checks named in the task, nothing more.
- `quality` (single run, Python 3.11): the ADR-003-approved I05 steps —
  `python -m ruff check .`, a coverage run+report (informational, no
  threshold), `python -m pip_audit`.

Trigger: `push`/`pull_request` on any branch (`branches: ["**"]`), per the
task's "at minimum on PRs — your call" — chose push+PR-on-any-branch so every
worktree in this six-person program gets feedback without needing a PR open
first.

YAML validated by parsing with `pyyaml` locally (`.github/workflows/ci.yml`
parses; job/step names enumerated and checked against the file). No GH
Actions runner is available in this environment, so the underlying shell
commands were instead run directly and verified to pass (see Tests/CI below)
— the workflow only wires already-verified commands.

### I05 — Quality tooling

Full evaluation, baseline numbers, and per-tool decisions are in
`docs/adr/ADR-003-quality-tooling.md`. Summary:

| Tool | Decision | Why |
|---|---|---|
| Ruff (lint) | **Adopted**, scoped rule set (`E4,E7,E9,F`) | Full default rule set = 178 findings (edit storm); scoped set = 41, isolated to a documented per-file baseline instead of fixed inline (see Decisions) |
| Ruff (format) | **Deferred**, documented | 77/145 files would reformat — explicit repo-wide churn, flagged for coordinator |
| mypy | **Deferred**, documented | 45 errors/16 files, several in `agent/loop.py` (frozen this wave) and needing real signature changes (`Allowlist`/`Sequence` variance), not config-only |
| pyright | **Deferred**, documented | Cross-checked mypy's conclusion: 41 errors, same root causes, same `loop.py` involvement |
| coverage.py | **Adopted**, informational only | 84% branch coverage measured; no `fail_under` (no arbitrary threshold per Constitution XII) |
| pip-audit | **Adopted**, gated | 0 known vulnerabilities in project dependencies; a future finding fails CI, which is the tool's own stated purpose, not an invented bar |

No source file under `src/` or `tests/` was edited to reach a clean `ruff
check .`. The 41 pre-existing findings are recorded as an explicit,
commented, per-file baseline in `pyproject.toml`
(`[tool.ruff.lint.per-file-ignores]`), including `router.py`'s one finding —
left as an ignore entry rather than edited, since `router.py` is frozen for
Person 1 this wave. This avoids an edit storm across ~20 files, several of
which are inside other people's declared work areas this wave (per
`docs/tareas-divididas.md`), while still gating CI so new findings fail the
build.

## Design completed (I06)

`docs/proposals/I06-runner-metadata.md` designs an additive, versioned
extension to the `run_tests` and `analyze_coverage` output contracts:
`exit_code`, `runner`, `duration_ms`, bounded `stdout_truncado` /
`stderr_truncado` (32 KiB and 500 lines per stream, head-truncated,
redacted-before-LLM like every other tool output), `salida_truncada`, and a
structured `motivo_fallo` enum. It:

- Documents T130's seven-way classification (success, ordinary failure, zero
  tests, contradictory output, unsupported output, spawn failure, timeout)
  as a table, ties each proposed field back to it, and states explicitly
  that `EstadoResultado`, `estado_global`/`estado`, and `resultado.error`
  are all unaffected — verified against
  `tests/unit/test_remediation_subprocess_semantics.py`'s actual assertions.
- Proposes a per-contract `contract_version` marker (additive minor bump;
  new fields not added to `required`) rather than a global contract-file
  version bump.
- States plainly that implementation needs Spec + Plan/ADR approval first,
  and that `specs/001-core-ai-qa-agent/contracts/tool-contracts.md` is not
  touched by this document (confirmed: `git diff` shows no change under
  `specs/`).
- Notes the I09 handoff constraint from `tareas-divididas.md` (I09 may
  reference these field names as a plausible future source but must not
  implement against them before approval).

**No contract, tool implementation, or test file was changed for I06.**

## Files changed

New:
- `.github/workflows/ci.yml`
- `docs/adr/ADR-003-quality-tooling.md`
- `docs/proposals/I06-runner-metadata.md`
- `docs/improvements/person-3-result.md` (this file)

Modified:
- `pyproject.toml` — `dev` extras gain `ruff`, `coverage`, `pip-audit`;
  new `[tool.coverage.run]`, `[tool.coverage.report]`, `[tool.ruff]`,
  `[tool.ruff.lint]`, `[tool.ruff.lint.per-file-ignores]` sections.
- `.gitignore` — adds `.coverage`, `.coverage.*`, `htmlcov/`,
  `.ruff_cache/` (new local tool artifacts, none of which should be
  committed).

Not touched: `src/qa_agent/agent/loop.py`, `src/qa_agent/agent/router.py`
(frozen this wave), and no other file under `src/` or `tests/`.

## Tests

Full suite, before and after every change in this branch:

```
python -m pytest -q
354 passed, 6156 warnings in ~5-7s
```

Matches the stated baseline (354 passed) exactly — no regression, no test
added or removed, since I04/I05/I06 add no application code and I05
deliberately avoided touching test files' lint findings.

`python -m pip check` → `No broken requirements found.` (before and after
adding the three new dev dependencies).

## CI

Commands the new `.github/workflows/ci.yml` runs, all verified locally in
this environment (Python 3.14.7 locally; workflow matrix targets 3.11/3.12
which were not available to install in this sandboxed environment, so the
underlying commands — not the exact interpreter version — were verified):

```
python -m pytest -q            → 354 passed
python -m pip check             → No broken requirements found.
python -m ruff check .          → All checks passed!
python -m coverage run -m pytest -q && python -m coverage report
                                 → 354 passed; TOTAL 84% (branch)
python -m pip_audit              → No known vulnerabilities found
```

## Decisions (ADR links)

- `docs/adr/ADR-003-quality-tooling.md` — full per-tool evaluation, baseline
  numbers, adoption/deferral decisions, and rejected alternatives for I05.

## Dependencies

Added to `pyproject.toml`'s `[project.optional-dependencies].dev` (Person 3
coordinates dependency additions per `docs/tareas-divididas.md`):

- `ruff>=0.16,<0.17` (tested at 0.16.4)
- `coverage>=7.15,<8` (tested at 7.15.4)
- `pip-audit>=2.10,<3` (tested at 2.10.1)

No production (`[project.dependencies]`) dependency was added or changed.
`requires-python` was not changed (`>=3.11`, unchanged).

## Remaining SDD gate

- I06 remains **design only**. Implementing any part of
  `docs/proposals/I06-runner-metadata.md` requires, in order: a Spec update,
  a Plan/ADR approval of the versioning approach, then a contract edit to
  `specs/001-core-ai-qa-agent/contracts/tool-contracts.md`, then code in
  `run_tests.py`/`analyze_coverage.py` plus test extensions. None of that
  is authorized by this branch.
- I05's deferred candidates (`ruff format`, mypy/pyright) each have a
  documented reason in ADR-003 and are explicitly **not** blocked on new
  Spec/Plan approval to revisit — they are ordinary follow-up technical-debt
  items once their prerequisite (a repo-wide formatting commit window for
  format; the `Allowlist`/`Sequence` variance fix plus an unfrozen
  `agent/loop.py` for typing) exists.
- The Ruff per-file-ignore baseline in `pyproject.toml` is an explicit,
  intentionally temporary carve-out, not a design gate — any file owner may
  shrink their file's entry the next time they touch that file, no approval
  needed beyond their own change's normal review.

## Risks

- **Ruff baseline drift**: the per-file-ignore list suppresses specific rule
  codes per file, not per line. If a file gains a *new* instance of an
  already-ignored code (e.g. a second unused import in a file already
  ignoring `F401`), Ruff will not flag it — the baseline is coarse-grained.
  Mitigated by keeping the ignored code list minimal (only the four codes
  actually observed) and by the ADR's guidance to shrink entries
  opportunistically.
- **CI environment drift**: workflow commands were verified in a Windows,
  Python-3.14 sandbox; the workflow itself targets Ubuntu + Python 3.11/3.12
  (per `requires-python`), which was not directly exercised here (no GH
  Actions runner available). The commands are simple and
  version/OS-agnostic (`pytest`, `pip check`, `ruff check`, `coverage`,
  `pip_audit`), so risk is low, but this is a real gap between "verified
  locally" and "verified in the target CI environment" worth flagging.
- **`pip-audit` environment sensitivity**: locally it reported one skipped,
  unrelated package (`personal-ai-assistant`) present only because this
  machine's Python environment is shared across unrelated local projects.
  This will not occur in CI's clean-checkout environment; documented in
  ADR-003 so a future reader isn't confused if they reproduce this locally
  and see the same skip.
- **`router.py` Ruff finding left unfixed**: one real, trivial `F401`
  (unused `typing.Any` import) sits in `router.py`'s per-file-ignore rather
  than being fixed, purely because that file is frozen for Person 1 this
  wave. Low risk (it is a genuinely unused import, not a functional issue),
  but it means Ruff is silent about `router.py` beyond that one baselined
  code until Person 1's wave ends.
- **Coverage `source` uses the module name (`qa_agent`), not a file path**:
  chosen because this worktree's editable install resolves to a sibling
  clone (documented in ADR-003). This is more portable, not less — but a
  future reader changing the install method (e.g. a non-editable install
  with multiple `qa_agent` copies on `sys.path`) should re-verify coverage
  still attributes correctly.
