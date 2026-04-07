# Shell expansion mangles markdown prompts

**Date**: 2026-04-05
**Type**: gotcha
**Session**: #0032

## What happened

The healer ran as `run_agent "$AGENT" "$(cat "$HEALER_PROMPT_FILE")" ...` in daemon.sh. The healer prompt (healer.md) contained backticks and `$` characters inside markdown code blocks. Shell `$(cat ...)` expansion interpreted these as command substitution and variable expansion, silently mangling the prompt. The healer never produced output across 4+ sessions.

## Lesson

Never pass markdown files through shell `$(cat ...)` expansion when the content contains backticks, `$`, or other shell-special characters. Either:
1. Merge the logic into an existing agent step (as we did -- healer became a builder step)
2. Use a heredoc with single-quoted delimiter `<<'EOF'` to prevent expansion
3. Pass the file path and let the agent read it, instead of injecting content via shell

## Impact

This bug went undetected for 4 sessions because the healer failure was non-fatal and the daemon continued. Silent failures in non-blocking auxiliary steps can persist indefinitely.
