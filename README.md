<p align="center">
  <img src="assets/icon.png" alt="Nightshift" width="240" />
</p>

<h1 align="center">Nightshift</h1>

<p align="center">
  <strong>An autonomous engineering system that maintains itself.</strong><br/>
  Point it at any codebase. It finds bugs, fixes them, creates PRs, reviews them with another AI agent, merges them, and writes a handoff so the next session knows exactly what happened. Then it does it again. Every 60 seconds. For as long as you let it run.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Claude-Supported-F97316" alt="Claude Code" />
  <img src="https://img.shields.io/badge/Codex-Supported-10B981" alt="Codex" />
  <img src="https://img.shields.io/badge/License-MIT-22C55E" alt="MIT License" />
  <img src="https://img.shields.io/badge/Tests-600+-blue" alt="Tests" />
  <img src="https://img.shields.io/badge/PRs%20Merged-35+-purple" alt="PRs" />
</p>

---

## This repo maintains itself

Most of the code in this repository was written, tested, reviewed, and merged by AI agents -- not humans. The 4 daemon system runs autonomously: the **Builder** ships features, the **Reviewer** audits code quality, the **Overseer** audits the process itself, and the **Strategist** advises the human on what to change.

The human's role is to start the daemon, monitor it, and occasionally course-correct. The agents do the engineering.

**The proof is in the git history.** Every PR was created by an agent. Every code review was performed by a sub-agent. Every handoff, learning, and task was written by an agent. You can verify this yourself:

```bash
gh pr list --state merged --limit 50          # every merged PR
cat docs/sessions/index.md                     # every daemon session with timestamps
cat docs/handoffs/LATEST.md                    # what the last session built
ls docs/learnings/                             # permanent memory from past mistakes
```

### The numbers (and growing)

| Metric | Count |
|--------|-------|
| Python modules | 21 |
| Source lines | 6,000+ |
| Tests | 600+ |
| PRs merged | 35+ |
| Tasks created and tracked | 39 |
| Learnings (permanent memory) | 21+ |
| Versions released | v0.0.1 through v0.0.7 |
| Commits on main | 145+ |

These numbers update every time the daemon runs. Check the [vision tracker](docs/vision-tracker/TRACKER.md) for live progress.

---

## What it does

Nightshift has two loops:

**Loop 1 -- Hardening** (100% complete): Point it at any repository. It detects your stack automatically (language, framework, package manager, test runner, linter), spins up an isolated git worktree, and runs cycles. Each cycle: find a production-readiness issue, fix it, verify it, score it, commit it. Categories: security vulnerabilities, missing error handling, test coverage gaps, accessibility, code quality, performance, and polish.

**Loop 2 -- Feature Building** (63% complete): Give it a feature spec in plain English. It profiles the repo, plans the architecture, decomposes into parallelizable tasks, spawns sub-agents for each task, integrates the results wave by wave, and verifies the full feature end-to-end.

### How a cycle works

```
1. Scan codebase across 7 categories
2. Find an issue, fix it
3. Verify: did tests pass? blocked files touched? files deleted? shift log updated?
4. Score 1-10 for production impact (diff scorer with 4 factors)
5. Below threshold? Reverted. Above? Committed.
6. Steer: category balancing, test escalation, backend forcing, path diversity
7. Repeat
```

Every fix goes through a 6-stage verification gate. If ANY stage fails, the entire cycle is reverted. `git reset --hard`. The AI doesn't get to negotiate.

---

## The 4 daemons

The self-maintaining layer. Each daemon has a single purpose, a dedicated prompt, and runs in a tmux session. They share a lockfile -- only one runs at a time.

### Builder (`make daemon`)

Picks up tasks from the queue (`docs/tasks/`), builds features, writes tests, runs the full test suite, creates a branch, opens a PR, spawns a sub-agent for code review, merges on pass, writes the handoff. Loops every 60 seconds.

In one overnight run: 19 PRs shipped across 12 sessions. Tests grew from 145 to 482. Three versions released.

### Reviewer (`make review`)

Never builds features. Reviews existing code one file at a time. Line-by-line audit: type safety, error handling, test gaps, dead code, documentation drift. Every fix runs the full test suite. Branch, PR, review, merge.

### Overseer (`make overseer`)

Doesn't touch code. Audits the process: duplicate tasks, wrong priorities, stale handoffs, percentage drift, direction problems. Picks the single biggest systemic issue per cycle and fixes it.

### Strategist (`make strategist`)

Runs once. Reads everything: git log, PRs, evaluations, learnings, session indices, tracker, task queue. Produces a report: what's working, what's failing, what's missing. Each recommendation has evidence and a specific fix. The human reviews and approves.

---

## Session memory

AI agents are stateless. Nightshift isn't.

### Handoffs (`docs/handoffs/`)

Every session ends by writing a structured handoff: what was built, decisions made (and why), known issues, current state, what the next session should do, and which files to read first. The next session reads this before doing anything. Full context transfer in 30 seconds.

### Learnings (`docs/learnings/`)

Permanent memory. Every gotcha, failure, and non-obvious pattern gets a learning file. Every future session reads all learnings before touching code. The system cannot make the same mistake twice.

Real examples from this repo's memory:

- *"mypy rejects .get() on required TypedDict fields -- use direct key access"*
- *"Always use `make check`, never partial lint commands -- partial checks miss test file errors"*
- *"Code review advisory notes must become follow-up tasks -- 'known limitation' is not a valid disposition"*
- *"Sessions die at 500 max turns without warning -- reduce context usage by 10-20%"*

### Task queue (`docs/tasks/`)

Numbered markdown files with status, priority, and acceptance criteria. The builder picks up the lowest-numbered pending task. When it finishes, it creates follow-up tasks based on what it learned. The queue feeds itself.

**Adding tasks as a human:** Create a GitHub Issue with the `task` label. The daemon converts it to a task file automatically.

```bash
gh issue create --title "Add dark mode" --label "task"          # normal priority
gh issue create --title "Fix CI" --label "task,urgent"          # urgent
gh issue create --title "Build webhook" --label "task,loop2"    # with vision section
```

---

## Guard rails

### Verification pipeline

Every fix goes through 6 stages before it's accepted:

1. Did the commit happen and shift log update?
2. Did it touch blocked files? (lockfiles, node_modules, .env -- instant rejection)
3. Did the test suite pass?
4. Did it delete any files? (zero tolerance -- immediate revert)
5. Is it balanced across categories? (no tunnel-visioning on easy fixes)
6. Is it exploring different parts of the codebase? (no same-directory loops)

### Diff scorer

Every accepted fix is scored 1-10 for production impact. Four factors: category bonus, diff content analysis (regex patterns for auth/encryption/error-handling), test bonus, breadth bonus. Below the threshold? Reverted.

### Prompt injection protection

Nightshift reads instruction files from target repos (CLAUDE.md, AGENTS.md, .cursorrules). These are wrapped in an untrusted boundary before the agent sees them -- the agent is told to treat them as coding-convention references only, never as directives.

### Self-modification guard

Before every cycle, 7 control files are snapshotted. After the cycle, every file is diffed against its snapshot. If any control file was modified: full diff logged, alert file written, session flagged, next cycle alerted.

### Cost tracking

Session costs are parsed from stream-json logs in real time. Per-session and per-shift budget ceilings halt the daemon if spending exceeds the limit.

---

## Architecture

```
nightshift/
├── types.py          # TypedDicts for all data structures (mypy --strict)
├── constants.py      # Config defaults, scoring patterns, category data
├── errors.py         # NightshiftError
├── shell.py          # Subprocess execution, git helpers
├── config.py         # Config loading, agent resolution, env detection
├── state.py          # State read/write, cycle management
├── worktree.py       # Git worktree lifecycle, shift log management
├── cycle.py          # Prompt building, verification, baseline evaluation
├── scoring.py        # Post-cycle diff scoring (1-10 production impact)
├── costs.py          # Session cost parsing, budget tracking, ledger
├── cleanup.py        # Log rotation, orphan branch pruning
├── multi.py          # Multi-repo support
├── profiler.py       # Repo profiling (Loop 2)
├── planner.py        # Feature planning from natural language (Loop 2)
├── decomposer.py     # Task decomposition into waves (Loop 2)
├── subagent.py       # Sub-agent spawning and management (Loop 2)
├── integrator.py     # Wave integration, test diagnosis (Loop 2)
├── feature.py        # Feature CLI orchestrator (Loop 2)
├── cli.py            # CLI entry points
├── __init__.py       # Package re-exports
└── __main__.py       # python3 -m nightshift
```

**Dependency chain** (strictly enforced, no circular imports):

```
types -> constants -> errors -> shell -> config/state -> worktree -> cycle ->
scoring -> costs -> cleanup -> multi -> profiler -> planner -> decomposer ->
subagent -> integrator -> feature -> cli
```

**Type enforcement**: mypy --strict. Full annotations on every function. Zero `cast()`. Zero `# type: ignore`. `Any` only at JSON deserialization boundaries.

**Linting**: ruff with 13 rule sets. Zero `# noqa` in source code.

---

## Install

### One-liner

```bash
curl -sL https://raw.githubusercontent.com/Recusive/Nightshift/main/scripts/install.sh | bash
```

Installs into `~/.codex/skills/nightshift` and `~/.claude/skills/nightshift`.

### Repo setup

Add runtime artifacts to `.gitignore`:

```bash
cat <<'EOF' >> .gitignore
docs/Nightshift/worktree-*/
docs/Nightshift/*.runner.log
docs/Nightshift/*.state.json
EOF
```

Optional config:

```bash
cp ~/.codex/skills/nightshift/.nightshift.json.example .nightshift.json
```

---

## Usage

### Run against any repo

```bash
nightshift run                              # interactive -- asks for agent
nightshift run --agent claude               # use Claude
nightshift run --agent codex                # use Codex
nightshift test                             # short validation run (2 cycles)
nightshift multi /repo1 /repo2 --agent claude  # multi-repo
```

### Run the daemon (self-maintaining mode)

```bash
# Start (interactive -- asks for agent and duration)
make daemon

# Or specify directly
tmux new-session -d -s nightshift "bash scripts/daemon.sh claude 60"

# Monitor
tmux capture-pane -t nightshift -p -S -15   # daemon output
cat docs/sessions/index.md                   # session history
gh pr list --state all --limit 5             # recent PRs

# Stop
tmux send-keys -t nightshift C-c            # graceful
tmux kill-session -t nightshift             # immediate
```

### Feature building (Loop 2)

```bash
nightshift plan "Add user authentication with OAuth"         # plan only
nightshift plan "Add dark mode" --agent claude               # plan with agent
nightshift build "Add user authentication with OAuth"        # full pipeline
nightshift build --status                                    # check progress
nightshift build --resume                                    # resume after crash
```

---

## Config

`.nightshift.json` in the repo root:

```json
{
  "agent": "claude",
  "hours": 8,
  "cycle_minutes": 30,
  "verify_command": null,
  "blocked_paths": [".github/", "infra/", "deploy/"],
  "blocked_globs": ["*.lock", "package-lock.json"],
  "score_threshold": 3,
  "claude_model": "claude-opus-4-6",
  "claude_effort": "max",
  "codex_model": "o3",
  "budget_per_session_usd": 15.0,
  "budget_per_shift_usd": 100.0
}
```

If `verify_command` is omitted, Nightshift auto-detects from `package.json`, `Cargo.toml`, `go.mod`, `pyproject.toml`, etc.

Environment variable overrides: `NIGHTSHIFT_CLAUDE_MODEL`, `NIGHTSHIFT_CODEX_MODEL`, `NIGHTSHIFT_CODEX_THINKING`.

---

## How it maintains itself

This is the part that's different from every other AI coding tool.

Nightshift pointed at its own codebase started improving itself. The builder daemon picks up tasks, builds features, writes tests, creates PRs, reviews them with a sub-agent, merges them, and writes a handoff so the next session continues where it left off.

The git history tells the story:

```bash
# See every PR the agents shipped
gh pr list --state merged --limit 50

# See the session-by-session record
cat docs/sessions/index.md

# See what the system learned from its own mistakes
ls docs/learnings/

# See the task queue it maintains for itself
for f in docs/tasks/0*.md; do
  num=$(basename "$f" .md)
  st=$(grep "^status:" "$f" | head -1 | sed 's/status: //')
  title=$(grep "^# " "$f" | head -1 | sed 's/# //')
  printf "  %s  %-12s  %s\n" "$num" "[$st]" "$title"
done
```

The human starts the daemon and monitors it. The agents do the engineering. Every PR, every test, every code review, every handoff, every learning -- written by the agents, verifiable in the git history.

---

## Roadmap

- [x] Pluggable agent adapters (Codex, Claude)
- [x] Runner-enforced guard rails and verification pipeline
- [x] Post-cycle diff scoring (1-10 production impact)
- [x] Anti-tunnel-vision: category balancing, test escalation, backend forcing
- [x] Multi-repo support
- [x] Self-improving daemon (4 specialized daemons)
- [x] Session memory: handoffs + learnings
- [x] Self-evaluation against real repos
- [x] Loop 2: Feature builder pipeline (profiler, planner, decomposer, sub-agents, integrator)
- [x] Feature CLI (`nightshift build`, `nightshift plan`)
- [x] Prompt injection protection (untrusted instruction boundary)
- [x] Self-modification guard (control file snapshots + diff detection)
- [x] Cost tracking and budget ceilings
- [x] Configurable models per daemon
- [x] Interactive daemon setup
- [x] Log rotation and orphan branch pruning
- [ ] Loop 2: Sub-agent parallelization within waves
- [ ] Loop 2: End-to-end testing (dev server + Playwright/Cypress)
- [ ] Reviewer and Overseer daemon production deployment
- [ ] Instruction file size caps and symlink protection
- [ ] Monitoring/alerting webhooks
- [ ] Built-in to [Orbit](https://github.com/Recusive/Orbit-Release) as a native feature

---

## Requirements

- Python 3.9+
- Git
- `claude` CLI or `codex` CLI

---

## License

MIT
