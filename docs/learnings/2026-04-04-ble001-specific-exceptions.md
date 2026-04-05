# Learning: ruff BLE001 requires specific exception types

**Date**: 2026-04-04
**Session**: 0023
**Type**: gotcha

## What happened
Used bare `except Exception` in cleanup.py for error handling around subprocess calls (`git`, `gh`). ruff BLE001 flagged all 3 catches. Had to change to `(OSError, subprocess.SubprocessError, NightshiftError)`.

## The lesson
When catching errors from `run_capture()` / subprocess calls, use the specific exception tuple `(OSError, subprocess.SubprocessError, NightshiftError)` instead of `Exception`. This covers:
- `OSError` / `FileNotFoundError`: command binary not found
- `subprocess.SubprocessError`: includes `TimeoutExpired`, `CalledProcessError`
- `NightshiftError`: raised by `run_capture()` when `check=True` and exit code != 0

Tests that mock exceptions must also use one of these types, not bare `Exception`, or the except clause won't catch them.
