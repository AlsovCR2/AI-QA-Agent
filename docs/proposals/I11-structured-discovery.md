# I11 — Structured Language/Symbol Discovery (Design Only)

## Status

DESIGN ONLY. No AST/LSP/index infrastructure is installed and no extraction
code is written as part of this document. This is advisory input for a
future Spec/Plan/ADR, per the backlog's classification of I11
(`Requires future Spec: YES`, `Requires future Plan/ADR: YES`,
`Current SDD status: POST-MVP`). It grants no implementation authority.

Author: Person 4 (I07/I11/I13 wave). Builds on I07
(`src/qa_agent/tools/exclusion_policy.py`), which decides *which files* are
visible to discovery; this document is scoped to what happens *inside* a
file I07's policy already allows through — the two concerns are
independent and this design requires no change to I07.

## 1. Problem statement

Today, real-symbol extraction lives entirely in
`generate_test_cases.py::_extraer_metodos` and has exactly two tiers:

- **Python**: `ast.parse` + `ast.walk` over `ast.FunctionDef` nodes — a real
  parser, full syntactic fidelity for Python, but does not resolve types,
  imports, decorators-as-metadata, or class membership (it flattens all
  functions found anywhere in the module, including nested ones).
- **Everything else** (C#, Java, JS, TS, Ruby, Go, PHP, C/C++, Kotlin,
  Swift — the full `_EXTENSIONES_CODIGO` map): one shared regex,
  `\b(?:public|private|protected|internal|static|virtual|override|async)\s+[\w<>\[\]?,\.]+\s+(\w+)\s*\(([^)]*)\)`,
  applied uniformly regardless of language. It is a best-effort heuristic,
  not a parser, and its precision ceiling is low and language-blind.

Separately, "language detection" is implicit and extension-based only
(`_EXTENSIONES_CODIGO`); there is no shared interface that other tools
(`locate`, `search`, future ones) could reuse to ask "what language is this
file, and can I trust structural claims about it."

## 2. Goals

- Define stable, minimal interfaces for **language detection** and
  **symbol extraction**, decoupled from any specific implementation
  (native AST, LSP, external index).
- Preserve Constitution VI (determinism, no LLM in this layer) and
  FR-008/FR-019 (never fabricate symbols; distinguish "found none" from
  "could not analyze").
- Specify deterministic fallback behavior when no AST/LSP/index backend is
  available for a language.
- Specify explicit behavior for languages with no support at all.
- Compare AST / LSP / structured-index implementation strategies on
  precision, cost, and dependency footprint.
- Specify failure semantics (parse errors, oversized files, timeouts,
  unexpected exceptions) using the same idioms already established in this
  codebase (`search.py`'s truncation-with-note, `run_tests.py`'s bounded
  `subprocess` timeout, `generate_test_cases.py`'s backend-error handling).

## 3. Proposed interfaces

```python
class LenguajeDetectado(str, Enum):
    PYTHON = "python"
    CSHARP = "csharp"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUBY = "ruby"
    GO = "go"
    PHP = "php"
    C = "c"
    CPP = "cpp"
    KOTLIN = "kotlin"
    SWIFT = "swift"
    DESCONOCIDO = "desconocido"


class DetectorLenguaje(Protocol):
    """Deterministic, extension/marker-based — never network, never LLM."""

    def detectar(self, ruta_archivo: Path) -> LenguajeDetectado: ...


@dataclass(frozen=True)
class Simbolo:
    nombre: str
    tipo: Literal["funcion", "metodo", "clase", "interfaz", "desconocido"]
    firma: str
    linea_inicio: int
    linea_fin: int | None
    confianza: Literal["alta", "media", "baja"]
    # alta  = real grammar/AST parse for that language
    # media = validated structural heuristic (e.g. ctags-style regex grammar)
    # baja  = single shared cross-language heuristic (today's regex fallback)


@dataclass(frozen=True)
class ResultadoExtraccion:
    simbolos: list[Simbolo]
    estado: Literal["extraido", "sin_coincidencias", "no_soportado", "parse_error", "omitido_por_tamano", "error_extraccion"]
    detalle: str | None = None  # human-readable reason, redacted if it may embed content


class ExtractorSimbolos(Protocol):
    lenguajes_soportados: frozenset[LenguajeDetectado]

    def extraer(self, contenido: str, lenguaje: LenguajeDetectado) -> ResultadoExtraccion: ...
```

Two things this shape enforces:

1. `Simbolo.confianza` makes the fidelity of each result inspectable by the
   caller (and, transitively, citable by the LLM prompt as "heuristic" vs.
   "structural"), instead of presenting every extracted method as equally
   trustworthy — today's `generate_test_cases.py` output does not carry
   this distinction at all.
2. `ResultadoExtraccion.estado` separates **"analyzed, found zero"**
   (`sin_coincidencias`) from **"could not be analyzed"**
   (`no_soportado`, `parse_error`, `omitido_por_tamano`,
   `error_extraccion`) — today's code conflates these into a single empty
   list. This is a design gap worth naming even though closing it is out
   of scope for a design-only document; a future Plan implementing I11
   should carry this forward as an explicit acceptance criterion.

## 4. Deterministic fallback behavior (no AST/LSP/index available)

Fixed, three-step order — never chosen ad hoc per call, always the same
per `(language, capability-tier-installed)` pair, so a given deployment is
reproducible (VI):

1. **Native AST**, if the interpreter/stdlib already provides one for that
   language with zero new dependencies. Today this is Python's `ast` only.
   Result tagged `confianza="alta"`.
2. **Deterministic structural heuristic**, if one is registered for that
   language family (today: the shared brace-language signature regex).
   Result tagged `confianza="baja"` — explicitly *not* promoted to `media`
   or `alta` just because it ran; confidence reflects the technique, not
   whether it executed successfully.
3. **No extractor registered** for the language → `estado="no_soportado"`,
   `simbolos=[]`. This must not silently reuse the cross-language regex
   unless that language family is deliberately registered for it (today,
   the regex is applied to *every* non-Python extension, which is itself
   an overreach this design flags — a future Plan should enumerate exactly
   which language families the shared regex is validated against, rather
   than applying it universally by default).

Adding a language to tier 1 or 2 is a deliberate, reviewed change to this
document and the registry, never an automatic byproduct of adding a file
extension to discovery (Constitution XII — no speculative complexity).

## 5. Explicit behavior for unsupported languages

- `DetectorLenguaje.detectar()` returning `DESCONOCIDO` (unrecognized
  extension) or an extension recognized by discovery-as-"code" but absent
  from `ExtractorSimbolos.lenguajes_soportados` are both terminal states:
  `ResultadoExtraccion(simbolos=[], estado="no_soportado")`.
- `no_soportado` is **not an error** — the file is still returned as a
  `fuentes` citation (whole-file content, unchanged from today's
  behavior); only the *structural symbol list* is empty. This matches
  FR-019: the agent never invents symbols it did not actually parse, but
  it also never hides that a file was consulted as evidence.
- The caller-facing contract (e.g. `generate_test_cases`) must surface
  `no_soportado` distinctly if it ever exposes per-file extraction status
  to the LLM prompt or the CLI, so "no functions found" and "cannot parse
  this language yet" are never conflated in what a user reads.

## 6. Comparison of implementation options

### Option A — Per-language AST / grammar parser

Native AST (stdlib) where available; otherwise a grammar-binding library
per language (e.g. `tree-sitter` core + one `tree-sitter-<lang>` grammar
package per language), invoked in-process.

- **Precision**: high — syntactically exact for that language's grammar:
  correctly handles generics, decorators, nested/local functions,
  multi-line signatures, records/primary constructors, etc. Still
  *syntactic only* — no cross-file type or import resolution.
- **Determinism**: high — pure parse of the given text, no process
  lifecycle, no network.
- **Dependencies**: Python needs none (stdlib `ast`). Each additional
  language needs one grammar-binding package (a real new pip dependency,
  versioned against a specific grammar revision — a maintenance surface
  that grows linearly with languages supported).
- **Cost profile**: cheapest option that still yields `confianza="alta"`
  results; the natural incremental path (one language, one dependency, one
  PR at a time).

### Option B — LSP (spin up a language server, query `textDocument/documentSymbol`)

Launch the ecosystem's language server (pyright/tsserver for JS/TS,
OmniSharp or csharp-ls for C#, jdtls for Java, gopls for Go,
rust-analyzer for Rust) as a subprocess and speak JSON-RPC to it.

- **Precision**: very high — semantic, not just syntactic: resolves
  imports, inheritance, overload sets, cross-file references.
- **Determinism**: weaker — servers do background indexing/workspace
  initialization with variable timing; a query issued before indexing
  settles can under-report symbols. Any adoption would have to define a
  bounded "wait for ready" protocol and mark results incomplete if that
  bound is hit, or the tool stops being reproducible (violates VI).
- **Dependencies**: heaviest tier. Each server is an external
  binary/runtime with its own install story (npm global package, `dotnet
  tool install`, a JVM, the Go toolchain, `cargo install`) — none of these
  are ordinary pip dependencies, and standing up "one interpreter, N
  language runtimes" is a meaningfully larger operational footprint than
  this project currently has. A JSON-RPC client library is also a new
  Python dependency.
- **Security/least-privilege note**: launching a language server is
  process execution over untrusted project content, structurally the same
  category of risk `run_tests.py`/`analyze_coverage.py` already manage via
  a fixed command allowlist and a bounded `subprocess.run(..., timeout=…)`.
  Any Option B adoption must go through that same allowlist discipline —
  it cannot invoke an LSP binary with unconstrained arguments.
- **Cost profile**: highest precision, highest cost and largest new attack
  surface; justified only if Option A's syntactic ceiling repeatedly and
  demonstrably fails a real, evidenced use case.

### Option C — Structured index (universal ctags, or SCIP-style per-language indexers)

Pre-compute (or compute on demand) a symbol index file and query it
instead of parsing on every call.

- **Precision, light variant (ctags)**: medium — `ctags`-style tools are
  themselves regex/heuristic grammars internally for most languages, so
  the precision ceiling is close to Option A's weakest tier, just
  externalized to a tool that already covers many languages.
- **Precision, heavy variant (SCIP)**: comparable to Option B — dedicated
  per-language indexers (e.g. `scip-python`, `scip-java`) do real semantic
  analysis; same dependency and process-execution footprint concerns as
  Option B, just batched instead of interactive.
- **Freshness risk**: any cached index must be regenerated whenever the
  underlying file changes, or the tool would present stale structure as
  current — a direct conflict with FR-008 ("report only what is actually
  observed"). An index-based design must either regenerate on every
  discovery call (losing most of the performance benefit that motivated
  indexing) or carry an explicit staleness check tied to file mtime/hash.
- **Dependencies**: light variant needs one external binary
  (`universal-ctags`, not reliably pip-installable cross-platform — would
  need to be present on the host or bundled); heavy variant has the same
  footprint as Option B per language.

### Recommendation captured by this design (not an implementation directive)

Consistent with Constitution II (modularity), IV (least privilege — avoid
unnecessary process execution against untrusted content) and XII (no
speculative complexity): pursue **Option A, incrementally, one language at
a time**, preferring a single well-vetted grammar-binding dependency
(`tree-sitter` + one grammar package per newly supported language) over
Option B or C. Option B/C should be revisited only if a future Spec
documents a concrete, evidenced case where Option A's syntactic ceiling is
insufficient — not adopted preemptively.

## 7. Confidence/precision limits per approach (summary table)

| Approach | Confidence tier | Known ceiling |
|---|---|---|
| Python stdlib `ast` | `alta` | Syntactic only — no cross-file type/import resolution. |
| Shared cross-language regex (today's fallback) | `baja` | Misses expression-bodied members, multi-line parameter lists, generic constraints spanning lines, records/primary constructors, arrow functions/lambdas assigned to consts, decorators before a signature. |
| `tree-sitter` grammar per language (Option A general case) | `alta` | Grammar-accurate parse tree; still syntactic only, no semantic resolution. |
| LSP (Option B) | `muy alta` | Semantic and cross-file, but timing-dependent (background indexing) — must be explicitly bounded or marked incomplete to remain reproducible. |
| `universal-ctags` index (Option C light) | `media` | Same heuristic ceiling as the shared regex, for languages ctags does not parse with a real grammar. |
| SCIP-style index (Option C heavy) | `muy alta` | Comparable to LSP; freshness must be actively managed. |

## 8. Failure semantics

- **Parse/grammar error** (e.g. `ast.parse` raising `SyntaxError` on a
  malformed file): return `estado="parse_error"`, `simbolos=[]` — distinct
  from `sin_coincidencias`, so a caller can tell "this file is broken" from
  "this file legitimately declares nothing extractable." (Today's code
  catches `SyntaxError` and returns `[]` indistinguishable from "no
  functions" — carried forward here as a named gap for the eventual Plan.)
- **Oversized files** (large generated code, minified bundles): a fixed
  size/line-count cap, beyond which extraction is skipped and reported as
  `estado="omitido_por_tamano"` — never silently truncated and presented
  as a complete symbol list. Mirrors `search.py`'s existing
  `max_ocurrencias` truncation-with-`nota` precedent.
- **Binary / undecodable content**: unchanged — already filtered upstream
  by `generate_test_cases.py`'s
  `except (OSError, UnicodeDecodeError): continue` before content ever
  reaches an extractor; this design does not loosen that boundary.
- **Timeout** (relevant to Option B/C, which may shell out or wait on an
  external process): a fixed bounded timeout, mirroring `run_tests.py`'s
  `subprocess.run(..., timeout=120)`; on timeout, report
  `estado="error_extraccion"` (or a dedicated `omitido_por_timeout` state
  if a future Plan wants that granularity) — never a partial result
  presented as complete.
- **Any unanticipated exception**: caught at the extractor boundary, never
  propagated to crash the tool call; reported as `estado="error_extraccion"`
  with a message passed through `Redactor` before being surfaced, following
  the same pattern `generate_test_cases.ejecutar()` already applies to LLM
  backend errors.

## 9. Dependency model (nothing installed by this document)

| Option | New dependency per language | Notes |
|---|---|---|
| A — Python | none | stdlib `ast`, already used today. |
| A — other languages | one `tree-sitter-<lang>` grammar package (+ `tree-sitter` core, added once) | Pure grammar binding, no external runtime/process. |
| B — LSP | one external server binary/runtime per language (npm/dotnet-tool/JVM/Go toolchain/cargo, not pip) + one JSON-RPC client library (added once) | Largest footprint; requires process-execution allowlist discipline like `run_tests.py`. |
| C — light (ctags) | one external `universal-ctags` binary (not reliably pip-installable) | No new Python library beyond stdlib output parsing. |
| C — heavy (SCIP) | one per-language indexer binary/toolchain + one protobuf-based SCIP reader library (added once) | Same footprint class as Option B. |

None of these are installed, vendored, or referenced from code as part of
this document. Any concrete adoption is a separate, future Spec/Plan/ADR,
per the backlog's classification of I11.

## 10. Relationship to I07

I07 (`exclusion_policy.py`) answers "which files does discovery even look
at." I11 is strictly downstream of that decision: it operates only on
files I07's centralized policy already allows through, and requires no
change to I07's exclusion sets. The two remain independently testable and
independently evolvable.
