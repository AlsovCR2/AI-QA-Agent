# Person 6 — Result (I14, I15, I16)

- Branch: `work/person-6`
- Base commit: `14fba46` (`abraham-full-tasks-branch`, Wave 1 integration —
  Persons 1–5's work already present)
- Scope: `docs/improvements/qa-agent-improvement-backlog.md` items I14, I15,
  I16; `docs/tareas-divididas.md` Person 6 assignment (final wave).
- Zone owned: `docs/proposals/I14-cli-capabilities.md`,
  `docs/proposals/I15-semantic-qa-evaluation.md`,
  `docs/proposals/I16-orchestration-evaluation.md` (all new).

## Items

| Item | Description | Classification | Status |
|---|---|---|---|
| I14 | Future CLI capabilities (`--json`/`--no-color`, execution controls, `qa-agent eval`) | FUTURE FEATURE | Design completed |
| I15 | Semantic QA evaluation (current SDK vs. custom layer vs. LangChain) | FUTURE FEATURE | Evaluation completed |
| I16 | LangGraph/LlamaIndex orchestration evaluation | NOT RECOMMENDED (current classification) | Evaluation completed |

## Status

**DONE.** All three items are design/evaluation-only, exactly as scoped.
No code was changed under `src/` or `tests/`. No dependency was added
anywhere. `python -m pytest -q` is unchanged at 500 passed.

## Design completed (I14, I15)

### I14 — `docs/proposals/I14-cli-capabilities.md`

Split into three independent parts, as required:

- **Part A — machine-readable output** (`--json`, `--no-color`): output
  schema for `--json` mirroring `RespuestaDelAgente`, redaction applied
  before serialization (T125 boundary unchanged), `--mostrar-historial`'s
  default-hidden behavior preserved under `--json` (`acciones: null` unless
  the flag is also set). Purely additive, backward-compatible with the
  current v1 CLI contract.
- **Part B — execution controls** (`--max-steps`, `--model`, `--dry-run`,
  `--trace-file`): each flag's validation, error behavior (shared exit-code
  convention: `0`/`2`), and interaction with `--demo`/`--pregunta`/REPL
  spelled out. `--dry-run` is the most safety-relevant flag designed here —
  it is specified to never call `_pedir_autorizacion` and never pass
  `autorizacion=True` under any direct or indirect path while active,
  strictly preserving T126 rather than merely not-regressing it. Also
  additive/backward-compatible.
- **Part C — `qa-agent eval`**: built directly on Person 2's I10
  `run_evaluation`/`compare_runs` signatures and `qa-agent eval
  run|report|compare` CLI shape — no competing interface invented. Explicitly
  states that adding `eval` is **not** backward-compatible with the current
  contract's own sentence ("no subcommands registered") and must be treated
  as a v2 CLI contract decision by whatever future Spec approves it, with an
  explicit note that this does not reopen the door to `qa-agent chat`
  (still deferred to US-12).
- A summary backward-compatibility table (Parts A/B: yes; Part C: no, needs
  an explicit v2 decision) closes the document.

### I15 — `docs/proposals/I15-semantic-qa-evaluation.md`

- Defined five concrete future semantic QA cases: requirement→code
  candidate, requirement→test candidate, edge-case suggestions, failure
  correlation, root-cause hypothesis — each with its deterministic input
  (existing tools: `search`/`locate`/`leer_archivo`/`run_tests`/
  `analyze_test_results`) and semantic output spelled out, plus an explicit
  note that case #2 does not touch `generate_test_cases`'s immutable
  two-argument contract (T128).
- Anchored every case to Person 5's I12 Rule I12-1 (Deterministic
  Precedence): every output is `origin: HYPOTHESIS` permanently, no
  promotion path, never controls authorization/evidence/completion scoring.
- Compared three options — (A) extend the existing `LLMBackend` ABC with one
  more structured-output method, (B) a minimal custom `qa_agent/semantic/`
  module on top of `LLMBackend`, (C) LangChain — on code/dependency weight,
  token usage, latency, structured-output reliability, testability,
  maintainability, and measurable value. LangChain was **not installed**;
  every claim about it is reasoned from its known architecture and
  explicitly flagged as such, never presented as a measured number.
- **Recommendation: Option A now, Option B as the natural refactor once a
  third/fourth case starts duplicating shared parsing/retry logic — Option C
  rejected outright**, consistent with the backlog's own "LangChain is
  explicitly out of scope" / "REVISIT AFTER T131" classification.

## Evaluation completed (I16)

`docs/proposals/I16-orchestration-evaluation.md`:

- Read Person 1's ADR-001 and result doc plus `agent/loop.py` and all five
  extracted modules directly (`wc -l`, `grep -n "^    def "`) to ground the
  evaluation in real, measured evidence rather than a generic framework
  comparison:
  - `loop.py`: 1,947 → **1,358 lines** (verified directly). Five extractions
    (778 lines total: `intent_policy.py` 168, `layer_policy.py` 142,
    `runner_detection.py` 55, `grounding.py` 83, `plan_enrichment.py` 330)
    were LOW/MEDIUM risk, pure/`self`-free logic, safely moved with zero
    regression (full suite 354→371 passed across the series).
  - The **only** thing ADR-001 declined to extract — the T125/T126
    authorization/execution boundary and its filesystem-rail dependencies
    (~900 of the remaining 1,358 lines) — was declined **because of
    security-verification cost** (needing a dedicated parity-proving
    regression suite before moving code), not because of graph/branching
    complexity.
- Compared current loop vs. LangGraph vs. LlamaIndex Workflows on: measured
  orchestration pain (as above), state/branching requirements (flat,
  single-agent, `EstadoDelAgente`, no parallel/sub-agent branching today),
  resumability need (**none — T127 removed `.qa_sessions` persistence,
  US-12 remains deferred**, so the frameworks' core differentiator matches
  no present requirement), LOC/complexity, testing, dependencies, migration
  risk, latency/cost. Neither framework was installed; all claims about them
  are reasoned from their known architecture and flagged as such (IX).
- Central finding: migrating to either framework would not reduce the one
  real measured pain point (security-boundary verification cost) — it would
  add a rewrite of that exact boundary into an unfamiliar execution model on
  top of the same verification burden, at the highest-risk part of the
  codebase.
- Section 5 states explicit, concrete conditions that would change this
  recommendation (US-12 un-deferred, real multi-agent/parallel need
  emerging, a future measurement showing branching complexity — not
  verification complexity — is the dominant cost) — none currently true.

## Files changed

New docs only:

- `docs/proposals/I14-cli-capabilities.md`
- `docs/proposals/I15-semantic-qa-evaluation.md`
- `docs/proposals/I16-orchestration-evaluation.md`
- `docs/improvements/person-6-result.md` (this file)

No file under `src/`, `tests/`, `specs/`, or any existing doc was modified.
`git status --porcelain` shows only the four new files above as untracked
additions; no existing tracked file has a diff.

## Dependencies

**NONE ADDED**, for all three items. `git diff --stat pyproject.toml`
against the base commit is empty (zero lines changed). No `import langchain`,
`import langgraph`, `import llama_index`, or any related package appears
anywhere in this branch's changes — neither framework was installed at any
point during this work; every claim about them in I15/I16 is explicitly
reasoned/architectural, not measured, and labeled as such (Constitution IX).

## Remaining SDD gate

- I14: backlog classification "Requires future Spec: YES, Requires future
  Plan/ADR: YES" — unchanged; this document is explicitly preparatory input
  to that future Spec, not a substitute for it. In particular, Part C
  (`qa-agent eval`) additionally requires the future Spec to make an
  explicit CLI contract version decision (v1 → v2) before any
  implementation, since it is the first subcommand the contract would ever
  register.
- I15: backlog classification "Requires future Spec: YES, Requires future
  Plan/ADR: YES," "Recommendation: REVISIT AFTER T131" — this evaluation is
  that revisit's input; actual implementation of Option A/B still requires
  its own future Spec/Plan, and Rule I12-1 must be a hard constraint on
  that future Plan, not a suggestion.
- I16: backlog classification "NOT RECOMMENDED," "Recommendation: REVISIT
  AFTER T131" — this evaluation performs that revisit on independently
  reasoned grounds and reaches the same conclusion (KEEP CURRENT LOOP,
  see below); it does not authorize migration, and per its own §5, only a
  future, separately-approved product change (US-12 un-deferred, or a
  measured branching-complexity pain point) would warrant a further
  re-evaluation.
- None of I14/I15/I16 introduces a new FR/SC/US (Constitution XIV). No
  public contract (`agent-interface-contract.md`, `llm-backend-contract.md`,
  `tool-contracts.md`) was changed by this work.

## Risks

- **I14 Part C's v2 contract decision is a real, non-trivial future
  commitment** — this document flags it clearly, but whoever writes the
  future Spec must not fold it in as an incidental detail; it changes the
  CLI's fundamental argument-parsing shape (first-ever subcommand) and
  needs its own explicit sign-off, separate from Parts A/B's genuinely
  backward-compatible additions.
- **I15's Option A/B recommendation is conditioned on Rule I12-1 being
  implemented exactly as designed** in Person 5's I12 document — this
  evaluation does not re-derive or weaken that rule; any future
  implementation that lets an LLM hypothesis silently influence
  authorization, evidence, or completion status would violate both I12 and
  this document's own stated precondition for A/B being safe choices.
- **I16's recommendation is time-bound to current requirements, not
  permanent** — §5 of that document names the specific conditions
  (US-12 un-deferred, real multi-agent need, measured branching-complexity
  pain) that would warrant a future re-evaluation; this is stated explicitly
  so a future reader does not treat "KEEP CURRENT LOOP" as a closed question
  forever, only as the correct answer given today's requirements and
  today's evidence.
- **All three documents reason about LangChain/LangGraph/LlamaIndex without
  installing them** — every such claim is explicitly labeled as
  architectural reasoning, not a measurement, per the task's own
  instruction and Constitution IX. A future evaluator with a genuine need
  to install one of these frameworks (e.g. for a spike, in an isolated
  environment, with explicit approval) should treat that as new, stronger
  evidence than anything in this document, not as confirmation of it.

## Recommendation summary

- **I16 final recommendation: KEEP.** No migration to LangGraph or
  LlamaIndex Workflows. The current Python ReAct loop (`agent/loop.py` +
  Person 1's five extracted modules) remains the orchestration mechanism.
  Real, measured evidence (ADR-001) shows the loop's only genuine
  difficulty is a security-verification cost at the T125/T126 boundary,
  which neither framework reduces and which migration would likely worsen
  by adding a rewrite risk on top of the same verification burden. Neither
  framework's core differentiator (stateful branching, checkpointed
  resumability, multi-agent coordination) matches a currently present
  requirement — resumability is explicitly, recently, and deliberately
  absent (T127), not merely unbuilt.
- **I15 final choice: A** (extend the existing `LLMBackend` interface with
  one more structured-output method), with **B** (a minimal custom
  `qa_agent/semantic/` layer) as the documented next step once shared
  prompt/parse/retry logic starts duplicating across three-plus cases — not
  before. **C (LangChain) is rejected**: it is the only option that adds any
  dependency at all (excluded by this program's constraints independent of
  the rest of the comparison), and no case defined in §1 of the I15 document
  needs any capability unique to LangChain (chain composition, agent
  frameworks, retrieval/memory) — all explicitly out of scope per
  Constitution XII and this program's charter.
