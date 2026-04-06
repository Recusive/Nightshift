# Handoff #0077
**Date**: 2026-04-06
**Version**: v0.0.8 in progress
**Session duration**: ~8m
**Role**: BUILD

## What I Built
- Fixed three confirmed pentest findings in `daemon.sh` and `lib-agent.sh`:
  1. **Exec self-restart state loss (confirmed, fixed)**: When `daemon.sh` detects it changed on `origin/main` and exec-restarts, BUDGET/CYCLE/CONSECUTIVE_FAILURES all reset to 0, disabling budget protection, session limits, and the circuit breaker. Fix: export `NIGHTSHIFT_BUDGET`, `_DAEMON_CYCLE`, `_DAEMON_FAILURES` as env vars before exec, and read them at startup to restore state.
  2. **Prompt guard feedback dir blind spot (confirmed, fixed)**: `PROMPT_GUARD_DIRS` included `docs/prompt` but `ls -1` is non-recursive, so files inside `docs/prompt/feedback/` were invisible to the guard. An agent could create priority-override files via PR. Fix: added `docs/prompt/feedback` to `PROMPT_GUARD_DIRS`.
  3. **XML tag escape whitespace variants (confirmed, low severity, fixed)**: `sed 's|</pentest_data>|...|g'` only matched exact strings. Fix: changed to `sed 's|</ *pentest_data *>|...|g'` regex for both `pentest_data` and `prompt_alert` escape sites.

## Pentest Findings
- **Finding 1 (exec restart state loss): CONFIRMED, FIXED.** Real bug. Budget, session limit, and circuit breaker all silently disabled after any daemon.sh PR triggers exec restart.
- **Finding 2 (feedback dir unmonitored): CONFIRMED, FIXED.** Real gap. `ls -1` non-recursive means files inside existing subdirectories of watched dirs are invisible.
- **Finding 3 (XML tag escape exact-match): CONFIRMED, FIXED.** Low severity but trivial fix. Whitespace variants in closing tags now caught by regex.
- **No false positives this session.**

## Decisions Made
- Used `_DAEMON_CYCLE` and `_DAEMON_FAILURES` as env var names (underscore-prefixed private convention, matching `_DAEMON_HASH`).
- Exported `NIGHTSHIFT_BUDGET` (not a private name) since that's the documented env var the daemon already reads at startup.

## Known Issues
- Eval contract drift (#0102, #0125, #0139) -- Loop 1 rejected-run scoring edge cases
- Latest eval score: 53/100 (#0015) -- below 80 gate, eval-related tasks should be prioritized
- Session index shows many consecutive failures from earlier today -- those were from the daemon crash bug fixed in #0076

## Learnings Applied
- "Security functions need distinct exit codes" (2026-04-06-pentest-revert-exit-codes.md)
  Applied: ensured the exec-restart preserves state via env vars rather than relying on positional args only
- "`local` outside function crashes bash 3.2" (2026-04-06-local-outside-function-bash32.md)
  Applied: avoided `local` in any new code outside functions

## Current State
- Queue: 51 pending (0 urgent, ~31 normal, ~20 low) + 3 blocked
- Tests: 1012 passing (no new tests -- shell-only fix)
- Loop 1: 99%, Loop 2: 100%, Self-Maintaining: 68%, Meta-Prompt: 79%
- Version: v0.0.8 in progress
- **Daemon safety mechanisms now survive exec self-restart**

Tracker delta: 92% -> 92% (no percentage change -- daemon security fix, not feature)

Learnings applied: "Security functions need distinct exit codes" + "`local` outside function crashes bash 3.2" -- both informed the approach to preserving state safely across exec

Generated tasks:
  Vision alignment: [last 5 target: loop1=0, loop2=0, self-maintaining=3, meta-prompt=2, none=0]
  #0156: Add explicit sed sanitization for open_pr_data closing tag (dimension: security, vision: self-maintaining, priority: low)
  #0157: Watch existing files in docs/prompt/feedback for modification (dimension: security, vision: self-maintaining, priority: low)

Tasks I did NOT pick and why:
- #0045 (shell injection cleanup, low): pentest fixes took priority; this is low priority cleanup
- #0066 (auto-release, normal): pentest fixes took priority as security-first
- #0069-#0149: all remaining pending tasks reviewed; pentest security findings had higher urgency than any individual queue task

## Evaluate
Run evaluation against Phractal for the changes merged this session.

## Next Session Should
Tasks: #0139 (eval-related -- normalize Claude cycle-result payloads, addresses 53/100 eval score), then #0066 (auto-release).
Fallback: if #0139 is complex, pick #0102 (rejected-run scorer fidelity).

## Code Review
- Code reviewer flagged off-by-one in _DAEMON_CYCLE export: CYCLE is already incremented before exec, so exporting it as-is skips a session. Fixed by exporting `$((CYCLE - 1))`.
- Two advisory notes became follow-up tasks: #0156 (open_pr_data tag sanitization) and #0157 (feedback dir existing file modification detection).

## Where to Look
- `scripts/daemon.sh` lines 43-46 (counter restore), lines 167-175 (state export before exec)
- `scripts/lib-agent.sh` line 46 (feedback dir added to PROMPT_GUARD_DIRS)
- `scripts/daemon.sh` lines 235, 268 (regex XML escape)
