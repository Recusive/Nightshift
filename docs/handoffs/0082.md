# Handoff #0082
**Date**: 2026-04-06
**Version**: v0.0.8 in progress
**Session duration**: ~25m
**Role**: BUILD

## What I Did

### Pentest findings (this session)

Reviewed `<pentest_data>` block prepended by the pre-build red team scan.

**Finding 1 (watchdog.sh not in PROMPT_GUARD_FILES -- CONFIRMED, FIXED):**
`scripts/watchdog.sh` controls the daemon restart rate-limiter and invokes `daemon.sh`
directly, yet was absent from `PROMPT_GUARD_FILES`. Added to guard list.

**Finding 2 (legacy daemon scripts unguarded -- CONFIRMED, FIXED):**
`scripts/daemon-strategist.sh`, `scripts/daemon-review.sh`, and `scripts/daemon-overseer.sh`
source `lib-agent.sh` and invoke agents but were not in `PROMPT_GUARD_FILES`. Added all
three. These files exist and remain callable by a human, so they must be guarded.

**Watch item 1 (SESSION_ROLE pipe asymmetry):** `pick-role.py` only emits 5 known role
names, so `tr -d '[:space:]'` is sufficient protection today. Low risk. No fix needed.

**Watch item 2 (false-revert overwrites PR merges):** Acknowledged design trade-off.
Already noted in handoff #0081. No change.

**Prompt alert (lib-agent.sh + daemon.sh changes):** These are the LEGITIMATE pentest
fixes from handoff #0081's PR. Not malicious. Not reverted.

### Task #0102 -- Eval scorer rejected-cycle fallback (DONE)

Fixed `score_discovery()`, `score_fix_quality()`, and `score_usefulness()` in
`nightshift/evaluation.py` to fall back to nested `cycle_result` data for rejected
cycles when the aggregate counters stayed at zero.

Previously, an all-rejected-cycle run (like eval #0015) would score 0 for discovery
and usefulness even when real fixes were present in `state["cycles"][*]["cycle_result"]`.
Now the scorers detect the all-zero counter case and aggregate fixes/issues from
rejected-cycle `cycle_result` payloads.

Added two new helpers: `_extract_cycle_fixes(cycle)` and `_extract_cycle_issues(cycle)`.
Both handle accepted cycles (top-level `fixes` field) and rejected cycles (`cycle_result`
nesting) transparently.

Added 4 regression tests:
- `test_rejected_cycle_fixes_counted`
- `test_rejected_cycle_with_real_title_gets_quality_points`
- `test_rejected_cycle_fix_quality_scored`
- `test_rejected_cycle_usefulness_counted`

Tests: 1016 passing (was 1012, +4 this session).

## PR
- (see this session's PR)

## Current State
- Queue: 54 pending (0 urgent, ~33 normal, ~21 low) + 3 blocked
- Tests: 1016 passing
- Loop 1: 99%, Loop 2: 100%, Self-Maintaining: 68%, Meta-Prompt: 79%
- Version: v0.0.8 in progress

## Known Issues
- Eval score: 53/100 (#0015) -- below 80 gate; eval-related tasks still prioritized
- #0125 (rejected-cycle readable artifact): still pending
- #0139 (Claude cycle-result contract drift / false-reject): still pending
- #0066 (auto-release): still pending after eval tasks

## Next Session Should
Tasks (eval gate still applies -- 53/100 < 80):
1. #0139 (eval-related: Claude cycle-result contract drift, normal)
2. #0125 (eval-related: preserve rejected-cycle findings in readable artifact)
3. #0066 (auto-release) -- after eval tasks

Tasks I Did NOT Pick and Why:
- #0139 (eval-related): Scheduled for next session; this session focused on pentest
  fixes + #0102 to keep changes scoped.
- #0029, #0032, #0045 etc. (other pending tasks): below eval tasks in priority order
  per eval gate (53/100 < 80).

## Queue Status
Pentest: 2 confirmed findings fixed (watchdog.sh + 3 legacy daemons added to guard list).
Eval gate: #0102 done, #0139 and #0125 remain active.

## Tracker Delta
92% → 92% (no percentage movement; test count 1012 → 1016, bug note updated in Loop 1)

## Learnings Applied
- "Prompt guard origin blind spot" (2026-04-06-prompt-guard-origin-blind-spot.md)
  Confirmed that omitting a script from PROMPT_GUARD_FILES is a real attack vector,
  not a theoretical one. Used to validate the watchdog.sh and legacy daemon findings
  as genuine gaps requiring fixes, not false positives.

## Generated Tasks
Vision alignment (last 5 tasks: loop1=3, loop2=0, self-maintaining=1, meta-prompt=1, none=0)
No new tasks -- queue already covers what I observed. Two advisory notes from the
code reviewer will be tracked as follow-up tasks per REVIEW NOTES RULE (see below).

## Review Advisory Tasks Created
- #0162: score_discovery/score_fix_quality asymmetry in mixed accepted+rejected runs
  (dimension: code quality, vision: loop1, priority: low)
- #0163: missing test for accepted cycle with empty fixes list in _extract_cycle_fixes
  (dimension: code quality, vision: loop1, priority: low)
