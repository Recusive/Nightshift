<p align="center">
  <img src="assets/icon.png" alt="Nightshift" width="240" />
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
  <img src="https://img.shields.io/badge/Tests-933-blue" alt="Tests" />
  <img src="https://img.shields.io/badge/License-MIT-22C55E" alt="MIT License" />
</p>

---

## This repo maintains itself

Most of the code in this repository was written, tested, reviewed, and merged by AI agents. The control plane currently has four daemon entry points:

- **Builder**: reads the task queue, runs a pentest preflight, builds or fixes one scoped task, tests it, opens a PR, reviews it, and merges it
- **Reviewer**: audits shipped code and fixes quality gaps
- **Overseer**: audits process drift, task hygiene, and systemic issues
- **Strategist**: produces a top-down health report for humans

The human role is operational: start a daemon, monitor it, and redirect when priorities change. The agents own the engineering loop.

**Proof points live in the repo, not in marketing copy.** Check them directly:

```bash
gh pr list --state merged --limit 50          # every merged PR
cat docs/sessions/index.md                    # daemon sessions with timestamps
cat docs/handoffs/LATEST.md                   # what the last session built
make tasks                                    # authoritative task queue summary
```

## Current state

Snapshot taken from live repo data on `2026-04-05`. Generated docs such as the
[vision tracker](docs/vision-tracker/TRACKER.md) and
[module map](docs/architecture/MODULE_MAP.md) are the source of truth when these
numbers change.

| Signal | Current reading | Source |
|--------|-----------------|--------|
| Overall vision progress | 92% | `docs/vision-tracker/TRACKER.md` |
| Loop 1 hardening | 99% | `docs/vision-tracker/TRACKER.md` |
| Loop 2 feature builder | 100% | `docs/vision-tracker/TRACKER.md` |
| Self-maintaining repo | 68% | `docs/vision-tracker/TRACKER.md` |
| Meta-prompt system | 78% | `docs/vision-tracker/TRACKER.md` |
| Tests | 933 passing | `python3 -m pytest tests/ -q` |
| Python modules | 28 | `docs/architecture/MODULE_MAP.md` |
| Merged PRs | 80 | `gh pr list --state merged --json number` |

---

## What ships today

Nightshift has two loops:

**Loop 1 -- Hardening** (99% in the tracker): point it at a repository, let it
profile the stack, create an isolated worktree, find one production-readiness
issue per cycle, and either reject or commit the fix behind guard rails. This
loop already supports Codex and Claude, diff scoring, multi-repo mode, prompt
injection boundaries for repo instructions, and evaluation against Phractal.
The main remaining gap is evaluation fidelity on rejected runs.

**Loop 2 -- Feature Building** (100% in the tracker): give it a feature request
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
curl -sL https://raw.githubusercontent.com/Recusive/Nightshift/main/scripts/install.sh | bash
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
docs/Nightshift/worktree-*/
docs/Nightshift/*.runner.log
docs/Nightshift/*.state.json
EOF
```

Optional per-repo config:

```bash
cp ~/.codex/skills/nightshift/.nightshift.json.example .nightshift.json
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

### From the installed skill bundle

Use the bundled wrapper scripts:

```bash
~/.codex/skills/nightshift/scripts/run.sh --agent claude
~/.codex/skills/nightshift/scripts/test.sh --agent claude --cycles 2 --cycle-minutes 5
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

Builder daemon examples:

```bash
tmux new-session -d -s nightshift "bash scripts/daemon.sh claude 60"
NIGHTSHIFT_PENTEST_AGENT=codex tmux new-session -d -s nightshift "bash scripts/daemon.sh claude 60"
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

- `NIGHTSHIFT_CLAUDE_MODEL`
- `NIGHTSHIFT_CODEX_MODEL`
- `NIGHTSHIFT_CODEX_THINKING`
- `NIGHTSHIFT_BUDGET`
- `NIGHTSHIFT_PENTEST_AGENT`
- `NIGHTSHIFT_PENTEST_MAX_TURNS`

## How it keeps context between sessions

Nightshift is designed for stateless agents, so the repo carries the memory:

- **Handoffs**: every session writes a structured summary to `docs/handoffs/`, and the next session starts from `LATEST.md`
- **Learnings**: agents read `docs/learnings/INDEX.md` first, then open only the relevant learning files
- **Task queue**: work lives in `docs/tasks/`; urgent pending tasks outrank normal ones, then the queue falls back to lowest-numbered pending internal work
- **Evaluations**: after each merge, the next session runs Nightshift against Phractal and turns low scores into tracked follow-up work

```bash
cat docs/handoffs/LATEST.md
cat docs/learnings/INDEX.md
make tasks
ls docs/evaluations/
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
daemon when cumulative spend exceeds `NIGHTSHIFT_BUDGET`.

---

## Architecture

Nightshift has 28 Python modules today. The generated
[module map](docs/architecture/MODULE_MAP.md) is the authoritative inventory.

High-level layout:

```text
nightshift/
├── Core runtime:     types.py, constants.py, errors.py, shell.py, state.py, config.py
├── Loop 1 runtime:   worktree.py, cycle.py, scoring.py, evaluation.py, multi.py
├── Loop 2 runtime:   profiler.py, planner.py, decomposer.py, subagent.py,
│                     coordination.py, integrator.py, e2e.py, readiness.py,
│                     summary.py, feature.py
├── Self-maintenance: cleanup.py, compact.py, costs.py, module_map.py
└── CLI surface:      cli.py, __init__.py, __main__.py
```

Type checking is `mypy --strict`. Linting is Ruff. The local gate is
`make check`.

## Current frontier

Shipped already:

- hardening loop with worktrees, scoring, and guard rails
- feature builder loop with plan/build/resume/status flows
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
- deepen Orbit integration

See [docs/vision-tracker/TRACKER.md](docs/vision-tracker/TRACKER.md) for the
current scoreboard and [docs/tasks/](docs/tasks/) for the active backlog.

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
