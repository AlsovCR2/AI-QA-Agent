# I13 — Next Ecosystem: JavaScript/TypeScript (Design Only)

## Status

DESIGN ONLY. No implementation, no new dependencies, no new code. Advisory
input for a future Spec/Plan/ADR, per the backlog's classification of I13
(`Requires future Spec: YES`, `Requires future Plan/ADR: YES`,
`Current SDD status: FUTURE FEATURE`). It grants no implementation
authority.

Author: Person 4 (I07/I11/I13 wave). Uses this author's own I11 design
(`docs/proposals/I11-structured-discovery.md`) as the reference model for
any future symbol-extraction depth, but I13 itself does not require I11 to
be implemented — see §9.

## 1. Candidate selection and justification

Candidates considered against the currently-recognized conventions
(Python, .NET via `*.csproj`/`*.sln`, Maven-Java via `pom.xml`, Gradle via
`build.gradle`): **JavaScript/TypeScript**, Go, Rust.

Discovery already partially recognizes many extensions as "source" for
citation purposes (`generate_test_cases.py`'s `_EXTENSIONES_CODIGO`
includes `.js`, `.ts`, `.go`), so raw extension recognition does not
differentiate the candidates. The decision instead rests on what a first
**runner + coverage + parsing** increment actually costs and how much of
the ecosystem it unlocks:

- **JavaScript/TypeScript — selected.**
  - One project marker (`package.json`) plus one detection step
    (`tsconfig.json` / a `"typescript"` dependency) covers **two**
    currently-unsupported languages in a single increment, both of which
    already appear in `_EXTENSIONES_CODIGO` today with no runner behind
    them.
  - The dominant test runners (Jest, Vitest, Mocha) all ship a
    **stable, documented JSON report mode** (`--json` /
    `--reporter=json`), a strictly easier and more reliable parsing target
    than the regex-based text scraping `run_tests.py` already does for
    pytest/dotnet/maven/gradle.
  - Coverage tooling (Istanbul, consumed by Jest/Vitest/`c8`/`nyc`)
    produces a standard `coverage-summary.json`, directly analogous in
    maturity to the Cobertura XML / JaCoCo XML already consumed for
    .NET/Maven.
  - Highest likely real-world prevalence among the three candidates,
    including as the frontend half of full-stack projects whose backend
    (Python/.NET/Java) this agent may already be analyzing in the same
    repository.
- **Go — not selected (this round).** `go.mod` is an equally simple
  marker and `go test -json` gives a stable NDJSON stream, but Go
  coverage output (`go tool cover -func`) is less standardized than
  Istanbul's summary JSON, and Go does not close two languages in one
  increment the way JS/TS does.
- **Rust — not selected (this round).** `Cargo.toml` is an equally simple
  marker, but `cargo test`'s default output is text-only; JSON test output
  has historically required an unstable/nightly toolchain flag
  (`-Z unstable-options`), which conflicts with this project's
  determinism and no-speculative-complexity posture (Constitution VI/XII)
  — a stable JSON contract is not guaranteed across ordinary `cargo test`
  invocations the way it is for Jest/Vitest/pytest/dotnet/mvn/gradle.

This is a single-increment recommendation, not a ranking of overall
ecosystem importance; Go and Rust remain reasonable candidates for a
later increment once JS/TS establishes the pattern.

## 2. Detection method

Follows the existing marker-file convention already used for .NET/Maven/
Gradle detection (`loop.py`'s `_MARCADORES_DOTNET`/`_MARCADORES_MAVEN`/
`_MARCADORES_GRADLE` — read-only reference, not edited by this document or
by I07; wiring a new marker set into `loop.py` is explicitly deferred to a
future integration window, same as I07's centralization):

1. **Ecosystem marker**: `package.json` present at the project root (or
   nearest ancestor within the allowlisted perimeter) → Node.js/JS project
   candidate. Absence → not detected, no behavior change from today.
2. **Runner disambiguation**: read `package.json`'s `dependencies`/
   `devDependencies` for one of `"jest"`, `"vitest"`, `"mocha"` (in that
   priority order if more than one is present, since Jest is the most
   common default and typically the one actually wired to
   `scripts.test`). Purely a JSON read — deterministic, no execution, no
   LLM (Constitution VI).
3. **TypeScript flag**: `tsconfig.json` present, or `"typescript"` listed
   in `dependencies`/`devDependencies`. This flag does not change which
   runner or coverage command is selected (Jest/Vitest/Mocha all execute
   `.ts` test files once the project's own tooling — `ts-jest`,
   `esbuild-register`, etc. — is configured); it only matters for a future
   I11 JS-vs-TS grammar choice at the symbol-extraction layer.
4. **Terminal unsupported state**: `package.json` present but none of
   `"jest"`/`"vitest"`/`"mocha"` declared → `detectado_no_soportado`
   ("Node.js project detected, no supported test runner recognized"),
   distinct from "no ecosystem detected at all." See §8.

## 3. Runner

Each runner would be invoked as one **fixed, argument-frozen command
string**, matching the existing `run_tests.py`/`analyze_coverage.py`
allowlist convention exactly — no runtime-constructed arguments, ever
(Constitution IV / SC-011).

The one new wrinkle versus every currently-allowlisted command: JSON
report modes typically accept an output-file path. Two designs, evaluated
for a future Plan to choose between:

- **(a) Fixed, pre-known relative output path baked into the allowlisted
  string itself** — e.g. the complete allowlist entry is the literal
  string `"npx jest --json --outputFile=.qa-agent/jest-report.json"`,
  with no interpolation at all. **Recommended**: preserves the existing
  "every allowlisted command is a static string" guarantee without any
  exception.
- **(b) Parse JSON from stdout directly** (Jest/Vitest support this too)
  — avoids a file artifact, but reintroduces the same
  stdout-interleaving risk `run_tests.py`'s pytest text-parser already has
  today (a test's own `console.log` calls could corrupt the JSON payload
  unless a silencing flag is also part of the fixed command).

## 4. Command allowlist (illustrative — not adopted by this document)

Additions of this shape to `run_tests.py`'s `_COMANDOS_PERMITIDOS`:

```
"npx jest --json --outputFile=.qa-agent/jest-report.json"
"npx vitest run --reporter=json --outputFile=.qa-agent/vitest-report.json"
"npx mocha --reporter json --reporter-option output=.qa-agent/mocha-report.json"
```

Additions of this shape to `analyze_coverage.py`'s
`_COMANDOS_COBERTURA_PERMITIDOS`:

```
"npx jest --coverage --coverageReporters=json-summary"
"npx vitest run --coverage --coverage.reporter=json-summary"
"npx c8 --reporter=json-summary mocha"
```

These are illustrative only. Whichever set a future Plan actually adopts
must remain fixed strings with zero argument interpolation, exactly like
every existing entry, and the Mocha reporter flag must be verified against
the pinned Mocha version before being treated as authoritative.

## 5. Result parser

- **Jest** (`--json`): one JSON object —
  `numPassedTests`/`numFailedTests`/`numPendingTests`, plus
  `testResults[].assertionResults[].status/title/failureMessages`. Maps
  onto the existing `ResultadoDeHerramienta` shape
  (`pasadas`/`falladas`/`errores`/`total`/`detalle_fallos`), the same
  target shape `run_tests.py`'s dotnet/maven/gradle parsers already
  populate. Open decision for a future Plan: Jest has no first-class
  "error" vs "failure" distinction the way pytest collection errors do —
  whether a file-level crash (no individual assertions ran) maps to
  `errores` or `falladas` needs an explicit ruling.
- **Vitest** (`--reporter=json`): structurally Jest-API-compatible by
  design; same mapping approach applies.
- **Mocha** (JSON reporter): `{stats: {passes, failures, pending}, tests,
  failures}` — same shape family, same mapping approach.
- All three are already-structured JSON, a materially easier and more
  reliable parsing target than the current regex text-scraping used for
  pytest/dotnet/maven/gradle — a reliability improvement worth naming,
  though retrofitting the existing parsers is out of scope here.

## 6. Coverage source

`coverage/coverage-summary.json` (Istanbul format): total and per-file
`lines`/`statements`/`branches`/`functions`, each with a `pct` field.
Directly analogous in role to the Cobertura XML (.NET) and JaCoCo XML
(Maven) formats `analyze_coverage.py` already consumes. A future Plan
should reuse the existing per-ecosystem dispatch pattern already
established there (mirrors `run_tests.py`'s `_parsear_salida` dispatch by
command prefix) rather than inventing a new mechanism.

## 7. Fixture strategy

Mirrors the existing precedent in `test_tools_run_tests.py`: fake
`.csproj`/`pom.xml` projects with **canned, literal VSTest/Surefire output
strings** fed directly to the parser function — `dotnet`/`mvn`/`gradle`
are never actually invoked in the test suite.

For JS/TS, the same discipline applies:

- **Parser-level fixtures**: `tmp_path`-built `package.json` (declaring
  `"jest"`/`"vitest"`/`"mocha"`) plus a small literal JSON string
  (captured once from a real minimal reference project and pinned as a
  fixture constant) fed directly to the parser — no `npx`, no
  `node_modules`, no network in CI (Constitution III: fast, hermetic,
  reproducible tests).
- **Detection-level fixtures**, following the
  `test_discovery_exclusion_characterization.py` precedent from I07:
  `package.json` alone → detected, unsupported runner;
  `package.json` + `"jest"` devDependency → Jest detected;
  `package.json` + `tsconfig.json` → TypeScript flagged; no
  `package.json` → not detected at all.
- **Live integration test** (actually running `npm install && npx jest`
  against a tiny fixture project) is explicitly **not recommended**,
  for consistency with the fact that no currently-supported ecosystem's
  test suite invokes the real `dotnet`/`mvn`/`gradle` toolchain either —
  keeping JS/TS to the same "parser only, never the real toolchain in CI"
  standard avoids a new network/toolchain dependency in this repository's
  own CI.

## 8. Security considerations

- **`npx` can silently fetch and execute a package that isn't installed
  locally.** This is a materially different risk profile from
  `dotnet test`/`mvn test`/`gradle test`, which only ever execute code
  already present in the target project's own dependency-locked toolchain
  — a real divergence from every currently-supported ecosystem, and the
  single most important open security question for this proposal. A
  future Plan MUST resolve it before any JS/TS command reaches a real
  allowlist, e.g. by invoking the locally resolved
  `node_modules/.bin/<runner>` binary directly (verified to exist first,
  never falling back to an implicit network fetch) instead of `npx`.
- **`package.json`'s `"scripts"` block is attacker-controllable content**
  within a project the agent is asked to analyze. This design deliberately
  never executes `npm run test` or any user-defined script — it only ever
  invokes a fixed, pre-approved runner binary with fixed flags, exactly
  matching the existing "fixed commands only, no argument interpolation"
  discipline (SC-011 / Constitution IV). `package.json` content is only
  ever used to *select which pre-approved fixed command applies*, never to
  *construct* a command.
- **Large monorepo output**: the same bounded-timeout
  (`subprocess.run(..., timeout=…)`) and truncate-with-note precedents
  already used by `run_tests.py`/`search.py` apply unchanged.
- **Secret redaction**: `Redactor` must run over any captured
  stdout/stderr and over coverage-JSON file contents before either reaches
  an LLM prompt, exactly as it does for every currently-supported
  ecosystem today.

## 9. Explicit unsupported-state behavior

- `package.json` absent → ecosystem not detected; behavior is unchanged
  from today (no regression is an explicit requirement of adopting this
  design, not a new fallback to invent).
- `package.json` present, no recognized runner declared →
  `estado_global="no_ejecutado"` with an explicit message ("Node.js
  project detected, but no supported test runner — jest/vitest/mocha —
  was recognized"). Never silently falls back to pytest, which would
  misreport a JS project as "0 tests, nothing failed" — a false-honesty
  violation of FR-013/FR-017.
- `package.json` present, a runner is declared, but the resolved binary is
  not actually installed → the fixed command fails at execution (non-zero
  exit / `command not found`, or npx's fetch-then-fail path depending on
  how §8's open question is resolved); this must surface as
  `estado_global="no_ejecutado"` with the real (redacted) stderr, never be
  inferred as "0 tests passed."
- TypeScript compile errors (test files failing to type-check before any
  test executes) are a distinct failure mode from a failing assertion; the
  parser should map them to `errores`, not `falladas`, consistent with how
  `run_tests.py` already separates collection-time failures from assertion
  failures wherever the underlying runner reports that distinction.

## 10. Dependencies

None. No new Python package is required in `qa-agent` itself for
run_tests/analyze_coverage support — everything relies on tooling already
present in the *target* JS/TS project (`npx`/`node_modules`-resolved
binaries), which this repository never installs or vendors. (A later,
separate addition of `tree-sitter-javascript`/`tree-sitter-typescript`
grammar packages, if I11's Option A is pursued for JS/TS symbol
extraction, is out of scope for this document — see §11.)

## 11. Relationship to I07 and I11

- **I07**: the centralized exclusion policy
  (`src/qa_agent/tools/exclusion_policy.py`) already treats
  `node_modules/` as excluded, both in `NOMBRES_DIRECTORIO_EXCLUIDOS` and,
  post-ruling, in `PATRONES_EXCLUSION_ALLOWLIST`. Discovery tools will not
  scan into `node_modules/` once a JS/TS project is analyzed, with no
  further change required.
- **I11**: `.js`/`.ts` are already recognized as "source" for `fuentes`
  citation purposes today, at `confianza="baja"` per I11 §7 (the shared
  cross-language regex heuristic). I13 does not require I11 to be
  implemented — I13 closes the **test execution and coverage** gap; I11,
  if and when extended to JS/TS, would separately close the **symbol
  precision** gap using the `tree-sitter-javascript`/`tree-sitter-
  typescript` grammars I11 §6/§9 already names as the natural Option A
  pairing.
