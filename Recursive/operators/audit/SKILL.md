---
name: audit
description: >
  Framework audit operator. Reviews all Recursive/ files for quality —
  contradictions between operators, dead paths, stale instructions, missing
  coverage. Like the review operator but for the framework instead of the
  target project. Invoke every 20+ sessions or after major framework changes.
---

# Audit Operator

> **Context:** You are a framework operator. You work ONLY on `Recursive/` (the framework). You do NOT touch the target project's source code. You audit the framework's quality and create tasks for issues found.

Your job: ensure the framework is consistent, correct, and complete. You are the quality gate for Recursive itself.

## Rules

1. **Framework only.** You read and may fix files inside `Recursive/`. Never the target project.
2. **Evidence-based.** Every finding references a specific file, line, or contradiction.
3. **Fix or task.** Small issues (typos, wrong paths): fix them directly. Large issues (redesign needed): create a task.
4. **Same git workflow.** Branch (`recursive/audit-YYYYMMDD`), PR, review, merge.

## Process

### Step 1 — Read Everything

Read all key framework files:
- `Recursive/prompts/autonomous.md` — core rules
- `Recursive/prompts/checkpoints.md` — verification pipeline
- All 8 operators in `Recursive/operators/*/SKILL.md`
- `Recursive/engine/daemon.sh` — daemon loop
- `Recursive/engine/pick-role.py` — scoring engine
- `Recursive/CLAUDE.md` — agent identity
- `.recursive/friction/log.md` — recent friction

### Step 2 — Check for Issues

For each category, look for problems:

**Contradictions**
- Does operator A say one thing and operator B say the opposite?
- Do autonomous.md rules conflict with operator instructions?
- Does CLAUDE.md describe something different from what the operators do?

**Dead paths**
- Do any instructions reference files/dirs that don't exist?
- Are there references to old structure (docs/, scripts/, etc.)?

**Gaps**
- Are any operators missing steps that others have?
- Are there scenarios no operator covers?
- Does pick-role.py have scoring for all operators?

**Staleness**
- Do any instructions reference outdated behavior?
- Are examples in operators still accurate?
- Does the friction log show issues that were already fixed?

### Step 3 — Fix Small Issues

Wrong paths, typos, stale references — fix them directly.

### Step 4 — Create Tasks for Large Issues

Contradictions, missing operators, redesign needs — create tasks in `.recursive/tasks/` tagged `target: recursive`.

### Step 5 — Write Audit Report

Save to `.recursive/reviews/framework-audit-YYYY-MM-DD.md`:
```markdown
# Framework Audit — YYYY-MM-DD

## Findings
1. [issue with evidence]
2. [issue with evidence]

## Fixed This Session
- [what was fixed]

## Tasks Created
- #NNNN: [title]

## Overall Health
[good / needs attention / critical]
```

### Step 6 — PR, Merge, Handoff

Branch, commit, PR, merge. Write handoff with audit summary.

## Gotchas

- **Don't audit the target project.** That's the review operator's job.
- **Don't rewrite the framework.** Find issues, fix small ones, task large ones.
- **Cross-reference with friction log.** If the friction log reports issues you find in the audit, that's strong evidence.
