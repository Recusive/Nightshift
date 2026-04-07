---
name: Count-only fallback must thread to all verifier callers
description: When an agent returns count fields instead of a structured list, the count must be stored in a typed field and consumed by every downstream verifier — not just appended to prose notes
type: code-patterns
date: 2026-04-06
---

## The Pattern

`_as_cycle_result()` detected `fixes_committed: 1` and appended "Agent reported 1 fix(es) in summary form." to `notes`. But `expected_fix_commits()` and `allowed_total_cycle_commits()` read `fixes = cycle_result.get("fixes", [])` and returned `len([]) = 0` — they never saw the prose note.

Result: eval score 53/100, blocked at the 80 gate. Every real Claude cycle was false-rejected as "structured output implies 0."

## Why It Matters

Prose notes are for humans. Verifiers read typed fields. If you detect a count-only fallback, store it in a typed field (`fixes_count_only: int`), then update every function that branches on the empty list to check that field.

Check all callers when you add a fallback:
- `grep` for every reference to `cycle_result.get("fixes")`
- For each caller, ask: would this return wrong results if fixes=[] but fixes_count_only=N?
- Fix each one, add a test for each one

## Application

Same pattern could apply to `logged_issues` if agents start returning `issues_logged: N` count-only payloads. The fix is symmetric: add `issues_count_only: int` and update `expected_cycle_commits` and `allowed_total_cycle_commits` accordingly.
