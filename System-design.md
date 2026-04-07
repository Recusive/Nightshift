# System Design

## Operators

### Target Operators (work on the project, never touch Recursive/)

| Operator | What it does |
|----------|-------------|
| **BUILD** | Picks a task from the queue, writes code, writes tests, ships a PR, merges, updates changelog/tracker/handoff. The workhorse. |
| **REVIEW** | Picks one source file, reads every function, fixes quality issues (types, error handling, dead code, naming), ships a PR. |
| **OVERSEE** | Reads every pending task, closes duplicates, wontfixes stale ones, reorders priorities, decomposes stuck tasks. No code. |
| **STRATEGIZE** | Reads last 10+ sessions of history, cost data, prompt health, writes a strategy report with recommendations, creates follow-up tasks. No code. |
| **ACHIEVE** | Measures a 20-check autonomy scorecard (0-100), finds the #1 human dependency, eliminates it with code, ships a PR. |
| **SECURITY-CHECK** | Red-teams the system read-only, finds break paths, classifies as CONFIRMED or THEORETICAL, produces a report. No code changes. |

### Framework Operators (work on Recursive/, never touch the project)

| Operator | What it does |
|----------|-------------|
| **EVOLVE** | Reads `.recursive/friction/log.md`, finds patterns (same issue 3+ times), fixes the root cause in Recursive/. Only triggered when friction accumulates. |
| **AUDIT** | Reviews all Recursive/ files for quality — contradictions, dead paths, stale instructions, gaps. Like REVIEW but for the framework. Every 25+ sessions. |

### Friction Loop (how target operators feed framework operators)

```
Target operators (build/review/oversee/strategize/achieve/security-check)
    │
    │  During each session, if the framework causes friction:
    │  confusing instruction, wrong path, missing signal, etc.
    │
    │  append to .recursive/friction/log.md
    │
    ▼
.recursive/friction/log.md
    │
    │  When 3+ entries accumulate with the same pattern:
    │
    ▼
Framework operators (evolve/audit)
    │
    │  Read friction log → find patterns → fix Recursive/ → clear fixed entries
    │
    ▼
Better framework → less friction next cycle
```

---

## Daemon Flow

```
╔══════════════════════════════════════════════════════════════════╗
║                     RECURSIVE DAEMON                            ║
║              bash Recursive/engine/daemon.sh claude 60          ║
╚══════════════════════════════════════════════╦═══════════════════╝
                                               │
                                               ▼
                                    ┌─────────────────┐
                                    │   ACQUIRE LOCK   │
                                    │ .recursive-daemon│
                                    │     .lock        │
                                    └────────┬────────┘
                                             │
                 ╔═══════════════════════════╗│╔══════════════════╗
                 ║     CYCLE LOOP           ║│║  STOP CONDITIONS ║
                 ║  repeats until stopped   ║│║  - max sessions  ║
                 ╚═══════════════════════════╝│║  - budget limit  ║
                                              │║  - 3 failures    ║
┌─────────────────────────────────────────────┘║  - Ctrl+C        ║
│                                              ╚══════════════════╝
▼
┌──────────────────────────────────┐
│ 1. RESET TO ORIGIN/MAIN         │
│    git fetch origin              │
│    git checkout main             │
│    git reset --hard origin/main  │
│    git clean -fd                 │
└───────────────┬──────────────────┘
                │
                ▼
┌──────────────────────────────────┐
│ 2. HOT RELOAD                    │
│    source lib-agent.sh           │
│    if daemon.sh changed on main: │
│       exec into new version      │
└───────────────┬──────────────────┘
                │
                ▼
┌──────────────────────────────────┐
│ 3. HOUSEKEEPING                  │
│    ├─ rotate old session logs    │
│    ├─ trim healer log            │
│    ├─ prune orphan branches      │
│    ├─ compact old handoffs       │
│    ├─ archive done tasks         │
│    └─ sync GitHub Issues → tasks │
└───────────────┬──────────────────┘
                │
                ▼
┌──────────────────────────────────┐
│ 4. CHECK FOR OPEN PRs            │
│    gh pr list --state open       │
│    if found: inject PR context   │
│    into the prompt               │
└───────────────┬──────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────┐
│ 5. PICK ROLE (pick-role.py)                          │
│                                                      │
│    Reads signals from .recursive/:                   │
│    ┌────────────────────────────────────────┐        │
│    │ eval_score          53/100             │        │
│    │ autonomy_score      85/100             │        │
│    │ consecutive_builds  4                  │        │
│    │ sessions_since_*    review:2 strat:10  │        │
│    │ pending_tasks       69                 │        │
│    │ healer_status       good               │        │
│    │ urgent_tasks        false              │        │
│    └────────────────────────────────────────┘        │
│                                                      │
│    Scores 6 operators:                               │
│    ┌──────────────────┬───────┬─────────────────┐    │
│    │ build            │ 50+   │ default          │    │
│    │ review           │ 10+   │ after 5+ builds  │    │
│    │ oversee          │  5+   │ 50+ pending      │    │
│    │ strategize       │  5+   │ every 15 sess    │    │
│    │ achieve          │  5+   │ autonomy < 70    │    │
│    │ security-check   │  5+   │ every 10 sess    │    │
│    └──────────────────┴───────┴─────────────────┘    │
│                                                      │
│    Highest score wins. Ties → BUILD.                 │
│    Also writes signals JSON (--with-signals)         │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│ 6. ASSEMBLE PROMPT                                   │
│                                                      │
│    ┌──────────────────────────────────────────┐      │
│    │ <project_context>                        │ ◄── from .recursive.json
│    │   project_name: Nightshift               │      │
│    │   framework_dir: Recursive/              │      │
│    │   runtime_dir: .recursive/               │      │
│    │ </project_context>                       │      │
│    ├──────────────────────────────────────────┤      │
│    │ autonomous.md                            │ ◄── identity + rules
│    │   IDENTITY (3 zones)                     │      │
│    │   SECURITY / VERIFICATION / CI rules     │      │
│    │   ROLE OVERRIDE mechanism                │      │
│    ├──────────────────────────────────────────┤      │
│    │ <system_signals>                         │ ◄── JSON from pick-role
│    │   { eval: 53, pending: 69, ... }         │      │
│    │ </system_signals>                        │      │
│    ├──────────────────────────────────────────┤      │
│    │ checkpoints.md                           │ ◄── 4 verification checkpoints
│    │   1. Signal Analysis                     │      │
│    │   2. Forced Tradeoff                     │      │
│    │   3. Pre-Commitment                      │      │
│    │   4. Commitment Check                    │      │
│    ├──────────────────────────────────────────┤      │
│    │ operators/{role}/SKILL.md                │ ◄── the winning operator
│    │   (frontmatter stripped)                 │      │
│    └──────────────────────────────────────────┘      │
│                                                      │
│    + open PR data (if any)                           │
│    + prompt alert (if integrity violation detected)  │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│ 7. PROMPT GUARD: SNAPSHOT                            │
│    save checksums of all guarded files               │
│    (Recursive/operators, engine, prompts, agents,    │
│     CLAUDE.md, AGENTS.md, CI workflows)              │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│ 8. RUN AGENT                                         │
│                                                      │
│    claude -p "$PROMPT" --max-turns 500               │
│           --output-format stream-json                │
│           --model claude-opus-4-6                    │
│           --effort max                               │
│                                                      │
│    Output captured to .recursive/sessions/*.log      │
│                                                      │
│    ┌──────────────────────────────────────────┐      │
│    │         AGENT SESSION                    │      │
│    │                                          │      │
│    │  The agent:                              │      │
│    │  ├─ reads .recursive/handoffs/LATEST.md  │      │
│    │  ├─ outputs SIGNAL ANALYSIS (ckpt 1)     │      │
│    │  ├─ outputs TRADEOFF ANALYSIS (ckpt 2)   │      │
│    │  ├─ outputs PRE-COMMITMENT (ckpt 3)      │      │
│    │  ├─ executes the operator's process      │      │
│    │  ├─ branches, commits, PRs, merges       │      │
│    │  ├─ writes handoff to .recursive/        │      │
│    │  └─ may ROLE OVERRIDE if signals warrant │      │
│    └──────────────────────────────────────────┘      │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│ 9. PROMPT GUARD: VERIFY                              │
│    compare post-session checksums to snapshots        │
│    if modified: flag [PROMPT MODIFIED] in index       │
│    check origin/main for unauthorized direct pushes   │
│    if origin tampered: revert + alert                 │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│ 10. EXTRACT RESULTS                                  │
│    ├─ feature name (from session log)                │
│    ├─ PR URL (from session log)                      │
│    ├─ role override (from session log)               │
│    └─ exit code                                      │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│ 11. SELF-EVALUATION (every Nth session)              │
│    if session_count % eval_frequency == 0:           │
│       clone test target → run tool → score → report  │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│ 12. RECORD SESSION                                   │
│                                                      │
│    Append to .recursive/sessions/index.md:           │
│    ┌──────────────────────────────────────────────┐  │
│    │ Timestamp│Session│Role│Exit│Dur│Cost│Status  │  │
│    │          │       │    │    │   │    │Feature  │  │
│    │          │       │    │    │   │    │PR│Ovrrd │  │
│    └──────────────────────────────────────────────┘  │
│                                                      │
│    Record costs to .recursive/sessions/costs.json    │
│    Commit + push index and costs to main             │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│ 13. BUDGET + CIRCUIT BREAKER CHECK                   │
│    if cumulative cost >= budget: STOP                 │
│    if 3+ consecutive failures: STOP                  │
│    if max_sessions reached: STOP                     │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
                ┌───────────────┐
                │   COOLDOWN    │
                │  sleep ${PAUSE}s  │
                └───────┬───────┘
                        │
                        │ loop back to step 1
                        ▼
                   ┌─────────┐
                   │ CYCLE 2 │
                   │   ...   │
                   └─────────┘


══════════════════════════════════════════════════════
 THE 6 OPERATORS (what the agent does in step 8)
══════════════════════════════════════════════════════

┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   BUILD     │  │   REVIEW    │  │   OVERSEE   │
│             │  │             │  │             │
│ pick task   │  │ pick file   │  │ triage ALL  │
│ build it    │  │ deep read   │  │ close dupes │
│ test it     │  │ fix issues  │  │ wontfix old │
│ PR + merge  │  │ PR + merge  │  │ reorder     │
│ update docs │  │ write log   │  │ PR + merge  │
│ handoff     │  │ handoff     │  │ handoff     │
└─────────────┘  └─────────────┘  └─────────────┘

┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│ STRATEGIZE  │  │   ACHIEVE   │  │SECURITY-CHECK│
│             │  │             │  │              │
│ gather data │  │ score 0-100 │  │ read-only    │
│ diagnose    │  │ find #1 dep │  │ red team     │
│ recommend   │  │ fix it      │  │ find breaks  │
│ create tasks│  │ test it     │  │ classify:    │
│ write report│  │ PR + merge  │  │  CONFIRMED   │
│ handoff     │  │ handoff     │  │  THEORETICAL │
└─────────────┘  └─────────────┘  └──────────────┘


══════════════════════════════════════════════════════
 FILE SYSTEM MAP
══════════════════════════════════════════════════════

Recursive/                ◄── THE FRAMEWORK (portable)
├── engine/               daemon.sh, pick-role.py, lib-agent.sh
├── operators/            6 × SKILL.md + references/
├── lib/                  costs, cleanup, compact, config, eval
├── prompts/              autonomous.md, checkpoints.md
├── agents/               5 sub-agent definitions
├── ops/                  DAEMON, OPERATIONS, PRE-PUSH, SCORING
├── scripts/              init.sh, validate-tasks, list-tasks
├── skills/               setup/ (first-run wizard)
├── templates/            project scaffolds
└── tests/                test_pick_role.py

.recursive/               ◄── RUNTIME STATE (per-project)
├── handoffs/             LATEST.md (session memory)
├── tasks/                work queue + .next-id
├── sessions/             index.md + costs.json + *.log
├── learnings/            INDEX.md + knowledge files
├── evaluations/          quality score reports
├── vision/               human input: what to build
├── vision-tracker/       progress bars
├── changelog/            version history
├── architecture/         MODULE_MAP.md
├── autonomy/             autonomy score reports
├── strategy/             strategy reports
├── healer/               health observations
├── reviews/              code review logs
└── plans/                meta-layer planning

nightshift/               ◄── THE TARGET PROJECT
├── core/                 errors, types, constants, shell, state
├── settings/             config, eval_targets
├── owl/                  hardening loop
├── raven/                feature builder
├── infra/                worktree, module_map, multi
├── schemas/              JSON schemas
├── scripts/              check, install, run, test, smoke-test
└── tests/                847 tests
```
