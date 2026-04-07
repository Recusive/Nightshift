# Learning: Evaluation reruns should reuse existing tasks

**Date**: 2026-04-05
**Session**: Cache-read pricing assertions + Phractal evaluation rerun
**Type**: process

## What happened

The second Phractal evaluation reproduced the same low-scoring dimensions as
`docs/evaluations/0001.md` (startup, shift log, verification, clean state,
usefulness). Step 0 still said "create a task" for every below-threshold
dimension, which would have duplicated tasks `#0097`-`#0102` even though the
queue already covered each failure.

## The lesson

Before creating evaluation follow-up tasks, scan pending tasks for the same
root cause. If a matching task already exists, reference it in the evaluation
report instead of creating another copy. Repeated reruns should add evidence,
not queue spam.

## Applied fix

Updated `docs/evaluations/README.md` and `docs/prompt/evolve.md` so rerun
evaluations reuse existing pending tasks when the failure is already tracked.
