# AGENTS.md

## MANDATORY: Session Start

1. **Read `.recursive/handoffs/LATEST.md`** -- What happened last session, what is broken, what to build next. This is your memory.
2. **Read `Recursive/ops/OPERATIONS.md`** on your first session, or when the handoff tells you to. This is the complete map of every system, folder, and file.
3. **Read `.recursive/learnings/INDEX.md`** -- One-line summaries of hard-won knowledge. Only open individual learning files when relevant to your current task. Do NOT read every file -- the index tells you what exists.
4. **Read `.recursive/architecture/MODULE_MAP.md`** when the task touches `nightshift/*.py`. It is the fast orientation map for modules, dependencies, and recent shipped sessions.

Do NOT start building until you have read the handoff.

## What This Is

Nightshift is an autonomous engineering system with two loops:

- **Owl** (`nightshift/owl/`) -- hardening loop. Cycle execution, readiness checks, diff scoring.
- **Raven** (`nightshift/raven/`) -- feature builder. Planning, decomposition, sub-agent coordination, integration.

The `nightshift/` package spawns headless agent cycles in an isolated git worktree, enforces guard rails, verifies each cycle, and tracks state. The orchestration layer lives in `Recursive/`.

Full vision: `.recursive/vision/00-overview.md`

## Quick Reference

```bash
make test        # run tests
make check       # full CI locally (lint + typecheck + test + dry-run + artifacts)
make tasks       # show pending/blocked/in-progress tasks
make clean       # remove runtime artifacts
bash Recursive/engine/daemon.sh claude 60   # start daemon (claude agent, 60-min cycles)
bash Recursive/engine/daemon.sh codex 60    # start daemon (codex agent, 60-min cycles)
python3 -m nightshift module-map --write    # refresh .recursive/architecture/MODULE_MAP.md
```

## Recursive (Orchestration Layer)

The autonomous framework lives in `Recursive/`. It is a separate layer from the `nightshift/` package -- a portable agentic orchestrator that can run on any codebase.

```
Recursive/
  engine/       daemon.sh, pick-role.py, lib-agent.sh, watchdog.sh
  operators/    6 operators (build/review/oversee/strategize/achieve/security-check)
  lib/          costs, cleanup, compact, config, evaluation (standalone Python, zero nightshift deps)
  agents/       sub-agent definitions (code-reviewer, safety, docs, architecture, meta)
  prompts/      autonomous.md (universal rules), checkpoints.md (verification pipeline)
  scripts/      generic utilities (task validation, rollback, init)
  templates/    project scaffolds (handoff, task, eval, session-index, config)
  tests/        tests for Recursive-layer code (pick-role, etc.)
  ops/          OPERATIONS.md, DAEMON.md, PRE-PUSH-CHECKLIST.md, ROLE-SCORING.md
```

Each cycle the engine picks an **operator** based on system signals:
- **build**: picks tasks, builds features, ships PRs. Default.
- **review**: reviews code file by file. After 5+ consecutive builds.
- **oversee**: audits task queue, culls noise. When 50+ pending tasks.
- **strategize**: big picture analysis. Every 15+ sessions.
- **achieve**: measures autonomy (0-100), eliminates human deps. When autonomy low.
- **security-check**: red team preflight before each build.

```bash
# Start the daemon in tmux (recommended -- survives terminal disconnect)
tmux new-session -d -s recursive "caffeinate -s bash Recursive/engine/daemon.sh claude 60"

# Monitor
tmux capture-pane -t recursive -p -S -15
cat .recursive/sessions/index.md
gh pr list --state all --limit 5

# Stop
tmux send-keys -t recursive C-c             # graceful (after current session)
tmux kill-session -t recursive              # immediate
```

**Hot reload:** The daemon re-sources `lib-agent.sh` and checks for `daemon.sh` changes at the start of every loop iteration. Changes take effect next iteration automatically.

**WARNING: The daemon and the monitor/human share the same working directory.** Do not run `git checkout`, `git stash`, or any branch-switching commands while the daemon is mid-session.

**Making changes while the daemon is running:** Use a git worktree in `/tmp`:

```bash
tmux has-session -t recursive 2>&1 && echo "RUNNING" || echo "NOT RUNNING"

# If RUNNING: use a worktree
CHANGE_NAME="example-change"
git worktree add /tmp/nightshift-work origin/main -b "fix/$CHANGE_NAME"
cd /tmp/nightshift-work && git add . && git commit -m "..." && git push origin "fix/$CHANGE_NAME"
gh pr create --head "fix/$CHANGE_NAME" && gh pr merge --merge --delete-branch --admin
git worktree remove /tmp/nightshift-work
```

Full daemon operations guide: `Recursive/ops/DAEMON.md`

## Git Workflow

- **Never push to main directly.** Branch, PR, sub-agent review, merge.
- Branch naming: `feat/`, `fix/`, `docs/`, `refactor/`, `release/`
- **Review notes MUST become tasks.** If the code review sub-agent flags advisory notes, known limitations, or follow-up items but still passes, you MUST create follow-up tasks in `.recursive/tasks/` before merging.
- **If CI fails after merge:** create a `fix/` branch and PR. Never push directly to main, even for "trivial" fixes.
- **After merge:** once CI on `main` is green, run `python3 -m nightshift run --dry-run --agent codex > /dev/null` and `python3 -m nightshift run --dry-run --agent claude > /dev/null` on `main` before reporting success.
- **Human task creation:** Humans create tasks as GitHub Issues with the `task` label. The daemon syncs them to `.recursive/tasks/` automatically.
- **Exception: housekeeping commits push to main directly.** Task sync commits bypass the branch-PR workflow because `git reset --hard origin/main` at cycle start would wipe uncommitted files.
- Full workflow: `Recursive/ops/OPERATIONS.md` under "Git Workflow"

## Environment

- Python 3.9+. Use `python3`. **Never hardcode absolute paths.**
- Dev tools: `pip install -r requirements-dev.txt`
- Per-repo config: `.recursive.json`
- Test target: `https://github.com/fazxes/Phractal`

## Code Quality Rules

**Always use `make check` for verification.** Never run ruff, mypy, or pytest individually as your final check -- `make check` runs all of them against `nightshift/` and `Recursive/tests/`. Partial checks miss things.

These are enforced by CI. Non-negotiable.

**Typing (mypy strict):**
- Full type annotations on every function
- All data structures are TypedDicts in `nightshift/core/types.py`
- Zero `cast()` calls. Zero `# type: ignore` comments.
- `Any` only at JSON deserialization boundaries

**Linting (ruff):**
- Rule sets: `E`, `W`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`, `BLE`, `S`, `T20`, `PT`, `C4`
- Zero `# noqa` in source (one exception in tests for `sys.path.insert`)
- `S603`/`S607` suppressed only in `shell.py`, `cycle.py`, `worktree.py` via per-file-ignores
- `T201` suppressed only in `constants.py` and `cli.py`

**ASCII-only source:**
- No emojis, Unicode, or non-ASCII in `.py`, `.sh`, `.toml` files
- Markdown docs are exempt

## Code Structure

**Non-negotiable rules:**
- **One concern per module.** If you are adding >50 lines of new logic to an existing file, it belongs in its own module.
- **No hardcoded data in logic files.** Regex patterns, score maps, category weights, thresholds go in `nightshift/core/constants.py` or a dedicated `*_patterns.py`. Logic files import them.
- **Functions over inline code.** If a block of code does one thing and is >10 lines, extract it into a named function.
- **Config over magic numbers.** If a value might change, put it in `DEFAULT_CONFIG` and `core/types.py`, not inline.

**Package layout:**

```
nightshift/
  core/        errors, types, constants, shell, state (foundation -- no internal deps)
  settings/    config, eval_targets (configuration loading)
  owl/         cycle, readiness, scoring (hardening loop)
  raven/       planner, decomposer, subagent, coordination, integrator,
               feature, e2e, profiler, summary (feature builder loop)
  infra/       module_map, multi, worktree (infrastructure)
  cli.py       CLI entry point
  scripts/     install.sh, check.sh, run.sh, test.sh, smoke-test.sh
  tests/       unit and integration tests
```

**Dependency flow (no circular imports):**

`core/errors` -> `core/types` -> `core/constants` -> `core/shell` -> `core/state` -> `settings/config` -> `settings/eval_targets` -> `owl/scoring` -> `owl/readiness` -> `owl/cycle` -> `raven/summary` -> `raven/profiler` -> `raven/e2e` -> `raven/coordination` -> `raven/planner` -> `raven/subagent` -> `raven/decomposer` -> `raven/integrator` -> `raven/feature` -> `infra/worktree` -> `infra/module_map` -> `infra/multi` -> `cli`

New modules slot into this chain.

**New module checklist:**
1. Create the `.py` file in the appropriate subpackage
2. Add to the subpackage `__init__.py` re-exports
3. Add to `nightshift/__init__.py` re-exports
4. Add to `nightshift/scripts/install.sh` PACKAGE_FILES
5. Update this file's structure tree if needed

## Editing Conventions

- `nightshift/eval_targets.py` stores repo-specific evaluation defaults such as the Phractal verification command
- Shell scripts live in `nightshift/scripts/` (package-level) and `Recursive/engine/` (daemon)
- `Recursive/scripts/validate-tasks.sh` is the standalone task-frontmatter validator; do not wire it into `make check` until the known malformed backlog is repaired
- Per-repo config: `.recursive.json`
- `.recursive/architecture/MODULE_MAP.md` is generated by `python3 -m nightshift module-map --write`; refresh it whenever `nightshift/*.py` changes
- Before pushing: read `Recursive/ops/PRE-PUSH-CHECKLIST.md`

## Keeping This File Current

When you change project structure or conventions, update this file. Keep it short -- details belong in `Recursive/ops/OPERATIONS.md`.
