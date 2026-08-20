# AI-QA-Agent Improvement Backlog

## Scope and authority

This is an advisory backlog, not an authoritative SDD artifact. It does not
modify the Constitution, Spec, Plan, contracts or canonical Tasks and grants no
implementation authority. T125–T131 remain the complete remediation scope.
Items below require a separate approval when indicated; none may be implemented
during the current remediation except for the explicitly identified narrow
overlap.

## I01 — Modularize `agent/loop.py`

**Observed opportunity:** `src/qa_agent/agent/loop.py` is approximately 1,900
physical lines and combines routing support, planning enrichment, authorization,
execution, evidence handling, response policy and several intent heuristics.

**Potential value:** Smaller cohesive units could reduce regression surface,
clarify ownership and make security boundaries easier to test.

**Current SDD status:** TECHNICAL DEBT

**Covered by T125–T131:** NO

**Requires future Spec:** NO

**Requires future Plan/ADR:** YES

**Estimated complexity:** HIGH

**Recommendation:** REVISIT AFTER T131

**Reason:** The current remediation needs narrow changes in the loop, but a
broad refactor would obscure security/correctness evidence. Plan incremental
extractions only after the focused regressions are stable.

## I02 — Reduce or move hardcoded intent phrase and regex tables

**Observed opportunity:** `loop.py` contains `_FRASES_ANALISIS_GLOBAL`,
`_FRASES_INTENCION_PRUEBAS`, layer verbs/connectors and detection regexes;
`router.py` contains additional phrase/regex routing rules.

**Potential value:** A single focused policy module or declarative table could
make intent coverage auditable and reduce accidental overlap.

**Current SDD status:** TECHNICAL DEBT

**Covered by T125–T131:** NO

**Requires future Spec:** NO

**Requires future Plan/ADR:** DEPENDS

**Estimated complexity:** MEDIUM

**Recommendation:** REVISIT AFTER T131

**Reason:** Moving equivalent rules is internal cleanup; changing their semantic
coverage would require explicit behavior review. Do not combine it with T125 or
T126.

## I03 — Strengthen the partial JSON Schema validator

**Observed opportunity:** `tools/base.py` implements a custom subset supporting
`type`, `properties`, `required`, `items`, `enum`, `minimum` and `maximum`.
Pydantic is installed, but the tool contracts are currently validated by this
partial implementation.

**Potential value:** A standards-compliant validator could improve nested error
reporting and reduce divergence as schemas grow.

**Current SDD status:** TECHNICAL DEBT

**Covered by T125–T131:** NO

**Requires future Spec:** NO

**Requires future Plan/ADR:** YES

**Estimated complexity:** MEDIUM

**Recommendation:** KEEP IN BACKLOG

**Reason:** Existing contract tests cover the used subset and no approved gap
demonstrates incorrect validation. Replacing it now would add dependency and
compatibility risk unrelated to remediation.

## I04 — Add continuous integration

**Observed opportunity:** No active workflow was found under `.github/workflows`
for automatically running the repository's tests on changes.

**Potential value:** Repeatable branch/PR verification across supported Python
versions and operating systems.

**Current SDD status:** TECHNICAL DEBT

**Covered by T125–T131:** NO

**Requires future Spec:** NO

**Requires future Plan/ADR:** YES

**Estimated complexity:** MEDIUM

**Recommendation:** REVISIT AFTER T131

**Reason:** CI does not repair T125–T130 and must not be introduced through the
closure gate. Add it later around the verified command set.

## I05 — Add development quality tooling

**Observed opportunity:** `pyproject.toml` configures pytest but not Ruff,
static type checking or a project coverage threshold.

**Potential value:** Earlier detection of style, dead-code, typing and coverage
regressions.

**Current SDD status:** TECHNICAL DEBT

**Covered by T125–T131:** NO

**Requires future Spec:** NO

**Requires future Plan/ADR:** YES

**Estimated complexity:** MEDIUM

**Recommendation:** REVISIT AFTER T131

**Reason:** Tool selection and enforcement levels need a separate developer
workflow decision. T131 must use only already-configured validation.

## I06 — Add richer deterministic runner metadata

**Observed opportunity:** Existing tool contracts expose counts/states but not
`exit_code`, bounded stdout/stderr, detected runner, duration or a structured
reason.

**Potential value:** Better diagnostics, reproducibility and downstream
correlation without relying on free-form text.

**Current SDD status:** POST-MVP

**Covered by T125–T131:** NO

**Requires future Spec:** YES

**Requires future Plan/ADR:** YES

**Estimated complexity:** MEDIUM

**Recommendation:** KEEP IN BACKLOG

**Reason:** T130 may use return code and output internally but cannot expand the
approved output schema. New public fields require contract/version decisions.

## I07 — Centralize ignore and exclusion policy

**Observed opportunity:** Ignore sets are duplicated across `allowlist.py`,
`explore.py`, `generate_test_cases.py` and `loop.py`; `locate.py` and `search.py`
reuse only the explore set.

**Potential value:** Consistent discovery, fewer accidental scans of build/VCS
content and one auditable policy surface.

**Current SDD status:** TECHNICAL DEBT

**Covered by T125–T131:** NO

**Requires future Spec:** NO

**Requires future Plan/ADR:** DEPENDS

**Estimated complexity:** MEDIUM

**Recommendation:** KEEP IN BACKLOG

**Reason:** Centralization is useful but can change discovery output subtly.
Execute separately with focused compatibility tests.

## I08 — Expand secret-redaction pattern coverage

**Observed opportunity:** `security/redactor.py` currently recognizes `sk-*`,
Bearer tokens, `api_key=` variants and an ASS-like generic form. No verified
example currently proves that an approved secret category bypasses these
patterns; T125 instead proves the placement of this existing policy.

**Potential value:** Coverage for additional provider tokens, password/secret
assignments, private keys and configurable organization-specific formats.

**Current SDD status:** TECHNICAL DEBT

**Covered by T125–T131:** NO

**Requires future Spec:** NO

**Requires future Plan/ADR:** DEPENDS

**Estimated complexity:** MEDIUM

**Recommendation:** KEEP IN BACKLOG

**Reason:** Pattern expansion has false-positive and data-loss tradeoffs. T125
must reuse the approved Redactor policy; pattern work should be evidence-driven
and independently tested. No TASK COVERAGE GAP is asserted without a concrete
existing bypass.

## I09 — Add lightweight structured observability

**Observed opportunity:** Logging is redacted and formatted, while durations,
correlation IDs, provider/model, authorization decisions, stop reasons and
actual token usage are not consistently represented as structured events.

**Potential value:** Faster diagnosis, request correlation and cost/performance
analysis while preserving secrecy.

**Current SDD status:** POST-MVP

**Covered by T125–T131:** NO

**Requires future Spec:** DEPENDS

**Requires future Plan/ADR:** YES

**Estimated complexity:** MEDIUM

**Recommendation:** REVISIT AFTER T131

**Reason:** Constitution VIII supports traceability, but these exact fields and
retention rules are not approved. Authorization logging must be designed with
FR-021 before implementation.

## I10 — Add a formal benchmark/evaluation harness

**Observed opportunity:** The repository has deterministic unit fixtures but no
versioned evaluation corpus with golden expectations and reproducible aggregate
metrics for agent quality.

**Potential value:** Detect semantic quality regressions and compare models or
prompt changes using stable scenarios.

**Current SDD status:** POST-MVP

**Covered by T125–T131:** NO

**Requires future Spec:** YES

**Requires future Plan/ADR:** YES

**Estimated complexity:** HIGH

**Recommendation:** REVISIT AFTER T131

**Reason:** Metrics, acceptable drift, fixtures and provider variability require
a product/evaluation design. The prompt explicitly excludes a benchmark harness
from current remediation.

## I11 — Improve structured language and symbol discovery

**Observed opportunity:** Language/runner recognition uses marker files and
extension/regex heuristics; symbol discovery is not backed by ASTs, language
servers or standardized indexes across ecosystems.

**Potential value:** More precise requirement-to-symbol discovery and fewer
false positives for large multi-language projects.

**Current SDD status:** POST-MVP

**Covered by T125–T131:** NO

**Requires future Spec:** YES

**Requires future Plan/ADR:** YES

**Estimated complexity:** HIGH

**Recommendation:** KEEP IN BACKLOG

**Reason:** This is new capability depth, not required to close any canonical
gap. Language-specific dependencies and fallback behavior need approval.

## I12 — Add structured evidence provenance

**Observed opportunity:** Observations carry a plan step and tool result, but no
uniform provenance object with source type, path, line/range, hash and bounded
excerpt.

**Potential value:** Stable citations, deduplication and later verification of
whether evidence changed between runs.

**Current SDD status:** POST-MVP

**Covered by T125–T131:** NO

**Requires future Spec:** YES

**Requires future Plan/ADR:** YES

**Estimated complexity:** HIGH

**Recommendation:** KEEP IN BACKLOG

**Reason:** It changes data and tool contracts and overlaps future audit-engine
concepts explicitly excluded from current remediation.

## I13 — Add ecosystem and language support

**Observed opportunity:** The code recognizes Python, .NET, Maven/Java and
Gradle conventions plus multiple source extensions, but many runners, coverage
formats and language semantics remain unsupported.

**Potential value:** Broader applicability to JavaScript/TypeScript, Go, Rust
and other ecosystems.

**Current SDD status:** FUTURE FEATURE

**Covered by T125–T131:** NO

**Requires future Spec:** YES

**Requires future Plan/ADR:** YES

**Estimated complexity:** HIGH

**Recommendation:** KEEP IN BACKLOG

**Reason:** Each ecosystem needs explicit command allowlists, parsing contracts,
fixtures and security review; none belongs to current correctness work.

## I14 — Add future CLI capabilities

**Observed opportunity:** The approved CLI lacks `--json`, `--no-color`,
`--max-steps`, `--model`, `--dry-run`, `--trace-file` and `qa-agent eval`.

**Potential value:** Better automation, CI consumption, reproducibility and
operator control.

**Current SDD status:** FUTURE FEATURE

**Covered by T125–T131:** NO

**Requires future Spec:** YES

**Requires future Plan/ADR:** YES

**Estimated complexity:** MEDIUM

**Recommendation:** KEEP IN BACKLOG

**Reason:** T129 restores only the existing CLI contract. Adding flags while
repairing that contract would be unauthorized scope expansion.

## I15 — Evaluate future semantic QA with LangChain

**Observed opportunity:** Candidate semantic work could include requirement-to-
code/test suggestions, edge-case proposals or hypothesis generation where
deterministic tools cannot establish relationships alone.

**Potential value:** Optional structured prompting/chains around semantic
hypotheses, provided deterministic evidence remains authoritative.

**Current SDD status:** FUTURE FEATURE

**Covered by T125–T131:** NO

**Requires future Spec:** YES

**Requires future Plan/ADR:** YES

**Estimated complexity:** HIGH

**Recommendation:** REVISIT AFTER T131

**Reason:** LangChain is explicitly out of scope. Any future output must remain
a HYPOTHESIS until independently verified and must never control evidence,
authorization, integrity or final deterministic status.

## I16 — Evaluate LangGraph/LlamaIndex orchestration alternatives

**Observed opportunity:** The repository currently uses a custom Python ReAct
loop; no approved evidence shows that replacing orchestration would simplify
the product enough to offset migration risk.

**Potential value:** Potentially useful only if future workflows become
materially more stateful, branching or resumable than the approved MVP.

**Current SDD status:** NOT RECOMMENDED

**Covered by T125–T131:** NO

**Requires future Spec:** YES

**Requires future Plan/ADR:** YES

**Estimated complexity:** HIGH

**Recommendation:** REVISIT AFTER T131

**Reason:** Migration is explicitly excluded and would obscure the current
security/correctness remediation. Re-evaluate only from measured orchestration
pain and a separately approved product change; do not migrate for framework
parity.

## Classification summary

- **Technical debt:** I01, I02, I03, I04, I05, I07, I08.
- **Post-MVP:** I06, I09, I10, I11, I12.
- **Future features:** I13, I14, I15.
- **Not recommended at current maturity:** I16.
- **Task coverage gaps:** NONE. No inspected candidate demonstrates an existing
  approved Spec violation outside T125–T131.
