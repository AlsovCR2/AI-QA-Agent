# AI-QA-Agent Remediation Log

Starting branch: main

Starting HEAD: aacffa89d9e3b5241cbfca1a892fa6a76c7a98cd

Scope: canonical T125–T131 only. This log records implementation evidence and
does not introduce requirements.

## T125

Gap: G1 — raw protected values could reach an external LLM before redaction.

Status: FIXED

Authority: FR-021; SC-008; Constitution XI; canonical T125.

Files changed:

- src/qa_agent/security/redactor.py
- src/qa_agent/agent/loop.py
- tests/unit/test_remediation_security.py

Regression test: a concrete recording backend captures all one-pass and ReAct
arguments and asserts that user, context and tool-observation secrets are absent
while redaction markers are present.

Before: 2 failed; raw protected values appeared in recorded backend arguments.

After: 22 passed across remediation, redactor and authorization/redaction tests.

Commands executed:

- python -m pytest tests/unit/test_remediation_security.py tests/unit/test_redactor.py tests/unit/test_agent_autorizacion_redaccion.py -q

Results: PASS — 22 passed.

Evidence: all external-backend inputs exercised by the Agent are redacted copies;
the original deterministic tool result remains available internally.

Remaining limitations: generation-tool backend integration is repaired in T128
and must preserve this same boundary.

## T126

Gap: G2/G3 — indirect test execution and coverage bypassed authorization.

Status: FIXED

Authority: FR-012/015/016/025/030; SC-004/011; Constitution IV/V; canonical T126.

Files changed:

- src/qa_agent/agent/loop.py
- src/qa_agent/tools/analyze_coverage.py
- tests/unit/test_remediation_security.py
- tests/unit/test_agent_qa_integration.py

Regression test: pending/denied/approved matrices patch subprocess.run for
coverage and for the indirect run_tests → analyze_test_results path.

Before: 4 failed and 2 passed; pending and denied each called a subprocess once.

After: 6 passed; pending/denied call count is zero and approved call count is one.

Commands executed:

- python -m pytest tests/unit/test_remediation_security.py -k t126 -q
- related authorization/tool suite
- full P0 python -m pytest -q

Results: PASS — 6 focused, 40 related, and 332 full-suite tests passed.

Evidence: coverage declares the existing authorization boundary; one-pass
analysis inherits it only when its configured prerequisite executes run_tests.

Remaining limitations: target repositories remain trusted as approved; no
sandbox or process/network isolation is claimed.

## T127

Gap: G6/G7 — deferred persistent chat/memory/tasks were active in the MVP CLI.

Status: FIXED

Authority: Constitution XII/XIV; Plan Storage: N/A; US-12 deferred; canonical
T127. US-11 remains active.

Files changed:

- src/qa_agent/cli/main.py
- src/qa_agent/agent/session_manager.py
- tests/unit/test_remediation_security.py

Regression test: CLI help does not expose chat; constructing the historical
session manager does not create .qa_sessions; normal one-pass and ReAct use in
a temporary cwd creates no persistent directory.

Before: 2 failed and 1 passed; CLI exposed chat and construction created
.qa_sessions.

After: 3 focused tests passed; 116 related tests, including US-11/ReAct, passed.

Commands executed:

- python -m pytest tests/unit/test_remediation_security.py -k t127 -q
- related reasoning/ReAct/P0 suite
- full P0 python -m pytest -q

Results: PASS — P0 checkpoint 332 passed.

Evidence: deferred chat is no longer registered as a CLI command; default
session-manager construction is side-effect free; approved ephemeral Agent and
ReAct behavior remains green.

Remaining limitations: historical deferred modules remain internal and
unregistered to avoid an unrelated deletion/refactor.

## T128

Gap: G5.

Status: FIXED

Authority: FR-017/019/028/029; SC-013; Constitution VII/IX; canonical T128.

Files changed:

- src/qa_agent/tools/generate_test_cases.py
- tests/unit/test_tools_generate_cases.py

Regression test: concrete LLMBackend implementation verifies the two-argument
contract, canonical output enum, pre-LLM redaction and explicit backend error.

Before: 2 failed; the incompatible one-argument call yielded an empty successful
result and hid backend failure.

After: 3 focused and 13 related/contract tests passed.

Commands executed:

- python -m pytest tests/unit/test_tools_generate_cases.py -k t128 -q
- python -m pytest tests/unit/test_tools_generate_cases.py tests/contract/test_tool_contracts.py -q

Results: PASS.

Evidence: request dictionary and evidence list reach the concrete backend;
protected source values are absent; provider errors return outer ERROR.

Remaining limitations: generated cases remain LLM suggestions as approved and
are not deterministic evidence.

## T129

Gap: G8.

Status: FIXED

Authority: FR-001/002/050; canonical T129.

Files changed:

- src/qa_agent/cli/main.py (T127 prerequisite removed the deferred command)
- tests/integration/test_cli_contract.py

Regression test: in-process top-level options plus direct installed-entry-point
version smoke.

Before: Stage-1 baseline exposed main/chat command routing instead of the
documented top-level shape.

After: 5 CLI E2E tests passed and direct installed invocations exited zero.

Commands executed:

- python -m pytest tests/integration/test_cli_contract.py -q
- installed qa-agent.exe --version
- installed qa-agent.exe --ruta . --pregunta hola --demo --mostrar-historial

Results: PASS.

Evidence: all five approved flags are top-level; main/chat are not registered;
installed qa-agent 0.1.0 responds successfully.

Remaining limitations: the Scripts directory is not on this shell's PATH, so
T131 invoked the installed executable by its resolved absolute path.

## T130

Gap: G9.

Status: FIXED

Authority: FR-013/017/018/019/031; SC-005/014; Constitution VII/IX; canonical
T130.

Files changed:

- src/qa_agent/tools/run_tests.py
- src/qa_agent/tools/analyze_coverage.py
- tests/unit/test_remediation_subprocess_semantics.py

Regression test: return-code/output matrices cover success, ordinary test
failure, zero tests, contradictory output, unsupported output, spawn failure and
timeout for both tools.

Before: 7 failed and 7 passed; contradictory/non-parseable executions were
reported as successful.

After: 14 focused and 40 related tests passed.

Commands executed:

- python -m pytest tests/unit/test_remediation_subprocess_semantics.py -q
- related runner and Agent integration suite
- full P1 python -m pytest -q

Results: PASS.

Evidence: ordinary test failures remain valid executed results; zero tests are
explicit; infrastructure/unsupported/contradictory states return ERROR without
expanding the approved schemas.

Remaining limitations: richer runner metadata remains deferred to backlog I06.

## T131

Gap: final regression/evidence closure.

Status: FIXED

Authority: canonical T131 and T125–T130 authorities.

Files changed:

- specs/001-core-ai-qa-agent/tasks.md (T125–T131 state/evidence only)
- docs/remediation/qa-agent-remediation-log.md

Regression test: final focused and full suites plus dependency, installed CLI,
SDD consistency and Git checks.

Before: Stage 1 baseline 321 passed.

After: 354 passed.

Commands executed:

- final focused remediation suite
- full python -m pytest -q
- python -m pip check
- installed CLI smoke
- speckit-analyze precheck and cross-artifact analysis
- git diff --check and git status

Results:

- PASS: focused 45; full 354; pip check; installed CLI E2E; SDD analyze.
- FAIL: 0.
- SKIPPED: 0.
- UNAVAILABLE: 0 within approved remediation scope.

Evidence: canonical task evidence references and exact command results above.

Remaining limitations: target repositories are trusted for MVP. Sandbox and
untrusted-target verification are N/A and are not claimed.
