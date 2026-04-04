# How to Write a Task

Read this when you need to create a task file — either because the human asked you to add one, or because you're splitting a large task into follow-ups.

## Step 1: Find the next number

```bash
ls docs/tasks/[0-9]*.md | tail -1
```

Take that number, add 1, zero-pad to 4 digits. If the last file is `0007.md`, yours is `0008.md`.

## Step 2: Create the file

Path: `docs/tasks/NNNN.md`

```markdown
---
status: pending
priority: normal
target: v0.0.X
created: YYYY-MM-DD
completed:
---

# Short title (what to build, not how)

Description of what the human wants. Include enough context that an agent
reading this in a future session — with no memory of this conversation —
knows exactly what to build.

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
```

## Step 3: Set the right fields

**status** — always `pending` for new tasks.

**priority:**
| Value | When to use |
|-------|------------|
| `urgent` | Human said "do this NOW" or "before anything else." Gets picked up before all other pending tasks regardless of number. |
| `normal` | Default. Picked up in number order. |
| `low` | Nice-to-have. Only picked up when no normal/urgent tasks are pending. |

**target** — which version this belongs to. Check `docs/ops/OPERATIONS.md` version milestones to find the right one. If unsure, use the current in-progress version.

**created** — today's date.

**completed** — leave blank. The agent fills this when done.

## Step 4: Write the description

Good task descriptions answer: **what** to build and **why** it matters. The agent figures out **how** by reading the code.

**Good:**
```
# Add session timeout to the daemon

The daemon runs forever with no timeout per session. If a session hangs
(agent stuck in a loop, waiting for input that never comes), it blocks
the entire daemon. Add a --session-timeout flag (default: 30 minutes)
that kills the session if it exceeds the limit.
```

**Bad:**
```
# Fix the timeout thing

Make it work better.
```

**Acceptance criteria** are optional but strongly recommended. They tell the agent when the task is DONE — not "I think it works" but "these specific things are true."

## Step 5: Where to put it relative to other tasks

The agent picks the **lowest-numbered pending task** (unless something is `urgent`). So:

- If your task should happen NEXT: give it a number right after the last done task.
- If your task should happen AFTER existing pending tasks: give it the next number after the last file.
- If your task should jump the queue: set `priority: urgent`.

Example:
```
0001.md  status: done
0002.md  status: done
0003.md  status: done
0004.md  status: pending   ← agent picks this up next
0005.md  status: pending
0006.md  status: pending
0007.md  status: pending
```

If you want something done before 0004, you have two options:
1. Set your new task to `priority: urgent` (it jumps ahead of all normal tasks)
2. Renumber — but this is messy, so prefer option 1

## Step 6: What happens after you create it

Nothing else. The file exists, that's it. The next daemon cycle (or manual session):
1. Reads `docs/tasks/`
2. Finds your file as the lowest pending
3. Sets it to `in-progress`
4. Builds it
5. Sets it to `done`
6. Writes a handoff pointing to the next pending tasks

## Special cases

**Task is too big for one session:**
The agent marks it `done` with a note in the description ("Completed phase 1, see follow-up tasks"), then creates new task files for the remaining phases.

**Task is blocked:**
Set `status: blocked`. Add a note at the top of the description saying what it's blocked on. The agent skips blocked tasks and picks the next pending one.

**Task turns out to be unnecessary:**
Set `status: done` with a note: "Skipped — no longer needed because X." Don't delete the file.

**Human wants to cancel a task:**
Set `status: done` with a note: "Cancelled by human." Don't delete the file.
