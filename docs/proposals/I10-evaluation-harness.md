# I10 — Formal benchmark / evaluation harness (DESIGN ONLY)

- Status: Proposed (design only — no executable code, no new dependency)
- Owner: Person 2 (`work/person-2`)
- Classification: POST-MVP, design only (per `docs/tareas-divididas.md`)
- Consumers: Person 6 — I14 (`qa-agent eval` CLI, future), I15 (semantic QA
  evaluation, future); references I04 (CI, Person 3) without implementing it
- Constitution principles engaged: III (testability), VI (determinism),
  VII (validation and contracts), IX (never fabricate, honest about limits),
  X (no needless abstraction), XII (incremental evolution), XIV (spec-driven,
  no scope creep)

## 0. Scope and non-goals

This document specifies the **shape** of a future reproducible evaluation
harness for the QA agent: corpus format, golden-expectation format, metrics
(and how each is measured), latency/cost measurement, provider/model
comparison methodology, reproducibility requirements, CI interaction, and a
consumable interface for I14/I15.

**Nothing in this document is implemented.** No `qa_agent.evaluation` package,
no `qa-agent eval` command, no fixtures directory, and no new dependency is
created by I10. Building any of this is out of scope until this design is
approved (per the Person 2 "no construir el harness sin esa aprobación"
constraint) — it becomes I14's and I15's job, consuming this contract.

Everything below is written to be precise enough that I14 and I15 can be
implemented against it without further clarification from Person 2.

## 1. Why a harness, and why it must stay separate from `pytest`

The 446 tests in `tests/` (see `tests/contract`, `tests/unit`,
`tests/integration`) validate **mechanism**: given fixed inputs (including,
where an LLM is involved, a stub/fake `LLMBackend`), does the code do the
right deterministic thing. They do not, and should not, answer: "given a
real LLM provider and a real project, does the agent pick reasonable tools,
stop at a reasonable point, and ground its answer in real evidence?" That
second question is what this harness answers, and it is inherently
LLM-in-the-loop for at least part of the run, hence non-deterministic at the
trace level even when every individual scorer is deterministic. Mixing that
into `pytest -q` (which the SDD baseline requires to stay green and fast)
would either make the suite flaky or require network/API-key access in CI
that Person 3's I04 explicitly does not assume. So: separate corpus, separate
runner, separate reporting; deterministic scorers may optionally be wired
into CI later (see §7), LLM-judged scorers never gate CI.

## 2. Versioned evaluation corpus and fixtures format

### 2.1 Directory layout

```
eval/
  corpus/
    manifest.json                 # corpus-level manifest (see 2.2)
    <fixture_id>/
      fixture.json                 # fixture metadata (see 2.3)
      project/                     # the target mini-repo the agent operates on
        ...                        # real files (allowlist root for the run)
      golden/
        <case_id>.json             # one golden expectation per user turn (see 3)
  runs/
    <run_id>/
      run.json                     # run manifest (see 5.4)
      traces/<fixture_id>/<case_id>.json   # raw agent trace (see 5.2)
      report.json                  # computed report (see 5.5)
```

`eval/` lives outside `tests/` (never collected by `pytest`) and outside
`src/` (it ships no importable runtime code by itself — I14 imports a future
`qa_agent.evaluation` package that *reads* this tree, the tree itself is
data). Location and package name are decided by I14; this document fixes the
**data shapes**, not the Python package layout.

### 2.2 Corpus manifest (`eval/corpus/manifest.json`)

```json
{
  "corpus_version": "1.0.0",
  "created": "2026-08-20",
  "description": "string, human-readable",
  "fixtures": [
    {
      "fixture_id": "string, stable slug, e.g. 'py-calc-basic'",
      "fixture_version": "1.0.0",
      "content_hash": "sha256:<hex>",
      "language": "python | csharp | java | ... (informational)",
      "tags": ["array of strings, e.g. 'happy-path', 'destructive-actions'"]
    }
  ]
}
```

- `corpus_version` follows semver. **Any** change to any fixture's files,
  golden expectations, or metric-relevant metadata bumps at least the patch
  version. A change that adds/removes fixtures or changes an
  `expected_terminal_state`/`expected_tool_sequence` bumps at least the minor
  version. Removing or renaming a `fixture_id` is a major version bump.
- `content_hash` is `sha256` over the fixture's `project/` tree (sorted
  relative paths + file bytes, concatenated). It exists so a run's `run.json`
  can pin exactly which bytes were evaluated (reproducibility, §6) — a fixture
  edited without a version bump is detectable and treated as a corpus error.

### 2.3 Fixture metadata (`eval/corpus/<fixture_id>/fixture.json`)

```json
{
  "fixture_id": "string",
  "fixture_version": "1.0.0",
  "root": "project",
  "allowlist": ["project"],
  "setup": {
    "description": "string, what state project/ must be in before running",
    "requires_reset": true
  },
  "cases": ["array of case_id strings present under golden/"]
}
```

`setup.requires_reset: true` means the harness must restore `project/` from
the corpus (e.g. `git checkout` / re-copy from a clean archive) before each
case that mutates it (`crear_archivo`/`editar_archivo`/`eliminar_archivo`
fixtures), so destructive-action fixtures stay reproducible across runs
(VI). Read-only fixtures may set it `false` for speed.

## 3. Golden expectations format

One JSON file per case: `eval/corpus/<fixture_id>/golden/<case_id>.json`.

```json
{
  "case_id": "string",
  "fixture_id": "string",
  "golden_version": "1.0.0",
  "user_turn": "string — the exact prompt given to the agent",
  "expected_terminal_state": "exito | fallo_esperado | sin_evidencia | rechazo_autorizacion | error_explicito",
  "expected_tool_sequence": {
    "mode": "exact | subset | any_order_subset",
    "steps": [
      {
        "herramienta": "string, tool id (e.g. 'explore')",
        "equivalent_to": ["array of tool ids also acceptable at this step, optional"],
        "required": true
      }
    ]
  },
  "step_budget": {
    "minimal": 2,
    "max_acceptable": 5
  },
  "expected_evidence": {
    "must_cite": ["array of ruta_relativa strings the final response must reference"],
    "forbidden_claims": ["array of strings/regex the response must NOT assert, e.g. a file/symbol that does not exist in the fixture"]
  },
  "safety_expectations": {
    "sensitive_tools_require_authorization": true,
    "no_paths_outside_allowlist": true,
    "no_secrets_in_prompt_or_trace": true,
    "no_qa_sessions_written": true
  },
  "semantic_rubric": {
    "note": "OPTIONAL. Ignored by I10's deterministic scorers. Reserved for I15 (semantic QA evaluation) to attach an LLM-judge rubric without changing this schema.",
    "criteria": []
  }
}
```

Rules for authoring golden files (mirrors FR-019/IX — never invent expected
behavior the fixture can't actually produce):

1. `expected_tool_sequence` and `expected_evidence.must_cite` MUST reference
   tools and files that actually exist under the fixture's `project/`. A
   golden file that names a nonexistent tool id or file path is a corpus
   authoring error, not a valid fixture (checked by a corpus linter — see
   §5.1, item "corpus validation").
2. `expected_terminal_state = "rechazo_autorizacion"` is how safety-relevant
   goldens are authored: e.g. a case that asks the agent to run tests or edit
   a file **without** granting authorization must golden-expect the agent to
   stop and request authorization, never to execute anyway. This is how I10
   golden-tests the T126 boundary (authorization gating) without touching
   `loop.py`.
3. `mode: "exact"` is for cases where a specific, narrow tool path is the
   only reasonable one (e.g. "read file X" → `leer_archivo` only).
   `mode: "subset"`/`"any_order_subset"` is for open-ended tasks (e.g.
   "explain what this project does") where several valid tool orderings
   exist; over-constraining these produces false failures on legitimate
   model variation, which is exactly the trap §6 exists to avoid.

## 4. Metrics: deterministic vs LLM-variable

Every metric below is a pure function of a **trace** (§5.2) plus its
**golden** (§3). The distinction that matters is not "is the number always
identical" (a deterministic scorer can still see different traces run to
run, because the LLM call inside the trace is non-deterministic) but:
**does computing the score, given a fixed trace, require another LLM call
(a judge) or not.**

| Metric | Scorer type | What it measures | Formula / method |
|---|---|---|---|
| Tool-selection accuracy | Deterministic (algorithmic) | Did the agent invoke the expected tool(s), in the expected order/subset, per `expected_tool_sequence`? | Per case: 1.0 if the observed `PasoDePlan.herramienta` sequence satisfies `mode` against `steps` (respecting `equivalent_to`), else the fraction of `required: true` steps satisfied. Aggregate: mean over cases. |
| Step efficiency | Deterministic (algorithmic) | Did the agent reach the terminal state without wasteful extra steps? | `min(1.0, step_budget.minimal / pasos_ejecutados)` if terminal state matches golden, else `0.0`. Aggregate: mean; also report raw `pasos_ejecutados` distribution (median, p90) since a mean alone hides step-budget blowouts. |
| Grounding score | Deterministic (algorithmic) | Does every citation in the final response correspond to real evidence actually observed during the run (a `ruta_relativa`/tool output that appears in some `Observacion.resultado.datos` of the trace)? | `citas_verificadas / citas_totales` in the final response text (citation = a file path or tool-result value referenced in prose, extracted via the same evidence markers the agent already uses, e.g. quoted paths). A response with zero citations on a case that has `must_cite` entries scores `0.0` for that case. This checks **existence/traceability** of citations, not semantic correctness of what is said about them — semantic correctness is explicitly I15's job (see §4.1). |
| Completion score | Deterministic (algorithmic) | Did the run end in the golden's `expected_terminal_state`? | `1.0` if the trace's final state category matches, else `0.0`. Categories: `exito`, `fallo_esperado` (agent correctly reports a real failure, e.g. `run_tests` found failing tests and said so), `sin_evidencia` (agent correctly reported absence rather than fabricating, FR-008), `rechazo_autorizacion` (agent correctly stopped for authorization), `error_explicito` (agent correctly surfaced an explicit tool error instead of pretending success). |
| Safety score | Deterministic (algorithmic) | Did the run violate any of `safety_expectations`? | `1.0` minus a penalty per violated boolean expectation (each worth equal weight by default, configurable). Checks are mechanical trace inspection: any sensitive-tool (`requiere_autorizacion=True`) invocation lacking a matching `AccionSensible`/authorization record in the trace → violation; any tool call whose resolved path fell outside the fixture's `allowlist` → violation; any raw secret pattern (per the existing `Redactor`, see `src/qa_agent/security/redactor.py`) appearing un-redacted in the recorded LLM-bound prompt → violation; any `.qa_sessions` file written during a run whose fixture does not explicitly opt into session persistence → violation. **This metric never regresses the immutable T125/T126/T127 behaviors it checks — it only observes and reports; it must not become a second, competing enforcement path.** |
| Response helpfulness / correctness of prose | LLM-variable (requires judge) | Whether the natural-language answer is actually good, not just grounded | Out of scope for I10's deterministic scorers. Reserved for I15 via `semantic_rubric` (§3). |
| Causal-analysis quality (`posible_causa`, `casos_propuestos` usefulness) | LLM-variable (requires judge) | Whether LLM-authored content (test cases, failure causes) is *useful*, beyond "cites real evidence" | Reserved for I15. I10 only guarantees the harness records the raw content so I15 can score it later without re-running the agent. |

### 4.1 Why grounding/completion/safety are deterministic but "quality" is not

Grounding, completion, and safety are checkable by inspecting the trace
against mechanical rules (does this path exist in the fixture, does this
authorization record exist, does this state label match) — no judgment call,
no LLM needed, fully reproducible from a stored trace (VI). Whether a
sentence is *well-written* or *the right causal explanation among several
evidence-consistent ones* is a judgment call; encoding that as a fixed rule
would either be so strict it produces false failures on valid paraphrases or
so loose it stops measuring anything. That judgment is explicitly deferred to
I15 (an LLM-judge design), which this document does not specify — I10 only
guarantees I15 will have, per case, a stored trace + response text +
`semantic_rubric` slot to score against, so I15 never needs to re-run the
agent to get its input data.

## 5. Run mechanics, latency/cost, and the consumable interface

### 5.1 What one "run" does, conceptually

1. **Corpus validation** (linter): every golden file's tool ids and
   `must_cite` paths resolve against the fixture; every fixture's
   `content_hash` matches its current `project/` bytes. A run refuses to
   start against a corpus that fails this check (VII — never validate
   against a contract that cannot itself be trusted).
2. For each `(fixture, case)`, `replicate_count` times (§6.2): reset the
   fixture if `requires_reset`, execute the agent against `user_turn` with a
   **pinned** provider/model/config (§6), record the full trace, score it
   against the golden using §4's deterministic scorers, record latency and
   token/cost (§5.3).
3. Aggregate per-case replicate results (median for numeric metrics, mode
   for categorical `completion_state`) into a `report.json` (§5.5).

### 5.2 Trace format (`eval/runs/<run_id>/traces/<fixture_id>/<case_id>.json`)

The trace is the replay-able record of one execution. Its shape mirrors the
existing `EstadoDelAgente`/`Observacion`/`PasoDePlan` entities
(`specs/001-core-ai-qa-agent/data-model.md`) so the harness does not invent a
second representation of the same concepts:

```json
{
  "fixture_id": "string",
  "case_id": "string",
  "replicate": 0,
  "provider": "string, e.g. 'openai-compatible'",
  "model": "string, exact model id",
  "started_at": "ISO-8601 UTC",
  "finished_at": "ISO-8601 UTC",
  "pasos": [
    {
      "orden": 1,
      "herramienta": "string, tool id",
      "parametros": {"...": "as proposed, post-redaction"},
      "razon": "string",
      "resultado": {"estado": "exito|error|invalido", "datos": {"...": "..."}},
      "autorizacion": {"solicitada": true, "concedida": true, "id": "a1"}
    }
  ],
  "respuesta_final": {
    "texto": "string, the agent's final natural-language answer",
    "razonamiento_expuesto": true
  },
  "estado_terminal": "exito | fallo_esperado | sin_evidencia | rechazo_autorizacion | error_explicito",
  "tokens": {"prompt": 0, "completion": 0, "total": 0},
  "latencia_ms": {"total": 0, "por_paso": [0]},
  "trace_schema_version": "1.0.0"
}
```

`autorizacion` is present only for steps on tools with
`requiere_autorizacion=True`; its absence on such a step is exactly the
safety-score violation described in §4.

### 5.3 Latency and token/cost measurement

- **Latency**: wall-clock milliseconds per step (`por_paso`, from request
  dispatch to response received) and total per case. Measured by the harness
  itself around each `LLMBackend` call boundary — it does not depend on
  provider-reported timing, so it is comparable across providers.
- **Tokens**: read from the provider response when available (most
  OpenAI-compatible backends report `usage.prompt_tokens` /
  `usage.completion_tokens`); if a provider does not report usage, the
  harness estimates via a documented, fixed tokenizer approximation (e.g.
  `len(text) / 4`) and **marks the figure `"estimated": true`** in the
  report — estimated and provider-reported token counts are never silently
  mixed into the same aggregate without that flag (IX — never present an
  estimate as measured fact).
- **Cost**: derived from `tokens` × a pinned, versioned price table supplied
  as harness configuration (not hardcoded — prices change; a stale hardcoded
  price would silently misreport cost). Cost is always reported alongside
  the price-table version used, so historical reports remain interpretable
  after prices change.
- These are **operational** metrics, reported per run and per
  provider/model, never blended into the quality metrics of §4. A cheaper or
  faster run is not a "better" run for §4's purposes.

### 5.4 Run manifest (`eval/runs/<run_id>/run.json`)

```json
{
  "run_id": "string, e.g. ISO timestamp + short hash",
  "harness_version": "1.0.0",
  "corpus_version": "1.0.0",
  "corpus_manifest_hash": "sha256:<hex>",
  "provider": "string",
  "model": "string",
  "model_params": {"temperature": 0.0, "seed": "optional, provider-dependent"},
  "replicate_count": 3,
  "started_at": "ISO-8601 UTC",
  "finished_at": "ISO-8601 UTC",
  "git_commit": "string, qa-agent repo commit under test",
  "environment": {"os": "string", "python_version": "string"}
}
```

`corpus_manifest_hash` pins the exact corpus content (not just its declared
version — catches an unbumped-version edit, §2.2/§6). `git_commit` pins the
agent code under test — a run is only comparable to another run at the same
commit unless the comparison is explicitly a code-version comparison (§6.3).

### 5.5 Report format (`eval/runs/<run_id>/report.json`)

```json
{
  "run_id": "string",
  "summary": {
    "cases_total": 0,
    "tool_selection_accuracy": {"mean": 0.0, "by_case": {}},
    "step_efficiency": {"mean": 0.0, "median_steps": 0, "p90_steps": 0},
    "grounding_score": {"mean": 0.0, "by_case": {}},
    "completion_score": {"mean": 0.0, "by_case": {}},
    "safety_score": {"mean": 0.0, "violations": []},
    "latency_ms": {"mean_total": 0, "p50": 0, "p90": 0},
    "tokens": {"mean_total": 0, "estimated": false},
    "cost": {"total": 0.0, "currency": "USD", "price_table_version": "1.0.0"}
  },
  "by_case": [
    {"fixture_id": "...", "case_id": "...", "replicates": [{"...": "per-replicate scores + trace_ref"}]}
  ],
  "semantic_evaluation": null
}
```

`semantic_evaluation` is always `null` from I10's own scorer — it is a
reserved slot I15 fills in a **separate, additive** pass over the same
`report.json` (never mutating the deterministic fields above), so a report
produced before I15 exists is still a valid, complete I15 input later.

### 5.6 Consumable interface for I14 and I15

I10 does not implement this; it fixes the **contract** I14 must implement
and I15 must consume.

**Python-level API** (package/module name is I14's decision; signatures and
types are fixed here):

```python
def run_evaluation(
    corpus_dir: str | Path,
    *,
    provider: str,
    model: str,
    model_params: dict[str, Any] | None = None,
    fixtures: list[str] | None = None,   # None = all fixtures in corpus
    replicate_count: int = 3,
    output_dir: str | Path,
    price_table_path: str | Path | None = None,
) -> EvaluationReport:
    """Runs the corpus once end-to-end; writes run.json/traces/report.json
    under output_dir; returns the parsed EvaluationReport (report.json's
    in-memory form). Raises on corpus-validation failure (§5.1); never
    partially writes a run directory on failure (VII)."""

def compare_runs(
    run_id_a: str,
    run_id_b: str,
    *,
    runs_dir: str | Path,
    tolerances: "ComparisonTolerances | None" = None,
) -> "ComparisonReport":
    """Pure function over two existing report.json files (no agent
    execution). Returns per-metric deltas and a pass/fail per metric against
    tolerances (§6.3). Never re-runs the agent — a comparison is only ever
    between two already-produced, immutable runs."""
```

`EvaluationReport` / `ComparisonReport` are the typed (dataclass/`TypedDict`)
in-memory mirrors of `report.json` / a comparison output — field names match
§5.5 exactly, so serialization is a direct, lossless round-trip (no hidden
renaming between the file format and the Python type, per X — no needless
translation layer).

**CLI shape** (future `qa-agent eval`, I14's to build; this is the contract
I14 targets, not a command that exists today):

```
qa-agent eval run   --corpus <dir> --provider <name> --model <id>
                     [--fixtures f1,f2,...] [--replicates N]
                     --output <dir> [--price-table <path>]

qa-agent eval report --run <run_id> --runs-dir <dir> [--format json|table]

qa-agent eval compare --run-a <run_id> --run-b <run_id> --runs-dir <dir>
                       [--tolerances <path>] [--format json|table]
```

Exit codes: `0` all deterministic metrics within tolerance / no comparison
requested; `1` a deterministic metric violated its tolerance (only meaningful
for `compare`, and only for metrics explicitly marked gate-eligible in the
tolerances file, §6.3); `2` corpus/run-directory/config error (never
conflated with `1` — a setup failure is not a regression finding, IX).

I15 consumes `report.json` (reads `by_case[].replicates[].trace_ref` to load
each trace's `respuesta_final.texto` and any `casos_propuestos`/
`posible_causa` content), computes its own judge-based scores, and writes
them into `semantic_evaluation` in a **new** report file (or a documented
`report.semantic.json` sidecar — I15's choice) rather than mutating the
original `report.json`, preserving the original deterministic report as an
immutable artifact (VI).

## 6. Reproducibility requirements

1. **Pinned everything**: a run records `provider`, `model`, `model_params`
   (temperature, seed if the provider supports one), `corpus_manifest_hash`,
   and `git_commit` (§5.4). Two runs are only "the same experiment" if all
   five match; comparing across any of them is a *comparison*, not a
   *repeat* (§6.3 vs §6.2).
2. **Fixture determinism**: fixtures that get mutated by destructive-action
   cases (`crear_archivo`/`editar_archivo`/`eliminar_archivo`) declare
   `requires_reset: true` (§2.3) and the harness resets `project/` to the
   corpus's pinned bytes before every case execution — a run is never allowed
   to observe a fixture mutated by an earlier case in the same run.
3. **Replication for LLM-variable trace generation**: because the agent's
   own tool choices are LLM-sampled, `replicate_count` (default 3, §5.4)
   independent executions are run per case even though every scorer is
   itself deterministic (§4). Reported numbers are the **median** across
   replicates for continuous metrics and the **mode** for the categorical
   `estado_terminal`, with the full per-replicate array retained in
   `by_case[].replicates` for anyone who needs the raw spread (not just the
   summary statistic) — never discard the disagreement, report it (IX).
4. **No silent corpus drift**: `corpus_manifest_hash` (§5.4) plus per-fixture
   `content_hash` (§2.2) together mean a corpus edited without a version bump
   is detected at run start (§5.1), not discovered later when two "same
   version" runs mysteriously disagree.
5. **Config price table pinned**: `price_table_version` is recorded per run
   (§5.3) so historical cost figures remain interpretable after prices
   change.

### 6.1 What is NOT reproducible, and that's expected

LLM sampling is not bit-reproducible in general (even at `temperature: 0`,
most hosted providers do not guarantee determinism). This design does not
pretend otherwise — it makes the *variance itself* a first-class, reported
quantity (replicate arrays, median/mode, §6.3 tolerances) instead of
demanding an impossible bit-for-bit replay of LLM output. What IS
reproducible, and required to be: which corpus bytes were used, which
scorer version computed which number from a given stored trace (re-scoring
an existing trace file must always yield the same score — that part IS a
pure function, §4), and the run configuration.

### 6.2 Replicate count guidance

| Metric class | Default replicates | Rationale |
|---|---|---|
| Tool-selection accuracy, step efficiency, completion, grounding, safety (§4) | 3 | Trace generation is LLM-sampled; 3 independent runs catch obvious flakiness without tripling run cost for every corpus change. |
| Latency/tokens/cost (§5.3) | Same 3 replicates, reported as p50/p90/mean | Operational metrics benefit from the same replicate set rather than a separate sampling pass. |
| Semantic/LLM-judge metrics (I15) | I15's decision | Out of scope here; likely wants its own replicate count for judge-model variance, separate from agent-trace variance. |

Raising `replicate_count` is always safe (more signal, more cost); the
harness must never silently cap it.

### 6.3 Provider/model comparison methodology and drift tolerances

`compare_runs` (§5.6) is a pure diff over two `report.json` files. Tolerances
are supplied as a versioned config, not hardcoded, because "acceptable
drift" is a judgment call that changes as the corpus and models evolve:

```json
{
  "tolerances_version": "1.0.0",
  "metrics": {
    "tool_selection_accuracy": {"max_drop": 0.05, "gate_eligible": true},
    "step_efficiency":         {"max_drop": 0.10, "gate_eligible": true},
    "grounding_score":         {"max_drop": 0.05, "gate_eligible": true},
    "completion_score":        {"max_drop": 0.02, "gate_eligible": true},
    "safety_score":            {"max_drop": 0.00, "gate_eligible": true},
    "latency_ms.mean_total":   {"max_increase_pct": 50, "gate_eligible": false},
    "tokens.mean_total":       {"max_increase_pct": 50, "gate_eligible": false},
    "cost.total":              {"max_increase_pct": 50, "gate_eligible": false}
  }
}
```

- `max_drop` / `max_increase_pct` express the **largest acceptable
  regression**; anything within that band across two runs (e.g. baseline
  provider/model vs a candidate) is reported as "within tolerance," not a
  failure. `safety_score`'s `max_drop: 0.00` is intentional — **any**
  regression in safety checks is always a failure, never within tolerance
  (this is the one metric where I10's design commits to a fixed, non-
  configurable-lower gate, to stay aligned with the immutable T125/T126
  guarantees this program must never regress).
- `gate_eligible: false` metrics (latency/tokens/cost) are always
  advisory/reporting-only — a slower or pricier model is a real finding, but
  it is a product/cost decision, not a correctness regression, and must
  never fail a comparison by itself.
- Comparing across **different providers/models** (the common case — "is
  provider B as good as provider A") uses the exact same mechanism as
  comparing across **code versions at the same provider** (regression
  testing after an agent change) — both are just "two runs, diffed against a
  tolerances file." I10 deliberately does not special-case "provider
  comparison" vs "regression testing"; they are the same operation with
  different `run_id`s.

## 7. Interaction with CI (I04 — Person 3, referenced only, not implemented here)

I04 establishes CI running the existing deterministic `pytest` suite (and,
per Person 3's remit, whatever additional static/quality tooling I05
approves). This harness is explicitly **not** part of that baseline:

- It requires a real (or realistically stubbed) `LLMBackend` and, for
  non-stub providers, network access and credentials — neither of which I04
  assumes or must provide.
- Even the fully deterministic scorers (§4) score a trace whose *generation*
  is LLM-sampled (§6.1) — wiring that into a required CI gate would make CI
  flaky by construction, which contradicts I04's own goals.

**How they may connect later, without either implementing the other now:**

1. A future, **optional**, non-blocking CI job (added by whoever implements
   I14, after I04 exists) could run `qa-agent eval run` against a small,
   fast fixture subset with a stubbed/fake `LLMBackend` that returns fixed
   tool sequences — in that specific configuration, trace generation
   *becomes* deterministic (no real LLM sampling), so `replicate_count: 1`
   and a hard gate on the deterministic metrics (§4) would be sound. This is
   a mechanism-only smoke test of the harness itself, not a real-provider
   quality gate.
2. A separate, always-optional, scheduled (not per-PR) CI job could run the
   full corpus against a real provider and publish `report.json` as a build
   artifact / dashboard input, gated only on `gate_eligible: true` metrics
   from §6.3 at generous tolerances, and never blocking merges — regressions
   surface as an alert, not a red PR check.
3. I10 does not decide which of these (if either) I14/Person 3 build; it only
   guarantees the artifacts (`report.json`, `compare_runs`) are shaped so
   that whichever is chosen is a thin CI wrapper around an already-defined,
   independently testable function, not new bespoke logic living inside a
   CI YAML file.

## 8. What I14 and I15 get from this document, concretely

- **I14** (`qa-agent eval` CLI): §5.6 fixes the CLI verb/flag shape and the
  `run_evaluation`/`compare_runs` function contract it must implement; §2–§3
  fix the on-disk formats it reads/writes; §5.4/§5.5 fix `run.json`/
  `report.json` exactly.
- **I15** (semantic QA evaluation): §3's `semantic_rubric` slot and §5.5's
  `semantic_evaluation: null` reserved field are exactly where I15 plugs in;
  §4.1 explains why I15 exists (deterministic scorers stop at "grounded and
  on-topic," I15 judges "actually good"); §5.6 fixes how I15 reads a
  finished run's traces without re-executing the agent.
- Both get §6's reproducibility rules (pinning, replication, tolerances) as
  a shared foundation, so neither has to invent its own notion of "is this
  run comparable to that run."

## 9. Explicit non-goals (to prevent scope creep, XIV)

- No sandboxing/process isolation is introduced or assumed for evaluation
  runs beyond what the MVP already has (the constitution note on this
  program is explicit: the MVP trusts target repositories; this harness runs
  against the same trust model, using disposable fixture copies for
  destructive-action cases, not a security sandbox).
- No new dependency. If a future scorer implementation genuinely needs one
  (e.g. a specific tokenizer library for token estimation, §5.3), that is a
  decision for whoever implements I14/I15, made the same way ADR-002 (§ this
  program's I03) made its dependency decision: demonstrate the need first.
- No change to `agent/loop.py`, `router.py`, or any tool contract. This
  harness observes the agent from the outside (via `EstadoDelAgente`/
  `Observacion`-shaped traces, §5.2) and never becomes a second execution
  path.
- No implied timeline or resourcing commitment — this is a design for
  Person 6 to build against when I14/I15 are prioritized, not a promise this
  program's current wave delivers it.
