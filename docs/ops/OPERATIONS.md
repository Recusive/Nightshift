# Nightshift Operations Guide

You are an AI agent starting a session in the Nightshift repo. This document is your map. It explains every system, every folder, every file, and exactly how to use, update, and maintain each one.

You should have already read `docs/handoffs/LATEST.md` before this file. If you haven't, read it first — it's shorter and tells you what to do next. This document is the full reference for every system in the repo.

---

## The Repo at a Glance

```
Nightshift/
├── nightshift/                  ← THE PRODUCT (Python package)
├── tests/                       ← TEST SUITE
├── docs/
│   ├── handoffs/                ← SHORT-TERM MEMORY (read LATEST.md first every session)
│   ├── vision/                  ← LONG-TERM DIRECTION (where we're going)
│   ├── vision-tracker/          ← SCOREBOARD (progress bars)
│   ├── changelog/               ← HISTORY (per-version release notes)
│   ├── prompt/                  ← THE SELF-IMPROVING PROMPT + FEEDBACK
│   ├── ops/                     ← THIS FILE (how everything works)
│   ├── context/                 ← LEGACY CONTEXT (architecture decisions from early builds)
│   └── Nightshift/              ← RUNTIME ARTIFACTS (shift logs, state files, worktrees)
├── CLAUDE.md                    ← AGENT INSTRUCTIONS (always loaded)
├── nightshift/SKILL.md          ← THE HARDENING SKILL PROMPT
├── nightshift.schema.json       ← STRUCTURED OUTPUT SCHEMA
├── .nightshift.json.example     ← PER-REPO CONFIG TEMPLATE
├── .nightshift.json             ← THIS REPO'S CONFIG (verify command override)
├── scripts/run.sh / scripts/test.sh  ← THIN SHELL WRAPPERS
├── scripts/install.sh           ← ONE-LINER INSTALLER
├── pyproject.toml               ← PROJECT CONFIG (mypy, ruff, pytest)
├── requirements-dev.txt         ← PINNED DEV TOOL VERSIONS
├── scripts/check.sh             ← LOCAL CI SCRIPT
└── .github/workflows/ci.yml     ← CI PIPELINE
```

---

## System 1: Handoffs (`docs/handoffs/`)

### What it is
Your short-term memory. Instead of reading the entire repo every session, you read ONE file and know exactly where things stand.

### Files
| File | Purpose |
|------|---------|
| `LATEST.md` | The most recent handoff. **Read this first every session.** |
| `NNNN.md` | Individual session handoffs (0001.md, 0002.md, ...) |
| `README.md` | Format spec and rules |
| `weekly/week-YYYY-WNN.md` | Compacted weekly summaries |

### How to use
1. **Start of session**: Read `LATEST.md`. It tells you what was built, what's broken, what to build next, and which files to look at.
2. **End of session**: Write a new handoff `NNNN.md` (increment the number). Copy it to `LATEST.md`.
3. **Compaction**: When 7+ numbered files exist, merge them into `weekly/week-YYYY-WNN.md` and delete the originals. Keep only what's still relevant.

### Format
```markdown
# Handoff #NNNN
**Date**: YYYY-MM-DD
**Version**: vX.X.X
**Session duration**: ~Xh

## What I Built
## Decisions Made
## Known Issues
## Current State
## Next Session Should
## Where to Look
```

### Rules
- Carry forward known issues from the previous handoff if you didn't fix them
- Drop resolved items
- Be ruthless about brevity — if the next agent doesn't need it, don't write it
- Always update LATEST.md after writing your handoff

---

## System 2: Vision Docs (`docs/vision/`)

### What it is
The north star. Describes what Nightshift is becoming: two autonomous loops and a self-maintaining repo. Written for AI agents — explains the architecture, gives examples, lists open problems.

### Files
| File | Purpose |
|------|---------|
| `00-overview.md` | The full vision: both loops, meta-prompt, architecture, success criteria |
| `01-loop1-hardening.md` | Loop 1 deep dive: what exists, what's enforced, 6-item improvement roadmap |
| `02-loop2-feature-builder.md` | Loop 2 deep dive: phases, sub-agent architecture, open design questions |

### How to use
- **Read when**: The handoff points you here, or you need to understand the big picture before making a design decision.
- **Don't read when**: The handoff has enough context for your task. Save tokens.

### How to update
- When you complete a roadmap item, mark it done in the relevant file
- When you make a design decision for Loop 2, update the open questions section
- When you discover a new problem or pattern, add it to the relevant file
- Keep the tone: written for an AI agent who has never seen the repo

---

## System 3: Vision Tracker (`docs/vision-tracker/`)

### What it is
A scoreboard showing progress toward the vision. Progress bars for every component across all four areas: Loop 1, Loop 2, Self-Maintaining, Meta-Prompt.

### Files
| File | Purpose |
|------|---------|
| `TRACKER.md` | The single tracker file with all progress bars |

### How to use
- **Read when**: Start of session (in the handoff, the percentages come from here). Or when you need to decide what to build next.

### How to update
Every session, after you finish building:
1. Check each component you affected
2. Update its status: `Not started` → `In progress` → `Done`
3. Update its progress bar: `░` for not done, `█` for done (20 chars = 100%)
4. Recalculate section percentages: `(done components / total components) * 100`
5. Recalculate overall: weighted average (Loop 1: 40%, Loop 2: 30%, Self-Maintaining: 15%, Meta-Prompt: 15%)
6. Update "Last updated" date

### Rules
- Don't inflate progress. If something is half-done, say "In progress" with honest percentage.
- If you broke something, move it back.
- "Done" means: code exists, tests pass, it works in a real run.

---

## System 4: Changelog (`docs/changelog/`)

### What it is
Per-version release notes. One file per version. Documents what was added, changed, fixed, removed.

### Files
| File | Purpose |
|------|---------|
| `README.md` | Index with version table and contributor guide |
| `v0.0.1.md` | Initial Beta release notes |
| `v0.0.2.md` | Control Plane release notes |
| `vX.X.X.md` | Future versions — one file each |

### How to use
- **Read when**: You need to understand what changed in a specific version.

### How to update
After every session:
1. Find the current version file (check `README.md` table for "In progress")
2. Add your changes under the right section: `Added`, `Changed`, `Fixed`, `Removed`, `Internal`
3. Tag each entry: `[feat]`, `[fix]`, `[refactor]`, `[test]`, `[docs]`, `[meta]`, `[remove]`

### When to create a new version file
When all planned features for the current version are done:
1. Update current version status to "Released" in `README.md`
2. Create new `vX.X.X.md` with a codename and "In progress" status
3. Add it to the `README.md` table
4. Tag and release on GitHub

---

## System 5: The Self-Improving Prompt (`docs/prompt/`)

### What it is
The prompt the human pastes at the start of each session. It tells you (the agent) to read the handoff, decide what to build, propose it, build it, test it, update everything, and push.

### Files
| File | Purpose |
|------|---------|
| `evolve.md` | The prompt itself. 10 steps: awareness → decide → propose → build → verify → update docs → pre-push checklist → branch/PR/merge → release check → report |
| `feedback/README.md` | Guide for the human on how to write feedback |
| `feedback/YYYY-MM-DD.md` | Human feedback files (if any) |

### How to use
- The human pastes `evolve.md` content into Claude Code. You follow it.
- If you learn something that would help future sessions, add it to `evolve.md`.

### How to update
- If a step is consistently causing problems, fix the instructions
- If you discover a better priority order, update the priority engine in Step 2
- If new systems are added (like this ops guide), add them to Step 1's reading list
- Keep the prompt tight — every line should earn its place

### Feedback loop
After testing what you built, the human drops notes in `feedback/`. Next session reads them. If feedback contradicts the prompt's priority list, feedback wins.

---

## System 6: The Product (`nightshift/`)

### What it is
The Python package that IS Nightshift. The overnight hardening runner.

### Modules
| Module | Responsibility | Key functions |
|--------|---------------|---------------|
| `types.py` | TypedDicts for all data structures | `NightshiftConfig`, `ShiftState`, `CycleResult`, `CycleVerification` |
| `constants.py` | Constants + utilities | `DATA_VERSION`, `DEFAULT_CONFIG`, `SHIFT_LOG_TEMPLATE`, `now_local()`, `print_status()` |
| `errors.py` | Exception class | `NightshiftError` |
| `shell.py` | Subprocess execution | `run_command()`, `run_capture()`, `git()`, `command_exists()`, `run_shell_string()` |
| `config.py` | Config + agent resolution | `merge_config()`, `resolve_agent()`, `prompt_for_agent()`, `infer_package_manager()`, `infer_verify_command()` |
| `state.py` | State I/O + mutation | `load_json()`, `write_json()`, `read_state()`, `append_cycle_state()`, `top_path()` |
| `worktree.py` | Git worktree lifecycle | `ensure_worktree()`, `ensure_shift_log()`, `sync_shift_log()`, `revert_cycle()`, `cleanup_safe_artifacts()` |
| `cycle.py` | Per-cycle logic | `build_prompt()`, `command_for_agent()`, `verify_cycle()`, `evaluate_baseline()`, `extract_json()`, `blocked_file()` |
| `cli.py` | Entry points + main loop | `run_nightshift()`, `summarize()`, `verify_cycle_cli()`, `build_parser()`, `main()` |
| `__main__.py` | Package entry point | `python3 -m nightshift` |
| `__init__.py` | Re-exports all public names | Everything above |

### Dependency flow
```
types → constants → errors → shell → config/state → worktree → cycle → cli
```
No circular imports. Each module only imports from modules to its left.

### How to modify
1. Read the module you're changing AND its callers
2. Follow existing patterns (look at how similar functions are structured)
3. Add types to `types.py` if you're introducing new data structures
4. Write tests in `tests/test_nightshift.py`
5. Run full suite: `python3 -m pytest tests/ -v`

---

## System 7: Tests (`tests/`)

### What it is
123 pytest tests covering every pure function, config, state, CLI, and integration.

### Files
| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `test_nightshift.py` | All tests (organized by class: `TestConstants`, `TestExtractJson`, `TestBuildPrompt`, etc.) |

### How to run
```bash
python3 -m pytest tests/ -v                    # full suite
python3 -m pytest tests/ -v -k "TestBuildPrompt"  # specific class
```

### How to add tests
1. Find the test class for the module you're testing (or create one)
2. Write test methods following existing patterns
3. Use `tmp_path` fixture for filesystem tests
4. Use `unittest.mock.patch` for stdin/tty mocking
5. Run the full suite — make sure nothing else broke

---

## System 8: CI/CD

### Files
| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` | GitHub Actions pipeline |
| `scripts/check.sh` | Local CI (mirrors the GH Actions pipeline) |
| `pyproject.toml` | mypy strict, ruff rules, pytest config |
| `requirements-dev.txt` | Pinned dev tool versions |

### Pipeline stages
1. **Lint** — `ruff check` + `ruff format --check`
2. **Type check** — `mypy --strict`
3. **Test** — `pytest` on Python 3.9 + 3.12
4. **Integration** — dry-run both agents
5. **Validate artifacts** — schema/config parsing, install.sh references, shell syntax

### How to run locally
```bash
bash scripts/check.sh
```

---

## System 8b: Pre-Push Checklist (`docs/ops/PRE-PUSH-CHECKLIST.md`)

### What it is
A mandatory checklist the agent runs through before every `git push`. Catches forgotten doc updates, missing handoffs, stale tracker percentages, and unstaged files.

### How to use
Before pushing, read the checklist and answer every item. Output the results in the session. If anything fails, fix it. Then push.

### When it runs
- Automatically: the evolve prompt (Step 7) mandates it before every commit/push
- Manually: if you're pushing outside the evolve workflow, read it yourself

---

## System 9: CLAUDE.md

### What it is
The file Claude Code always loads at session start. Contains project description, structure, architecture, conventions.

### How to update
- When you add/remove/rename modules: update the project structure section
- When you change conventions: document them
- When you add new systems: add them to the structure
- Keep it factual — this is reference, not narrative

---

## System 10: Skill + Schema

### Files
| File | Purpose |
|------|---------|
| `nightshift/SKILL.md` | The prompt injected into agent cycles during hardening shifts. Discovery strategies, priority order, fix/log framework, safety rails, shift log template. |
| `nightshift.schema.json` | JSON Schema for structured agent output. Codex uses `--output-schema`. Claude parses with `extract_json()`. |
| `.nightshift.json.example` | Config template users copy to their repos |
| `.nightshift.json` | This repo's config (sets verify command to use correct Python) |

### How to update nightshift/SKILL.md
- Edit to change agent behavior during hardening shifts
- Keep YAML frontmatter (`name`, `description`) — the `description` controls when the skill triggers
- The shift log template is in `constants.py`, not SKILL.md

---

## System 11: Shell Scripts + Installer

### Files
| File | Purpose |
|------|---------|
| `scripts/run.sh` | Sets PYTHONPATH, runs `python3 -m nightshift run "$@"` |
| `scripts/test.sh` | Sets PYTHONPATH, runs `python3 -m nightshift test "$@"` |
| `scripts/install.sh` | Downloads entire package to `~/.codex/skills/nightshift/` and `~/.claude/skills/nightshift/` |
| `scripts/daemon.sh` | Self-improving loop. Runs the evolve prompt forever in autonomous mode. Uses lockfile to prevent overlapping instances. |
| `scripts/validate-docs.sh` | Doc consistency validator. Checks test counts, module registration, tracker percentages, path references. Fails if anything drifts. |
| `scripts/smoke-test.sh` | End-to-end test against a real repo (default: Phractal). Proves the system works, not just unit tests. |
| `scripts/context-map.sh` | Generates a slim context file with module sizes, function signatures, dependency graph, test counts. Saves tokens. |
| `scripts/rollback.sh` | Reverts a merged PR cleanly. Creates revert branch + PR. |

### Daemon (continuous self-improvement)

```bash
./scripts/daemon.sh              # run forever with claude (default)
./scripts/daemon.sh codex        # run forever with codex
./scripts/daemon.sh claude 120   # 120s pause between sessions
```

Each session: reads handoff, picks highest priority, builds, tests, verifies behavior, pushes, creates PR, reviews with sub-agent, merges. Then the next session starts.

Session logs saved to `docs/sessions/`. Stop with Ctrl+C.

The daemon injects an auto-approve prefix that:
- Skips the human confirmation step (Step 3)
- Enforces the production-readiness rule: nothing ships unless the agent is 100% certain it works
- After 3 failed attempts on one item, logs it and moves to the next priority

### How to update
- If you add a new Python module, add it to the `PACKAGE_FILES` list in `scripts/install.sh`
- Shell scripts are thin wrappers — almost never need editing
- Always run `bash -n scripts/script.sh` to syntax-check after editing

---

## System 12: Runtime Artifacts (`docs/Nightshift/`)

### What it is
Created when Nightshift runs. NOT checked into git (except shift logs).

### Files (generated at runtime)
| File | Purpose | Git status |
|------|---------|------------|
| `YYYY-MM-DD.md` | Shift log (human-readable) | Committed to nightshift branch |
| `YYYY-MM-DD.state.json` | Machine-readable state | Gitignored |
| `YYYY-MM-DD.runner.log` | Raw runner output | Gitignored |
| `worktree-YYYY-MM-DD/` | Isolated git worktree | Gitignored |

### How to clean up after a test run
```bash
git worktree remove docs/Nightshift/worktree-YYYY-MM-DD
git branch -d nightshift/YYYY-MM-DD
rm -f docs/Nightshift/YYYY-MM-DD.state.json docs/Nightshift/YYYY-MM-DD.runner.log
```

---

## Git Workflow

### Branching strategy
- **`main` is protected.** Never push directly to main.
- Every session creates a feature branch: `feat/description`, `fix/description`, `docs/description`, `release/vX.X.X`
- Push the branch, create a PR, review with a sub-agent, merge if it passes.

### The PR flow (you do this every session)
```
1. Create branch:    git checkout -b feat/diff-scorer
2. Build + test:     (the usual workflow)
3. Commit:           git add [files] && git commit -m "feat: add diff scorer"
4. Push:             git push origin feat/diff-scorer
5. Create PR:        gh pr create --title "feat: add diff scorer" --body "..."
6. Review:           spawn a sub-agent to review the diff (see below)
7. Merge:            gh pr merge --squash (if review passes)
8. Clean up:         git checkout main && git pull && git branch -d feat/diff-scorer
```

### Sub-agent PR review
Before merging, spawn a sub-agent with this task:
```
Review this PR for: bugs, logic errors, security issues, missing tests, 
convention violations, and whether it matches the stated goal. 
Read the diff with `gh pr diff <number>`. 
Report: PASS (merge it) or FAIL (list what needs fixing).
```
If the review says FAIL, fix the issues, push again, re-review. Only merge on PASS.

### Merge strategy
- **Always use regular merge** (`--merge`), never `--squash`. Every commit on the branch must be preserved on main. If you made 10 commits, all 10 appear in main's history.
- **Always use `--admin` flag** when merging PRs. The agent is the sole creator, maintainer, and admin of this repo. No human review approval is required. The sub-agent code review replaces human review.
- Example: `gh pr merge --merge --delete-branch --admin`

---

## Release Strategy

### When to release
You decide. Here are the rules:

**Patch release (v0.0.X → v0.0.X+1):**
- Bug fixes only
- No new features
- Example: fixed `merge_config` shallow update, fixed `run_command` timeout

**Minor release (v0.X.0 → v0.X+1.0):**
- New features that change what Nightshift can do
- Example: added diff scorer, added Loop 2 scaffolding, added multi-repo support

**Major release (v1.0.0):**
- Loop 1 and Loop 2 both work in production
- Not happening anytime soon

### How to decide
After merging a PR, ask yourself:
1. **Is this a meaningful user-facing change?** If someone installed Nightshift yesterday, would they want this update? → Release.
2. **Is this just internal cleanup?** Tests, docs, refactors that don't change behavior? → Don't release. Batch with the next real change.
3. **Is this a bug fix for something that affects users?** → Patch release immediately.
4. **Did I just finish a planned milestone?** Check the version changelog — are all planned items done? → Release.

### How to release

Release commits are the ONE exception to the PR rule. They go directly on main because they're purely ceremonial (changelog status change + tag).

```bash
# 0. Verify tests pass on the exact commit you're tagging
make check

# 1. Update changelog: mark current version as "Released", create next version file
# 2. Update changelog README table
# 3. Commit directly on main:
git add docs/changelog/
git commit -m "release: vX.X.X -- Codename"

# 4. Tag and push
git tag vX.X.X
git push origin main && git push origin vX.X.X

# 5. Create GitHub release
#    Release notes MUST include:
#      a) A highlights/summary section at the top
#      b) The FULL changelog from docs/changelog/vX.X.X.md below it
#    The release page must be self-contained — no "see file for details" links.
gh release create vX.X.X \
  --title "vX.X.X -- Codename" \
  --notes "$(cat <<EOF
## Highlights
- [curated summary bullets]

---

$(cat docs/changelog/vX.X.X.md)
EOF
)"
```

Or: `make release VERSION=X.X.X CODENAME=Name`

---

## Version Milestones

What defines each version. Use this to know when a release is ready.

### v0.0.2 — Control Plane (current)
- [x] Python orchestrator replacing bash
- [x] Pluggable agent adapters (Codex + Claude)
- [x] Runner-enforced guard rails
- [x] Machine-readable state
- [x] 123-test suite
- [x] Vision docs + self-improving prompt
- [x] Changelog + tracker + handoffs + ops guide
- [ ] Commit and push to main
- [ ] Tag and release on GitHub

### v0.0.3 — Intelligence (next)
- [ ] Fix `merge_config` shallow update (security bug)
- [ ] Fix `run_command` timeout race (reliability bug)
- [ ] Post-cycle diff scorer
- [ ] Cycle-to-cycle state injection
- [ ] Validated against Phractal test target

### v0.0.4 — Agent Quality
- [ ] Test writing incentives
- [ ] Backend exploration forcing
- [ ] Smarter category balancing

### v0.0.5 — Loop 2 Scaffold
- [ ] Feature planner module
- [ ] Task decomposer module
- [ ] `nightshift build` CLI command (even if basic)

### v1.0.0 — Production
- [ ] Loop 1 runs reliably overnight on real repos
- [ ] Loop 2 can build a simple feature end-to-end
- [ ] Both loops tested on 3+ real repos

---

## Error Recovery

Things go wrong. Here's what to do.

### Dirty worktree from a crashed session
```bash
# Check if a worktree exists
git worktree list

# Remove it
git worktree remove docs/Nightshift/worktree-YYYY-MM-DD --force

# Delete the branch if needed
git branch -D nightshift/YYYY-MM-DD

# Clean up artifacts
make clean
```

### Tests pass locally, fail in CI
1. Check the CI log: `gh run view --log-failed`
2. Common causes:
   - Python version mismatch (CI uses 3.9 + 3.12, you might be on 3.13)
   - Missing dependency (CI installs from `requirements-dev.txt`)
   - File not committed (works locally because it exists, fails in CI because it's not staged)
3. Fix, push, watch CI again

### Handoff is wrong or corrupt
1. Read the previous handoffs (numbered files) to reconstruct state
2. Read `git log --oneline -20` for recent history
3. Read the tracker for current progress
4. Write a corrected LATEST.md

### Agent built the wrong thing
1. Don't panic — it's on a branch, not main
2. Close the PR: `gh pr close <number>`
3. Delete the branch: `git push origin --delete <branch>`
4. Write a feedback note in `docs/prompt/feedback/` explaining what went wrong
5. Next session reads the feedback and adjusts

### Merge conflict on PR
1. Pull main: `git checkout main && git pull`
2. Rebase your branch: `git checkout <branch> && git rebase main`
3. Resolve conflicts, continue rebase
4. Force push branch: `git push origin <branch> --force-with-lease`
5. PR auto-updates

---

## Test Target Repo

For end-to-end validation, use the Phractal repo:

```bash
# Clone (one-time)
git clone https://github.com/fazxes/Phractal.git /tmp/nightshift-test-target

# Run a quick test shift
cd /tmp/nightshift-test-target
python3 -m nightshift test --agent claude --cycles 2 --cycle-minutes 5

# Check results
cat docs/Nightshift/YYYY-MM-DD.md
```

This is a real full-stack project with real issues. Use it to validate that Loop 1 actually finds and fixes things.

After testing, document results in the handoff: "Tested against Phractal — found X issues, Y were real, Z were false positives."

---

## Environment

### Python
Use whatever `python3` resolves to. The codebase targets Python 3.9+ (the minimum in CI). Do NOT hardcode absolute Python paths in any config or script. If a specific Python is needed for local testing, set it via environment variable, not in committed files.

### Dev tools
Pinned in `requirements-dev.txt`. Install with:
```bash
pip install -r requirements-dev.txt
```

### Quick commands
```bash
make test          # run tests
make check         # full CI locally
make dry-run       # preview cycle prompt
make quick-test    # 2-cycle validation
make clean         # remove runtime artifacts
```

---

## The Session Workflow

Every session follows `docs/prompt/evolve.md` Steps 1-10. In short:

```
Step 1:  Read handoff (LATEST.md) --> status report
Step 2:  Decide what to build (priority engine)
Step 3:  Propose to human --> wait for "go"
Step 4:  Build + write tests
Step 5:  Verify (make check)
Step 6:  Update ALL docs (handoff, changelog, tracker, vision, CLAUDE.md, etc.)
Step 7:  Pre-push checklist (docs/ops/PRE-PUSH-CHECKLIST.md)
Step 8:  Branch, commit, push, PR, sub-agent review, merge
Step 9:  Release check (is this a milestone?)
Step 10: Report
```

See `docs/prompt/evolve.md` for the full details of each step. This summary exists for quick reference only — the evolve prompt is authoritative.

---

## Quick Reference: What to Update When

| After you... | Update these |
|---|---|
| Build a feature | handoff, changelog, tracker, tests |
| Fix a bug | handoff, changelog, tracker (if it was tracked) |
| Change project structure | handoff, CLAUDE.md, scripts/install.sh, OPERATIONS.md |
| Complete a version milestone | changelog (new version file), tracker, README table, GitHub release |
| Make a design decision | handoff, vision docs (if architectural) |
| Learn something surprising | handoff, evolve.md (if it helps future sessions) |
| Add a new system/doc | this file (OPERATIONS.md), CLAUDE.md |
| Merge a PR | check if release criteria are met |
