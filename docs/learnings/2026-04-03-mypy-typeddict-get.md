# Learning: mypy rejects .get() on required TypedDict fields
**Date**: 2026-04-03
**Session**: 0004 (daemon session 1)
**Type**: gotcha

## What happened
Code review on the state injection PR flagged using `.get()` on a required TypedDict field. mypy strict mode treats required fields as always-present, so `.get()` is unnecessary and can mask type errors. The reviewer caught this and the agent fixed it.

## The lesson
For required TypedDict fields, use direct key access `state["field"]` not `state.get("field")`. Only use `.get()` on `total=False` TypedDicts where fields are genuinely optional. This applies to `NightshiftConfig`, `ShiftState`, `Counters`, `CycleVerification` — all required fields.

## Evidence
- PR #9 review feedback: "use direct key access on required TypedDict field"
- Fix commit: f7f1877
