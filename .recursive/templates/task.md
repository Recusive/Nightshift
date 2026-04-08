# Task Template

Create tasks in `.recursive/tasks/NNNN-short-name.md`. Use `.next-id` for numbering.

```markdown
---
title: [Descriptive title]
status: pending
priority: [urgent|normal|low]
created: YYYY-MM-DD
target: [project|recursive]
environment: [internal|integration]
vision_section: [loop1|loop2|self-maintaining|meta-prompt|none]
source: [manual|pentest|evaluation|healer|generated]
---

# NNNN: [Title]

## Description
[What needs to be done and why]

## Acceptance Criteria
- [ ] [Specific, testable criterion]
- [ ] [Specific, testable criterion]

## Context
[Links to related PRs, tasks, evaluations, or learnings]
```

## Frontmatter Fields

| Field | Required | Values |
|-------|----------|--------|
| title | yes | descriptive name |
| status | yes | pending, in-progress, blocked, done, wontfix |
| priority | yes | urgent, normal, low |
| created | yes | YYYY-MM-DD |
| environment | no | internal (default), integration |
| vision_section | no | which vision section this advances |
| source | no | where this task came from |
| blocked_reason | if blocked | environment, dependency, design |
| completed | if done | YYYY-MM-DD |
| target | no | version this targets (e.g., v0.0.7) |
