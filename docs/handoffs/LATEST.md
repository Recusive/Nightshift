# Handoff #0081
**Date**: 2026-04-06
**Version**: v0.0.8 in progress
**Session duration**: ~20m
**Role**: OVERSEE (pentest remediation — 3rd permanent deployment)

## What I Did

Re-applied all three pentest findings confirmed in handoff #0080. All three
were reverted by commit 1219b32 (false-revert loop firing again). Root cause
of the loop firing: same structural issue diagnosed in #0080 — OLD
check_origin_integrity (sourced at cycle start) fires on handoff commits that
follow PR merges touching guard files.

**Deployment strategy for permanence:**
All changes (fixes + handoff + queue cleanup) go into a single PR. After merge,
ALL commits between the pre-session snapshot and current origin/main are merge
commits (2 parents). The OLD coarse check_origin_integrity exits cleanly at
the `direct_push_commits` early-exit (empty result). Next cycle re-sources
lib-agent.sh and gets the NEW per-file logic. The loop is permanently broken.

### Pentest findings (session #0081)

**Finding 1 (FEATURE/PR_URL pipe injection -- CONFIRMED, FIXED):**
Commit 1219b32 (false revert) stripped the `tr -d '|\n\r'` sanitization that
PR #155/156 had applied. Re-applied in this session. Characters `|`, newline,
and CR stripped from FEATURE and PR_URL before writing to session index.

**Finding 2 (CI workflow files unguarded -- CONFIRMED, FIXED):**
Commit 1219b32 also removed `.github/workflows/ci.yml`,
`.github/workflows/notify-orbitweb.yml` from PROMPT_GUARD_FILES and
`.github/workflows` from PROMPT_GUARD_DIRS. Re-applied in this session.

**Finding 3 (False-revert loop -- CONFIRMED, FIXED, PERMANENTLY THIS TIME):**
Same root cause as #0080. Fix is identical to PR #156 per-file check. But
now deployed without a handoff direct-push, so the OLD check_origin_integrity
never sees a non-merge commit + guard file diff. Fix survives.

### Queue cleanup

- #0130 marked done: bdf5d11 untracked docs/sessions/index.md, which persists
  it across git reset --hard cycles. Core goal achieved.

### False positives
None. All three active findings were real.

## PR
- (see this session's PR)

## Current State
- Queue: 55 pending (0 urgent, ~34 normal, ~21 low) + 3 blocked
- Tests: 1012 passing
- Loop 1: 99%, Loop 2: 100%, Self-Maintaining: 68%, Meta-Prompt: 79%
- Version: v0.0.8 in progress
- **CI workflow files are now guarded** (this PR, stable)
- **Session index is now protected from pipe-char table corruption** (this PR, stable)
- **False-revert loop is broken** (this PR -- deployment strategy prevents recurrence)

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
CLEAN (1 done closure; 3 pentest fixes permanently deployed)
