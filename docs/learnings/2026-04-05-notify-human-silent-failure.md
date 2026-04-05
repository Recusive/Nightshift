# notify_human Must Fail Silently

**Date**: 2026-04-05
**Type**: pattern
**Category**: Code Patterns

## The Learning

Shell functions called from daemon loops must never cause the daemon to exit.
`notify_human` wraps every external call (`gh`, `curl`) with `|| true` so that
network failures, missing credentials, or misconfigured webhooks cannot crash the
daemon. The function exists to help, not to block -- if notification fails, the
daemon still has the log files and session index as fallback.

## Why This Matters

The daemon runs unattended for hours. A transient GitHub API failure at 3am should
not kill an otherwise healthy build loop. The notification is best-effort; the
daemon's own log and index are the authoritative record.

## Applied Where

- `scripts/lib-agent.sh`: `notify_human()` -- every line ends in `|| true`
- Future daemon helper functions should follow the same pattern
