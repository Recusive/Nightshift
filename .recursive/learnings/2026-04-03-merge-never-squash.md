# Learning: Always --merge, never --squash, always --admin
**Date**: 2026-04-03
**Session**: 0002
**Type**: pattern

## What happened
Early PRs used --squash which collapsed all branch commits into one. The human wants every individual commit preserved on main — if you made 10 commits, all 10 appear in history. Also, --admin is required because the agent is the sole maintainer and branch protection would otherwise block merges.

## The lesson
Every `gh pr merge` must be: `gh pr merge --merge --delete-branch --admin`. No exceptions. This is documented in docs/ops/OPERATIONS.md and docs/prompt/evolve.md Step 8.

## Evidence
- PR #3: first squash merge, human corrected
- PR #4: first --merge merge (correct)
- All subsequent PRs use --merge --delete-branch --admin
