# Learning: Generated docs need session labels for in-flight changes
**Date**: 2026-04-05
**Session**: 0049
**Type**: pattern

## What happened
`MODULE_MAP.md` is generated before the session commit exists. My first version
labeled touched modules as `working tree`, which would have been committed and
left stale metadata the moment the PR merged.

## The lesson
If a generated artifact records "last changed" metadata before commit time, use
the current session/handoff number for dirty files instead of `working tree`.
That keeps the committed document truthful after merge even though the future PR
number is not known yet.

## Evidence
- First generated map showed `working tree` for `module_map.py`, `cli.py`,
  `types.py`, and `constants.py`
- Switched dirty-file labels to `session #0049`
- Final `docs/architecture/MODULE_MAP.md` now stays meaningful after merge
