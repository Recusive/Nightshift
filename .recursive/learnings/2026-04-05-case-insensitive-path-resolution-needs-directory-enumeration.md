# Learning: Case-insensitive path resolution needs directory enumeration
**Date**: 2026-04-05
**Session**: 0055
**Type**: gotcha

## What happened
The first fix for the `Docs/` vs `docs/` Nightshift path bug still failed on macOS because `Path.exists()` returned true for `repo / "docs"` even when the real directory entry was `Docs`. That preserved the queried casing instead of the on-disk casing, so both the dry-run prompt and `verify_cycle()` still compared against the wrong path.

## The lesson
When you need canonical path casing on a case-insensitive filesystem, do not trust `Path.exists()` alone. Enumerate the parent directory and match child names case-insensitively so you recover the actual on-disk spelling.

## Evidence
- `tests/test_nightshift.py::TestRunNightshiftPaths::test_dry_run_uses_existing_docs_case`
- `tests/test_nightshift.py::TestShiftLogVerificationTolerance::test_case_insensitive_shift_log_path_accepted`
- `docs/evaluations/0011.md`
