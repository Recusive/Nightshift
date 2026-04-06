---
description: Consolidate reviews from Claude and Codex, then fix all confirmed issues
argument-hint: [cycle-number]
allowed-tools: Read, Write, Edit, Bash(bun run typecheck:*), Bash(bun run lint:*), Bash(bun test:*), Glob, Grep
---

# Consolidate and Fix

Two independent code reviews exist for cycle $1:

- `reviews/cycle-$1-claude.md`
- `reviews/cycle-$1-codex.md`

Your job:

1. Read both review files
2. Consolidate into confirmed issues
3. Fix ALL confirmed issues
4. Log what you fixed to `reviews/cycle-$1-fixes.md`

## Instructions

Think carefully before making changes.

### STEP 1: READ REVIEWS

Read both review files completely. Understand what each reviewer found.

### STEP 2: COMPARE AND CONSOLIDATE

Categorize every issue:

#### Issues BOTH Found (High Confidence - Will Fix)

| #   | Issue | Claude Severity | Codex Severity | Agreed Fix |
| --- | ----- | --------------- | -------------- | ---------- |

#### Issues Only Claude Found

For each, decide: VALID (will fix) | INVALID (not an issue) | OPTIONAL (nice to have)

| #   | Issue | Severity | Decision | Reasoning |
| --- | ----- | -------- | -------- | --------- |

#### Issues Only Codex Found

For each, decide: VALID (will fix) | INVALID (not an issue) | OPTIONAL (nice to have)

| #   | Issue | Severity | Decision | Reasoning |
| --- | ----- | -------- | -------- | --------- |

#### Disagreements

| #   | Issue | Claude Position | Codex Position | Your Resolution |
| --- | ----- | --------------- | -------------- | --------------- |

### STEP 3: CREATE FIX LIST

#### Will Fix (Confirmed)

| #   | File:Line | Issue | Fix Description |
| --- | --------- | ----- | --------------- |

#### Will Not Fix (Rejected)

| #   | Issue | Reason |
| --- | ----- | ------ |

#### Optional (Deferred)

| #   | Issue | Why Optional |
| --- | ----- | ------------ |

### STEP 4: APPLY FIXES

Fix ALL issues in the "Will Fix" list. For each:

1. Make the code change
2. Verify fix doesn't break anything
3. Run linters/type checks if available

Work systematically. Do not skip any confirmed issue.

### STEP 5: WRITE FIX LOG

Write to `reviews/cycle-$1-fixes.md`:

```markdown
# Fix Log: Cycle $1

**Date**: [current date]

## Review Comparison

### Issues Both Found

[table]

### Issues Only Claude Found

[table with decisions]

### Issues Only Codex Found

[table with decisions]

### Disagreements Resolved

[table]

## Final Fix List

### Fixed

| #   | File | Issue | What Changed |
| --- | ---- | ----- | ------------ |

### Rejected

| #   | Issue | Reason |
| --- | ----- | ------ |

### Deferred

| #   | Issue | Reason |
| --- | ----- | ------ |

## Quality Score

- Claude's Score: X/10
- Codex's Score: X/10
- Post-Fix Score: X/10

## Remaining Concerns

[Anything needing attention in next cycle]

## Verification Commands

bun run typecheck
bun run lint
bun test
```

### STEP 6: CONFIRM COMPLETION

After writing the fix log, tell me:

- How many issues fixed
- Any issues you rejected and why
- Ready to push? (yes/no)

Begin by reading both review files.
