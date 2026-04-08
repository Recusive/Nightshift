---
name: recursive-setup
description: >
  First-run setup for the Recursive autonomous framework. Sets up a project
  to be built by Recursive — creates .recursive.json config, scaffolds all
  runtime directories, writes the vision doc from user input, and configures
  the daemon. Use this skill when the user says "setup recursive", "init
  recursive", "configure recursive", "set up the project", "first run",
  or when .recursive.json doesn't exist and the user wants to start.
---

# Recursive Setup

You are setting up a project to be built by the Recursive autonomous framework.

## What You're Doing

The user has downloaded Recursive into their repo and wants to start using it.
You need to gather information about their project and configure everything
so the daemon can start working.

## Step 1 — Gather Project Info

Ask the user these questions (use AskUserQuestion if available, otherwise ask inline):

1. **Project name** — What is this project called?
2. **Description** — One sentence: what does it do?
3. **Test command** — How do you run tests? (e.g., `make test`, `npm test`, `cargo test`)
4. **CI command** — How do you run the full CI check? (e.g., `make check`, `npm run lint && npm test`)
5. **Vision** — In a few sentences, what should this project become? What's the end goal?
6. **Agent preference** — Claude or Codex? (default: Claude)
7. **Test target** — Is there an external repo to evaluate against? (optional, can be blank)

If any of these can be inferred from the repo (package.json, Makefile, Cargo.toml, pyproject.toml), infer them and confirm with the user instead of asking.

## Step 2 — Run Init

Run the init script with the project name:

```bash
bash .recursive/scripts/init.sh --name "PROJECT_NAME"
```

This creates `.recursive.json`, `.recursive/` with 14 directories, and all starter files.

## Step 3 — Configure

Update `.recursive.json` with the user's answers:

```json
{
  "project": {
    "name": "PROJECT_NAME",
    "description": "USER_DESCRIPTION",
    "test_target": "USER_TEST_TARGET"
  },
  "commands": {
    "check": "USER_CI_COMMAND",
    "test": "USER_TEST_COMMAND"
  },
  "agents": {
    "default": "USER_AGENT_CHOICE",
    "model": "claude-sonnet-4-6",
    "effort": "high"
  }
}
```

## Step 4 — Write the Vision

Replace the placeholder in `.recursive/vision/00-overview.md` with the user's
vision. Keep the template structure but fill in their answers:

```markdown
# PROJECT_NAME — Vision

## What is PROJECT_NAME?
[User's description]

## Success Criteria
[Derived from their vision — what does "done" look like?]

## Architecture
[Read the repo and describe the current architecture]
```

If the user gave a detailed vision, also create additional vision docs
(e.g., `01-core-features.md`, `02-infrastructure.md`) to break it down.

## Step 5 — Symlink Agents

Set up `.claude/agents/` symlinks if they don't exist:

```bash
mkdir -p .claude/agents
for f in .recursive/agents/*.md; do
    ln -sf "../../.recursive/agents/$(basename $f)" ".claude/agents/$(basename $f)"
done
```

## Step 6 — Verify

Run a quick check:
1. Verify `.recursive.json` exists and has valid JSON
2. Verify all 14 `.recursive/` directories exist
3. Verify `.recursive/vision/00-overview.md` has real content (not placeholders)
4. Verify `.claude/agents/` symlinks point to `.recursive/agents/`
5. Run `python3 .recursive/engine/pick-role.py .` to verify the scoring engine works

## Step 7 — Report

Tell the user:

```
Recursive is set up for PROJECT_NAME.

Config:     .recursive.json
Vision:     .recursive/vision/00-overview.md
Runtime:    .recursive/ (14 directories)
Agents:     .claude/agents/ (symlinked)

To start the daemon:
  bash .recursive/engine/daemon.sh claude 60

To start in tmux (recommended):
  tmux new-session -d -s recursive "bash .recursive/engine/daemon.sh claude 60"
  tmux attach -t recursive

The daemon will read your vision, pick up tasks, and start building.
```

## Gotchas

- If `.recursive.json` already exists, ask the user if they want to overwrite or update it.
- If `.recursive/vision/00-overview.md` already has content, don't overwrite — ask first.
- If the repo has no test command, set `"test": ""` and note that the agent won't be able to verify its work until one is configured.
- Don't run the daemon for the user — just tell them how. They decide when to start.
