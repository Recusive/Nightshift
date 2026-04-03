# Nightshift — Development History

## Origin

Built on 2026-04-01 in a single session. The idea: an autonomous agent that runs while you sleep, systematically improving your codebase overnight. Like having a senior engineer on the night shift who reads through the whole codebase, fixes what they can, and leaves detailed notes about what they found.

The user wanted something that:

- Runs for 8-10 hours unattended
- Finds and fixes production-readiness issues across the full stack
- Logs anything too big to fix autonomously
- Documents everything in a shift log the day team reads first thing

## Architecture Decisions

### Git Worktree Isolation

**Problem:** The first test run used `git checkout -b` which stashed the user's uncommitted changes and switched their branch. When the user returned, their working state was disrupted.

**Solution:** All work happens in a git worktree (`docs/Nightshift/worktree-YYYY-MM-DD/`). The user's main checkout, branch, and uncommitted changes are never touched. The worktree directory is gitignored.

**Why inside the project:** Originally the worktree was created as a sibling directory (e.g., `../Snowflake-v0-nightshift-2026-04-01`). The user preferred keeping it inside the project at `docs/Nightshift/` so everything nightshift-related is in one place.

### Multi-Cycle Runner

**Problem:** A single Claude Code session hits context limits after ~30-60 minutes of active work. An 8-hour shift needs to survive context compression.

**Solution:** The `run.sh` script runs a bash `while` loop that spawns fresh `claude -p` sessions. Each session:

1. Reads the shift log from the previous cycle to know what's been done
2. Picks different files and strategies
3. Makes 3-5 fixes, updating the shift log after each one
4. Exits cleanly

The shift log on disk is the shared memory between cycles. Git commits are durable checkpoints.

**Cycle duration:** 30 minutes default for overnight runs. Test runs use shorter cycles with `--max-turns 45`.

### Shift Log as Primary Artifact

The shift log (`docs/Nightshift/YYYY-MM-DD.md`) is the most important output. Design decisions:

- **Updated after every fix, not batched.** If the session dies mid-cycle, the log is still current.
- **Fix and log update committed together.** One commit includes both the code change and the shift log entry. Prevents the log from falling out of sync.
- **Copied back to main repo after each cycle.** The runner script copies the shift log from the worktree to `docs/Nightshift/` in the user's main checkout so they can check progress without entering the worktree.
- **Summary rewritten by final cycle.** The last cycle's prompt prioritizes rewriting the Summary paragraph to reflect the entire shift, not just the first cycle.

### Fix Entry Format

Each fix documents three things:

- **What I found** — the specific issue (file, line, what's wrong)
- **Why it matters** — the production impact if left unfixed
- **What I did** — the exact change made

This evolved from an earlier format that only had "What was wrong" and "What I did" — missing the "why" made the log less useful for prioritization.

## Gotchas (Lessons from Testing)

### The Easy-Wins Trap

In early test runs, the agent spent entire shifts adding `type="button"` and `aria-label` attributes — real issues, but trivial ones. The shift log read like a linter output, not a senior engineer's notes.

**Fix:** Added a Gotchas section to the skill explaining this failure mode. Rather than rigid rules ("max 2 per category"), the skill explains *why* variety matters and what a wasted shift looks like. This respects Anthropic's guidance on avoiding railroading — give Claude the context to make good decisions instead of prescriptive rules.

### Frontend-Only Tunnel Vision

Across 3 test runs on the Orbit codebase (Tauri + React), the agent never touched the Rust backend. React components are numerous and visible, so they dominate discovery.

**Fix:** The Gotchas section explicitly calls this out. In the third test run, the agent did explore the Rust backend and documented in the Summary why it didn't fix anything there (the patterns were intentional with documented reasons). This is the correct behavior — exploring and making an informed decision is better than forcing fixes.

### Shift Log Not Updated Across Cycles

In run 2, the agent made 12 commits but only cycle 1 updated the shift log. Cycles 2-4 hit the turn limit before getting to log updates.

**Fixes applied:**

1. Increased `--max-turns` from 30 to 45 for test runs (50 for overnight)
2. Changed the Fix Workflow to bundle the log update with the fix commit
3. Made the runner prompts explicitly say "After EACH fix, immediately update the shift log"

### Summary Never Rewritten

The Summary paragraph was written by cycle 1 and never updated by later cycles — so it only described the first ~20 minutes of the shift.

**Fix:** The final cycle's prompt now explicitly prioritizes: "REWRITE the Summary paragraph to reflect the ENTIRE shift across all cycles." The template also includes an example of what a good summary looks like.

## Test Runs

### Run 1 (Worktree Agent Test)

- **Method:** Single subagent in Claude Code worktree
- **Duration:** ~10 minutes
- **Result:** 4 fixes (all a11y), 2 logged issues
- **Takeaway:** Skill works, but no variety

### Run 2 (First Multi-Cycle)

- **Method:** `nightshift-test.sh` with 4 cycles, `--max-turns 30`
- **Duration:** ~24 minutes
- **Result:** 12 fixes, but shift log only updated by cycle 1
- **Takeaway:** Need more turns, bundled log commits, stronger prompts

### Run 3 (Improved Skill + Gotchas)

- **Method:** `nightshift-test.sh` with 4 cycles, `--max-turns 45`
- **Duration:** ~33 minutes
- **Result:** 12 fixes across 25 files (4 error handling, 5 a11y, 3 code quality), Summary properly rewritten, shift log fully updated
- **Takeaway:** Gotchas section worked — agent explored theme system IPC, added `prefers-reduced-motion`, found keyboard activation gaps, looked at Rust backend

## Current State (v0.0.1)

### What works well

- Worktree isolation — user's working directory untouched
- Multi-cycle overnight runner with fresh sessions
- Shift log with what/why/how for every fix
- Copy-back to main repo after each cycle
- Gotchas section guides agent toward variety
- Final cycle rewrites Summary

### Known limitations

- Claude Code only (Codex, Copilot CLI planned)
- Still gravitates toward frontend over backend
- No test writing in most runs
- Agent occasionally finds the same issues as previous cycles despite reading the log
- `bun install` in worktree adds ~5s startup overhead per run

### Roadmap

- OpenAI Codex support
- GitHub Copilot CLI support
- Built-in to Orbit as a native feature
- Test generation as a primary fix category
- Deeper backend exploration strategies
- Plugin packaging for Claude Code marketplace

