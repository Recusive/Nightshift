# Learning: Reassess stale eval tasks with a fresh rerun
**Date**: 2026-04-05
**Session**: 0058
**Type**: pattern

## What happened
Task `#0097` still claimed Claude startup needed `CLAUDECODE` stripping or
effort overrides, but fresh evaluations `#0013` and `#0014` both showed the
default `nightshift test --agent claude` command starting cleanly on Phractal.
The right fix was to close the stale task with evidence, not add dead code for
a failure mode that no longer reproduced.

## The lesson
When an eval-created task tracks external tool behavior, rerun the prescribed
default evaluation path before implementing anything. If the failure no longer
reproduces, retire the task and update the active docs instead of hardening
against a ghost regression.

## Evidence
- `docs/tasks/0097.md`
- `docs/evaluations/0013.md`
- `docs/evaluations/0014.md`
