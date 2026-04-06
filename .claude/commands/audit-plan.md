---
description: Audit a refactor plan for correctness, architecture, performance, and production readiness
argument-hint: <path-to-plan-doc>
allowed-tools: Read, Glob, Grep, Write, Bash(git diff:*), Bash(git log:*), Bash(git branch:*)
---

# Architectural Audit

You are performing a comprehensive code review and architectural audit of a proposed refactor plan.

**Plan document**: $1

## Validation

If `$1` is empty, output:

```
Usage: /audit-plan <path-to-plan-doc>
Example: /audit-plan docs/ICON-THEME-SYSTEM.md
```

Stop execution.

## Context

- Current branch: !`git branch --show-current`
- This is a **Tauri 2 + React 19** production application with strict TypeScript, Zustand + Immer state management, and a Rust backend.

---

## Step 0: Understand the Plan

Read the plan document at `$1` completely. Extract:

1. **What system is being refactored** (e.g., icon themes, state management, routing)
2. **Goal of the refactor** (e.g., extensibility, performance, simplification)
3. **Current implementation files** mentioned or implied
4. **Proposed new files/patterns**
5. **Reference patterns** in the codebase (similar existing systems)

If the plan document doesn't exist, output "Plan document not found at `$1`" and stop.

---

## Step 1: Read Current Implementations

Read every file the plan proposes to change or replace. Also read:

- Direct imports and dependencies of those files
- At least one similar existing pattern for comparison (e.g., if adding a provider, read an existing provider)

**Stop reading when you can answer:**

- What does the current code do?
- What are its inputs, outputs, and side effects?
- What patterns does it follow?

---

## Step 2: Audit Against Criteria

Evaluate the plan against ALL of the following. **Skip sections that don't apply**, but be explicit about what you skipped and why.

### 2.1 Correctness & Proven Patterns

- Does the proposed abstraction correctly handle the core responsibility?
- Is the chosen state management pattern (Context, Zustand, hooks, etc.) consistent with the codebase?
- Are there any algorithmic complexity regressions (e.g., O(1) to O(n))?
- Any risk of breaking existing build/bundler patterns (Vite glob, tree-shaking, code splitting)?

### 2.2 Architecture & Design

- Is the proposed API surface the right abstraction level? Too broad? Too narrow?
- Should this logic live in a provider, a hook, a utility, or a service?
- Is centralizing logic better than keeping it co-located with components?
- How does this integrate with existing related systems?
- Does the abstraction boundary make sense for testing?

### 2.3 Performance

- Compare current vs proposed loading/rendering strategy
- Does the refactor change Vite's tree-shaking or code-splitting behavior?
- Will the new pattern cause unnecessary re-renders?
- Where should memoization happen (provider level, hook level, component level)?
- Any bundle size impact?

### 2.4 Framework & Tooling Best Practices

- Is the proposed pattern consistent with codebase conventions?
- Should we add memoization (React.memo, useMemo, useCallback) to prevent re-renders?
- Is the current loading strategy (eager/lazy) still the right choice post-refactor?
- Does it follow the project's ESLint, TypeScript, and import conventions?

### 2.5 Production Readiness

- Error handling: What happens when expected resources are missing?
- Fallback chain: Is the degradation path robust?
- Edge cases: Identify at least 3-5 concrete edge cases the plan doesn't address
- Type safety: Are all types strict (no `any`, no `@ts-ignore`)?
- What happens if required providers/contexts aren't mounted?
- What happens under concurrent access or race conditions?

### 2.6 Future Extensibility

- Does the architecture support likely future capabilities?
- Can we add external format/standard compatibility without major refactoring?
- Is there a clean path to add user-facing configuration?
- Should we define formal interfaces/schemas now for forward compatibility?

### 2.7 Missing Considerations

- Does the plan address all variants/modes (dark mode, responsive, etc.)?
- How do custom/external configurations handle mode variants?
- Should there be validation for external inputs (format checks, required fields)?
- Is the persistence strategy (localStorage, backend settings, config file) appropriate?

### 2.8 Test Coverage

- Are there existing tests that verify no regressions?
- Should we add unit tests for the new resolution/loading logic?
- Should we add visual regression tests for affected UI?
- How do we verify that all existing functionality still works at scale?

---

## Step 3: Write Audit Report

Write the audit to `reviews/audit-plan.md`:

```markdown
# Plan Audit: [Plan Title]

**Date**: [current date]
**Plan Document**: $1
**Branch**: [branch name]

## Plan Summary

[2-3 sentences: What the refactor does, what it replaces, and the stated goal]

## Files Reviewed

| File           | Role                   | Risk |
| -------------- | ---------------------- | ---- |
| `path/to/file` | Current implementation | High |
| `path/to/file` | Reference pattern      | Low  |

_Risk: High (core logic, many dependents), Medium (feature code), Low (utilities, tests)_

## Verdict: [APPROVE / APPROVE WITH CHANGES / NEEDS REWORK]

[1-2 sentence justification]

## Critical Issues (Must Fix Before Implementation)

| #   | Section | Problem        | Recommendation |
| --- | ------- | -------------- | -------------- |
| 1   | 2.1     | [What's wrong] | [How to fix]   |

## Recommended Improvements (Should Consider)

| #   | Section | Problem                | Recommendation |
| --- | ------- | ---------------------- | -------------- |
| 1   | 2.3     | [What could be better] | [Suggestion]   |

## Nice-to-Haves (Optional Enhancements)

| #   | Section | Idea          | Benefit        |
| --- | ------- | ------------- | -------------- |
| 1   | 2.6     | [Enhancement] | [Why it helps] |

## Edge Cases Not Addressed

[Concrete scenarios the plan doesn't handle]

- What happens if X?
- What happens when Y?

## Code Suggestions

[Specific code examples for critical issues and recommended improvements]

## Verdict Details

### Correctness: [PASS / CONCERNS]

[Details]

### Architecture: [PASS / CONCERNS]

[Details]

### Performance: [PASS / CONCERNS]

[Details]

### Production Readiness: [PASS / CONCERNS]

[Details]

### Extensibility: [PASS / CONCERNS]

[Details]
```

---

## Step 4: Output

After writing file:

1. Print: `Audit written to reviews/audit-plan.md`
2. Print the **Verdict**, **Critical Issues**, and **Edge Cases** sections

---

## Policies

- **Be thorough.** This is production code. A missed issue can affect the entire UI or data flow.
- **Don't rubber-stamp.** If the plan is good, say so with evidence. If it has problems, say so directly.
- **Be concrete.** Every issue should reference specific files, lines, or code patterns. Vague concerns like "might have performance issues" are not helpful without specifics.
- **Respect existing patterns.** If the codebase already has a convention, the plan should follow it unless there's a compelling reason not to.
- **Code suggestions required.** For every critical issue, provide a concrete code example showing the fix.

Begin by reading the plan document.
