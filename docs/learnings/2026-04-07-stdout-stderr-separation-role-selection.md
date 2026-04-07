---
name: stdout-stderr separation for role selection
description: pick_session_role must capture stderr separately or unexpected stdout corrupts SESSION_ROLE silently
type: feedback
---

When a shell function calls a Python script that intentionally separates stdout
(structured output) from stderr (logging), do NOT use `2>&1` to capture them
together. If you do, `tail -1` on the merged stream will pick up any unexpected
stdout line (atexit, future library print, exception after sys.exit) instead of
the real structured value.

**Why:** `pick-role.py` writes the role name to stdout and reasoning to stderr by
design. With `2>&1`, an atexit handler or uncaught exception printing a line after
`print(winner)` would make `tail -1` capture the stray line. `SESSION_ROLE` would
become garbage, fall through to the `*` case, silently default to `build`, and the
daemon would run only BUILD for all future cycles -- losing OVERSEE/STRATEGIZE/ACHIEVE
scheduling -- with no error message anywhere.

**How to apply:** When calling a Python script that writes structured output to
stdout and logs to stderr, use `mktemp` to route stderr to a temp file and capture
stdout cleanly:
```bash
_stderr_buf=$(mktemp)
stdout_val=$(python3 script.py args 2>"$_stderr_buf" || true)
cat "$_stderr_buf"  # Print logs to daemon output in controlled order
rm -f "$_stderr_buf"
```
This pattern ensures the structured value is always on stdout-only, and logs appear
in a controlled order rather than interleaved with real-time stderr.
