<p align="center">
  <img src="assets/icon.png" alt="Nightshift" width="240" />
</p>

<h1 align="center">Nightshift</h1>

<p align="center">
  <strong>Your overnight engineer. Autonomous. Thorough. Ready by morning.</strong><br/>
  Run it before bed. Wake up to a reviewed worktree, a shift log, and a machine-readable record of what the agent actually did.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Codex-Supported-10B981" alt="Codex" />
  <img src="https://img.shields.io/badge/Claude-Supported-F97316" alt="Claude Code" />
  <img src="https://img.shields.io/badge/License-MIT-22C55E" alt="MIT License" />
</p>

---

## About

Nightshift is an overnight codebase-hardening runner built by **[Recursive Labs](https://github.com/Recusive)** as part of the [Orbit](https://github.com/Recusive/Orbit-Release) ecosystem.

The original version relied mostly on prompt discipline. This version adds a real control plane:

- a Python orchestrator (the `nightshift/` package)
- pluggable agent adapters (Codex and Claude — pick one, both go through the same pipeline)
- machine-readable shift state (`docs/Nightshift/YYYY-MM-DD.state.json`)
- runner-enforced guard rails, verification gates, and halt conditions

---

## What It Does

Nightshift runs in an isolated git worktree and repeatedly asks an agent to:

1. read the current repo instructions and shift log
2. find a small production-readiness improvement
3. fix it or log it
4. verify it
5. record it

The runner enforces the difference between a productive overnight shift and 8 hours of churn.

### Runner-enforced guard rails

- Max `3` fixes per cycle
- Max `5` files per fix
- Max `12` files touched per cycle
- Max `4` low-impact fixes per shift
- Blocked edits for CI/deploy/infra/generated files and lockfiles
- Hot-file protection via recent git activity
- Halt after repeated failed verification or empty cycles
- Worktree must end clean after every accepted cycle
- Each fix commit must include the shift log update

### Output artifacts

- `docs/Nightshift/YYYY-MM-DD.md` — human-readable shift log
- `docs/Nightshift/YYYY-MM-DD.state.json` — machine-readable cycle state
- `docs/Nightshift/YYYY-MM-DD.runner.log` — raw runner output
- `nightshift/YYYY-MM-DD` — isolated review branch

---

## Architecture

```
Main repo checkout                 Nightshift worktree
├── untouched                      ├── agent edits happen here
├── no branch switching            ├── isolated nightshift/YYYY-MM-DD branch
└── receives copied logs           └── verification happens after each cycle
```

### Package modules (18)

| Module | Purpose |
|--------|---------|
| `types.py` | TypedDicts for all data structures (strict typing) |
| `constants.py` | Config defaults, scoring patterns, category data |
| `errors.py` | NightshiftError |
| `shell.py` | Subprocess execution, git helper, shell utilities |
| `config.py` | Config loading, agent resolution, environment detection |
| `state.py` | State read/write, cycle state management |
| `worktree.py` | Git worktree lifecycle, shift log management |
| `cycle.py` | Prompt building, verification, baseline evaluation, state injection |
| `scoring.py` | Post-cycle diff scoring (1-10 production impact) |
| `multi.py` | Multi-repo support (sequential hardening across repos) |
| `profiler.py` | Repo understanding and profiling (Loop 2) |
| `planner.py` | Feature planning from natural language (Loop 2) |
| `decomposer.py` | Task decomposition into parallelizable units (Loop 2) |
| `subagent.py` | Sub-agent spawning and management (Loop 2) |
| `integrator.py` | Wave integration, test diagnosis, fix agents (Loop 2) |
| `cli.py` | CLI entry points: run, test, multi, summarize, verify-cycle |
| `__init__.py` | Package re-exports |
| `__main__.py` | Entry point for `python3 -m nightshift` |

### Self-improving infrastructure

| File | Purpose |
|------|---------|
| `scripts/daemon.sh` | Self-improving daemon (see [Daemon](#daemon)) |
| `docs/prompt/evolve.md` | 11-step session lifecycle prompt |
| `docs/prompt/evolve-auto.md` | Autonomous mode override |
| `docs/handoffs/` | Session-to-session memory |
| `docs/learnings/` | Cross-session knowledge (gotchas, patterns) |
| `docs/evaluations/` | Self-evaluation reports (scored against real repos) |
| `docs/sessions/` | Daemon session logs (stream-json) |
| `docs/tasks/` | Task queue |
| `docs/vision-tracker/` | Progress scoreboard |
| `docs/changelog/` | Per-version release notes |

---

## Install

### One-liner

```bash
curl -sL https://raw.githubusercontent.com/Recusive/Nightshift/main/scripts/install.sh | bash
```

This installs Nightshift into both:

- `~/.codex/skills/nightshift`
- `~/.claude/skills/nightshift`

### Repo setup

Add runtime artifacts to `.gitignore`:

```bash
cat <<'EOF' >> .gitignore
docs/Nightshift/worktree-*/
docs/Nightshift/*.runner.log
docs/Nightshift/*.state.json
EOF
```

Optional: copy the config template into the repo root:

```bash
cp ~/.codex/skills/nightshift/.nightshift.json.example .nightshift.json
```

---

## Config

Nightshift looks for `.nightshift.json` in the repo root.

Supported keys:

```json
{
  "agent": "codex or claude",
  "hours": 8,
  "cycle_minutes": 30,
  "verify_command": null,
  "blocked_paths": [".github/", "infra/", "deploy/"],
  "blocked_globs": ["*.lock", "package-lock.json"],
  "max_fixes_per_cycle": 3,
  "max_files_per_fix": 5,
  "max_files_per_cycle": 12,
  "max_low_impact_fixes_per_shift": 4,
  "stop_after_failed_verifications": 2,
  "stop_after_empty_cycles": 2,
  "score_threshold": 3,
  "test_incentive_cycle": 3,
  "backend_forcing_cycle": 3
}
```

If `verify_command` is omitted, Nightshift tries to infer one from common repo manifests such as `package.json`, `Cargo.toml`, `go.mod`, and `pyproject.toml`.

---

## Usage

### Overnight run

```bash
~/.codex/skills/nightshift/scripts/run.sh            # prompts for agent choice
~/.codex/skills/nightshift/scripts/run.sh --agent codex
~/.codex/skills/nightshift/scripts/run.sh --agent claude
~/.codex/skills/nightshift/scripts/run.sh 10          # 10 hours
~/.codex/skills/nightshift/scripts/run.sh 6 45        # 6 hours, 45 min per cycle
```

If no `--agent` flag is passed and `.nightshift.json` doesn't set one, the runner asks which agent to use.

### Short validation run

```bash
~/.codex/skills/nightshift/scripts/test.sh
~/.codex/skills/nightshift/scripts/test.sh --agent codex --cycles 2 --cycle-minutes 5
```

### Multi-repo run

```bash
python3 -m nightshift multi /path/to/repo1 /path/to/repo2 --agent codex
python3 -m nightshift multi /path/to/repo1 /path/to/repo2 --agent codex --test --cycles 2
```

Runs a full hardening shift on each repo sequentially. Validates all repos upfront, prints an aggregate summary at the end.

### Direct orchestrator usage

```bash
python3 -m nightshift run
python3 -m nightshift run --agent codex
python3 -m nightshift run --agent claude
python3 -m nightshift test
python3 -m nightshift multi /path/to/repo1 /path/to/repo2 --agent codex
python3 -m nightshift summarize
```

Both agents go through the same runner, same verification, same policy enforcement. The only difference is the CLI command each adapter constructs.

---

## Morning Review

```bash
cat docs/Nightshift/2026-04-02.md
cat docs/Nightshift/2026-04-02.state.json
git log nightshift/2026-04-02 --oneline
git merge nightshift/2026-04-02
git worktree remove docs/Nightshift/worktree-2026-04-02
git branch -d nightshift/2026-04-02
```

The shift log is for humans. The state file is for quick auditing:

- how many cycles ran
- which categories were touched
- which files changed
- whether verification passed
- why the run stopped

---

## Requirements

- Python 3.9+
- Git
- `codex` CLI or `claude` CLI (whichever agent you choose)

---

## Daemon

Nightshift can run itself autonomously in a loop, building features, fixing bugs, and shipping releases with zero human intervention.

```bash
# Start the self-improving daemon in tmux
tmux new-session -d -s nightshift "bash scripts/daemon.sh claude 60"

# Monitor
cat docs/sessions/index.md          # session history
gh pr list --state all --limit 5    # recent PRs

# Stop
tmux send-keys -t nightshift C-c
```

Full daemon operations guide: `docs/ops/DAEMON.md`

In one 4-hour daemon run, Nightshift autonomously:
- Shipped 19 PRs across 12 sessions
- Grew from 145 to 482 tests
- Completed Loop 1 (100%), started Loop 2 (45%)
- Released v0.0.3, v0.0.4, v0.0.5
- Validated itself against Phractal (real monorepo)
- Found and fixed its own bugs through self-evaluation

---

## Roadmap

- [x] Pluggable agent adapters (Codex, Claude)
- [x] Runner-enforced guard rails
- [x] Structured cycle outputs and state files
- [x] Post-cycle diff scoring before accepting a fix
- [x] Cycle-to-cycle state injection
- [x] Test writing incentives
- [x] Backend exploration forcing
- [x] Category balancing
- [x] Multi-repo support
- [x] Validated against real monorepo (Phractal)
- [x] Self-improving daemon (autonomous loop)
- [x] Cross-session learnings system
- [x] Self-evaluation against real repos
- [x] Loop 2: Repo profiler
- [x] Loop 2: Feature planner
- [x] Loop 2: Task decomposer
- [x] Loop 2: Sub-agent spawner
- [x] Loop 2: Wave integrator
- [ ] Loop 2: Feature CLI (`nightshift build`)
- [ ] Loop 2: End-to-end pipeline test
- [ ] Built-in to Orbit as a native feature

---

## License

MIT
