---
date: 2026-04-06
session: pentest-security-fixes
type: security
---

# Shell Injection: Use Env Vars to Pass Agent-Controlled Text into Python -c

## The Pattern

When a shell script calls `python3 -c "..."` and needs to pass agent-controlled
text (anything extracted from agent output: feature names, task titles, log lines)
into the Python code, **never interpolate the value directly into the quoted
string**. Pass it via an environment variable instead.

**Unsafe:**
```bash
result=$(python3 -c "
...
after_task='$after_task',   # single-quote injection here
")
```

An agent can output `Built: foo'; os.system("id"); x='` and the shell expands
this into valid Python that runs an arbitrary command.

**Safe:**
```bash
result=(_AFTER_TASK="$after_task" python3 -c "
import os
...
after_task=os.environ.get('_AFTER_TASK', ''),
")
```

The env var is opaque to the shell's string-quoting rules. The Python code
reads it as a plain string — no injection possible regardless of content.

## When to Apply

Any `python3 -c "..."` invocation in a shell script where a variable comes from:
- Agent session output (e.g., `Built:` line text)
- User-supplied input
- External data sources (PR titles, file contents, GitHub API responses)

Daemon-internal values (REPO_DIR, agent name "codex"/"claude", fixed session IDs)
are lower risk because they cannot be influenced by the agent being orchestrated.

## Self-Similar Pattern

The same principle applies to SQL, subprocess args, and any interpolation into
an interpreted context: always treat agent output as untrusted data. Env vars,
temporary files, or stdin pipes are all safe channels. String interpolation is not.
