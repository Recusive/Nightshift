# Daemon Operations Guide

This is the operator reference for the current Nightshift control plane.
Nightshift now runs through one unified daemon, `scripts/daemon.sh`, and that
daemon chooses a role each cycle with `scripts/pick-role.py`.

---

## Unified Architecture

One loop owns the repo and the lockfile. Each cycle it:

1. Resets to `origin/main`
2. Runs housekeeping
3. Runs the pentest preflight
4. Resets again
5. Picks the session role
6. Loads the matching prompt
7. Runs the agent
8. Records logs, cost, and session index data
9. Optionally runs evaluation
10. Sleeps or trips the retry/circuit-breaker path

Role selection lives in [scripts/pick-role.py](/Users/no9labs/Developer/Recursive/Nightshift/scripts/pick-role.py). The scoring rules are documented in [docs/ops/ROLE-SCORING.md](/Users/no9labs/Developer/Recursive/Nightshift/docs/ops/ROLE-SCORING.md).

## Roles

| Role | Prompt | Purpose |
|------|--------|---------|
| `build` | `docs/prompt/evolve.md` | Pick a task, implement, test, review, merge |
| `review` | `docs/prompt/review.md` | Review code quality and patch defects |
| `oversee` | `docs/prompt/overseer.md` | Audit queue/process drift and fix systemic issues |
| `strategize` | `docs/prompt/strategist.md` | Big-picture planning and report writing |
| `achieve` | `docs/prompt/achieve.md` | Raise autonomy and remove human dependencies |

`docs/prompt/evolve-auto.md` is prepended to every unified-daemon session
before the role prompt.

---

## Starting the Daemon

### Foreground

```bash
bash scripts/daemon.sh
bash scripts/daemon.sh codex
bash scripts/daemon.sh claude 60
bash scripts/daemon.sh claude 60 10
```

Arguments are:

1. agent name
2. pause between sessions in seconds
3. max sessions (`0` means loop forever)

### tmux

```bash
tmux new-session -d -s nightshift "bash scripts/daemon.sh claude 60"
tmux capture-pane -t nightshift -p -S -20
```

This is the recommended production path.

### Force a Specific Role

Use `NIGHTSHIFT_FORCE_ROLE` when you want the unified daemon to run one role
instead of scoring all roles:

```bash
NIGHTSHIFT_FORCE_ROLE=build bash scripts/daemon.sh claude 60
NIGHTSHIFT_FORCE_ROLE=review bash scripts/daemon.sh codex 60
NIGHTSHIFT_FORCE_ROLE=oversee bash scripts/daemon.sh claude 120 1
NIGHTSHIFT_FORCE_ROLE=strategize bash scripts/daemon.sh claude 0 1
NIGHTSHIFT_FORCE_ROLE=achieve bash scripts/daemon.sh claude 0 1
```

Valid values are `build`, `review`, `oversee`, `strategize`, and `achieve`.

### Optional Environment Variables

| Variable | Meaning |
|----------|---------|
| `NIGHTSHIFT_FORCE_ROLE` | Skip scoring and force one role |
| `NIGHTSHIFT_BUDGET` | Stop after cumulative spend reaches this USD amount |
| `NIGHTSHIFT_PENTEST_AGENT` | Use a different agent for the pentest preflight |
| `NIGHTSHIFT_PENTEST_MAX_TURNS` | Override the pentest turn budget (default `120`) |
| `NIGHTSHIFT_KEEP_LOGS` | Number of session logs to retain live |
| `NIGHTSHIFT_KEEP_HEALER_ENTRIES` | Healer-log retention limit |

---

## How Role Selection Works

At the start of every cycle, `scripts/daemon.sh` calls
[scripts/pick-role.py](/Users/no9labs/Developer/Recursive/Nightshift/scripts/pick-role.py).
That scorer reads the live system state and prints one winner.

Primary inputs:

- `docs/handoffs/LATEST.md`
- `docs/sessions/index.md`
- the latest report in `docs/evaluations/`
- pending/stale task counts from `docs/tasks/`
- `docs/healer/log.md`
- the latest report in `docs/autonomy/`
- open GitHub issues labeled `needs-human`

The exact math belongs in
[docs/ops/ROLE-SCORING.md](/Users/no9labs/Developer/Recursive/Nightshift/docs/ops/ROLE-SCORING.md),
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

After reset, the daemon hot-reloads shared shell helpers from `lib-agent.sh`.
If `daemon.sh` itself changed on `main`, it `exec`s into the new version.

Housekeeping then runs:

- rotate old session logs
- trim the healer log
- prune orphan branches
- compact old handoffs
- archive done task files
- sync GitHub issues labeled `task` into `docs/tasks/`

### 2. Open PR recovery

If a previous session left an open PR, the daemon injects a recovery instruction
into both the pentest prompt and the main role prompt. The session is expected
to finish or repair that PR instead of silently rebuilding the work.

### 3. Pentest preflight

The daemon always runs `docs/prompt/pentest.md` first. Its result is inserted as
a `<pentest_data>` block into the main session prompt. The daemon treats that
block as data, not instructions, and resets the repo again after the preflight.

### 4. Prompt construction

The unified prompt stack for the main session is:

1. optional prompt-integrity alert from the previous cycle
2. optional open-PR recovery instruction
3. the current `<pentest_data>` block
4. `docs/prompt/evolve-auto.md`
5. one role prompt chosen by `pick-role.py`

### 5. Agent run

The agent runs with stream-json logging into `docs/sessions/YYYYMMDD-HHMMSS.log`.
When the run ends, the daemon records:

- exit code
- duration
- session cost
- detected role
- best-effort feature summary
- best-effort PR URL

Those fields are appended to `docs/sessions/index.md`.

### 6. Evaluation and wait path

If the cycle succeeded and the evaluation cadence says "run now", the daemon
launches evaluation after the session. Otherwise it sleeps for the configured
pause. Failed sessions increment the consecutive-failure counter and eventually
trip the circuit breaker.

---

## Logs and State

These are the authoritative runtime artifacts:

| Path | Purpose |
|------|---------|
| `docs/sessions/index.md` | Unified session history across all roles |
| `docs/sessions/*.log` | Stream-json session logs |
| `docs/sessions/*-pentest.log` | Pentest preflight logs |
| `docs/sessions/costs.json` | Cost ledger used by budget checks |
| `docs/handoffs/LATEST.md` | Short-term memory for the next cycle |
| `docs/evaluations/*.md` | Real-repo evaluation reports |
| `docs/healer/log.md` | System-health observations |

Legacy role-specific indexes still exist:

- `docs/sessions/index-review.md`
- `docs/sessions/index-overseer.md`

Treat them as historical artifacts from the old single-role scripts. The unified
daemon writes `docs/sessions/index.md`.

---

## Monitoring

### Check whether the daemon is alive

```bash
tmux has-session -t nightshift 2>&1 && echo alive || echo dead
tmux capture-pane -t nightshift -p -S -20
```

### Inspect the latest unified session log

```bash
LATEST_LOG=$(find docs/sessions -maxdepth 1 -name '*.log' ! -name '*-pentest.log' | sort | tail -1)
```

Then inspect it directly or with a small parser. Stream-json logs contain
assistant messages, tool calls, and the final `result` block.

### Check the current system state

```bash
cat docs/handoffs/LATEST.md
cat docs/sessions/index.md
gh pr list --state all --limit 10
```

### Understand a surprising role pick

```bash
python3 scripts/pick-role.py "$(pwd)"
```

The script prints the winning role to stdout and the scoring breakdown to stderr.

---

## Legacy Entry Points

These files still exist, but they are no longer the primary control plane:

| Script | Status | Notes |
|--------|--------|-------|
| `scripts/daemon.sh` | current | Unified daemon, recommended entrypoint |
| `scripts/daemon-review.sh` | deprecated | Emits a deprecation warning and points to `NIGHTSHIFT_FORCE_ROLE=review` |
| `scripts/daemon-overseer.sh` | deprecated | Emits a deprecation warning and points to `NIGHTSHIFT_FORCE_ROLE=oversee` |
| `scripts/daemon-strategist.sh` | legacy helper | Single-run strategist entrypoint; unified daemon can also select `strategize` |

If you need manual role selection, prefer the unified daemon plus
`NIGHTSHIFT_FORCE_ROLE`.

---

## Common Operations

### Run one overseer audit cycle

```bash
NIGHTSHIFT_FORCE_ROLE=oversee bash scripts/daemon.sh claude 0 1
```

### Run one strategist cycle under the unified daemon

```bash
NIGHTSHIFT_FORCE_ROLE=strategize bash scripts/daemon.sh claude 0 1
```

### Run one ACHIEVE cycle

```bash
NIGHTSHIFT_FORCE_ROLE=achieve bash scripts/daemon.sh claude 0 1
```

### Resume normal autonomous behavior

```bash
unset NIGHTSHIFT_FORCE_ROLE
bash scripts/daemon.sh claude 60
```

---

## Failure and Recovery

### Another daemon already holds the lock

The unified daemon uses `.nightshift-daemon.lock`. If startup says another
daemon is running, verify first and only then remove the lock directory.

### Prompt/control files were modified during a session

Prompt integrity is checked around both the pentest and main session. If a
session mutates prompt/control files, the daemon writes `prompt-alert.md`,
resets the repo, and injects that alert into the next cycle.

### Three consecutive failures

The circuit breaker stops the daemon after three failed cycles. Inspect:

- `docs/sessions/index.md`
- the latest session log
- the latest pentest log
- `docs/handoffs/LATEST.md`

### Budget stop

If `NIGHTSHIFT_BUDGET` is set and cumulative spend reaches it, the daemon stops
and records a `BUDGET-STOP` row in `docs/sessions/index.md`.

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
tmux kill-session -t nightshift
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
tmux new-session -d -s nightshift "caffeinate -s bash scripts/daemon.sh codex 60"
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
| [scripts/daemon.sh](/Users/no9labs/Developer/Recursive/Nightshift/scripts/daemon.sh) | Unified loop, housekeeping, pentest, session logging |
| [scripts/pick-role.py](/Users/no9labs/Developer/Recursive/Nightshift/scripts/pick-role.py) | Role scoring and selection |
| [scripts/lib-agent.sh](/Users/no9labs/Developer/Recursive/Nightshift/scripts/lib-agent.sh) | Shared shell helpers used by daemon entrypoints |
| [docs/ops/ROLE-SCORING.md](/Users/no9labs/Developer/Recursive/Nightshift/docs/ops/ROLE-SCORING.md) | Human-readable scoring reference |
| [docs/prompt/evolve-auto.md](/Users/no9labs/Developer/Recursive/Nightshift/docs/prompt/evolve-auto.md) | Global autonomous-mode constraints |
| [docs/prompt/evolve.md](/Users/no9labs/Developer/Recursive/Nightshift/docs/prompt/evolve.md) | BUILD role prompt |
| [docs/prompt/review.md](/Users/no9labs/Developer/Recursive/Nightshift/docs/prompt/review.md) | REVIEW role prompt |
| [docs/prompt/overseer.md](/Users/no9labs/Developer/Recursive/Nightshift/docs/prompt/overseer.md) | OVERSEE role prompt |
| [docs/prompt/strategist.md](/Users/no9labs/Developer/Recursive/Nightshift/docs/prompt/strategist.md) | STRATEGIZE role prompt |
| [docs/prompt/achieve.md](/Users/no9labs/Developer/Recursive/Nightshift/docs/prompt/achieve.md) | ACHIEVE role prompt |

---

## Source of Truth

When this guide and the live scripts disagree, trust the code:

1. `scripts/daemon.sh`
2. `scripts/pick-role.py`
3. `docs/ops/ROLE-SCORING.md`

This document should explain those files, not invent behavior that the code
does not implement.
