# Module Map

Last updated: 2026-04-08 by session #0001
Generated via: `python3 -m nightshift module-map --write`
Stale after: 5 newer sessions without a refresh

This file is generated from the current `nightshift/*.py` sources plus git history.
Read it before opening modules one by one when you need fast orientation.

## Modules (3)

| Module | Lines | Purpose | Key symbols | Last changed |
|---|---:|---|---|---|
| `__main__.py` | 5 | Entry point for python3 -m nightshift. | `main` | 2802c51 |
| `cli.py` | 670 | CLI entry points: run, test, summarize, verify-cycle, module-map. | `run_nightshift`, `summarize`, `verify_cycle_cli`, `plan_feature` | PR #128 (4e32c37) |
| `__init__.py` | 475 | Nightshift -- autonomous overnight codebase improvement agent. | `AGENT_DEFAULT_MODELS`, `BACKEND_DIR_NAMES`, `BACKEND_EXTENSIONS`, `CATEGORY_ORDER` | PR #218 (4029811) |

## Dependency Order

Topological order derived from internal `nightshift.*` imports.
`__init__.py` is excluded because it re-exports the package surface.

`__main__ -> cli`

## Recent Shipped Sessions

- PR #218: fix: address PR #218 review -- tag validation, numeric sort, version param guard
- PR #217: test: add coverage for pentest signal functions in signals.py
- PR #208: feat: wire feature summary into CLI output and write summary.md to log dir
- PR #207: fix: add trailing anchors to all status: regex patterns in signals.py
- PR #206: fix: guard against IndexError when ReadinessCheck details is empty
