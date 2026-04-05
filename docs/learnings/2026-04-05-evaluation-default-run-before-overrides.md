# Default eval run before overrides

**Date**: 2026-04-05
**Type**: process
**Session**: #0045 (Default model config parity assertions)

## What happened

The two previous Phractal evaluations only became scorable after manual
workarounds (`env -u CLAUDECODE` plus temporary config overrides), so it was
tempting to assume the third rerun needed the same treatment. The prescribed
default command actually started and completed on its own, which meant the old
startup failure was no longer current evidence.

## Rule

On evaluation reruns, always execute the prescribed default command in a fresh
clone first. Only if that run fails to start or cannot be scored should you use
temporary overrides in a second fresh clone, and the report must document both
attempts.
