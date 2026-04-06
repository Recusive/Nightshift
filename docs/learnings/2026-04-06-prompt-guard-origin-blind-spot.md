---
name: prompt-guard-origin-blind-spot
description: Working-tree-only guards are blind to pushed remote changes; fix by recording origin hash before the cycle and comparing after
type: feedback
---

When a prompt guard only diffs the local working tree against a pre-cycle
snapshot, an agent can push malicious changes to `origin/main` without touching
the working tree. The guard sees a clean working tree, reports no modification,
and then `git reset --hard origin/main` silently pulls the compromise in.

**Fix pattern**: record `git rev-parse origin/main` into the snapshot directory
before the agent runs. After the agent finishes, fetch origin and compare the
current `origin/main` hash to the saved one. If changed, diff guard files on
`origin/main` against the snapshot. If any differ, revert by restoring snapshot
files and force-pushing back to `origin/main` before the reset runs.

**Test pattern**: create a bare origin + victim clone + attacker clone using
`git init -b main --bare` (requires git 2.28+). Snapshot from victim, attacker
pushes malicious commit, run the check. The `-b main` flag is essential --
without it, the bare repo defaults to `master`, the attacker clone has no
branch to track, and the attacker push gets rejected as non-fast-forward.

**Why:** The working-tree-only guard assumes the agent can only affect state it
touches locally. Remote pushes are a separate channel the guard did not watch.
