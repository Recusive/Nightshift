# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Keeping This File Current

When you add, remove, or significantly change files, architecture, scripts, or conventions in this repo, update this CLAUDE.md to reflect those changes before finishing your work. This file is the source of truth for future Claude Code sessions — if it's stale, they start wrong. Treat it like a living document, not a snapshot.

## What This Is

Nightshift is an autonomous overnight codebase improvement agent — a Claude Code skill that runs while you sleep, systematically finding and fixing production-readiness issues across an entire codebase. It is not a compiled application; it's a prompt-based automation system (SKILL.md) + bash runners.

Built by Recursive Labs as part of the Orbit ecosystem. Currently Claude Code only.

## Project Structure

- **SKILL.md** — The core skill. Contains all operational logic: discovery strategies, priority order, fix/log decision framework, safety rails, shift log template, and gotchas. This is the file you edit to change how Nightshift behaves.
- **run.sh** — Overnight runner. Bash while-loop that spawns fresh `claude -p` sessions in 30-min cycles inside a git worktree. Configurable duration and cycle length.
- **test.sh** — Test runner. 4 short cycles (~5-10 min each) for validation. Same architecture as run.sh.
- **install.sh** — One-liner installer. Downloads SKILL.md + run.sh to `~/.claude/skills/nightshift/`.
- **docs/context/development-history.md** — Architecture decisions and lessons from test runs.

## Key Architecture Concepts

**Worktree isolation**: All work happens in `docs/Nightshift/worktree-YYYY-MM-DD/`. The user's main checkout, branch, and uncommitted changes are never touched. This was a deliberate fix after the first test run disrupted the user's working state by using `git checkout -b`.

**Multi-cycle design**: A single Claude session hits context limits after ~30-60 min. The runner spawns fresh `claude -p` sessions in a loop. The shift log on disk (`docs/Nightshift/YYYY-MM-DD.md`) is the shared memory between cycles — each cycle reads what was done and picks different areas.

**Shift log as primary artifact**: Updated after every fix (never batched). Fix and log entry are committed together in one atomic commit. Copied back to main repo after each cycle so progress is visible without entering the worktree. Summary is rewritten by the final cycle to cover the entire shift.

## Testing Changes

There is no unit test suite for Nightshift itself. To validate changes:

```bash
# Copy test.sh to a target project, then run it there:
cp test.sh /path/to/target-project/scripts/nightshift-test.sh
chmod +x /path/to/target-project/scripts/nightshift-test.sh
cd /path/to/target-project
./scripts/nightshift-test.sh
```

This runs 4 short cycles against the target codebase. Success criteria: shift log is populated with varied fixes, commits are clean, target project's tests still pass.

## Editing Conventions

- SKILL.md uses YAML frontmatter (`name`, `description`) for Claude Code skill registration. The `description` field controls when the skill triggers — it must list trigger phrases.
- Shell scripts use `set -e` and are meant to run from the target project's root directory (not from this repo).
- The runner scripts install dependencies in the worktree via `bun install --frozen-lockfile` falling back to `npm install`.
- `--max-turns 45` for test runs, `--max-turns 50` for overnight runs.

## Known Behavioral Issues

These are documented in `docs/context/development-history.md` and addressed in SKILL.md's Gotchas section:

- Agent gravitates toward easy accessibility fixes (aria-labels, type="button") over higher-impact work
- Frontend tunnel vision — React components dominate discovery while backend goes unexplored
- Later cycles sometimes rediscover issues from earlier cycles despite reading the shift log
- Test writing rarely happens in practice despite being priority #3
