# Learning: Test interactive shell functions with piped input

**Date**: 2026-04-04
**Session**: 0021
**Type**: pattern

## What happened

Interactive shell functions (`read -r` prompts) can be tested non-interactively by piping input via `echo -e`. Each `\n` simulates pressing Enter. This lets you verify that the function sets global variables correctly without actually running the daemon loop.

```bash
source scripts/lib-agent.sh
echo -e "2\n1\n" | interactive_setup "builder daemon"
echo "AGENT=$AGENT MAX_SESSIONS=$MAX_SESSIONS"
# Output: AGENT=codex MAX_SESSIONS=4
```

This pattern works for any bash function that uses `read -r`. The key is that each `read` consumes one line from stdin. Order matters: first `\n` answers the first prompt, second answers the second, etc.
