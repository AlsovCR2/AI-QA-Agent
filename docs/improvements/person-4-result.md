# Person 4 — I07/I11/I13 result

Branch: `work/person-4`, created from HEAD (`a69d315`) in the isolated
worktree. Does not touch `main`. Nothing pushed.

## Items

- **I07** — TECHNICAL DEBT — centralize ignore/exclusion policy — **IMPLEMENTED**.
- **I11** — POST-MVP — structured language/symbol discovery — **DESIGN ONLY**.
- **I13** — FUTURE FEATURE — next ecosystem (JavaScript/TypeScript) — **DESIGN ONLY**.

## Status

DONE.

## Implementation completed (I07)

### Inventory of duplicated definitions (before)

| File | Constant | Mechanism | Set |
|---|---|---|---|
| `allowlist.py` | `_EXCLUSIONES_DEFECTO` | gitwildmatch patterns (`pathspec`), matched against the full relative path | `.git/`, `__pycache__/`, `*.pyc`, `.venv/`, `node_modules/`, `dist/`, `build/`, `.pytest_cache/`, `.env` |
| `explore.py` | `DIRECTORIOS_IGNORADOS` | directory-name equality during tree walk | `.git`, `.vs`, `bin`, `obj`, `packages`, `node_modules` |
| `generate_test_cases.py` | `_DIRECTORIOS_IGNORADOS` | directory-name membership over path parts | `.git`, `.vs`, `.idea`, `.vscode`, `__pycache__`, `.venv`, `venv`, `node_modules`, `bin`, `obj`, `packages` |
| `agent/loop.py` (read-only reference, **not edited**) | two inline `ignorados = {...}` literals | directory-name equality | `.git`, `.vs`, `bin`, `obj`, `packages`, `node_modules` (identical to `explore.py`'s pre-I07 set) |
| `locate.py` / `search.py` | (none of their own) | reused `explore.py`'s `DIRECTORIOS_IGNORADOS` via import, plus each tool's own `Allowlist` instance for a secondary per-file check | inherited |

### Characterization step (before centralizing)

`tests/unit/test_discovery_exclusion_characterization.py` (commit
`7c84c4b`) builds one fixture tree with every "noise" directory listed
above plus real code, and measures — against the actual pre-refactor
source, not assumed — exactly what each of `explore`/`locate`/`search`/
`generate_test_cases`/`Allowlist.contiene()` included or excluded. This
surfaced two genuine, previously-undocumented discrepancies (below) before
any centralization code was written.

### Centralized module

`src/qa_agent/tools/exclusion_policy.py` (new) exposes:

- `NOMBRES_DIRECTORIO_EXCLUIDOS: frozenset[str]` — directory-name set,
  consumed by `explore.py`, `locate.py`, `search.py`,
  `generate_test_cases.py`.
- `PATRONES_EXCLUSION_ALLOWLIST: tuple[str, ...]` — gitwildmatch patterns,
  consumed by `allowlist.py`.
- Helper functions `es_directorio_excluido()` /
  `contiene_directorio_excluido()`.

`locate.py`/`search.py` now import the directory-name set directly from
`exclusion_policy.py` (previously they imported it transitively through
`explore.py`); `explore.py` still re-exports `DIRECTORIOS_IGNORADOS` as an
alias for backward compatibility with any other importer.

## Design completed (I11, I13)

- `docs/proposals/I11-structured-discovery.md` — language-detection and
  symbol-extraction `Protocol` interfaces, a fixed three-step deterministic
  fallback order (native AST → deterministic regex heuristic → explicit
  `no_soportado`), an explicit unsupported-language state distinct from
  "supported, zero matches," a comparison of AST/LSP/structured-index
  options with confidence tiers and dependency footprints per option, and
  failure semantics (parse error, oversized file, timeout, unexpected
  exception) modeled on patterns already in this codebase
  (`search.py`'s truncation-with-note, `run_tests.py`'s bounded subprocess
  timeout). No AST/LSP/index infrastructure installed; no extraction code
  written.
- `docs/proposals/I13-next-ecosystem.md` — selects JavaScript/TypeScript
  as the single next-increment candidate (over Go/Rust), with justification
  tied to closing two currently-unsupported extensions in one increment,
  stable JSON test-report modes across Jest/Vitest/Mocha, and a
  standardized Istanbul coverage-summary format. Defines detection method
  (marker file `package.json`, following the existing `loop.py` marker
  convention for .NET/Maven/Gradle), runner selection, an illustrative
  command allowlist, a result-parser mapping onto the existing
  `ResultadoDeHerramienta` shape, coverage source, fixture strategy
  (parser-only, no real `npx`/`node_modules` invocation in CI — mirroring
  the existing .NET/Maven/Gradle precedent), security considerations (most
  notably that `npx` can implicitly fetch and execute unpinned code, a real
  divergence from every currently-supported ecosystem, flagged as an open
  question a future Plan must resolve before adoption), and explicit
  unsupported-state behavior. No implementation, no new dependencies, no
  new code.

## Files changed

- `src/qa_agent/tools/exclusion_policy.py` (new) — centralized policy.
- `src/qa_agent/tools/allowlist.py` — `_EXCLUSIONES_DEFECTO` now sources
  from `exclusion_policy.PATRONES_EXCLUSION_ALLOWLIST`.
- `src/qa_agent/tools/explore.py` — `DIRECTORIOS_IGNORADOS` now imported
  (re-exported) from `exclusion_policy.NOMBRES_DIRECTORIO_EXCLUIDOS`.
- `src/qa_agent/tools/locate.py` — imports the directory-name set directly
  from `exclusion_policy.py` instead of via `explore.py`.
- `src/qa_agent/tools/search.py` — same as `locate.py`.
- `src/qa_agent/tools/generate_test_cases.py` — `_DIRECTORIOS_IGNORADOS`
  now imported (re-exported) from `exclusion_policy.py`.
- `tests/unit/test_discovery_exclusion_characterization.py` (new) —
  characterization fixtures; updated in the second commit so the two
  assertions that documented the resolved discrepancies now assert the new
  (widened) behavior, with every other assertion unchanged.
- `docs/proposals/I11-structured-discovery.md` (new).
- `docs/proposals/I13-next-ecosystem.md` (new).
- `docs/improvements/person-4-result.md` (this file, new).

`src/qa_agent/agent/loop.py` and `src/qa_agent/agent/router.py` were
**not modified** (verified with
`git diff a69d315 -- src/qa_agent/agent/loop.py src/qa_agent/agent/router.py`
→ empty). `loop.py`'s two inline `ignorados = {...}` literals are now
stale duplicates of `exclusion_policy.NOMBRES_DIRECTORIO_EXCLUIDOS` and
should be wired to it in a future integration window once Person 1
completes I01/I02, per the task's explicit deferral instruction.

## Tests

- Two small commits, both green:
  1. `7c84c4b` `test: add discovery exclusion characterization fixtures` —
     10 new tests, all passing against the pre-refactor source.
  2. `9438354` `refactor: centralize repository exclusions` — no new
     tests; the two characterization tests describing the resolved
     discrepancies are updated in place to assert the post-ruling
     behavior.
- Full suite: `364 passed`, 0 failed (354 baseline + 10 new
  characterization tests).
- `python -m pip check`: clean.

### Environment note (important for anyone re-verifying this branch)

The global Python environment's editable install of `qa-agent` was found
to point at an **unrelated checkout**
(`C:\Users\AbrahamVillalobosUga\qa-agent`, a separate git repository with
its own `origin/main`), not at this worktree. Running plain
`python -m pytest` from this worktree silently imports `qa_agent` from
that other checkout — the test *files* collected are this worktree's, but
the *source* exercised is not, so pass/fail counts from a bare
`python -m pytest` here are not meaningful evidence for this branch's
changes. All verification in this document was done with
`PYTHONPATH=<this worktree>/src` prepended, which was confirmed (via a
throwaway diagnostic test, since discarded) to correctly resolve
`qa_agent` to this worktree's `src/`. No global site-packages state was
modified to fix this — the fix is scoped to how tests are invoked, not to
the shared environment. Anyone continuing this branch, or the other five
owners verifying their own worktrees, should confirm which `qa_agent` a
bare `pytest` run actually imports (`python -c "import qa_agent;
print(qa_agent.__file__)"`) before trusting its result.

## Decisions / rulings

Two genuine inconsistencies were found while centralizing (both resolved
by taking the **union** — protection is only ever widened, never
narrowed — and both are asserted by name in
`test_discovery_exclusion_characterization.py`):

1. **Directory-name set (ruling 1).** Before I07, `explore.py` (and
   `locate.py`/`search.py`, which reused its set) excluded only
   `{.git, .vs, bin, obj, packages, node_modules}` by directory name,
   while `generate_test_cases.py` additionally excluded
   `{__pycache__, .venv, venv, .idea, .vscode}`. `locate`/`search`
   partially compensated for this via their secondary `Allowlist`
   per-file check (which already excluded `__pycache__`/`.venv` through
   its own patterns), but not bare `venv`, `.idea`, or `.vscode` — those
   leaked through both `explore` and `locate`/`search` before this change.
   **Resolution**: `NOMBRES_DIRECTORIO_EXCLUIDOS` is the union of both
   sets; `explore`/`locate`/`search`/`generate_test_cases` all now share
   it. Verified against the full test suite (no test depended on the
   narrower behavior) before making the change.
2. **Allowlist patterns (ruling 2).** `Allowlist`'s default gitwildmatch
   patterns did not include `bin/obj/packages/.vs/.idea/.vscode` or
   `venv/` (bare), even though the directory-name walk in
   `explore`/`generate_test_cases` already pruned several of those names.
   Because `Allowlist.contiene()` is the actual FR-025 authorization
   check and can be queried directly with an arbitrary path — not only
   through a tree walk that happens to prune first — this was a real
   least-privilege gap (Constitution IV): a path explicitly inside one of
   those directories was reported as "authorized" if asked directly.
   **Resolution**: `PATRONES_EXCLUSION_ALLOWLIST` is the union, adding
   `bin/`, `obj/`, `packages/`, `.vs/`, `.idea/`, `.vscode/`, `venv/`
   to the pre-existing pattern set.

**Not changed, documented as a known preexisting gap (out of scope for
I07):** `dist/`, `build/`, `.pytest_cache/` were never duplicated in any
directory-name set — they existed only as `Allowlist` patterns from the
start, so there is no "duplicate to reconcile." `explore.py` does not
consult `Allowlist` per descendant during its tree walk (only for the root
path once), so it still does not prune `dist/`/`build/`/`.pytest_cache/`
during traversal, unchanged from before I07. Fixing this would require
changing `explore.py`'s traversal algorithm, not just centralizing
constants, and was judged out of scope for a duplication-centralization
task; flagged here for a future, separately-scoped change.

## Dependencies

None added, none removed. `pip check` clean.

## Remaining SDD gate

I07 is TECHNICAL DEBT remediation with `Requires future Plan/ADR: DEPENDS`
per the backlog; this centralization is a same-behavior-plus-two-documented-
widening-rulings refactor, verified against the full existing test suite
plus new characterization coverage, and is considered complete for this
wave. Wiring `agent/loop.py`'s two inline exclusion literals to the new
centralized module remains explicitly deferred to a future integration
window (post I01/I02, owned by Person 1) per this task's instructions —
this is the one known follow-up carried forward, not a gap in I07 itself.

I11 and I13 are both explicitly DESIGN ONLY per their backlog status
(POST-MVP / FUTURE FEATURE, both `Requires future Spec: YES` and
`Requires future Plan/ADR: YES`); neither proposal grants implementation
authority. Concrete adoption of either requires its own Spec and Plan/ADR
cycle.

## Risks

- The directory-name and Allowlist-pattern widening (rulings 1 and 2)
  changes discovery-tool *output* for projects that happen to contain a
  legitimately-named `bin/`, `obj/`, `packages/`, `.vs/`, `.idea/`,
  `.vscode/`, or bare `venv/` directory that is not actually a build/VCS/
  dependency artifact (e.g. a Python `bin/` script folder, or a directory
  a user genuinely named `venv` for something other than a virtualenv).
  Such content will now be silently absent from `explore`/`locate`/
  `search`/`generate_test_cases` output and from `Allowlist.contiene()`
  authorization, where it previously was not. This is the intended
  direction of the ruling (never narrow protection) but is a real,
  user-visible behavior change worth calling out explicitly to the other
  five owners and to whoever reviews this branch, since it affects every
  discovery tool's default behavior project-wide.
- `agent/loop.py`'s two inline exclusion literals are now stale relative to
  the centralized policy (they still reflect the pre-I07, narrower set).
  This is intentional (loop.py is off-limits this wave) but means
  `loop.py`-driven layer/directory heuristics and the discovery tools are
  now inconsistent with each other until the deferred integration happens.
- The environment discrepancy described above (stray editable install)
  could cause a future verifier to see a misleadingly-green or
  misleadingly-red suite if they run bare `python -m pytest` without
  setting `PYTHONPATH` to this worktree's `src/`. Flagged prominently in
  §Tests above so it is not missed.
