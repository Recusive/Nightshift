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
  <img src="https://img.shields.io/badge/Claude-Compatible-F97316" alt="Claude Code" />
  <img src="https://img.shields.io/badge/License-MIT-22C55E" alt="MIT License" />
</p>

---

## About

Nightshift is an overnight codebase-hardening runner built by **[Recursive Labs](https://github.com/Recusive)** as part of the [Orbit](https://github.com/Recusive/Orbit-Release) ecosystem.

The original version relied mostly on prompt discipline. This version adds a real control plane:

- a Python orchestrator (`nightshift.py`)
- a schema-backed Codex adapter
- machine-readable shift state (`docs/Nightshift/YYYY-MM-DD.state.json`)
- runner-enforced guard rails, verification gates, and halt conditions

Codex is now the default unattended agent. Claude remains available through the same runner as a compatibility adapter.

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

### Key files

| File | Purpose |
|------|---------|
| `nightshift.py` | Orchestrator, policy engine, verifier, state manager |
| `nightshift.schema.json` | Required final-response schema for Codex cycles |
| `SKILL.md` | Interactive nightshift skill instructions |
| `run.sh` | Thin wrapper around `nightshift.py run` |
| `test.sh` | Thin wrapper around `nightshift.py test` |
| `.nightshift.json.example` | Optional per-repo config template |

---

## Install

### One-liner

```bash
curl -sL https://raw.githubusercontent.com/Recusive/Nightshift/main/install.sh | bash
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
  "agent": "codex",
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
  "stop_after_empty_cycles": 2
}
```

If `verify_command` is omitted, Nightshift tries to infer one from common repo manifests such as `package.json`, `Cargo.toml`, `go.mod`, and `pyproject.toml`.

---

## Usage

### Overnight run

```bash
~/.codex/skills/nightshift/run.sh
~/.codex/skills/nightshift/run.sh 10
~/.codex/skills/nightshift/run.sh 6 45
```

The default unattended path uses fresh `codex exec` cycles with the shift log plus the state file as cross-cycle memory.

### Short validation run

```bash
~/.codex/skills/nightshift/test.sh
~/.codex/skills/nightshift/test.sh --cycles 2 --cycle-minutes 5
```

### Direct orchestrator usage

```bash
python3 nightshift.py run
python3 nightshift.py test
python3 nightshift.py summarize
```

### Claude compatibility

```bash
python3 nightshift.py run --agent claude
```

Claude uses the same runner and verification logic, but Codex is the first-class unattended path.

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

- Python 3.10+
- Git
- `codex` CLI for the default unattended path
- `claude` CLI only if you want the compatibility adapter

---

## Roadmap

- [x] Codex unattended runner
- [x] Runner-enforced guard rails
- [x] Structured cycle outputs and state files
- [ ] Stronger Claude structured-output compatibility
- [ ] Smarter repo-type detection for category balancing
- [ ] Post-cycle diff scoring before accepting a fix
- [ ] Built-in to Orbit as a native feature

---

## License

MIT
