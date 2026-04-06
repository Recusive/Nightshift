---
date: 2026-04-06
type: code-pattern
topic: Evaluation scorers must check cycle_result for rejected cycles
---

# Eval scorers: fall back to cycle_result for rejected cycles

When all cycles are rejected, `state["counters"]["fixes"]` and
`state["counters"]["issues_logged"]` stay at zero because `append_cycle_state()`
is only called for accepted cycles.

Rejected cycles store their data under `state["cycles"][*]["cycle_result"]` while
accepted cycles store it at `state["cycles"][*]["fixes"]` (promoted by
`append_cycle_state()`).

Scorers that only read aggregate counters will always report 0 for an all-rejected
run even when real fixes are present in the state JSON.

**Fix pattern:**

```python
def _extract_cycle_fixes(cycle: object) -> list[dict[str, object]]:
    if not isinstance(cycle, dict):
        return []
    direct = cycle.get("fixes")           # accepted cycle
    if isinstance(direct, list):
        return [f for f in direct if isinstance(f, dict)]
    cycle_result = cycle.get("cycle_result")  # rejected cycle
    if isinstance(cycle_result, dict):
        nested = cycle_result.get("fixes")
        if isinstance(nested, list):
            return [f for f in nested if isinstance(f, dict)]
    return []
```

Then in the scorer: if `counter_value == 0`, aggregate from `_extract_cycle_fixes`
across all cycles. This avoids double-counting on runs that mixed accepted and
rejected cycles.

**Why this matters:** Evaluation #0015 scored Discovery at 5/10 and Usefulness at 4/10
despite real fixes existing in the rejected-cycle `cycle_result`. The auto-scorer would
have reported 0 for both before this fix.
