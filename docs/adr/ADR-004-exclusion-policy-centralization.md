# ADR-004: Centralize directory/path exclusion policy (I07)

- Status: Accepted (retroactive — decision was made and implemented by
  Person 4 in `work/person-4`; this ADR formalizes it after the fact,
  per the final whole-branch review's I-2 finding)
- Date decided: 2026-08-20 (Person 4, I07). ADR recorded: 2026-08-21.
- Owner: Person 4 (`work/person-4`)
- Backlog item: I07 (TECHNICAL DEBT — centralize ignore/exclusion policy),
  `docs/improvements/qa-agent-improvement-backlog.md`
- Related: `src/qa_agent/tools/exclusion_policy.py`,
  `tests/unit/test_discovery_exclusion_characterization.py`,
  `docs/improvements/person-4-result.md`
- Constitution principles engaged: IV (least privilege), X (no needless
  duplication), XII (incremental evolution — widen, never narrow, without
  fresh justification)

## Context

Before I07, the set of "noise" directory names to exclude from discovery
(VCS metadata, build artifacts, dependency directories, IDE configuration)
was defined independently in four places, using two different mechanisms:

| File | Constant | Mechanism | Set |
|---|---|---|---|
| `allowlist.py` | `_EXCLUSIONES_DEFECTO` | gitwildmatch patterns (`pathspec`) against the full relative path | `.git/`, `__pycache__/`, `*.pyc`, `.venv/`, `node_modules/`, `dist/`, `build/`, `.pytest_cache/`, `.env` |
| `explore.py` | `DIRECTORIOS_IGNORADOS` | directory-name equality during tree walk | `.git`, `.vs`, `bin`, `obj`, `packages`, `node_modules` |
| `generate_test_cases.py` | `_DIRECTORIOS_IGNORADOS` | directory-name membership over path parts | `.git`, `.vs`, `.idea`, `.vscode`, `__pycache__`, `.venv`, `venv`, `node_modules`, `bin`, `obj`, `packages` |
| `agent/loop.py` (two inline literals) | `ignorados = {...}` | directory-name equality | `.git`, `.vs`, `bin`, `obj`, `packages`, `node_modules` (identical to `explore.py`'s pre-I07 set) |

`locate.py`/`search.py` had no set of their own — they reused `explore.py`'s
`DIRECTORIOS_IGNORADOS` transitively, plus each tool's own `Allowlist`
instance as a secondary per-file check.

Four independently-maintained copies of the same intent is a Constitution X
violation (needless duplication) and a latent correctness risk: nothing
enforced that the copies stayed in sync, and by the time I07 started, they
had already silently drifted (see Findings below).

## Method

Before writing any centralization code,
`tests/unit/test_discovery_exclusion_characterization.py` was added: one
fixture tree containing every "noise" directory listed above plus real
code, measuring — against the actual pre-refactor source, not assumed —
exactly what each of `explore`/`locate`/`search`/`generate_test_cases`/
`Allowlist.contiene()` included or excluded. This surfaced two genuine,
previously-undocumented discrepancies before any centralization code was
written.

## Findings (drift discovered while centralizing)

1. **Directory-name set.** `explore.py` (and `locate`/`search`, which
   reused its set) excluded only `{.git, .vs, bin, obj, packages,
   node_modules}` by directory name, while `generate_test_cases.py`
   additionally excluded `{__pycache__, .venv, venv, .idea, .vscode}`.
   `locate`/`search` partially compensated via their secondary `Allowlist`
   per-file check (which already excluded `__pycache__`/`.venv` through
   its own patterns), but not bare `venv`, `.idea`, or `.vscode` — those
   leaked through both `explore` and `locate`/`search`.
2. **Allowlist patterns.** `Allowlist`'s default gitwildmatch patterns did
   not include `bin/obj/packages/.vs/.idea/.vscode` or bare `venv/`, even
   though the directory-name walk in `explore`/`generate_test_cases`
   already pruned several of those names. Because `Allowlist.contiene()`
   is the actual FR-025 authorization check and can be queried directly
   with an arbitrary path — not only through a tree walk that happens to
   prune first — this was a real least-privilege gap (Constitution IV): a
   path explicitly inside one of those directories was reported as
   "authorized" if asked directly.

Not a discrepancy, and explicitly out of scope: `dist/`, `build/`,
`.pytest_cache/` were never duplicated in any directory-name set — they
existed only as `Allowlist` patterns from the start. `explore.py` does not
consult `Allowlist` per descendant during its tree walk (only for the root
path once), so it still does not prune `dist/`/`build/`/`.pytest_cache/`
during traversal. Fixing that would require changing `explore.py`'s
traversal algorithm, not just centralizing constants — flagged as a
separately-scoped follow-up, not addressed here.

## Decision

Create `src/qa_agent/tools/exclusion_policy.py` as the single source of
truth, with two constants for the two distinct mechanisms already in use
(a directory-name-equality set is not interchangeable with a gitwildmatch
pattern set — they answer different questions: "is this directory name
noise at any depth" vs. "does this specific path match an authorization
exclusion pattern"):

- `NOMBRES_DIRECTORIO_EXCLUIDOS: frozenset[str]` — directory-name set,
  consumed by `explore`, `locate`, `search`, `generate_test_cases`, and
  (per the I-3 follow-up fix, see below) `agent/loop.py`.
- `PATRONES_EXCLUSION_ALLOWLIST: tuple[str, ...]` — gitwildmatch patterns,
  consumed by `Allowlist`.
- `es_directorio_excluido(nombre)` — helper wrapping the frozenset
  membership check, for callers that only have a bare directory name.

Both findings above were resolved by taking the **union** of the
divergent sets — protection is only ever widened, never narrowed. This
was verified safe against the full existing test suite (no test depended
on the narrower behavior) plus the new characterization coverage before
the change was made.

`explore.py` keeps re-exporting `DIRECTORIOS_IGNORADOS` as an alias for
backward compatibility with any other importer; `locate.py`/`search.py`
were switched to import the directory-name set directly from
`exclusion_policy.py` instead of transitively through `explore.py`.

`agent/loop.py`'s two inline exclusion literals were explicitly **not**
touched by this decision — `loop.py` was off-limits to Person 4 this wave
(owned by Person 1's concurrent I01/I02 work) — and were deliberately
deferred to a future integration window, carried forward as a known
follow-up in `docs/improvements/person-4-result.md`. That follow-up was
closed in the final-review fix wave (I-3): both `loop.py` helpers now call
`es_directorio_excluido()` from this module, so `loop.py` uses the exact
same policy as the other discovery tools.

## Alternatives considered

- **Leave the four copies as-is, just document the divergence.** Rejected:
  documentation without a single source of truth does not stop the next
  edit to any one copy from silently reintroducing drift; the two findings
  above are proof the copies had already diverged undetected.
- **Standardize on one mechanism only (e.g. make everything a gitwildmatch
  pattern, drop the plain directory-name set).** Rejected: the two
  mechanisms solve genuinely different problems for genuinely different
  callers — tree-walk pruning wants a cheap name-equality check at every
  node visited, while `Allowlist.contiene()` needs to answer "is this
  arbitrary path authorized" without walking a tree at all. Collapsing to
  one mechanism would either slow down the tree walk (gitwildmatch match
  per node instead of a frozenset lookup) or weaken `Allowlist` (name-only
  equality can't express `*.pyc`-style glob patterns it already relies on).
- **Narrow every tool down to the smallest common set instead of taking
  the union.** Rejected: this is the "reduce protection to reconcile"
  direction, which cuts against Constitution IV (least privilege in the
  authorization direction) and would actively un-exclude directories some
  tools already correctly excluded (e.g. `generate_test_cases` would have
  started showing `__pycache__`/`.venv` content again). The union direction
  is the only one that cannot make any tool's authorization surface wider
  than it already effectively was in the widest existing tool.

## Consequences

- One source of truth for both mechanisms; the four previously-independent
  copies collapse to one module plus thin re-exports for backward
  compatibility.
- Real, user-visible behavior change: projects with a legitimately-named
  `bin/`, `obj/`, `packages/`, `.vs/`, `.idea/`, `.vscode/`, or bare `venv/`
  directory that is not actually a build/VCS/dependency artifact will now
  have that content silently absent from `explore`/`locate`/`search`/
  `generate_test_cases` output and from `Allowlist.contiene()`
  authorization, where some tools previously showed/authorized it. This is
  the intended direction of the ruling (never narrow protection) but is
  called out explicitly since it affects every discovery tool's default
  behavior project-wide.
- No new dependency; `pip check` stays clean.
- `dist/`/`build/`/`.pytest_cache/` remain un-pruned by `explore.py`'s
  traversal (pre-existing gap, out of scope here — see Findings).

## Verification

- `tests/unit/test_discovery_exclusion_characterization.py`: 10 new tests
  at introduction, all green against pre-refactor source, then updated in
  place (only the two assertions describing the resolved discrepancies
  change) to assert the post-ruling behavior.
- Full suite: 364 passed (354 baseline + 10 new), 0 failed.
- `python -m pip check`: clean.
- `agent/loop.py` / `agent/router.py` confirmed untouched by this decision
  at the time (`git diff a69d315 -- loop.py router.py` empty); wired in
  later by the I-3 follow-up fix, with its own test coverage added to the
  same characterization file.
