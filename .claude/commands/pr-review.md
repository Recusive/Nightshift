---
description: Run a senior-level code review of branch changes vs main
argument-hint: <cycle-number> <model-name>
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git rev-parse:*), Bash(git rev-list:*), Bash(wc:*), Bash(date:*), Read, Write, Glob, Grep
---

# Code Review Cycle

You are conducting a senior-level code review of all changes on this branch compared to main.

**Cycle**: $1
**Model**: $2
**Output**: `reviews/cycle-$1-$2.md`

## Validation

If `$1` is empty or `$2` is empty, output:

```
Usage: /pr-review <cycle-number> <model-name>
Example: /pr-review 1 claude
```

Stop execution.

## Context

- Current branch: !`git branch --show-current`
- Commits ahead: !`git rev-list --count main..HEAD`
- Files changed: !`git diff main --name-only`

This is a **Tauri 2.9.x + React 19.2.3** application using Claude Agent SDK. The codebase uses strict TypeScript, ESLint, and follows modern React patterns.

---

## Severity Definitions

| Severity       | Meaning                                                     | Action                  |
| -------------- | ----------------------------------------------------------- | ----------------------- |
| **CRITICAL**   | Breaks functionality, security flaw, data loss              | Must fix before merge   |
| **WARNING**    | Bug in edge case, missing error handling, pattern violation | Should fix before merge |
| **SUGGESTION** | Code quality, readability, optimization                     | Optional / follow-up    |

---

## Step 0: Scope Check

```bash
git diff main --stat
git diff main --name-only | wc -l
```

**Size limits:**

- **Small** (< 300 lines changed, < 10 files): Full review
- **Medium** (300-800 lines, 10-20 files): Prioritize production code over tests/config
- **Large** (800+ lines or 20+ files): Stop. Output "PR too large for effective review. Recommend splitting by feature/concern." and list suggested split points based on file groupings.

**If no commits ahead of main**: Output "No changes to review" and stop.

**If cycle 2+**: Check if previous cycle review exists in `reviews/`. Reference it but conduct independent review.

---

## Step 1: Discovery

```bash
git diff main --name-only
git log main..HEAD --oneline
git diff main
```

Categorize files:

- **Production**: `src/` excluding `*.test.*`, `*.spec.*`
- **Tests**: `*.test.*`, `*.spec.*`, `__tests__/`
- **Config**: `*.json`, `*.toml`, `*.yaml` at root
- **Docs**: `*.md`

**Priority order**: Production > Config > Tests > Docs

If over token budget, skip lower-priority categories and note "Tests/docs not reviewed due to PR size."

---

## Step 2: Context Gathering

For each **production file** changed:

1. Read the full file (not just diff)
2. Read direct imports that are also in this repo
3. Find one similar existing pattern in codebase (if new feature)

**Stop reading when you can answer:**

- What does this code receive as input?
- What does it output or effect?
- How do errors propagate?

Don't read exhaustively. Read enough to review confidently.

---

## Step 3: Evaluate

Review against these criteria. **Skip categories that don't apply** to the changed code.

### Correctness

- Logic does what's intended
- Conditionals handle boundaries (off-by-one, null, empty)
- Async: cleanup on unmount, no stale closures, race conditions addressed
- State updates account for batching and closure capture

### Error Handling

- Errors caught at appropriate boundaries
- User-facing errors are meaningful
- Network/API failures handled
- Loading states shown during async
- Partial failures don't corrupt state

### Type Safety

- No `any` without comment explaining why
- No `@ts-ignore` without comment
- Null/undefined handled explicitly (no unwarranted non-null assertions)

### React Patterns

- Hook dependencies correct
- No conditional hook calls
- State colocated (not over-lifted)
- Effects clean up properly
- Keys stable and unique (no array index for dynamic lists)

### Tauri-Specific

- `#[tauri::command]` validates input
- New commands have capability permissions
- IPC errors propagate correctly to JS
- No shell injection in command construction

### Security

- No hardcoded secrets
- User input sanitized before use in commands/queries
- No `dangerouslySetInnerHTML` without sanitization

### Integration

- Changes match existing patterns in codebase
- Public API changes are backwards-compatible (or breaking change is documented)
- Dependent code updated if interface changed

### Code Quality

- Names are clear
- Functions do one thing
- No copy-pasted logic that should be extracted
- Complex logic has explanatory comments

---

## Step 4: Write Review

Create `reviews/cycle-$1-$2.md`:

```markdown
# Code Review: Cycle $1

**Reviewer**: $2
**Date**: !`date +%Y-%m-%d`
**Branch**: !`git branch --show-current`

## Summary

[2-3 sentences: What this branch does, key findings, merge readiness]

## Files Reviewed

| File          | Risk | Notes             |
| ------------- | ---- | ----------------- |
| `src/foo.tsx` | High | Core logic change |
| `src/bar.ts`  | Low  | Utility addition  |

_Risk: High (core logic, security, many dependents), Medium (feature code), Low (utilities, tests, docs)_

## Issues

| #   | Sev        | Location           | Problem        | Fix          |
| --- | ---------- | ------------------ | -------------- | ------------ |
| 1   | CRITICAL   | `src/foo.tsx:45`   | [What's wrong] | [How to fix] |
| 2   | WARNING    | `src/bar.ts:20-25` | [What's wrong] | [How to fix] |
| 3   | SUGGESTION | `src/baz.tsx:10`   | [What's wrong] | [How to fix] |

## Red Flags

Check only if found. Omit rows with no findings.

| Flag                 | Location    | Acceptable?                       |
| -------------------- | ----------- | --------------------------------- |
| `console.log`        | `file:line` | Yes if guarded by debug flag / No |
| `TODO` without issue | `file:line` | Note for tracking                 |
| `any` type           | `file:line` | Justified because... / Needs fix  |
| Empty catch          | `file:line` | No                                |
| Commented-out code   | `file:line` | No                                |

## Unhandled Scenarios

[List specific edge cases this code doesn't handle, if any. Be concrete:]

- What happens if `items` is empty?
- What happens if API returns 500?
- What happens if user navigates away mid-save?

## Merge Recommendation

**[READY | NEEDS CHANGES | NEEDS REWORK | TOO LARGE]**

- **READY**: No critical issues, warnings are minor or acknowledged
- **NEEDS CHANGES**: Has warnings that should be fixed
- **NEEDS REWORK**: Has critical issues or design problems
- **TOO LARGE**: PR should be split before review

**Required before merge:**

- [ ] Fix issue #1
- [ ] Address issue #2
```

---

## Output

After writing file:

1. Print: `Review written to reviews/cycle-$1-$2.md`
2. Print the **Summary** and **Merge Recommendation** sections

---

## Policies

**console.log**: Acceptable if behind a debug flag or in error handlers. Flag unguarded console.log in production paths.

**TODO/FIXME**: Acceptable in active development. Flag only if TODO describes a bug or missing critical functionality.

**Soft limits**: Don't flag function length or component size unless it causes actual problems (hard to test, multiple responsibilities, bugs).

**Accessibility**: Only flag what's verifiable from code—missing alt text, non-semantic elements (div with onClick instead of button), missing aria-label on icon buttons. Don't claim to verify keyboard navigation or screen reader behavior.

**Testing**: Note if new code lacks tests. Don't block merge for missing tests unless it's critical path code.

**Cross-cycle escalation**: If a previous cycle flagged an issue and it's unfixed, reference it: "Issue persists from cycle 1, #3."
