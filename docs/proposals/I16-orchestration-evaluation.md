# I16 — Orchestration alternatives evaluation: current ReAct loop vs. LangGraph vs. LlamaIndex Workflows (EVALUATION ONLY)

- Status: Evaluation only — no code, no new dependency, neither LangGraph
  nor LlamaIndex installed to produce this document
- Owner: Person 6 (`work/person-6`)
- Classification: NOT RECOMMENDED at current maturity (per
  `docs/improvements/qa-agent-improvement-backlog.md` §I16 — unchanged by
  this evaluation; see §6)
- Inputs used as evidence: `docs/adr/ADR-001-loop-modularization.md` and
  `docs/improvements/person-1-result.md` (Person 1) — real, measured
  evidence about what was actually difficult/risky to extract from
  `agent/loop.py`, not a hypothesis about it; direct reading of
  `src/qa_agent/agent/loop.py` and the five modules Person 1 extracted
  (`intent_policy.py`, `layer_policy.py`, `runner_detection.py`,
  `grounding.py`, `plan_enrichment.py`)
- Constitution principles engaged: VI (determinism), X (no needless
  abstraction), XII (incremental evolution — no premature multi-agent/RAG/
  frameworks), XIV (spec-driven, no scope creep)

## 0. Scope and non-goals

This document compares the current orchestration mechanism against
LangGraph and LlamaIndex Workflows on exactly the axes the task specifies:
current measured orchestration pain, state/branching requirements,
resumability need, LOC/complexity, testing, dependencies, migration risk,
and latency/cost implications. **It does not implement, install, or import
either framework.** Every claim about LangGraph/LlamaIndex is reasoned from
their publicly known architecture, stated as such, never presented as a
number measured in this repository (IX). A valid, and here the actual, final
recommendation is **KEEP CURRENT LOOP** — this document does not recommend
migration for framework parity or because either framework is popular; it
recommends migration only if the evidence in §1–§2 showed a real, currently
felt pain that a framework would solve, and it does not.

## 1. What Person 1's ADR-001 actually found difficult or risky (real evidence)

This is the load-bearing section — the rest of this document's conclusion
follows from what is measured here, not from a general framework comparison
performed in the abstract.

### 1.1 The loop's history, in numbers

`agent/loop.py` started at **1,947 lines** mixing at least eight distinct
responsibilities (ADR-001 §"Problem"). Person 1 extracted five of them into
standalone modules across four commits, each proven safe by full-suite runs
(354 → 363 → 365 → 371 passed) plus, where available, existing regression
suites (121 tests across `test_profundidad_analisis.py`/
`test_profundidad_capa.py`/`test_intencion_pruebas.py`) that required
**zero changes** to stay green through each extraction:

| Extracted module | Lines | What it is | Risk (ADR-001's own classification) |
|---|---|---|---|
| `intent_policy.py` | 168 | Phrase/regex tables for intent detection | LOW |
| `layer_policy.py` | 142 | Layer/folder regex, connectors, real-filesystem resolution | LOW |
| `runner_detection.py` | 55 | Marker-file → test/coverage command lookup | LOW |
| `grounding.py` | 83 | SC-017/FR-019 honesty check on final response text | LOW |
| `plan_enrichment.py` | 330 | Deterministic plan-enrichment routines (explore-by-layer, locate+generate, exhaustive reads) | MEDIUM |

Verified directly (`wc -l`, this evaluation): `loop.py` is now **1,358
lines**. What Person 1's extractions have in common: every one of them is
**pure, `self`-free logic** (string matching, regex, marker-file lookup, a
text-scanning honesty check, or plan-object mutation taking explicit
parameters) with **no control-flow branching over agent state** — they are
called *from* the loop, they do not decide the loop's shape.

### 1.2 What Person 1 deliberately did NOT extract, and the stated reason

ADR-001's "What stays in `loop.py` and why" and Person 1's own result doc
are explicit and specific — not "we ran out of time," but a reasoned
risk-acceptance:

> "the authorization/execution boundary (`_ejecutar_siguiente_paso`,
> `_atender_react`, `_atender_una_pasada`, `_parametros_para`,
> `_resultado_de_pruebas`) and filesystem rail helpers... Deliberately **not
> extracted**... this is the T125/T126 security boundary: this is where
> parameters are validated against schema, the allowlist is consulted
> (FR-025), authorization is created/checked/denied
> (`GestorDeAutorizacion`), and the tool is actually invoked."

Concretely, per this evaluation's direct read of `loop.py` (`grep -n "^
def "`), the un-extracted cluster is:

- `atender` / `_atender_una_pasada` / `_atender_react` (lines 374, 417, 618)
  — the lifecycle entry points and the ReAct percieve→plan→act→observe→
  reflect cycle itself.
- `_ejecutar_siguiente_paso` (line 985, running to ~1279 — the single
  largest function in the file, ~295 lines) — parameter resolution, schema
  validation, allowlist check, authorization gate, actual tool invocation.
- Seven filesystem-"rail" helpers (`_resolver_archivo_real`,
  `_corregir_escritura`, `_buscar_archivo_por_nombre`,
  `_buscar_directorio_por_nombre`, `_resolver_directorio_real`,
  `_capas_reales`, `_encolar_explore_capas_reales`, lines 768–984) that
  resolve LLM-proposed paths against the real filesystem immediately before
  authorization/execution.

ADR-001's own words for why this cluster stays: extracting it "would need a
dedicated characterization-test pass on the exact T126 invariant
(pending/denied authorization ⇒ zero target subprocess calls) and the T130
classification semantics, written *before* any code moves," is "a larger,
security-focused effort that deserves its own ADR/session," and — per
Person 1's result doc — represents "~900 of the remaining 1,358 lines."

### 1.3 What this evidence actually shows about where the loop's complexity lives

Reading §1.1 and §1.2 together: **the loop's difficulty is concentrated in a
security-sensitive authorize→validate→execute boundary and its immediate
filesystem-correction dependencies, not in generic multi-step
branching/state-management complexity.** The parts that *were* safely,
independently, low-riskily extractable (intent detection, layer detection,
runner detection, grounding checks, plan enrichment — 590 lines, ~30% of the
original file) are exactly the parts that have nothing to do with
orchestration shape at all; they are deterministic policy/lookup functions
that happen to be called from inside the loop. The part that resisted
extraction did so **because of security review cost, not because of
graph/branching complexity** — nothing in ADR-001 says "we couldn't extract
this because the control flow was too tangled to represent outside a single
function"; it says "we couldn't extract this without a dedicated
parity-proving regression suite for an authorization invariant." That is a
*process/verification* cost, and it is identical regardless of which
orchestration mechanism sits around the boundary — LangGraph or LlamaIndex
would still need the exact same authorization-gate logic living somewhere,
and moving *where* it lives does not reduce the *verification burden* of
proving it is unchanged; if anything, moving it into a new framework's
execution model would make it strictly harder to write a parity-proving
regression suite, because the "before" and "after" would differ in more than
just code location.

## 2. State/branching requirements and resumability need

- **Current shape**: single-agent, single-conversation, in-process control
  flow. `EstadoDelAgente` (`agent/reasoning.py`) holds `intencion`, `plan`,
  `observaciones`, `pasos_ejecutados`, `pasos_max` (default 12, SC-016) — a
  flat, linear accumulation of observations across at most `pasos_max`
  steps, no branching into parallel sub-agents, no sub-graph delegation, no
  cross-agent handoff.
- **Branching that exists today**: `_seleccionar_herramienta`
  (deterministic-routing-then-LLM-fallback, per ADR-001's own description)
  and the plan-enrichment routines' conditional insertion of extra steps —
  both are ordinary Python `if`/dispatch logic over a flat state object, not
  a graph of named nodes/edges. Nothing in the current design has more than
  one path of execution alive at a time.
- **Resumability**: **there is none, and none is required.** Per the
  approved CLI contract (`specs/001-core-ai-qa-agent/contracts/agent-interface-contract.md`
  §"El punto de entrada aprobado no registra subcomandos"), persistent
  conversation, memory, and `.qa_sessions` belong to US-12, which
  **remains deferred**. T127 (part of the immutable remediation this whole
  program must not regress) specifically removed `.qa_sessions`
  persistence. A framework whose primary differentiator is checkpointed,
  resumable, potentially-long-running graph execution (LangGraph's
  documented core value proposition) is solving a problem — mid-run
  persistence and resumption — that this codebase has deliberately,
  recently, and explicitly ruled out at the remediation level, not merely
  "not yet built."

This is the second reason (alongside §1.3) the pain a graph framework exists
to solve does not match the pain actually present here: LangGraph and
LlamaIndex Workflows both exist chiefly to make **stateful, branching,
potentially long-running/resumable, potentially multi-agent** execution
tractable. The current agent is single-agent, bounded to `pasos_max=12`
steps, entirely in-process, and explicitly non-resumable by design. None of
the three defining problems those frameworks solve is present.

## 3. LOC/complexity, testing, dependencies, migration risk, latency/cost

All figures for LangGraph/LlamaIndex below are architectural reasoning
(publicly known package structure/execution model), not measurements taken
against this repository — stated per IX, consistent with the "not installed"
constraint.

| Axis | Current loop (measured) | LangGraph (reasoned) | LlamaIndex Workflows (reasoned) |
|---|---|---|---|
| LOC/complexity | 1,358 lines in `loop.py` + 778 lines across 5 extracted single-responsibility modules = 2,136 lines total for the whole orchestration+policy surface, each module independently readable without the framework's own execution model in your head | Would require re-expressing the loop as a graph of nodes/edges/conditional-edges plus a `StateGraph` schema — a new vocabulary layered over the same logic, not a reduction in the amount of domain logic (the authorization/schema-validation/allowlist checks in `_ejecutar_siguiente_paso` do not shrink by becoming a graph node) | Same shape of trade-off: Workflows' `@step`-decorated event-driven model replaces direct function calls with event classes and step methods — again a new vocabulary over the same domain logic |
| Testing | Every extracted module is directly unit-testable with plain function calls and `FakeLLM` (Constitution III); 500 tests pass today with zero framework-specific test infrastructure | Testing a `StateGraph` typically means either invoking the compiled graph end-to-end or reaching into its internal node functions — the latter re-derives what this codebase already has today (independently testable functions), the former is a coarser-grained test than the current suite's targeted unit tests | Testing event-driven `@step` workflows requires driving the framework's event bus/context, an additional testing surface beyond calling a Python function directly |
| Dependencies | Zero framework dependency for orchestration itself (uses stdlib control flow over dataclasses already in `reasoning.py`) | New dependency (`langgraph` + its own transitive deps), on top of the existing `openai`/`pydantic`/`typer`/`rich`/`pathspec`/`python-dotenv` set — explicitly excluded by this program's "no production framework" constraint, independent of the rest of this comparison | Same — new dependency (`llama-index-core` + workflow extras), same exclusion |
| Migration risk | N/A (nothing to migrate) | HIGH: the exact cluster ADR-001 identified as too risky to *move within the same file* (T125/T126 boundary, ~900 lines) would need to be *rewritten* into a different execution paradigm (graph nodes/edges with framework-managed state passing) — strictly more invasive than the in-language extraction ADR-001 already declined to attempt without a dedicated parity-proving regression suite of its own | Same order of risk — event-driven step rewrite of the same security-sensitive cluster |
| Latency/cost | Baseline: one in-process function-call chain per step, no framework dispatch overhead | Graph execution adds framework-level dispatch/state-serialization overhead per node transition — for a ≤12-step, single-agent loop this overhead is unlikely to be the dominant cost (LLM call latency dominates either way) but it is not zero, and buys nothing here since there is no parallel/branching execution to schedule | Same reasoning — event-bus dispatch overhead added for no corresponding scheduling benefit at this branching factor |

## 4. Why "current measured orchestration pain" does not point at a framework gap

Restating §1.3 as the central finding: the *only* documented, measured
difficulty in this codebase's orchestration layer is the cost of proving a
security invariant (T126: pending/denied authorization ⇒ zero target
subprocess calls) stays true across a refactor. That is a **verification
cost**, addressed by writing a dedicated characterization/regression suite
*before* moving code (ADR-001's own stated prerequisite for ever attempting
this extraction) — a cost every option pays identically, current-loop or
framework-based, because the invariant being verified does not change
depending on which orchestration mechanism hosts the code. Migrating to
LangGraph or LlamaIndex would not reduce this cost; it would add to it, by
requiring the same regression proof *plus* a rewrite of the boundary into an
unfamiliar execution model, at the exact moment the codebase can least
afford to introduce doubt about that boundary's correctness (Constitution
V/VI, T125/T126 as immutable remediation this whole program must not
regress).

No other pain point qualifies as "measured": the five successfully extracted
modules (§1.1) demonstrate the *opposite* of a framework gap — they show
that ordinary Python module boundaries were sufficient to cleanly separate
five distinct responsibilities from the loop, at LOW/MEDIUM risk, verified
by full-suite runs, with zero framework adoption required.

## 5. What would change this recommendation

Per the backlog's own I16 entry ("Re-evaluate only from measured
orchestration pain and a separately approved product change; do not migrate
for framework parity"), the conditions under which a future re-evaluation
could reach a different conclusion:

1. **US-12 (persistent, resumable sessions) is un-deferred and approved** —
   at that point, "does the orchestration layer need checkpointed
   resumability" stops being a hypothetical (§2) and becomes a real
   requirement a framework built for exactly that (LangGraph's checkpointing)
   could genuinely address better than hand-rolled persistence.
2. **The agent grows a second, materially different execution mode
   requiring real branching/parallelism** — e.g. multiple sub-agents working
   concurrently on independent sub-tasks with a need to merge results
   (not currently planned anywhere in this program's scope, and explicitly
   the kind of "premature multi-agent" adoption Constitution XII warns
   against absent a demonstrated need).
3. **A dedicated future measurement** (not present today) shows the current
   loop's *branching/state* complexity — as opposed to its
   *security-boundary verification* complexity, which §4 shows a framework
   does not help with — has become the dominant source of bugs or extension
   difficulty, e.g. via a concrete count of branching-logic-caused defects
   or a concrete extension that repeatedly proves hard to add safely under
   the current linear model.

None of these three conditions is currently true. This document does not
manufacture one of them to justify a recommendation the evidence does not
support.

## 6. Recommendation

**KEEP CURRENT LOOP.** This matches, and is not merely restating, the
backlog's own current classification (`NOT RECOMMENDED`,
"Recommendation: REVISIT AFTER T131" — T131 is part of the immutable
remediation baseline this branch already sits on top of, so this evaluation
*is* that revisit, and it reaches the same conclusion on independently
reasoned grounds):

- The only real, measured orchestration difficulty in this codebase (§1) is
  a security-verification cost at the T125/T126 boundary, which migration
  to either framework would not reduce and would likely increase (§4).
- Neither framework's core differentiator (stateful graph branching,
  checkpointed resumability, multi-agent coordination) matches a currently
  present requirement (§2) — resumability is explicitly, recently, and
  deliberately absent (T127), not merely unbuilt.
- Both frameworks would add a new dependency this program's constraints
  already exclude, for a LOC/complexity/testing profile that is neutral-to-
  worse than the current five-module extraction Person 1 already achieved
  with zero framework adoption (§3).
- Migration risk is concentrated exactly where the codebase can least
  afford to introduce doubt: the T125/T126 authorization boundary (§3, §4).

This is a genuine "keep" verdict reached by evaluating the framework
alternatives against real evidence, not a default assumed without
comparison — §1–§4 show the comparison was made, and every axis in §3 either
favors the current loop or is neutral; none favors migration.

## 7. Explicit non-goals (XIV)

- Does not implement, install, or import LangGraph or LlamaIndex anywhere in
  this repository or environment.
- Does not modify `agent/loop.py` or any of the five extracted modules.
- Does not revisit or weaken ADR-001's own stopping point for I01 — this
  document treats that ADR's reasoning as evidence, not as something to be
  second-guessed by a framework comparison.
- No new FR/SC/US introduced. Per the backlog, this item's classification
  ("NOT RECOMMENDED," "REVISIT AFTER T131") is confirmed, not changed, by
  this evaluation.
