# Process Verification Checkpoints

These checkpoints counteract RLHF biases by making your reasoning visible,
verifiable, and accountable. Each checkpoint produces a structured block in
your session output that can be audited by future sessions.

## Checkpoint 1: Signal Analysis (before deciding anything)

Read the system signals injected in the `<system_signals>` block. Output
a SIGNAL ANALYSIS block with specific, verifiable numbers. Not "eval is low"
but "eval is 53/100, down from 58."

The purpose is to prevent action bias — jumping straight to coding without
reading the data. You must demonstrate you READ the state before deciding.

```
SIGNAL ANALYSIS
===============
eval_score:          NN/100 (from signals)
consecutive_builds:  N
pending_tasks:       N (N urgent)
recent_roles:        [list from signals]
recent_security:     N of last 5 builds were security-driven
tracker_movement:    [yes/no — did overall % change recently?]
```

Numbers must be verifiable against actual files. If the block is missing or
numbers don't match reality, the session is flagged.

## Checkpoint 2: Forced Tradeoff Analysis (before starting work)

State at least 2 options with the cost of NOT doing each. This prevents
easy-task selection and rationalization — you can't just say "I'll do X
because it's important." You must say "I'm NOT doing Y, and the cost is Z."

```
TRADEOFF ANALYSIS
=================
Option A: [task/action]
  Impact: [what improves]
  Cost of skipping: [what stays broken]

Option B: [task/action]
  Impact: [what improves]
  Cost of skipping: [what stays broken]

Decision: Option [X]. [Evidence-based reason, not just "it's important"]
```

## Checkpoint 3: Pre-Commitment Metric (before building)

Declare a specific, measurable success criterion BEFORE starting work.
This prevents completion bias — declaring success regardless of quality.
The next session will check whether your metric actually moved.

```
PRE-COMMITMENT
==============
Metric: [specific measurable outcome]
Verification: [how to check it]
Fallback: [what to do if it doesn't work]
```

## Checkpoint 4: Commitment Check (in the handoff)

The handoff includes what you committed to. The NEXT session reads it and
verifies: did the metric actually move? This creates a cross-session
feedback loop — accountability across sessions.

In your handoff:
```
## Commitment Check
Pre-commitment: [what you promised]
Actual result: [to be verified by next session]
```

In the next session's Step 0:
- Read the previous handoff's Commitment Check
- If MET: note "Previous commitment: MET" in status report
- If MISSED: note "Previous commitment: MISSED — [reason]"
- If same commitment missed 3+ times: create investigation task
- If no Commitment Check exists (first session or non-BUILD): skip, note "N/A"
