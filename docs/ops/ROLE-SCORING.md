# Role Scoring Reference

This document describes how `scripts/pick-role.py` decides which role the daemon runs each cycle. It is reference documentation, not an active prompt. The scoring engine in `pick-role.py` implements these rules in Python.

The daemon has five roles: BUILD, REVIEW, OVERSEE, STRATEGIZE, ACHIEVE. Each cycle, the scoring engine reads system signals and picks the highest-scoring role.

<context>
Nightshift is an autonomous engineering system. The repo contains:
- `nightshift/` -- the Python package (the product)
- `scripts/` -- daemon scripts, shell utilities
- `tests/` -- the test suite
- `docs/` -- handoffs, tasks, evaluations, vision, changelog, prompts, operations

You run inside `scripts/daemon.sh` in a loop. Each cycle you get a fresh checkout of main, assess the system, pick a role, and execute. Your output is captured as stream-json to a log file.

Key paths:
- `docs/handoffs/LATEST.md` -- what happened last session
- `docs/tasks/` -- the task queue (pending/done/blocked)
- `docs/evaluations/` -- E2E evaluation reports with scores
- `docs/sessions/index.md` -- session history
- `docs/healer/log.md` -- system health observations
- `docs/strategy/` -- strategy reports
- `docs/vision-tracker/TRACKER.md` -- progress scoreboard
- `CLAUDE.md` -- project conventions
</context>

---

## PHASE 1: ASSESS

Read these files and extract the system signals. Do this EVERY session before deciding anything.

<assessment_protocol>

1. **Read `docs/handoffs/LATEST.md`** -- what happened last, what's broken, what's recommended next
2. **Read `docs/sessions/index.md`** (last 10 entries) -- session pattern, costs, failures, roles
3. **Read the latest file in `docs/evaluations/`** -- extract the total score (NN/100)
4. **Scan `docs/tasks/`** -- count pending tasks (skip archive/, GUIDE.md, README.md)
5. **Read `docs/healer/log.md`** (last entry) -- system health rating
6. **Check `docs/strategy/`** -- when was the last strategy report written?
7. **Check `docs/reviews/`** -- when was the last code review session?
8. **Check `docs/autonomy/`** -- latest autonomy score (if any reports exist)

Extract these signals:

```
SYSTEM SIGNALS
==============
eval_score:              [NN/100 from latest evaluation, or "none" if no evaluations exist]
consecutive_builds:      [how many BUILD sessions in a row from session index]
sessions_since_review:   [count sessions since last REVIEW entry in index]
sessions_since_strategy: [count sessions since last STRATEGIZE entry, or since last file in docs/strategy/]
pending_task_count:      [number of status: pending tasks]
stale_task_count:        [tasks pending 20+ sessions -- check created date vs session count]
healer_status:           [good / caution / concern from last healer entry]
tracker_movement:        [did overall % change in last 5 sessions?]
autonomy_score:          [NN/100 from latest docs/autonomy/ report, or "none"]
needs_human_issues:      [count of open GitHub issues with needs-human label]
```

**Defaults for missing data:** If any signal file is missing or unreadable, use these:
- eval_score: 80 (assume healthy until proven otherwise)
- sessions_since_review: 0
- sessions_since_strategy: 0
- consecutive_builds: 0
- All others: 0

On a cold start (empty session index, no evaluations), BUILD wins by default. The system needs features before it needs reviews or strategy.

**Grounding rule:** Use ONLY data from the files listed above. Do not estimate or guess signal values. If a file has no relevant data, use the default above.

</assessment_protocol>

---

## PHASE 2: DECIDE

Score each role based on the signals you extracted. Show your math.

<scoring_rules>

**BUILD** -- pick up a task, write code, ship a PR
```
base:                           50
eval_score >= 80:              +30  (product is healthy, build freely)
eval_score < 80:               -40  (GATE: must pick eval-related tasks only)
urgent tasks exist:            +20  (urgent work always pulls toward BUILD)
```

**REVIEW** -- pick one file, review it, fix quality issues
```
base:                           10
consecutive_builds >= 5:       +40  (code quality debt accumulating)
healer_status == "concern":    +30  (system flagged quality issues)
sessions_since_review >= 10:   +20  (overdue for review)
sessions_since_review >= 5:    +10  (review getting stale)
```

**OVERSEE** -- close tasks, reduce queue, organize for other roles
```
base:                            5
pending_task_count >= 80:      +50  (queue critically large)
pending >= 50 AND not recently
  overseen (5+ sessions ago):  +35  (queue large, needs attention)
stale_task_count >= 5:         +30  (tasks rotting)
new tasks synced from GitHub:  +25  (queue needs organizing)
last overseer said NEEDS MORE
  WORK:                        +20  (previous cleanup incomplete)
CAP: if overseer ran < 3
  sessions ago AND said CLEAN:   5  (don't re-run, queue is fine)
```

**STRATEGIZE** -- big picture review, write strategy report
```
base:                            5
sessions_since_strategy >= 15:  +60  (overdue for strategic review)
tracker_movement == false:      +30  (progress stalled, need to reassess)
```

**ACHIEVE** -- measure and improve system autonomy, eliminate human dependencies
```
base:                            5
autonomy_score < 70:           +50  (system not self-sufficient)
needs_human_issues >= 3:       +30  (humans being paged)
eval_score < 80 for 10+ sess: +20  (stuck, not self-improving)
consecutive_builds >= 10:      +15  (no self-reflection happening)
```
To compute `autonomy_score`: read the latest report in `docs/autonomy/`. If none exists, score is 0.
To compute `needs_human_issues`: run `gh issue list --label needs-human --state open` and count.

**Pick the highest score.** Ties go to BUILD (building features is the default).

**Hard constraints:**
- STRATEGIZE max once per 10 sessions (cap prevents hiding in strategy mode)
- ACHIEVE max once per 5 sessions (autonomy work is high-value but infrequent)
- Urgent tasks always force BUILD regardless of scores
- eval_score < 80 gates BUILD to eval-related tasks only, but does NOT block REVIEW/OVERSEE/STRATEGIZE/ACHIEVE
- Override: if `NIGHTSHIFT_FORCE_ROLE` env var is set, skip scoring and use that role (valid values: `build`, `review`, `oversee`, `strategize`, `achieve`)

</scoring_rules>

Output your decision:

```
ROLE DECISION
=============
System signals:
  eval_score:              NN/100
  consecutive_builds:      N
  sessions_since_review:   N
  sessions_since_strategy: N
  pending_tasks:           N
  stale_tasks:             N
  healer_status:           [status]
  autonomy_score:          NN/100
  needs_human_issues:      N

Scoring:
  BUILD:      NN  (breakdown)
  REVIEW:     NN  (breakdown)
  OVERSEE:    NN  (breakdown)
  STRATEGIZE: NN  (breakdown)
  ACHIEVE:    NN  (breakdown)

-> [ROLE] this session because [one sentence reason]
```

---

## PHASE 3: EXECUTE

Based on your decision, read ONE of these prompt files and follow it end-to-end:

| Role | Prompt file | What you do |
|------|-------------|-------------|
| BUILD | `docs/prompt/evolve.md` | Pick a task, build it, test it, PR it, merge it, update all docs |
| REVIEW | `docs/prompt/review.md` | Pick one file, review it, fix quality issues, PR, merge |
| OVERSEE | `docs/prompt/overseer.md` | Audit the task queue, fix priorities, cull duplicates, clean up |
| STRATEGIZE | `docs/prompt/strategist.md` | Review the big picture, write a strategy report |
| ACHIEVE | `docs/prompt/achieve.md` | Measure autonomy score, eliminate one human dependency |

**Read the ENTIRE prompt file and follow it step by step.** The role prompts are 100-650 lines. You MUST read the full file, not just the first 200 lines. If using shell commands to read, use `cat` not `sed -n '1,220p'`. Do NOT read the other role prompts. One role per session.

**Post-execution requirement (ALL roles):** After completing the role prompt's steps, update `docs/handoffs/LATEST.md` with what you did this session. BUILD's evolve.md already requires this. For REVIEW, OVERSEE, STRATEGIZE, and ACHIEVE: write a brief handoff noting your role, what you did, and what the next session should know. The next cycle reads LATEST.md first -- stale data causes bad decisions.

After reading the role prompt, announce which role you adopted so the session log is traceable:

```
EXECUTING ROLE: [BUILD/REVIEW/OVERSEE/STRATEGIZE/ACHIEVE]
```

---

<examples>

<example>
Scenario: eval score is 66/100, 3 consecutive builds, 45 pending tasks

ROLE DECISION
=============
System signals:
  eval_score:              66/100
  consecutive_builds:      3
  sessions_since_review:   3
  sessions_since_strategy: 8
  pending_tasks:           45
  stale_tasks:             1
  healer_status:           caution
  autonomy_score:          55/100
  needs_human_issues:      1

Scoring:
  BUILD:      10  (50 base -40 eval gate = 10, no urgent tasks)
  REVIEW:     10  (10 base, builds < 5, no healer concern, review < 5)
  OVERSEE:    10  (10 base, tasks < 50, stale < 3)
  STRATEGIZE:  5  (5 base, strategy < 15)
  ACHIEVE:    55  (5 +50 autonomy 55 < 70)

-> ACHIEVE this session because autonomy score 55 < 70 and eval is gated. Fixing the highest-impact human dependency pushes autonomy up while eval tasks are handled by future BUILD sessions.
</example>

<example>
Scenario: eval score is 85/100, 7 consecutive builds, 62 pending tasks, 4 stale

ROLE DECISION
=============
System signals:
  eval_score:              85/100
  consecutive_builds:      7
  sessions_since_review:   7
  sessions_since_strategy: 12
  pending_tasks:           62
  stale_tasks:             4
  healer_status:           good

Scoring:
  BUILD:      80  (50 +30 eval healthy)
  REVIEW:     60  (10 +40 consecutive >= 5 +10 review >= 5)
  OVERSEE:    100 (10 +50 pending >= 50 +40 stale >= 3)
  STRATEGIZE:  5  (5 base, strategy < 15)
  ACHIEVE:    55  (5 +50 autonomy 0 < 70)

-> OVERSEE this session because 62 pending tasks with 4 stale. Queue needs cleanup before more building adds noise.
</example>

<example>
Scenario: eval score 83, 6 consecutive builds, healer flagged quality concern

ROLE DECISION
=============
System signals:
  eval_score:              83/100
  consecutive_builds:      6
  sessions_since_review:   6
  sessions_since_strategy: 5
  pending_tasks:           38
  stale_tasks:             1
  healer_status:           concern
  autonomy_score:          72/100
  needs_human_issues:      0

Scoring:
  BUILD:      80  (50 +30 eval healthy)
  REVIEW:     90  (10 +40 consecutive >= 5 +30 healer concern +10 review >= 5)
  OVERSEE:    10  (10 base, tasks < 50, stale < 3)
  STRATEGIZE:  5  (5 base, strategy < 15)
  ACHIEVE:     5  (5 base, autonomy 72 >= 70)

-> REVIEW this session because 6 consecutive builds with healer flagging quality concerns. REVIEW scores 90 vs BUILD 80.
</example>

<example>
Scenario: eval score 82, 2 builds since last review, 18 sessions since strategy

ROLE DECISION
=============
System signals:
  eval_score:              82/100
  consecutive_builds:      2
  sessions_since_review:   2
  sessions_since_strategy: 18
  pending_tasks:           35
  stale_tasks:             0
  healer_status:           good
  autonomy_score:          85/100
  needs_human_issues:      0

Scoring:
  BUILD:      80  (50 +30 eval healthy)
  REVIEW:     10  (10 base)
  OVERSEE:    10  (10 base)
  STRATEGIZE: 65  (5 +60 overdue by 3 sessions)
  ACHIEVE:     5  (5 base, autonomy 85 >= 70)

-> STRATEGIZE this session because 18 sessions without strategic review. Everything else is healthy -- time for big picture analysis.
</example>

</examples>
