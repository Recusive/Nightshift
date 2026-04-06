---
description: Run a senior-level code review of branch changes vs main
argument-hint: [cycle-number] [model]
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Read, Write, Glob, Grep
---

# Code Review Cycle

You are conducting a senior-level code review of all changes in this PR compared to main. Your goal is to ensure the code is correct, follows best practices, and is production-ready.

- **Cycle Number**: $1
- **Model**: $2

Save your complete review to: `reviews/cycle-$1-$2.md`

## Context

- Current branch: !`git branch --show-current`
- Files changed: !`git diff main --name-only`
- Commit history: !`git log main..HEAD --oneline`

This is a Tauri 2.9.x + React 19.2.3 application using Claude Agent SDK. The codebase uses strict TypeScript, ESLint, and follows modern React patterns.

You are reviewing ONLY the changes on this branch compared to main.

If this is cycle 2, 3, or 4: Previous review files exist in reviews/. You may read them to understand what was already found and fixed, but conduct your own independent review—don't just confirm previous findings.

## Instructions

Think step by step. Follow these steps exactly:

### STEP 1: DISCOVERY

Run these commands to understand the scope:

- `git diff main --name-only` - list all changed files
- `git diff main` - see the full diff
- `git log main..HEAD --oneline` - understand commit history

Read each modified file completely. Do NOT skip this step.

### STEP 2: TRACE FULL CONTEXT

Do NOT review changes in isolation. For each changed file:

- Read the ENTIRE file, not just the diff lines
- Identify all imports, dependencies, and modules the changed code interacts with
- Read those related files to understand data flow
- Trace function calls upstream and downstream
- Check for existing patterns the new code should follow
- Verify changes integrate correctly with existing code

Ask yourself: "Do I understand the complete data flow and logic flow?" If no, keep reading.

### STEP 3: UNDERSTAND INTENT

Before critiquing, understand what the code is trying to accomplish. Trace the logic end-to-end. If unclear, note it.

### STEP 4: EVALUATE

Review against these criteria:

#### Correctness and Logic

- Does the code do what it's supposed to do?
- Conditionals correct? Off-by-one, boundary conditions, null/undefined edge cases?
- Async logic handled properly? Race conditions, cleanup, stale closures?
- Do changes break existing functionality?

#### Edge Cases and Error Handling

For EVERY function/component, ask "What could go wrong?":

- Empty states: arrays, strings, objects, zero values
- Null/undefined inputs
- Boundary conditions: first, last, single, maximum
- Invalid input: wrong types, malformed data
- Network failures: API errors, timeouts, offline
- Race conditions: events out of order, double clicks
- User interruption: navigate away, cancel, refresh
- Error propagation: caught and handled? Useful messages?
- Loading states: feedback during async?
- Partial failures: only part succeeds?

#### Integration and Consistency

- Follows patterns established elsewhere?
- Interfaces/contracts maintained or properly updated?
- Data flow consistent with similar features?
- Ripple effects missed?

#### Best Practices

- SOLID principles (especially SRP, DI)
- React: proper hooks, composition, custom hook extraction
- State: proper lifting, colocation, no prop drilling
- Over-engineered for the problem?

#### Code Quality

- Readability: clear naming, self-documenting
- DRY: duplicated logic to extract?
- Function/component size: doing too much?
- Testability: pure functions, injectable dependencies?

#### Type Safety and Security

- No unjustified `any` types
- Proper null/undefined handling
- Input validation, XSS/CSRF considerations
- No exposed secrets

#### Performance

- Unnecessary re-renders (missing useMemo/useCallback)?
- Memory leaks (missing useEffect cleanup)?
- N+1 queries or redundant operations?

### STEP 5: WRITE REVIEW TO FILE

Write the following to `reviews/cycle-$1-$2.md`:

```markdown
# Code Review: Cycle $1

**Reviewer**: $2
**Date**: [current date]
**Branch**: [branch name]

## Branch Summary

[What this branch accomplishes based on commits and code]

## Files Changed

[List from git diff main --name-only]

## Related Files Read

[Files read for context]

## Issues Found

| #   | File:Line | Severity                    | Category                                                                           | Problem              | Fix          |
| --- | --------- | --------------------------- | ---------------------------------------------------------------------------------- | -------------------- | ------------ |
| 1   | ...       | CRITICAL/WARNING/SUGGESTION | Correctness/Edge Case/Logic/Integration/Best Practice/Security/Performance/Quality | What's wrong and why | Concrete fix |

## Red Flags

[Any of: console.log, debugger, TODO/FIXME, @ts-ignore, hardcoded secrets, commented-out code, magic numbers, empty catch blocks, breaking interface changes, unhandled promise rejections, missing error boundaries, missing loading/error states]

## Quality Score

[1-10 with justification]

## Top 3 Priority Fixes

1. ...
2. ...
3. ...

## Edge Cases Missing

[Specific scenarios not handled]

## Integration Concerns

[Risks to existing functionality]

## Merge Recommendation

[READY TO MERGE | NEEDS CHANGES | NEEDS REWORK]
```

Do not print to terminal. Write directly to the file.

Begin by running git commands to understand scope, then read files, then write review to file.
