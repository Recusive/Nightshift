# Task Queue

Numbered task files. The agent picks up the lowest-numbered `pending` task. Humans add tasks by creating the next numbered file.

See `GUIDE.md` for step-by-step instructions on creating tasks.

## How It Works

### For humans
1. Check latest number: `ls docs/tasks/[0-9]*.md | tail -1`
2. Create the next one with `status: pending`
3. Done. The agent picks it up next cycle.

### For agents
1. Scan `docs/tasks/` for `status: pending` files (Step 2 of evolve.md)
2. `urgent` priority first, then lowest number
3. Set `status: in-progress`, build it, set `status: done`
4. If no pending tasks, fall back to the priority engine

### Status values
- `pending` — waiting to be picked up
- `in-progress` — being worked on right now
- `done` — completed and merged
- `blocked` — can't proceed (note what it's blocked on)

### Priority values
- `urgent` — jumps the queue
- `normal` — standard order (lowest number first)
- `low` — only if nothing else is pending

### Rules
- One task per file
- Sequential numbers, zero-padded to 4 digits
- Never reuse a number, never delete files
- Done tasks are archived to `docs/tasks/archive/` and remain as history
