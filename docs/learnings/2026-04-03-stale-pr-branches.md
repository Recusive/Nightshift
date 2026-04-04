---
type: gotcha
date: 2026-04-03
topic: stale PR branches can revert merged work
---

# Stale PR branches can revert merged work

When a PR branch was created before other PRs were merged to main, merging it as-is will revert the newer work. The `git diff main..branch` shows "deletions" that are actually features missing from the stale branch.

**Detection**: Run `git log --oneline main...origin/branch --left-right` to see commits unique to each side. If main has commits not on the branch, the branch is stale.

**Fix**: Rebase the branch onto main before merging: `git checkout branch && git rebase main`. Resolve conflicts keeping main's version for anything the branch didn't intentionally change.

**Prevention**: Always check `gh pr checks` and review the diff before merging. An empty `statusCheckRollup` with `mergeable: UNKNOWN` is a red flag.
