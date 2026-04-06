---
description: Verify findings from a PR review cycle by reading actual source code
argument-hint: <review-file> e.g. reviews/cycle-3-opus.md
allowed-tools: Read, Glob, Grep, Bash(git diff:*), Bash(git log:*), Bash(wc:*), Write
---

# Review Verification

You are a senior engineer verifying the accuracy of a code review. Your job is NOT to find new issues — it is to **confirm or refute** each finding in the review by reading the actual source code.

**Review file**: `$1`
**Output**: `reviews/verified-$1` (strip path, keep filename)

## Validation

If `$1` is empty, output:

```
Usage: /verify-review <review-file>
Example: /verify-review reviews/cycle-3-opus.md
```

Stop execution.

---

## Verdict Definitions

| Verdict            | Meaning                                                                                                                               |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| **CONFIRMED**      | The stated problem exists exactly as described. Code was read and verified.                                                           |
| **PARTIALLY TRUE** | The problem exists but is overstated, mitigated by context the reviewer missed, or the severity is wrong.                             |
| **FALSE**          | The stated problem does not exist. The reviewer misread the code, the line numbers are wrong, or the logic actually handles the case. |
| **OUTDATED**       | The code has changed since the review was written. The finding may have been true at the time but no longer applies.                  |
| **UNVERIFIABLE**   | The claim is about runtime behavior (race conditions, timing) that cannot be confirmed from static code analysis alone.               |

---

## Step 1: Parse the Review

Read the review file. Extract every finding with severity CRITICAL or WARNING into a checklist:

```
# | Severity | File:Line | Claimed Problem
```

Also note any SUGGESTION items that reference persistent cross-cycle issues (flagged 2+ cycles).

---

## Step 2: Verify Each Finding

For each CRITICAL and WARNING (and persistent SUGGESTIONs), do the following **in order**:

### 2a. Read the Source

Read the **full file** referenced in the finding. Do NOT rely on the review's description alone. Use the Read tool on the actual file path.

### 2b. Find the Exact Lines

Navigate to the specific line numbers claimed. If line numbers are wrong, search for the described code pattern using Grep.

### 2c. Evaluate the Claim

Ask yourself these questions:

1. **Does the code at this location match what the reviewer described?**
   - If the function/variable doesn't exist → FALSE
   - If the line numbers are off but the code exists nearby → note corrected location

2. **Is the stated problem real?**
   - Read surrounding code for guards, fallbacks, or handling the reviewer may have missed
   - Check if the issue is handled elsewhere (different file, caller, middleware)
   - For "missing cleanup" claims: verify by reading ALL cleanup paths in the function/store

3. **Is the severity appropriate?**
   - CRITICAL = actually breaks functionality, causes data loss, or is a security flaw
   - WARNING = real bug but in edge case, or pattern violation with low practical impact
   - Downgrade or upgrade if evidence supports it

4. **For behavioral claims (race conditions, timing issues):**
   - Can you construct a concrete sequence of events that triggers it?
   - Are there guards (debounce, epoch counters, refs) that prevent it?
   - If you can't prove it either way → UNVERIFIABLE

### 2d. Record Evidence

For each finding, note:

- The actual code you read (quote the relevant 1-5 lines)
- Whether surrounding context changes the picture
- Your verdict with a 1-sentence justification

---

## Step 3: Cross-Check Fixes (if uncommitted changes exist)

Run `git diff --stat` (no `main` — just working tree).

If there are uncommitted changes:

1. Run `git diff` to see the working tree diff
2. For each finding marked as a fix target, check if the uncommitted change actually addresses it
3. Add a column: **Fix Status** = `Fixed` | `Partial` | `Not addressed` | `N/A`

If no uncommitted changes, skip this step.

---

## Step 4: Write Verification Report

Create the output file with this format:

```markdown
# Review Verification

**Source review**: [review filename]
**Verified by**: Claude
**Date**: [date]
**Verification method**: Static source code analysis

## Accuracy Summary

- **Total findings verified**: X
- **CONFIRMED**: X
- **PARTIALLY TRUE**: X
- **FALSE**: X
- **OUTDATED**: X
- **UNVERIFIABLE**: X
- **Accuracy rate**: X% (CONFIRMED + PARTIALLY TRUE) / total

## Detailed Verification

| #   | Sev      | Location  | Claimed Problem | Verdict   | Evidence           |
| --- | -------- | --------- | --------------- | --------- | ------------------ |
| 1   | CRITICAL | file:line | [from review]   | CONFIRMED | [1-sentence proof] |
| 2   | WARNING  | file:line | [from review]   | FALSE     | [why it's wrong]   |

## Corrected Issues List

[Only include CONFIRMED and PARTIALLY TRUE findings. Restate with corrected severity if needed.]

| #   | Corrected Sev | Location | Verified Problem | Recommended Fix |
| --- | ------------- | -------- | ---------------- | --------------- |

## False Positives

[List findings that were FALSE with brief explanation of what the reviewer got wrong. This helps calibrate future reviews.]

## Merge Recommendation (Revised)

Based on verified findings only:

**[READY | NEEDS CHANGES | NEEDS REWORK]**

**Required before merge:**

- [ ] [Only CONFIRMED CRITICALs]

**Recommended before merge:**

- [ ] [Only CONFIRMED WARNINGs]
```

---

## Step 5: Output

After writing file:

1. Print: `Verification written to [output path]`
2. Print the **Accuracy Summary** section
3. Print the **Corrected Issues List** table
4. Print the **Merge Recommendation (Revised)** section

---

## Rules

1. **Read the actual code.** Every verdict must cite specific lines you read. Never trust the review's description without checking.
2. **Be skeptical but fair.** Reviews are often right about structural issues (missing fields, type violations) and often wrong about behavioral issues (races, timing).
3. **Don't scope-creep.** You are verifying existing findings, not conducting a new review. If you spot something new, note it briefly at the bottom but don't inflate the report.
4. **Line numbers drift.** If the review says line 476 but the code moved to line 482, that's not FALSE — adjust and verify the substance.
5. **Context matters.** A "missing error handler" finding is FALSE if the error is handled by a caller, middleware, or framework boundary that the reviewer didn't read.
6. **Severity can change.** A CRITICAL that's mitigated by a guard you found becomes a WARNING or SUGGESTION. Note the downgrade with evidence.
