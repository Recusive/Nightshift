# Handoff #0103
**Date**: 2026-04-07
**Version**: v0.0.8 in progress
**Session duration**: ~3h (human-driven restructuring)
**Role**: BUILD (major restructuring)

## What I Built

### 1. Created Recursive/ -- the portable autonomous framework
Extracted the framework layer into `Recursive/` as a self-contained, project-agnostic system.
- `Recursive/engine/` -- daemon.sh, lib-agent.sh, pick-role.py, watchdog.sh, format-stream.py
- `Recursive/operators/` -- build, review, oversee, strategize, achieve, security-check
- `Recursive/lib/` -- costs.py, cleanup.py, compact.py, evaluation.py, config.py (moved from nightshift/)
- `Recursive/agents/` -- code-reviewer.md, docs-reviewer.md, meta-reviewer.md, safety-reviewer.md, architecture-reviewer.md
- `Recursive/prompts/` -- includes checkpoints.md (Process Verification Pipeline with 4 checkpoints)
- `Recursive/ops/` -- OPERATIONS.md, DAEMON.md, PRE-PUSH-CHECKLIST.md, ROLE-SCORING.md
- `Recursive/scripts/` -- init.sh (creates all 14 .recursive/ directories with starter files), list-tasks.sh
- `Recursive/templates/` -- project scaffolding templates
- `Recursive/tests/` -- framework-level tests
- `Recursive/CLAUDE.md` -- the framework's own identity and instructions

### 2. Moved runtime data from docs/ to .recursive/
All 14 runtime state directories now live under `.recursive/`:
handoffs, tasks, sessions, learnings, evaluations, autonomy, strategy, healer, reviews, plans, architecture, changelog, vision, vision-tracker.

The `docs/` directory has been **deleted** entirely. Project documentation that was in docs/ is now split between `.recursive/` (runtime state) and `Recursive/ops/` (operational guides).

### 3. Removed 4 meta-layer modules from nightshift/
Moved to `Recursive/lib/`: costs.py, cleanup.py, compact.py, evaluation.py. These are framework concerns, not product concerns.

### 4. Restructured nightshift/ into subdirectories
- `nightshift/core/` -- constants.py, errors.py, shell.py, state.py, types.py
- `nightshift/settings/` -- config.py, eval_targets.py
- `nightshift/owl/` -- hardening loop: cycle.py, readiness.py, scoring.py
- `nightshift/raven/` -- feature builder: coordination.py, decomposer.py, e2e.py, feature.py, integrator.py, planner.py, profiler.py, subagent.py, summary.py
- `nightshift/infra/` -- module_map.py, multi.py, worktree.py
- `nightshift/scripts/` -- product scripts (moved from top-level scripts/)
- `nightshift/tests/` -- product tests (moved from top-level tests/)

### 5. Other structural changes
- `.claude/agents/` files are now **symlinks** to `Recursive/agents/`
- Config file is `.recursive.json` (replaces `.nightshift.json`)
- Daemon runs from `Recursive/engine/daemon.sh`
- `scripts/` top-level directory **deleted** (split between nightshift/scripts/ and Recursive/engine/)
- `docs/prompt/` **deleted** (superseded by Recursive/operators/)
- Session index now has 10 columns (agent override mechanism added)
- `Recursive/scripts/init.sh` bootstraps new projects with all 14 .recursive/ directories

### 6. Process Verification Pipeline
Added 4 checkpoints in `Recursive/prompts/checkpoints.md`:
1. Signal Analysis (before deciding)
2. Forced Tradeoff Analysis (before starting work)
3. (2 additional checkpoints -- read the file for details)

- Tests: 847 passing, make check green

## Decisions Made
- **Framework vs product separation**: Recursive/ is portable and project-agnostic. nightshift/ is the Nightshift product. `.recursive/` is per-project runtime state. This three-way split is the core architectural decision.
- **Subdirectory structure for nightshift/**: core (foundational types/errors), settings (config), owl (hardening loop), raven (feature builder), infra (worktree/multi/module-map). Names are thematic, not generic.
- **Symlinks for agents**: `.claude/agents/*.md` symlink to `Recursive/agents/` so Claude Code discovers them automatically while the source of truth lives in the framework.
- **init.sh for bootstrapping**: New projects run `bash Recursive/scripts/init.sh` to get all 14 `.recursive/` directories with starter files.

## Known Issues

**CRITICAL -- must fix before daemon runs cleanly:**
- `Recursive/ops/OPERATIONS.md` has stale paths referencing old `docs/` and `scripts/` locations
- `Recursive/ops/DAEMON.md` has stale paths referencing old `docs/` and `scripts/` locations
- `Recursive/ops/PRE-PUSH-CHECKLIST.md` has stale paths referencing old structure
- `Recursive/ops/ROLE-SCORING.md` has stale paths referencing old structure

**Non-critical but should fix soon:**
- `.recursive/vision/` and `.recursive/vision-tracker/` content still references old `docs/` structure internally
- The root `CLAUDE.md` likely has stale references to `docs/` paths, `scripts/` paths, and old make targets -- **read it carefully and cross-check against actual file paths before trusting any path it mentions**

**Carry-forward from previous sessions:**
- Eval score: 53/100 (STALE -- task #0177 directs re-running evaluation)
- Pentest watch items still open: #0188 (_is_valid_autonomy_file code-block bypass), #0191 (CODEX_THINKING too broad)

## Current State
- Loop 1: 99%
- Loop 2: 100%
- Self-Maintaining: 68%
- Meta-Prompt: 79%
- Overall: 92%
- Version: v0.0.8 in progress -- ~69 pending tasks
- Tests: 847 passing
- Eval: 53/100 (STALE)
- Autonomy: 85/100

## Next Session Should

1. **Read `Recursive/CLAUDE.md`** -- this is the new framework identity document. It explains what belongs where (Recursive/ vs .recursive/ vs nightshift/ vs project root).
2. **Run `make check`** to verify everything still passes.
3. **Fix stale paths in `Recursive/ops/`** -- OPERATIONS.md, DAEMON.md, PRE-PUSH-CHECKLIST.md, and ROLE-SCORING.md all reference deleted `docs/` and `scripts/` paths. This is the highest-priority fix because the daemon reads these files.
4. **Audit root `CLAUDE.md`** -- it was written for the old structure. Many paths it references (docs/handoffs/, docs/ops/, scripts/daemon.sh, etc.) no longer exist. Update all paths to match the new layout.
5. **After path fixes**: pick up pending tasks from `.recursive/tasks/`, starting with lowest-numbered. Task #0177 (eval re-run) remains high priority due to EVAL SCORE GATE (53/100 < 80).

## Where to Look

- `Recursive/CLAUDE.md` -- framework identity and "what belongs where" guide
- `Recursive/engine/daemon.sh` -- daemon entry point (moved from scripts/)
- `Recursive/operators/` -- all operator prompts (build, review, oversee, strategize, achieve, security-check)
- `Recursive/ops/` -- operational docs that need path updates
- `nightshift/core/` -- foundational modules (constants, errors, shell, state, types)
- `nightshift/owl/` -- hardening loop (cycle, readiness, scoring)
- `nightshift/raven/` -- feature builder (all feature/decomposer/planner modules)
- `nightshift/infra/` -- infrastructure (worktree, multi, module_map)
- `nightshift/settings/` -- config and eval_targets
- `.recursive/tasks/` -- pending task queue
- `.recursive.json` -- project config (replaces .nightshift.json)
- `Makefile` -- updated targets (make check, make test, make daemon all point to new locations)
