# Nightshift Operations Guide

You are an AI agent starting a session in the Nightshift repo. This document is your map. It explains every system, every folder, every file, and exactly how to use, update, and maintain each one.

You should have already read `.recursive/handoffs/LATEST.md` before this file. If you haven't, read it first — it's shorter and tells you what to do next. This document is the full reference for every system in the repo.

---

## The Repo at a Glance

```
Nightshift/
├── nightshift/                  ← THE PRODUCT (Python package)
│   ├── core/                    ← Core modules (constants, errors, shell, state, types)
│   ├── settings/                ← Config + eval targets
│   ├── owl/                     ← Cycle logic (cycle, readiness, scoring, eval_runner)
│   ├── raven/                   ← Loop 2 modules (planner, decomposer, subagent, integrator, etc.)
│   ├── infra/                   ← Infrastructure (module_map, multi, release, worktree)
│   ├── scripts/                 ← Shell wrappers (check.sh, install.sh, run.sh, test.sh, smoke-test.sh)
│   ├── tests/                   ← Product test suite
│   ├── schemas/                 ← JSON schemas
│   ├── assets/                  ← Static assets
│   ├── cli.py                   ← Entry points + main loop
│   ├── __init__.py              ← Re-exports all public names
│   ├── __main__.py              ← Package entry point (python3 -m nightshift)
│   ├── SKILL.md                 ← The hardening skill prompt
│   └── README.md                ← Product documentation
├── .recursive/                   ← THE FRAMEWORK (portable across projects)
│   ├── engine/                  ← Daemon loop (daemon.sh, lib-agent.sh, pick-role.py, watchdog.sh)
│   ├── operators/               ← Role prompts (build, review, oversee, strategize, achieve, security-check)
│   ├── prompts/                 ← Global prompts (autonomous.md, checkpoints.md)
│   ├── agents/                  ← Sub-agent definitions (code-reviewer, docs-reviewer, etc.)
│   ├── lib/                     ← Framework Python lib (costs, cleanup, compact, config, evaluation)
│   ├── scripts/                 ← Framework scripts (validate-tasks.sh, list-tasks.sh, init.sh, rollback.sh)
│   ├── templates/               ← Templates (handoff, task, evaluation, session-index, project-config)
│   ├── tests/                   ← Framework test suite
│   ├── ops/                     ← Operations guides (this file, DAEMON.md, PRE-PUSH-CHECKLIST.md, ROLE-SCORING.md)
│   ├── CLAUDE.md                ← Framework agent instructions
│   └── AGENTS.md                ← Agent configuration reference
├── .recursive/                  ← WORKING MEMORY (project-specific runtime state)
│   ├── handoffs/                ← Short-term memory (read LATEST.md first every session)
│   ├── tasks/                   ← Task queue (pending/done/blocked)
│   ├── sessions/                ← Daemon session logs (stream-json + index)
│   ├── evaluations/             ← Self-evaluation reports
│   ├── learnings/               ← Cross-session knowledge
│   ├── healer/                  ← System health observations
│   ├── autonomy/                ← Autonomy score reports
│   ├── strategy/                ← Strategy reports
│   ├── reviews/                 ← Code review reports
│   ├── architecture/            ← Generated module map
│   ├── vision/                  ← Long-term direction
│   ├── vision-tracker/          ← Progress scoreboard
│   ├── changelog/               ← Per-version release notes
│   └── plans/                   ← Feature plans
├── Runtime/                     ← RUNTIME ARTIFACTS (shift logs, state files, worktrees)
├── CLAUDE.md                    ← Agent instructions (always loaded)
├── AGENTS.md                    ← Agent configuration reference
├── .recursive.json              ← Project config (project name, commands, agents)
├── .nightshift.json.example     ← Per-repo config template
├── pyproject.toml               ← Project config (mypy, ruff, pytest)
├── requirements-dev.txt         ← Pinned dev tool versions
├── Makefile                     ← Build targets (test, check, daemon, etc.)
└── .github/workflows/ci.yml     ← CI pipeline
```

---

## System -1: Evaluations (`.recursive/evaluations/`)

### What it is
Self-scoring. After every merge, the agent runs Nightshift against Phractal and scores itself across 10 dimensions. Failures become tasks.

### Files
| File | Purpose |
|------|---------|
| `README.md` | Scorecard (10 dimensions), report format, threshold rules |
| `NNNN.md` | Individual evaluation reports (sequential numbers) |

### How it works (cross-session, not self-grading)
1. Session N merges a PR, writes handoff with "Evaluate" flag
2. Session N+1 starts, reads the handoff, sees the evaluation flag
3. Session N+1 runs Step 0: clones Phractal, runs 2-cycle test shift
4. Session N+1 reads shift log + state + runner log (from the test shift, not from session N)
5. Scores 10 dimensions (startup, discovery, fix quality, shift log, state file, verification, guard rails, clean state, breadth, usefulness)
6. Writes report to `.recursive/evaluations/NNNN.md`
7. Any dimension below 6/10 becomes a task in `.recursive/tasks/`
8. Session N+1 then proceeds to its own build task

The agent that evaluates is NOT the agent that built the feature. This prevents grading your own homework.

### How to update
- When you add a new evaluation dimension: update the scorecard in `README.md`
- When you improve scoring criteria: update the dimension descriptions
- The score should trend upward over time as fixes land

---

## System 0: Task Queue (`.recursive/tasks/`)

### What it is
The work queue. Numbered task files. The agent picks up the lowest-numbered `pending` task. Humans add tasks by creating the next numbered file.

### Files
| File | Purpose |
|------|---------|
| `GUIDE.md` | Full format spec, field definitions, rules |
| `.next-id` | Next available task number (atomic ID allocation) |
| `NNNN.md` | Individual task files (0001.md, 0002.md, ...) |
| `archive/` | Completed tasks (auto-moved by daemon housekeeping) |

### How to use (human)

**Preferred: create a GitHub Issue** with the `task` label. The daemon syncs issues to task files automatically during housekeeping. Add `urgent`, `low`, `integration`, or vision section labels as needed. See `.recursive/tasks/GUIDE.md` for the full label mapping.

```bash
gh issue create --title "Add dark mode" --label "task"
gh issue create --title "Fix CI" --label "task,urgent"
```

**Alternative: create the file directly.**
1. Read `.next-id` for the next number. Use it, increment, write back.
2. Create the task file with `status: pending` in frontmatter
3. Done. The agent picks it up. **Never scan the directory to guess the next number.**

### How to use (agent)
1. Read all `.md` files in `.recursive/tasks/` (skip GUIDE.md, README.md, archive/)
2. Filter to `status: pending`
3. Skip tasks tagged `environment: integration` (require external resources)
4. Pick the lowest-numbered pending task (urgent priority first)
5. If the latest Step 0 evaluation in `.recursive/evaluations/` scored below `80/100`, prefer an eval-related pending internal task before any other normal-priority task
6. Set `status: in-progress` when starting, `status: done` when finished
7. If blocked, set `status: blocked` with `blocked_reason:` (environment | dependency | design)
8. If no pending internal tasks, fall back to the priority engine in `.recursive/operators/build/SKILL.md`
9. If ALL remaining tasks are integration or blocked, log in handoff and exit cleanly

### Task fields
See `.recursive/tasks/GUIDE.md` for full field definitions: `status`, `priority`, `environment`, `blocked_reason`, `needs_human`, `skipped_by`, `target`

### How to update
- When you finish a task: set `status: done`, add `completed: YYYY-MM-DD`
- Done tasks are auto-archived to `archive/` by daemon housekeeping
- If a task is too big: mark it done with a note, create follow-up tasks
- When creating tasks: use `.next-id`, commit it alongside the task file

---

## System 1: Handoffs (`.recursive/handoffs/`)

### What it is
Your short-term memory. Instead of reading the entire repo every session, you read ONE file and know exactly where things stand.

### Files
| File | Purpose |
|------|---------|
| `LATEST.md` | The most recent handoff. **Read this first every session.** |
| `NNNN.md` | Individual session handoffs (0001.md, 0002.md, ...) |
| `README.md` | Format spec and rules |
| `weekly/week-YYYY-WNN.md` | Compacted weekly summaries |

### How to use
1. **Start of session**: Read `LATEST.md`. It tells you what was built, what's broken, what to build next, and which files to look at.
2. **End of session**: Write a new handoff `NNNN.md` (increment the number). Copy it to `LATEST.md`.
3. **Compaction**: When 7+ numbered files exist, merge them into `weekly/week-YYYY-WNN.md` and delete the originals. Keep only what's still relevant.

### Format
```markdown
# Handoff #NNNN
**Date**: YYYY-MM-DD
**Version**: vX.X.X
**Session duration**: ~Xh

## What I Built
## Decisions Made
## Known Issues
## Current State
## Next Session Should
## Where to Look
```

### Rules
- Carry forward known issues from the previous handoff if you didn't fix them
- Drop resolved items
- Be ruthless about brevity — if the next agent doesn't need it, don't write it
- Always update LATEST.md after writing your handoff

---

## System 2: Vision Docs (`.recursive/vision/`)

### What it is
The north star. Describes what Nightshift is becoming: two autonomous loops and a self-maintaining repo. Written for AI agents — explains the architecture, gives examples, lists open problems.

### Files
| File | Purpose |
|------|---------|
| `00-overview.md` | The full vision: both loops, meta-prompt, architecture, success criteria |
| `01-loop1-hardening.md` | Loop 1 deep dive: what exists, what's enforced, 6-item improvement roadmap |
| `02-loop2-feature-builder.md` | Loop 2 deep dive: phases, sub-agent architecture, open design questions |

### How to use
- **Read when**: The handoff points you here, or you need to understand the big picture before making a design decision.
- **Don't read when**: The handoff has enough context for your task. Save tokens.

### How to update
- When you complete a roadmap item, mark it done in the relevant file
- When you make a design decision for Loop 2, update the open questions section
- When you discover a new problem or pattern, add it to the relevant file
- Keep the tone: written for an AI agent who has never seen the repo

---

## System 3: Vision Tracker (`.recursive/vision-tracker/`)

### What it is
A scoreboard showing progress toward the vision. Progress bars for every component across all four areas: Loop 1, Loop 2, Self-Maintaining, Meta-Prompt.

### Files
| File | Purpose |
|------|---------|
| `TRACKER.md` | The single tracker file with all progress bars |

### How to use
- **Read when**: Start of session (in the handoff, the percentages come from here). Or when you need to decide what to build next.

### How to update
Every session, after you finish building:
1. Check each component you affected
2. Update its status: `Not started` → `In progress` → `Done`
3. Update its progress bar: `░` for not done, `█` for done (20 chars = 100%)
4. Recalculate section percentages: `(done components / total components) * 100`
5. Recalculate overall: weighted average (Loop 1: 40%, Loop 2: 30%, Self-Maintaining: 15%, Meta-Prompt: 15%)
6. Update "Last updated" date

### Rules
- Don't inflate progress. If something is half-done, say "In progress" with honest percentage.
- If you broke something, move it back.
- "Done" means: code exists, tests pass, it works in a real run.

---

## System 3a: Module Map (`.recursive/architecture/`)

### What it is
A generated architecture index for `nightshift/*.py`. It gives future sessions a
single file with module purposes, key symbols, dependency order, and recent
shipped-session summaries so they do not have to rediscover the package from
scratch.

### Files
| File | Purpose |
|------|---------|
| `MODULE_MAP.md` | Generated module inventory, dependency order, and recent merged-session summaries |

### How to use
- **Read when**: Your task touches `nightshift/*.py` and you need fast orientation before opening individual modules.
- **Refresh when**: Any session changes `nightshift/*.py`, module exports, or dependency flow.
- **Command**: `python3 -m nightshift module-map --write`

### Rules
- Treat `MODULE_MAP.md` as generated output. Refresh it with the CLI command instead of hand-editing rows.
- If the module count or dependency order changes, update `CLAUDE.md` and any affected ops docs in the same session.
- The healer treats the map as stale if it goes 5+ sessions without a refresh.

---

## System 4: Changelog (`.recursive/changelog/`)

### What it is
Per-version release notes. One file per version. Documents what was added, changed, fixed, removed.

### Files
| File | Purpose |
|------|---------|
| `README.md` | Index with version table and contributor guide |
| `v0.0.1.md` | Initial Beta release notes |
| `v0.0.2.md` | Control Plane release notes |
| `vX.X.X.md` | Future versions — one file each |

### How to use
- **Read when**: You need to understand what changed in a specific version.

### How to update
After every session:
1. Find the current version file (check `README.md` table for "In progress")
2. Add your changes under the right section: `Added`, `Changed`, `Fixed`, `Removed`, `Internal`
3. Tag each entry: `[feat]`, `[fix]`, `[refactor]`, `[test]`, `[docs]`, `[meta]`, `[remove]`

### When to create a new version file
When all planned features for the current version are done:
1. Update current version status to "Released" in `README.md`
2. Create new `vX.X.X.md` with a codename and "In progress" status
3. Add it to the `README.md` table
4. Tag and release on GitHub

---

## System 5: Operators and Prompts (`.recursive/operators/`, `.recursive/prompts/`)

### What it is
The operator prompts that define each daemon role. Each operator lives in its own directory under `.recursive/operators/` with a `SKILL.md` file. The global autonomous-mode prompt is `.recursive/prompts/autonomous.md`.

### Files
| File | Purpose |
|------|---------|
| `.recursive/operators/build/SKILL.md` | Builder prompt (v1 daemon). In v2, the brain delegates to `.recursive/agents/build.md`. |
| `.recursive/operators/review/SKILL.md` | Code review operator. |
| `.recursive/operators/oversee/SKILL.md` | Overseer operator. Audits task queue. |
| `.recursive/operators/strategize/SKILL.md` | Strategist operator. Big-picture planning. |
| `.recursive/operators/achieve/SKILL.md` | Autonomy operator. |
| `.recursive/operators/security-check/SKILL.md` | Red-team operator. |
| `.recursive/operators/evolve/SKILL.md` | Framework improvement operator. Fixes .recursive/ friction patterns. |
| `.recursive/operators/audit/SKILL.md` | Framework audit operator. Reviews .recursive/ for contradictions and staleness. |
| `.recursive/prompts/autonomous.md` | Global autonomous-mode constraints (used by v1 daemon). |
| `.recursive/prompts/checkpoints.md` | Checkpoint prompt for session progress tracking. |

**v2 agents** (used by the brain in the current architecture):

| File | Purpose |
|------|---------|
| `.recursive/agents/brain.md` | Brain orchestrator (Opus). Reads dashboard, delegates, reviews PRs. |
| `.recursive/agents/build.md` | Build sub-agent (Sonnet). Implements tasks, creates PRs. |
| `.recursive/agents/review.md` | Review sub-agent. Deep code review, fixes issues. |
| `.recursive/agents/oversee.md` | Oversee sub-agent. Audits task queue. |
| `.recursive/agents/strategize.md` | Strategize sub-agent. Big-picture analysis. |
| `.recursive/agents/achieve.md` | Achieve sub-agent. Autonomy engineering. |
| `.recursive/agents/security.md` | Security sub-agent. Red team / pentest. |
| `.recursive/agents/evolve.md` | Evolve sub-agent. Framework friction fixes. |
| `.recursive/agents/audit-agent.md` | Audit sub-agent. Framework quality review + pattern analysis. |
| `.recursive/agents/code-reviewer.md` | Code review specialist (read-only, no worktree). |
| `.recursive/agents/safety-reviewer.md` | Security review specialist (read-only). |
| `.recursive/agents/architecture-reviewer.md` | Architecture review specialist (read-only). |
| `.recursive/agents/docs-reviewer.md` | Docs review specialist (read-only). |
| `.recursive/agents/meta-reviewer.md` | Framework PR review specialist (read-only). |

### How to use
- In v2: the brain reads agent definitions from `.recursive/agents/` and delegates via the Agent() tool.
- In v1 (legacy): the daemon loaded the winning role's `SKILL.md` directly.
- If you learn something that would help future sessions, update the relevant agent definition in `.recursive/agents/`.

### How to update
- If a step is consistently causing problems, fix the instructions in the relevant operator
- If you discover a better priority order, update the priority engine in the build operator
- If new systems are added (like this ops guide), add them to the reading list
- Keep the prompts tight — every line should earn its place

---

## System 5a: Healer Observations (`.recursive/healer/`)

### What it is
The healer is no longer a standalone daemon step. It was merged into the
builder workflow, so every builder session now performs system observation in
Step 6n ("Observe the System") and Step 6o ("Generate Work") of
`.recursive/operators/build/SKILL.md`.

### Files
| File | Purpose |
|------|---------|
| `.recursive/healer/log.md` | Current healer history written by builder sessions; newest entries stay live for fast reads |
| `.recursive/healer/archive/*.md` | Monthly archive files created by housekeeping when old healer entries rotate out of the live log |
| `.recursive/operators/build/SKILL.md` (Step 6n/6o) | Builder-side observation steps that replaced the standalone healer |

### How it works
1. The builder reads recent sessions, cost analysis, the task queue, the vision tracker, the module map, and the existing healer log.
2. It appends a new dated entry to `.recursive/healer/log.md` with a health label (`good`, `caution`, or `concern`).
3. Daemon housekeeping keeps the live healer log bounded by rotating older top-level entries into `.recursive/healer/archive/YYYY-MM.md`.
4. If the observation reveals actionable gaps, the builder creates follow-up tasks during Step 6o.
5. If the pattern needs human attention, the daemon can escalate with `notify_human`.

### How to inspect healer output
- Read `.recursive/healer/log.md` for the durable observation history.
- Check `.recursive/healer/archive/` when you need older observations that have rotated out of the live log.
- Read the matching builder session log in `.recursive/sessions/*.log` for raw execution details.
- There are no dedicated `*-healer.log` session files anymore; the old standalone healer flow was removed when the observation step moved into the builder prompt.

### How to change or disable it
- There is no standalone on/off shell toggle anymore.
- To change or disable the healer behavior, edit the builder prompt in `.recursive/operators/build/SKILL.md` (Step 6n / Step 6o).

### Legacy note
Older docs and tasks may still mention `persist_healer_changes()` in
`.recursive/engine/lib-agent.sh`. That helper was removed when task `#0061` merged healer
output into the normal builder session flow. Treat any remaining references to
that function as historical context, not current behavior.

---

## System 6: The Product (`nightshift/`)

### What it is
The Python package that IS Nightshift. The overnight hardening runner.

### Modules (organized by subpackage)

**`nightshift/core/`** -- Core infrastructure
| Module | Responsibility | Key functions |
|--------|---------------|---------------|
| `types.py` | TypedDicts for all data structures | `NightshiftConfig`, `ShiftState`, `CycleResult`, `CycleVerification` |
| `constants.py` | Constants + utilities | `DATA_VERSION`, `DEFAULT_CONFIG`, `SHIFT_LOG_TEMPLATE`, `now_local()`, `print_status()` |
| `errors.py` | Exception class | `NightshiftError` |
| `shell.py` | Subprocess execution | `run_command()`, `run_capture()`, `git()`, `command_exists()`, `run_shell_string()` |
| `state.py` | State I/O + mutation | `load_json()`, `write_json()`, `read_state()`, `append_cycle_state()`, `top_path()` |

**`nightshift/settings/`** -- Configuration
| Module | Responsibility | Key functions |
|--------|---------------|---------------|
| `config.py` | Config + agent resolution | `merge_config()`, `resolve_agent()`, `prompt_for_agent()`, `infer_package_manager()`, `infer_verify_command()` |
| `eval_targets.py` | Repo-specific evaluation defaults | `infer_target_verify_command()` |

**`nightshift/owl/`** -- Cycle logic (Loop 1)
| Module | Responsibility | Key functions |
|--------|---------------|---------------|
| `cycle.py` | Per-cycle logic | `build_prompt()`, `command_for_agent()`, `verify_cycle()`, `evaluate_baseline()`, `extract_json()`, `blocked_file()` |
| `eval_runner.py` | Evaluation runner (dry-run + full) | `run_eval_dry_run()`, `run_eval_full()`, `score_artifacts()`, `format_eval_table()` |
| `readiness.py` | Readiness checks | |
| `scoring.py` | Post-cycle diff scoring | `score_diff()`, `diff_line_score()`, `has_test_files()` |

**`nightshift/raven/`** -- Loop 2 modules
| Module | Responsibility | Key functions |
|--------|---------------|---------------|
| `profiler.py` | Repo analysis | `profile_repo()` |
| `planner.py` | Feature planning | `build_plan_prompt()`, `validate_plan()`, `parse_plan()`, `execution_order()`, `format_plan()`, `scope_check()` |
| `decomposer.py` | Task decomposition | `decompose_plan()`, `build_work_order_prompt()`, `format_work_orders()` |
| `subagent.py` | Sub-agent spawner | `spawn_task()`, `spawn_wave()`, `format_wave_result()` |
| `integrator.py` | Wave integration | `integrate_wave()`, `collect_wave_files()`, `stage_files()`, `run_test_suite()`, `diagnose_failure()`, `format_integration_result()` |
| `feature.py` | Build CLI command | |
| `coordination.py` | Wave coordination | |
| `e2e.py` | End-to-end orchestration | |
| `summary.py` | Summary generation | |

**`nightshift/infra/`** -- Infrastructure
| Module | Responsibility | Key functions |
|--------|---------------|---------------|
| `module_map.py` | Module map generation | |
| `multi.py` | Multi-repo orchestration | `run_multi_shift()`, `validate_repos()`, `format_multi_summary()` |
| `release.py` | Auto-release version tagging | `check_and_release()`, `find_releasable_version()` |
| `worktree.py` | Git worktree lifecycle | `ensure_worktree()`, `ensure_shift_log()`, `sync_shift_log()`, `revert_cycle()`, `cleanup_safe_artifacts()` |

**`nightshift/`** -- Top-level
| Module | Responsibility | Key functions |
|--------|---------------|---------------|
| `cli.py` | Entry points + main loop | `run_nightshift()`, `summarize()`, `verify_cycle_cli()`, `plan_feature()`, `build_parser()`, `main()` |
| `__main__.py` | Package entry point | `python3 -m nightshift` |
| `__init__.py` | Re-exports all public names | Everything above |

**`.recursive/lib/`** -- Framework library (NOT in the nightshift product package)
| Module | Responsibility | Key functions |
|--------|---------------|---------------|
| `costs.py` | Session cost tracking | `record_session()`, `parse_session_tokens()`, `calculate_cost()`, `read_ledger()`, `write_ledger()`, `total_cost()`, `format_session_cost()`, `default_ledger_path()` |
| `cleanup.py` | Daemon housekeeping | `rotate_logs()`, `rotate_healer_log()`, `prune_orphan_branches()` |
| `compact.py` | Handoff compaction | `compact_handoffs()` |
| `config.py` | Framework config | |
| `evaluation.py` | Evaluation orchestration | |

### Dependency flow (nightshift package)
```
core/errors → settings/eval_targets → core/types → core/constants → core/shell → raven/summary → raven/coordination → infra/module_map → owl/readiness → owl/scoring → core/state → settings/config → infra/multi → raven/e2e → raven/profiler → infra/worktree → owl/cycle → raven/planner → raven/subagent → raven/decomposer → raven/integrator → raven/feature → cli
```
No circular imports. Each module only imports from modules to its left. `multi.py` receives the `run_nightshift` callable from `cli.py` via dependency injection to avoid circular deps.

Note: `cleanup.py`, `compact.py`, `costs.py`, `evaluation.py`, and `config.py` (framework config) now live in `.recursive/lib/`, not in the nightshift product package.

### How to modify
1. Read the module you're changing AND its callers
2. Follow existing patterns (look at how similar functions are structured)
3. Add types to `types.py` if you're introducing new data structures
4. Write tests in `nightshift/tests/test_nightshift.py`
5. Run full suite: `python3 -m pytest nightshift/tests/ -v`

---

## System 7: Tests (`nightshift/tests/`)

### What it is
915 pytest tests covering every pure function, config, state, CLI, and integration.

### Files
| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `test_nightshift.py` | All tests (organized by class: `TestConstants`, `TestExtractJson`, `TestBuildPrompt`, etc.) |

### How to run
```bash
python3 -m pytest nightshift/tests/ -v                    # full suite
python3 -m pytest nightshift/tests/ -v -k "TestBuildPrompt"  # specific class
```

### How to add tests
1. Find the test class for the module you're testing (or create one)
2. Write test methods following existing patterns
3. Use `tmp_path` fixture for filesystem tests
4. Use `unittest.mock.patch` for stdin/tty mocking
5. Run the full suite — make sure nothing else broke

---

## System 8: CI/CD

### Files
| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` | GitHub Actions pipeline |
| `nightshift/scripts/check.sh` | Local CI (mirrors the GH Actions pipeline) |
| `pyproject.toml` | mypy strict, ruff rules, pytest config |
| `requirements-dev.txt` | Pinned dev tool versions |

### Pipeline stages
1. **Lint** — `ruff check` + `ruff format --check`
2. **Type check** — `mypy --strict`
3. **Test** — `pytest` on Python 3.9 + 3.12
4. **Integration** — dry-run both agents
5. **Validate artifacts** — schema/config parsing, install.sh references, shell syntax

### How to run locally
```bash
bash nightshift/scripts/check.sh
```

### Post-merge health
After a PR merges and `gh run list --branch main --limit 1` shows green CI on `main`, run:

```bash
python3 -m nightshift run --dry-run --agent codex > /dev/null
python3 -m nightshift run --dry-run --agent claude > /dev/null
```

Do not report the session as successful until both dry-runs pass on `main`.

---

## System 8b: Pre-Push Checklist (`.recursive/ops/PRE-PUSH-CHECKLIST.md`)

### What it is
A mandatory checklist the agent runs through before every `git push`. Catches forgotten doc updates, missing handoffs, stale tracker percentages, and unstaged files.

### How to use
Before pushing, read the checklist and answer every item. Output the results in the session. If anything fails, fix it. Then push.

### When it runs
- Automatically: the build operator (Step 7) mandates it before every commit/push
- Manually: if you're pushing outside the build workflow, read it yourself

---

## System 9: CLAUDE.md

### What it is
The file Claude Code always loads at session start. Contains project description, structure, architecture, conventions.

### How to update
- When you add/remove/rename modules: update the project structure section
- When you change conventions: document them
- When you add new systems: add them to the structure
- Keep it factual — this is reference, not narrative

---

## System 10: Skill + Schema

### Files
| File | Purpose |
|------|---------|
| `nightshift/SKILL.md` | The prompt injected into agent cycles during hardening shifts. Discovery strategies, priority order, fix/log framework, safety rails, shift log template. |
| `nightshift.schema.json` | JSON Schema for structured agent output. Codex uses `--output-schema`. Claude parses with `extract_json()`. |
| `.nightshift.json.example` | Config template users copy to their repos |
| `.recursive.json` | This repo's project config (project name, commands, agents) |

### How to update nightshift/SKILL.md
- Edit to change agent behavior during hardening shifts
- Keep YAML frontmatter (`name`, `description`) — the `description` controls when the skill triggers
- The shift log template is in `constants.py`, not SKILL.md

---

## System 11: Shell Scripts + Installer

### Files
| File | Purpose |
|------|---------|
| `nightshift/scripts/run.sh` | Sets PYTHONPATH, runs `python3 -m nightshift run "$@"` |
| `nightshift/scripts/test.sh` | Sets PYTHONPATH, runs `python3 -m nightshift test "$@"` |
| `.recursive/scripts/list-tasks.sh` | Summarizes active tasks and flags malformed task files |
| `.recursive/scripts/validate-tasks.sh` | Validates numbered task frontmatter and reports missing/invalid required fields |
| `nightshift/scripts/install.sh` | Downloads entire package to `~/.codex/skills/nightshift/` and `~/.claude/skills/nightshift/` |
| `.recursive/engine/daemon.sh` | Unified daemon. Loops, picks role, runs pentest preflight, then executes the selected role. |
| `.recursive/engine/lib-agent.sh` | Shared shell helpers used by daemon entrypoints |
| `.recursive/engine/pick-role.py` | Role scoring and selection |
| `.recursive/engine/watchdog.sh` | Daemon watchdog for crash recovery |
| `nightshift/scripts/smoke-test.sh` | End-to-end test against a real repo (default: Phractal). Proves the system works, not just unit tests. |
| `.recursive/scripts/rollback.sh` | Reverts a merged PR cleanly. Creates revert branch + PR. |

### Unified Daemon

```bash
make daemon       # Unified daemon: picks role each cycle (build/review/oversee/strategize/achieve)
```

Runs via tmux in production. See `.recursive/ops/DAEMON.md` for the complete operations guide: starting, monitoring, stopping, troubleshooting, and the recommended daily workflow.

Only one daemon runs at a time (shared lockfile).

### Shared daemon helpers (`.recursive/engine/lib-agent.sh`)

| Function | Purpose |
|------|---------|
| `run_agent()` | Normalized Claude/Codex invocation with JSONL logging |
| `extract_result_summary()` | Pulls a bounded handoff out of a stream-json log so one agent run can brief the next |
| `cleanup_old_logs()` | Rotates stale daemon log files via `.recursive/lib/cleanup.py:rotate_logs()` |
| `cleanup_healer_log()` | Rotates older healer entries into `.recursive/healer/archive/` via `.recursive/lib/cleanup.py:rotate_healer_log()` |
| `cleanup_orphan_branches()` | Removes remote Nightshift branches that no longer have open PRs |
| `compact_handoffs()` | Rolls older numbered handoffs into weekly summaries |
| `archive_done_tasks()` | Moves completed task files into `.recursive/tasks/archive/` |
| `sync_github_tasks()` | Mirrors GitHub issues labeled `task` into `.recursive/tasks/` files |
| `should_evaluate()` / `run_evaluation()` | Detects the handoff evaluation flag and runs the prescribed Step 0 evaluation |
| `notify_human()` | Best-effort GitHub issue + optional webhook escalation for human attention |

`persist_healer_changes()` is intentionally absent from this table because the
function was removed. Healer persistence now happens inside the builder session
when Step 6n/6o appends to `.recursive/healer/log.md` and commits the result as part
of the normal session workflow.

### How to update
- If you add a new Python module, add it to the `PACKAGE_FILES` list in `nightshift/scripts/install.sh`
- Shell scripts are thin wrappers — almost never need editing
- If you change the builder's pentest/fixer handshake, update both `.recursive/operators/security-check/SKILL.md` and `.recursive/ops/DAEMON.md`
- Always run `bash -n path/to/script.sh` to syntax-check after editing

---

## System 12: Runtime Artifacts (`Runtime/Nightshift/` + isolated test roots)

### What it is
Created when Nightshift runs. Full overnight `run` sessions use repo-local
`Runtime/Nightshift/`; `test`/evaluation sessions keep their machine-readable
artifacts and linked worktrees under `$TMPDIR/nightshift-test-runs/...` so the
target checkout stays clean.

### Files (generated at runtime)
| File | Purpose | Git status |
|------|---------|------------|
| `YYYY-MM-DD.md` | Shift log (human-readable) | Committed to nightshift branch for `run`; lives in the isolated worktree for `test` |
| `YYYY-MM-DD.state.json` | Machine-readable state | Gitignored / temp-root for `test` |
| `YYYY-MM-DD.runner.log` | Raw runner output | Gitignored / temp-root for `test` |
| `worktree-YYYY-MM-DD/` | Isolated git worktree | Gitignored in `run`; temp-root for `test` |

### How to clean up after a test run
```bash
git worktree remove "$TMPDIR"/nightshift-test-runs/<repo>-<hash>/worktree-YYYY-MM-DD
git branch -d nightshift/YYYY-MM-DD
rm -rf "$TMPDIR"/nightshift-test-runs/<repo>-<hash>
```

---

## Git Workflow

### Branching strategy
- **`main` is protected.** Never push directly to main.
- Every session creates a feature branch: `feat/description`, `fix/description`, `docs/description`, `release/vX.X.X`
- Push the branch, create a PR, review with a sub-agent, merge if it passes.

### The PR flow (you do this every session)
```
1. Create branch:    git checkout -b feat/diff-scorer
2. Build + test:     (the usual workflow)
3. Commit:           git add [files] && git commit -m "feat: add diff scorer"
4. Push:             git push origin feat/diff-scorer
5. Create PR:        gh pr create --title "feat: add diff scorer" --body "..."
6. Review:           spawn a sub-agent to review the diff (see below)
7. Merge:            gh pr merge --merge --delete-branch --admin (if review passes)
8. Clean up:         git checkout main && git pull && git branch -d feat/diff-scorer
```

### Sub-agent PR review
Before merging, spawn a sub-agent with this task:
```
Review this PR for: bugs, logic errors, security issues, missing tests, 
convention violations, and whether it matches the stated goal. 
Read the diff with `gh pr diff <number>`. 
Report: PASS (merge it) or FAIL (list what needs fixing).
```
If the review says FAIL, fix the issues, push again, re-review. Only merge on PASS.

**Review notes MUST become tasks.** If the review passes but flags advisory notes, known limitations, or follow-up suggestions, you MUST either fix them before merging OR create follow-up tasks in `.recursive/tasks/` with the exact issue and acceptance criteria. "Known limitation" is not a valid disposition — the task queue exists to track deferred work. Dismissing a review note without a task means it disappears from the system's memory.

### Merge strategy
- **Always use regular merge** (`--merge`), never `--squash`. Every commit on the branch must be preserved on main. If you made 10 commits, all 10 appear in main's history.
- **Always use `--admin` flag** when merging PRs. The agent is the sole creator, maintainer, and admin of this repo. No human review approval is required. The sub-agent code review replaces human review.
- Example: `gh pr merge --merge --delete-branch --admin`

---

## Release Strategy

### When to release
You decide. Here are the rules:

**Patch release (v0.0.X → v0.0.X+1):**
- Bug fixes only
- No new features
- Example: fixed `merge_config` shallow update, fixed `run_command` timeout

**Minor release (v0.X.0 → v0.X+1.0):**
- New features that change what Nightshift can do
- Example: added diff scorer, added Loop 2 scaffolding, added multi-repo support

**Major release (v1.0.0):**
- Loop 1 and Loop 2 both work in production
- Not happening anytime soon

### How to decide
After merging a PR, ask yourself:
1. **Is this a meaningful user-facing change?** If someone installed Nightshift yesterday, would they want this update? → Release.
2. **Is this just internal cleanup?** Tests, docs, refactors that don't change behavior? → Don't release. Batch with the next real change.
3. **Is this a bug fix for something that affects users?** → Patch release immediately.
4. **Did I just finish a planned milestone?** Check the version changelog — are all planned items done? → Release.

### How to release

Release commits are the ONE exception to the PR rule. They go directly on main because they're purely ceremonial (changelog status change + tag).

```bash
# 0. Verify tests pass on the exact commit you're tagging
make check

# 1. Update changelog: mark current version as "Released", create next version file
# 2. Update changelog README table
# 3. Commit directly on main:
git add .recursive/changelog/
git commit -m "release: vX.X.X -- Codename"

# 4. Tag and push
git tag vX.X.X
git push origin main && git push origin vX.X.X

# 5. Create GitHub release
#    Release notes MUST include:
#      a) A highlights/summary section at the top
#      b) The FULL changelog from .recursive/changelog/vX.X.X.md below it
#    The release page must be self-contained — no "see file for details" links.
gh release create vX.X.X \
  --title "vX.X.X -- Codename" \
  --notes "$(cat <<EOF
## Highlights
- [curated summary bullets]

---

$(cat .recursive/changelog/vX.X.X.md)
EOF
)"
```

Or: `make release VERSION=X.X.X CODENAME=Name`

---

## Version Milestones

What defines each version. Use this to know when a release is ready.

### v0.0.2 — Control Plane (current)
- [x] Python orchestrator replacing bash
- [x] Pluggable agent adapters (Codex + Claude)
- [x] Runner-enforced guard rails
- [x] Machine-readable state
- [x] 123-test suite
- [x] Vision docs + self-improving prompt
- [x] Changelog + tracker + handoffs + ops guide
- [ ] Commit and push to main
- [ ] Tag and release on GitHub

### v0.0.3 — Intelligence (released)
- [x] Fix `merge_config` shallow update (security bug)
- [x] Fix `run_command` timeout race (reliability bug)
- [x] Post-cycle diff scorer
- [x] Cycle-to-cycle state injection
- [x] Test writing incentives (bonus, originally v0.0.4)
- [x] Backend exploration forcing (bonus, originally v0.0.4)
- [x] Validated against Phractal test target

### v0.0.4 — Agent Quality (released)
- [x] Test writing incentives (shipped in v0.0.3)
- [x] Backend exploration forcing (shipped in v0.0.3)
- [x] Smarter category balancing
- [x] Fix shift-log-in-commit verification for codex

### v0.0.5 — Multi-Repo (released)
- [x] Multi-repo support (`nightshift multi` subcommand)

### v0.0.6 — Loop 2 Foundation
- [x] Repo profiling module (`nightshift/profiler.py`)
- [x] Feature planner module (`nightshift/planner.py`)
- [x] Task decomposer module (`nightshift/decomposer.py`)
- [x] Sub-agent spawner module (`nightshift/subagent.py`)
- [x] Wave integrator module (`nightshift/integrator.py`)
- [x] `nightshift build` CLI command (`nightshift/feature.py` -- build/status/resume)

### v1.0.0 — Production
- [ ] Loop 1 runs reliably overnight on real repos
- [ ] Loop 2 can build a simple feature end-to-end
- [ ] Both loops tested on 3+ real repos

---

## Error Recovery

Things go wrong. Here's what to do.

### Dirty worktree from a crashed session
```bash
# Check if a worktree exists
git worktree list

# Remove it
git worktree remove Runtime/Nightshift/worktree-YYYY-MM-DD --force

# Delete the branch if needed
git branch -D nightshift/YYYY-MM-DD

# Clean up artifacts
make clean
```

### Tests pass locally, fail in CI
1. Check the CI log: `gh run view --log-failed`
2. Common causes:
   - Python version mismatch (CI uses 3.9 + 3.12, you might be on 3.13)
   - Missing dependency (CI installs from `requirements-dev.txt`)
   - File not committed (works locally because it exists, fails in CI because it's not staged)
3. Fix, push, watch CI again

### Handoff is wrong or corrupt
1. Read the previous handoffs (numbered files) to reconstruct state
2. Read `git log --oneline -20` for recent history
3. Read the tracker for current progress
4. Write a corrected LATEST.md

### Agent built the wrong thing
1. Don't panic -- it's on a branch, not main
2. Close the PR: `gh pr close <number>`
3. Delete the branch: `git push origin --delete <branch>`
4. Write a feedback note explaining what went wrong
5. Next session reads the feedback and adjusts

### Bad PR was already merged
1. Use the rollback script: `bash .recursive/scripts/rollback.sh <PR-number>`
2. It creates a revert branch, revert commit, and new PR automatically
3. Review and merge the revert PR

### Merge conflict on PR
1. Pull main: `git checkout main && git pull`
2. Rebase your branch: `git checkout <branch> && git rebase main`
3. Resolve conflicts, continue rebase
4. Force push branch: `git push origin <branch> --force-with-lease`
5. PR auto-updates

---

## Test Target Repo

For end-to-end validation, use the Phractal repo:

```bash
# Clone (one-time)
git clone https://github.com/fazxes/Phractal.git /tmp/nightshift-test-target

# Run a quick test shift
cd /tmp/nightshift-test-target
python3 -m nightshift test --agent claude --cycles 2 --cycle-minutes 5

# Check results (use the paths printed at the end of the run)
# Shift log:   ...
# State file:  ...
# Runner log:  ...
```

This is a real full-stack project with real issues. Use it to validate that Loop 1 actually finds and fixes things.

After testing, document results in the handoff: "Tested against Phractal — found X issues, Y were real, Z were false positives."

---

## Environment

### Python
Use whatever `python3` resolves to. The codebase targets Python 3.9+ (the minimum in CI). Do NOT hardcode absolute Python paths in any config or script. If a specific Python is needed for local testing, set it via environment variable, not in committed files.

### Dev tools
Pinned in `requirements-dev.txt`. Install with:
```bash
pip install -r requirements-dev.txt
```

### Quick commands
```bash
make test          # run tests
make check         # full CI locally
make dry-run       # preview cycle prompt
make quick-test    # 2-cycle validation
make clean         # remove runtime artifacts
```

---

## The Session Workflow

Every session follows `.recursive/operators/build/SKILL.md` Steps 1-12. In short:

```
Step 1:  Read handoff (LATEST.md) --> status report
Step 2:  Decide what to build (task queue, eval gate, priority engine)
Step 3:  Propose to human --> wait for "go"
Step 4:  Build + write tests
Step 5:  Verify (make check)
Step 6:  Update ALL docs (handoff, changelog, tracker, vision, CLAUDE.md, etc.)
Step 7:  Pre-push checklist (.recursive/ops/PRE-PUSH-CHECKLIST.md)
Step 8:  Branch, commit, push, PR, sub-agent review, merge
Step 9:  Post-merge health check (CI on main + codex/claude dry-runs)
Step 10: Flag handoff for evaluation (next session scores your work)
Step 11: Release check (is this a milestone?)
Step 12: Report
```

See `.recursive/operators/build/SKILL.md` for the full details of each step. This summary exists for quick reference only — the build operator prompt is authoritative.

---

## Quick Reference: What to Update When

| After you... | Update these |
|---|---|
| Build a feature | handoff, changelog, tracker, tests |
| Fix a bug | handoff, changelog, tracker (if it was tracked) |
| Change project structure | handoff, CLAUDE.md, nightshift/scripts/install.sh, OPERATIONS.md |
| Complete a version milestone | changelog (new version file), tracker, README table, GitHub release |
| Make a design decision | handoff, vision docs (if architectural) |
| Learn something surprising | handoff, relevant operator SKILL.md (if it helps future sessions) |
| Add a new system/doc | this file (OPERATIONS.md), CLAUDE.md |
| Merge a PR | check if release criteria are met |
