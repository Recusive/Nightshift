---
name: audit-refactor-plan
description: Audit proposed refactor plans for production readiness in the Nightshift Python CLI and daemon codebase. Use when asked to evaluate a plan document for correctness, architecture, performance, tooling fit, extensibility, edge cases, and test coverage before implementation.
---

# Audit Refactor Plan

Perform a comprehensive code review and architectural audit of a proposed refactor plan for Nightshift.

## Input and validation

Require a plan document path.

If the path is missing, output exactly:

```text
Usage: /audit-plan <path-to-plan-doc>
Example: /audit-plan docs/strategy/2026-04-06.md
```

Stop execution.

If the path does not exist, output exactly:

```text
Plan document not found at `<path-to-plan-doc>`
```

Stop execution.

## Context

Collect context first:

- Current branch: `git branch --show-current`
- Repository root: `git rev-parse --show-toplevel`
- System assumptions: production Nightshift Python 3.9+ autonomous engineering system with strict mypy, ruff, pytest, thin shell wrappers, and daemon/worktree orchestration.

Before auditing implementation details, read the repo instructions that Nightshift requires:

1. `docs/handoffs/LATEST.md`
2. `docs/ops/OPERATIONS.md` on first session, or when the handoff tells you to
3. `docs/architecture/MODULE_MAP.md` when the plan touches `nightshift/*.py`
4. `docs/learnings/INDEX.md`, then only the specific learnings relevant to the refactor
5. `AGENTS.md`, `CLAUDE.md`, `README.md`, `pyproject.toml`, and `Makefile` when needed to confirm conventions

Capture these constraints before forming an opinion:

- Python 3.9+ with mypy strict
- Ruff rules from `pyproject.toml`
- ASCII-only source for `.py`, `.sh`, `.toml`
- No hardcoded absolute paths
- TypedDict-based data contracts in `nightshift/types.py`
- No `cast()` and no `# type: ignore`
- One concern per module
- Config and thresholds live in constants/config, not inline logic
- Changes to `nightshift/*.py` often require refreshing `docs/architecture/MODULE_MAP.md`
- Final verification uses `make check`

## Step 0: Understand the plan

Read the plan document fully. Extract:

1. What system is being refactored
2. Goal of the refactor
3. Current implementation files mentioned or implied
4. Proposed new files and patterns
5. Reference patterns in the codebase
6. Which Nightshift invariants the plan must preserve

## Step 1: Read current implementations

Read every file the plan proposes to change or replace. Also read:

- Direct imports and dependencies of those files
- At least one similar existing pattern for comparison
- `docs/architecture/MODULE_MAP.md` when auditing `nightshift/*.py`
- Relevant operations or learning docs if the refactor touches daemon flow, worktrees, evaluation, CLI entrypoints, or task/docs automation

Stop reading only when you can answer:

- What current code does
- Inputs, outputs, and side effects
- Existing code patterns being followed
- Which operational constraints the current system depends on

## Step 2: Audit against criteria

Evaluate every applicable section. Skip only sections that do not apply, and explicitly state what was skipped and why.

### 2.1 Correctness and proven patterns

- Verify the proposed abstraction handles the core responsibility.
- Verify module placement matches Nightshift conventions:
  - one concern per module
  - no business logic in `cli.py`
  - no score maps, regexes, thresholds, or other hardcoded data inside logic modules
  - config belongs in `DEFAULT_CONFIG` and typed config structures
  - new modules fit the dependency flow and do not introduce circular imports
- Identify algorithmic complexity regressions.
- Identify risks to subprocess execution, worktree management, daemon orchestration, or generated-doc maintenance.

### 2.2 Architecture and design

- Evaluate API surface scope (too broad vs too narrow).
- Decide whether logic belongs in a module, config object, constant table, shell wrapper, CLI entrypoint, or docs generator.
- Evaluate centralization vs module co-location.
- Verify integration with related systems:
  - CLI entrypoints in `nightshift/cli.py`
  - daemon roles and scripts in `scripts/`
  - planner, build, evaluation, and integration flows
  - `.nightshift.json` config behavior
  - generated docs such as `docs/architecture/MODULE_MAP.md`
- Verify boundaries support testing and operational workflows.

### 2.3 Performance

- Compare current vs proposed execution strategy.
- Identify startup-cost regressions from heavier import graphs or extra repo scans.
- Identify repeated subprocess, git, filesystem, or evaluation work the refactor could multiply.
- Evaluate daemon-cycle latency impact.
- Recommend caching, lazy imports, or precomputed summaries only where they fit Nightshift's module boundaries.

### 2.4 Framework and tooling best practices

- Verify consistency with Nightshift's codebase conventions.
- Verify mypy strict compatibility.
- Verify ruff compatibility, including the per-file ignore boundaries already declared in `pyproject.toml`.
- Verify ASCII-only source rules for `.py`, `.sh`, `.toml`.
- Verify no `cast()`, no `# type: ignore`, and no hardcoded absolute paths.
- Verify new modules follow the "one concern per module" rule and keep constants out of logic files.

### 2.5 Production readiness

- Evaluate error handling when repositories, worktrees, sessions, or config files are missing.
- Evaluate fallback behavior when verification, agent execution, or cleanup fails.
- Identify at least 3-5 concrete edge cases not addressed.
- Verify strict typing safety and TypedDict compatibility.
- Evaluate behavior when required env/config/runtime prerequisites are absent.
- Evaluate race conditions and operational hazards:
  - daemon and human operating in the same repo
  - stale runtime artifacts
  - interrupted cleanup
  - repeated session state reuse
  - subprocess or shell injection boundaries

### 2.6 Future extensibility

- Evaluate support for likely future capabilities.
- Evaluate path for adding new daemon roles, new agent backends, or new evaluation targets.
- Evaluate whether formal interfaces or schemas should be defined now.
- Evaluate whether the plan preserves task/docs automation, generated module maps, and multi-agent extensibility.

### 2.7 Missing considerations

- Verify plan coverage across Nightshift modes:
  - dry-run vs real run
  - daemon vs one-shot commands
  - codex vs claude agents
  - single-repo vs multi-repo flows
  - local repo vs eval target repo behavior
- Evaluate handling of `.nightshift.json` and environment-variable overrides.
- Evaluate validation requirements for external inputs.
- Evaluate persistence strategy for runtime artifacts, generated docs, and repo-local state.

### 2.8 Test coverage

- Identify existing tests that protect regressions.
- Recommend targeted tests where useful, but require `make check` as the final verification gate.
- Mention `make test` or narrower commands only as supporting evidence, not the final sign-off.
- When `nightshift/*.py` changes are implied, note whether `python3 -m nightshift module-map --write` also needs verification.
- Define how to verify end-to-end behavior for daemon, CLI, or evaluation flows affected by the refactor.

## Step 3: Write audit report

Write the report to `reviews/audit-plan.md` using this structure:

```markdown
# Plan Audit: [Plan Title]

**Date**: [current date]
**Plan Document**: [path-to-plan-doc]
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

[Concrete scenarios the plan does not handle]

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

## Step 4: Final output contract

After writing the report:

1. Print `Audit written to reviews/audit-plan.md`
2. Print the `Verdict`, `Critical Issues`, and `Edge Cases` sections

## Policies

- Be thorough; this is production code.
- Do not rubber-stamp; justify approval with evidence.
- Be concrete; reference files, lines, and code patterns.
- Respect existing conventions unless there is a strong reason to deviate.
- Provide concrete code suggestions for every critical issue.
- Prefer repo evidence over generic best-practice advice.
