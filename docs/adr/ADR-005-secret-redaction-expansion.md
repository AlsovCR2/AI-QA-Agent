# ADR-005: Expand secret-redaction pattern coverage (I08)

- Status: Accepted (retroactive — decision was made and implemented by
  Person 5 in `work/person-5`; this ADR formalizes it after the fact,
  per the final whole-branch review's I-2 finding)
- Date decided: 2026-08-20 (Person 5, I08). ADR recorded: 2026-08-21.
- Owner: Person 5 (`work/person-5`)
- Backlog item: I08 (TECHNICAL DEBT — redactor pattern coverage gaps),
  `docs/improvements/qa-agent-improvement-backlog.md`
- Related: `src/qa_agent/security/redactor.py`,
  `tests/unit/test_redactor.py`, `tests/unit/test_remediation_security.py`
  (T125), `docs/improvements/person-5-result.md`
- Constitution principles engaged: IV (least privilege), XI (secrets never
  cross the LLM boundary unredacted), VI (determinism), X (no needless
  over-broadening without evidence)

## Context

`src/qa_agent/security/redactor.py`'s `Redactor` is the single mechanism
standing between raw tool output/session state and anything that leaves
the security boundary — the external LLM backend, the response returned
to the caller, and the visible session history (FR-021 / SC-008 / XI,
exercised end-to-end by the T125 regression suite in
`tests/unit/test_remediation_security.py`). Its coverage was pattern-based
and, before I08, did not cover several common real-world secret shapes:
GitHub tokens, AWS access key IDs, bare (non-`Bearer`-prefixed) JWTs, PEM
private key blocks, npm registry tokens, connection-string embedded
credentials, and generic `password=`/`secret=`/`token=` assignments (the
existing pattern only handled `api[_-]?key=`).

I08 asks whether these seven candidate gaps are true gaps against the
current patterns, and if so, to close them without weakening any existing
guarantee.

## Method

TDD, one category at a time, in three reviewable commits: write a RED test
proving the gap against the *unmodified* redactor, implement the minimal
pattern to turn it GREEN, then rerun the full T125 regression suite before
moving to the next category (not just the new tests — see the idempotency
finding below, which was only caught by rerunning the whole file). Every
category got one positive test (secret is masked) and one false-positive
test (a superficially-similar-but-not-secret value is left intact).

## Findings

All seven candidate categories were confirmed as true, previously-uncaught
gaps (each RED test failed against the pre-change redactor before its
corresponding pattern was added):

| Category | Pattern added | False-positive guard |
|---|---|---|
| GitHub tokens (`ghp_`/`gho_`/`ghs_`/`github_pat_`) | `\b(?:ghp\|gho\|ghs)_[A-Za-z0-9]{36,}\b` and `\bgithub_pat_[A-Za-z0-9_]{20,}\b` | Prefix-anchored; does not fire on arbitrary 36-char strings |
| AWS access key IDs | `\bAKIA[0-9A-Z]{16}\b` | `AKIA` prefix required; a non-`AKIA` 20-char ID passes through |
| Bare JWT (no `Bearer ` prefix) | `\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b` | Anchored on the `eyJ` JSON-header base64 prefix and three dot-separated segments; does not match a single-segment base64 blob |
| PEM private key blocks | `-----BEGIN (?:RSA \|EC \|DSA \|OPENSSH \|)PRIVATE KEY-----[\s\S]+?-----END (?:...)PRIVATE KEY-----` | `PUBLIC KEY` blocks explicitly excluded from the alternation (not secret) |
| npm registry tokens | `\bnpm_[A-Za-z0-9]{36}\b` | Prefix + fixed length required |
| Connection-string embedded credentials | `(?<=://)[^\s:@/]{1,100}:[^\s@/]{1,200}(?=@)` | Lookbehind/lookahead scoped so only the `user:pass` segment is masked; scheme, host, path stay legible; a URL without embedded credentials does not match |
| Generic `password=`/`secret=`/`token=` assignments | `\b(?:password\|secret\|token)\s*=\s*(?!\*\*\*(?:[\s'"]\|$))['"]?[^\s'"&]+['"]?` | Exact-word match only — `\b` does not fire between `_` and `token`, so compound identifiers like `reset_token` are untouched; negative lookahead prevents re-collapsing an already-redacted `token=***` from an earlier pattern in the same pass |

No candidate was skipped as too ambiguous — every one admitted a pattern
narrow enough to pass its paired false-positive test (UUID, git commit
hash, non-`AKIA` ID, semver/domain string, single-segment base64, public-key
PEM, plain hex checksum, credential-free URL, time-of-day + email text,
compound identifier).

**Idempotency hazard caught during implementation:** the generic assignment
pattern runs last in the pattern list. Without its negative lookahead, it
would re-match an already-redacted `token=***` (produced earlier in the
same pass by, e.g., the `sk-` pattern) and collapse it to bare `***`,
losing the key name and breaking two pre-existing tests that assert
`"token=***"` is preserved verbatim. This is why every pattern-group commit
reran the *whole* `test_redactor.py` file, not just its own new tests.

## Decision

Add all seven patterns to `Redactor`, each scoped as narrowly as its
false-positive test demands, in three separate commits (not one), so each
group is independently reviewable and independently revertible. The
generic `password=`/`secret=`/`token=` pattern is accepted with a known,
explicitly-documented breadth trade-off (below) rather than narrowed
further or dropped, because narrowing it (e.g. requiring a minimum value
length or excluding common placeholder words) would reintroduce exactly
the kind of untested, unproven heuristic I08 set out to avoid — the
existing scope (exact key match, not substring) is already the narrowest
version that reliably catches the real gap.

## Alternatives considered

- **Do nothing / defer all seven as "acceptable residual risk."** Rejected:
  each RED test demonstrated a real, currently-unredacted secret shape that
  could reach the LLM backend or a visible response, directly cutting
  against XI/FR-021. TECHNICAL DEBT classification plus a demonstrated gap
  is exactly the case I08 is scoped to close.
- **Implement all seven as one commit.** Rejected in favor of one commit
  per pattern group: each pattern carries its own false-positive risk
  profile (see table), and a single large regex commit is harder to review
  or bisect if one pattern later needs narrowing.
- **Scope the connection-string pattern to known DB schemes only
  (`postgres://`, `mysql://`, …).** Rejected: the risk is Basic-Auth-style
  embedded credentials, which is a URL-syntax property, not a
  database-specific one — any `scheme://user:pass@` is equally sensitive
  regardless of scheme. Scoping to a scheme allowlist would create false
  negatives for schemes not yet enumerated, with no compensating precision
  benefit (the pattern's false-positive test suite already showed
  credential-free URLs pass through cleanly regardless of scheme).
- **Narrow the generic `password=/secret=/token=` pattern to avoid masking
  non-secret placeholder values** (e.g. `password=changeme`,
  `secret=False`). Considered and explicitly rejected: this is accepted as
  intentional over-redaction (a value is masked, not corrupted or removed —
  the assignment key and surrounding structure remain legible) rather than
  a defect, because any heuristic to exclude "placeholder-looking" values
  would itself be an unproven, untested judgment call about what counts as
  a real secret — exactly the kind of complexity XII asks to avoid without
  concrete evidence of a real false-positive problem in practice.

## Consequences

- Positive: seven previously-unredacted real-world secret shapes are now
  masked before reaching the LLM backend, the returned response, or the
  visible session history, closing a genuine gap against FR-021/SC-008/XI.
- Positive: zero changes to the redaction call sites in `loop.py` that T125
  exercises — this ADR is scoped entirely to `Redactor`'s pattern list, so
  T125's core property (raw protected values never reach the external
  LLM/backend) is unaffected by construction, not just by test result.
- Accepted trade-off: the generic assignment pattern will over-redact some
  non-secret placeholder values (`password=changeme`, `secret=False`).
  Documented here and in `docs/improvements/person-5-result.md` for
  reviewer visibility; not treated as a defect to silently ship or
  silently fix.
- Accepted trade-off: the PEM-block pattern is non-greedy but not
  header/footer-type-matched — two malformed, back-to-back PEM blocks of
  different key types with nothing between them could in theory match
  across both. Judged acceptable (minimal pattern, not a full PEM parser);
  real PEM files do not interleave key types this way.
- No new dependency; `pip check` stays clean.

## Verification

- `tests/unit/test_redactor.py`: 27 new tests (9 + 6 + 12 across the three
  commits), one positive + one false-positive per category; 39 passed
  total (12 pre-existing + 27 new) at the end.
- Full suite: 381 passed (354 baseline + 27 new), 0 failed.
- T125 regression, rerun after every pattern-group commit and again at the
  end: `tests/unit/test_remediation_security.py` + `test_redactor.py`
  together — 50 passed, 0 failed.
- `python -m pip check`: clean.
- `src/qa_agent/agent/loop.py` / `src/qa_agent/agent/router.py` confirmed
  untouched (`git diff --stat 561e084 -- loop.py router.py` empty) — this
  decision only adds detectors to `Redactor`, it does not touch any
  redaction call site.
