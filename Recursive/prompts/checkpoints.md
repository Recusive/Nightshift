# Process Verification Checkpoint

This checkpoint counteracts action bias by making your reasoning visible
and verifiable. It applies to ALL operators.

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
friction_entries:    N
```

Numbers must be verifiable against actual files. If the block is missing or
numbers don't match reality, the session is flagged.

NOTE: Checkpoints 2-4 (Forced Tradeoff, Pre-Commitment, Commitment Check)
apply only to the BUILD operator and are embedded in its SKILL.md.
