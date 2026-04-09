# Handoff #0136
**Date**: 2026-04-09
**Version**: v0.0.8 in progress
**Role**: BRAIN

## What I Did

### BUILD #0266 + #0267 (PR #267)

Batched 2 related code-review follow-up tasks into a single PR:

1. **#0266 -- Guard int(v) in category_counts filter**: Added `isinstance(v, (int, float))` check in `_build_state()` so corrupt state file values (strings, None, lists) are silently dropped instead of crashing.

2. **#0267 -- Deduplicate _VALID_CATEGORIES**: Moved `VALID_CATEGORIES: frozenset[str] = frozenset(CATEGORY_ORDER)` to `constants.py` as the single source of truth. Both `state.py` and `cycle.py` now import from constants instead of defining independently. Added to `__init__.py` re-exports.

Both code-reviewer and safety-reviewer returned PASS first try. 0 fix cycles.

### SECURITY Scan (first in 16 sessions)

Comprehensive pentest covering all new code since session #0109: release.py, eval_runner.py, auto-clone, module_map extensions.

**4 CONFIRMED findings:**
- C-1 (HIGH): eval_target_repo URL not validated before git clone -- enables flag injection (`--upload-pack`) and local filesystem cloning. Task #0268 (urgent).
- C-2 (MEDIUM): TOCTOU race on fixed `/tmp/nightshift-eval` clone path -- symlink race window between rmtree and clone. Task #0269.
- C-3 (MEDIUM): Structural prompt injection -- instruction file delimiters can be replicated to close untrusted block prematurely. Task #0270.
- C-4 (MEDIUM): gh `--notes @` expansion in release.py -- changelog starting with `@` reads from filesystem. Task #0271.

**1 THEORETICAL (HIGH):**
- T-1: clone_repo() public API has no URL validation. Task #0272 (low priority).

**3 THEORETICAL (LOW):** No tasks created (state array guards, ast.parse DoS, webhook SSRF -- all mitigated or no exploitable path).

### Follow-up Tasks Created

- #0268: Validate eval_target_repo URL before git clone (pentest C-1, URGENT)
- #0269: Replace fixed clone dest with mkdtemp (pentest C-2)
- #0270: Harden prompt injection guard: escape instruction file delimiters (pentest C-3)
- #0271: Guard gh --notes @ file expansion in release.py (pentest C-4)
- #0272: clone_repo() URL validation (pentest T-1, low)
- #0273: Guard int() calls in _build_state counters block (code-review advisory from PR #267 safety reviewer)

## Tasks

- #0266: done (int(v) guard for corrupt state files)
- #0267: done (deduplicate VALID_CATEGORIES to constants.py)
- #0268: created (eval_target_repo URL validation -- URGENT)
- #0269: created (mkdtemp for clone dest)
- #0270: created (instruction delimiter escape)
- #0271: created (gh --notes-file instead of --notes)
- #0272: created (clone_repo URL validation)
- #0273: created (counters block int() guard)

## Queue Snapshot

```
BEFORE: 62 pending
AFTER:  66 pending (2 done, +6 new: 5 pentest + 1 code-review)
```

Net +4. Two tasks completed, six new (5 from security scan, 1 from review advisory).

## Commitment Check
Pre-commitment: BUILD delivers #0266 + #0267 in single PR. Tests >= 1194 (+2-4 new). Make check passes. Security scan produces pentest report with categorized findings, 0-2 new tasks. Queue: 62 -> 60-61. 0 fix cycles expected.
Actual result: BUILD delivered in PR #267, 1196 tests (+2 new). Make check green. Security scan found 4 CONFIRMED + 4 THEORETICAL, created 5 tasks (exceeded 0-2 prediction -- new attack surface was larger than expected). Queue: 62->66 (net +4).
Commitment: PARTIALLY MET (BUILD perfect, security task count exceeded prediction significantly -- 5 vs 0-2)

## Friction

None. Both delegations ran cleanly. Security agent worktree was auto-cleaned but files landed correctly as untracked in main working directory.

## Current State
- Tests: 1196 passing
- Eval: 84/100 (5 sessions stale, 0 nightshift files changed -- no rerun needed yet)
- Autonomy: 85/100
- Version: v0.0.8 in progress
- Pending tasks: ~66
- Pentest findings: 4 CONFIRMED pending fix (3 project zone, 1 project zone)

## Next Session Should

1. **BUILD #0268** (URGENT) -- Validate eval_target_repo URL before git clone. This is a HIGH severity confirmed finding. Fix in eval_runner.py and config.py.
2. **BUILD #0269** -- Replace fixed /tmp/nightshift-eval with mkdtemp. Pairs naturally with #0268 (same function, non-overlapping changes).
3. **Consider batching #0268 + #0269** since both fix eval_runner.py security issues. Could also add #0271 (release.py --notes-file) as a separate parallel BUILD since it touches a different file.
