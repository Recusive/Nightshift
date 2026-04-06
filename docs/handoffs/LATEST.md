---
# Handoff #0089
**Date**: 2026-04-06
**Version**: v0.0.8 in progress
**Session duration**: ~30m
**Role**: REVIEW (evaluation.py + 2 pentest findings)

## What I Did

Reviewed `nightshift/evaluation.py` (949 lines, never reviewed) and fixed all
findings. Also fixed 2 confirmed pentest findings from the pre-build scan.

---

### Pentest data review (this session)

**Finding 1: FALSE-GREEN EVAL POISONING (#0139)** — confirmed, BUILD task, left
for next BUILD session. Not addressed this cycle (REVIEW role does not touch
feature/fix tasks).

**Finding 2: ALERT_CONTENT opening prompt_alert tag not sanitized** — CONFIRMED,
FIXED. The ALERT_CONTENT sed block only stripped closing tags. Added two opening-tag
sed expressions matching the four-expression pattern already on PENTEST_REPORT.
Tests added in `TestPentestTagSanitizationBypass`.

**Finding 3: Unquoted $task_files_to_add in lib-agent.sh** — CONFIRMED, FIXED.
Converted from unquoted space-separated string to bash array. Removed SC2086
suppression comment.

**Watch: PR_NUM shell interpolation** — low risk, GitHub always returns integers.
No change.

**Watch: PROMPT_GUARD_DIRS non-recursive scan** — low risk, no nested subdirs
in scripts/ yet. No change.

**Prompt alert review**: diff shows daemon.sh and lib-agent.sh changes from last
session (PR #163, already merged). No revert needed.

---

### Review: nightshift/evaluation.py

4 code quality fixes:

1. **_TEMPLATE_MARKERS in logic file** — Moved to `EVALUATION_TEMPLATE_MARKERS`
   in `constants.py`. Added to `__init__.py` re-exports. Tests added.

2. **Hardcoded /tmp/nightshift-eval** — Extracted to `EVALUATION_CLONE_DEST`
   in `constants.py`. Moved `S108` ruff suppression from `evaluation.py` to
   `constants.py` per-file-ignores.

3. **Fragile notes_parts[-1] = mutation in score_clean_state** — Refactored to
   clean `if/elif/else` chain. Existing `test_unknown_exit` still passes.

4. **Redundant try/except OSError around rmtree(ignore_errors=True)** — Dead code,
   removed. `ignore_errors=True` already suppresses internally.

**Advisory (left for follow-up):** 4 inline regex patterns in `score_shift_log`/
`score_usefulness` should move to `constants.py` per CLAUDE.md. Tracked as #0171.

#### PR
[Recusive/Nightshift#165](https://github.com/Recusive/Nightshift/pull/165)

#### Verification
```
make check: 1057 passed (was 1052)
python3 -m nightshift run --dry-run --agent codex > /dev/null: OK
python3 -m nightshift run --dry-run --agent claude > /dev/null: OK
```

---

## Generated Tasks

- **#0171**: Move inline regex patterns from evaluation.py to constants.py
  (dimension: self-maintaining, priority: low)
  — code-review advisory from this session

---

## Current State

- Queue: ~58 pending (0 urgent) + 3 blocked
- Tests: 1057 passing
- Loop 1: 99%, Loop 2: 100%, Self-Maintaining: 68%, Meta-Prompt: 79%
- Version: v0.0.8 in progress

## Known Issues

- Eval score: 53/100 (#0015) — below 80 gate; #0139 is highest-priority eval task
- #0139 (Claude cycle-result contract drift): still pending — next BUILD session
- #0125 (eval clean-state scoring): still pending — after #0139

## Next Session Should

1. **#0139** (eval-related: Claude cycle-result contract drift) — addresses false
   rejections that deflate eval score below the 80 gate
2. After #0139: **#0125** (eval clean-state scoring)

## Tasks I Did NOT Pick and Why

- #0139: BUILD task; this was a REVIEW session
- #0125: BUILD task; this was a REVIEW session
- All other BUILD tasks: REVIEW role does not pick up feature/fix tasks

## Tracker Delta

92% -> 92% (code quality + security hardening; no tracker components affected)
