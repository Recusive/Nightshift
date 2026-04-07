---
name: next-id stale after multi-task OVERSEE sessions
description: OVERSEE sessions that create multiple tasks leave .next-id at the first task number, causing ID collisions for subsequent sessions
type: feedback
---

When an OVERSEE session creates N tasks in a loop (e.g., 0182, 0183, 0184, 0185),
`.next-id` may only be incremented to reflect the FIRST task created (182 -> 183)
rather than the last (185 -> 186), or may not be updated at all.

The builder session that runs next reads `.next-id = 182` and tries to create a task
with a number that already exists, causing a file clobber.

**Why:** OVERSEE does not always commit `.next-id` with each individual task file;
it may update it once at the end for the first task only, or forget entirely.

**How to apply:** At the start of any BUILD session, compare the current `.next-id`
against the highest-numbered existing task file in `docs/tasks/`. If `.next-id` is
lower than (highest_existing + 1), fix it before creating new tasks. Fix inline,
commit with the new task files.
