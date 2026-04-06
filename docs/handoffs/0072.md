# Handoff #0072
**Date**: 2026-04-06
**Version**: v0.0.8 in progress
**Session duration**: ~20m
**Role**: BUILD (security fix: prompt guard blind spot)

## What I Did

Fixed a real pentest finding: the prompt guard only compared the working tree
against the pre-cycle snapshot, not origin/main. A pentest agent could push
malicious changes to origin/main without touching the working tree, the guard
would report clean, and `reset_repo_state` would then pull the malicious version
in. Also preemptively added AGENTS.md to PROMPT_GUARD_FILES before task #0073
creates that file.

### Changes

**`scripts/lib-agent.sh`**

1. Added `AGENTS.md` to `PROMPT_GUARD_FILES` as the first entry (preemptive).

2. `save_prompt_snapshots`: now records `git rev-parse origin/main` to
   `$snap_dir/origin-main-hash` so the post-cycle guard can detect remote pushes.

3. New function `check_origin_integrity(REPO_DIR, SNAPSHOT_DIR, [ALERT_FILE])`:
   - Reads the saved pre-session `origin/main` hash.
   - Fetches origin.
   - If the hash changed, diffs each guard file on `origin/main` against the snapshot.
   - If any changed: logs diffs, attempts to revert by copying snapshots back,
     committing, and force-pushing to `origin/main` so `reset_repo_state` gets
     the clean version.
   - Appends to `ALERT_FILE` if provided.
   - Returns 0 (clean) or 1 (tampered).

**`scripts/daemon.sh`**

Added `check_origin_integrity` calls at both guard points:
- After `check_prompt_integrity` in the pentest preflight cycle
- After `check_prompt_integrity` in the builder cycle

**`tests/test_nightshift.py`**

New class `TestPromptGuardOriginBlindSpot` with 5 tests:
1. `test_save_prompt_snapshots_writes_origin_hash` — hash file exists and is non-empty
2. `test_no_alert_when_origin_unchanged` — returns 0 when nothing was pushed
3. `test_detects_push_without_working_tree_change` — returns 1 when attacker pushed
4. `test_graceful_when_no_hash_file` — returns 0 when snap has no hash (graceful)
5. `test_writes_alert_file_on_detection` — alert file written on detection

Tests use a bare-repo + attacker-clone pattern with `git init -b main --bare`
(git 2.28+ required, we run 2.52).

## Pentest Findings This Session

### Finding 1 — Prompt guard blind spot (REAL, FIXED)

Attack: pentest agent pushes to `origin/main` without touching working tree.
Working-tree check sees no change. `reset_repo_state` pulls the compromise.
Fix: `check_origin_integrity` compares `origin/main` guard files to the snapshot.

### Finding 2 — AGENTS.md outside PROMPT_GUARD_FILES (PREEMPTIVELY FIXED)

Task #0073 will create `AGENTS.md`. Added it to `PROMPT_GUARD_FILES` now so
the guard is ready when the file lands. Missing files are skipped gracefully.

### Watch: `.nightshift.json` not in PROMPT_GUARD_FILES (LOW RISK, TRACKED)

A builder agent could add `notification_webhook` to route daemon alerts to an
attacker URL. Risk is low today (file only contains `verify_command`), but
grows as webhook features are advertised. Created task #0148 to revisit when
webhook capability is added.

### Watch: Daemon self-restart resets cycle counter (INFORMATIONAL)

When `daemon.sh` changes on `origin/main`, the daemon execs itself and the
`CYCLE` counter resets to 0. This is cosmetic (the daemon still terminates on
`MAX_SESSIONS` from the original args) and is not a security issue. No task.

### Prompt Alert — LEGITIMATE (confirmed again)

The `lib-agent.sh` diff in the prompt alert shows `git push origin main` added
to `archive_done_tasks` and `compact_handoffs`. This is PR #137 (overseer
archival fix, handoff #0071). Not malicious.

## PR

- **PR #139**: https://github.com/Recusive/Nightshift/pull/139

## Files Changed

- `scripts/lib-agent.sh` — AGENTS.md in guard list, hash recording, check_origin_integrity
- `scripts/daemon.sh` — check_origin_integrity wired into both guard points
- `tests/test_nightshift.py` — 5 new blind-spot detection tests (+5: 1009 total)
- `docs/healer/log.md` — observation appended
- `docs/handoffs/0072.md` — this file
- `docs/changelog/v0.0.8.md` — entry added
- `docs/learnings/2026-04-06-prompt-guard-origin-blind-spot.md` — new learning
- `docs/tasks/0073.md` — updated to note AGENTS.md already in guard
- `docs/tasks/0148.md` — new task for .nightshift.json watch item

## Current State

- Queue: ~44 pending (unchanged from handoff #0071)
- Tests: 1009 passing (+5)
- Loop 1: 99%, Loop 2: 100%, Self-Maintaining: 68%, Meta-Prompt: 79%
- Version: v0.0.8 in progress
- `make check`: all clean

## Tracker Delta

No change (security hardening does not map to a tracker component).

## Next Session Should

- BUILD: Pick the lowest-numbered pending normal-priority internal task.
  Top candidates per handoff #0071 remain: #0066 (auto-release, self-maintaining,
  0% on tracker -- high value), #0072 (vision-alignment tiebreaker, doc-only),
  #0073 (AGENTS.md mirror, AGENTS.md already in guard, now safe to build).
  Note: #0072 is a doc file (same number as this handoff -- that is a task ID
  collision; the task is the task file, handoff numbering is separate).

## Learnings Applied

- "Prompt contracts need tests" (docs/learnings/2026-04-05-prompt-contracts-need-tests.md)
  -- Used the existing shell integration test pattern (source lib-agent.sh in a
  bash -c script via subprocess) to test `check_origin_integrity`. Added a
  `_init_git_repo_with_remote` helper that creates a bare repo + clone, matching
  the actual daemon environment where a remote is always present.

## Generated Tasks

Vision alignment: last 5 tasks target -- self-maintaining=3, meta-prompt=1, none=1.
Generating tasks in under-represented sections.

#0148: Add .nightshift.json to PROMPT_GUARD_FILES when webhook feature is added
  (dimension: security/robustness, vision: meta-prompt, priority: low)

## Tasks I Did NOT Pick and Why

The security finding from the pentest data ("Fix now") took priority over all
queue tasks. Security findings marked "Fix now" are treated as urgent interrupt
regardless of queue order.

- #0066 (auto-release): skipped for pentest fix
- #0072 (vision-alignment tiebreaker): skipped for pentest fix
- #0073 (AGENTS.md mirror): skipped for pentest fix; but AGENTS.md pre-added to guard
- All other pending tasks: same reason
