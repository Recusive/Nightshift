# Helper name collision in test files

**Date**: 2026-04-05
**Type**: gotcha
**Session**: #0040 (Sub-agent coordination)

## What happened

Added a `_make_work_order()` helper function at the bottom of `test_nightshift.py` for coordination tests. This shadowed the existing `_make_work_order()` defined at line ~5126 with different parameter signatures. The new definition (requiring positional `task_id` and `prompt`) replaced the old one (accepting `**overrides` with defaults), breaking 15 existing tests.

## Root cause

Python module-level functions share a single namespace. A second `def _make_work_order(...)` silently replaces the first. No warning, no error until the old callers fail at runtime.

## Fix

Renamed the new helper to `_make_coord_order()` to avoid collision.

## Rule

Before adding module-level helper functions to shared test files, grep for the name first. If a helper with that name already exists, use a unique prefix (e.g., `_make_coord_order`, `_make_e2e_order`) or reuse the existing helper if its signature is compatible.
