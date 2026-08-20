# AI-QA-Agent Remediation Plan

> **Documento de planificación previo a la implementación.** Las secciones
> “Current evidence”, “Before” y el baseline de 321 pruebas describen el estado
> observado antes de ejecutar T125–T131; no representan el código actual. La
> evidencia posterior autoritativa está en
> `docs/remediation/qa-agent-remediation-log.md`: T125–T131 FIXED, 354 pruebas
> PASS y CLI instalado verificado. Este plan se conserva para trazabilidad de
> la decisión y del ciclo rojo → verde.

## Baseline

- **Branch:** `main`
- **HEAD:** `aacffa89d9e3b5241cbfca1a892fa6a76c7a98cd`
- **Current test baseline:** `python -m pytest` — 321 passed, 0 failed,
  4,950 `DeprecationWarning` from `pathspec`, in 4.35 s (Python 3.14.7,
  pytest 9.1.1).
- **Installed package:** `qa-agent 0.1.0`, editable install pointing to this
  checkout. The console-script directory is not currently available on `PATH`;
  `python -m qa_agent.cli.main` remains usable for inspecting Typer behavior.
- **SDD analyze status:** PASS (existing SDD Remediation Gate; not rerun for
  these derived documents).
- **Authoritative feature directory:** `specs/001-core-ai-qa-agent`.
- **Working tree at entry:** the ten SDD/documentation files intentionally
  modified by the previous gate remain modified. No pre-existing change exists
  under `src/` or `tests/`.

## Authority

The Constitution, approved Spec, approved Plan and contracts, and canonical
`tasks.md` are authoritative, in that order. Source and tests describe the
current implementation but cannot create product requirements.

T125–T131 are the complete canonical implementation scope for this remediation.
This plan is derived documentation: it cannot introduce requirements, FRs, SCs,
User Stories, Tasks, framework migrations, sandbox guarantees, or future product
capabilities. G4 remains resolved: target repositories are trusted and target
tests/coverage execute on the host without a sandbox promise. US-11/ReAct stays
active; US-12 persistence remains deferred.

### T125 — Pre-LLM redaction boundary

**Gap:** G1 — raw repository/tool evidence can reach an external LLM before
redaction.

**Authority:** Constitution XI (information security); FR-021; SC-008;
`contracts/llm-backend-contract.md` rules “Los prompt y respuestas pasan por el
Redactor” and “Toda entrada ... pasa por el Redactor antes de enviarse o
guardarse”; `contracts/agent-interface-contract.md` redaction boundary.

**Current evidence:**

- `src/qa_agent/agent/loop.py::Agent._seleccionar_herramienta` passes raw
  `solicitud_texto` to `LLMBackend.seleccionar_herramienta`.
- `Agent._atender_una_pasada` passes raw request text and the unredacted
  `ResultadoDeHerramienta` to `LLMBackend.generar_respuesta`; redaction occurs
  only after the backend returns.
- `Agent._atender_react` passes raw `Intencion`, context and accumulated
  observations through `planificar`, `razonar` and `evaluar`.
- `Agent._respuesta_react` passes raw observations and intent to `responder`.
- `Sesion` redacts visible history, but that does not protect the earlier
  external-backend boundary.
- Existing `test_agent_autorizacion_redaccion.py` verifies displayed response
  and history, not what an external backend receives.

**Required behavior:** Evidence, context, request text and prompt-bound values
containing secrets recognized by the approved `Redactor` policy must be
redacted before any external `LLMBackend` method receives them. Returned output
continues to be redacted before display/history. This is an information-flow
boundary, not a sandbox requirement and not permission to redesign the backend.

**Likely affected components:**

- `src/qa_agent/agent/loop.py`
- `src/qa_agent/security/redactor.py` (reuse policy; do not expand patterns as
  part of T125 unless needed to express the existing test secret)
- `src/qa_agent/agent/reasoning.py` only if a safe copied representation is
  needed without mutating real observations
- `tests/unit/test_agent_autorizacion_redaccion.py`
- possibly a focused backend-spy fixture in the same test module

**Regression tests required:** Add a recording/spy `LLMBackend` that captures
arguments for the relevant one-pass and ReAct calls. Place recognized secrets
in user text, tool results, observations and context. Assert that the spy never
receives raw protected values and receives the redaction marker instead. Also
assert the original deterministic result remains available for internal
validation and that final output/history remain redacted.

**Acceptance evidence:** Focused tests fail before the fix because the spy
contains the raw token, then pass after the minimum boundary change. A search
through every recorded backend argument finds zero occurrences of each raw
secret, while the tool result was executed and the response remains usable.

**Dependencies:** None. Complete before T126 so authorization tests observe the
final safe LLM boundary.

**Risk:** High. In-place mutation could corrupt deterministic evidence;
incomplete coverage of backend methods could leave a bypass. Use redacted copies
and enumerate the actual `LLMBackend` calls rather than relying on final-output
redaction.

### T126 — Unbypassable authorization for target-code execution

**Gap:** G2 and G3 — indirect `run_tests` and `analyze_coverage` can execute
target code without the approved human authorization boundary.

**Authority:** Constitution IV/V; FR-012, FR-015, FR-016, FR-025 and FR-030;
SC-004 and SC-011; `agent-interface-contract.md` authorization section;
`tool-contracts.md` rules for `run_tests`, `analyze_test_results` and
`analyze_coverage`.

**Current evidence:**

- `RunTestsHerramienta.requiere_autorizacion = True`, so direct selection uses
  the normal authorization rail.
- `AnalyzeCoverageHerramienta.requiere_autorizacion = False`, although its
  `ejecutar` method calls `subprocess.run`.
- `Agent._parametros_para("analyze_test_results")` invokes
  `Agent._resultado_de_pruebas` while constructing parameters.
- `_resultado_de_pruebas` calls `run_tests.ejecutar` directly with
  `conjunto_autorizado=True`, before the selected non-sensitive
  `analyze_test_results` tool reaches the normal authorization check.
- Existing authorization tests cover directly sensitive tools, not this
  indirect parameter-construction path or coverage.

**Required behavior:** Every active operation that executes target code must
respect the existing authorization states, regardless of whether it is selected
directly or invoked as a prerequisite. PENDING and DENIED produce no subprocess;
APPROVED may continue after route/command validation. The requirement is
behavioral and does not require a new `PolicyEngine`, `Gateway` or broad loop
refactor.

**Likely affected components:**

- `src/qa_agent/agent/loop.py::_parametros_para`
- `src/qa_agent/agent/loop.py::_resultado_de_pruebas`
- `src/qa_agent/agent/loop.py::_atender_una_pasada`
- `src/qa_agent/agent/loop.py::_ejecutar_siguiente_paso`
- `src/qa_agent/tools/analyze_coverage.py`
- focused tests in `tests/unit/test_agent_autorizacion_redaccion.py`,
  `test_agent_qa_integration.py` and/or `test_reasoning.py`

**Regression tests required:** Instrument the execution tool or patch
`subprocess.run` and prove, for both indirect test analysis and coverage:

- PENDING authorization → zero subprocess calls and a pending action;
- DENIED authorization → zero subprocess calls and a denied/not-executed result;
- APPROVED authorization → execution may continue exactly once;
- invoking `analyze_test_results` cannot bypass the same policy by calling
  `run_tests` during parameter construction;
- both one-pass and ReAct routes preserve the rule where applicable.

**Acceptance evidence:** Focused tests show an exact call count of zero for
PENDING/DENIED and one only after APPROVED, with visible authorization state and
no fabricated test/coverage result.

**Dependencies:** T125 first. T127 can follow independently after T126.

**Risk:** High. Retrying a request after approval can duplicate prior actions;
moving prerequisite execution too late can break `analyze_test_results`. Keep
the behavior localized and preserve FR-020 history ordering.

### T127 — Remove/deactivate deferred persistence

**Gap:** G6/G7 — active persistence and chat/task behavior belongs to deferred
US-12 and conflicts with `Storage: N/A`.

**Authority:** Constitution XII/XIV; Spec v1.4 assumptions; Plan `Storage: N/A`
and “Alcance diferido: US-12”; canonical T127. Approved decision: US-11 KEEP;
US-12, persistent chat/memory/tasks DEFER; `.qa_sessions` REMOVE from active MVP
behavior.

**Current evidence:**

- `SesionManager.__init__` defaults to `./.qa_sessions` and immediately calls
  `mkdir`, before a save request.
- `AgentConversacional.__init__` always constructs `SesionManager` and
  `GestorTareas`.
- `cli/main.py` registers an active `chat` subcommand, constructs the persistent
  agent and exposes `/sesion`, `/tarea` and `/memoria` behavior.
- `tests/unit/test_reasoning.py` still asserts persistent session/task/chat
  behavior from deferred T085–T094.
- The approved non-persistent `Agent` and its ReAct loop do not require
  `SesionManager`.

**Required behavior:** Remove or deactivate active CLI/API paths that expose
deferred persistent conversation, memory and task management, and prevent
normal MVP execution from creating `.qa_sessions`. Preserve `Agent`, ephemeral
`Sesion` action history, ReAct planning/reasoning, authorization and all approved
US-11 behavior. Historical modules may remain unreachable if deleting them
would create unnecessary risk; they must not be active MVP behavior.

**Likely affected components:**

- `src/qa_agent/cli/main.py`
- `src/qa_agent/agent/conversational.py`
- `src/qa_agent/agent/session_manager.py`
- `src/qa_agent/agent/gestor_tareas.py`
- deferred tests in `tests/unit/test_reasoning.py`
- new/adjusted CLI or construction regression proving no directory creation

**Regression tests required:** Run normal one-shot and ReAct MVP construction in
a temporary working directory and assert `.qa_sessions` is absent before and
after. Assert the active CLI no longer advertises or dispatches deferred chat,
session, memory or task commands. Re-run US-11 reasoning tests to prove ReAct
planning, observations, step limits and response anchoring remain intact.

**Acceptance evidence:** A clean temporary project remains free of
`.qa_sessions` through agent construction and normal use; no active MVP entry
point persists session/task state; the approved US-11 focused suite passes.

**Dependencies:** Complete after T126, then run the P0 checkpoint.

**Risk:** Medium. Removing chat registration may also resolve part of the Typer
shape involved in T129, but T127 must not claim T129 complete. Avoid deleting
the ephemeral `Sesion` used by FR-020 or any ReAct model used by US-11.

### T128 — Restore GenerateTestCases backend contract

**Gap:** G5 — `GenerateTestCasesHerramienta` calls the real backend with an
incompatible signature and converts the programming error into valid-looking
empty output.

**Authority:** Constitution VII/IX; FR-017, FR-019, FR-028 and FR-029; SC-013;
`llm-backend-contract.md::LLMBackend.generar_respuesta`; approved
`tool-contracts.md::generate_test_cases` input/output schemas; canonical T128.

**Current evidence:**

- `LLMBackend.generar_respuesta(self, solicitud: dict, resultados: list)`
  returns a response dictionary.
- `GenerateTestCasesHerramienta.ejecutar` calls
  `self._llm_backend.generar_respuesta(prompt)` with one string argument.
- The broad `except Exception` converts the resulting `TypeError` or provider
  failure into `casos_propuestos=[]` with `EstadoResultado.EXITO`.
- Current tests use an unconstrained `Mock`; they do not enforce the abstract
  backend signature and therefore miss the incompatibility.

**Required behavior:** Invoke the real `LLMBackend` contract with its approved
two arguments and adapt the returned dictionary without inventing evidence.
Programming/interface failures and backend failures must yield an explicit
ERROR/INVALIDO result and error message, not a successful empty list. An actual
absence of relevant source remains the approved successful empty-evidence case.

**Contract enum sub-fix:** YES, narrowly part of T128. The approved input enum is
`happy_path | edge_cases | usuarios_no_validos`; the approved output `tipo` enum
is `happy_path | edge_case | negativo`. The implementation already defines this
mapping, but `_construir_prompt` incorrectly instructs the model to return the
input `cripticidad` exactly. Align the prompt/parser to the existing approved
mapping; do not change either contract enum.

**Likely affected components:**

- `src/qa_agent/tools/generate_test_cases.py`
- possibly a small contract-conforming fake/spy in
  `tests/unit/test_tools_generate_cases.py`
- `tests/contract/test_tool_contracts.py` if needed to assert the existing enums

**Regression tests required:** Use a concrete `LLMBackend` test double with the
real method signature. Assert the tool passes a request dictionary plus real
source-backed results, accepts the backend response shape, produces canonical
`tipo`, and preserves cited `fuentes`. Separately assert signature/provider or
malformed-response failures are explicit non-success results. Assert no-code
evidence remains a successful empty result without calling the backend.

**Acceptance evidence:** The contract-conforming backend records exactly two
arguments and produces non-empty validated cases; edge and invalid-user inputs
produce `edge_case` and `negativo`; injected backend failure returns an explicit
error and cannot be confused with “no relevant source”.

**Dependencies:** P0 checkpoint must pass first.

**Risk:** Medium. `generar_respuesta` is oriented to final agent responses, so
the adapter must use its existing shapes without inventing a new LLM interface.
Do not silently broaden T128 into a backend redesign.

### T129 — Restore documented CLI contract

**Gap:** G8 — installed Typer behavior differs from the approved top-level CLI.

**Authority:** FR-001, FR-002 and FR-050;
`contracts/agent-interface-contract.md::Contrato de CLI`; `quickstart.md`;
`pyproject.toml [project.scripts]`; canonical T129.

**Current evidence:**

- The contract requires the `qa-agent` entry point with top-level `--ruta`,
  `--pregunta`, `--demo`, `--version` and `--mostrar-historial` where applicable.
- `cli/main.py` registers both `main` and deferred `chat` using `@app.command()`.
  Typer consequently exposes a command group, requiring `main` before the
  documented options.
- `python -m qa_agent.cli.main --help` currently lists `main` and `chat`, and
  `python -m qa_agent.cli.main --version` fails with “No such option”.
- The package is editable-installed, but the console-script directory is not on
  this shell's PATH; subprocess E2E must account for environment availability
  and report UNAVAILABLE rather than PASS when the executable cannot be found.

**Required behavior:** The installed entry point must implement the approved
top-level forms. `--pregunta` performs a non-interactive request; `--ruta`
selects the target root; `--demo` forces FakeLLM; `--mostrar-historial` controls
the optional history rendering; `--version` prints the installed version and
exits. Do not rewrite the contract to preserve the broken subcommand shape.

**Likely affected components:**

- `src/qa_agent/cli/main.py`
- `pyproject.toml` only if entry-point wiring, not product syntax, is defective
- a new CLI-focused test module or extensions to `test_cli_render.py`

**Regression/E2E tests required:** Use Typer's `CliRunner` for each authoritative
top-level option and combinations documented by the contract, including
`--ruta <tmp> --pregunta <text> --demo` and the same with
`--mostrar-historial`. Verify `--version` and help. Where practical, invoke the
installed `qa-agent` console script in a subprocess; if PATH prevents it, use
the resolved script path and record the direct PATH check separately.

**Acceptance evidence:** All documented top-level invocations exit as expected,
do not require a `main` token, and no active deferred `chat` command is exposed.
The installed entry-point smoke test passes or is explicitly UNAVAILABLE with
the in-process Typer contract still proven.

**Dependencies:** T127 removes/deactivates deferred chat; T128 completed first
per the canonical P1 order.

**Risk:** Medium. Typer changes can affect module invocation and installed
console scripts differently; test both surfaces without adding new CLI flags.

### T130 — Deterministic subprocess result semantics

**Gap:** G9 — parsers can report success or `no_ejecutado` without reliably
using process `returncode`.

**Authority:** Constitution VII/IX; FR-013, FR-017, FR-018, FR-019 and FR-031;
SC-005 and SC-014; `tool-contracts.md::run_tests` and
`tool-contracts.md::analyze_coverage`; canonical T130.

**Current evidence:**

- `RunTestsHerramienta.ejecutar` captures `resultado_proc.returncode` but ignores
  it, parses combined stdout/stderr and always returns outer
  `EstadoResultado.EXITO` after parsing.
- `AnalyzeCoverageHerramienta.ejecutar` behaves the same way.
- Timeout and `OSError` are explicit, but a nonzero process with empty,
  unsupported or misleading parseable output can be classified incorrectly.
- Current mocked parser tests mostly set `returncode=0`; runner failure
  semantics are not covered systematically.

**Required behavior:** Combine return code, executable/process availability and
bounded output interpretation to distinguish deterministically:

- successful execution;
- executed tests with test failures (a valid run with `estado_global=fallo`);
- executable/tool unavailable or spawn failure;
- zero collected tests where the runner output distinguishes it;
- unparseable/unsupported output;
- timeout/process execution failure;
- not executed because validation/authorization/ruta prevented execution.

Parseable stdout alone must never override a contradictory process failure.
Expected runner-specific nonzero codes for ordinary test failures may remain a
valid executed run when the output proves that state.

**Approved output fields:** Existing contracts require only counts,
`detalle_fallos`, `estado_global` for tests, and coverage fields plus `estado`
for coverage; `ResultadoDeHerramienta.error` already carries an explicit reason.
They do **not** require `exit_code`, captured stdout/stderr, detected runner,
duration, or a new reason field in `datos`. T130 may use those values internally
and bounded text in `error` where already supported, but must not expand the
contract. Richer metadata belongs to I06.

**Likely affected components:**

- `src/qa_agent/tools/run_tests.py`
- `src/qa_agent/tools/analyze_coverage.py`
- `tests/unit/test_tools_run_tests.py`
- `tests/unit/test_tools_coverage.py`

**Regression tests required:** For both tools, mock subprocess results covering
return code 0 success, runner-specific test failure, executable `OSError`,
timeout, nonzero empty output, nonzero unsupported output, zero-tests output and
contradictory parseable-success/nonzero failure. Assert the exact outer
`EstadoResultado`, contract state and explicit error/no-error semantics.

**Acceptance evidence:** Every documented state maps to one unambiguous contract
result; non-executed/process failures are not `EXITO`; ordinary test failures
remain distinguishable from infrastructure failure; no test relies solely on
parseable stdout.

**Dependencies:** T128 and T129 completed first per canonical order.

**Risk:** High. Test runners use different nonzero conventions. Preserve known
pytest/dotnet/Maven/Gradle test-failure behavior and change only cases where
return code plus evidence proves execution failure or ambiguity.

### T131 — Regression and closure gate

**Gap:** Final evidence gate for G1, G2, G3, G5, G6, G8 and G9.

**Authority:** Canonical T131; Constitution III, VII, IX, XIII and XIV; all
requirements and contracts cited by T125–T130.

**Current evidence:** Stage-1 baseline is 321 passed. The existing SDD analysis
is PASS, but no T125–T130 regression exists yet and none may be marked complete.

**Required behavior:** T131 verifies only the approved remediation. It cannot
add unrelated features, tooling, benchmarks, frameworks or architecture work.
Evidence must distinguish PASS, FAIL, SKIPPED and UNAVAILABLE.

**Likely affected components:**

- focused regression modules modified by T125–T130
- `specs/001-core-ai-qa-agent/tasks.md` completion/evidence references only
  after objective Done conditions pass
- `docs/remediation/qa-agent-remediation-log.md`

**Regression suite required:**

1. T125 spy-backend secret-boundary tests.
2. T126 direct/indirect authorization tests for pending, denied and approved.
3. T127 `.qa_sessions` absence plus US-11/ReAct preservation tests.
4. T128 concrete backend-contract and enum mapping/error tests.
5. T129 Typer top-level and installed-entry-point CLI tests.
6. T130 subprocess return-code matrices for tests and coverage.
7. Related contract/integration tests.
8. Full `python -m pytest`.
9. `python -m pip check`.
10. Any validation commands already configured by the repository.
11. `/speckit.analyze` after task evidence/completion updates.
12. `git diff --check` and final `git status`.

**Acceptance evidence:** T125–T130 focused and related tests PASS; full suite has
zero failures; `pip check` reports no broken requirements; CLI E2E is PASS or
truthfully UNAVAILABLE; `/speckit.analyze` passes after canonical task updates;
diff check passes; the remediation log records exact commands/results; no
source outside T125–T130 scope or backlog feature I01–I16 was implemented.

**Dependencies:** T125 → T126 → T127 → P0 checkpoint; then T128 → T129 → T130 →
P1 checkpoint; T131 last. Any unresolved P0 blocker stops P1.

**Risk:** Medium. A green legacy suite alone is insufficient because it already
passes with the verified gaps. Closure depends on the new focused regressions.

## Traceability Matrix

| Task | Gap     | FR/SC/Principle                            | Plan/Contract                          | Code Area                                              | Regression Test                                              | Acceptance Evidence                                                                      |
| ---- | ------- | ------------------------------------------ | -------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| T125 | G1      | FR-021; SC-008; XI                         | LLM contract safe contexts             | `agent/loop.py`, `security/redactor.py`                | Recording backend for one-pass/ReAct inputs                  | Zero raw protected values in all recorded external-backend arguments                     |
| T126 | G2/G3   | FR-012/015/016/025/030; SC-004/011; IV/V   | Agent authorization and tool contracts | `agent/loop.py`, `run_tests.py`, `analyze_coverage.py` | Pending/denied/approved matrices including indirect analysis | 0 subprocess calls pending/denied; exactly 1 allowed after approval                      |
| T127 | G6/G7   | XII/XIV; approved scope correction         | Plan `Storage: N/A`, US-12 deferred    | CLI, conversational/session/task modules               | Temp-cwd no-persistence test plus US-11 suite                | No `.qa_sessions` or active persistence; ReAct behavior remains green                    |
| T128 | G5      | FR-017/019/028/029; SC-013; VII/IX         | LLM and generate-test-case contracts   | `tools/generate_test_cases.py`                         | Concrete contract backend, error and enum tests              | Two-argument call yields validated cases; failures explicit; canonical output types      |
| T129 | G8      | FR-001/002/050                             | Agent CLI contract and quickstart      | `cli/main.py`, entry point                             | Typer runner and installed console-script smoke              | Approved flags work top-level without `main`; deferred chat absent                       |
| T130 | G9      | FR-013/017/018/019/031; SC-005/014; VII/IX | Test/coverage tool contracts           | `run_tests.py`, `analyze_coverage.py`                  | Return-code/output state matrices                            | Each execution/failure/no-execution state is unambiguous and contract-valid              |
| T131 | Closure | III/VII/IX/XIII/XIV and all above          | Canonical tasks and verification gate  | Tests, tasks evidence, remediation log                 | Focused + related + full suite + pip/CLI/SDD checks          | Results classified PASS/FAIL/SKIPPED/UNAVAILABLE with no unresolved P0/P1 Done condition |
