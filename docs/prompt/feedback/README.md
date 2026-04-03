# Feedback

Drop files here after testing what the agent built. The next agent session reads everything in this folder.

## Format

Create a file named `YYYY-MM-DD.md` or `YYYY-MM-DD-topic.md`:

```markdown
# Feedback: [what you tested]

## What worked
- [bullet points]

## What didn't work
- [bullet points]

## What to do differently
- [bullet points]
```

Keep it short. The agent reads this to adjust its next session's priorities.

## Examples

```markdown
# Feedback: diff scorer test run

## What worked
- Scoring logic correctly ranked security fixes higher than cleanup

## What didn't work  
- Score of 3 threshold is too low — trivial fixes still getting through
- Scoring takes 5+ seconds per cycle on large repos

## What to do differently
- Raise default threshold to 5
- Cache file classification so it doesn't re-read the full diff
```

```markdown
# Feedback: ran nightshift on Reclip repo

## What worked
- Found a real SQL injection in the search endpoint
- Shift log was clear and actionable

## What didn't work
- Spent 4 cycles on React component cleanup before touching the API layer
- Ignored the Python backend entirely

## What to do differently
- Backend exploration forcing needs to be more aggressive
- Maybe force the first cycle to be backend-only on full-stack repos
```
