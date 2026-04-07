---
date: 2026-04-06
type: optimization
tags: [security, shell, python3-c]
---

# Comprehensive python3 -c audit: fix all or fix none

## What happened

A pentest found `cleanup_old_logs` used `'$log_dir'` in a `python3 -c "..."` string.
`cleanup_healer_log` had already been fixed to use heredoc+sys.argv. The same unsafe
pattern existed in four other functions: `cleanup_orphan_branches`, `run_evaluation`,
`should_evaluate`, and `notify_human`. Each was caught separately across multiple sessions.

## The pattern

When a fix addresses "X function is unsafe", grep for the same call pattern in the
whole file before closing the task. `grep -n "python3 -c" scripts/lib-agent.sh` takes
2 seconds and reveals all callers. Fixing them all in one pass prevents the pentest
from finding the same class of issue 4 more times.

## How to apply

Before closing any "fix insecure X pattern in function Y" task:
1. `grep -n "<pattern>" <file>` to find all instances
2. Check each: safe (env var / sys.argv / stdin) or unsafe (string interpolation)?
3. Fix all unsafe ones in the same PR
4. The "comprehensive audit" framing in the commit message signals closure to future
   pentest scans
