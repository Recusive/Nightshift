# Learning: Stale doc tasks need a reality check first
**Date**: 2026-04-05
**Session**: 0050
**Type**: pattern

## What happened
Task `#0054` still told the agent to document `persist_healer_changes()` and a
rename-`healer.md` disable flow, even though task `#0061` had already removed
the standalone healer path and merged observation into builder Step 6n/6o.

## The lesson
When a docs task references a removed workflow, update the task text to match
the current architecture before closing it. Then document the replacement path
and explicitly label the old behavior as legacy context.

## Evidence
`docs/tasks/0054.md`, `docs/tasks/archive/0061.md`, `docs/ops/OPERATIONS.md`
