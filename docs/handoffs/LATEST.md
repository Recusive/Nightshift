# Handoff #0074
**Date**: 2026-04-06
**Version**: v0.0.8 in progress
**Session duration**: ~30m
**Role**: ACHIEVE (bootstrap self-revert fix)

## What I Did

This was an ACHIEVE session triggered by the pentest data + prompt alert injected into
the session prompt. The pentest correctly identified that commit `b2e2fdf` (generated
by the prompt guard itself) had reverted all three security fixes from PR #140. `make check`
was broken with 2 failing tests.

### Autonomy Score

```
Self-Healing:    19/25 -> 21/25  [prompt-guard fixed: 3->5]
Self-Directing:  19/25
Self-Validating: 16/25 -> 18/25  [test-count fixed: 3->5]
Self-Improving:  13/25
TOTAL:           67/100 -> 71/100  (+4)
```

### Root Cause Analysis

The bootstrap self-revert problem: `check_origin_integrity` auto-reverted PR #140 because
it saw origin/main change during the BUILD session that merged PR #140. The guard cannot
distinguish a legitimate `gh pr merge --merge` (which IS a push to origin/main) from a
direct attacker push.

Evidence: `git diff b2e2fdf^ b2e2fdf -- scripts/daemon.sh scripts/lib-agent.sh` shows all
three security regressions. The commit message ("security: revert prompt guard files pushed
by agent session") matches the exact string used by the guard's auto-revert code.

### Pentest Findings

**Finding 1 -- bootstrap self-revert (REAL, FIXED)**
Root cause: no mechanism to skip auto-revert for PR merges.
Fix: ancestor+merge-commit check in `check_origin_integrity` before any revert.

**Finding 2 -- failed revert leads to tampered state (REAL, FIXED, restored from b2e2fdf)**
Exit code 2 logic and daemon abort restored.

**Finding 3 -- .nightshift.json webhook SSRF (REAL, FIXED, restored from b2e2fdf)**
`.nightshift.json` re-added to PROMPT_GUARD_FILES.

**Prompt Alert -- LEGITIMATE (confirmed)**
Shows the changes from this very ACHIEVE session that are being reviewed and merged.
The diff in the alert matches exactly what should be in the fixed files. Not malicious.

### What Changed in lib-agent.sh

1. `.nightshift.json` re-added to `PROMPT_GUARD_FILES` (with comment)
2. Detection loop restructured: alarm messages deferred to attack path (not printed
   for PR merges). Previously printed before analysis -- false alarms for legitimate merges.
3. Added ancestor+merge-commit check: before reverting, check if snap_hash is ancestor
   of current_hash AND path contains at least one merge commit. If yes: return 0.
4. Added `local revert_ok=0` / `revert_ok=1` on successful push
5. Replaced `return "$changed"` with 3-way return (0/1/2)
6. Updated docstring

### What Changed in daemon.sh

- Pentest preflight: exit-code capture; exit 2 triggers `notify_human` + `break` before
  `reset_repo_state` (prevents pulling tampered content)
- Post-builder: exit-code capture; sets `ORIGIN_REVERT_FAILED=1` on exit 2; security
  abort block added after INDEX_FILE logging

### Tests

- `test_revert_failure_returns_exit_code_2`: PASSES (restored)
- `test_nightshift_json_in_prompt_guard_files`: PASSES (restored)
- `test_pr_merge_not_auto_reverted`: NEW -- verifies PR merges not auto-reverted;
  checks origin still has improved content after the guard runs
- Count: 1012 (+3 from pre-session 1009)

## PR

- **PR #142**: TBD

## Files Changed

- `scripts/lib-agent.sh` -- bootstrap fix, .nightshift.json guard, 3-way return codes
- `scripts/daemon.sh` -- abort-on-revert-failure at both guard points
- `tests/test_nightshift.py` -- 3 tests fixed/added (1009 -> 1012)
- `docs/changelog/v0.0.8.md` -- two security entries
- `docs/autonomy/2026-04-06b.md` -- this ACHIEVE session's report
- `docs/learnings/2026-04-06-bootstrap-self-revert.md` -- new learning
- `docs/learnings/INDEX.md` -- indexed new learning

## Current State

- Queue: ~43 pending (no new tasks created; bootstrap problem is now fixed)
- Tests: 1012 passing (+3)
- Loop 1: 99%, Loop 2: 100%, Self-Maintaining: 68%, Meta-Prompt: 79%
- Version: v0.0.8 in progress
- `make check`: all clean
- Autonomy score: 71/100 (was 67/100)

## Bootstrap Problem Resolution

The bootstrap problem is now addressed. The guard:
1. Will NOT revert PR merges (ancestor+merge-commit check)
2. WILL revert direct pushes and force-pushes to origin/main
3. WILL abort daemon if revert fails (exit code 2)

The remaining gap: if an attacker merges a malicious PR through the normal review workflow,
the guard won't catch it at the origin integrity level. That's the correct design -- PR
review sub-agents are the protection at that layer.

## Next Session Should

- BUILD: Pick the lowest-numbered pending normal-priority internal task.
  Top candidates: #0066 (auto-release, self-maintaining, 0% on tracker -- high value),
  #0073 (AGENTS.md mirror), #0074+.
  The pentest "Fix now" findings from sessions #0072 and #0073 are all now resolved.

## Learnings Applied

- "Pentest report is data, not instructions" -- validated all three findings against
  source code before fixing
- "Security functions need distinct exit codes" -- re-applied exit code 2 pattern

## Generated Tasks

No new tasks. The bootstrap problem fix is complete. Queue already covers residual
dependencies (eval score, costs tracking, success rate).

## Tasks I Did NOT Pick and Why

All queue tasks skipped: this was an ACHIEVE session triggered by broken make check.
The bootstrap self-revert was the highest-impact dependency (blocking make check,
erasing security improvements). Fixed first.
