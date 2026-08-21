# PERSON 1–6 Program — Global Execution Ledger

Target branch: `abraham-full-tasks-branch`
Starting HEAD: `a69d3150b8854670067230b12b6ee4b76ede5688`
Baseline: 354 passed, `pip check` clean, Python 3.14.7 (metadata requires `>=3.11`).
`loop.py`: 1947 lines. `router.py`: 284 lines.

Authority order used: Constitution → Spec → Plan → contracts → tasks.md →
remediation log (T125–T131, immutable) → improvement backlog → tareas-divididas.md.

No existing ADR directory found; workers create `docs/adr/ADR-0XX-<slug>.md`.
No existing `.github/workflows`; Person 3 creates the first one.

| Person | Item | Classification | Status | Tests | Dependency | Integration |
|---|---|---|---|---|---|---|
| 1 | I01 | TECHNICAL DEBT | NOT STARTED | - | I02 first | pending |
| 1 | I02 | TECHNICAL DEBT | NOT STARTED | - | none | pending |
| 2 | I03 | TECHNICAL DEBT | NOT STARTED | - | none | pending |
| 2 | I10 | POST-MVP (design only) | NOT STARTED | - | none | pending |
| 3 | I04 | TECHNICAL DEBT | DONE | 354 passed | none | pending |
| 3 | I05 | TECHNICAL DEBT | DONE (scoped; ruff format + mypy/pyright deferred, documented) | 354 passed | I04 | pending |
| 3 | I06 | POST-MVP (design only) | DONE (design only) | 354 passed (no code touched) | none | pending |
| 4 | I07 | TECHNICAL DEBT | NOT STARTED | - | none | pending |
| 4 | I11 | POST-MVP (design only) | NOT STARTED | - | I07 | pending |
| 4 | I13 | FUTURE FEATURE (design only) | NOT STARTED | - | I11 | pending |
| 5 | I08 | TECHNICAL DEBT | NOT STARTED | - | none | pending |
| 5 | I09 | POST-MVP (design only) | NOT STARTED | - | I06 (optional) | pending |
| 5 | I12 | POST-MVP (design only) | NOT STARTED | - | none | pending |
| 6 | I14 | FUTURE FEATURE (design only) | NOT STARTED | - | I10 | pending |
| 6 | I15 | FUTURE FEATURE (evaluation only) | NOT STARTED | - | I10, I12 | pending |
| 6 | I16 | NOT RECOMMENDED (evaluation only) | NOT STARTED | - | I10, loop evidence | pending |

## Waves

- Wave 1 (parallel worktrees): Persons 1, 2, 3, 4, 5 — `work/person-1`..`work/person-5` from `abraham-full-tasks-branch@a69d315`.
- Wave 2: Person 6 — dispatched after Person 2 (I10) and Person 5 (I12) results are available, plus Person 1's loop.py outcome.
- Integration order into `abraham-full-tasks-branch`: Person 2 (I03) → Person 3 (I04/I05) → Person 4 (I07) → Person 5 (I08) → Person 1 (I02/I01) → cross-person wiring → all design/evaluation docs.

## Log

- Coordinator baseline verified; branch confirmed `abraham-full-tasks-branch`, clean tree, HEAD `a69d315`.
- Person 3 (`work/person-3` from `561e084`): I04 CI workflow
  (`.github/workflows/ci.yml`), I05 quality tooling adopted (Ruff lint scoped
  rule set, coverage.py informational, pip-audit gated) per
  `docs/adr/ADR-003-quality-tooling.md`, I06 design
  (`docs/proposals/I06-runner-metadata.md`, no contract/code change). No
  file under `src/` or `tests/` modified; `agent/loop.py`/`agent/router.py`
  untouched. `pyproject.toml` and `.gitignore` updated. 354 passed
  throughout; `pip check` clean. Details: `docs/improvements/person-3-result.md`.
