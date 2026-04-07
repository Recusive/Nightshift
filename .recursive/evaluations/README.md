# Evaluations

After every merge, the agent runs Nightshift against a real repo and scores itself. Failures become tasks.

## How It Works

1. Agent merges a PR, CI passes on main
2. Agent runs a 2-cycle test shift against Phractal (or another test target)
3. Agent reads the shift log, state file, and runner log
4. Agent scores across 10 dimensions (see scorecard below)
5. Agent writes an evaluation report here: `docs/evaluations/NNNN.md`
6. For any dimension scoring below 6/10, agent creates a task in `docs/tasks/`
   unless an existing pending task already covers that exact failure; in that
   case the report should reference the existing task instead of duplicating it
7. Next session picks up those tasks

## Rerun protocol

Always score the prescribed default command first in a fresh clone. If that run
fails to start or cannot produce a scorable result, rerun in a second fresh
clone with the minimum temporary overrides needed to collect evidence, and
document both attempts in the report.

## Known target metadata

Repo-specific evaluation defaults live in `nightshift/eval_targets.py`. Use
that metadata for stable real-repo settings instead of ad-hoc `.nightshift.json`
overrides. Current known target:

- `github.com/fazxes/Phractal` -> `python3 -m compileall apps/api/app`

## Scorecard (10 dimensions, max 100)

| # | Dimension | What it measures | Max |
|---|-----------|-----------------|-----|
| 1 | **Startup** | Did the runner start without errors? Worktree created? Baseline ran? | 10 |
| 2 | **Discovery** | Did the agent find real issues (not template placeholders)? | 10 |
| 3 | **Fix quality** | Are the fixes correct? Would a human accept them? | 10 |
| 4 | **Shift log** | Is it well-written? No template artifacts? Accurate commit hashes? | 10 |
| 5 | **State file** | Does it exist? Valid JSON? Counters make sense? | 10 |
| 6 | **Verification** | Did baseline/post-cycle verification run? Did it catch anything? | 10 |
| 7 | **Guard rails** | Were limits respected? No blocked paths touched? Category balance? | 10 |
| 8 | **Clean state** | Is the worktree clean after? No leftover artifacts? | 10 |
| 9 | **Breadth** | Did the agent explore multiple areas, not just one directory? | 10 |
| 10 | **Usefulness** | Would the day team actually read this shift log and act on it? | 10 |

## Evaluation Report Format

```markdown
# Evaluation #NNNN
**Date**: YYYY-MM-DD
**Target**: repo name
**Agent**: codex | claude
**Cycles**: N
**After task**: #NNNN (what was just merged)

## Scores

| Dimension | Score | Notes |
|-----------|-------|-------|
| Startup | X/10 | ... |
| Discovery | X/10 | ... |
| Fix quality | X/10 | ... |
| Shift log | X/10 | ... |
| State file | X/10 | ... |
| Verification | X/10 | ... |
| Guard rails | X/10 | ... |
| Clean state | X/10 | ... |
| Breadth | X/10 | ... |
| Usefulness | X/10 | ... |
| **Total** | **XX/100** | |

## Tasks Created
- #NNNN: [title] (for dimension X scoring below 6)

## Raw Evidence
- Shift log: [path or inline]
- State file: [key observations]
- Runner log: [errors or notable events]
```

## Threshold

Any dimension scoring **below 6/10** needs follow-up task coverage. Create a
new task when the failure is new; if a pending task already tracks that exact
gap, reference the existing task in the report instead of creating a duplicate.

## History

Track progress over time. Each evaluation should score higher than the last as fixes land.
