# Learning: gitignored directories survive git clean -fd

**Date**: 2026-04-04
**Session**: 0022
**Type**: pattern

The daemon does `git reset --hard origin/main && git clean -fd` at the start of each cycle. This wipes untracked files BUT respects `.gitignore`. Since `docs/sessions/` is in `.gitignore`, files there (like `costs.json` and session logs) survive across cycles.

This means `docs/sessions/` is the right place for runtime state that should persist across cycles but not be committed. The `costs.json` ledger accumulates correctly without any special handling.

If you need a file to survive daemon resets, put it in a gitignored directory. If you need it to persist across `git clean -fdx` (which removes ignored files too), store it outside the repo.
