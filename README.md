# Nightshift

An autonomous overnight codebase improvement agent for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Run it before bed. Wake up to a shift log of fixes, a clean git branch, and a codebase that's more production-ready than when you left it.

## What it does

Nightshift acts like a senior engineer on the night shift. It systematically explores your codebase, finds production-readiness issues, fixes the small ones, and logs the big ones for you to review in the morning.

**What it fixes:**
- Security vulnerabilities (hardcoded secrets, injection vectors, unsafe eval)
- Crash paths and error handling gaps (unhandled errors, missing boundaries)
- Missing tests for critical paths
- Accessibility issues (aria-labels, keyboard navigation, focus management)
- Code quality violations (type safety, dead code, convention violations)
- Performance issues (memory leaks, unnecessary re-renders)
- Production polish (loading states, error messages, empty states)

**What it leaves for you:**
- Anything touching >5 files or requiring architecture changes
- Decisions that need product/design input
- Code that's actively being worked on (checks git blame)
- Build configs, CI/CD, deployment scripts

Everything is documented in a detailed shift log at `docs/Nightshift/YYYY-MM-DD.md`.

## How it works

```
Your repo (untouched)              Worktree (isolated copy)
├── your uncommitted changes       ├── nightshift/2026-04-01 branch
├── your current branch            ├── all fixes happen here
└── completely safe                └── shift log updated after each fix
```

Nightshift runs in a **git worktree** — an isolated copy of your repo. Your working directory, uncommitted changes, and current branch are never touched. Each fix gets its own atomic commit. The shift log is copied back to your main repo after each cycle so you can check progress anytime.

For long runs (overnight), the runner script spawns **fresh Claude sessions** in cycles. Each cycle reads the shift log from the previous cycle and continues where it left off. This avoids context window limits and lets it run for 8-10+ hours.

## Install

### As a Claude Code skill (recommended)

```bash
# Copy the skill to your global skills directory
mkdir -p ~/.claude/skills/nightshift
cp SKILL.md ~/.claude/skills/nightshift/
cp run.sh ~/.claude/skills/nightshift/
chmod +x ~/.claude/skills/nightshift/run.sh
```

### Quick start

Make sure `docs/Nightshift/worktree-*/` is in your project's `.gitignore`:

```bash
echo 'docs/Nightshift/worktree-*/' >> .gitignore
```

## Usage

### Interactive (in a Claude Code session)

```
/nightshift
```

### Overnight (from terminal)

```bash
# Default: 8 hours, 30 min cycles
~/.claude/skills/nightshift/run.sh

# Custom duration
~/.claude/skills/nightshift/run.sh 10       # 10 hours
~/.claude/skills/nightshift/run.sh 6 45     # 6 hours, 45 min per cycle
```

### Test run (4 short cycles)

```bash
# Copy test.sh to your project's scripts/ directory
cp test.sh scripts/nightshift-test.sh
chmod +x scripts/nightshift-test.sh
./scripts/nightshift-test.sh
```

## What you get in the morning

**Shift log** at `docs/Nightshift/YYYY-MM-DD.md`:
- Summary of the full shift
- Every fix documented with what was found, why it matters, and what was changed
- Logged issues that need human review (with suggested approaches)
- Recommendations for follow-up

**Git branch** `nightshift/YYYY-MM-DD`:
- One atomic commit per fix
- Clean commit messages with category tags
- All tests passing

**Review and merge:**
```bash
# See what it did
cat docs/Nightshift/2026-04-01.md
git log nightshift/2026-04-01 --oneline

# Cherry-pick individual fixes
git cherry-pick <commit-hash>

# Or merge the whole branch
git merge nightshift/2026-04-01

# Clean up
git worktree remove docs/Nightshift/worktree-2026-04-01
git branch -d nightshift/2026-04-01
```

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | The skill — instructions for the agent |
| `run.sh` | Overnight runner (multi-cycle, fresh sessions) |
| `test.sh` | Test runner (4 short cycles for validation) |

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- Git

## License

MIT
