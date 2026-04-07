# Agent Definition Template

Every agent in `.recursive/agents/` follows this structure.

## Required Frontmatter

```yaml
---
name: agent-name
description: When the brain should delegate to this agent. Be specific.
tools: [comma-separated list of tools this agent needs]
model: sonnet
isolation: worktree        # omit for read-only agents
permissionMode: bypassPermissions
color: blue                # visual identifier in UI
---
```

## Required Body Sections

### Identity
One paragraph: who you are, what zone you work in, what you never do.

### Rules
Numbered constraints. Zone boundaries, verification requirements, output format.

### Process
Numbered steps the agent follows when invoked. The brain provides task context.

### Verification
What the agent checks before reporting done. Always includes `make check`.

### Output Format
Exact format the brain expects. Usually: `Built: [feature]\nPR: [url]` or `PASS/FAIL`.

### Gotchas
Known failure modes and how to avoid them.
