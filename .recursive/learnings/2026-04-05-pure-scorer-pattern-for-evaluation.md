# Pure scorer pattern for evaluation dimensions

**Date**: 2026-04-05
**Session**: #0041
**Context**: Built `nightshift/evaluation.py` with 10 dimension scorers

## The Pattern

Each evaluation scorer is a pure function: takes `ShiftArtifacts` (a TypedDict with parsed state, shift log text, exit code, and validity flags), returns `DimensionScore` (name, score, max_score, notes). No I/O, no file reads, no subprocess calls inside scorers.

All I/O happens in three boundary functions: `clone_target_repo()`, `run_test_shift()`, `parse_shift_artifacts()`. These feed artifacts into the pure scoring pipeline.

## Why This Matters

- **Testability**: 66 tests cover all 10 scorers with zero mocks, zero tmp_path, zero fixtures. Just construct a `ShiftArtifacts` dict and assert on the score.
- **Composability**: `score_all_dimensions()` is a one-liner that maps all scorers over the same artifacts.
- **Debugging**: When a dimension scores low, the `notes` field explains why without needing to reproduce the I/O.

## When to Apply

Any time you build a system that evaluates or grades output:
1. Parse raw data into a typed intermediate (the "artifacts" layer)
2. Score the intermediate with pure functions
3. Keep I/O at the edges only

This is the same pattern as `readiness.py` (pure file scanners) and `summary.py` (pure path analysis), but formalized for scoring.

## Related

- `nightshift/evaluation.py` -- the implementation
- `nightshift/readiness.py` -- same pattern for readiness checks
- `nightshift/summary.py` -- same pattern for feature summaries
- Task #0082 -- profiler.py fragile config construction (hit again this session when adding eval config keys)
