# Learning: Daemon doesn't recover from partial session work
**Date**: 2026-04-03
**Session**: 0003-daemon
**Type**: failure

## What happened
Session 3 died mid-edit while fixing code review feedback on PR #12. The PR was open with 1 commit, but the review fixes were uncommitted local changes. The daemon's next cycle does `git reset --hard origin/main` which wipes those local changes. The PR stays open and stale. The next session reads the handoff (which says "build backend forcing") and might rebuild from scratch, not knowing PR #12 already exists.

## The lesson
Before starting a new session, the daemon must check `gh pr list --state open`. If a previous session left an open PR, that context must be prepended to the prompt: "PR #N is open. Check its CI. If it passes, merge it. If it fails, fix and merge. Do NOT rebuild from scratch."

## Evidence
- PR #12 left open after session 3 failure
- Manual intervention required to finish and merge
- Fix: daemon.sh now checks for open PRs before each cycle
