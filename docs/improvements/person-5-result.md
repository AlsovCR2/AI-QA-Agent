# Person 5 — Result (I08, I09, I12)

Branch: `work/person-5`, based on `abraham-full-tasks-branch@561e084`.

## Items

| Item | Classification | Scope this wave |
|---|---|---|
| I08 | TECHNICAL DEBT | Implement |
| I09 | POST-MVP | Design only |
| I12 | POST-MVP | Design only |

## Status

DONE.

## Implementation completed (I08)

`src/qa_agent/security/redactor.py` gained seven new detector categories,
added in three reviewable commits (TDD: RED test confirming the gap →
implement minimal pattern → GREEN → rerun T125 regression suite before
moving on). Every category has one positive test and one false-positive
test in `tests/unit/test_redactor.py`.

| Category | Pre-change status | Verdict | Pattern added |
|---|---|---|---|
| GitHub tokens (`ghp_`/`gho_`/`ghs_`/`github_pat_`) | Not caught by any existing pattern (confirmed by RED run) | True gap — implemented | `\b(?:ghp|gho|ghs)_[A-Za-z0-9]{36,}\b` and `\bgithub_pat_[A-Za-z0-9_]{20,}\b` |
| AWS access key IDs (`AKIA...`) | Not caught | True gap — implemented | `\bAKIA[0-9A-Z]{16}\b` |
| JWT without a `Bearer ` prefix | Existing `Bearer\s+...` pattern only caught JWTs *after* the word "Bearer"; a bare JWT was not caught | True gap — implemented | `\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b` (anchored on the `eyJ` JSON-header base64 prefix to avoid matching version strings/domains) |
| PEM private key blocks | Not caught | True gap — implemented | `-----BEGIN (?:RSA \|EC \|DSA \|OPENSSH \|)PRIVATE KEY-----[\s\S]+?-----END (?:...)PRIVATE KEY-----`; PUBLIC KEY blocks are explicitly excluded (not secret) |
| npm registry tokens (`npm_...`) | Not caught | True gap — implemented | `\bnpm_[A-Za-z0-9]{36}\b` |
| DB/connection-string embedded credentials (`scheme://user:pass@host`) | Not caught | True gap — implemented | `(?<=://)[^\s:@/]{1,100}:[^\s@/]{1,200}(?=@)` — lookbehind/lookahead so only the `user:pass` segment is masked; scheme, host, path are preserved for diagnosability |
| Generic `password=`/`secret=`/`token=` assignments | Not caught (the existing pattern only handles `api[_-]?key=`) | True gap — implemented | `\b(?:password\|secret\|token)\s*=\s*(?!\*\*\*(?:[\s'"]\|$))['"]?[^\s'"&]+['"]?` — exact-word match only (compound identifiers like `reset_token` are untouched because `\b` does not fire between `_` and `token`), plus a negative lookahead so it does not re-collapse a value already redacted by an earlier pattern in the same pass |

No candidate category was skipped as too ambiguous. All seven listed in the
task were true gaps against the pre-change patterns (confirmed by running
each positive test before the corresponding implementation commit and
observing failure), and each admitted a pattern narrow enough to pass its
paired false-positive test (UUID, git commit hash, non-`AKIA` 20-char ID,
semver/domain string, single-segment base64 blob, public-key PEM block,
plain hex checksum, URL without embedded credentials, time-of-day + email
text, compound identifier). The generic `password=/secret=/token=` pattern
carries the highest residual false-positive *breadth* risk of the seven
(it will also redact non-secret placeholder values such as
`password=changeme` or a boolean-like `secret=True`) — this is treated as
acceptable over-redaction (a value is masked, not corrupted; the assignment
key and structure remain legible) rather than a genuine false positive,
and it is scoped narrowly to the exact keys `password`/`secret`/`token`,
not to any key containing those words as a substring.

### Idempotency detail worth flagging for review

The generic assignment pattern runs last in the pattern list. Without the
`(?!\*\*\*(?:[\s'"]|$))` negative lookahead, it would re-match an
already-redacted `token=***` (produced earlier in the same pass by the
`sk-` pattern, for example) and collapse it to bare `***`, losing the key
name and breaking two pre-existing tests
(`test_secretos_no_aparecen_en_respuesta_ni_historial`,
`test_secretos_no_aparecen_en_logs`) that assert `"token=***"` is preserved.
This was caught by rerunning the full `test_redactor.py` file after adding
the pattern (not just the new tests) — a reminder that new patterns must be
checked against the *whole* suite, not only their own group.

## Design completed (I09, I12)

- `docs/proposals/I09-observability.md` — opt-in, default-OFF structured
  observability layer: correlation ID, per-tool duration, model/provider
  identifier, authorization decision, stop reason, token usage. Defines a
  sensitivity classification table for every field, requires the whole
  event dict to be routed through the existing `Redactor` (structural
  safety, not per-field discipline), a bounded/non-persistent retention
  policy, and an explicit off-by-default justification tied to Constitution
  IV/V/XI. References I06 as optional future input only; does not block on
  it.
- `docs/proposals/I12-evidence-provenance.md` — bounded `Provenance` object
  (source type, path, line/range, content hash, excerpt capped at 500
  chars, verbatim-only, passed through `Redactor`). States the core
  invariant as a named rule ("Rule I12-1 — Deterministic Precedence"):
  deterministic evidence always outranks LLM hypothesis, and LLM output can
  never automatically be promoted to `DETERMINISTIC` — `EvidenceOrigin` is
  a closed two-value enum with no promotion path, specifically so Person
  6's I15 inherits this constraint rather than re-deriving it.

Both documents are design-only: no dataclass, contract, or existing file
other than the redactor/tests was touched to produce them.

## Files changed

- `src/qa_agent/security/redactor.py` — 7 new patterns (3 commits)
- `tests/unit/test_redactor.py` — 27 new tests (9 + 6 + 12 across the 3 groups)
- `docs/proposals/I09-observability.md` — new
- `docs/proposals/I12-evidence-provenance.md` — new
- `docs/improvements/person-5-result.md` — new (this file)

## Tests

- Baseline (at `561e084`, before this branch's changes): `354 passed`.
- Final `python -m pytest -q`: **381 passed** (354 + 27 new redactor tests),
  `python -m pip check`: clean.
- `tests/unit/test_redactor.py` alone: 39 passed (12 pre-existing + 27 new).

## Security regression evidence (T125)

`python -m pytest tests/unit/test_remediation_security.py tests/unit/test_redactor.py -q`
was rerun after every pattern-group commit (3 times) and again at the end:
final result **50 passed**, 0 failed. T125's core property — raw protected
values never reach the external LLM/backend (`_assert_frontera_redactada`
in `test_remediation_security.py`) — is unaffected: this work only adds
detectors to the `Redactor`, it does not touch the redaction call sites in
`loop.py` that T125 exercises.

## Dependencies

- I08 has no dependency (developed and tested the `Redactor` in isolation,
  per the coordinator's note "No depende de: I01 para desarrollar y probar
  el `Redactor`").
- I09 optionally references Person 3's I06 runner-metadata design as a
  future input; does not block on it, per instructions.
- I12 has no dependency and is itself a dependency for Person 6's I15
  (Rule I12-1 must hold before I15 is designed).

## Remaining SDD gate

Both I09 and I12 remain **design-only** per their POST-MVP classification.
Neither may be implemented until a future Spec + Plan/ADR is written and
approved, consistent with `qa-agent-improvement-backlog.md` (`Requires
future Spec: DEPENDS/YES`, `Requires future Plan/ADR: YES` for both items)
and with the coordinator's ledger. I08 is TECHNICAL DEBT and was
implemented directly, matching its backlog classification
(`Requires future Spec: NO`); its `Requires future Plan/ADR: DEPENDS` was
resolved as "no plan needed" because the change is additive, pattern-level,
fully covered by paired positive/false-positive tests, and does not touch
any approved contract or the redaction call sites themselves.

## Risks

- **Generic assignment pattern breadth.** `password=`/`secret=`/`token=`
  will mask non-secret placeholder values (e.g. `secret=False`). Accepted
  as over-redaction rather than a defect; flagged here for reviewer
  visibility rather than silently shipped.
- **PEM block regex is non-greedy but not header-matched.** Two PEM blocks
  of *different* types placed back-to-back with no other content between
  them (e.g. a truncated `BEGIN RSA PRIVATE KEY` immediately followed by an
  unrelated `END EC PRIVATE KEY` from a different, malformed block) could
  in theory match across both. This is a pre-existing-style trade-off
  (minimal pattern, not a full PEM parser) and is documented rather than
  engineered around, since real PEM files do not interleave key types this
  way.
- **Connection-string pattern is scheme-agnostic.** It fires on any
  `scheme://user:pass@` regardless of scheme (not just DB schemes), which
  is intentionally broader than "database connection strings" — any
  embedded Basic-Auth-style URL credential is equally sensitive, so this is
  treated as correct behavior, not scope creep, but is called out in case
  a reviewer expected DB-only scoping.
- **Local dev environment note (not a code risk):** this worktree's Python
  environment resolves the editable `qa_agent` install to a *different*
  clone (`C:\Users\AbrahamVillalobosUga\qa-agent`) rather than this
  worktree's `src/`. All test runs in this session set
  `PYTHONPATH=<worktree>/src` explicitly to target the correct source tree;
  a reviewer rerunning `python -m pytest -q` without setting `PYTHONPATH`
  from within this worktree may silently test the wrong checkout. Flagging
  this for the coordinator since it likely affects other persons' worktrees
  identically.

## Confirmed constraints honored

- `src/qa_agent/agent/loop.py` and `src/qa_agent/agent/router.py` were not
  modified (`git diff --stat 561e084 -- loop.py router.py` is empty).
- No persistent storage, no `.qa_sessions` revival, introduced anywhere in
  this branch (I08 is pattern-only; I09/I12 are design documents that
  explicitly rule persistence out of scope).
- Nothing was pushed; all work is local to `work/person-5`.
