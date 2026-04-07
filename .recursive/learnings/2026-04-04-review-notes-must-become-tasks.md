# Learning: Code review advisory notes must become follow-up tasks

**Date**: 2026-04-04
**Session**: Human-monitored daemon run (sessions 1-3)
**Type**: process failure

## What happened

The code review sub-agent on PRs #30 and #31 flagged advisory notes (context flooding vector, new file creation not detected, symlink attack on instruction files). The building agent said "known limitations, not blocking" and merged without creating follow-up tasks. The human monitor caught this and had to create the tasks manually.

## The lesson

Code review notes that say "not blocking" or "advisory" still represent real gaps. If the review flags something, one of two things must happen:

1. Fix it before merging (if it's small enough)
2. Create a follow-up task with the exact issue and acceptance criteria

"Known limitation" is not a valid disposition. The whole point of the task queue is to track work that can't be done right now. Dismissing a review note without a task means it disappears from the system's memory.

## Evidence

- PR #30 review: flagged context flooding and symlink vectors, no tasks created
- PR #31 review: flagged snapshot bypass and new file creation, no tasks created
- Human created tasks #0036 and #0037 retroactively
