---
type: pattern
date: 2026-04-05
session: 0028
---

# Daemon sub-agent outputs need explicit persistence

When adding a lightweight agent call inside the daemon loop (like the healer),
its file outputs (task files, log entries) will be wiped by `git reset --hard
origin/main` at the start of the next cycle unless you persist them.

Options considered:
- Gitignore the output dir: works for logs but task files must be committed
- Direct push to main: violates project rules
- Let builder commit them: fragile, builder might miss untracked files
- Branch+PR+merge: follows project workflow, every step fails gracefully

The branch+PR+merge approach via `persist_healer_changes()` is the right call.
Each step (`checkout -b`, `add`, `commit`, `push`, `pr create`, `pr merge`)
returns 0 on failure so the daemon never crashes. The cost is ~6 git/gh API
calls per cycle, but only when the sub-agent actually created output.
