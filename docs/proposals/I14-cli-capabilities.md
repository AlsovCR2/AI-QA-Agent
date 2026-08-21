# I14 — Future CLI capabilities (DESIGN ONLY)

- Status: Proposed (design only — no code change, no new dependency)
- Owner: Person 6 (`work/person-6`)
- Classification: FUTURE FEATURE (per `docs/improvements/qa-agent-improvement-backlog.md`
  §I14 — "Requires future Spec: YES", "Requires future Plan/ADR: YES")
- Depends on: Part C depends on `docs/proposals/I10-evaluation-harness.md`
  (Person 2) — uses Person 2's `run_evaluation`/`compare_runs` signatures and
  `qa-agent eval` CLI shape verbatim, does not invent a competing one.
- Constitution principles engaged: V (human-in-the-loop), VI (determinism),
  VII (validation/contracts), VIII (observability), IX (never fabricate),
  X (no needless abstraction), XII (incremental evolution), XIV (spec-driven,
  no scope creep — this document is a preparatory design for a future Spec,
  not the Spec itself, and authorizes no implementation)

## 0. Scope and non-goals

This document specifies, for three independent capability groups, the exact
flags/subcommands, their valid combinations, their error behavior, their
interaction with the five currently approved flags (`--ruta`, `--pregunta`,
`--demo`, `--mostrar-historial`, `--version`), and backward compatibility
against `specs/001-core-ai-qa-agent/contracts/agent-interface-contract.md`.

**Nothing in this document is implemented.** No flag is added to
`src/qa_agent/cli/main.py`. No new FR/SC/US is introduced (XIV). Building any
of A/B/C requires its own future Spec + Plan/ADR per the backlog's own
classification of I14 — this document is written precisely enough that that
future work can start from it without re-deriving the design, not to
pre-authorize it.

## 1. The current approved contract, in one sentence

`agent-interface-contract.md` §"Contrato de CLI" fixes a **single command**
(`qa-agent [--ruta DIR] [--pregunta TEXT] [--demo] [--mostrar-historial]
[--version]`) with an explicit, deliberate statement: *"El punto de entrada
aprobado no registra subcomandos. En particular, `qa-agent chat` no forma
parte del MVP."* That sentence is load-bearing for this whole document — see
§4.

## Part A — Machine-readable output (`--json`, `--no-color`)

### A.1 `--json`

- **Shape**: boolean flag, default `False`. When set, `main()` (and the
  future `_chat_diferido` successor, if ever un-deferred — out of scope)
  skips all `rich` `Panel`/`Table` rendering and instead prints one JSON
  document to stdout.
- **Output schema** (draft, mirrors `RespuestaDelAgente` fields already
  produced by `Agent.atender`, no new data invented):

  ```json
  {
    "respuesta": {
      "texto": "string",
      "confianza": "string | number, as produced by Agent.atender"
    },
    "recomendaciones": ["string", "..."],
    "razonamiento": [
      {
        "orden": 1,
        "herramienta": "string",
        "razon": "string",
        "parametros": {"...": "as proposed, post-redaction"},
        "observacion": "string, post-redaction, post-`_acotar_render`-equivalent truncation"
      }
    ],
    "acciones": null
  }
  ```

  `acciones` is `null` unless `--mostrar-historial` is also passed, in which
  case it is the same array `_renderizar_respuesta` currently builds for the
  historial table (`orden`, `herramienta_id`, `estado`, `salida`) — this
  preserves FR-050's "historial oculto por defecto" behavior identically in
  JSON mode; `--json` changes *serialization format*, not *what is shown by
  default* (X — no incidental behavior change riding along with a format
  change).
- **Redaction**: every string field above passes through the same `Redactor`
  instance already used for rich rendering, applied to the JSON-serializable
  structure before `json.dumps`, not after — the non-negotiable T125 boundary
  (secrets never reach an unredacted sink) applies identically regardless of
  output format.
- **Interactive REPL + `--json`**: valid combination. Each turn prints one
  JSON document instead of one set of panels; the prompt (`"> "`) and
  session-end message move to stderr (not stdout) so a consumer piping stdout
  through `jq`/similar never has to filter non-JSON lines out of a JSON
  stream.
- **Error behavior**: if the agent raises before producing a
  `RespuestaDelAgente` (a genuine internal error, not a normal
  `sin_evidencia`/`rechazo_autorizacion` outcome — those are still valid JSON
  documents with an appropriate `respuesta.texto`), `--json` mode emits
  `{"error": {"tipo": "string", "mensaje": "string, redacted"}}` to stdout and
  exits non-zero, rather than an unstructured traceback — a machine consumer
  must never have to regex a human-formatted stack trace.
- **`--version` + `--json`**: `--version` remains `is_eager=True` and exits
  before any agent construction (unchanged); whether `--version`'s own output
  becomes `{"version": "..."}` under `--json` is a minor, low-risk detail left
  to the future implementation — flagged here as an open question, not
  resolved, since it does not affect any safety-relevant behavior.

### A.2 `--no-color`

- **Shape**: boolean flag, default `False`. Forces `rich.console.Console` to
  construct with `no_color=True, force_terminal=False` (or equivalent),
  producing the same panel/table structure but without ANSI escape codes —
  for logging pipelines / non-TTY consumers that still want the human-shaped
  layout, just without color codes polluting the text.
- **Interaction with `--json`**: `--json` implies no `rich` rendering at all,
  so `--no-color` is a no-op when `--json` is also passed. The future
  implementation MUST NOT treat this combination as an error (it is a
  harmless redundancy, not a conflict) — silently ignoring `--no-color` under
  `--json` is the correct behavior, optionally surfaced as a one-line notice
  on stderr, never a hard failure, since failing on a redundant-but-harmless
  flag combination would violate the spirit of "operator control" this whole
  item exists to serve.
- **Auto-detection**: independently of the flag, the future implementation
  should also respect `NO_COLOR` (env var, an existing informal standard) and
  non-TTY stdout as sane defaults — `--no-color` is the explicit override,
  not the only path to plain output. This is an implementation detail noted
  for completeness, not a new flag.

### A.3 Backward compatibility (Part A)

Both flags default to today's exact behavior (colored `rich` panels, human
history hidden unless `--mostrar-historial`). No existing flag's meaning
changes. Part A alone is a **strictly additive, backward-compatible**
extension of the current v1 contract — it does not, by itself, require a
contract version bump, only a documented addition to the flag table.

## Part B — Execution controls (`--max-steps`, `--model`, `--dry-run`, `--trace-file`)

### B.1 `--max-steps N`

- **Shape**: optional integer, no default override (falls back to
  `EstadoDelAgente.pasos_max`'s existing default of 12, SC-016) when omitted.
- **Validation**: `N` must be a positive integer. The future implementation
  MUST also impose a fixed upper ceiling (proposed: 50) — `--max-steps` is an
  operator convenience for tuning within a sane range, not a way to disable
  SC-016's infinite-loop protection entirely; a value above the ceiling is a
  usage error (exit code 2, §B.5), not silently clamped (IX — never silently
  reinterpret an operator's explicit input).
- **Interaction**: applies uniformly to every `Agent.atender` call made
  during the process's lifetime (REPL: every turn; `--pregunta`: the one
  call). Does not interact with `--dry-run` beyond the obvious (a dry run
  still respects the step ceiling while planning).

### B.2 `--model <id>`

- **Shape**: optional string, overrides the `LLM_MODEL` environment variable
  for this invocation only (process-local, never mutates the actual env var
  or any persisted config — VI, no hidden state).
- **Interaction with `--demo`**: `--demo` forces `FakeLLM`, which has no
  concept of a model id. `--model` combined with `--demo` is not an error —
  it is accepted and ignored, with an informational (not warning-level,
  since it is not a misuse) stderr line: *"--model ignorado (modo --demo usa
  FakeLLM)"*. Erroring here would punish an operator for a harmless
  combination (e.g. a script that always passes `--model` and sometimes adds
  `--demo` for local testing).
- **Interaction with real providers**: only meaningful when `LLM_API_KEY`
  (or equivalent) is set and `--demo` is absent; in that case it is a direct
  override of `construir_backend`'s existing env-var-driven model selection,
  no new selection logic invented.

### B.3 `--dry-run`

This is the flag with the highest security-relevant surface in Part B, so its
design must be explicit about not weakening T126 (sensitive-action
authorization gating, including indirect paths).

- **Shape**: boolean flag, default `False`.
- **Semantics**: in dry-run mode, the agent still perceives, plans, and
  reasons (percieve→plan→act deterministic-and-LLM cycle unchanged) but
  **no tool whose `requiere_autorizacion=True` is ever invoked, and no tool
  is ever invoked based on a captured authorization decision while dry-run is
  active** — regardless of what the operator would have answered at the
  authorization prompt. This is deliberately **stricter** than "skip the
  prompt and assume denial once": dry-run must never call
  `_pedir_autorizacion` at all, and must never pass `autorizacion=True` to
  `Agent.atender` under any code path, direct or indirect (T126's own
  "including indirect paths" language applies identically here — a `--dry-run`
  session must not become a backdoor that reaches `run_tests`/
  `analyze_coverage` through `analyze_test_results` or any other indirection).
- **What DOES run**: tools with `requiere_autorizacion=False` (read-only:
  `explore`, `search`, `locate`, `leer_archivo`) still execute normally —
  dry-run previews the *sensitive* part of a plan, it does not pretend the
  whole agent is offline. This gives the operator a real, evidence-grounded
  preview of "here is what the agent would do next" without the destructive
  or execution risk.
- **Output**: each step whose tool required authorization is recorded in the
  razonamiento/trace with an explicit terminal marker (proposed:
  `estado: "no_ejecutado_dry_run"`) instead of `exito`/`error`/`invalido`, so
  a `--json`/`--trace-file` consumer can distinguish "planned but withheld by
  dry-run" from every other terminal state defined by I10 §5.2/§4 — dry-run
  introduces a new, clearly-labeled state, it does not overload an existing
  one (IX — never make one state mean two different things).
- **Interaction with `--pregunta` / REPL**: valid in both modes; in REPL,
  dry-run applies to the whole session (no per-turn toggle) to keep the
  security model simple and auditable — a session is either dry-run or not,
  never silently switching mid-conversation.
- **Interaction with `--mostrar-historial`/`--json`**: orthogonal; both
  render the `no_ejecutado_dry_run` marker like any other `estado`.

### B.4 `--trace-file <path>`

- **Shape**: optional path. When set, the full razonamiento (all steps,
  parameters, observations, terminal state) for every turn of the session is
  appended, post-redaction, to the given file as one JSON object per line
  (JSON Lines) or accumulated into a single JSON array — the future
  implementation picks one, but whichever is chosen, the per-step object
  shape SHOULD mirror I10's trace schema (`docs/proposals/I10-evaluation-harness.md`
  §5.2: `orden`/`herramienta`/`parametros`/`razon`/`resultado`/`autorizacion`)
  so a human-run `--trace-file` output and an `eval`-run trace (Part C) are
  visually/structurally the same shape, even though a CLI trace is not part
  of the `eval/` corpus and is never consumed by `run_evaluation`/
  `compare_runs` — this is a convergence-of-shape convenience, not a shared
  code path or a new coupling between B and C.
- **Scope distinction from the allowlist (FR-025)**: writing to `--trace-file`
  is an **operator-initiated CLI output**, not an agent tool call against the
  target project — it is not subject to `Allowlist` (which bounds what the
  agent, not the operator, may read/write inside the analyzed project). The
  future implementation must still apply ordinary path sanity (reject a path
  that resolves inside the analyzed project's own tree by accident, to avoid
  a trace file polluting `explore`/`search` results on a later run — a
  usability guard, not a security boundary) and must never create parent
  directories implicitly (fails with exit code 2 if the parent doesn't
  exist, rather than silently creating arbitrary directories).
- **Redaction**: identical requirement to `--json` (§A.1) — every field
  written passes through `Redactor` before serialization. This is the same
  non-negotiable boundary, not a separate policy.
- **Interaction with `--dry-run`**: fully compatible; the trace file simply
  contains `no_ecutado_dry_run` markers alongside normal steps.

### B.5 Error behavior (Part B, shared)

All Part B flags use a shared exit-code convention, consistent with I10's own
exit-code scheme so an operator does not need to memorize two different
conventions for the same binary: `0` normal completion, `2` usage/config
error (invalid `--max-steps` value, unwritable `--trace-file` parent, `--model`
on a backend that rejects the model id at construction time). No Part B flag
introduces a new success/failure distinction beyond what `Agent.atender`
already returns — B only changes *how much control the operator has over the
run* and *how much is recorded*, never the underlying safety semantics.

### B.6 Backward compatibility (Part B)

All four flags are optional with no-op-safe defaults (omit `--max-steps` →
today's 12; omit `--model` → today's env-var selection; omit `--dry-run` →
today's real execution; omit `--trace-file` → no file written). Existing
invocations without these flags are byte-for-byte unaffected. Like Part A,
Part B is additive and does not by itself require a contract version bump.

## Part C — Evaluation command (`qa-agent eval`)

### C.1 Dependency on I10

Part C is explicitly **not** an independent design — it targets exactly the
CLI shape and Python-level interface Person 2 already fixed in
`docs/proposals/I10-evaluation-harness.md` §5.6:

```
qa-agent eval run   --corpus <dir> --provider <name> --model <id>
                     [--fixtures f1,f2,...] [--replicates N]
                     --output <dir> [--price-table <path>]

qa-agent eval report --run <run_id> --runs-dir <dir> [--format json|table]

qa-agent eval compare --run-a <run_id> --run-b <run_id> --runs-dir <dir>
                       [--tolerances <path>] [--format json|table]
```

backed by `run_evaluation(corpus_dir, *, provider, model, model_params=None,
fixtures=None, replicate_count=3, output_dir, price_table_path=None) ->
EvaluationReport` and `compare_runs(run_id_a, run_id_b, *, runs_dir,
tolerances=None) -> ComparisonReport`. I14 does not redefine these signatures,
flags, or exit codes (`0`/`1`/`2` per I10 §5.6) — it only fixes **where this
CLI surface sits relative to the rest of the approved contract** (§C.2) and
**how it composes with Parts A and B** (§C.3). Building `eval` is gated on
I10 itself being approved and implemented first — this document assumes that
precondition, it does not satisfy it.

### C.2 Contract-version decision (see also §4)

`eval` is the **first subcommand** the approved CLI would ever have. The
current contract's explicit sentence — *"El punto de entrada aprobado no
registra subcomandos"* — means adding `eval` is not a natural, backward-
compatible extension of v1; it is a **new major version of the CLI contract**
(proposed: v2), because:

1. Today, `qa-agent <flags>` unambiguously means "run one agent turn." Under
   a naive addition, `qa-agent eval` could be parsed either as a subcommand
   or as a (nonsensical) value for some existing option — Typer's own
   default-command mechanics require an explicit decision about how the two
   coexist (e.g., keep `main` as the implicit default command via
   `invoke_without_command=True` on a `typer.Typer(no_args_is_help=False)`
   root, and register `eval` as a sibling `typer.Typer` sub-app). This is a
   structural change to the CLI's argument-parsing shape, not a new flag.
2. `eval`'s own flags (`--corpus`, `--provider`, `--run`, `--runs-dir`, etc.)
   are a **separate namespace** from the main command's flags
   (`--ruta`/`--pregunta`/`--demo`/`--mostrar-historial`). They must not be
   merged into one flat flag list — `qa-agent eval run --ruta foo` must be a
   parse error (unrecognized flag for that subcommand), not silently
   accepted, so an operator never wonders whether `--ruta` means "project
   being analyzed" or "project under evaluation" (VII — validation must
   reject ambiguity, not paper over it).

### C.3 Interaction with existing approved flags and with Parts A/B

- `--version` stays global (usable as `qa-agent --version` and, if the future
  implementation chooses, also as `qa-agent eval --version` reporting the
  same value — not a new version scheme for `eval` specifically).
- `--ruta`, `--pregunta`, `--demo`, `--mostrar-historial` are **not** valid
  under `eval` subcommands; they belong to the single-turn agent-invocation
  command only. `eval run`'s `--corpus`/`--fixtures` play an analogous but
  distinct role (which fixtures to evaluate, not which live project to
  analyze) and must not be aliased to `--ruta` even though both are "a path."
- Part A's `--json`/`--no-color`: **recommended** to apply uniformly as
  global flags available both on the bare command and on every `eval`
  subcommand (`qa-agent eval report --run X --json` should work, and lines
  up with I10 §5.6's own `--format json|table` on `eval report`/`eval
  compare` — the future implementation should treat I10's `--format json`
  and I14's `--json` as the same concept under `eval`, not two competing
  flags; i.e. `eval report --format json` is the canonical spelling under
  `eval`, and a bare `--json` alias MAY be accepted for consistency with the
  main command but must not diverge in output shape).
- Part B's `--max-steps`/`--model`/`--dry-run`/`--trace-file` are **not**
  applicable to `eval` — `eval` runs are already fully specified by I10's own
  `model_params`/`replicate_count`/pinned config (I10 §5.4/§6). Passing a
  Part B flag to an `eval` subcommand is a usage error (exit code 2), not a
  silently-ignored no-op like the `--model`/`--demo` case in §B.2 — unlike
  that case, there is no harmless interpretation of e.g. `--dry-run` under
  `eval run` (I10's replicate/reset semantics already have no destructive
  side effect on the *live* project, only on disposable fixture copies, so
  "dry run of an eval run" is not a meaningful request and should be
  rejected rather than guessed at).
- `qa-agent chat` remains explicitly out of scope. Adding `eval` is a
  narrowly-scoped, single-purpose exception carved out for operator/CI
  tooling around evaluation runs — it is not a reopening of the "does the CLI
  register general-purpose subcommands" question, and does not imply
  `chat`/`--sesion-dir`/persistent conversation (US-12, still deferred) get
  any closer to being un-deferred. A future Spec adopting `eval` MUST say
  this explicitly, to prevent `eval`'s approval from being read as precedent
  for reviving `chat`.

### C.4 Error behavior

Exactly I10 §5.6's exit codes: `0` all deterministic metrics within
tolerance / no comparison requested; `1` a deterministic, gate-eligible
metric violated its tolerance (only for `compare`); `2` corpus/run-directory/
config error. I14 adds no new exit code for the CLI wrapper itself — a
Typer-level argument-parse failure (e.g. missing required `--corpus`) uses
Typer's own standard usage-error exit code, which the future implementation
should confirm does not collide with I10's `2` (both being "config/usage
error" is an acceptable overlap, not a conflict, since neither is a
regression-finding code `1`).

## 2. Cross-cutting: what all three parts must NOT do

- None of A/B/C changes the sensitive-action authorization semantics, the
  redaction boundary, the `.qa_sessions` non-persistence, the
  `generate_test_cases` two-argument contract, or the subprocess
  classification semantics (T125–T131). Every flag design above was checked
  against each of these explicitly (§A.1 redaction, §B.3 dry-run/T126,
  §B.4 redaction) rather than assumed compatible.
- None introduces a new dependency. `--json` uses the stdlib `json` module;
  `--no-color` uses `rich`'s existing `Console` constructor arguments (already
  a dependency); `--trace-file` uses stdlib file I/O; `eval` reuses I10's own
  "no new dependency" commitment.
- None is implemented by this document. A future Spec (per the backlog's own
  "Requires future Spec: YES") is required before any code change, and that
  Spec is expected to make the concrete contract-version decision this
  document only flags as necessary (§C.2/§4).

## 3. Files this document intentionally does not touch

`src/qa_agent/cli/main.py`, `specs/001-core-ai-qa-agent/contracts/agent-interface-contract.md`,
`pyproject.toml`, and no test file. This is a design proposal only.

## 4. Explicit backward-compatibility statement (summary)

| Part | Backward compatible with current v1 contract? | Reason |
|---|---|---|
| A (`--json`, `--no-color`) | YES | Purely additive, opt-in, default preserves today's exact output |
| B (`--max-steps`, `--model`, `--dry-run`, `--trace-file`) | YES | Purely additive, opt-in, default preserves today's exact behavior |
| C (`qa-agent eval`) | **NO — requires a v2 contract decision** | Introduces the first subcommand; the current contract explicitly states no subcommands are registered. This is a deliberate, named exception scoped to evaluation tooling, not a reversal of that design decision, and it must be stated as such in whatever future Spec approves it, not silently folded into a "minor CLI update." |

## 5. Explicit non-goals (XIV)

- No implied timeline or resourcing commitment.
- No new FR/SC/US introduced by this document; a future Spec authoring Parts
  A/B/C would introduce whatever FR/SC/US numbers are needed at that time.
- Does not revisit or weaken the backlog's own I14 classification
  ("Requires future Spec: YES", "Requires future Plan/ADR: YES") — this
  document is input to that future Spec, not a substitute for it.
