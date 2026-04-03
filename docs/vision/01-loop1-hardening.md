# Loop 1 — Hardening Loop Deep Dive

## Current State

Loop 1 is built and working. Here is exactly what exists:

- `nightshift/` Python package — orchestrator with 8 modules
- `nightshift.schema.json` — structured output schema for agent cycles
- `nightshift/SKILL.md` — the prompt that tells the agent how to behave during a hardening shift
- `scripts/run.sh` / `scripts/test.sh` — thin wrappers that invoke `python3 -m nightshift run|test`
- 123 unit tests covering all pure functions and CLI entry points
- Codex and Claude adapters — both headless, both go through the same verification

### What the orchestrator enforces today

| Guard Rail | How It Works |
|---|---|
| Max 3 fixes per cycle | Rejects cycle if commits exceed limit |
| Max 5 files per fix | Checks each fix's file list against limit |
| Max 12 files per cycle | Counts unique non-log files across all commits |
| Max 4 low-impact fixes per shift | Tracks cumulative `impact: "low"` across cycles |
| Blocked paths | CI, deploy, infra, vendor, lockfiles — hard reject |
| Hot file protection | Files with >2 commits in last 7 days are flagged |
| Category dominance | Rejects if one category exceeds 50% of total fixes |
| Path bias | Rejects if same top-level dir is dominant for 3 consecutive cycles |
| Clean worktree | Rejects cycle if worktree is dirty after agent finishes |
| Shift log in every commit | Rejects commits that don't include the shift log update |
| No file deletions | Rejects any commit with `D` in git name-status |
| Baseline verification | Runs repo tests before starting — enters log-only mode if they fail |
| Post-cycle verification | Runs repo tests after each cycle — reverts on failure |
| Halt conditions | Stops after 2 consecutive failed verifications or 2 empty cycles |

### What the agent is told (via prompt)

The `build_prompt()` function in `cycle.py` constructs a per-cycle prompt that includes:
- Cycle number and whether it's the final cycle
- All hard limits (copied from config)
- Which files are hot (recent git activity)
- Which top-level paths were dominant in prior cycles
- Whether log-only mode is active
- Blocked paths and globs
- Instructions to end with a JSON object matching the schema

The `nightshift/SKILL.md` file provides the broader behavioral guidance:
- Discovery strategies (how to explore the codebase)
- Priority order (Security > Error Handling > Tests > A11y > Code Quality > Performance > Polish)
- Fix vs. log decision framework (when to fix, when to just document)
- Shift log format and conventions
- Safety rails (what never to touch)

## Improvement Roadmap

These are ordered by impact. Build them in this order unless you have a strong reason not to.

### 1. Post-Cycle Diff Scorer

**Problem**: Currently, any cycle that passes verification is accepted. A cycle that adds `type="button"` to 3 buttons is accepted the same as a cycle that fixes a SQL injection.

**Solution**: After verification passes, score the diff:
- Read the actual changes (git diff)
- Classify: security fix? error handling? trivial cleanup?
- Score on a 1-10 scale based on production impact
- If score < threshold (configurable, default 3), revert and tell the agent to try harder

**Where it goes**: New function in `cycle.py`, called between `verify_cycle()` and `append_cycle_state()`.

### 2. Cycle-to-Cycle State Injection

**Problem**: Each cycle reads the shift log to see what's done, but the state file has richer information (categories touched, paths visited, file lists). The agent doesn't see this.

**Solution**: Include a condensed state summary in the prompt. Not the full JSON — a human-readable paragraph like: "Previous cycles fixed 2 Security issues in `src/api/` and 1 Error Handling issue in `src/components/`. Categories not yet explored: Tests, A11y, Performance, Polish. Avoid `src/api/` and `src/components/` — explore `src/lib/`, `src/hooks/`, `server/`."

**Where it goes**: Extend `build_prompt()` in `cycle.py` to read from the state dict and generate this summary.

### 3. Test Writing Incentives

**Problem**: Agents rarely write tests despite it being priority #3. They prefer quick single-file fixes.

**Solution**: 
- Track test-writing separately in the state (`tests_written: 0`)
- After cycle 3, if no tests have been written, add a prompt escalation: "You have not written any tests yet. Your next fix MUST include a test file."
- Give test-writing cycles a higher diff score automatically

**Where it goes**: Counter in `state.py`, prompt logic in `cycle.py`.

### 4. Backend Exploration Forcing

**Problem**: In full-stack repos, agents gravitate toward React components.

**Solution**:
- During prompt building, analyze the repo structure and identify backend directories
- If the first 3 cycles all touched frontend paths, inject: "The backend has not been explored. Focus this cycle on `server/`, `api/`, `lib/`, or equivalent."
- Use the existing path bias detection but make it directional (not just "don't repeat", but "go here instead")

**Where it goes**: New function in `cycle.py` that analyzes repo structure, feeds into `build_prompt()`.

### 5. Multi-Repo Support

**Problem**: Currently runs on one repo at a time.

**Solution**: Accept a list of repo paths. Create worktrees in each. Cycle between repos (not just cycles within one repo). Shared state tracks which repos got attention.

**Where it goes**: New `multi` subcommand in `cli.py`, state extension in `state.py`.

### 6. Deep Merge for Config

**Problem** (found by Nightshift itself): `merge_config()` uses shallow `dict.update()`. If you set `blocked_paths` in `.nightshift.json`, it replaces all defaults instead of extending.

**Solution**: For list fields, extend instead of replace. Or provide `blocked_paths_add` / `blocked_paths_remove` keys.

**Where it goes**: `config.py`, `merge_config()` function.
