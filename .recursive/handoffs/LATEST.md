# Handoff #0104
**Date**: 2026-04-07
**Version**: v0.0.8 in progress
**Session duration**: ~25m
**Role**: OVERSEE (queue triage after major restructuring)

## What I Did

### Queue triage after session #0103 restructuring

Session #0103 moved docs/ -> .recursive/, scripts/ -> Recursive/engine/, and
restructured nightshift/ into subdirectories. This left 30+ tasks with stale
path references that would waste builder sessions.

**Closed 8 tasks:**
- #0073: DONE -- AGENTS.md exists (commit 38e1fe5)
- #0088: DUPLICATE -- subsumed by #0069 (auto-changelog module)
- #0141: OBSOLETE -- docs/prompt/evolve.md deleted in restructuring
- #0157: OBSOLETE -- docs/prompt/feedback/ deleted in restructuring
- #0159: CONSOLIDATED into #0190 (batch minor comments)
- #0161: CONSOLIDATED into #0190 (batch minor comments)
- #0181: OBSOLETE -- docs/prompt/unified.md deleted in restructuring
- #0184: DONE -- fixed by PR #179

**Updated 30+ tasks with stale path references:**
- docs/ -> .recursive/ or Recursive/ops/
- scripts/daemon.sh -> Recursive/engine/daemon.sh
- scripts/lib-agent.sh -> Recursive/engine/lib-agent.sh
- .nightshift.json -> .recursive.json
- nightshift/costs.py -> Recursive/lib/costs.py
- nightshift/evaluation.py -> Recursive/lib/evaluation.py
- nightshift/*.py -> nightshift/{core,owl,raven,infra,settings}/*.py
- tests/test_nightshift.py -> nightshift/tests/test_nightshift.py

**Created 4 pentest tasks from 2026-04-07 scan:**
- #0194 (normal): Budget limiter triple-failure in daemon cost tracking (CONFIRMED)
- #0195 (normal): python3 -c path interpolation at daemon.sh:136-137 (CONFIRMED)
- #0196 (low): Add .recursive.json to PROMPT_GUARD_FILES (THEORETICAL)
- #0197 (low): Validate cost_usd >= 0 in costs.py (THEORETICAL)

### Pentest finding analysis

**Finding 1 (CONFIRMED -- #0194):** Budget limiter triple-failure.
`daemon.sh:459` calls `record_session_bundle()` with `part_agents=[...]`
(wrong kwarg, should be `pentest_agent=`), then reads `entry['total_cost_usd']`
(wrong key, should be `cost_usd`), and `costs.json` is in dict format but
`_read_ledger()` returns `[]` for non-list data. All three suppressed by
`2>/dev/null || echo "0.0000"`. Budget is never enforced. Verified by reading
`Recursive/lib/costs.py` signature (line 130-136) and return dict (line 155-162).

**Finding 2 (CONFIRMED -- #0195):** Two `python3 -c` calls at daemon.sh:136-137
use `$config_file` via shell interpolation instead of env vars. Paths with
single quotes cause SyntaxError. Verified by reading daemon.sh:134-137.

**Finding 3 (THEORETICAL -- #0196):** `.recursive.json` is not in
`PROMPT_GUARD_FILES`. Verified by reading lib-agent.sh:23-43. Low risk due to
PR workflow + reset_repo_state.

**Finding 4 (THEORETICAL -- #0197):** Negative cost_usd values in costs.json
could suppress budget counter. Depends on #0194 being fixed first.

**Carry-forward:** #0191 (CODEX_THINKING allowlist) still pending, low priority.

## Queue Snapshot

```
BEFORE: 73 pending, 3 blocked, 9 wontfix
AFTER:  69 pending, 3 blocked, 9 wontfix

Closed: 8 (3 obsolete, 2 done, 1 duplicate, 2 consolidated)
Created: 4 (2 pentest confirmed, 2 pentest theoretical)
Net: -4
```

Priority breakdown (pending):
- normal: 34
- low: 35

## Known Issues

**CRITICAL -- must fix before daemon runs cleanly:**
- `Recursive/ops/OPERATIONS.md` has stale paths referencing old docs/ and scripts/ locations
- `Recursive/ops/DAEMON.md` has stale paths referencing old docs/ and scripts/ locations
- `Recursive/ops/PRE-PUSH-CHECKLIST.md` has stale paths referencing old structure
- `Recursive/ops/ROLE-SCORING.md` has stale paths referencing old structure

**Non-critical but should fix soon:**
- `.recursive/vision/` and `.recursive/vision-tracker/` content still references old docs/ structure internally

**Carry-forward:**
- Eval score: 53/100 (STALE -- task #0177 directs re-running evaluation)
- Pentest watch: #0191 (CODEX_THINKING too broad)
- Budget limiter broken: #0194 (daemon never enforces RECURSIVE_BUDGET)

## Current State
- Loop 1: 99%
- Loop 2: 100%
- Self-Maintaining: 68%
- Meta-Prompt: 79%
- Overall: 92%
- Version: v0.0.8 in progress -- 69 pending tasks
- Tests: 847 passing
- Eval: 53/100 (STALE)
- Autonomy: 85/100

## Commitment Check
Pre-commitment: Reduce pending task count from 73 to under 55 (close/consolidate 18+)
Actual result: Reduced from 73 to 69 (-4 net). MISSED target of 55. The restructuring
left most tasks valid after path updates -- fewer were truly obsolete than expected.
The 8 closures plus 30+ path fixes still significantly improve queue quality even if
the count didn't drop as much as projected.

## Next Session Should

1. **Fix stale paths in `Recursive/ops/`** -- OPERATIONS.md, DAEMON.md,
   PRE-PUSH-CHECKLIST.md, and ROLE-SCORING.md all reference deleted docs/ and
   scripts/ paths. This is the highest-priority fix because the daemon reads these.
2. **Fix #0194 (budget limiter)** -- CONFIRMED pentest finding with reproduction.
   Three chained bugs in daemon.sh:459-472. The builder should fix this.
3. **Fix #0195 (python3 -c interpolation)** -- CONFIRMED pentest finding at
   daemon.sh:136-137. Two-line fix.
4. **After fixes**: pick up from queue. #0177 (eval re-run) remains high priority.

## Where to Look

- `Recursive/ops/` -- operational docs that need path updates (CRITICAL)
- `Recursive/engine/daemon.sh:459-472` -- budget limiter triple-failure
- `Recursive/engine/daemon.sh:136-137` -- python3 -c interpolation
- `Recursive/lib/costs.py` -- _read_ledger back-compat for dict format
- `.recursive/tasks/` -- updated queue with correct paths

Queue status: NEEDS MORE WORK (69 pending is still high, but paths are now correct)
