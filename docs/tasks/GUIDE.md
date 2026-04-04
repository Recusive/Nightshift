# How to Create Tasks

This is the shared task queue. Both the agent and the human create tasks here. In practice, the agent creates most tasks — after finishing one task, it creates follow-ups for what comes next. The human drops in tasks occasionally when they want something specific built.

## Check the queue

```bash
for f in docs/tasks/0*.md; do
  num=$(basename "$f" .md)
  st=$(grep "^status:" "$f" | head -1 | sed 's/status: //')
  title=$(grep "^# " "$f" | head -1 | sed 's/# //')
  printf "  %s  %-12s  %s\n" "$num" "[$st]" "$title"
done
```

## Find the next number

```bash
ls docs/tasks/[0-9]*.md | tail -1
```

Add 1, zero-pad to 4 digits.

## Create the file

`docs/tasks/NNNN.md`:

```markdown
---
status: pending
priority: normal
target: v0.0.X
created: YYYY-MM-DD
completed:
---

# Short title

What to build and why.

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
```

## Fields

**status**: `pending` | `in-progress` | `done` | `blocked`

**priority**: `urgent` (jumps queue) | `normal` (number order) | `low` (only if nothing else pending)

**target**: version from `docs/ops/OPERATIONS.md` milestones. Current in-progress if unsure.

## When the agent finishes a task

The agent does TWO things:
1. Marks the current task `done` with `completed` date
2. Creates the NEXT task(s) based on what it learned — the vision tracker, the roadmap, or what it discovered while building

This is how the queue stays alive. The agent always leaves work for the next session.

Example flow:
```
Session reads 0004 (Phractal test) -> builds it -> marks done
  -> creates 0009 (fix monorepo detection based on what it learned)
  -> creates 0010 (run second Phractal shift with fixes)
  -> handoff says "Tasks: #0006, #0009, #0010"
```

## When the human adds a task

Same process, simpler. Create the file, set `pending`. That's it. If it should jump the queue, set `priority: urgent`.

## Writing good descriptions

The agent has full repo context — it reads CLAUDE.md, vision docs, and code. You just need to say WHAT, not HOW.

**Brief is fine if vision docs have the detail:**
```
# Build backend exploration forcing

See docs/vision/01-loop1-hardening.md item #4 for full spec.
```

**More detail when it's a new idea not in the vision docs:**
```
# Add session timeout to the daemon

If a session hangs, it blocks the daemon forever. Add a --session-timeout
flag (default: 30 min) that kills hung sessions.

## Acceptance Criteria
- [ ] Flag works
- [ ] Killed sessions log "timeout" in the session index
```

## Special cases

**Task too big**: Mark done with a note, create follow-up tasks.

**Task blocked**: Set `status: blocked`, note what it's waiting on. Agent skips to next pending.

**Task unnecessary**: Set `status: done` with note "Skipped — reason."

**Task cancelled**: Set `status: done` with note "Cancelled."

**Work done without a task**: Create a retroactive task with `status: done`. Keeps history complete.

**Never delete task files.** They are the project history.
