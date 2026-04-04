# Learning: Always run ruff format before pushing — CI will catch it
**Date**: 2026-04-03
**Session**: 0002
**Type**: gotcha

## What happened
PR #3 failed CI on the Lint step because tests/test_nightshift.py wasn't formatted. Tests passed locally, mypy passed, ruff check passed — but ruff format check failed. Had to push a fix commit.

## The lesson
`make check` runs everything including format check. Always run it before pushing. If you only run `pytest` and `ruff check`, you'll miss formatting. The one-liner: `python3 -m ruff format nightshift/ tests/` before committing.

## Evidence
- PR #3 CI run 23964677666: Lint failed
- Fix commit: b4ffdeb (ruff format test file)
