# CLAUDE.md

## MANDATORY: Session Start

1. **Read `docs/handoffs/LATEST.md`** — What happened last session, what's broken, what to build next. This is your memory.
2. **Read `docs/ops/OPERATIONS.md`** on your first session, or when the handoff tells you to. This is the complete map of every system, folder, and file.
3. **If the human pastes the evolve prompt** — Follow `docs/prompt/evolve.md` step by step.
4. **Read `docs/architecture/MODULE_MAP.md`** when the task touches `nightshift/*.py`. It is the fast orientation map for modules, dependencies, and recent shipped sessions.

Do NOT start building until you have read the handoff.
5. **Read `docs/learnings/INDEX.md`** — One-line summaries of hard-won knowledge. Only open individual learning files when relevant to your current task. Do NOT read every file — the index tells you what exists.

## What This Is

Nightshift is an autonomous engineering system. The `nightshift/` package spawns headless agent cycles (Codex or Claude) in an isolated git worktree, enforces guard rails, verifies each cycle, and tracks state. You pick an agent and the same pipeline runs.

Full vision: `docs/vision/00-overview.md`

## Quick Reference

```bash
make test        # run tests
make check       # full CI locally
make dry-run     # preview cycle prompt
make tasks       # show pending/blocked/in-progress tasks
bash scripts/validate-tasks.sh   # validate numbered task frontmatter
make clean       # remove runtime artifacts
make daemon      # unified daemon (auto-picks role: build/review/oversee/strategize)
python3 -m nightshift module-map --write   # refresh docs/architecture/MODULE_MAP.md
```

## Daemon

One unified daemon that picks its own role each cycle. Full guide: `docs/ops/DAEMON.md`

Each cycle the agent reads system signals (eval scores, task queue size, session history) and scores four roles. The highest score wins:
- **BUILD**: picks up tasks, builds features, PRs, merges. Includes pentest preflight and healer observations.
- **REVIEW**: reviews code file by file, fixes quality issues. Triggered after 5+ consecutive builds.
- **OVERSEE**: audits task queue, fixes priorities, culls stale tasks. Triggered when 50+ pending tasks accumulate.
- **STRATEGIZE**: big picture review, produces strategy report. Triggered every 15+ sessions.
- **ACHIEVE**: measures autonomy score (0-100), eliminates human dependencies. Triggered when autonomy is low or needs-human issues accumulate. Reports to `docs/autonomy/`.

The agent decides autonomously -- no human picks the mode. Role decisions are logged in the session index.

```bash
# Start the daemon in tmux (recommended -- survives terminal disconnect)
tmux new-session -d -s nightshift "caffeinate -s bash scripts/daemon.sh codex 60"
tmux new-session -d -s nightshift "caffeinate -s bash scripts/daemon.sh claude 60"

# Monitor
tmux capture-pane -t nightshift -p -S -15   # daemon wrapper output
cat docs/sessions/index.md                   # session history (includes role column)
gh pr list --state all --limit 5             # recent PRs

# Read the live stream-json log (see what the agent is doing right now)
LATEST_LOG=$(ls docs/sessions/*.log | tail -1)
cat "$LATEST_LOG" | python3 -c "
import json, sys
for line in sys.stdin:
    try:
        e = json.loads(line.strip())
        if e.get('type') == 'assistant':
            for b in e['message']['content']:
                if b.get('type') == 'tool_use': print(f\"{b['name']}: {str(b.get('input',{}))[:80]}\")
                elif b.get('type') == 'text' and len(b.get('text','')) > 15: print(f\"MSG: {b['text'][:120]}\")
    except: pass
"

# Stop
tmux send-keys -t nightshift C-c            # graceful (after current session)
tmux kill-session -t nightshift             # immediate
```

**Hot reload:** The daemon re-sources `lib-agent.sh` and checks for `daemon.sh` changes at the start of every loop iteration. If the agent modifies shell scripts during a session, the changes take effect next iteration automatically. No manual restart needed.

**WARNING: The daemon and the monitor/human share the same working directory.** Do not run `git checkout`, `git stash`, or any branch-switching commands while the daemon is mid-session — it will corrupt or lose the daemon's uncommitted work.

**Making changes while the daemon is running:** Use a git worktree in `/tmp` instead of touching the main repo:

```bash
# Check if daemon is running
tmux has-session -t nightshift 2>&1 && echo "RUNNING" || echo "NOT RUNNING"

# If RUNNING: use a worktree (safe — isolated copy, daemon unaffected)
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

Full daemon operations guide with troubleshooting: `docs/ops/DAEMON.md`

## Git Workflow

- **Never push to main directly.** Branch, PR, sub-agent review, merge.
- Branch naming: `feat/`, `fix/`, `docs/`, `refactor/`, `release/`
- **Review notes MUST become tasks.** If the code review sub-agent flags advisory notes, known limitations, or follow-up items but still passes, you MUST create follow-up tasks in `docs/tasks/` before merging. "Known limitation" is not a valid reason to skip — the task queue tracks deferred work.
- **If CI fails after merge:** create a `fix/` branch and PR. Never push directly to main, even for "trivial" fixes.
- **Human task creation:** Humans create tasks as GitHub Issues with the `task` label. The daemon's housekeeping step syncs them to `docs/tasks/` automatically. See `docs/tasks/GUIDE.md` for details.
- **Exception: housekeeping commits push to main directly.** `sync_github_tasks` commits and pushes task files to main before the agent session starts. This bypasses the branch-PR workflow because the daemon's `git reset --hard origin/main` at cycle start would wipe uncommitted files. These are structural doc changes (task files), not code.
- Full workflow: `docs/ops/OPERATIONS.md` under "Git Workflow"

## Environment

- Python 3.9+. Use `python3`. **Never hardcode absolute paths.**
- Dev tools: `pip install -r requirements-dev.txt`
- Test target: `https://github.com/fazxes/Phractal`

## Code Quality Rules

**Always use `make check` for verification.** Never run ruff, mypy, or pytest individually as your final check — `make check` runs all of them against both `nightshift/` and `tests/`. Partial checks miss things.

These are enforced by CI. Non-negotiable.

**Typing (mypy strict):**
- Full type annotations on every function
- All data structures are TypedDicts in `nightshift/types.py`
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

**Code Structure (non-negotiable):**
- **One concern per module.** If you're adding >50 lines of new logic to an existing file, it belongs in its own module. cycle.py handles cycle logic — not scoring. cli.py handles CLI — not business logic.
- **No hardcoded data in logic files.** Regex patterns, score maps, category weights, thresholds — these go in `constants.py` or a dedicated `*_patterns.py`. Logic files import them.
- **New module checklist:** create the `.py` file, add to `__init__.py` re-exports, add to `scripts/install.sh` PACKAGE_FILES, add to this file's structure tree.
- **Follow the dependency flow:** `errors -> eval_targets -> types -> constants -> shell -> summary -> cleanup -> compact -> coordination -> costs -> module_map -> readiness -> scoring -> state -> config -> multi -> e2e -> profiler -> worktree -> cycle -> evaluation -> planner -> subagent -> decomposer -> integrator -> feature -> cli`. New modules slot into this chain. No circular imports. (`multi.py` uses a late import of `run_nightshift` from `cli.py` to avoid circular deps.)
- **Functions over inline code.** If a block of code does one thing and is >10 lines, extract it into a named function. The function name documents the intent.
- **Config over magic numbers.** If a value might change (thresholds, limits, timeouts), put it in `DEFAULT_CONFIG` and `types.py`, not inline.

**Contributors:**
- Run `make check` before pushing
- Don't suppress warnings — fix them
- Dev tool versions pinned in `requirements-dev.txt`

## Editing Conventions

- `nightshift/SKILL.md` uses YAML frontmatter for skill registration
- `nightshift/eval_targets.py` stores repo-specific evaluation defaults such as the Phractal verification command
- Shell scripts are thin wrappers in `scripts/`
- `scripts/validate-tasks.sh` is the standalone task-frontmatter validator; do not wire it into `make check` until the known malformed backlog is repaired
- Per-repo config: `.nightshift.json` (see `.nightshift.json.example`)
- `docs/architecture/MODULE_MAP.md` is generated by `python3 -m nightshift module-map --write`; refresh it whenever `nightshift/*.py` changes
- Before pushing: read `docs/ops/PRE-PUSH-CHECKLIST.md`

## Keeping This File Current

When you change project structure or conventions, update this file. But keep it short — details belong in `docs/ops/OPERATIONS.md`.
