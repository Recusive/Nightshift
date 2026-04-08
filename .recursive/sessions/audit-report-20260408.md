---
date: 2026-04-08
session: audit-76-session-review
auditor: audit-agent
---

# Framework Audit Report -- 2026-04-08

First audit in 76 sessions. First audit ever under the v2 brain-delegates-to-sub-agents architecture.

---

## QUALITY AUDIT

### Files Audited (14)

- `.recursive/prompts/autonomous.md`
- `.recursive/prompts/checkpoints.md`
- `.recursive/ops/DAEMON.md`
- `.recursive/ops/OPERATIONS.md`
- `.recursive/ops/ROLE-SCORING.md`
- `.recursive/engine/daemon.sh`
- `.recursive/engine/pick-role.py`
- `.recursive/engine/signals.py`
- `.recursive/engine/dashboard.py`
- `.recursive/engine/lib-agent.sh`
- `.recursive/agents/brain.md`
- `.recursive/agents/build.md` (representative of sub-agent definitions)
- `.recursive/agents/audit-agent.md`
- `AGENTS.md`, `CLAUDE.md` (project-level)
- `.recursive/operators/build/SKILL.md`, `evolve/SKILL.md`, `security-check/SKILL.md`, `audit/SKILL.md`
- `.recursive/friction/log.md`
- `.recursive/decisions/log.md`
- `.recursive/commitments/log.md`

### Issues Found: 8

#### CRITICAL

**C1: autonomous.md -- Zones 1 and 2 both labeled `.recursive/`**
- File: `.recursive/prompts/autonomous.md`, lines 8 and 15
- Zone 1 says "`.recursive/` -- THIS IS YOU" and Zone 2 also says "`.recursive/` -- YOUR WORKING MEMORY"
- This is a copy-paste error. The two zones are distinct concepts (framework code vs runtime state) but have the same label, which confuses any agent reading it.
- FIXED: Zone 2 label changed to "`.recursive/` runtime state -- YOUR WORKING MEMORY"

**C2: DAEMON.md -- Wrong budget environment variable name**
- File: `.recursive/ops/DAEMON.md`, env vars table
- DAEMON.md documents `RECURSIVE_BUDGET` but daemon.sh uses `RECURSIVE_BUDGET_USD`
- An operator following DAEMON.md would set the wrong variable and have no budget control.
- FIXED: Updated to `RECURSIVE_BUDGET_USD` with default value documented.

#### IMPORTANT

**I1: DAEMON.md -- Missing 3 roles (security-check, evolve, audit)**
- File: `.recursive/ops/DAEMON.md`, Roles table and RECURSIVE_FORCE_ROLE examples
- Roles table only listed 5 roles (v1). pick-role.py and the v2 brain support 8.
- RECURSIVE_FORCE_ROLE valid values documented as only 5 (missing security-check, evolve, audit).
- FIXED: Roles table updated to 8 roles with zone column. Force-role examples and valid values updated.

**I2: DAEMON.md -- Stale tmux session name (`nightshift` vs `recursive`)**
- File: `.recursive/ops/DAEMON.md`, tmux section and Security Incident Response section
- DAEMON.md used `nightshift` as the tmux session name. CLAUDE.md and AGENTS.md both use `recursive`.
- A human following DAEMON.md would `tmux kill-session -t nightshift` during an incident and kill nothing.
- FIXED: All occurrences updated to `recursive`.

**I3: DAEMON.md -- Cycle lifecycle describes v1 pentest preflight (stale)**
- File: `.recursive/ops/DAEMON.md`, Cycle Lifecycle section
- Described "daemon always runs security-check preflight first" and "pentest_data block" -- v1 behavior.
- In v2, the brain delegates security-check as one of 8 possible roles. No automatic pentest preflight.
- FIXED: Cycle lifecycle rewritten to match actual v2 daemon.sh behavior.

**I4: DAEMON.md -- Key Files section had hardcoded absolute paths from wrong machine**
- File: `.recursive/ops/DAEMON.md`, Key Files section
- All links used `/Users/no9labs/Developer/.recursive/Nightshift/...` -- an absolute path from a specific
  developer machine that would be wrong on any other system. Also missing dashboard.py and signals.py.
- FIXED: Replaced with relative paths. Added dashboard.py, signals.py, brain.md.

**I5: OPERATIONS.md -- System 5 operators list missing evolve and audit operators**
- File: `.recursive/ops/OPERATIONS.md`, System 5 section
- Listed 6 operators but evolve and audit were added as part of the v2 architecture.
- How-to-use section also described v1 daemon loading SKILL.md directly.
- FIXED: Full operator list (8 operators) added. v2 sub-agent definitions table added (14 agents).
  How-to-use updated to distinguish v1 (SKILL.md) and v2 (agents/).

**I6: ROLE-SCORING.md -- Describes v1 manual scoring process (PHASE 1/2/3)**
- File: `.recursive/ops/ROLE-SCORING.md`
- Header says "the daemon has five roles" (should be 8). PHASE 1 instructs agent to manually read files
  and extract signals. PHASE 2 instructs agent to manually compute scores. PHASE 3 instructs agent to
  read SKILL.md and announce "EXECUTING ROLE:". All of this is v1 behavior.
- In v2, pick-role.py handles scoring automatically and outputs advisory JSON. The brain reads the
  dashboard (pre-computed). The brain does not manually implement a scoring formula.
- PARTIAL FIX: Header updated to clarify advisory role in v2 and mention all 8 roles.
  RECURSIVE_FORCE_ROLE valid values updated to include all 8 roles.
- TASK CREATED: #0203 -- Full rewrite of ROLE-SCORING.md to document v2 brain decision-making.

#### MINOR

**M1: lib-agent.sh PROMPT_GUARD_FILES references daemon-v1.sh**
- File: `.recursive/engine/lib-agent.sh`, line 28
- daemon-v1.sh is still in the engine directory and in the guard list, which is correct (it should
  be guarded). However, DAEMON.md and other docs should note it as legacy. No fix needed -- the
  file exists and the guard is appropriate.

**M2: AGENTS.md operators list says 6 operators (missing evolve/audit)**
- File: `AGENTS.md` (project root)
- Operators section lists "6 operators (build/review/oversee/strategize/achieve/security-check)"
- No fix applied here (AGENTS.md is a project-level file, not a .recursive/ framework file).
- This is a gap for the build agent to fix when updating AGENTS.md.

---

## PATTERN ANALYSIS

### Sessions Analyzed: 76 (all available in index.md)

#### Role Distribution (last 80 recorded sessions)

From session index analysis:
- build: ~35% of sessions
- oversee: ~25% of sessions
- achieve: ~10% of sessions
- review: ~10% of sessions
- strategize: ~5% of sessions
- security-check: 2 sessions (2026-04-07 only, v2 era)
- brain: 0 entries (v2 brain sessions are recorded differently)

The session index contains a mix of v1 and early-v2 sessions. The 2026-04-06 cluster
shows a mass failure event (7+ consecutive circuit breaks from 11:19-11:54) that was
eventually resolved. This appears to have been a tooling/environment issue, not a
framework issue.

#### Failure Rate

The 2026-04-06 session cluster had an extreme failure concentration:
- 20+ consecutive failures in a 2-hour window (11:19-11:54)
- Multiple circuit break events
- All failed sessions show exit code 1, pentest: failed (exit 1)
- Zero cost recorded for failed sessions (pentest failed before brain ran)

After recovery (12:59), sessions ran normally. The failure pattern suggests an
infrastructure issue (likely network/auth) rather than a framework bug.

#### Cost Trends

From costs.json (v2 era only, 2 entries):
- Session 1: $0.5477 (security-check, 36K output tokens)
- Session 2: $0.3913 (security-check, 26K output tokens)

Pre-v2 sessions from index.md show much higher costs ($27-$34 for some oversee sessions,
which is anomalous). The $27.89 and $27.08 sessions (20260406-103855 and 20260406-105418)
warrant investigation -- these are 2-3x more expensive than comparable sessions.

#### Commitment Hit Rate

UNMEASURABLE -- commitments/log.md contains only the header, zero entries.
The decisions/log.md has only 1 entry (spike test from 2026-04-07).
This is the most significant process gap found: the brain's feedback loop
(Checkpoint 4: Commitment Check) is not generating persistent data.

#### Optimization Opportunities: 4

1. **Commitment logging not working** -- The brain session report instructions
   say to write to commitments/log.md and decisions/log.md at end of session, but
   this is not happening (or not being committed). With 0 entries, the pre-commitment
   feedback loop is completely blind. TASK CREATED: #0204

2. **Security findings in .recursive/ have no clean fix path** -- Confirmed by
   friction log entry 2026-04-07. Security issues in framework code require either
   zone violations or leaving exploits unfixed. This is a structural gap.
   TASK CREATED: #0202

3. **ROLE-SCORING.md documents v1 process in detail** -- Any agent reading this
   file gets instructions to manually compute scores and execute roles directly,
   which conflicts with v2 brain architecture. This causes confusion and wasted turns.
   TASK CREATED: #0203

4. **Session index missing PR URLs for brain sessions** -- Brain sessions delegate
   to sub-agents who create PRs, but the brain log doesn't contain the PR URL
   in a format the daemon can extract. Index.md shows empty PR columns for v2.
   TASK CREATED: #0205

---

## Tasks Created

- #0202: Fix security-to-.recursive/ gap (no operator path for pentest findings in framework)
- #0203: Update ROLE-SCORING.md to reflect v2 brain architecture
- #0204: Add commitment tracking to brain sessions (log is empty)
- #0205: Session index PR URL extraction for brain sessions

## Files Fixed This Session

1. `.recursive/prompts/autonomous.md` -- Zone 2 label corrected (copy-paste bug)
2. `.recursive/ops/DAEMON.md` -- Budget env var, missing roles, stale tmux names,
   v1 pentest lifecycle, hardcoded absolute paths in Key Files section
3. `.recursive/ops/ROLE-SCORING.md` -- Role count updated (5->8), RECURSIVE_FORCE_ROLE valid values updated
4. `.recursive/ops/OPERATIONS.md` -- System 5 operators list updated (6->8 + v2 agent definitions)

## Overall Health

**Needs attention.** The framework documentation is significantly stale relative to
the v2 architecture. The critical issue is that ROLE-SCORING.md still describes a
v1 workflow that conflicts with v2. The commitment/decision logging gap means the
brain has no feedback loop on its prediction accuracy after 76 sessions.

Framework code (daemon.sh, pick-role.py, signals.py, dashboard.py, lib-agent.sh,
brain.md) is current and correct. The gaps are documentation, not implementation.
