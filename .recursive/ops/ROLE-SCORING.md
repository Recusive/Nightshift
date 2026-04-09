# Role Scoring Reference

> **v2 Architecture Note**: This document describes the advisory scoring algorithm implemented
> in `.recursive/engine/pick-role.py`. It is reference documentation for understanding how the
> advisory recommendation is computed -- NOT a manual process for the brain agent.
>
> In v2, `pick-role.py` runs automatically and outputs a scored advisory ranking. The brain agent
> (Opus) reads this advisory as one input among several, then applies its own 4-checkpoint analysis
> (Signal Analysis, Forced Tradeoff, Pre-Commitment, Commitment Check) to decide what to delegate.
> The brain MAY override the advisory. See `.recursive/agents/brain.md` for the brain's decision
> process.

---

## How the Advisory Works (v2 Flow)

1. `daemon.sh` calls `pick-role.py --advise` at the start of each cycle
2. `pick-role.py` reads all system signals from `.recursive/` state files (via `signals.py`)
3. It computes a score for each of the 8 roles and returns a JSON advisory block:
   - `recommended`: the highest-scoring role
   - `score`: the winning score
   - `reason`: human-readable signal summary for the winner
   - `alternatives`: the next 3 roles with scores and reasons
   - `drift_warning`: set if 80%+ of recent sessions were BUILD
   - `signals`: all numeric/boolean signal values (safe for prompt injection)
   - `recent_roles`: the last 5 role names from the session index
4. The daemon injects this advisory into the brain's prompt as context
5. The brain reads the advisory alongside the dashboard, handoff, and task queue
6. The brain decides what to delegate (may follow or override the advisory)

**Force override**: If `RECURSIVE_FORCE_ROLE` env var is set to a valid role name, `pick-role.py`
skips scoring entirely and emits that role as the advisory recommendation. Valid values:
`build`, `review`, `oversee`, `strategize`, `achieve`, `security-check`, `evolve`, `audit`

---

## System Signals

`signals.py` reads these values from `.recursive/` state files. Each signal has a safe default
used when the source file is missing or unreadable.

| Signal | Source | Default |
|--------|--------|---------|
| `eval_score` | Latest file in `.recursive/evaluations/` | 80 |
| `autonomy_score` | Latest file in `.recursive/autonomy/` | 0 |
| `consecutive_builds` | Session index -- count consecutive BUILD rows from end | 0 |
| `sessions_since_build` | Session index -- sessions since last BUILD row | 0 |
| `sessions_since_review` | Session index -- sessions since last REVIEW row | 0 |
| `sessions_since_strategy` | Session index -- sessions since last STRATEGIZE row | 0 |
| `sessions_since_achieve` | Session index -- sessions since last ACHIEVE row | 0 |
| `sessions_since_oversee` | Session index -- sessions since last OVERSEE row | 0 |
| `sessions_since_security` | Session index -- sessions since last SECURITY-CHECK row | 0 |
| `sessions_since_evolve` | Session index -- sessions since last EVOLVE row | 0 |
| `sessions_since_audit` | Session index -- sessions since last AUDIT row | 0 |
| `pending_tasks` | `.recursive/tasks/` -- count files with `status: pending` | 0 |
| `stale_tasks` | `.recursive/tasks/` -- pending tasks older than 20 days | 0 |
| `urgent_tasks` | `.recursive/tasks/` -- any task with `priority: urgent` | false |
| `healer_status` | `.recursive/healer/log.md` -- last `**System health:**` value | good |
| `needs_human_issues` | GitHub -- `gh issue list --label needs-human --state open` | 0 |
| `tracker_moved` | Session index -- any `%` in recent status cells | false |
| `recent_security_sessions` | Session index + archived pentest tasks (dual-signal) | 0 |
| `friction_entries` | `.recursive/friction/log.md` -- count `## YYYY-MM-DD` headers | 0 |
| `pentest_framework_tasks` | `.recursive/tasks/` -- pending tasks with `source: pentest` AND `target: recursive` | 0 |
| `sessions_since_eval` | `.recursive/evaluations/` vs session index -- sessions since latest eval file was written (dashboard-only, not used in scoring) | 0 |

**Eval file validation**: `read_latest_eval_score()` validates the file before reading the score.
A file must have a `**Date**:` line and at least 3 scored dimension rows (`N/10` format) outside
fenced code blocks. This prevents fabricated eval files from influencing role selection.

**Autonomy file validation**: `read_latest_autonomy_score()` similarly requires `**Date**:` outside
code blocks and at least one `TOTAL: N/100` line. It returns the LAST match, so reports with both
a baseline and updated score return the updated value.

---

## Scoring Rules

`compute_scores()` in `pick-role.py` computes an integer score for each role. Higher is better.
Ties are broken by priority order: build > oversee > review > security-check > evolve > achieve > strategize > audit.

### BUILD -- build features, ship PRs

```
base:                                   50
eval_score >= 80:                      +30   (healthy product, build freely)
eval_score < 80:                       -20   (eval gated -- demoted but not locked out)
urgent_tasks == true:                  +20   (urgent work always pulls toward BUILD)
sessions_since_build >= 5:            +25   (escape hatch: nothing built recently)
sessions_since_build >= 10:           +15   (critical: stacks on top of the +25)
recent_security_sessions >= 3
  AND urgent_tasks:                    -15   (anti-loop: in security cycle, don't auto-dominate)
```

### REVIEW -- review code quality, fix issues

```
base:                                   10
consecutive_builds >= 5:              +40   (code quality debt accumulating)
healer_status in (concern, caution)
  AND sessions_since_review >= 2:     +30   (healer flagged, not just reviewed)
healer_status in (concern, caution)
  AND sessions_since_review < 2:      +10   (reviewed recently, healer may not have updated)
sessions_since_review >= 10:          +20   (overdue for review)
sessions_since_review >= 5:           +10   (review getting stale)
```

### OVERSEE -- audit task queue, reduce noise

```
base:                                    5
pending_tasks >= 80:                  +60   (critical queue size)
pending_tasks >= 50
  AND sessions_since_oversee >= 3:    +45   (large queue, not recently overseen)
pending_tasks >= 50
  AND sessions_since_oversee >= 1:    +20   (large queue, recently overseen)
pending_tasks >= 30
  AND sessions_since_oversee >= 5:    +25   (medium queue, overdue)
stale_tasks >= 5:                     +25   (tasks rotting)
sessions_since_oversee == 0:           =5   (hard cap: just ran last cycle)
```

### STRATEGIZE -- big picture review, write strategy report

```
base:                                    5
sessions_since_strategy >= 15:        +60   (overdue for strategic review)
tracker_moved == false:               +30   (progress stalled, need reassessment)

Hard cap: capped at 5 if sessions_since_strategy < 10 (prevents hiding in strategy mode)
```

### ACHIEVE -- measure autonomy, eliminate human dependencies

```
base:                                    5
autonomy_score < 70:                  +50   (system not self-sufficient)
autonomy_score < 90:                  +20   (elif, mutually exclusive: room for improvement above 70)
needs_human_issues >= 3:              +30   (humans being paged)
sessions_since_achieve >= 15:         +25   (hasn't run in a long time)
consecutive_builds >= 10:             +15   (no self-reflection happening)

Hard cap: score = -1 (ineligible) if sessions_since_achieve < 5
```

### SECURITY-CHECK -- red team, adversarial audit

```
base:                                    5
sessions_since_security >= 10:        +50   (overdue for security review)
sessions_since_security >= 5:         +20   (getting stale)
consecutive_builds >= 5
  AND sessions_since_security >= 3:   +15   (lots of builds without security review)

Hard cap: capped at 5 if sessions_since_security < 3 (don't re-run too frequently)
```

### EVOLVE -- fix friction patterns in the framework

```
base:                                    5
friction_entries >= 5:                +50   (lots of friction accumulated)
friction_entries >= 3
  AND sessions_since_evolve >= 5:     +30   (moderate friction, hasn't evolved recently)
sessions_since_evolve >= 20:          +20   (overdue regardless of friction count)
pentest_framework_tasks >= 1:         +40   (confirmed security vuln in .recursive/ -- security urgency)

Hard cap: capped at 5 if sessions_since_evolve < 5 AND pentest_framework_tasks == 0
           (don't re-run too frequently unless pentest tasks pending)
Hard cap: capped at 5 if friction_entries == 0 AND pentest_framework_tasks == 0
           (no friction and no pentest tasks = nothing to evolve)
```

### AUDIT -- framework quality review

```
base:                                    5
sessions_since_audit >= 25:           +50   (overdue for framework audit)
sessions_since_audit >= 15:           +20   (getting stale)

Hard cap: capped at 5 if sessions_since_audit < 10 (don't re-run too frequently)
```

---

## Winner Selection

```python
def pick_role(scores, urgent, recent_security=0):
    # Urgent tasks force BUILD unless in a security cycle
    if urgent and recent_security < 3:
        return "build"
    # Highest score wins; ties broken by priority order:
    priority = ["build", "oversee", "review", "security-check",
                "evolve", "achieve", "strategize", "audit"]
    best_score = max(scores.values())
    for role in priority:
        if scores[role] == best_score:
            return role
    return "build"  # fallback
```

---

## v2 Brain Decision Examples

These examples show how the brain uses the advisory. The brain's analysis is in `<analysis>` tags.

### Example 1: Eval gated, autonomy low

Advisory input from pick-role.py:
```json
{
  "recommended": "achieve",
  "score": 55,
  "reason": "autonomy=55, needs_human=1",
  "signals": {
    "eval_score": 66, "autonomy_score": 55, "consecutive_builds": 3,
    "sessions_since_review": 3, "sessions_since_strategy": 8,
    "pending_tasks": 45, "stale_tasks": 1, "healer_status": "caution",
    "needs_human_issues": 1, "sessions_since_achieve": 12
  }
}
```

Score breakdown:
```
BUILD:      30  (50 -20 eval gate)
REVIEW:     10  (10 base)
OVERSEE:     5  (5 base, tasks < 50; so defaults to 0 so hard cap applies)
STRATEGIZE:  5  (5 base, strategy < 10)
ACHIEVE:    55  (5 +50 autonomy < 70)
SECURITY:    5  (5 base)
EVOLVE:      5  (5 base)
AUDIT:       5  (5 base)
```

Brain analysis:
```
Checkpoint 1 -- Signal Analysis: Eval at 66/100 is below the 80 gate. Advisory recommends
ACHIEVE (score 55) because autonomy score is 55. BUILD is demoted to 30 but still eligible.

Checkpoint 2 -- Forced Tradeoff: ACHIEVE vs BUILD. ACHIEVE would improve autonomy, but the
real blocker is the eval score. Task #0177 (re-run evaluation) is the highest-impact unblock.
BUILD is the right call despite the advisory -- the eval gate lifts when BUILD completes #0177.

Decision: override advisory. Delegate build agent with task #0177.
```

### Example 2: Large queue with stale tasks

Advisory input from pick-role.py:
```json
{
  "recommended": "oversee",
  "score": 90,
  "reason": "pending=85, stale=6",
  "signals": {
    "eval_score": 85, "consecutive_builds": 7, "sessions_since_review": 7,
    "sessions_since_strategy": 12, "pending_tasks": 85, "stale_tasks": 6,
    "healer_status": "good", "sessions_since_oversee": 4, "tracker_moved": true
  }
}
```

Score breakdown:
```
BUILD:      80  (50 +30 eval healthy)
REVIEW:     60  (10 +40 consecutive >= 5 +10 review >= 5)
OVERSEE:    90  (5 +60 pending >= 80 +25 stale >= 5)
STRATEGIZE:  5  (5 base, strategy < 10)
ACHIEVE:    -1  (ineligible: sessions_since_achieve defaults to 0, hard cap applies)
SECURITY:    5  (5 base)
EVOLVE:      5  (5 base)
AUDIT:       5  (5 base)
```

Brain analysis:
```
Checkpoint 1 -- Signal Analysis: Advisory recommends OVERSEE (score 90). 85 pending tasks with
6 stale. Eval is healthy at 85. OVERSEE beats BUILD (90 > 80).

Checkpoint 2 -- Forced Tradeoff: OVERSEE vs BUILD. Queue cleanup unblocks future sessions.
No urgent tasks. Advisory is correct.

Decision: follow advisory. Delegate oversee agent.
```

### Example 3: Healer flagged quality concern

Advisory input from pick-role.py:
```json
{
  "recommended": "review",
  "score": 90,
  "reason": "consec_builds=6, healer=concern",
  "signals": {
    "eval_score": 83, "consecutive_builds": 6, "sessions_since_review": 6,
    "sessions_since_strategy": 5, "pending_tasks": 38, "stale_tasks": 1,
    "healer_status": "concern", "autonomy_score": 72, "needs_human_issues": 0,
    "sessions_since_achieve": 10
  }
}
```

Score breakdown:
```
BUILD:      80  (50 +30 eval healthy)
REVIEW:     90  (10 +40 consecutive >= 5 +30 healer concern + sr >= 2 +10 sr >= 5)
OVERSEE:     5  (5 base, tasks < 30)
STRATEGIZE:  5  (5 base, strategy < 10)
ACHIEVE:    25  (5 +20 elif auto < 90 since 72 >= 70; builds=6 < 10 so no +15)
SECURITY:    5  (5 base)
EVOLVE:      5  (5 base)
AUDIT:       5  (5 base)
```

Brain analysis:
```
Checkpoint 1 -- Signal Analysis: Advisory recommends REVIEW (score 90). 6 consecutive builds,
healer flagged concern. REVIEW beats BUILD (90 > 80).

Checkpoint 2 -- No override needed. Healer concern + 6 builds is a clear signal.

Decision: follow advisory. Delegate review agent.
```

### Example 4: Friction log has actionable entries

Advisory input from pick-role.py:
```json
{
  "recommended": "evolve",
  "score": 85,
  "reason": "friction=5, since_evolve=8",
  "signals": {
    "eval_score": 82, "consecutive_builds": 2, "sessions_since_review": 2,
    "sessions_since_strategy": 18, "pending_tasks": 35, "stale_tasks": 0,
    "healer_status": "good", "friction_entries": 5, "sessions_since_evolve": 8,
    "tracker_moved": true
  }
}
```

Score breakdown:
```
BUILD:      80  (50 +30 eval healthy)
REVIEW:     10  (10 base)
OVERSEE:     5  (5 base, tasks < 30)
STRATEGIZE: 65  (5 +60 strategy >= 15; tracker_moved=true so no +30)
ACHIEVE:    -1  (ineligible: sessions_since_achieve defaults to 0, hard cap applies)
SECURITY:    5  (5 base)
EVOLVE:      85  (5 +50 friction >= 5 +30 friction >= 3 AND se >= 5)
AUDIT:       5  (5 base)
```

Brain analysis:
```
Checkpoint 1 -- Signal Analysis: Advisory recommends EVOLVE (score 85). Friction log has
5 entries. Last evolve was 8 sessions ago. EVOLVE beats BUILD (85 > 80).
Sessions since strategy is 18 -- strategize also scores 65 (+60 since >= 15).

Checkpoint 2 -- EVOLVE vs STRATEGIZE vs BUILD. Eval is healthy. Evolve scores 85, build 80,
strategize 65. Friction entries are actionable framework improvements.

Decision: follow advisory. Delegate evolve agent to fix the 3+ occurrence pattern.
```

---

## Reference: All 8 Roles

| Role | When advisory triggers | Default priority | Sub-agent | Zone |
|------|------------------------|-----------------|-----------|------|
| build | Always (base 50); boosted by healthy eval + urgent tasks | 1st (tie-break) | `build` | project |
| oversee | pending >= 50 OR stale >= 5 | 2nd (tie-break) | `oversee` | project |
| review | consecutive_builds >= 5 OR healer concern | 3rd (tie-break) | `review` | project |
| security-check | sessions_since_security >= 5 | 4th (tie-break) | `security` | project |
| evolve | friction_entries >= 3 AND sessions_since_evolve >= 5 | 5th (tie-break) | `evolve` | framework |
| achieve | autonomy_score < 70 OR needs_human >= 3 | 6th (tie-break) | `achieve` | project |
| strategize | sessions_since_strategy >= 15 | 7th (tie-break) | `strategize` | project |
| audit | sessions_since_audit >= 15 | 8th (tie-break) | `audit-agent` | framework |

---

## Source of Truth

- Scoring algorithm: `.recursive/engine/pick-role.py` -- `compute_scores()` and `pick_role()`
- Signal readers: `.recursive/engine/signals.py`
- Dashboard aggregator: `.recursive/engine/dashboard.py`
- Brain decision process: `.recursive/agents/brain.md` (4-checkpoint analysis)
- Tests: `.recursive/tests/test_pick_role.py`
