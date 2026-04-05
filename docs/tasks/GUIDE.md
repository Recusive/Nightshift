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

Read `docs/tasks/.next-id`. That file contains a single number — the next available task ID. Use it, then increment it and write the new value back. Always commit `.next-id` alongside the new task file.

```bash
# Read, use, increment
NEXT=$(cat docs/tasks/.next-id)
printf "%04d" "$NEXT"   # your task number, zero-padded
echo $(( NEXT + 1 )) > docs/tasks/.next-id
```

**Never scan the directory to guess the next number.** That causes collisions when the daemon and a human (or two sessions) create tasks concurrently. The `.next-id` file is the single source of truth.

## Task archival

Completed tasks (`status: done`) are automatically moved to `docs/tasks/archive/` by the daemon's housekeeping step between sessions. This keeps the active directory small — only pending, in-progress, and blocked tasks remain.

The archive is permanent history. Never delete archived tasks.

## Create the file

`docs/tasks/NNNN.md`:

```markdown
---
status: pending
priority: normal
target: v0.0.X
vision_section: loop2
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

**environment**: `internal` | `integration` (optional, defaults to `internal`)
- `internal`: pure code changes — the builder daemon can complete these autonomously
- `integration`: requires external resources (repos, network, real environments, human input) — the builder SKIPS these and the overseer decomposes them into internal subtasks

**blocked_reason**: (required when `status: blocked`)
- `environment`: requires external resources the daemon cannot provide (e.g., clone Phractal, network access)
- `dependency`: blocked by another task that must complete first
- `design`: needs architectural decision or human input before proceeding

**needs_human**: `true` (optional) — set by overseer after 3+ failed attempts. Task excluded from automatic pickup until a human intervenes.

**skipped_by**: list of session IDs that read this task and chose not to do it (appended automatically)

**target**: version from `docs/ops/OPERATIONS.md` milestones. Current in-progress if unsure.

**vision_section**: (optional) Which tracker section this task advances: `loop1` | `loop2` | `self-maintaining` | `meta-prompt` | `none`. Set this when creating tasks so future sessions can check alignment. If omitted, the task is assumed to be `none` (internal cleanup).

## Vision-alignment rule

The task queue can drift — all tasks end up targeting the same vision section while other sections stagnate. Before creating new tasks, check alignment:

1. Read the last 5 tasks created (by number, regardless of status)
2. Count how many target each `vision_section`
3. If 3 or more of the last 5 target the **same** section, your new tasks **must** prioritize a different section
4. Check `docs/vision-tracker/TRACKER.md` — sections with lower percentages need more tasks

**How to flag:** If you notice the queue is skewed (e.g., 4 of last 5 tasks are all `meta-prompt`), note it in the handoff under "Vision alignment" so the next session is aware.

**Exception:** If a section genuinely has urgent work (bugs, blockers), alignment can be overridden — but you must explain why in the task description.

## When the agent finishes a task

The agent does THREE things:
1. Marks the current task `done` with `completed` date
2. Creates the NEXT task(s) based on what it learned — the vision tracker, the roadmap, or what it discovered while building
3. Creates follow-up tasks for ANY code review advisory notes, known limitations, or suggestions that weren't fixed before merging

**Rule: review notes must become tasks.** If the code review sub-agent passes but flags issues as "advisory", "known limitation", or "not blocking", each note MUST get a follow-up task with clear acceptance criteria. The task queue is the system's memory — anything not tracked as a task will be forgotten.

This is how the queue stays alive. The agent always leaves work for the next session.

Example flow:
```
Session reads 0004 (Phractal test) -> builds it -> marks done
  -> creates 0009 (fix monorepo detection based on what it learned)
  -> creates 0010 (run second Phractal shift with fixes)
  -> handoff says "Tasks: #0006, #0009, #0010"
```

## When the human adds a task

**Preferred: use GitHub Issues.** The daemon syncs them automatically.

```bash
# Simple task
gh issue create --title "Add dark mode" --label "task"

# Urgent task
gh issue create --title "Fix CI" --label "task,urgent"

# With details and vision section
gh issue create --title "Build webhook" --label "task,integration,loop2" \
  --body "Description and acceptance criteria here"
```

**Label mapping:**

| GitHub label | Frontmatter field |
|---|---|
| `task` | (required -- triggers sync) |
| `urgent` | `priority: urgent` |
| `low` | `priority: low` |
| `integration` | `environment: integration` |
| `loop1` / `loop2` / `self-maintaining` / `meta-prompt` | `vision_section:` |

Default: `priority: normal`, no environment tag.

The daemon's housekeeping step runs `sync_github_tasks` before each session. It reads `.next-id`, creates the task file, increments `.next-id`, closes the issue with a "Converted to task #NNNN" comment, and commits the new files to main.

**Alternative: create the file directly.** Same as the agent process -- read `.next-id`, create the file, increment. Use this only if GitHub is unavailable or you need to set fields not covered by labels.

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
