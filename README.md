<p align="center">
  <img src="assets/icon.png" alt="Nightshift" width="128" />
</p>

<h1 align="center">Nightshift</h1>

<p align="center">
  <strong>Your overnight engineer. Autonomous. Thorough. Ready by morning.</strong><br/>
  Run it before bed. Wake up to a shift log of production-ready fixes, a clean git branch, and a codebase that's stronger than when you left it.
</p>

<p align="center">
  <a href="https://github.com/Recusive/Nightshift/releases/latest"><img src="https://img.shields.io/github/v/release/Recusive/Nightshift?label=Release&color=6366f1" alt="Release" /></a>
  <img src="https://img.shields.io/badge/Claude_Code-Supported-F97316?logo=anthropic&logoColor=white" alt="Claude Code" />
  <img src="https://img.shields.io/badge/Codex-Coming_Soon-6B7280" alt="Codex" />
  <img src="https://img.shields.io/badge/Copilot_CLI-Coming_Soon-6B7280" alt="Copilot CLI" />
  <img src="https://img.shields.io/badge/License-MIT-22C55E" alt="MIT License" />
</p>

---

## About

Nightshift is built by the **[Recursive Labs](https://github.com/Recusive)** team as part of the [Orbit](https://github.com/Recusive/Orbit) ecosystem — an AI-native development environment. While Nightshift will ship as a built-in feature in Orbit, it works as a standalone skill with any compatible coding agent today.

Currently supported: **Claude Code**. Support for OpenAI Codex, GitHub Copilot CLI, and other agents is coming.

---

## What It Does

Nightshift acts like a senior engineer on the night shift. It systematically explores your entire codebase — frontend, backend, infrastructure — finds production-readiness issues, fixes the small ones, and logs the big ones for you to review in the morning.

<details>
<summary><b>What it fixes</b></summary>

- **Security** — hardcoded secrets, injection vectors, unsafe eval, path traversal
- **Error handling** — unhandled errors, missing boundaries, crash paths, silent failures
- **Tests** — critical paths without coverage, happy-path-only test files
- **Accessibility** — missing aria-labels, keyboard navigation, focus management
- **Code quality** — type safety violations, dead code, convention drift
- **Performance** — memory leaks, unnecessary re-renders, missing lazy loading
- **Polish** — loading states, error messages, empty states, responsive edge cases

</details>

<details>
<summary><b>What it leaves for you</b></summary>

- Anything touching >5 files or requiring architecture changes
- Decisions that need product/design input
- Code that's actively being worked on (checks git blame)
- Build configs, CI/CD, deployment scripts
- Compiled artifacts and sidecars that need manual rebuilds

</details>

Everything is documented in a detailed shift log at `docs/Nightshift/YYYY-MM-DD.md`.

---

## How It Works

```
Your repo (untouched)              Worktree (isolated copy)
├── your uncommitted changes       ├── nightshift/2026-04-01 branch
├── your current branch            ├── all fixes happen here
└── completely safe                └── shift log updated after each fix
```

Nightshift runs in a **git worktree** — a fully isolated copy of your repo. Your working directory, uncommitted changes, and current branch are never touched.

For overnight runs, the runner spawns **fresh Claude sessions** in 30-minute cycles. Each cycle reads the shift log from the previous cycle and picks up where it left off. No context window limits. Runs for 8-10+ hours.

---

## Install

### One-liner

```bash
curl -sL https://raw.githubusercontent.com/Recusive/Nightshift/main/install.sh | bash
```

### Manual

```bash
mkdir -p ~/.claude/skills/nightshift
curl -sL https://github.com/Recusive/Nightshift/raw/main/SKILL.md -o ~/.claude/skills/nightshift/SKILL.md
curl -sL https://github.com/Recusive/Nightshift/raw/main/run.sh -o ~/.claude/skills/nightshift/run.sh
chmod +x ~/.claude/skills/nightshift/run.sh
```

Then add to your project's `.gitignore`:

```bash
echo 'docs/Nightshift/worktree-*/' >> .gitignore
```

---

## Usage

### Interactive

```
/nightshift
```
> In any Claude Code session. The agent sets up a worktree and starts the discovery-fix-document loop.

### Overnight

```bash
~/.claude/skills/nightshift/run.sh          # 8 hours (default)
~/.claude/skills/nightshift/run.sh 10       # 10 hours
~/.claude/skills/nightshift/run.sh 6 45     # 6 hours, 45 min per cycle
```
> Run from your project root before bed. Each cycle is a fresh Claude session.

### Test Run

```bash
# Copy to your project
cp test.sh scripts/nightshift-test.sh
chmod +x scripts/nightshift-test.sh

# 4 short cycles (~30 min total)
./scripts/nightshift-test.sh
```

---

## What You Get in the Morning

### Shift Log

`docs/Nightshift/YYYY-MM-DD.md` — the first thing you read:

- **Summary** — what was explored, most impactful fixes, what needs attention
- **Fixes** — every fix with what was found, why it matters, and what was changed
- **Logged issues** — things too big to fix autonomously, with suggested approaches
- **Recommendations** — patterns noticed, areas needing deeper work

### Git Branch

`nightshift/YYYY-MM-DD` — clean, atomic, ready to merge:

- One commit per fix
- Category-tagged commit messages
- All tests passing

### Review & Merge

```bash
# See what it did
cat docs/Nightshift/2026-04-01.md
git log nightshift/2026-04-01 --oneline

# Cherry-pick individual fixes
git cherry-pick <commit-hash>

# Or merge everything
git merge nightshift/2026-04-01

# Clean up
git worktree remove docs/Nightshift/worktree-2026-04-01
git branch -d nightshift/2026-04-01
```

---

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | The skill — discovery strategies, gotchas, safety rails, shift log template |
| `run.sh` | Overnight runner — multi-cycle, fresh sessions, worktree isolation |
| `test.sh` | Test runner — 4 short cycles for validation |
| `install.sh` | One-liner installer |

---

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- Git

---

## Roadmap

- [ ] OpenAI Codex support
- [ ] GitHub Copilot CLI support
- [ ] Built-in to Orbit as a native feature
- [ ] Test generation as a primary fix category
- [ ] Deeper backend/Rust exploration strategies

---

## Built By

<p>
  <a href="https://github.com/Recusive"><strong>Recursive Labs</strong></a> — the team behind <a href="https://github.com/Recusive/Orbit">Orbit</a>, an AI-native development environment.
</p>

## License

MIT
