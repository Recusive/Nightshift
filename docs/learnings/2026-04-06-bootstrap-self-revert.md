---
type: learning
date: 2026-04-06
topic: prompt-guard bootstrap self-revert
---

# Prompt Guard Bootstrap Self-Revert

## What Happened

Session #0073 built security fixes and merged them via PR #140. The guard (running in the
same daemon cycle) then auto-reverted PR #140 because it saw origin/main change during the
session -- which is exactly what a PR merge causes.

Commit `b2e2fdf` ("security: revert prompt guard files pushed by agent session") was written
by `check_origin_integrity` itself. Two tests broke. All three security fixes were undone.

## Root Cause

`check_origin_integrity` cannot distinguish:
- Agent merged a PR (origin/main advances by a merge commit)
- Attacker directly pushed to origin/main (origin/main advances by a regular commit)

Both look like "origin/main changed during the session."

## Fix

Before reverting, check two conditions:
1. `git merge-base --is-ancestor snap_hash current_hash` -- forward progression (not force-push)
2. `git log --merges snap_hash..current_hash | wc -l > 0` -- at least one merge commit (PR workflow)

If both true: return 0 silently (legitimate PR merge). Do not revert.
If either false: proceed with the revert (attack pattern).

## Lessons

1. **Security guards must understand authorized workflows.** The guard was designed for the
   blind-spot attack but was unaware that the daemon itself uses `gh pr merge --merge` which
   is also a forward push to origin/main.

2. **Deferred printing prevents false alarms.** The original code printed scary alarm messages
   in the detection loop before any analysis. Restructure: collect first, check, then emit
   alarms only in the attack path.

3. **Self-modifying systems need bootstrap analysis.** Any time a system's own security
   mechanisms can be triggered against the system's own improvement mechanisms, the bootstrap
   scenario must be explicitly tested. This was not tested in PR #140.

4. **Force-push reverts create their own bootstrap risk.** The guard's revert uses force-push
   to origin/main. If the ancestor check is wrong, the guard can undo legitimate merges
   indefinitely. The ancestor+merge-commit check is a more precise gate.
