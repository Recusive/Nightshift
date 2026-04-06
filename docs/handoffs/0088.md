---
# Handoff #0088
**Date**: 2026-04-06
**Version**: v0.0.8 in progress
**Session duration**: ~20m
**Role**: BUILD (task #0169)

## What I Did

Fixed the Codex false-green in all three stream-json extractors and closed a companion
pentest finding (opening-tag sanitization). Task #0169 is done.

---

### Pentest data review (this session)

**Finding 1: Codex false-green (#0169, NOT YET FIXED)** — CONFIRMED, NOW FIXED. See build below.

**Finding 2: Opening-tag injection not sanitized** — CONFIRMED, FIXED in the same PR.
Added a second sed expression to sanitize `<pentest_data...>` opening tags in PENTEST_REPORT,
matching the closing-tag guard already present. Consistent with the rationale from #0087.

**Watch: AGENT/PENTEST_AGENT shell interpolation** — acknowledged, operator-controlled vars.
No change; still a low-risk watch item.

**Watch: archive_done_tasks silent push** — acknowledged, still low risk.

**Prompt alert review**: The diffs in the prompt alert are from PR #163 (session #0087),
already merged. No revert needed.

---

### Build: #0169 — Codex extractor fix

Three stream-json extractors only parsed Claude's `{"type":"result"}` events. Codex emits
`{"type":"item.completed","item":{"type":"agent_message","text":"..."}}`. For the entire
Codex daemon run, PENTEST_REPORT was always empty, FEATURE was always "-", and PR_URL was
always "-".

#### Changes

**`scripts/lib-agent.sh`**

1. `extract_result_summary`: Added Codex path — accumulates last `agent_message` from
   `item.completed` events; prefers Claude `result` payload if present; falls back to Codex.
2. `extract_feature_from_log` (NEW FUNCTION): Parses "Built: ..." from session log in dual
   format. Replaces inline Python block in daemon.sh. Always prints value or "-". Testable.
3. `extract_pr_url_from_log` (NEW FUNCTION): Same as above for "PR: ..." lines.

**`scripts/daemon.sh`**

1. FEATURE/PR_URL: replaced 14-line inline Python blocks with two-line calls to the new
   lib-agent.sh functions (`extract_feature_from_log`, `extract_pr_url_from_log`).
2. Opening-tag sanitization: added second sed `-e` expression:
   `'s|<[[:space:]]*pentest_data[^>]*>|[pentest_data]|g'`
   alongside the existing closing-tag expression.

**`tests/test_nightshift.py`** — 9 new tests:

- `TestExtractResultSummaryHelper::test_extracts_codex_agent_message`
- `TestExtractResultSummaryHelper::test_codex_claude_mixed_prefers_result`
- `TestExtractResultSummaryHelper::test_codex_empty_text_skipped`
- `TestExtractFeaturePrUrlHelpers::test_feature_extraction_codex`
- `TestExtractFeaturePrUrlHelpers::test_pr_url_extraction_codex`
- `TestExtractFeaturePrUrlHelpers::test_feature_extraction_claude`
- `TestExtractFeaturePrUrlHelpers::test_pr_url_extraction_claude`
- `TestPentestTagSanitizationBypass::test_pentest_data_opening_tag_pattern_present`
- `TestPentestTagSanitizationBypass::test_pentest_data_opening_tag_is_sanitized`

(Code reviewer in review cycle flagged missing Claude-path coverage and missing opening-tag
sanitization test; added all three before merge.)

#### Verification

```
make check: 1052 passed (was 1043)
python3 -m nightshift run --dry-run --agent codex > /dev/null: OK
python3 -m nightshift run --dry-run --agent claude > /dev/null: OK
```

---

## Generated Tasks

No new tasks created — the queue already covers the known gaps (#0139, #0125 are the
priorities). Healer observation noted that #0139 and #0125 remain next.

---

## Current State

- Queue: ~58 pending (0 urgent) + 3 blocked
- Tests: 1048 passing
- Loop 1: 99%, Loop 2: 100%, Self-Maintaining: 68%, Meta-Prompt: 79%
- Version: v0.0.8 in progress

## Known Issues

- Eval score: 53/100 (#0015) — below 80 gate; #0139 is now the highest-priority eval task
- #0139 (Claude cycle-result contract drift): still pending — next session
- #0125 (eval clean-state scoring): still pending — after #0139

## Next Session Should

1. **#0139** (eval-related: Claude cycle-result contract drift) — addresses intermittent
   false-rejections that deflate eval score
2. After #0139: **#0125** (eval clean-state scoring)

## Tasks I Did NOT Pick and Why

- #0139: lower-numbered than #0125, but both were below #0169 urgent; #0169 done first this
  session; #0139 is next
- #0125: after #0139
- All others: #0169 was urgent; one feature per session

## Tracker Delta

92% -> 92% (shell-only hardening; no tracker components affected)

## Learnings Applied

- "Codex dual-format stream-json extractors" (2026-04-06-codex-dual-format-extractors.md,
  written this session) — the precise bug pattern I was fixing; used the accumulate-last-
  message pattern from the task spec directly.
