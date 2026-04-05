# Thread config through callers, don't read inside builders

**Date**: 2026-04-04
**Task**: #0035

## What happened

Adding `config: NightshiftConfig` to `command_for_agent()` required updating every caller in the chain: `cycle.py`, `cli.py`, `planner.py`, `subagent.py`, `feature.py`, `integrator.py`, and `profiler.py` (which builds a minimal config for test runner inference). Plus every test that calls any of these functions.

## Lesson

When adding a new required parameter to a function used widely, expect a cascade. The fix is mechanical but touches many files. Don't skip any caller -- mypy will catch missed call sites, but only if you run it. The `profiler.py` case was non-obvious: it constructs a minimal `NightshiftConfig` inline and needed all 4 new fields added.

## Pattern

Thread config as a parameter rather than reading it inside the function. This keeps functions pure and testable -- tests pass `DEFAULT_CONFIG` directly instead of needing config files on disk.
