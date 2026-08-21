# I09 — Structured Observability (Design Only, POST-MVP)

Status: DESIGN ONLY — no code in this change. Requires a future Spec +
Plan/ADR before implementation (per `qa-agent-improvement-backlog.md` §I09
and `tareas-divididas.md` Persona 5).

Author: Person 5 (I08/I09/I12 owner). Date: 2026-08-20.

## 1. Problem

`RedactorFormatter` (`src/qa_agent/logging_config.py`) guarantees secrets
never reach logs, but log lines are free-text, not structured events. There
is no correlation ID tying one user request to its tool calls, no per-tool
duration, no explicit record of which model/provider answered, no record of
authorization decisions (granted/denied/pending), no stop-reason field, and
token usage — when the backend reports it — is not captured anywhere.
Diagnosing a slow or failed run today means re-reading prose log lines.

## 2. Goals / Non-goals

**Goals**
- Define a structured, OPT-IN event schema an operator can turn on to
  diagnose one run without reading source.
- Every field must be classified by sensitivity and pass through the
  existing `Redactor` before being emitted.
- Bounded, non-persistent by default (Constitution XII: no new storage
  without justified need).

**Non-goals**
- No new persistent store, no revival of `.qa_sessions` (T127 keeps that
  deferred; this design does not touch it).
- No change to `loop.py` or `router.py` in this document — this is a design
  artifact only. Implementation is a separate, future, approved change and
  is explicitly out of scope for Person 5's current wave (Person 1 owns
  `loop.py`/`router.py` this wave).
- No APM/tracing vendor integration, no network export. This is local,
  in-process, opt-in emission only.
- Does not depend on I06 (Person 3's runner-metadata design); I06's fields
  are referenced below purely as an optional future input, not a
  requirement, per the coordinator's dependency note ("optional").

## 3. Design

### 3.1 Correlation ID

A `correlation_id` (UUID4, generated once per `Agent.atender(...)` call) is
attached to every event emitted during that call. It is process-local and
never persisted; it exists only to let an operator `grep` one run's events
out of a stream. It is not a session ID — no continuity across calls, no
storage, no reuse (this keeps XII intact: it is an ephemeral correlation
handle, not a memory feature).

### 3.2 Event schema (draft)

```json
{
  "schema_version": "1",
  "event": "tool_call | authorization | model_call | run_summary",
  "correlation_id": "uuid4",
  "ts": "ISO-8601 UTC",
  "tool_id": "string | null",
  "duration_ms": "number | null",
  "model": {"provider": "string", "model_id": "string"} ,
  "authorization": "granted | denied | pending | null",
  "stop_reason": "string | null",
  "token_usage": {"prompt": "number", "completion": "number"} | null
}
```

One JSON object per emitted line (structured logging, not free text), so it
composes with existing `RedactorFormatter`-based logging rather than
replacing it.

### 3.3 Field-by-field sensitivity classification

| Field | Sensitivity | Redactor applies? | Notes |
|---|---|---|---|
| `schema_version` | Public | No | Static constant. |
| `event` | Public | No | Enum, no user content. |
| `correlation_id` | Public (opaque) | No | Random UUID, carries no meaning outside the process; not a secret, not PII. |
| `ts` | Public | No | Timestamp. |
| `tool_id` | Public | No | Fixed catalog identifier (e.g. `run_tests`), not free text. |
| `duration_ms` | Public | No | Numeric measurement, no content. |
| `model.provider` / `model.model_id` | Internal | No | Configuration identifiers (e.g. `openai`, `gpt-4o`), not secrets. Never includes the API key. |
| `authorization` | Internal | No | Enum only (granted/denied/pending); never includes the raw command or path that was authorized — see 3.5. |
| `stop_reason` | Internal | Yes (defense in depth) | Free-text-adjacent (e.g. "max steps exceeded", but a future stop reason could echo a plan fragment) — pass through `Redactor` even though today's values are static enums, so a future free-text reason cannot leak. |
| `token_usage.*` | Internal | No | Integers only. |

Any field NOT in this table is out of scope for I09 and must not be added
without updating this classification.

### 3.4 Redactor integration

Rule: **any field whose value could ever contain LLM output, tool output,
or user input MUST be passed through `Redactor.redactar(...)` before
serialization**, exactly like `RedactorFormatter` already does for prose
logs. Concretely: `stop_reason` is redacted; all other fields in the
schema above are drawn from closed enums or numeric measurements and are
therefore not free text, so passing them through the redactor would be a
no-op — but the emitter implementation should still route the *entire*
event dict through `Redactor.redactar(...)` (it already recurses over
dicts) rather than hand-picking which fields to skip. This makes the
safety property structural, not a per-field discipline the next author has
to remember: **if a future field is added that could carry user/LLM/tool
content, redaction is automatic, not opt-in per field.**

This is the same posture as T125: redact at the boundary, unconditionally,
rather than trusting each call site to remember.

### 3.5 What is explicitly excluded from `authorization` events

The `authorization` event's `granted|denied|pending` value is emitted
without the raw file path, shell command, or diff that was authorized. If a
future increment wants that detail for audit purposes, it must go through
the same `Redactor` pass and be explicitly re-approved — recording *what
was authorized* in full is a bigger surface than recording *whether it
was*, and is not part of this design.

### 3.6 Retention policy

- **No persistent store.** Events are emitted to the existing logging
  pipeline (stdout/stderr or whatever handler `configurar_logging` attaches
  today) and nowhere else. No file, no DB, no `.qa_sessions` entry.
- **Bounded by process lifetime.** Events exist only as long as the log
  sink already configured by the host keeps them (log rotation, terminal
  scrollback, CI job log retention — all outside this system's control and
  already governed by whatever policy applies to today's prose logs).
- If a future increment wants a rolling in-memory ring buffer (e.g. "last
  N events for `qa_agent status`"), that is a NEW proposal requiring its
  own justified-need writeup per XII — it is out of scope here and must
  not be assumed.

### 3.7 Opt-in / default-off

**Default: OFF.** Rationale:
- Constitution IV (least privilege) and XI (secrets never in logs) argue
  for the narrowest default. Even with redaction, a new structured
  emission path is new attack surface (a bug in the redactor pass-through
  is a smaller blast radius if the feature is off by default) until this
  design has run in production long enough to be trusted.
- Existing behavior (prose logs via `RedactorFormatter`) already satisfies
  VIII's traceability requirement at MVP level; I09 is an *enhancement*,
  not a gap-fill, so it does not need to default on to meet any existing
  requirement.

Proposed activation: an explicit flag (e.g. `QA_AGENT_OBSERVABILITY=1` env
var or a constructor parameter on `Agent`, to be decided in the future
Plan/ADR) that a human operator sets deliberately (Constitution V:
human-in-the-loop — an operator opts in, the agent does not enable its own
telemetry). When off, zero events are constructed (not constructed-then-
discarded) to avoid paying the redaction/serialization cost or risking a
partially-implemented redaction path being exercised silently.

## 4. Relationship to I06 (optional, not required)

Person 3's I06 (runner-metadata design, `docs/proposals/I06-runner-metadata.md`
if/when it lands) may eventually define approved fields such as runner name
or exit-code semantics that this schema's `tool_call` event could reuse
instead of inventing parallel fields. This design does **not** reference or
assume any I06 field today — if I06 lands with an approved contract, a
future revision of this document can add a `runner` sub-object under
`tool_call`, subject to the same sensitivity classification and Redactor
pass described above. Until then, `tool_id` and `duration_ms` are sufficient
and self-contained.

## 5. Open questions for the future Spec/Plan

1. Where does the opt-in flag live — env var, CLI flag, `Agent` constructor
   parameter, or config file? (Needs a decision before implementation.)
2. Should `model_call` events include prompt/response byte counts (useful
   for cost analysis) without including content? Byte count alone is not
   free text and would not need redaction, but must be explicitly approved
   as a new field with its own sensitivity row.
3. Should there be a maximum events-per-run cap to bound emission volume
   for pathological loops (SC-016 already caps `pasos_max`; this would be a
   belt-and-suspenders cap on the observability layer itself)?

## 6. Explicit non-regression statement

This design introduces no persistent storage, no `.qa_sessions` revival, no
change to `loop.py`/`router.py`, and no change to the `Redactor`'s existing
behavior. It only proposes a new, opt-in, off-by-default consumer of the
already-existing `Redactor`.
