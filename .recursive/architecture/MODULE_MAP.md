# Module Map

Last updated: 2026-04-08 by session #0001
Generated via: `python3 -m nightshift module-map --write`
Stale after: 5 newer sessions without a refresh

This file is generated from the current `nightshift/*.py` sources plus git history.
Read it before opening modules one by one when you need fast orientation.

## Modules (3)

| Module | Lines | Purpose | Key symbols | Last changed |
|---|---:|---|---|---|
| `cli.py` | 703 | CLI entry points: run, test, summarize, verify-cycle, module-map. | `run_nightshift`, `summarize`, `verify_cycle_cli`, `plan_feature` | PR #231 (1052c38) |
| `__main__.py` | 5 | Entry point for python3 -m nightshift. | `main` | 2802c51 |
| `__init__.py` | 491 | Nightshift -- autonomous overnight codebase improvement agent. | `AGENT_DEFAULT_MODELS`, `BACKEND_DIR_NAMES`, `BACKEND_EXTENSIONS`, `CATEGORY_ORDER` | PR #231 (1052c38) |

## Dependency Order

Topological order derived from internal `nightshift.*` imports.
`__init__.py` is excluded because it re-exports the package surface.

`cli -> __main__`

## Recent Shipped Sessions

- PR #231: fix: resolve 3 code review blocking issues in eval_runner
- PR #230: fix: sessions-since counters parse delegation history from decisions log (#0222)
- PR #229: fix: include failed tasks in detect_file_conflicts scan (#0090)
- PR #228: feat: surface dependency cycles explicitly in module map output
- PR #227: fix: verify LICENSE already says Recursive Labs Inc, close task 0081
