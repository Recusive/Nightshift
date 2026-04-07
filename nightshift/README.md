# Nightshift

Autonomous overnight codebase improvement agent. Runs for hours while you sleep — finds and fixes production-readiness issues across the entire stack.

## What This Is

A Python package (`python3 -m nightshift`) with two operational loops:

- **Owl (Hardening):** Point it at any repo. It runs overnight, finds issues (security, error handling, tests, a11y, code quality), fixes them one commit at a time, writes a shift log.
- **Raven (Feature Builder):** Give it a feature request in plain English. It plans, decomposes into parallel sub-agents, builds, integrates, tests E2E, returns production-ready code.

## Module Map

### Core (foundation — no business logic)

| Module | What it does |
|--------|-------------|
| `errors.py` | `NightshiftError` exception class |
| `types.py` | All TypedDicts — the data contracts |
| `constants.py` | All constants, patterns, templates, thresholds |
| `shell.py` | Subprocess execution (`run_capture`, `run_command`, `git`) |
| `state.py` | JSON state persistence (`load_json`, `write_json`, `read_state`) |

### Config (project detection)

| Module | What it does |
|--------|-------------|
| `config.py` | Reads `.recursive.json`, infers commands, resolves agents |
| `eval_targets.py` | Known repo-specific evaluation defaults |

### Loop 1 — Hardening

| Module | What it does |
|--------|-------------|
| `cycle.py` | Single-cycle orchestration — prompt building, verification, policy enforcement |
| `scoring.py` | Post-cycle diff scoring — rates change quality |
| `readiness.py` | Production readiness checks — secrets, debug prints, test coverage |

### Loop 2 — Feature Builder

| Module | What it does |
|--------|-------------|
| `feature.py` | Feature build orchestrator — the top-level pipeline |
| `planner.py` | Feature planning — reads repo, creates structured plan |
| `decomposer.py` | Task decomposition — breaks plan into parallel work orders |
| `subagent.py` | Sub-agent spawning — runs parallel agents with isolated work |
| `integrator.py` | Wave integration — merges sub-agent work, runs tests, fixes conflicts |
| `coordination.py` | Conflict detection — finds file overlaps between sub-agents |
| `summary.py` | Feature summary generation |
| `e2e.py` | E2E test runner — smoke tests, inferred test commands |
| `profiler.py` | Repo profiling — detects language, framework, conventions |

### Infrastructure

| Module | What it does |
|--------|-------------|
| `worktree.py` | Git worktree isolation — all work happens in worktrees |
| `module_map.py` | Module map generator — renders dependency graph to markdown |
| `multi.py` | Multi-repo support — runs nightshift across multiple repos |

### Entry Points

| Module | What it does |
|--------|-------------|
| `cli.py` | CLI — `run`, `test`, `build`, `module-map`, `summarize` commands |
| `__init__.py` | Package re-exports |
| `__main__.py` | `python3 -m nightshift` entry |
| `SKILL.md` | Claude Code skill definition (the hardening prompt) |

### Schemas

| File | What it does |
|------|-------------|
| `schemas/feature.schema.json` | Structured output schema for feature planning |
| `schemas/task.schema.json` | Structured output schema for sub-agent task completion |

### Dependency Flow

```
errors -> types -> constants -> shell -> state -> config
    -> eval_targets
    -> scoring -> readiness
    -> cycle -> planner -> decomposer -> subagent
    -> coordination -> integrator -> summary -> e2e -> profiler
    -> worktree -> multi -> feature -> module_map -> cli
```

No circular imports. `multi.py` uses a late import of `run_nightshift` from `cli.py`.

## Scripts

| Script | What it does |
|--------|-------------|
| `scripts/check.sh` | Local CI — ruff, mypy, pytest, dry-runs, shell syntax, ASCII check |
| `scripts/install.sh` | One-liner installer for Claude Code / Codex skills |
| `scripts/run.sh` | Thin wrapper for overnight runs |
| `scripts/test.sh` | Thin wrapper for test runs |
| `scripts/smoke-test.sh` | E2E smoke test against a real repo |

## Tests

855 tests in `tests/`. Run with `make check` from the repo root.
