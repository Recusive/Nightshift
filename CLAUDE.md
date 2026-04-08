# CLAUDE.md

## MANDATORY: Session Start

1. **Read `.recursive/handoffs/LATEST.md`** -- What happened last session, what's broken, what to build next. This is your memory.
2. **Read `.recursive/ops/OPERATIONS.md`** on your first session, or when the handoff tells you to. This is the complete map of every system, folder, and file.
3. **If the human pastes the evolve prompt** -- Follow `.recursive/operators/build/SKILL.md` step by step.
4. **Read `.recursive/architecture/MODULE_MAP.md`** when the task touches `nightshift/*.py`. It is the fast orientation map for modules, dependencies, and recent shipped sessions.

Do NOT start building until you have read the handoff.
5. **Read `.recursive/learnings/INDEX.md`** -- One-line summaries of hard-won knowledge. Only open individual learning files when relevant to your current task. Do NOT read every file -- the index tells you what exists.

## What This Is

Nightshift is an autonomous engineering system. The `nightshift/` package spawns headless agent cycles (Codex or Claude) in an isolated git worktree, enforces guard rails, verifies each cycle, and tracks state. You pick an agent and the same pipeline runs.

Full vision: `.recursive/vision/00-overview.md`

## Quick Reference

```bash
make test        # run tests
make check       # full CI locally
make dry-run     # preview cycle prompt
make tasks       # show pending/blocked/in-progress tasks
bash .recursive/scripts/validate-tasks.sh   # validate numbered task frontmatter
make clean       # remove runtime artifacts
make daemon      # start the brain daemon (Opus orchestrates sub-agents each cycle)
python3 -m nightshift module-map --write   # refresh .recursive/architecture/MODULE_MAP.md
```

## Recursive (Meta-Layer)

The autonomous framework lives in `.recursive/`. It's a separate project from Nightshift -- a portable agentic layer that can run on any codebase.

```
.recursive/
├── engine/       daemon.sh, pick-role.py, lib-agent.sh, signals.py, dashboard.py, watchdog.sh
├── operators/    8 operators (build/review/oversee/strategize/achieve/security-check/evolve/audit)
├── lib/          costs, cleanup, compact, config, evaluation (standalone Python, zero nightshift deps)
├── agents/       14 sub-agent definitions (brain, build, review, oversee, achieve, strategize, security, evolve, audit-agent, + 5 reviewers)
├── prompts/      autonomous.md (v1 rules), checkpoints.md (verification pipeline)
├── ops/          DAEMON.md, OPERATIONS.md, PRE-PUSH-CHECKLIST.md, ROLE-SCORING.md
├── scripts/      generic utilities (init, validate-tasks, list-tasks, rollback)
├── skills/       per-repo setup wizard
├── templates/    project scaffolds (handoff, task, eval, session-index, config)
└── tests/        test_pick_role.py
```

**v2 Architecture (brain-delegates-to-sub-agents):** A brain agent (Opus) reads a dashboard of system signals, thinks through 4 checkpoints, and delegates to sub-agents (Sonnet) in git worktrees. Sub-agents create PRs; the brain reviews and merges them. The advisory recommendation from `pick-role.py` is one input to the brain's decision, not the sole decider.

Available roles (via sub-agents):
- **build**: picks tasks, builds features, ships PRs. Default.
- **review**: reviews code file by file. After 5+ consecutive builds.
- **oversee**: audits task queue, culls noise. When 50+ pending tasks.
- **strategize**: big picture analysis. Every 15+ sessions.
- **achieve**: measures autonomy (0-100), eliminates human deps. When autonomy low.
- **security-check**: red team preflight before each build.
- **evolve**: fixes friction patterns in framework. When 3+ friction entries.
- **audit**: reviews framework for contradictions and staleness. Every 25+ sessions.

```bash
# Start the daemon (from project root)
tmux new-session -d -s recursive "caffeinate -s bash .recursive/engine/daemon.sh claude 60"

# Monitor
tmux capture-pane -t recursive -p -S -15
cat .recursive/sessions/index.md
gh pr list --state all --limit 5

# Stop
tmux send-keys -t recursive C-c             # graceful
tmux kill-session -t recursive              # immediate
```

**Hot reload:** The daemon re-sources `lib-agent.sh` and checks for `daemon.sh` changes at the start of every loop iteration. If the agent modifies shell scripts during a session, the changes take effect next iteration automatically. No manual restart needed.

**WARNING: The daemon and the monitor/human share the same working directory.** Do not run `git checkout`, `git stash`, or any branch-switching commands while the daemon is mid-session -- it will corrupt or lose the daemon's uncommitted work.

**Making changes while the daemon is running:** Use a git worktree in `/tmp` instead of touching the main repo:

```bash
# Check if daemon is running
tmux has-session -t recursive 2>&1 && echo "RUNNING" || echo "NOT RUNNING"

# If RUNNING: use a worktree (safe -- isolated copy, daemon unaffected)
CHANGE_NAME="example-change"
git worktree add /tmp/nightshift-work origin/main -b "docs/$CHANGE_NAME"
# ... make changes in /tmp/nightshift-work/ ...
cd /tmp/nightshift-work && git add . && git commit -m "..." && git push origin "docs/$CHANGE_NAME"
gh pr create --head "docs/$CHANGE_NAME" && gh pr merge --merge --delete-branch --admin
git worktree remove /tmp/nightshift-work

# If NOT RUNNING: work directly in the repo as normal
git checkout -b "docs/$CHANGE_NAME"
# ... make changes ...
```

Full daemon operations guide with troubleshooting: `.recursive/ops/DAEMON.md`

## Runtime State (.recursive/)

`.recursive/` contains both the framework code (engine, operators, lib, agents, prompts) and runtime state (handoffs, tasks, sessions, learnings). Framework files are prompt-guarded; runtime state is auto-committed by the daemon.

```
.recursive/
├── handoffs/        Session memory (LATEST.md)
├── tasks/           Work queue (GUIDE.md + numbered task files)
├── sessions/        Logs, index.md, costs.json
├── learnings/       INDEX.md + knowledge files
├── evaluations/     Quality scores
├── architecture/    MODULE_MAP.md (auto-generated)
├── vision/          Human input: what to build
├── vision-tracker/  Progress tracking
├── changelog/       Version history
├── autonomy/        Autonomy reports
├── strategy/        Strategy reports
├── healer/          Health observations
├── reviews/         Code review logs
├── plans/           Meta-layer planning
├── friction/        Framework pain points (brain reads for evolve decisions)
├── decisions/       Brain decision log (what was delegated and why)
├── commitments/     Pre-commitment predictions and outcomes
└── incidents/       Incident log (prompt injection attempts, anomalies)
```

## Git Workflow

- **Never push to main directly.** Branch, PR, sub-agent review, merge.
- Branch naming: `feat/`, `fix/`, `docs/`, `refactor/`, `release/`
- **Review notes MUST become tasks.** If the code review sub-agent flags advisory notes, known limitations, or follow-up items but still passes, you MUST create follow-up tasks in `.recursive/tasks/` before merging. "Known limitation" is not a valid reason to skip -- the task queue tracks deferred work.
- **If CI fails after merge:** create a `fix/` branch and PR. Never push directly to main, even for "trivial" fixes.
- **After merge:** once CI on `main` is green, run `python3 -m nightshift run --dry-run --agent codex > /dev/null` and `python3 -m nightshift run --dry-run --agent claude > /dev/null` on `main` before reporting success.
- **Human task creation:** Humans create tasks as GitHub Issues with the `task` label. The daemon's housekeeping step syncs them to `.recursive/tasks/` automatically. See `.recursive/tasks/GUIDE.md` for details.
- **Exception: housekeeping commits push to main directly.** `sync_github_tasks` commits and pushes task files to main before the agent session starts. This bypasses the branch-PR workflow because the daemon's `git reset --hard origin/main` at cycle start would wipe uncommitted files. These are structural doc changes (task files), not code.
- Full workflow: `.recursive/ops/OPERATIONS.md` under "Git Workflow"

## Environment

- Python 3.9+. Use `python3`. **Never hardcode absolute paths.**
- Dev tools: `pip install -r requirements-dev.txt`
- Test target: `https://github.com/fazxes/Phractal`

## Code Quality Rules

**Always use `make check` for verification.** Never run ruff, mypy, or pytest individually as your final check -- `make check` runs ruff against `nightshift/` and `.recursive/` (engine, lib, tests), mypy against `nightshift/` only, and pytest across both. Partial checks miss things.

These are enforced by CI. Non-negotiable.

**Typing (mypy strict):**
- Full type annotations on every function
- All data structures are TypedDicts in `nightshift/core/types.py`
- Zero `cast()` calls. Zero `# type: ignore` comments.
- `Any` only at JSON deserialization boundaries

**Linting (ruff):**
- Rule sets: `E`, `W`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`, `BLE`, `S`, `T20`, `PT`, `C4`
- Zero `# noqa` in source (one exception in tests for `sys.path.insert`)
- `S603`/`S607` suppressed only in `nightshift/core/shell.py`, `nightshift/owl/cycle.py`, `nightshift/infra/worktree.py` via per-file-ignores
- `T201` suppressed only in `nightshift/core/constants.py` and `nightshift/cli.py`

**ASCII-only source:**
- No emojis, Unicode, or non-ASCII in `.py`, `.sh`, `.toml` files
- Markdown docs are exempt

**Code Structure (non-negotiable):**
- **One concern per module.** If you're adding >50 lines of new logic to an existing file, it belongs in its own module. cycle.py handles cycle logic -- not scoring. cli.py handles CLI -- not business logic.
- **No hardcoded data in logic files.** Regex patterns, score maps, category weights, thresholds -- these go in `core/constants.py` or a dedicated `*_patterns.py`. Logic files import them.
- **New module checklist:** create the `.py` file in the appropriate subpackage (`core/`, `settings/`, `owl/`, `raven/`, `infra/`), add to the subpackage's `__init__.py` re-exports, add to `nightshift/scripts/install.sh` PACKAGE_FILES, add to this file's structure tree.
- **Follow the dependency flow:** `core.errors -> core.types -> core.constants -> core.shell -> core.state -> settings.config -> settings.eval_targets -> owl.cycle -> owl.scoring -> owl.readiness -> raven.planner -> raven.decomposer -> raven.subagent -> raven.integrator -> raven.feature -> infra.worktree -> infra.module_map -> infra.multi -> cli`. New modules slot into this chain. No circular imports. (`infra/multi.py` uses a late import of `run_nightshift` from `cli.py` to avoid circular deps.)
- **Functions over inline code.** If a block of code does one thing and is >10 lines, extract it into a named function. The function name documents the intent.
- **Config over magic numbers.** If a value might change (thresholds, limits, timeouts), put it in `DEFAULT_CONFIG` and `core/types.py`, not inline.

**Contributors:**
- Run `make check` before pushing
- Don't suppress warnings -- fix them
- Dev tool versions pinned in `requirements-dev.txt`

## Nightshift Package Structure

```
nightshift/
├── cli.py              CLI entry point
├── core/               Foundations (errors, types, constants, shell, state)
├── settings/           Configuration (config, eval_targets)
├── owl/                Hardening loop (cycle, scoring, readiness)
├── raven/              Feature builder (planner, decomposer, subagent, integrator, etc.)
├── infra/              Infrastructure (worktree, module_map, multi)
├── schemas/            JSON schemas (feature, nightshift, task)
├── scripts/            check.sh, install.sh, run.sh, test.sh, smoke-test.sh
├── assets/             icon.png
└── tests/              Product tests
```

## Editing Conventions

- `nightshift/SKILL.md` uses YAML frontmatter for skill registration
- `nightshift/settings/eval_targets.py` stores repo-specific evaluation defaults such as the Phractal verification command
- Product shell scripts are thin wrappers in `nightshift/scripts/`; framework scripts in `.recursive/engine/` and `.recursive/scripts/`
- `.recursive/scripts/validate-tasks.sh` is the standalone task-frontmatter validator; do not wire it into `make check` until the known malformed backlog is repaired
- Per-repo config: `.recursive.json`
- `.recursive/architecture/MODULE_MAP.md` is generated by `python3 -m nightshift module-map --write`; refresh it whenever `nightshift/*.py` changes
- Before pushing: read `.recursive/ops/PRE-PUSH-CHECKLIST.md`

## Keeping This File Current

When you change project structure or conventions, update this file. But keep it short -- details belong in `.recursive/ops/OPERATIONS.md`.
