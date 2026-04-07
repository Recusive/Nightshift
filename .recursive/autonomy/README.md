# Autonomy Reports

Per-session reports from the ACHIEVE role measuring and improving system self-sufficiency.

Each report contains an autonomy score (0-100), identified human dependencies, root cause analysis, and what was fixed.

## Score Framework

| Category | Points | What it measures |
|----------|--------|-----------------|
| Self-Healing | 25 | Can the system recover from crashes, failures, and tampering without humans? |
| Self-Directing | 25 | Can the system decide what to work on, when to release, and when to clean up? |
| Self-Validating | 25 | Can the system prove its own correctness against real repos? |
| Self-Improving | 25 | Can the system learn from sessions and get better over time? |

## Files

| Pattern | Content |
|---------|---------|
| `YYYY-MM-DD.md` | Autonomy report with score, findings, and fixes |
