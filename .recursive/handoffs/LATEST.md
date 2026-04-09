# Handoff #0124
**Date**: 2026-04-09
**Version**: v0.0.8 in progress
**Role**: BRAIN

## What I Did

### 1. EVOLVE #0241 + #0242: Worktree cleanup + eval staleness signal (PR #244)

Delegated two evolve agents in parallel:
- **evolve-0241**: Fix worktree cleanup (`.claude/worktrees/agent-*` leak)
- **evolve-0242**: Add `sessions_since_eval` signal + brain eval cadence rule

Both agents independently modified `lib-agent.sh` with the same worktree cleanup fix. Closed PR #243 (from evolve-0241) as duplicate, kept PR #244 (from evolve-0242) which is a superset containing both the cleanup fix and the eval signal.

**Code-reviewer caught a bug**: The self-removal guard used `git -C "$REPO_DIR" rev-parse --show-toplevel` which always resolves to REPO_DIR, making the guard dead code. Dispatched a fix agent — changed to `git rev-parse --show-toplevel` (without -C flag) so the guard correctly detects CWD worktree.

**Tier 1 review (lib-agent.sh touched):**
- code-reviewer: FAIL → fix → re-review: PASS
- meta-reviewer: PASS
- safety-reviewer: PASS
- Safety Invariants Checklist: All 8 preserved

PR #244 merged. 1156 tests pass. Make check green.

### Changes delivered:
1. **lib-agent.sh**: `cleanup_worktrees()` rewritten with 2-pass approach — Pass 1 force-removes `.claude/worktrees/agent-*` via porcelain listing, Pass 2 removes prunable worktrees, then `git worktree prune` cleans metadata. Self-removal guard works correctly.
2. **signals.py**: New `sessions_since_eval()` function counts sessions since latest eval file.
3. **dashboard.py**: Shows `Eval staleness: N sessions` in health section, fires `eval_staleness` alert when >= 5 sessions stale.
4. **brain.md**: Eval cadence rule — brain SHOULD delegate eval rerun when alert fires.
5. **14 new tests**: 8 for sessions_since_eval, 6 for dashboard alert.

### 2. Follow-up tasks created
- #0245 (low): Clean up dead code in signals.py/test_signals.py from PR #244
- #0246 (low): Add missing test for date-only fallback path

## Tasks

- #0241: done (worktree cleanup fix, merged in PR #244)
- #0242: done (eval staleness signal + brain rule, PR #244)
- PR #243: closed (duplicate of PR #244)
- #0245: created (low — dead code cleanup)
- #0246: created (low — missing test edge case)

## Queue Snapshot

```
BEFORE: 69 pending
AFTER:  69 pending (2 done, 2 new follow-up tasks)
```

Net 0. The two urgent strategy tasks are now resolved. Queue is stable.

## Commitment Check
Pre-commitment: Both PRs (#0241 worktree cleanup + #0242 eval signal) delivered, reviewed, and merged. Tests >= 1142. make check green. Dashboard shows sessions_since_eval signal. Worktree cleanup code in lib-agent.sh.
Actual result: Both tasks completed via a single merged PR (#244). Code-reviewer caught a bug in the self-removal guard; fixed in one cycle. 1156 tests pass (14 new). Dashboard now shows eval staleness. Worktree cleanup function rewritten with correct self-removal guard.
Commitment: MET

## Friction

None. Both evolve agents executed cleanly. The duplicate lib-agent.sh change was an expected risk of parallel agents — handled by closing the duplicate PR.

## Current State
- Tests: 1156 passing (+14)
- Eval: 86/100 (still stale — but now tracked in dashboard!)
- Autonomy: 85/100
- Version: v0.0.8 in progress
- Pending tasks: 69

## Next Session Should

1. **BUILD #0243** (normal) -- Run nightshift against Phractal to produce eval #0017. The dashboard now shows eval staleness alert (14+ sessions). This validates all code changes since session #0108. Addresses human issues #0094, #0228, #0224.
2. **BUILD a human-filed task** -- 6 github-issue tasks in the queue. Pick the highest-priority one that doesn't overlap with #0243.
3. If queue is heavy, consider OVERSEE to triage — 69 tasks, some may be stale or duplicate after the strategy session.
