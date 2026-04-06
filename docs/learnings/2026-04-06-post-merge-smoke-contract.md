# Learning: Post-merge smoke checks need explicit prompt contracts
**Date**: 2026-04-06
**Session**: 0065
**Type**: pattern

## What happened
`scripts/check.sh` already ran codex and claude dry-runs before merge, but the builder prompt's Step 9 only checked main-branch CI status. ACHIEVE scoring therefore still counted post-merge smoke validation as missing, because nothing required those same dry-runs on `main` after the PR landed.

## The lesson
If a safety check matters after merge, put the exact commands in the post-merge prompt step and lock them with prompt-contract tests. Pre-merge automation does not enforce post-merge behavior by itself.

## Evidence
- `docs/tasks/0093.md` tracked the missing post-merge smoke gate.
- `docs/prompt/evolve.md` Step 9 and `docs/prompt/evolve-auto.md` now both require the two dry-runs.
- `tests/test_nightshift.py` now asserts those exact commands stay in both prompt files.
