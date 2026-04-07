# Learning: CI PR checkouts use detached HEAD — git tests fail
**Date**: 2026-04-03
**Session**: 0002
**Type**: gotcha

## What happened
`TestDiscoverBaseBranch::test_returns_string` passed locally but failed in CI on every PR. `discover_base_branch()` calls `git symbolic-ref refs/remotes/origin/HEAD` (fails in shallow clone) then falls back to `git branch --show-current` (returns empty on detached HEAD). GitHub Actions checks out PR merge commits in detached HEAD state.

## The lesson
Any test that calls git commands on the real repo must handle CI's detached HEAD. Either skip the assertion when `os.environ.get("CI")` is set, or mock the git call.

## Evidence
- PR #3 CI failure: `AssertionError: assert 0 > 0`
- Fix: skip `len(result) > 0` assertion when CI env var is set
- Same test passes on main (push events checkout the branch, not detached)
