# Handoffs

This is the agent's short-term memory. Instead of reading the entire repo at the start of each session, the agent reads the latest handoff to know exactly where things stand.

## How It Works

### At the end of every session

The agent writes a handoff file: `docs/handoffs/NNNN.md` (sequential number, zero-padded).

The handoff contains ONLY what the next session needs:
- What was built this session
- What's in progress (started but not finished)
- What to build next
- Any decisions made that affect future work
- Any bugs found but not fixed
- The current version and progress numbers

### At the start of every session

The agent reads ONE file: `docs/handoffs/LATEST.md` (copy to the most recent handoff). That's it. No reading the entire codebase upfront. If the agent needs deeper context on a specific module, it reads that module — but the handoff tells it WHERE to look.

### Weekly compaction

When 7 handoff files accumulate (e.g., `0001.md` through `0007.md`), the agent compacts them into a single weekly summary: `docs/handoffs/weekly/week-YYYY-WNN.md`. The 7 individual files are deleted. The compacted file keeps only what's still relevant — decisions that are still active, bugs that aren't fixed, progress that matters. Stale information is dropped.

The weekly file is ~50 lines max. One paragraph per session. Just enough to reconstruct the narrative if needed.

### File naming

```
docs/handoffs/
  README.md          — this file
  LATEST.md          — always the current handoff (copy or copy)
  0001.md            — session 1
  0002.md            — session 2
  ...
  weekly/
    week-2026-W14.md — compacted week 14
    week-2026-W15.md — compacted week 15
```

## Handoff Format

Every handoff follows this exact structure. No exceptions. Keep it tight — the whole point is to avoid wasting tokens.

```markdown
# Handoff #NNNN
**Date**: YYYY-MM-DD
**Version**: vX.X.X
**Session duration**: ~Xh

## What I Built
- [Feature/fix name]: [one line — what it does]
- Files: [list of created/modified files]
- Tests: +X new, XXX total passing

## Decisions Made
- [Decision]: [why — one line each]
- (skip this section if no decisions were made)

## Known Issues
- [Bug/gap]: [one line — what's wrong and where]
- (carry forward from previous handoff if not fixed)

## Current State
- Loop 1: XX% — [one line status]
- Loop 2: XX% — [one line status]
- Self-Maintaining: XX% — [one line status]
- Version: vX.X.X — [X of Y features done]

## Evaluate
Run evaluation against Phractal for the changes merged this session.
(Include this section after every session that merges code changes. Omit for docs-only sessions.)

## Next Session Should
Tasks: #NNNN, #NNNN (reference docs/tasks/ files by number)
Fallback: [if no pending tasks, what to do]

## Where to Look
- [module/file]: [why the next agent might need to read this]
- (only list files relevant to the next session's work — not the whole repo)
```

## Compacted Weekly Format

```markdown
# Week YYYY-WNN Summary
**Sessions**: NNNN–NNNN
**Dates**: YYYY-MM-DD to YYYY-MM-DD
**Version**: vX.X.X → vX.X.X

## Progress
- Loop 1: XX% → XX%
- Loop 2: XX% → XX%
- Overall: XX% → XX%

## What Was Built
- Session NNNN: [feature — one line]
- Session NNNN: [feature — one line]
- ...

## Decisions Still Active
- [Decision that future sessions need to respect]

## Bugs Still Open
- [Bug — one line]

## Lessons Learned
- [Pattern or gotcha discovered this week that helps future sessions]
```

## Rules for the Agent

1. **Write the handoff BEFORE your final commit.** It's part of your deliverable, not an afterthought.
2. **Be ruthless about brevity.** If the next agent doesn't need it, don't write it. The handoff is not a journal.
3. **Carry forward known issues.** If the previous handoff listed a bug and you didn't fix it, copy it to yours.
4. **Drop resolved items.** If you fixed a bug from the previous handoff, don't mention it in yours.
5. **Update LATEST.md.** After writing your handoff, copy it to `LATEST.md` so the next session finds it immediately.
6. **Compact at 7.** When you see 7 `.md` files (not counting README, LATEST, or weekly/), compact them into a weekly summary and delete the originals.
7. **The handoff replaces Step 1 of the evolve prompt.** Instead of reading the full repo, read `LATEST.md` first. Only read deeper if the handoff tells you to.
