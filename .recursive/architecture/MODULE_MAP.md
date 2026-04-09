# Module Map

Last updated: 2026-04-09 by session #0078
Generated via: `python3 -m nightshift module-map --write`
Stale after: 5 newer sessions without a refresh

This file is generated from the current `nightshift/*.py` sources plus git history.
Read it before opening modules one by one when you need fast orientation.

## Modules (27)

| Module | Lines | Purpose | Key symbols | Last changed |
|---|---:|---|---|---|
| `core/errors.py` | 7 | Nightshift error types. | `NightshiftError` | 1636b72 |
| `core/types.py` | 594 | Strict type definitions for all Nightshift data structures. | `NightshiftConfig`, `DiffScore`, `Counters`, `Baseline` | PR #231 (1052c38) |
| `settings/eval_targets.py` | 96 | Known evaluation targets and their repo-specific verification settings. | `infer_target_verify_command`, `_KNOWN_TARGET_VERIFY_COMMANDS` | 1636b72 |
| `core/constants.py` | 839 | Module-level constants and tiny utilities used across the package. | `now_local`, `print_status`, `DATA_VERSION`, `SUPPORTED_AGENTS` | PR #239 (7f5cee2) |
| `raven/summary.py` | 141 | Feature summary generation for Loop 2 build output. | `generate_feature_summary`, `_API_DIR_SEGMENTS`, `_CLI_DIR_SEGMENTS`, `_CONFIG_DIR_SEGMENTS` | 1636b72 |
| `core/shell.py` | 221 | Subprocess execution: streaming runner, git helper, shell utilities. | `run_command`, `run_capture`, `git`, `command_exists` | PR #202 (1c0ee48) |
| `core/state.py` | 193 | Shift state: read, write, mutate counters, JSON I/O. | `load_json`, `write_json`, `read_state`, `top_path` | PR #247 (c364e8f) |
| `owl/readiness.py` | 234 | Production-readiness checks for Loop 2 feature builds. | `collect_changed_files`, `check_secrets`, `check_debug_prints`, `check_test_coverage` | PR #204 (df36eff) |
| `raven/coordination.py` | 196 | Sub-agent coordination for Loop 2 -- detects file overlaps and generates hints. | `extract_file_references`, `detect_overlaps`, `generate_coordination_hints`, `inject_hints` | PR #229 (c2acba2) |
| `infra/module_map.py` | 466 | Generate a persistent module map for fast cross-session orientation. | `module_map_path`, `generate_module_map`, `render_module_map`, `write_module_map` | session #0078 |
| `infra/multi.py` | 117 | Multi-repo shift orchestration: run hardening loops across multiple repos. | `validate_repos`, `format_multi_summary`, `run_multi_shift` | 1636b72 |
| `infra/release.py` | 315 | Auto-release version tagging -- checks readiness and creates GitHub releases. | `check_and_release`, `find_releasable_version` | PR #223 (493d843) |
| `owl/scoring.py` | 113 | Post-cycle diff scoring: evaluates production impact of cycle changes. | `score_diff`, `log_score` | 1636b72 |
| `settings/config.py` | 256 | Configuration loading, agent resolution, and environment detection. | `merge_config`, `prompt_for_agent`, `resolve_agent`, `infer_package_manager` | PR #202 (1c0ee48) |
| `infra/worktree.py` | 245 | Git worktree lifecycle: create, shift log, sync, revert, cleanup. | `canonical_repo_relative_path`, `resolve_nightshift_dir`, `resolve_shift_log_relative_dir`, `resolve_test_runtime_dir` | 1636b72 |
| `owl/eval_runner.py` | 643 | Evaluation runner: score nightshift against a target repo (or dry-run with synthetic data). | `score_artifacts`, `format_eval_table`, `run_eval_dry_run`, `run_eval_full` | PR #231 (1052c38) |
| `raven/e2e.py` | 113 | End-to-end test runner for Loop 2 feature builds. | `infer_test_command`, `detect_smoke_test`, `run_e2e_tests`, `_MAKEFILE_TEST_TARGET` | 1636b72 |
| `raven/profiler.py` | 547 | Repo profiling for Loop 2 -- detects language, framework, dependencies, structure. | `profile_repo` | PR #220 (d9e4320) |
| `owl/cycle.py` | 941 | Per-cycle logic: prompt building, agent dispatch, verification, evaluation. | `extract_json`, `read_repo_instructions`, `wrap_repo_instructions`, `command_for_agent` | 1636b72 |
| `raven/planner.py` | 483 | Feature planner for Loop 2 -- builds structured plans from repo profiles. | `build_plan_prompt`, `validate_plan`, `parse_plan`, `execution_order` | 1636b72 |
| `raven/subagent.py` | 281 | Sub-agent spawner for Loop 2 -- executes work orders via codex or claude CLI. | `spawn_task`, `spawn_wave`, `format_wave_result`, `_TASK_COMPLETION_REQUIRED_KEYS` | 1636b72 |
| `raven/decomposer.py` | 175 | Task decomposer for Loop 2 -- converts FeaturePlans into sub-agent work orders. | `build_work_order_prompt`, `decompose_plan`, `format_work_orders` | 1636b72 |
| `raven/integrator.py` | 325 | Wave integrator for Loop 2 -- merges sub-agent work, runs tests, handles failures. | `collect_wave_files`, `stage_files`, `run_test_suite`, `diagnose_failure` | 1636b72 |
| `raven/feature.py` | 744 | Loop 2 feature-build orchestration and persisted build state. | `feature_state_path`, `feature_log_dir`, `read_feature_state`, `write_feature_state` | PR #208 (a4b3d0e) |
| `cli.py` | 703 | CLI entry points: run, test, summarize, verify-cycle, module-map. | `run_nightshift`, `summarize`, `verify_cycle_cli`, `plan_feature` | PR #231 (1052c38) |
| `__main__.py` | 5 | Entry point for python3 -m nightshift. | `main` | 2802c51 |
| `__init__.py` | 495 | Nightshift -- autonomous overnight codebase improvement agent. | `AGENT_DEFAULT_MODELS`, `BACKEND_DIR_NAMES`, `BACKEND_EXTENSIONS`, `CATEGORY_ORDER` | PR #239 (7f5cee2) |

## Dependency Order

Legend: A -> B means A must be loaded before B (A is a dependency of B).

Topological order derived from internal `nightshift.*` imports.
`__init__.py` is excluded because it re-exports the package surface.

`core/errors -> core/types -> settings/eval_targets -> core/constants -> raven/summary -> core/shell -> core/state -> owl/readiness -> raven/coordination -> infra/module_map -> infra/multi -> infra/release -> owl/scoring -> settings/config -> infra/worktree -> owl/eval_runner -> raven/e2e -> raven/profiler -> owl/cycle -> raven/planner -> raven/subagent -> raven/decomposer -> raven/integrator -> raven/feature -> cli -> __main__`

## Recent Shipped Sessions

- PR #248: fix: correct dependency flow ordering and ROLE-SCORING signal docs
- PR #247: fix: use fixes_count_only in append_cycle_state, not commit count (#0247)
- PR #246: eval: produce eval #0017 against Phractal (83/100, gate CLEAR)
- PR #245: fix: remove dead code in signals.py and unused constant in test_signals.py
- PR #244: fix: correct self-removal guard in cleanup_worktrees
