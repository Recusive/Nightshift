# Learnings

Cross-session knowledge that helps future agents avoid mistakes and repeat successes. The evolve prompt tells agents to read this directory at startup.

Unlike handoffs (which carry forward current state), learnings persist permanently. They capture patterns, gotchas, and hard-won knowledge that would otherwise die with each session.

## How It Works

1. At the end of every session, the agent writes learnings to this directory
2. Good learnings: patterns that worked, shortcuts discovered, things that saved turns
3. Bad learnings: mistakes made, time wasted, approaches that failed
4. The next session reads all files here and avoids known traps

## File Naming

```
YYYY-MM-DD-topic.md
```

Examples:
- `2026-04-03-turn-budget.md`
- `2026-04-03-mypy-typeddict-gotcha.md`
- `2026-04-04-ci-detached-head.md`

## Format

```markdown
# Learning: [short title]
**Date**: YYYY-MM-DD
**Session**: NNNN (handoff number)
**Type**: gotcha | pattern | optimization | failure

## What happened
[1-3 sentences describing the situation]

## The lesson
[What to do or avoid in future sessions]

## Evidence
[File paths, error messages, or turn counts that prove this matters]
```

## Rules for Agents

- Write learnings BEFORE the handoff — they're part of your deliverable
- Be specific. "mypy is strict" is useless. "mypy rejects `.get()` on required TypedDict fields — use direct key access" is useful
- Delete learnings that become obsolete (e.g., if a gotcha gets fixed in code)
- Keep each file short — one learning per file, under 30 lines
