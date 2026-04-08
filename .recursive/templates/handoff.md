# Handoff Template

Create `.recursive/handoffs/NNNN.md` after each session. Copy to `.recursive/handoffs/LATEST.md`.

```markdown
# Handoff NNNN — [Feature/Role Name]

## What I Did
- [bullet points of work completed]

## Decisions Made
- [design decisions with rationale]

## Known Issues
- [ ] [carry forward unresolved issues from previous handoff]
- [ ] [new issues discovered this session]

## Tracker Delta
XX% -> XX%

## Learnings Applied
- "[one-line summary from INDEX.md]" (.recursive/learnings/YYYY-MM-DD-topic.md)
  Affects my approach: [how this learning changed what I did]

## Generated Tasks
- #NNNN: [title]
- or "none"

## Tasks I Did NOT Pick and Why
- #NNNN: [reason — blocked-environment, blocked-dependency, justification]

## Evaluate
Run evaluation against [target repo] for the changes merged this session.

## Commitment Check
Pre-commitment: [metric from this session]
Actual result: [to be verified by next session]

## Next Session Should (ADVISORY)
- [recommendation for next highest-impact work]
```
