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
| 1 | I01 | TECHNICAL DEBT | COMPLETE | 371 passed, independent reviewer: SPEC ✅, Approved, no Critical/Important findings | I02 first | pending merge |
| 1 | I02 | TECHNICAL DEBT | COMPLETE | byte-identical extraction verified by reviewer | none | pending merge |
| 2 | I03 | TECHNICAL DEBT | COMPLETE | 446 passed (PYTHONPATH-verified), 92 new | none | pending merge |
| 2 | I10 | DESIGN COMPLETE | DESIGN COMPLETE | n/a (design doc) | none | pending merge |
| 3 | I04 | TECHNICAL DEBT | COMPLETE | 354 passed (matches baseline) | none | pending merge |
| 3 | I05 | TECHNICAL DEBT | COMPLETE (scoped) | Ruff lint 41 findings on pre-existing baseline, 0 audit vulns | I04 | pending merge |
| 3 | I06 | DESIGN COMPLETE | DESIGN COMPLETE | n/a (design doc) | none | pending merge |
| 4 | I07 | TECHNICAL DEBT | COMPLETE | 364 passed (coordinator-verified), 2 rulings (widen-only) | none | pending merge |
| 4 | I11 | DESIGN COMPLETE | DESIGN COMPLETE | n/a (design doc) | I07 | pending merge |
| 4 | I13 | DESIGN COMPLETE | DESIGN COMPLETE | n/a (design doc, JS/TS selected) | I11 | pending merge |
| 5 | I08 | TECHNICAL DEBT | COMPLETE | 381 passed, T125 suite 50 passed (coordinator-verified independently) | none | pending merge |
| 5 | I09 | DESIGN COMPLETE | DESIGN COMPLETE | n/a (design doc) | I06 (optional) | pending merge |
| 5 | I12 | DESIGN COMPLETE | DESIGN COMPLETE | n/a (design doc) | none | pending merge |
| 6 | I14 | FUTURE FEATURE (design only) | NOT STARTED | - | I10 | pending |
| 6 | I15 | FUTURE FEATURE (evaluation only) | NOT STARTED | - | I10, I12 | pending |
| 6 | I16 | NOT RECOMMENDED (evaluation only) | NOT STARTED | - | I10, loop evidence | pending |

## Waves

- Wave 1 (parallel worktrees): Persons 1, 2, 3, 4, 5 — `work/person-1`..`work/person-5` from `abraham-full-tasks-branch@a69d315`.
- Wave 2: Person 6 — dispatched after Person 2 (I10) and Person 5 (I12) results are available, plus Person 1's loop.py outcome.
- Integration order into `abraham-full-tasks-branch`: Person 2 (I03) → Person 3 (I04/I05) → Person 4 (I07) → Person 5 (I08) → Person 1 (I02/I01) → cross-person wiring → all design/evaluation docs.

## Log

- Coordinator baseline verified; branch confirmed `abraham-full-tasks-branch`, clean tree, HEAD `a69d315`.
- Ledger committed at `561e084`.
- Wave 1 dispatched (parallel, isolated worktrees, branches `work/person-1..5` from `561e084`): Person 1 (I02→I01), Person 2 (I03, I10 design), Person 3 (I04, I05, I06 design), Person 4 (I07, I11/I13 design), Person 5 (I08, I09/I12 design). Awaiting completion reports.
- **Person 2 COMPLETE** (`work/person-2`, `561e084..02f2264`). I03: Option A (keep partial validator) per ADR-002 — 92-case compatibility suite added, one-line `AttributeError` robustness fix, no new dependency, no schema broadened. I10: `docs/proposals/I10-evaluation-harness.md` design-only, no code/dependencies. Coordinator-reviewed diff (small, contained, additive) — approved for integration. 446 passed full suite (PYTHONPATH-verified).
- **Person 5 COMPLETE** (`work/person-5`, `561e084..df8b4ff`). I08: 7 new redaction categories (GitHub tokens, AWS keys, standalone JWT, PEM private keys, npm tokens, connection-string credentials, generic password/secret/token assignments), each with positive+false-positive tests, all pre-verified as true gaps. I09/I12 design docs complete; I12 explicitly anchors "deterministic evidence > LLM hypothesis, never auto-VERIFIED". Coordinator independently reran (not just trusted self-report, given security sensitivity): T125 suite 50 passed, full suite 381 passed, pip check clean. Confirmed loop.py/router.py untouched.
- **Person 3 COMPLETE** (`work/person-3`, `561e084..b014a24`). I04: `.github/workflows/ci.yml` reproduces exactly `pytest -q` + `pip check` on Python 3.11/3.12 matrix (justified by `requires-python>=3.11`), separate non-blocking quality job. I05 (ADR-003): adopted Ruff lint (scoped `E4,E7,E9,F`, per-file-ignore baseline for pre-existing findings, `router.py` explicitly excluded/frozen), `coverage.py` (informational, no threshold per Constitution XII), `pip-audit` (0 vulns). Deferred `ruff format` (77/145 files would reformat — flagged, not silently applied) and mypy/pyright (45/41 errors incl. in frozen loop.py). I06: design-only, tool-contracts.md untouched, preserves T130 semantics. 354 passed (matches baseline exactly), pip check clean. Coordinator-reviewed pyproject.toml + CI yaml directly — sound.
- **Person 4 COMPLETE** (`work/person-4`, `a69d315..f98564a`). I07: new `src/qa_agent/tools/exclusion_policy.py` centralizes `NOMBRES_DIRECTORIO_EXCLUIDOS` and `PATRONES_EXCLUSION_ALLOWLIST`, consumed by `allowlist.py`/`explore.py`/`locate.py`/`search.py`/`generate_test_cases.py`. Two genuine discrepancies found and resolved by union-only (never narrowing least-privilege): (1) `generate_test_cases` excluded more dir names than explore/locate/search; (2) `Allowlist`'s queryable patterns lacked several dir names the tree-walk already pruned. A pre-existing, out-of-scope gap (`explore.py` doesn't prune `dist/`/`build/`/`.pytest_cache/` per-descendant) honestly flagged, not silently fixed or hidden. I11/I13 design-only, JS/TS selected as next-ecosystem candidate. loop.py/router.py confirmed untouched. 364 passed (coordinator-verified), pip check clean. Coordinator read `exclusion_policy.py` and the ruling docstring directly — sound.
- **WAVE 1 INTEGRATED into `abraham-full-tasks-branch`** (order: Person 2 → Person 3 → Person 4 → Person 5 → Person 1, per plan). Merge commits: `0a1125c`(ledger)→Person2(clean)→Person3(`99d0c92`, ledger conflict resolved keeping coordinator version)→Person4(clean)→Person5(clean)→Person1(`cc70f97`, ledger conflict resolved keeping coordinator version). Post-integration security gate: full suite 500 passed; T125/T126 11 passed; T130 14 passed; T128 13 passed; T129 5 passed; T127 3 passed; `pip check` clean. Integrated HEAD: `cc70f97`.
- **Person 1 COMPLETE** (`work/person-1`, `561e084..3e01192`). I02: intent/regex policy centralized into `intent_policy.py`/`layer_policy.py`/`runner_detection.py`/`grounding.py` — byte-identical extraction (independent reviewer diffed against pre-extraction `loop.py` line by line, confirmed `is`-identity on re-exported functions). I01: `plan_enrichment.py` extracted (medium risk); T125/T126 authorization/execution boundary deliberately left in `loop.py` (1358 lines remain, all orchestration/security-boundary) — reviewer confirmed this is a defensible, well-documented stop point, not a shortcut. Independent reviewer verdict: SPEC ✅, Approved, zero Critical/Important findings. 371 passed, T125/T130 regressions 25/25 passed (reviewer's own rerun, plus coordinator's earlier independent rerun). `router.py` untouched (reviewed as already cohesive). **WAVE 1 COMPLETE — all 5 persons COMPLETE/DESIGN COMPLETE and reviewed.**
- **ENVIRONMENT HAZARD (discovered by Person 2, verified by coordinator):** this machine has a stray global editable `qa-agent` install pointing at an unrelated clone `C:\Users\AbrahamVillalobosUga\qa-agent` (same origin, was at the same `a69d315` commit but does NOT track this worktree's changes). Plain `python -m pytest -q` / `python -c "import qa_agent"` silently resolves to that OTHER clone, not this repo's working tree. **All verification from here on MUST use `PYTHONPATH="<repo>/src" python -m pytest -q`** (confirmed this forces the correct `src/qa_agent`). Coordinator's original baseline (354 passed) is valid because both clones were identical at that commit, but every worker's self-reported test result must be re-checked for this trap before being trusted. Person 3 (I04/CI) must not reproduce this trap in the CI workflow (CI runners won't have the stray install, but local `pip install -e .` steps must target this checkout).
