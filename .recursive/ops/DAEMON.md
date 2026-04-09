# Daemon Operations Guide

This is the operator reference for the current Nightshift control plane.
Nightshift runs as a v2 brain-delegates-to-sub-agents architecture.
`.recursive/engine/daemon.sh` runs a brain agent (Opus) each cycle that reads
the dashboard, thinks, and delegates to sub-agents (Sonnet) in git worktrees.

---

## v2 Architecture

One loop owns the repo and the lockfile. Each cycle it:

1. Resets to `origin/main`
2. Runs housekeeping
3. Gets advisory recommendation from `pick-role.py --advise`
4. Generates a system dashboard from `dashboard.py`
5. Runs the brain agent (Opus) with dashboard + advisory as context
6. Brain reads context, thinks (4 checkpoints), delegates to sub-agents
7. Sub-agents create PRs; brain reviews and merges them
8. Records logs, cost, and session index data
9. Trips circuit breaker or sleeps for next cycle

Role selection is advisory for the brain. The brain may override the recommendation.
Advisory scoring lives in `.recursive/engine/pick-role.py --advise`.

## Roles

| Role | Prompt | Purpose | Zone |
|------|--------|---------|------|
| `build` | `.recursive/agents/build.md` | Pick a task, implement, test, PR | project |
| `review` | `.recursive/agents/review.md` | Deep code review, fix quality issues, PR | project |
| `oversee` | `.recursive/agents/oversee.md` | Audit queue/process drift and fix systemic issues | project |
| `strategize` | `.recursive/agents/strategize.md` | Big-picture planning and report writing | project |
| `achieve` | `.recursive/agents/achieve.md` | Raise autonomy and remove human dependencies | project |
| `security` | `.recursive/agents/security.md` | Red team / pentest, produce findings report | project |
| `evolve` | `.recursive/agents/evolve.md` | Fix friction patterns in .recursive/ | framework |
| `audit-agent` | `.recursive/agents/audit-agent.md` | Review .recursive/ for contradictions and staleness | framework |

The brain reads `.recursive/agents/brain.md` for its full instructions.

---

## Starting the Daemon

### Foreground

```bash
bash .recursive/engine/daemon.sh
bash .recursive/engine/daemon.sh codex
bash .recursive/engine/daemon.sh claude 60
bash .recursive/engine/daemon.sh claude 60 10
```

Arguments are:

1. agent name
2. pause between sessions in seconds
3. max sessions (`0` means loop forever)

### tmux

```bash
tmux new-session -d -s recursive "caffeinate -s bash .recursive/engine/daemon.sh claude 60"
tmux capture-pane -t recursive -p -S -20
```

This is the recommended production path.

### Force a Specific Role

Use `RECURSIVE_FORCE_ROLE` when you want the unified daemon to run one role
instead of scoring all roles:

```bash
RECURSIVE_FORCE_ROLE=build bash .recursive/engine/daemon.sh claude 60
RECURSIVE_FORCE_ROLE=review bash .recursive/engine/daemon.sh codex 60
RECURSIVE_FORCE_ROLE=oversee bash .recursive/engine/daemon.sh claude 120 1
RECURSIVE_FORCE_ROLE=strategize bash .recursive/engine/daemon.sh claude 0 1
RECURSIVE_FORCE_ROLE=achieve bash .recursive/engine/daemon.sh claude 0 1
RECURSIVE_FORCE_ROLE=security-check bash .recursive/engine/daemon.sh claude 0 1
RECURSIVE_FORCE_ROLE=evolve bash .recursive/engine/daemon.sh claude 0 1
RECURSIVE_FORCE_ROLE=audit bash .recursive/engine/daemon.sh claude 0 1
```

Valid values are `build`, `review`, `oversee`, `strategize`, `achieve`, `security-check`, `evolve`, and `audit`.

### Optional Environment Variables

| Variable | Meaning |
|----------|---------|
| `RECURSIVE_FORCE_ROLE` | Skip scoring and force one role |
| `RECURSIVE_BUDGET_USD` | Stop after cumulative spend reaches this USD amount (default: 50) |
| `RECURSIVE_CLAUDE_MODEL` | Brain model override (default: claude-opus-4-6) |

---

## How Role Selection Works

At the start of every cycle, `.recursive/engine/daemon.sh` calls
[.recursive/engine/pick-role.py](/Users/no9labs/Developer/.recursive/Nightshift/.recursive/engine/pick-role.py).
That scorer reads the live system state and prints one winner.

Primary inputs:

- `.recursive/handoffs/LATEST.md`
- `.recursive/sessions/index.md`
- the latest report in `.recursive/evaluations/`
- pending/stale task counts from `.recursive/tasks/`
- `.recursive/healer/log.md`
- the latest report in `.recursive/autonomy/`
- open GitHub issues labeled `needs-human`

The exact math belongs in
[.recursive/ops/ROLE-SCORING.md](/Users/no9labs/Developer/.recursive/Nightshift/.recursive/ops/ROLE-SCORING.md),
not in this file. Read that file when debugging "why did the daemon pick this
role?" behavior.

Important constraints:

- Urgent tasks force `build`
- Low evaluation scores gate `build` toward eval-related tasks
- `strategize` is capped to avoid hiding in planning mode
- `achieve` is capped to avoid starving product work
- Ties fall back to `build`

---

## Cycle Lifecycle

### 1. Reset and housekeeping

Each cycle begins from a clean checkout of `origin/main`:

```bash
git fetch origin
git checkout main
git reset --hard origin/main
git clean -fd
```

After reset, the daemon hot-reloads shared shell helpers from `.recursive/engine/lib-agent.sh`.
If `.recursive/engine/daemon.sh` itself changed on `main`, it `exec`s into the new version.

Housekeeping then runs:

- rotate old session logs
- trim the healer log
- prune orphan branches
- compact old handoffs
- archive done task files
- sync GitHub issues labeled `task` into `.recursive/tasks/`

### 2. Open PR detection

The daemon queries for open PRs from previous sessions and injects the list
into the brain context as `<open_prs>`. The brain processes these before
starting new work.

### 3. Advisory and dashboard

The daemon calls `pick-role.py --advise` to get a JSON advisory recommendation.
It calls `dashboard.py` to generate a system-state dashboard. Both are injected
into the brain prompt as `<advisory_recommendation>` and `<dashboard>`.

### 4. Prompt guard snapshot

Before running the brain, the daemon snapshots all prompt/control files with
`save_prompt_snapshots`. After the session, `check_prompt_integrity` and
`check_origin_integrity` verify that no files were tampered with.

### 5. Brain run

The brain agent (Opus) runs with stream-json logging into `.recursive/sessions/raw/YYYYMMDD-HHMMSS.log`.
The brain reads the context, thinks through 4 checkpoints, and delegates to sub-agents.
When the run ends, the daemon records:

- exit code
- duration
- session cost
- feature (extracted from log via `extract_feature_from_log`)
- PR URL (extracted from log via `extract_pr_url_from_log`)
- prompt-tampered flag (set by `check_prompt_integrity` / `check_origin_integrity`)

These fields are written as a single markdown table row to
`.recursive/sessions/index.md` via `append_session_index_row` in
`lib-agent.sh`. This function sanitizes all values (strips pipe chars and
newlines) so each session always produces exactly one well-formed row.

**Do NOT write to `sessions/index.md` manually.** The daemon is the sole
writer. Manual writes cause multiline/broken rows that corrupt dashboard
signals.

### 6. Circuit breaker

Failed sessions increment the consecutive-failure counter. After 3 consecutive
failures the daemon stops. Auth failures are not counted toward the circuit breaker.

---

## Logs and State

These are the authoritative runtime artifacts:

| Path | Purpose |
|------|---------|
| `.recursive/sessions/index.md` | Unified session history across all roles |
| `.recursive/sessions/*.log` | Stream-json session logs |
| `.recursive/sessions/*-pentest.log` | Pentest preflight logs |
| `.recursive/sessions/costs.json` | Cost ledger used by budget checks |
| `.recursive/handoffs/LATEST.md` | Short-term memory for the next cycle |
| `.recursive/evaluations/*.md` | Real-repo evaluation reports |
| `.recursive/healer/log.md` | System-health observations |

Legacy role-specific indexes still exist:

- `.recursive/sessions/index-review.md`
- `.recursive/sessions/index-overseer.md`

Treat them as historical artifacts from the old single-role scripts. The unified
daemon writes `.recursive/sessions/index.md`.

---

## Monitoring

### Check whether the daemon is alive

```bash
tmux has-session -t recursive 2>&1 && echo alive || echo dead
tmux capture-pane -t recursive -p -S -20
```

### Inspect the latest unified session log

```bash
LATEST_LOG=$(find .recursive/sessions/raw -maxdepth 1 -name '*.log' | sort | tail -1)
```

Then inspect it directly or with a small parser. Stream-json logs contain
assistant messages, tool calls, and the final `result` block.

### Check the current system state

```bash
cat .recursive/handoffs/LATEST.md
cat .recursive/sessions/index.md
gh pr list --state all --limit 10
```

### Understand a surprising role pick

```bash
python3 .recursive/engine/pick-role.py "$(pwd)"
```

The script prints the winning role to stdout and the scoring breakdown to stderr.

---

## Legacy Entry Points

These files still exist, but they are no longer the primary control plane:

| Script | Status | Notes |
|--------|--------|-------|
| `.recursive/engine/daemon.sh` | current | Unified daemon, recommended entrypoint |
| `scripts/daemon-review.sh` | removed | Use `RECURSIVE_FORCE_ROLE=review` with the unified daemon |
| `scripts/daemon-overseer.sh` | removed | Use `RECURSIVE_FORCE_ROLE=oversee` with the unified daemon |
| `scripts/daemon-strategist.sh` | removed | Use `RECURSIVE_FORCE_ROLE=strategize` with the unified daemon |

If you need manual role selection, prefer the unified daemon plus
`RECURSIVE_FORCE_ROLE`.

---

## Common Operations

### Run one overseer audit cycle

```bash
RECURSIVE_FORCE_ROLE=oversee bash .recursive/engine/daemon.sh claude 0 1
```

### Run one strategist cycle under the unified daemon

```bash
RECURSIVE_FORCE_ROLE=strategize bash .recursive/engine/daemon.sh claude 0 1
```

### Run one ACHIEVE cycle

```bash
RECURSIVE_FORCE_ROLE=achieve bash .recursive/engine/daemon.sh claude 0 1
```

### Resume normal autonomous behavior

```bash
unset RECURSIVE_FORCE_ROLE
bash .recursive/engine/daemon.sh claude 60
```

---

## Failure and Recovery

### Another daemon already holds the lock

The unified daemon uses `.recursive-daemon.lock`. If startup says another
daemon is running, verify first and only then remove the lock directory.

### Prompt/control files were modified during a session

Prompt integrity is checked around both the pentest and main session. If a
session mutates prompt/control files, the daemon writes `prompt-alert.md`,
resets the repo, and injects that alert into the next cycle.

### Three consecutive failures

The circuit breaker stops the daemon after three failed cycles. Inspect:

- `.recursive/sessions/index.md`
- the latest session log
- the latest pentest log
- `.recursive/handoffs/LATEST.md`

### Budget stop

If `RECURSIVE_BUDGET` is set and cumulative spend reaches it, the daemon stops
and records a `BUDGET-STOP` row in `.recursive/sessions/index.md`.

### Wrong repo state after a crash

Start with:

```bash
git status --short
git worktree list
gh pr list --state open
```

The daemon already hard-resets to `origin/main` at the start of each cycle, so
manual cleanup should be rare.

---

## Security Incident Response

If `check_origin_integrity` detects that a file was pushed directly to
`origin/main` during an agent cycle (exit code 2), the daemon prints a
`notify_human` alert and breaks out of its loop.  The injected file **remains
on `origin/main`** and cannot be auto-reverted without risking loss of
legitimate intervening commits.

### What to do when the daemon aborts with exit code 2

**Step 1 — Kill the daemon session immediately.**

```bash
tmux kill-session -t recursive
```

Do NOT wait, do NOT let the daemon restart.  Each auto-restart calls
`reset_repo_state` which does `git reset --hard origin/main`, pulling the
injected file to disk before the guard fires and aborts again.  The injected
file lands on disk on every restart iteration.

**Step 2 — Remove the injected file from `origin/main` via a PR.**

```bash
# Identify the injected file from the notify_human message or daemon log
# Then, on a clean checkout or worktree:
git checkout -b fix/remove-injected-file origin/main
git rm path/to/injected/file
git commit -m "security: remove injected file from guard directory"
git push origin fix/remove-injected-file
gh pr create --title "security: remove injected file" --body "Removing file injected during agent cycle. See daemon log for details."
# Review the PR yourself, then merge
gh pr merge --merge --admin
```

**Do NOT direct-push to `main`.**  Even for a security remediation, a PR gives
you a second look at what you are removing.

**Step 3 — Verify `origin/main` is clean.**

```bash
git fetch origin
git log --no-merges --first-parent --oneline origin/main -10
# Confirm no unexpected direct-push commits remain
```

**Step 4 — Restart the daemon.**

```bash
tmux new-session -d -s recursive "caffeinate -s bash .recursive/engine/daemon.sh claude 60"
```

### TOCTOU window

There is a short window between when the daemon boots (`reset_repo_state`
pulls the latest `origin/main`) and when `check_origin_integrity` runs its
comparison.  The guard fires before any agent session starts, so no attacker
code runs.  However, if the daemon is killed and restarted without remediating
`origin/main`, the injected file will be checked out to disk on every restart
iteration.  This is why Step 1 (kill the session) must happen before Step 2
(remove the file).

---

## Key Files

| File | What it owns |
|------|---------------|
| `.recursive/engine/daemon.sh` | v2 brain loop, housekeeping, advisory, session logging |
| `.recursive/engine/pick-role.py` | Role scoring and advisory recommendation |
| `.recursive/engine/dashboard.py` | System dashboard aggregator for brain context |
| `.recursive/engine/signals.py` | Signal readers (eval, tasks, sessions, healer) |
| `.recursive/engine/lib-agent.sh` | Shared shell helpers (prompt guard, housekeeping, worktrees) |
| `.recursive/agents/brain.md` | Brain agent definition (Opus orchestrator) |
| `.recursive/ops/ROLE-SCORING.md` | Human-readable scoring reference (advisory only in v2) |
| `.recursive/prompts/autonomous.md` | Global autonomous-mode constraints (v1 operators) |

---

## Source of Truth

When this guide and the live scripts disagree, trust the code:

1. `.recursive/engine/daemon.sh`
2. `.recursive/engine/pick-role.py`
3. `.recursive/ops/ROLE-SCORING.md`

This document should explain those files, not invent behavior that the code
does not implement.
