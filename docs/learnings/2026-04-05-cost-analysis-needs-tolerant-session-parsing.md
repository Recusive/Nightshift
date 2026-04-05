# Learning: Cross-session cost analysis needs tolerant session parsing
**Date**: 2026-04-05
**Session**: 0048
**Type**: pattern

## What happened
`cost_analysis()` had to join `docs/sessions/index.md`, `docs/sessions/costs.json`, and per-session logs, but the historical data is not uniform. Older index rows predate the Cost column, Claude logs store the final report in a `result` event, and Codex logs often end with an `item.completed` agent message instead.

## The lesson
Any analytics built on Nightshift session history should treat the data as versioned and messy. Use the ledger as the cost source of truth, parse legacy index rows for duration/feature hints, and extract summary metrics from both Claude and Codex log shapes before computing trends.

## Evidence
- `nightshift/costs.py` now parses mixed index rows plus both final-report log shapes
- `tests/test_nightshift.py::TestCostAnalysis` covers legacy/new index rows and Claude/Codex summary extraction
