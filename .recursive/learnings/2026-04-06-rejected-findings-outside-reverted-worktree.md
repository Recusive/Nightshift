# Learning: Rejected findings must be written outside the reverted worktree
**Date**: 2026-04-06
**Session**: 0064
**Type**: pattern

## What happened
`nightshift test` rejects bad cycles by resetting the isolated worktree back to
`pre_head` and cleaning untracked files. That correctly keeps the target repo
clean, but it also wipes any shift-log edits describing what the rejected cycle
found unless the session copies a readable artifact somewhere else first.

## The lesson
If a rejected cycle should stay inspectable after `revert_cycle()`, write the
evidence to the runtime directory (or another non-reverted location) before the
reset. Do not rely on the worktree shift log surviving a rejected cycle.

## Evidence
- `nightshift/cli.py` now writes `$TMPDIR/nightshift-test-runs/.../YYYY-MM-DD.md`
  before calling `revert_cycle()`
- The fresh Phractal evaluation in `docs/evaluations/0015.md` had state + runner
  logs but no durable rejected-run markdown until this fix
