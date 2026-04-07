# Learning: Daemon scripts must hot-reload to maintain autonomy

**Date**: 2026-04-05
**Session**: Human-monitored daemon run
**Type**: failure

## What happened

The daemon loaded daemon.sh and lib-agent.sh once at startup. When the builder agent added new features (sync_github_tasks, healer, archive_done_tasks) during a session, they were merged to main but the running daemon process still had the old code. Required manual daemon restart every time a shell script changed — breaking autonomy.

## The fix

1. Re-source lib-agent.sh at the start of every loop iteration (after git reset pulls new code). New functions are available immediately.
2. Self-restart via exec when daemon.sh itself changes. Compares md5 hash before/after git reset. If different, exec replaces the process with the new version.

## Evidence

- sync_github_tasks built in PR #60, never ran until daemon restarted
- Healer fix in PR #54 required manual restart
- Three separate manual restarts needed in one monitoring session
