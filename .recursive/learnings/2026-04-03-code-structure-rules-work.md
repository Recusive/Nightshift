# Learning: The code structure rules in CLAUDE.md catch real violations
**Date**: 2026-04-03
**Session**: 0003 (manual)
**Type**: pattern

## What happened
The diff scorer was built entirely in cycle.py — 120 lines of scoring logic with hardcoded regex patterns, score maps, and category weights. After the human added "Code Structure (non-negotiable)" rules to CLAUDE.md, the monitor agent caught the violation and extracted everything into nightshift/scoring.py with patterns in constants.py.

## The lesson
The code structure rules are not bureaucracy — they prevent module bloat and keep the codebase navigable. When building a new feature with >50 lines of logic, create a new module immediately. Don't plan to "refactor later." Follow the new module checklist: create .py, add to __init__.py, add to install.sh PACKAGE_FILES.

## Evidence
- PR #7: diff scorer built in cycle.py (violation)
- PR #8: extracted to scoring.py + constants.py (fix)
- Rules: CLAUDE.md lines 58-64
