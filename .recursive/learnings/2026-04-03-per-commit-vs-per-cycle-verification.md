# Learning: Per-commit verification rules reject valid agent work
**Date**: 2026-04-03
**Session**: 0008
**Type**: gotcha

## What happened
verify_cycle() checked every individual commit for shift-log inclusion. Codex commits fixes and shift-log updates separately (fix first, then shift-log in a follow-up commit). Both Phractal validation cycles were rejected even though the agent did update the shift log -- just not in the same commit as the fix.

## The lesson
When writing verification rules, think about the invariant you actually care about. The real invariant is "every cycle must document its work in the shift log." The old rule ("every commit must include the shift log") was a stricter implementation that broke with real agent behavior. Changed to a cycle-level check: at least one commit must include the shift log. Same invariant, less brittle.

## Evidence
- Phractal test shift: both cycles rejected with shift-log violation
- Fix: cycle-level shift_log_seen flag instead of per-commit check
- Tests: 4 new verification tolerance tests confirm both patterns work
