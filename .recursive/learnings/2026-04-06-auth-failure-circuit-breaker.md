---
name: Auth failure and circuit breaker separation
description: Claude 'Not logged in' exits consume circuit-breaker slots unless detected and bypassed
type: feedback
---

Auth failures (Claude CLI "Not logged in. Please run /login") must not
count against the circuit breaker's consecutive-failure counter.

**Why:** Today's session index shows 9 auth failures between 11:46-11:54 that
triggered the circuit breaker twice (3 failures each time), stopping the daemon.
The human had to restart after re-authenticating. Auth failures are not code bugs.

**How to apply:** Check `is_auth_failure "$LOG_FILE"` in the circuit breaker block
before incrementing `CONSECUTIVE_FAILURES`. If true: `notify_human`, sleep 300s,
`continue` -- never increment the counter. The daemon retries indefinitely until
the human re-authenticates; it does not die.
