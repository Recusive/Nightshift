# exec self-restart loses shell state

**Category**: Security
**Date**: 2026-04-06

## What happened

`daemon.sh` uses `exec bash daemon.sh $AGENT $PAUSE $MAX_SESSIONS` to restart when it detects a code change on `origin/main`. Positional args survived, but three critical shell variables did not:

- `BUDGET` (set by `interactive_setup`, never exported)
- `CYCLE` (initialized to 0 at script top)
- `CONSECUTIVE_FAILURES` (initialized to 0 at script top)

After restart, all three defaulted to 0 -- disabling budget protection, session limits, and the circuit breaker.

## Fix

Export all three as env vars before `exec`, read them back at startup with `${_DAEMON_CYCLE:-0}` defaults.

## Lesson

`exec` replaces the process but starts a new script execution. Only env vars and explicit positional args survive. Any `local` or unset shell var is lost. When a script self-restarts via `exec`, audit every safety-critical variable to ensure it's either passed as an arg or exported.
