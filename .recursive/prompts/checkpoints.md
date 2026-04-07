# Process Verification Checkpoints

These checkpoints counteract RLHF biases by making your reasoning visible,
verifiable, and accountable. Every operator follows all 4 checkpoints.

## Checkpoint 1: Signal Analysis (before deciding anything)

Read the system signals injected in the `<system_signals>` block. Output
a SIGNAL ANALYSIS block with specific, verifiable numbers. Not "eval is low"
but "eval is 53/100, down from 58."

```
SIGNAL ANALYSIS
===============
eval_score:          NN/100 (from signals)
consecutive_builds:  N
pending_tasks:       N (N urgent)
recent_roles:        [list from signals]
recent_security:     N of last 5 builds were security-driven
tracker_movement:    [yes/no — did overall % change recently?]
friction_entries:    N
```

## Checkpoint 2: Forced Tradeoff Analysis (before starting work)

State at least 2 options with the cost of NOT doing each. Every operator
makes a choice — which file to review, which tasks to close, which
recommendation to prioritize. Show your reasoning.

```
TRADEOFF ANALYSIS
=================
Option A: [task/action]
  Impact: [what improves]
  Cost of skipping: [what stays broken]

Option B: [task/action]
  Impact: [what improves]
  Cost of skipping: [what stays broken]

Decision: Option [X]. [Evidence-based reason]
```

## Checkpoint 3: Pre-Commitment Metric (before starting work)

Declare a specific, measurable success criterion BEFORE starting work.
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
verifies: did the metric actually move?

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
- If no Commitment Check exists: skip, note "N/A"
