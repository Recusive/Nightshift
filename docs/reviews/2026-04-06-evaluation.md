# Review: nightshift/evaluation.py
**Date**: 2026-04-06
**Lines reviewed**: 949
**Issues found**: 6 (4 code quality + 2 pentest)
**Issues fixed**: 6

## Findings

### Code quality (evaluation.py)

1. **`_TEMPLATE_MARKERS` hardcoded in logic file** — CLAUDE.md requires regex patterns,
   marker lists, and other data to live in `constants.py`, not logic modules. Moved to
   `EVALUATION_TEMPLATE_MARKERS` in `constants.py`, added to `__init__.py` re-exports,
   updated import in `evaluation.py`. Added tests in `TestEvaluationConstants`.

2. **`/tmp/nightshift-eval` hardcoded absolute path** — CLAUDE.md: "Never hardcode absolute
   paths." Extracted to `EVALUATION_CLONE_DEST = "/tmp/nightshift-eval"` in `constants.py`.
   Added `S108` to `constants.py` per-file-ignores (moved from `evaluation.py` where the
   string previously lived). Added constant test.

3. **Fragile `notes_parts[-1] =` mutation in `score_clean_state`** — The exit-code `-1`
   branch appended a generic note then immediately replaced it by index. If code is
   rearranged, the index silently targets the wrong element. Refactored to a clean
   `if/elif/else` chain with direct `append`. Existing `test_unknown_exit` still passes.

4. **Redundant `try/except OSError` around `shutil.rmtree(ignore_errors=True)`** — The
   `ignore_errors=True` flag already suppresses all exceptions internally; the outer handler
   was dead code. Removed the outer try/except block.

### Pentest findings (daemon.sh, lib-agent.sh)

5. **[daemon.sh] `ALERT_CONTENT` opening `<prompt_alert>` tag not sanitized** — The
   ALERT_CONTENT sed block only stripped closing tags (`</prompt_alert>`, `</pentest_data>`).
   A compromised pentest agent injecting a diff with a literal `<prompt_alert>` opening tag
   would pass through unsanitized, potentially creating nested wrapper confusion. Added two
   additional sed expressions to sanitize opening `<prompt_alert...>` and `<pentest_data...>`
   tags, matching the four-expression pattern already applied to PENTEST_REPORT. Added two
   tests in `TestPentestTagSanitizationBypass`.

6. **[lib-agent.sh] Unquoted `$task_files_to_add` in git add** — `task_files_to_add` was
   a space-separated string passed unquoted to `git add`, relying on word-splitting. If
   `REPO_DIR` ever contains a space, paths would split incorrectly. Converted to a bash
   array (`local task_files_to_add=()`), appending with `+=()`, and expanded with
   `"${task_files_to_add[@]}"`. Removed the `# shellcheck disable=SC2086` comment that
   was suppressing the warning.

## Skipped

- `score_breadth` uses `or` truthiness to fall back to verification data when
  `files_touched` is absent. An empty list `[]` (falsy) would fall back unnecessarily,
  but since both paths produce 0 directories the score is identical. Behavioral impact
  is zero; left unchanged to avoid scope creep.
- Inline regex patterns in `score_shift_log`/`score_usefulness` (`r"##\s*Fix"` etc.)
  are technically data-in-logic per CLAUDE.md but are used exactly once, adjacent to
  their context, and have no tests that reference them directly. A future REVIEW session
  could move them to an `_evaluation_patterns.py` module.
