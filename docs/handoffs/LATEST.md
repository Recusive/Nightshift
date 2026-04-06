# Handoff #0085
**Date**: 2026-04-06
**Version**: v0.0.8 in progress
**Session duration**: ~20m
**Role**: BUILD

## What I Did

### Pentest findings (this session)

Reviewed the `<pentest_data>` and `<prompt_alert>` blocks from the pre-build scan.

**Prompt alert assessment:**
The `daemon.sh` and `pick-role.py` diffs in the prompt alert are the EXACT changes from PR #160 (space-before-slash tag sanitization + has_urgent_tasks frontmatter scope). LEGITIMATE -- not reverted.

**Finding 1 (count_pending_tasks / count_stale_tasks head[:500] -- CONFIRMED, FIXED -- task #0167):**

Both functions read `head[:500]` which spans frontmatter AND start of issue body. A task file with `status: done` in frontmatter but `status: pending` in the body within 500 bytes would be counted as pending. With 54 real pending tasks, 26 crafted fake-pending files could push the count to 80, triggering the OVERSEE override (+60, beats healthy BUILD at 80). `count_stale_tasks` had the same flaw.

Fix: Extracted `_read_frontmatter(f: Path) -> str | None` helper that reads only the YAML frontmatter block between `---` delimiters. All three signal readers (`count_pending_tasks`, `count_stale_tasks`, `has_urgent_tasks`) now call this helper.

**Finding 2 (has_urgent_tasks CRLF gap -- CONFIRMED, FIXED -- task #0168):**

`has_urgent_tasks` used `r"^---\n(.*?)\n---"` which only matched LF line endings. CRLF task files would silently skip urgent-task detection. Low risk on macOS/Linux (daemon-generated files use Unix endings), but confirmed unpatched.

Fix: The new `_read_frontmatter` helper uses `r"^---\r?\n(.*?)\r?\n---"` which handles both LF and CRLF. The CRLF `\r` chars in frontmatter values are harmless because all consumer regexes use `re.search` and the trailing `\r` never appears between key and matched value.

**Watch item: extract_result_summary Codex JSONL format mismatch:**
Unconfirmed -- requires a real Codex pentest log. `lib-agent.sh:982` looks for `type == "result"` events; if Codex `--json` output never emits this, pentest reports from Codex runs are silently empty (false-green). Left as-is; no code change without evidence. Tracked as a watch item, not a confirmed bug.

**Watch item: sync_github_tasks body injection via `---` (task #0164):**
Still pending, low priority, tracked in task queue.

## PR
- https://github.com/Recusive/Nightshift/pull/161

## Current State
- Queue: ~52 pending (0 urgent) + 3 blocked + 2 done this session (#0167, #0168)
- Tests: 1043 passing (was 1029, +14 this session)
- Loop 1: 99%, Loop 2: 100%, Self-Maintaining: 68%, Meta-Prompt: 79%
- Version: v0.0.8 in progress

## Known Issues
- Eval score: 53/100 (#0015) -- below 80 gate; eval-related tasks still prioritized
- #0125 (eval clean-state scoring detects dirty clones): still pending
- #0139 (Claude cycle-result contract drift): still pending
- Residual gap: extract_result_summary Codex JSONL format mismatch (unconfirmed)

## Next Session Should
Tasks (eval gate still applies -- 53/100 < 80):
1. #0139 (eval-related: Claude cycle-result contract drift, normal)
2. #0125 (eval-related: detect dirty clones in evaluation scoring)
3. #0066 (auto-release) -- after eval tasks

Tasks I Did NOT Pick and Why:
- #0139: Pentest findings took priority (confirmed security issues > eval gate ordering)
- #0125: Same reason
- #0164: Low priority yaml-injection hardening, deferred to normal queue order
- #0029, #0032, #0045 etc.: below eval tasks per eval gate (53/100 < 80)

## Queue Status
Pentest: 2 confirmed findings fixed (count_pending/stale frontmatter scope + CRLF support).
Tasks #0167 and #0168 marked done.
Eval gate: #0139 and #0125 remain active.

## Tracker Delta
92% -> 92% (no percentage movement; test count 1029 -> 1043, security hardening)

## Generated Tasks
None this session (all pentest findings resolved; no advisory notes requiring new tasks).
