# Module Map

Last updated: 2026-04-06 by session #0099
Generated via: `python3 -m nightshift module-map --write`
Stale after: 5 newer sessions without a refresh

This file is generated from the current `nightshift/*.py` sources plus git history.
Read it before opening modules one by one when you need fast orientation.

## Modules (29)

| Module | Lines | Purpose | Key symbols | Last changed |
|---|---:|---|---|---|
| `errors.py` | 7 | Nightshift error types. | `NightshiftError` | 2802c51 |
| `eval_targets.py` | 96 | Known evaluation targets and their repo-specific verification settings. | `infer_target_verify_command`, `_KNOWN_TARGET_VERIFY_COMMANDS` | PR #106 (e2d235c) |
| `types.py` | 564 | Strict type definitions for all Nightshift data structures. | `NightshiftConfig`, `DiffScore`, `Counters`, `Baseline` | PR #174 (e92c62f) |
| `constants.py` | 759 | Module-level constants and tiny utilities used across the package. | `now_local`, `print_status`, `DATA_VERSION`, `SUPPORTED_AGENTS` | PR #165 (5141160) |
| `shell.py` | 161 | Subprocess execution: streaming runner, git helper, shell utilities. | `run_command`, `run_capture`, `git`, `command_exists` | PR #27 (9e953eb) |
| `summary.py` | 141 | Feature summary generation for Loop 2 build output. | `generate_feature_summary`, `_API_DIR_SEGMENTS`, `_CLI_DIR_SEGMENTS`, `_CONFIG_DIR_SEGMENTS` | PR #67 (89f8cd6) |
| `cleanup.py` | 337 | Daemon housekeeping -- log rotation, healer archiving, and branch pruning. | `rotate_healer_log`, `rotate_logs`, `prune_orphan_branches`, `_HEALER_ENTRY_RE` | PR #88 (7e36fa5) |
| `compact.py` | 318 | Handoff compaction -- merges numbered handoff files into weekly summaries. | `compact_handoffs`, `_NUMBERED_RE`, `_SECTION_RE`, `_DATE_RE` | PR #83 (56e0c97) |
| `coordination.py` | 192 | Sub-agent coordination for Loop 2 -- detects file overlaps and generates hints. | `extract_file_references`, `detect_overlaps`, `generate_coordination_hints`, `inject_hints` | PR #72 (a5a3e47) |
| `costs.py` | 678 | Cost tracking for daemon sessions -- parse token usage from logs and maintain a ledger. | `parse_session_tokens`, `calculate_cost`, `read_ledger`, `write_ledger` | PR #174 (e92c62f) |
| `module_map.py` | 298 | Generate a persistent module map for fast cross-session orientation. | `module_map_path`, `generate_module_map`, `render_module_map`, `write_module_map` | PR #86 (77e5c25) |
| `readiness.py` | 211 | Production-readiness checks for Loop 2 feature builds. | `collect_changed_files`, `check_secrets`, `check_debug_prints`, `check_test_coverage` | PR #69 (3877225) |
| `scoring.py` | 113 | Post-cycle diff scoring: evaluates production impact of cycle changes. | `score_diff`, `log_score` | PR #10 (3e5f98f) |
| `state.py` | 187 | Shift state: read, write, mutate counters, JSON I/O. | `load_json`, `write_json`, `read_state`, `top_path` | PR #28 (60e4ed5) |
| `config.py` | 241 | Configuration loading, agent resolution, and environment detection. | `merge_config`, `prompt_for_agent`, `resolve_agent`, `infer_package_manager` | PR #106 (e2d235c) |
| `multi.py` | 117 | Multi-repo shift orchestration: run hardening loops across multiple repos. | `validate_repos`, `format_multi_summary`, `run_multi_shift` | PR #22 (12ac402) |
| `e2e.py` | 113 | End-to-end test runner for Loop 2 feature builds. | `infer_test_command`, `detect_smoke_test`, `run_e2e_tests`, `_MAKEFILE_TEST_TARGET` | PR #70 (95ef827) |
| `profiler.py` | 569 | Repo profiling for Loop 2 -- detects language, framework, dependencies, structure. | `profile_repo` | PR #78 (5cc11a3) |
| `worktree.py` | 245 | Git worktree lifecycle: create, shift log, sync, revert, cleanup. | `canonical_repo_relative_path`, `resolve_nightshift_dir`, `resolve_shift_log_relative_dir`, `resolve_test_runtime_dir` | PR #174 (e92c62f) |
| `cycle.py` | 941 | Per-cycle logic: prompt building, agent dispatch, verification, evaluation. | `extract_json`, `read_repo_instructions`, `wrap_repo_instructions`, `command_for_agent` | PR #167 (accff7f) |
| `evaluation.py` | 958 | Self-evaluation loop: score nightshift runs against real repos. | `clone_target_repo`, `run_test_shift`, `parse_shift_artifacts`, `score_startup` | PR #174 (e92c62f) |
| `planner.py` | 483 | Feature planner for Loop 2 -- builds structured plans from repo profiles. | `build_plan_prompt`, `validate_plan`, `parse_plan`, `execution_order` | PR #78 (5cc11a3) |
| `subagent.py` | 281 | Sub-agent spawner for Loop 2 -- executes work orders via codex or claude CLI. | `spawn_task`, `spawn_wave`, `format_wave_result`, `_TASK_COMPLETION_REQUIRED_KEYS` | PR #33 (bd23cc4) |
| `decomposer.py` | 175 | Task decomposer for Loop 2 -- converts FeaturePlans into sub-agent work orders. | `build_work_order_prompt`, `decompose_plan`, `format_work_orders` | PR #78 (5cc11a3) |
| `integrator.py` | 325 | Wave integrator for Loop 2 -- merges sub-agent work, runs tests, handles failures. | `collect_wave_files`, `stage_files`, `run_test_suite`, `diagnose_failure` | PR #33 (bd23cc4) |
| `feature.py` | 696 | Loop 2 feature-build orchestration and persisted build state. | `feature_state_path`, `feature_log_dir`, `read_feature_state`, `write_feature_state` | PR #78 (5cc11a3) |
| `cli.py` | 670 | CLI entry points: run, test, summarize, verify-cycle, module-map. | `run_nightshift`, `summarize`, `verify_cycle_cli`, `plan_feature` | PR #128 (4e32c37) |
| `__main__.py` | 5 | Entry point for python3 -m nightshift. | `main` | 2802c51 |
| `__init__.py` | 557 | Nightshift -- autonomous overnight codebase improvement agent. | `AGENT_DEFAULT_MODELS`, `BACKEND_DIR_NAMES`, `BACKEND_EXTENSIONS`, `CATEGORY_ORDER` | PR #174 (e92c62f) |

## Dependency Order

Topological order derived from internal `nightshift.*` imports.
`__init__.py` is excluded because it re-exports the package surface.

`errors -> eval_targets -> types -> constants -> shell -> summary -> cleanup -> compact -> coordination -> costs -> module_map -> readiness -> scoring -> state -> config -> multi -> e2e -> profiler -> worktree -> cycle -> evaluation -> planner -> subagent -> decomposer -> integrator -> feature -> cli -> __main__`

## Recent Shipped Sessions

- PR #175: fix: stale .next-id silent-drop and autonomy score fabrication bypass
- PR #174: fix: address review findings -- extract git_status_short, fix swapped test args, fix docs
- PR #173: security: close prompt-alert pre-poisoning path (pentest W1)
- PR #172: security: close open_pr_data injection vector in daemon.sh sed sanitizers (#0182)
- PR #171: overseer: add 4 pentest tasks from 2026-04-06 scan + update handoff
