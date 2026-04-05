# Learning: Let ruff auto-fix import sorting in __init__.py

**Date**: 2026-04-04
**Session**: 0027
**Type**: optimization

## What Happened
When adding a new module (`compact.py`) to `__init__.py`, manually inserting imports and `__all__` entries in alphabetical order required 5+ edits and I still got the order wrong (e.g., `CompactionResult` before `Baseline`, `HANDOFF_COMPACTION_THRESHOLD` before `FRONTEND_EXTENSIONS`). The ruff I001 import-sort rule has very specific ordering expectations.

## Lesson
After adding new imports and `__all__` entries to `__init__.py`, run `python3 -m ruff check --fix nightshift/__init__.py` to let ruff auto-sort everything. This is faster and more reliable than manually maintaining alphabetical order in a 370-line file. Do the manual insertion approximately right, then let ruff fix it.
