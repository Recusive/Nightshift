# Contributing to Nightshift

This guide is written for autonomous agents contributing to this repo. The resident maintainer is also an agent (the Nightshift daemon). Both sides need machine-parseable conventions to collaborate without human mediation.

**Human contributors**: This guide applies to you too. The conventions are strict but simple. Your agent (Claude, Codex, etc.) should read this file before making changes.

## Before You Start

1. Read `CLAUDE.md` -- it has the full project conventions, code quality rules, and dependency flow. Do not duplicate work already specified there.
2. This repo uses Python 3.9+, strict mypy, ruff linting, and ASCII-only source files. These are non-negotiable.
3. The CI pipeline (`make check`) must pass. It runs ruff, mypy, and pytest against `nightshift/` (including `nightshift/tests/`) and `Recursive/tests/`.

## Repo Structure

The repo has two main codebases and a runtime state directory:

```
nightshift/          # Product: the autonomous engineering tool
  core/              # errors, types, constants, shell, state
  settings/          # config, eval_targets
  owl/               # cycle, readiness, scoring
  raven/             # coordination, decomposer, e2e, feature,
                     #   integrator, planner, profiler, subagent, summary
  infra/             # module_map, multi, worktree
  tests/             # Product tests (847+)
  scripts/           # Product shell scripts (check, install, run, smoke-test, test)
  cli.py             # CLI entry point
  SKILL.md           # Skill registration (YAML frontmatter)

Recursive/           # Framework: the autonomous dev engine
  agents/            # Review agent definitions (code-reviewer, safety-reviewer, etc.)
  engine/            # Daemon runtime (daemon.sh, lib-agent.sh, pick-role.py, watchdog.sh)
  operators/         # Role prompts (build/, review/, oversee/, strategize/, achieve/)
  scripts/           # Framework scripts (init, rollback, validate-tasks, list-tasks)
  tests/             # Framework tests
  ops/               # Operational docs
  lib/               # Shared libraries
  templates/         # Templates
  prompts/           # Prompt files

.recursive/          # Runtime state (daemon-managed, mostly hands-off)
  handoffs/          # Session memory
  tasks/             # Work queue
  sessions/          # Session logs
  healer/            # System health observations
  vision-tracker/    # TRACKER.md -- updated by daemon after each session
  changelog/         # Version changelog entries
  autonomy/          # Autonomy score reports
  evaluations/       # Eval results
  reviews/           # Code review artifacts
  plans/             # Plan documents
  strategy/          # Strategy reports
  learnings/         # Hard-won knowledge index
  architecture/      # MODULE_MAP.md and architecture docs
  vision/            # Project vision docs

.claude/agents/      # Symlinks to Recursive/agents/ -- do not edit here
```

## Branch and Commit Conventions

### Branch naming

```
feat/short-description    # new feature
fix/short-description     # bug fix
docs/short-description    # documentation only
refactor/short-description # code restructuring
```

Use lowercase, hyphens between words. Keep it under 50 characters.

### Commit messages

```
type: one-line description of what and why
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`.

- Describe WHAT changed and WHY, not HOW.
- One logical change per commit.
- No merge commits in your branch -- rebase if needed.

## PR Format

The resident review daemon parses PRs programmatically. Follow this structure exactly:

```markdown
## Summary
- [bullet point: what this PR does]
- [bullet point: why]

## Test plan
- [how to verify this works]
```

**Title**: `type: short description` (under 70 characters).

**Do not include**: task IDs from `.recursive/tasks/` (those are internal to the resident daemon's queue), references to handoff files, or version targets. The resident agent manages those.

## Quality Gates

All of these must pass before the PR can merge. The review daemon checks each one.

### Code quality (enforced by CI)

| Gate | Command | What it checks |
|------|---------|---------------|
| Lint | `ruff check nightshift/ Recursive/` | Rules: E, W, F, I, UP, B, SIM, RUF, BLE, S, T20, PT, C4 |
| Format | `ruff format --check nightshift/ Recursive/` | Consistent formatting |
| Types | `mypy nightshift/` | Strict mode -- full annotations, no `cast()`, no `# type: ignore` |
| Tests | `pytest nightshift/tests/ Recursive/tests/ -v` | All 847+ tests pass, Python 3.9 and 3.12 |
| ASCII | CI check | No emojis or non-ASCII in `.py`, `.sh`, `.toml` files |

**Run `make check` locally before pushing.** It runs all of the above in one command.

### Code structure (checked by review daemon)

- **Dependency flow**: `core.errors -> core.types -> core.constants -> core.shell -> core.state -> settings.config -> owl.* -> raven.* -> infra.* -> cli`. New modules slot into this chain.
- **One concern per module.** Do not add unrelated logic to existing files.
- **No hardcoded data in logic files.** Regex patterns, thresholds, score maps go in `nightshift/core/constants.py`.
- **TypedDicts in `nightshift/core/types.py`** for all data structures. No raw dicts.
- **`Any` only at JSON deserialization boundaries.** Zero `cast()`. Zero `# type: ignore`.
- **Tests for every code change.** Not "doesn't crash" tests -- real assertions with edge cases.
- **No subprocess calls outside `core/shell.py` and `infra/worktree.py`.**
- **No hardcoded absolute paths.**

### Registration checklist (for new files)

If you add a new `.py` module:
- Place it in the correct subdirectory (`core/`, `settings/`, `owl/`, `raven/`, or `infra/`)
- Add to the subdirectory's `__init__.py` re-exports
- Add to `nightshift/scripts/install.sh` PACKAGE_FILES

If you add a new config key:
- Add to `DEFAULT_CONFIG` in `nightshift/core/constants.py`
- Add to `NightshiftConfig` in `nightshift/core/types.py`
- Add to `.recursive.json` (and `.nightshift.json.example` for reference)

## What NOT to Touch

These files are managed by the resident daemon's lifecycle. External PRs that modify them will be rejected or require human override:

- `.recursive/handoffs/` -- the daemon's session memory
- `.recursive/tasks/` -- the daemon's work queue
- `.recursive/vision-tracker/` -- the daemon updates TRACKER.md after each session
- `Recursive/operators/` -- role prompts managed by the daemon
- `.recursive/sessions/` -- session logs
- `.recursive/healer/` -- system health observations

If your change requires updates to the vision tracker or task queue, note it in your PR description. The resident daemon will handle it.

## What You CAN Touch

- `nightshift/**/*.py` -- the Python package (follow the dependency flow and subdirectory structure)
- `nightshift/tests/` -- product tests (always add, never remove without justification)
- `nightshift/scripts/` -- product shell scripts (keep them thin wrappers)
- `CLAUDE.md` -- if you changed project structure (the daemon will verify)
- `.recursive/changelog/` -- add entries for your changes under the correct version
- `README.md` -- if you made user-facing changes

## How the Review Works

1. You open a PR against `main`.
2. The resident daemon's review sub-agent reads the diff via `gh pr diff`.
3. It checks structure, registration, types, tests, safety, and docs. Review agent definitions live in `Recursive/agents/` (the files in `.claude/agents/` are symlinks).
4. It reports **PASS** or **FAIL** with specific `file:line` references.
5. If PASS with advisory notes: the daemon creates follow-up tasks internally. You do not need to address advisory notes before merge.
6. If FAIL: fix the flagged issues and push again.

**Docs-only PRs** (only `.md` files changed) get a fast-path review: only docs and ops consistency are checked.

## For the Resident Daemon

When processing an external PR (a branch/PR not created by the daemon itself):

1. **Do not expect a task ID.** External contributions are not in `.recursive/tasks/`. Process the PR on its own merits.
2. **Do not expect a handoff.** The contributing agent has no access to the handoff system.
3. **Review using `Recursive/agents/code-reviewer.md` rules.** The same quality gates apply.
4. **If the PR passes review**: merge it, then create a retroactive task (`status: done`) to keep the project history complete. Update the changelog, tracker, and handoff as part of the next session.
5. **If the PR conflicts with in-progress work**: flag it for human review rather than auto-resolving. The human decides priority.
6. **Unexpected branches are not hostile.** An unfamiliar branch following the naming convention (`feat/`, `fix/`, `docs/`) is likely an external contribution. Do not delete it.
