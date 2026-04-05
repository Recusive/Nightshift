# Learning: Refresh module map before writing the current handoff
**Date**: 2026-04-05
**Session**: 0051
**Type**: process

## What happened
`nightshift.module_map` labels dirty-file changes with the "next session" number by
looking at the highest numbered handoff already present. During this session I
noticed that if I wrote `docs/handoffs/0051.md` first and refreshed the module map
afterward, `docs/architecture/MODULE_MAP.md` would label itself as `session #0052`.

## The lesson
Run `python3 -m nightshift module-map --write` before creating the current numbered
handoff. The generator uses the next available handoff number, so handoff creation
changes the meaning of "current session."

## Evidence
- `nightshift/module_map.py::_next_session_label()` derives the label from existing
  numbered handoffs
- Running the generator before writing `0051.md` produced the correct `session #0051`
