# I12 — Structured Evidence Provenance (Design Only, POST-MVP)

Status: DESIGN ONLY — no code, no contract changes in this change. Requires
a future Spec + Plan/ADR before implementation (per
`qa-agent-improvement-backlog.md` §I12 and `tareas-divididas.md` Persona 5).

Author: Person 5 (I08/I09/I12 owner). Date: 2026-08-20.

## 1. Problem

`Observacion` (`src/qa_agent/agent/reasoning.py`) currently carries a
`paso: PasoDePlan`, a `resultado: Any`, and a free-text `evaluacion: str`.
There is no uniform record of *where* the underlying evidence came from
(which file, which tool result, which line range), no content hash to
detect whether the same claim still holds if the file changes between two
runs, and no bound on how much raw content is quoted as an "excerpt" when
evidence is surfaced to a human or to a report.

## 2. Goals / Non-goals

**Goals**
- Define a bounded `Provenance` object that can be attached to a piece of
  evidence: source type, path, line/range, content hash, bounded excerpt.
- State, as an explicit named rule, the invariant that deterministic
  evidence outranks semantic/LLM hypothesis, and that LLM output must never
  automatically become VERIFIED evidence.

**Non-goals**
- No change to `Observacion`, `PasoDePlan`, or any existing dataclass in
  this document. No contract file changes. Implementation is a future,
  separately-approved change.
- No new persistent store — a `Provenance` object is attached to an
  in-memory `Observacion` for the lifetime of one `Agent.atender(...)`
  call; it is not written anywhere.
- Does not define how Person 6's I15 consumes this — I15 depends on this
  document's invariant (see §4) but the consumption mechanism is I15's own
  design, out of scope here.

## 3. Design

### 3.1 `Provenance` object (draft shape)

```python
@dataclass(frozen=True)
class Provenance:
    source_type: SourceType        # ver 3.2
    path: str | None                # ruta relativa al proyecto, o None si no aplica
    line_range: tuple[int, int] | None  # (inicio, fin) 1-indexado, inclusive
    content_hash: str               # sha256 hex del contenido fuente completo referenciado
    excerpt: str                    # extracto acotado, ver 3.3
    origin: EvidenceOrigin          # ver 3.4 (DETERMINISTIC | HYPOTHESIS)
```

This is a plain, frozen, hashable data object — no behavior, no I/O, no
LLM calls (consistent with `reasoning.py`'s existing "modelos son datos
puros" convention).

### 3.2 `source_type` (closed enum)

- `file` — evidence read directly from a project file via an allowlisted
  tool (`leer_archivo`, `search`, `locate`, `explore`).
- `tool_result` — evidence derived from a tool's structured output that is
  not itself a file read (e.g. `run_tests`, `analyze_coverage` output).
- `llm_hypothesis` — a claim proposed by the LLM with no accompanying
  deterministic tool result. See §4 — this source type can NEVER carry
  `origin: DETERMINISTIC`.

Closed enum, not free text — an unrecognized source type must be rejected
at construction time by the future implementation, not silently accepted.

### 3.3 Bounded excerpt

- **Maximum length: 500 characters** (draft default; the future Plan/ADR
  may tune this, but it MUST be a fixed, enforced constant — never
  "however much the LLM decided to quote").
- If the underlying content exceeds the max, the excerpt is truncated with
  an explicit marker (e.g. trailing `"… [truncated, N more chars]"`) so a
  reader can tell truncation happened rather than assuming they saw
  everything.
- The excerpt is a **verbatim slice of the source** identified by `path` +
  `line_range` (or of the tool result, for `tool_result` provenance) — it
  is never LLM-paraphrased. Paraphrase is what makes an excerpt stop being
  evidence and start being a claim.
- **The excerpt MUST be passed through the existing `Redactor` before being
  attached to a `Provenance` object or surfaced anywhere** (response,
  history, logs, or a future report). This is the same non-negotiable
  boundary T125 already enforces for tool output; a bounded excerpt is
  still tool/file output and gets no special exemption. `content_hash` is
  computed over the **pre-redaction** source content (so it stays a stable
  fingerprint of what was actually read) but the hash itself is not a
  secret and is safe to expose unredacted.

### 3.4 The core invariant (named rule)

> **Rule I12-1 — Deterministic Precedence:** Evidence produced by a
> deterministic tool (file read, test run, coverage report, search/locate
> result) always outranks a semantic/LLM hypothesis about the same claim.
> **LLM output must never automatically become `origin: DETERMINISTIC`
> evidence.** An LLM hypothesis stays tagged `origin: HYPOTHESIS`
> indefinitely — the ONLY way a claim's provenance becomes
> `DETERMINISTIC` is for a deterministic tool call to independently
> produce a `Provenance` object with `source_type != llm_hypothesis`. There
> is no promotion path, no confidence-threshold upgrade, no "the LLM was
> right last time so trust it more" mechanism. Promotion does not exist.

This rule exists because Person 6's I15 (future feature, evaluation-only
per the program ledger) explicitly depends on it — I15 must not be able to
build a design where a sufficiently-confident LLM claim gets treated as
verified fact. This document is the place that invariant is anchored so
I15 (and any other future consumer) inherits it rather than re-deriving
it — and, per Constitution IX (never fabricate), a hypothesis presented as
verified fact is exactly the failure mode this rule forecloses.

`EvidenceOrigin` is therefore a **two-value closed enum**:
`DETERMINISTIC | HYPOTHESIS`. There is deliberately no third "verified by
LLM" or "high-confidence hypothesis" value — collapsing that distinction
into two values is what makes Rule I12-1 mechanically enforceable rather
than a comment someone can drift away from.

### 3.5 Content hash and change detection

- `content_hash = sha256(full_source_content).hexdigest()` — hashed over
  the complete referenced content (the whole file, or the whole tool
  result payload), not just the excerpt, so two runs can compare hashes to
  know whether the underlying evidence changed even if the excerpt window
  happens to look the same.
- This enables a future consumer to ask "is this citation still valid?"
  by re-reading the source and comparing hashes — without this design
  needing to define *how* that re-check happens (that is implementation,
  not provenance shape).

### 3.6 Relationship to existing entities

`Provenance` is an attachment, not a replacement: a future `Observacion`
could gain an optional `provenance: Provenance | None` field (None for
observations that predate this feature or that genuinely have no bounded
source, e.g. a pure LLM reflection). This document does not modify
`Observacion` — that is a future, separately-approved contract change.

## 4. Explicit non-regression / dependency statement

- No code, no contract, no dataclass in this repository is modified by
  this document.
- Rule I12-1 (§3.4) is the load-bearing invariant Person 6's I15 depends
  on and must be treated as a hard constraint, not a suggestion, by any
  future implementation or by I15's own design.
- This design does not require I06 or any other in-flight proposal to be
  approved first; it is self-contained.

## 5. Open questions for the future Spec/Plan

1. Exact excerpt max length (500 chars proposed here as a safe default —
   needs product sign-off).
2. Whether `tool_result` provenance should hash the raw tool payload or a
   canonicalized (e.g. redacted, whitespace-normalized) form — canonicalizing
   before hashing would make the hash stable across cosmetic-only changes
   but would weaken it as a "did the underlying evidence change" signal;
   this trade-off needs an explicit decision.
3. Whether `line_range` should be required (not `None`) for `source_type:
   file` to force citation precision, or remain optional for tools that
   cannot report a range.
