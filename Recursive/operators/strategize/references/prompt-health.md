# Prompt Health Audit

## Data Collection

1. Read the last 10 session logs in the sessions directory
2. For each session, capture: id, duration, cost, exit status, tracker delta, skipped tasks, CI failures, prompt modifications
3. Read all current prompt/control files with line numbers
4. For each session, identify which prompt instructions were directly relevant

## Classification

Classify prompt instructions into:

- **Helping**: followed and correlated with good outcomes
- **Ignored**: relevant but repeatedly skipped or worked around
- **Harmful/confusing**: created friction, redundant work, or contradictory behavior

Only make claims you can tie to prompt file lines plus session evidence.

## Pipeline Health (if verification pipeline is active)

Review the last 10 session logs for checkpoint quality:

1. **Signal Analysis blocks**: Real numbers from real files? Or formulaic copy-paste?
2. **Tradeoff Analysis blocks**: Genuine alternatives? Or fake "alternatives" with predetermined winner?
3. **Pre-Commitments**: Specific and measurable? Or vague and un-checkable?
4. **Commitment Checks**: Verified honestly? Or rubber-stamped as "MET"?
5. **Override usage**: >20% = recalibrate scoring. 0% = agent not using reasoning.

If checkpoints produce formulaic slop, recommend either rewriting the instructions or disabling via kill switch.
