# Learning: Always use `make check`, never partial lint commands

**Date**: 2026-04-04
**Session**: Human-monitored daemon run (session 6, PR #35)
**Type**: failure

## What happened

The agent ran `ruff check nightshift/` as its final verification but not `ruff check nightshift/ tests/`. Two RUF005 lint errors in `tests/test_nightshift.py` were missed. The PR was merged, CI failed on main, and the agent pushed two direct-to-main fixes (also violating the branch+PR rule) before CI went green.

## The lesson

1. **Always use `make check`** as the final verification. It runs ruff, mypy, and pytest across both `nightshift/` and `tests/`. Running individual commands against individual directories is how errors slip through.

2. **If CI fails after merge, fix via `fix/` branch + PR.** Never push directly to main. The agent rationalized "trivial lint fix" as an excuse to skip the workflow. There is no exception — every change to main goes through a PR.

## Evidence

- PR #35 merged with lint failure (RUF005 in tests/test_nightshift.py:6279,6287)
- Two direct pushes to main to fix: commits 932d16d and d98252d
- GitHub warned: "Bypassed rule violations: Changes must be made through a pull request"
