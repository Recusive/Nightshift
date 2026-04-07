---
type: pattern
date: 2026-04-05
---

# Dry-run integration tests need isolated runtime artifacts

## What happened
`make check` failed because `TestDryRunIntegration::test_run_dry_run_package`
picked up a leftover `docs/Nightshift/2026-04-05.state.json`, so the prompt
started at cycle 3 instead of cycle 1.

## The lesson
Integration tests that execute against the repo root must create or isolate
their own `docs/Nightshift/` runtime state. If they implicitly require that
directory to be empty, they become order-dependent and fail after ordinary
local runs.

## Evidence
`tests/test_nightshift.py`, `make clean`, `make check`
