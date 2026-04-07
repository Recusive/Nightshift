# Fresh eval evidence should drive scheduling gates

**Date**: 2026-04-05
**Type**: process
**Session**: #0057 (Eval score gate)

## What happened

Task `#0131` arrived from GitHub with a stale `66/100` problem statement, but
the mandatory Step 0 rerun on `2026-04-05` scored `70/100`. The task was still
valid, but the prompt change needed to cite fresh evidence, not the previous
handoff summary.

## Rule

When a task changes scheduling policy based on evaluation health, run Step 0
first and write the current evaluation report before editing the prompt or task
text. Queue gates should point at the latest scored report, not yesterday's
handoff number.
