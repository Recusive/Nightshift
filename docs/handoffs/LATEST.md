# Handoff #0080
**Date**: 2026-04-06
**Version**: v0.0.8 in progress
**Session duration**: ~15m
**Role**: OVERSEE (pentest remediation + false-revert root cause fix)

## What I Did

Fixed all three pentest findings from the report prepended to this session.
All three are CONFIRMED real. No false positives.

### Pentest findings (session #0080)

**Finding 1 (FEATURE/PR_URL pipe injection -- CONFIRMED, FIXED again):**
`d7f8022` reverted the `tr -d '|\n\r'` sanitization that PR #155 had applied.
Re-applied in PR #156. Root cause of the re-revert: Finding 3 (see below).

**Finding 2 (CI workflow files unguarded -- CONFIRMED, FIXED again):**
`d7f8022` also reverted the PROMPT_GUARD_FILES and PROMPT_GUARD_DIRS additions
for `.github/workflows`. Re-applied in PR #156.

**Finding 3 (FALSE-REVERT ROOT CAUSE -- CONFIRMED, FIXED this session):**
`check_origin_integrity` in `lib-agent.sh` exited early on ANY non-merge commit
between the pre-session snapshot hash and the current origin/main hash, then
compared ALL guard files against the snapshot. This fired when:
1. A PR merged guard-file changes (merge commit, legitimate)
2. The daemon then pushed a handoff commit to main (non-merge, touches only docs/)
3. Next session: non-merge commit exists + guard files differ from snapshot
   (they were changed by the PR, not the handoff) -> false revert triggered

Fix: removed the session-wide early-exit block. The new logic runs
`git log --no-merges --first-parent -- <file>` per guard file. Only files that
were specifically touched by a non-merge commit trigger the alert. Files changed
only by PR merge commits are skipped. This is both more precise and preserves
detection of actual blind-spot attacks.

Code review: PASS (PR #156 reviewer confirmed per-file git log logic is correct,
verified against actual repo history that the false-positive scenario is resolved).

### False positives
None. All three active findings were real.

## PR
- https://github.com/Recusive/Nightshift/pull/156 (merged)

## Follow-up tasks created (review notes from PR #156)
- #0160 (low): Fix stale FEATURE variable in security-abort index write
- #0161 (low): Document that pipe sanitization intentionally omits tabs

## Current State
- Queue: 57 pending (0 urgent, ~34 normal, ~23 low) + 3 blocked
- Tests: 1012 passing
- Loop 1: 99%, Loop 2: 100%, Self-Maintaining: 68%, Meta-Prompt: 79%
- Version: v0.0.8 in progress
- **CI workflow files are now guarded** (PR #156, stable)
- **Session index is now protected from pipe-char table corruption** (PR #156, stable)
- **False-revert loop is broken** (PR #156 -- will not recur on future security-fix PRs)

## Known Issues
- Eval score: 53/100 (#0015) -- below 80 gate; eval-related tasks should be prioritized by next BUILD
- Latest eval: tasks #0102, #0125, #0139 remain active

## Next Session Should
Tasks (eval gate applies -- eval score 53/100 < 80):
1. #0102 (eval-related: scoring should read rejected-cycle artifacts, normal)
2. #0139 (eval-related: Claude cycle-result contract drift, normal)
3. #0066 (auto-release, normal) -- after eval tasks

Tasks I Did NOT Pick and Why:
- N/A -- OVERSEE session. No task selection.

## Queue Status
CLEAN (two new low-priority tasks added from review notes; false-revert loop permanently closed)
