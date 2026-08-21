# I15 — Semantic QA evaluation: current SDK vs. minimal custom layer vs. LangChain (EVALUATION ONLY)

- Status: Evaluation only — no code, no new dependency, LangChain not
  installed to produce this document
- Owner: Person 6 (`work/person-6`)
- Classification: FUTURE FEATURE (per `docs/improvements/qa-agent-improvement-backlog.md`
  §I15 — "Requires future Spec: YES", "Requires future Plan/ADR: YES",
  "Recommendation: REVISIT AFTER T131", "LangChain is explicitly out of
  scope")
- Depends on: `docs/proposals/I12-evidence-provenance.md` (Person 5) — Rule
  I12-1 (Deterministic Precedence) is a hard constraint on every option
  evaluated here, not a suggestion (see §2).
- Constitution principles engaged: VI (determinism — LLM never does what
  deterministic logic can), IX (never fabricate, hypotheses stay
  hypotheses), X (no needless abstraction), XII (incremental evolution — no
  premature multi-agent/RAG/frameworks), XIV (spec-driven, no scope creep)

## 0. Scope and non-goals

This document (a) defines concrete future semantic QA cases the agent could
plausibly grow into, (b) compares three implementation options for producing
those cases' outputs, and (c) states a recommendation. **It does not
implement anything.** No `qa_agent.semantic` package, no new `LLMBackend`
method, no prompt template, no new dependency — including LangChain, which is
not installed anywhere in this repository or environment to produce this
evaluation. Every architectural claim about LangChain below is reasoned from
its publicly known package structure and stated as such, never presented as
a number measured in this repo (IX).

## 1. Concrete future semantic QA cases

These are the candidate cases this document evaluates options against. None
exists today; each is a plausible extension of the agent's current
tool-grounded reasoning loop (`agent/reasoning.py`'s `Intencion`/`Plan`/
`Observacion`/`EstadoDelAgente`), described in terms of its deterministic
input (what real evidence backs it) and its necessarily-semantic output
(what only an LLM can propose).

| # | Case | Deterministic input (from existing tools) | Semantic output (LLM-proposed) |
|---|---|---|---|
| 1 | Requirement → code candidate | `search`/`locate`/`leer_archivo` results scoped to the project | Ranked list of code files/symbols hypothesized to implement a given requirement text, with rationale |
| 2 | Requirement → test candidate | Same, plus existing test file contents (`leer_archivo` on `tests/`) | Which existing test(s) plausibly verify a requirement, and/or new test-case proposals (builds on, but is broader than, the existing `generate_test_cases` tool — see §1.1) |
| 3 | Edge-case suggestions | Code + existing test contents for a target file/module | Proposed untested edge cases (boundary values, error paths, concurrent/ordering cases) not present in the observed test suite |
| 4 | Failure correlation | `run_tests`/`analyze_test_results` structured output (which tests failed) + `search`/`leer_archivo` on recently-touched files | Hypothesis about which code file(s)/change(s) plausibly correlate with the observed failures |
| 5 | Root-cause hypothesis | Same as #4, plus the failing test's assertion/traceback text | A `posible_causa`-shaped explanation (the same field name I10 §5.6 already reserves a slot for) of *why* the failure likely occurs |

### 1.1 Relationship to the existing `generate_test_cases` tool

`generate_test_cases` already exists and already calls the LLM
(`src/qa_agent/tools/*` — its two-argument contract is immutable per T128).
Case #2 above is **not** a proposal to change that tool's contract; it is a
broader semantic capability (matching *existing* tests to a requirement, not
only generating new ones) that could live alongside it. Any future
implementation of case #2 must not touch `generate_test_cases`'s
two-argument signature.

### 1.2 The one rule every case above must obey

Per `docs/proposals/I12-evidence-provenance.md` §3.4, Rule I12-1
(**Deterministic Precedence**): **every output of cases #1–#5 is
`origin: HYPOTHESIS`, permanently.** There is no promotion path from
HYPOTHESIS to DETERMINISTIC/VERIFIED for any of these five cases — not by
confidence score, not by repeated agreement across replicates, not by a
human "looks right" skim. A hypothesis about which file implements a
requirement stays a hypothesis even if a human later confirms it manually;
the *human's confirmation* would be what creates new deterministic evidence
(e.g. by then reading the file), not the original LLM claim being upgraded.
None of these five outputs may ever:

- control whether a sensitive tool executes (T126's authorization gate is
  untouched by any of this — a HYPOTHESIS is never itself a trigger for
  `run_tests`/`analyze_coverage` without going through the exact same
  authorization path any other plan step already goes through),
- silently become part of `EstadoDelAgente`'s "real evidence" used by
  `_tiene_evidencia_real` or any completion/grounding check,
  or
- be reported by a future I10 evaluation run as `completion_score`/
  `grounding_score` input (I10 §4 already scopes those to deterministic
  scorers only; semantic quality is explicitly I10's `semantic_evaluation`
  reserved slot, which this document's judge-based scoring — §3 below —
  would fill, additively, never overwriting the deterministic report).

Any future implementation of options A/B/C must render this labeling
mechanically obvious in the output shape (e.g. a required, closed-enum
`origin` field per Provenance-adjacent shape, not a free-text disclaimer
sentence the LLM could omit or a UI convention a caller could forget to
apply) — the same "closed enum, not a comment" discipline I12 §3.4 already
commits to.

## 2. Evaluation methodology

For each case in §1, correctness has two layers, mirroring I10's own
deterministic-vs-LLM-variable split (`docs/proposals/I10-evaluation-harness.md`
§4/§4.1):

1. **Grounding/existence** (mechanically checkable, deterministic): does the
   hypothesis reference a file/symbol/test that actually exists in the
   project? This is checkable today by the exact same mechanism I10 already
   defines for `grounding_score` — no new scorer type needed.
2. **Quality/usefulness** (judgment call, requires an LLM judge or a human
   rater): is the *right* file identified, is the edge case actually
   valuable, is the root-cause hypothesis the most plausible one among
   several evidence-consistent explanations? This is exactly the
   `semantic_rubric`/`semantic_evaluation` slot I10 reserves and explicitly
   defers to I15 (§4.1 of that document). This document does not fully
   design that judge harness (that is a further, still-future increment);
   it fixes only which of options A/B/C is best positioned to produce
   *inputs* that harness can score.

The comparison below (§4) is against six criteria named in the task:
code/dependency weight, token usage, latency, structured-output reliability,
testability, maintainability, and one additional criterion the task also
names: measurable value.

## 3. The three options

### Option A — Current/direct SDK structured output (existing `LLMBackend` interface)

The agent already talks to an LLM exclusively through `LLMBackend`
(`src/qa_agent/llm/backend.py`), an `ABC` with `interpretar`,
`seleccionar_herramienta`, `generar_respuesta`, `planificar`, `razonar`,
`evaluar`, `responder` — each a plain method returning a `dict`/dataclass,
implemented today by `FakeLLM` (tests) and an OpenAI-compatible backend
(`openai_compatible_backend.py`, using the `openai` package already a
dependency). Option A means: add one more method to this same interface
(e.g. `hipotetizar(self, caso: str, evidencia: list[Observacion]) ->
dict[str, Any]`), implemented the same way `responder`/`planificar` already
are — a single prompt constructed from real observations, a JSON-mode or
schema-constrained call to the provider, `pydantic`-validated parsing of the
response into a typed hypothesis object carrying `origin: HYPOTHESIS`
unconditionally (not settable by the LLM's output — the caller sets it,
because per Rule I12-1 the value is a property of *how the evidence was
produced*, never something the LLM gets to assert about itself).

- **Code/dependency weight**: zero new dependency (`openai` and `pydantic`
  are already direct dependencies, see `pyproject.toml`). New code is one
  interface method + one implementation per backend + one dataclass — on the
  order of the existing `responder`/`planificar` methods' size (tens of
  lines each in `openai_compatible_backend.py`, based on the sibling methods
  already there).
- **Token usage**: one LLM call per case invocation, same shape as
  `responder`/`razonar` today — no additional round-trips, no
  agent-orchestrating-agent overhead. Prompt size is bounded by exactly the
  observations passed in (same bounding discipline I12 §3.3's excerpt cap
  already establishes for evidence quoting).
- **Latency**: one network round-trip per case, same order as any existing
  `atender` step today. No framework-level indirection between the call site
  and the HTTP request.
- **Structured-output reliability**: depends on the provider's JSON-mode/
  function-calling support (already relied on implicitly by
  `planificar`/`razonar`'s existing structured returns) plus explicit
  `pydantic` validation with a documented retry-once-on-malformed-JSON
  policy — the same pattern the codebase would need regardless of which
  option is chosen, since even LangChain's output parsers ultimately reduce
  to "ask the provider for JSON, validate, retry on failure."
- **Testability**: identical to every other `LLMBackend` method today —
  `FakeLLM` returns a fixed, hand-authored dict/dataclass, so every semantic
  case gets deterministic, LLM-free unit tests exactly like
  `test_reasoning.py`/`test_recomendaciones.py` already do for `responder`/
  `planificar`. No new test infrastructure needed.
- **Maintainability**: one more method on an interface the team already
  owns and already understands fully; no third-party abstraction to track
  version compatibility against.
- **Measurable value**: highest ease of instrumenting — because the call
  site is fully owned code, wiring in I10's trace/token/latency capture
  (§5.3 of that document) is a matter of wrapping one more already-existing
  call-boundary pattern, not learning a framework's own tracing/callback
  system.

### Option B — Minimal custom semantic layer

A small, purpose-built module (e.g. `qa_agent/semantic/`) sitting *on top
of* `LLMBackend` rather than extending its `ABC`: prompt templates per case
(#1–#5), a shared "call provider, parse JSON, validate against a
per-case `pydantic` model, retry once on failure, wrap in a `HYPOTHESIS`-
labeled envelope" helper, and per-case public functions
(`hipotetizar_requerimiento_a_codigo(...)`, etc.) that call the *existing*
`LLMBackend` instance passed in — no new abstract methods on the interface
itself, just a thin orchestration layer above it.

- **Code/dependency weight**: zero new dependency, same as A. Slightly more
  code than A (a dedicated module, shared retry/parse helper, five
  per-case functions rather than one interface method with a `caso`
  discriminator) — a genuine but modest increase, proportional to how many
  distinct prompt shapes the five cases actually need in practice (some may
  share a prompt template with a different evidence-selection step, in
  which case the marginal code over Option A shrinks further).
- **Token usage / latency**: identical to A — same one-call-per-case shape,
  the extra layer is Python-side orchestration, not additional round-trips.
- **Structured-output reliability**: same mechanism as A (JSON mode +
  `pydantic` + retry-once), but centralized in one helper instead of
  duplicated per backend implementation — a real maintainability edge over
  A if the number of cases grows past ~5, since each new case is "write a
  prompt + a pydantic model," not "implement a new abstract method on every
  `LLMBackend` subclass."
- **Testability**: same as A (swap in `FakeLLM`), plus the shared
  parse/retry helper becomes independently unit-testable in isolation from
  any specific case (a advantage A does not have, since A's parsing logic
  would be duplicated inside each backend implementation of the new
  interface method unless similarly factored out — meaning a careful
  Option-A implementation converges toward Option B's shape for the
  parsing helper anyway).
- **Maintainability**: better isolation of "semantic hypothesis production"
  as a named concern separate from "core agent orchestration," which makes
  Rule I12-1 easier to audit (one file/module is the entire surface where
  `origin: HYPOTHESIS` outputs are constructed, rather than that logic being
  spread across every `LLMBackend` implementation).
- **Measurable value**: same instrumentation ease as A, with the added
  benefit that a single module boundary is the natural place to plug in
  I10's `semantic_evaluation` judge harness later (§2), without touching
  `LLMBackend` itself.

### Option C — LangChain

LangChain would be added as a dependency (`langchain-core` plus a
provider-integration package, e.g. `langchain-openai`, since the project
already talks to OpenAI-compatible endpoints) to get: prompt template
objects, output parsers (including structured/Pydantic output parsers),
retry/fallback wrappers, and optionally its "chain"/"runnable" composition
API for wiring a multi-step semantic pipeline (e.g. retrieve evidence → build
prompt → call model → parse → validate) as a declared graph of Runnables
instead of straight-line Python calls.

**Explicitly not installed to produce this evaluation** — nothing below is a
number measured against this repository; it is reasoned from LangChain's
publicly documented architecture (a core package plus a large ecosystem of
optional provider/integration packages, itself the basis of the well-known
public discussion around its historically heavy and fast-moving dependency
surface) and stated as such per IX.

- **Code/dependency weight**: strictly worse than A/B by construction — it
  is the *only* option of the three that adds any dependency at all, which
  this program's constraint set (no new dependency, no production framework)
  already forecloses regardless of the rest of this comparison. Even judged
  on its own merits: `langchain-core` alone pulls in its own transitive
  dependency set (structured output/schema handling, retry utilities,
  tracing hooks), and a provider-integration package adds another layer on
  top of the `openai` SDK the project already depends on directly — net
  effect is two ways to talk to the same provider API existing in the
  dependency tree simultaneously (the project's own `openai` usage plus
  LangChain's wrapper around it), which is dependency weight added without
  a corresponding capability the project doesn't already have via A/B.
- **Token usage / latency**: no inherent token/latency advantage over A/B
  for the single-call, non-agentic cases in §1 (#1–#5 are each "gather
  evidence deterministically, then make one structured-output call" — none
  of them need LangChain's own multi-step agent/chain execution to be
  useful). Using a chain/runnable abstraction for a single LLM call adds
  Python-level indirection (multiple object constructions, a `.invoke()`
  dispatch through the Runnable protocol) without a compensating benefit at
  this call volume.
- **Structured-output reliability**: LangChain's structured-output parsers
  ultimately do the same thing Option A/B's `pydantic`-validate-and-retry
  approach does (ask for JSON, validate against a schema, retry on
  failure) — no meaningfully better reliability, since reliability here is
  bounded by the provider's own JSON-mode/function-calling adherence, not by
  which Python library wraps the call.
- **Testability**: worse than A/B — testing LangChain-based code typically
  means either mocking LangChain's own abstractions (Runnables, output
  parsers) in addition to the provider call, or running against LangChain's
  fake/test LLM implementations, which is one more framework surface the
  project's existing `FakeLLM`-based test discipline (already proven across
  446+ tests) would have to learn to work with or around, for no
  demonstrated gain over swapping in `FakeLLM` directly as A/B already do.
- **Maintainability**: worse — the team now tracks LangChain's own release
  cadence/breaking-change history (publicly known to be significant across
  its major versions) in addition to the provider SDK's, for a feature set
  (chains, agents, memory, retrievers) the five cases in §1 do not need
  (none of them require retrieval-augmented generation, multi-agent
  coordination, or persistent chain memory — all explicitly out of scope
  per Constitution XII and this program's charter).
- **Measurable value**: no case in §1 needs anything LangChain uniquely
  provides. Its main selling points (chain composition, agent frameworks,
  vector-store/retriever integrations, memory) are either irrelevant to
  five single-call structured-output tasks or actively out of scope for
  this project (XII — no premature RAG/multi-agent adoption; there is no
  multi-agent orchestration need here, and no retrieval-over-a-vector-store
  need — the agent's "retrieval" is already deterministic tool calls against
  the real filesystem, which LangChain does not improve on).

## 4. Comparison table

| Criterion | A — Direct SDK | B — Minimal custom layer | C — LangChain |
|---|---|---|---|
| Code/dependency weight | Lowest (0 new deps, minimal new code) | Low (0 new deps, one small module) | Highest (new dependency — excluded by program constraints regardless of merit) |
| Token usage | Baseline, 1 call/case | Same as A | No advantage over A/B |
| Latency | Baseline, 1 round-trip/case | Same as A | No advantage; extra indirection |
| Structured-output reliability | JSON mode + pydantic + retry (proven pattern already in use) | Same mechanism, centralized | Same underlying mechanism, extra framework layer |
| Testability | Reuses proven `FakeLLM` pattern | Same, plus isolated parse/retry helper | New framework mocking surface required |
| Maintainability | Team owns 100% of the surface | Team owns 100%, better separation of concerns | Tracks LangChain's own breaking-change history |
| Measurable value for §1's cases | Full — nothing in §1 needs more | Full — nothing in §1 needs more | No case needs LangChain-unique capability |

## 5. Recommendation

**Option A (current/direct SDK structured output via the existing
`LLMBackend` interface) for the first implementation**, with **Option B as
the natural refactor once a third or fourth case is added** and the shared
prompt/parse/retry logic starts genuinely duplicating across per-case
implementations — not before, since introducing the extra module boundary
speculatively, before duplication is observed, would itself be a small
instance of the premature-abstraction pattern Constitution X warns against.
**Option C (LangChain) is not recommended at this or any near-term stage**:
every criterion in §4 either favors A/B outright or shows no advantage for
C, none of the five cases in §1 need capabilities unique to LangChain
(multi-agent orchestration, RAG, persistent chain memory), and the program's
own constraints (XII incremental evolution, no premature multi-agent/RAG/
frameworks; this wave's explicit "no production framework" instruction) rule
it out independently of the comparison's outcome. This matches, and does not
contradict, the backlog's own I15 classification ("LangChain is explicitly
out of scope" — `docs/improvements/qa-agent-improvement-backlog.md` §I15).

This recommendation is conditioned on Rule I12-1 (§1.2) being enforced
exactly as designed in any future implementation: no option evaluated here
changes that requirement, and no option is preferred over another on
grounds that it makes enforcing that rule easier or harder — all three are
equally capable of tagging output `HYPOTHESIS`; the recommendation rests on
weight, reliability, and maintainability, not on safety, since none of the
three options offers a safety advantage the others lack.

## 6. Explicit non-goals (XIV)

- Does not implement any of the five cases in §1.
- Does not design the I15 judge-harness that would score semantic quality
  (§2) — that is further future work, referenced but not specified here.
- Does not modify `LLMBackend`, `Observacion`, or any existing contract.
- Does not install, import, or otherwise exercise LangChain anywhere in this
  repository or environment.
- No new FR/SC/US introduced. Per the backlog, this item is
  "REVISIT AFTER T131" — this document is preparatory evaluation for that
  future revisit, not the revisit's approval.
