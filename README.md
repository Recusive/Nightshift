<p align="center">
  <img src="nightshift/assets/icon.png" alt="Nightshift" width="240" />
</p>

<h1 align="center">Nightshift</h1>

<p align="center">
  <strong>An autonomous engineering system with two shipped loops and a self-maintaining control plane.</strong><br/>
  Nightshift can harden existing repositories, build features from natural-language specs, evaluate itself on a real target repo, and keep its own task queue, handoffs, changelog, tracker, and prompt system up to date.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Claude-Supported-F97316" alt="Claude Code" />
  <img src="https://img.shields.io/badge/Codex-Supported-10B981" alt="Codex" />
  <img src="https://img.shields.io/badge/Tracker-92%25-2563EB" alt="Vision Tracker" />
  <img src="https://img.shields.io/badge/Tests-847-blue" alt="Tests" />
  <img src="https://img.shields.io/badge/License-MIT-22C55E" alt="MIT License" />
</p>

---

## This repo maintains itself

Most of the code in this repository was written, tested, reviewed, and merged by AI agents. One unified daemon (`Recursive/engine/daemon.sh`) auto-selects from five roles each cycle via `Recursive/engine/pick-role.py`:

- **Builder**: reads the task queue, runs a pentest preflight, builds or fixes one scoped task, tests it, opens a PR, reviews it, and merges it
- **Reviewer**: audits shipped code and fixes quality gaps
- **Overseer**: audits process drift, task hygiene, and systemic issues
- **Strategist**: produces a top-down health report for humans
- **Achiever**: measures autonomy score (0-100), eliminates human dependencies

The human role is operational: start the daemon and monitor it. The agents own the engineering loop -- including deciding what to work on.

**Proof points live in the repo, not in marketing copy.** Check them directly:

```bash
gh pr list --state merged --limit 50          # every merged PR
cat .recursive/sessions/index.md              # daemon sessions with timestamps
cat .recursive/handoffs/LATEST.md             # what the last session built
make tasks                                    # authoritative task queue summary
```

## Current state

Snapshot taken from live repo data on `2026-04-07`. Generated docs such as the
[vision tracker](.recursive/vision-tracker/TRACKER.md) and
[module map](.recursive/architecture/MODULE_MAP.md) are the source of truth when these
numbers change.

| Signal | Current reading | Source |
|--------|-----------------|--------|
| Overall vision progress | 92% | `.recursive/vision-tracker/TRACKER.md` |
| Loop 1 hardening | 99% | `.recursive/vision-tracker/TRACKER.md` |
| Loop 2 feature builder | 100% | `.recursive/vision-tracker/TRACKER.md` |
| Self-maintaining repo | 68% | `.recursive/vision-tracker/TRACKER.md` |
| Meta-prompt system | 78% | `.recursive/vision-tracker/TRACKER.md` |
| Tests | 847 passing | `python3 -m pytest nightshift/tests/ -q` |
| Python modules | 34 | `.recursive/architecture/MODULE_MAP.md` |
| Merged PRs | 30+ | `gh pr list --state merged --json number` |

---

## What ships today

Nightshift has two loops:

**Loop 1 -- Hardening (Owl)** (99% in the tracker): point it at a repository, let it
profile the stack, create an isolated worktree, find one production-readiness
issue per cycle, and either reject or commit the fix behind guard rails. This
loop already supports Codex and Claude, diff scoring, multi-repo mode, prompt
injection boundaries for repo instructions, and evaluation against Phractal.
The main remaining gap is evaluation fidelity on rejected runs.

**Loop 2 -- Feature Building (Raven)** (100% in the tracker): give it a feature request
in plain English and it will profile the repo, plan the work, decompose it into
waves, spawn sub-agents, integrate the results, run E2E and readiness checks,
and persist build state for resume/status flows.

The self-maintaining layer around those loops already ships:

- task queue sync and prioritization
- structured handoffs and learnings
- per-version changelogs
- a generated vision tracker and module map
- cross-session cost analysis
- a builder pentest preflight before code changes
- branch/PR/review/merge automation

## Install

### Install the skill bundle

```bash
curl -sL https://raw.githubusercontent.com/Recusive/Nightshift/main/nightshift/scripts/install.sh | bash
```

This installs Nightshift's wrapper scripts and prompt assets into:

- `~/.codex/skills/nightshift`
- `~/.claude/skills/nightshift`

The installer does **not** create a global `nightshift` shell command. In a repo
checkout, use `python3 -m nightshift ...`. From an installed skill bundle, use
the wrapper scripts in `~/.codex/skills/nightshift/scripts/`.

### Repo setup

Add runtime artifacts to the target repo's `.gitignore`:

```bash
cat <<'EOF' >> .gitignore
Runtime/Nightshift/worktree-*/
Runtime/Nightshift/*.runner.log
Runtime/Nightshift/*.state.json
EOF
```

Optional per-repo config:

```bash
cp .recursive.json.example .recursive.json
```

## Running Nightshift

### From a repo checkout

Use the Python module entry point that the codebase actually ships:

```bash
python3 -m nightshift run --agent claude
python3 -m nightshift test --agent claude --cycles 2 --cycle-minutes 5
python3 -m nightshift summarize
python3 -m nightshift plan "Add OAuth login"
python3 -m nightshift build "Add OAuth login" --yes
python3 -m nightshift build --status
python3 -m nightshift build --resume
python3 -m nightshift multi /repo1 /repo2 --agent claude --test --cycles 1
python3 -m nightshift module-map --write
```

`python3 -m nightshift test ...` now keeps its state files, runner logs, and
linked worktree under `$TMPDIR/nightshift-test-runs/...` so evaluation clones
stay clean. Full `run` mode still writes repo-local runtime artifacts under
`Runtime/Nightshift/`.

### From the installed skill bundle

Use the bundled wrapper scripts:

```bash
~/.codex/skills/nightshift/nightshift/scripts/run.sh --agent claude
~/.codex/skills/nightshift/nightshift/scripts/test.sh --agent claude --cycles 2 --cycle-minutes 5
```

### Self-maintaining mode

```bash
make daemon      # builder
make review      # reviewer
make overseer    # process auditor
make strategist  # one-shot strategic report
make tasks       # task queue summary
make check       # local CI gate
```

Daemon examples:

```bash
tmux new-session -d -s nightshift "bash Recursive/engine/daemon.sh claude 60"
RECURSIVE_PENTEST_AGENT=codex tmux new-session -d -s nightshift "bash Recursive/engine/daemon.sh claude 60"
tmux capture-pane -t nightshift -p -S -15
```

## Config

Abridged example. Full source of truth: [`.nightshift.json.example`](.nightshift.json.example)

```json
{
  "agent": "codex or claude",
  "hours": 8,
  "cycle_minutes": 30,
  "verify_command": null,
  "blocked_paths": [".github/", "deploy/", "deployment/", "infra/"],
  "blocked_globs": ["*.lock", "package-lock.json", "pnpm-lock.yaml"],
  "max_fixes_per_cycle": 3,
  "max_files_per_fix": 5,
  "max_files_per_cycle": 12,
  "max_low_impact_fixes_per_shift": 4,
  "stop_after_failed_verifications": 2,
  "stop_after_empty_cycles": 2,
  "score_threshold": 3,
  "test_incentive_cycle": 3,
  "backend_forcing_cycle": 3,
  "category_balancing_cycle": 3,
  "claude_model": "claude-opus-4-6",
  "claude_effort": "max",
  "codex_model": "gpt-5.4",
  "codex_thinking": "extra_high",
  "notification_webhook": null,
  "readiness_checks": ["secrets", "debug_prints", "test_coverage"],
  "eval_frequency": 5,
  "eval_target_repo": "https://github.com/fazxes/Phractal"
}
```

If `verify_command` is left `null`, Nightshift tries to infer one from repo
signals such as `pyproject.toml`, `package.json`, `Cargo.toml`, or `go.mod`.

Environment variables:

- `RECURSIVE_CLAUDE_MODEL`
- `RECURSIVE_CODEX_MODEL`
- `RECURSIVE_CODEX_THINKING`
- `RECURSIVE_BUDGET`
- `RECURSIVE_PENTEST_AGENT`
- `RECURSIVE_PENTEST_MAX_TURNS`

## How it keeps context between sessions

Nightshift is designed for stateless agents, so the repo carries the memory:

- **Handoffs**: every session writes a structured summary to `.recursive/handoffs/`, and the next session starts from `LATEST.md`
- **Learnings**: agents read `.recursive/learnings/INDEX.md` first, then open only the relevant learning files
- **Task queue**: work lives in `.recursive/tasks/`; urgent pending tasks outrank normal ones, then the queue falls back to lowest-numbered pending internal work
- **Evaluations**: after each merge, the next session runs Nightshift against Phractal and turns low scores into tracked follow-up work

```bash
cat .recursive/handoffs/LATEST.md
cat .recursive/learnings/INDEX.md
make tasks
ls .recursive/evaluations/
```

Humans can add work by opening GitHub issues with the `task` label:

```bash
gh issue create --title "Add dark mode" --label "task"
gh issue create --title "Fix CI" --label "task,urgent"
```

## Guard rails

Nightshift does not trust the model to "be careful." It verifies:

- commit + shift-log presence
- blocked-path and lockfile violations
- repo verification commands when configured
- file deletion attempts
- repeated category or path tunnel vision
- prompt/control-file modifications during self-maintenance

### Diff scorer

Accepted fixes are scored `1-10` for production impact using category, content,
test, and breadth signals. Below threshold: revert the cycle. Above threshold:
keep the commit.

### Prompt injection protection

Instruction files from target repos (`CLAUDE.md`, `AGENTS.md`, etc.) are wrapped
in an untrusted boundary before the agent sees them. They are treated as coding
convention references only, never as behavioral directives.

### Self-modification guard

Before builder work starts, Nightshift snapshots control files, runs a pentest
preflight, and hard-resets back to `origin/main` before the main fixer session.
Any control-file diff is surfaced explicitly in the next builder prompt.

### Cost tracking

Session costs are parsed from stream-json logs. Budget enforcement can stop the
daemon when cumulative spend exceeds `RECURSIVE_BUDGET`.

---

## Architecture

### Product -- `nightshift/`

The Python package is organized into subdirectories by concern. 34 modules
across 5 subdirectories. The generated
[module map](.recursive/architecture/MODULE_MAP.md) is the authoritative inventory.

```text
nightshift/
├── cli.py                    # CLI entry point
├── __init__.py / __main__.py
│
├── core/                     # Shared foundations
│   ├── types.py              # TypedDicts for all data structures
│   ├── constants.py          # Thresholds, patterns, score maps
│   ├── errors.py             # Exception hierarchy
│   ├── shell.py              # Subprocess helpers
│   └── state.py              # Shift-state persistence
│
├── settings/                 # Configuration layer
│   ├── config.py             # Config loading and defaults
│   └── eval_targets.py       # Repo-specific eval defaults (Phractal)
│
├── owl/                      # Loop 1 -- Hardening
│   ├── cycle.py              # Single-cycle orchestrator
│   ├── scoring.py            # Diff scorer (1-10)
│   └── readiness.py          # Production-readiness checks
│
├── raven/                    # Loop 2 -- Feature Builder
│   ├── profiler.py           # Repo profiling
│   ├── planner.py            # Feature plan generation
│   ├── decomposer.py         # Plan -> waves -> sub-tasks
│   ├── subagent.py           # Sub-agent spawning
│   ├── coordination.py       # Wave coordination
│   ├── integrator.py         # Result integration
│   ├── e2e.py                # End-to-end verification
│   ├── summary.py            # Build summaries
│   └── feature.py            # Top-level build command
│
├── infra/                    # Infrastructure modules
│   ├── worktree.py           # Git worktree isolation
│   ├── multi.py              # Multi-repo mode
│   └── module_map.py         # Module-map generation
│
├── schemas/                  # JSON schemas
│   ├── nightshift.schema.json
│   ├── feature.schema.json
│   └── task.schema.json
│
├── scripts/                  # Shell wrappers
│   ├── install.sh            # Skill-bundle installer
│   ├── run.sh / test.sh      # Convenience runners
│   ├── check.sh              # Local CI gate
│   └── smoke-test.sh         # Quick sanity check
│
├── assets/
│   └── icon.png
│
└── tests/                    # Product test suite (847 tests)
    ├── test_nightshift.py
    ├── test_feature_build.py
    └── test_module_map.py
```

### Framework -- `Recursive/`

The autonomous orchestration framework that drives the daemon, role selection,
operator prompts, and agent lifecycle.

```text
Recursive/
├── engine/                   # Daemon runtime
│   ├── daemon.sh             # Main daemon loop
│   ├── lib-agent.sh          # Agent lifecycle helpers
│   ├── pick-role.py          # Role scoring engine
│   ├── watchdog.sh           # Process watchdog
│   └── format-stream.py      # Stream-log formatter
│
├── operators/                # Role-specific prompt sets
│   ├── build/
│   ├── review/
│   ├── oversee/
│   ├── strategize/
│   ├── achieve/
│   └── security-check/
│
├── agents/                   # Sub-agent prompts (reviewers)
│   ├── code-reviewer.md
│   ├── architecture-reviewer.md
│   ├── docs-reviewer.md
│   ├── safety-reviewer.md
│   └── meta-reviewer.md
│
├── lib/                      # Shared Python helpers
│   ├── cleanup.py
│   ├── compact.py
│   ├── config.py
│   ├── costs.py
│   └── evaluation.py
│
├── prompts/                  # System prompts
│   ├── autonomous.md
│   └── checkpoints.md
│
├── ops/                      # Operations documentation
│   ├── DAEMON.md
│   ├── OPERATIONS.md
│   ├── PRE-PUSH-CHECKLIST.md
│   └── ROLE-SCORING.md
│
├── scripts/                  # Framework utilities
│   ├── init.sh
│   ├── list-tasks.sh
│   ├── rollback.sh
│   └── validate-tasks.sh
│
├── templates/                # Structured-doc templates
│   ├── handoff.md
│   ├── evaluation.md
│   ├── session-index.md
│   ├── task.md
│   └── project-config.json
│
└── tests/                    # Framework tests
    └── test_pick_role.py
```

### Runtime state -- `.recursive/`

14 directories of persistent state that the daemon reads and writes each cycle.
Not checked into source control for target repos; versioned here because
Nightshift is its own target.

```text
.recursive/
├── architecture/     # Generated module map
├── autonomy/         # Autonomy score reports
├── changelog/        # Per-version changelogs
├── evaluations/      # Phractal eval results
├── handoffs/         # Session handoff summaries
├── healer/           # Healer observation logs
├── learnings/        # Hard-won knowledge index
├── plans/            # Feature build plans
├── reviews/          # Code review artifacts
├── sessions/         # Session index and logs
├── strategy/         # Strategy reports
├── tasks/            # Task queue (frontmatter YAML)
├── vision/           # Vision documents
└── vision-tracker/   # Auto-generated progress tracker
```

### Product output -- `Runtime/`

```text
Runtime/
└── Nightshift/       # Shift logs, state files, worktree links
```

Type checking is `mypy --strict`. Linting is Ruff. The local gate is
`make check`.

## Current frontier

Shipped already:

- hardening loop (Owl) with worktrees, scoring, and guard rails
- feature builder loop (Raven) with plan/build/resume/status flows
- multi-repo mode
- module map generation
- self-evaluation against Phractal
- builder pentest preflight and prompt-integrity checks
- cross-session learnings, handoffs, and cost tracking

Still open in the queue:

- fix the remaining real-repo evaluation gaps on rejected runs
- automate release tagging and changelog/tracker updates
- improve task queue hygiene and session-index fidelity
- add monitoring / alerting integrations

See [.recursive/vision-tracker/TRACKER.md](.recursive/vision-tracker/TRACKER.md) for the
current scoreboard and [.recursive/tasks/](.recursive/tasks/) for the active backlog.

---

## Requirements

- Python 3.9+
- Git
- `claude` CLI or `codex` CLI
- `gh` CLI for PR/release automation
- `tmux` if you want long-running daemon sessions

---

## License

MIT
