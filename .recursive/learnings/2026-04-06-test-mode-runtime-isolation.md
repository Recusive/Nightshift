# Learning: Test-mode runtime artifacts stay outside the target repo

**Date**: 2026-04-06
**Session**: #0062
**Type**: pattern

## What happened

The first eval-gate cleanup task was not about git cleanup at the end of the run. The real problem was where `nightshift test` wrote its runtime files: state, runner logs, synced shift logs, and the linked worktree all lived under the target checkout, so a rejected evaluation left the clone dirty by construction.

## What worked

Keep `run` mode unchanged for normal overnight work, but route `test` mode through a separate runtime-dir helper rooted in `$TMPDIR`. The linked worktree can still contain the repo-relative shift log for verification, while the target checkout itself stays clean.

## Apply this next time

When a real-repo eval bug says "cleanup," first check whether the runtime footprint belongs inside the target repo at all. If the artifacts are diagnostic-only, move them to an isolated runtime root instead of trying to scrub them after the fact.
