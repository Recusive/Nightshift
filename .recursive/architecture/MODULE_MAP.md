# Module Map

Last updated: 2026-04-09 by session #0093
Generated via: `python3 -m nightshift module-map --write`
Stale after: 5 newer sessions without a refresh

This file is generated from the current `nightshift/*.py` sources plus git history.
Read it before opening modules one by one when you need fast orientation.

## Modules (27)

| Module | Lines | Purpose | Key symbols | Last changed |
|---|---:|---|---|---|
| `core/errors.py` | 7 | Nightshift error types. | `NightshiftError` | 1636b72 |
| `core/types.py` | 594 | Strict type definitions for all Nightshift data structures. | `NightshiftConfig`, `DiffScore`, `Counters`, `Baseline` | PR #231 (1052c38) |
| `settings/eval_targets.py` | 99 | Known evaluation targets and their repo-specific verification settings. | `infer_target_verify_command`, `PHRACTAL_URL`, `_KNOWN_TARGET_VERIFY_COMMANDS` | PR #258 (9bf4032) |
| `core/constants.py` | 851 | Module-level constants and tiny utilities used across the package. | `now_local`, `print_status`, `DATA_VERSION`, `SUPPORTED_AGENTS` | PR #269 (2e91d5f) |
| `raven/summary.py` | 141 | Feature summary generation for Loop 2 build output. | `generate_feature_summary`, `_API_DIR_SEGMENTS`, `_CLI_DIR_SEGMENTS`, `_CONFIG_DIR_SEGMENTS` | 1636b72 |
| `core/shell.py` | 256 | Subprocess execution: streaming runner, git helper, shell utilities. | `run_command`, `run_capture`, `git`, `command_exists` | PR #269 (2e91d5f) |
| `core/state.py` | 237 | Shift state: read, write, mutate counters, JSON I/O. | `load_json`, `write_json`, `read_state`, `top_path` | PR #271 (2f509ab) |
| `owl/readiness.py` | 234 | Production-readiness checks for Loop 2 feature builds. | `collect_changed_files`, `check_secrets`, `check_debug_prints`, `check_test_coverage` | PR #204 (df36eff) |
| `raven/coordination.py` | 196 | Sub-agent coordination for Loop 2 -- detects file overlaps and generates hints. | `extract_file_references`, `detect_overlaps`, `generate_coordination_hints`, `inject_hints` | PR #229 (c2acba2) |
| `infra/module_map.py` | 473 | Generate a persistent module map for fast cross-session orientation. | `module_map_path`, `generate_module_map`, `render_module_map`, `write_module_map` | PR #251 (c32e527) |
| `infra/multi.py` | 117 | Multi-repo shift orchestration: run hardening loops across multiple repos. | `validate_repos`, `format_multi_summary`, `run_multi_shift` | 1636b72 |
| `infra/release.py` | 327 | Auto-release version tagging -- checks readiness and creates GitHub releases. | `check_and_release`, `find_releasable_version` | PR #268 (3ef4d4c) |
| `owl/scoring.py` | 113 | Post-cycle diff scoring: evaluates production impact of cycle changes. | `score_diff`, `log_score` | 1636b72 |
| `settings/config.py` | 259 | Configuration loading, agent resolution, and environment detection. | `merge_config`, `prompt_for_agent`, `resolve_agent`, `infer_package_manager` | PR #269 (2e91d5f) |
| `infra/worktree.py` | 279 | Git worktree lifecycle: create, shift log, sync, revert, cleanup. | `canonical_repo_relative_path`, `resolve_nightshift_dir`, `resolve_shift_log_relative_dir`, `resolve_test_runtime_dir` | session #0093 |
| `owl/eval_runner.py` | 739 | Evaluation runner: score nightshift against a target repo (or dry-run with synthetic data). | `score_artifacts`, `format_eval_table`, `run_eval_dry_run`, `run_eval_full` | session #0093 |
| `raven/e2e.py` | 113 | End-to-end test runner for Loop 2 feature builds. | `infer_test_command`, `detect_smoke_test`, `run_e2e_tests`, `_MAKEFILE_TEST_TARGET` | 1636b72 |
| `raven/profiler.py` | 547 | Repo profiling for Loop 2 -- detects language, framework, dependencies, structure. | `profile_repo` | PR #220 (d9e4320) |
| `owl/cycle.py` | 983 | Per-cycle logic: prompt building, agent dispatch, verification, evaluation. | `extract_json`, `read_repo_instructions`, `wrap_repo_instructions`, `command_for_agent` | PR #272 (304bb7a) |
| `raven/planner.py` | 483 | Feature planner for Loop 2 -- builds structured plans from repo profiles. | `build_plan_prompt`, `validate_plan`, `parse_plan`, `execution_order` | 1636b72 |
| `raven/subagent.py` | 281 | Sub-agent spawner for Loop 2 -- executes work orders via codex or claude CLI. | `spawn_task`, `spawn_wave`, `format_wave_result`, `_TASK_COMPLETION_REQUIRED_KEYS` | 1636b72 |
| `raven/decomposer.py` | 175 | Task decomposer for Loop 2 -- converts FeaturePlans into sub-agent work orders. | `build_work_order_prompt`, `decompose_plan`, `format_work_orders` | 1636b72 |
| `raven/integrator.py` | 325 | Wave integrator for Loop 2 -- merges sub-agent work, runs tests, handles failures. | `collect_wave_files`, `stage_files`, `run_test_suite`, `diagnose_failure` | 1636b72 |
| `raven/feature.py` | 744 | Loop 2 feature-build orchestration and persisted build state. | `feature_state_path`, `feature_log_dir`, `read_feature_state`, `write_feature_state` | PR #208 (a4b3d0e) |
| `cli.py` | 766 | CLI entry points: run, test, summarize, verify-cycle, module-map. | `run_nightshift`, `summarize`, `verify_cycle_cli`, `plan_feature` | PR #258 (9bf4032) |
| `__main__.py` | 5 | Entry point for python3 -m nightshift. | `main` | 2802c51 |
| `__init__.py` | 502 | Nightshift -- autonomous overnight codebase improvement agent. | `AGENT_DEFAULT_MODELS`, `BACKEND_DIR_NAMES`, `BACKEND_EXTENSIONS`, `CATEGORY_ORDER` | PR #269 (2e91d5f) |

## Dependency Order

Legend: A -> B means A must be loaded before B (A is a dependency of B).

Topological order derived from internal `nightshift.*` imports.
`__init__.py` is excluded because it re-exports the package surface.

`core/errors -> core/types -> settings/eval_targets -> core/constants -> raven/summary -> core/shell -> core/state -> owl/readiness -> raven/coordination -> infra/module_map -> infra/multi -> infra/release -> owl/scoring -> settings/config -> infra/worktree -> owl/eval_runner -> raven/e2e -> raven/profiler -> owl/cycle -> raven/planner -> raven/subagent -> raven/decomposer -> raven/integrator -> raven/feature -> cli -> __main__`

## Recent Shipped Sessions

- PR #273: docs: record eval 0020 rerun
- PR #272: fix: neutralize repo instruction delimiters
- PR #271: fix: sanitize corrupt state counters
- PR #268: fix: use --notes-file tempfile in release.py to prevent gh @ file expansion (C-4)
- PR #269: fix: validate eval_target_repo URL and use mkdtemp for clone dest (C-1, C-2)
