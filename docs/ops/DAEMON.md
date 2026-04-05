# Daemon Operations Guide

How to run, monitor, and manage the four Nightshift daemons. This is the complete reference for operating the autonomous system.

---

## The Four Daemons

Nightshift has four daemons, each with a different role:

| Daemon | Script | Prompt | Loops? | Purpose |
|--------|--------|--------|--------|---------|
| **Builder** | `scripts/daemon.sh` | `evolve-auto.md` + `evolve.md` | Yes, forever | Picks up tasks, builds features, ships code |
| **Reviewer** | `scripts/daemon-review.sh` | `review.md` | Yes, forever | Reviews code file by file, fixes quality issues |
| **Overseer** | `scripts/daemon-overseer.sh` | `overseer.md` | Yes, forever | Audits task queue, fixes priorities, cleans duplicates, catches direction problems |
| **Strategist** | `scripts/daemon-strategist.sh` | `strategist.md` | No, runs once | Reviews the big picture, advises human on what to change |

All four share a lockfile (`.nightshift-daemon.lock`) so **only one can run at a time**. They'd conflict on git otherwise.

### Quick start

```bash
make daemon       # Builder — loops, ships features
make review       # Reviewer — loops, fixes code quality
make overseer     # Overseer — loops, audits and fixes systemic issues
make strategist   # Strategist — runs once, produces a report
```

### Typical workflow

1. Run `make daemon` overnight — it builds features from the task queue
2. Run `make overseer` after a build run — it audits what was built, fixes task priorities, cleans duplicates, catches direction problems
3. Run `make strategist` when you want a human-readable big picture review
4. Run `make review` to harden what was built
5. Run `make daemon` again to continue building

Or: builder during the day, overseer + reviewer overnight.

---

## Builder Daemon (`scripts/daemon.sh`)

The primary daemon. Picks up tasks, builds features, tests, PRs, merges. Each session:

---

## Starting the Daemon

### Quick start (run in foreground)

```bash
./scripts/daemon.sh              # interactive setup (prompts for agent + duration)
./scripts/daemon.sh codex        # codex agent
./scripts/daemon.sh claude 120   # 120s pause between sessions
./scripts/daemon.sh claude 60 5  # stop after 5 sessions
```

### Production start (tmux — recommended)

Always run the daemon in tmux so it survives terminal disconnects and can be monitored from any session.

```bash
# Start the daemon in a detached tmux session
tmux new-session -d -s nightshift "bash scripts/daemon.sh claude 60"

# Verify it's running
tmux capture-pane -t nightshift -p -S -15
```

You should see:

```
Lock acquired. PID XXXXX.

==================================================
  NIGHTSHIFT DAEMON
  Agent:       claude
  Pause:       60s between sessions
  Max sessions: unlimited
  Circuit:     stops after 3 consecutive failures
  Logs:        /path/to/docs/sessions
  Stop:        Ctrl+C
==================================================

-- Session 1 --- HH:MM --- YYYYMMDD-HHMMSS --
```

### With a session limit

```bash
# Run 10 sessions then stop (good for overnight runs with a budget)
tmux new-session -d -s nightshift "bash scripts/daemon.sh claude 60 10"
```

### Using make

```bash
make daemon   # shortcut for ./scripts/daemon.sh (foreground)
```

---

## Monitoring the Daemon

### From a Claude Code session (agent-as-monitor)

This is how you supervise the daemon from another Claude session. Tell Claude to monitor and it will read the stream-json logs.

**1. Check if the daemon is alive:**

```bash
tmux has-session -t nightshift 2>&1 && echo "alive" || echo "dead"
ps aux | grep "claude -p" | grep -v grep
```

**2. Read the live session log:**

The daemon outputs `--output-format stream-json` which produces one JSON event per line. Each event contains tool calls, messages, and results. Use this Python parser to read them:

```bash
LATEST_LOG=$(ls docs/sessions/*.log | tail -1)
cat "$LATEST_LOG" | python3 -c "
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        event = json.loads(line)
        etype = event.get('type', '?')
        if etype == 'assistant':
            for block in event.get('message', {}).get('content', []):
                if block.get('type') == 'tool_use':
                    name = block['name']
                    inp = block.get('input', {})
                    if name == 'Bash':
                        print(f'BASH: {inp.get(\"command\", \"\")[:90]}')
                    elif name in ('Read', 'Write', 'Edit'):
                        print(f'{name}: {inp.get(\"file_path\", \"\").split(\"/\")[-1]}')
                    elif name == 'Agent':
                        print(f'AGENT: {inp.get(\"description\", \"\")[:60]}')
                    else:
                        print(name)
                elif block.get('type') == 'text':
                    t = block.get('text', '').strip()
                    if t and len(t) > 15:
                        print(f'MSG: {t[:140]}')
        elif etype == 'result':
            t = event.get('result', '').strip()
            if t:
                print(f'DONE: {t[:200]}')
    except json.JSONDecodeError:
        pass
"
```

This shows you exactly what the agent is doing: which files it reads, which tools it calls, what it's thinking, and the final result.

**3. Check event count (how far along is the session):**

```bash
LATEST_LOG=$(ls docs/sessions/*.log | tail -1)
python3 -c "
import json
count = sum(1 for line in open('$LATEST_LOG')
            if line.strip() and json.loads(line.strip()).get('type') == 'assistant')
print(f'{count} events (of 500 max turns)')
"
```

**4. Check for PRs (proof the agent is shipping):**

```bash
gh pr list --state all --limit 5
```

**5. Check the session index:**

```bash
cat docs/sessions/index.md
```

**6. Check the tmux pane (daemon wrapper output):**

```bash
tmux capture-pane -t nightshift -p -S -20
```

### Understanding the stream-json log format

Each line in the log is a JSON object. The key event types:

| Type | What it contains |
|------|-----------------|
| `assistant` | Agent's response — contains `message.content[]` with `tool_use` and `text` blocks |
| `result` | Final session output — contains the `SESSION COMPLETE` report |
| `system` | System events — API retries, errors |

**Tool use events** (inside `assistant` messages):

```json
{
  "type": "assistant",
  "message": {
    "content": [
      {
        "type": "tool_use",
        "name": "Read",
        "input": {"file_path": "/path/to/file.py"}
      }
    ]
  }
}
```

**Text events** (agent thinking/speaking):

```json
{
  "type": "assistant",
  "message": {
    "content": [
      {
        "type": "text",
        "text": "Now let me build the feature..."
      }
    ]
  }
}
```

**Result event** (session complete):

```json
{
  "type": "result",
  "result": "SESSION COMPLETE\n================\n\nBuilt: Feature name\n..."
}
```

---

## Stopping the Daemon

### Graceful stop (after current session finishes)

From inside the tmux session:

```bash
tmux send-keys -t nightshift C-c
```

This sends Ctrl+C which triggers the trap handler. The daemon finishes the current pause/session boundary and stops cleanly.

### Immediate stop

```bash
tmux kill-session -t nightshift
```

This kills everything immediately. If a session is mid-work, the PR may be left open. The next daemon run will detect it via open-PR recovery.

### If the lock file is stuck

If the daemon crashes without cleanup, the lock file remains:

```bash
rmdir .nightshift-daemon.lock
```

---

## What to Look For (Is It Working?)

### Signs the daemon is healthy

1. **Session index grows** — new rows in `docs/sessions/index.md` with `success` status
2. **PRs are merging** — `gh pr list --state merged --limit 5` shows recent merges
3. **Tests are increasing** — `python3 -m pytest tests/ -q` shows growing test count
4. **Handoff updates** — `docs/handoffs/LATEST.md` changes after each session
5. **Log files are large** — each `.log` file should be 1-6MB of stream-json

### Signs something is wrong

1. **Circuit breaker tripped** — session index shows `CIRCUIT-BREAK` row. Check the last 3 log files.
2. **Consecutive failures** — multiple `failed` rows in the index. Read the logs to find the error.
3. **Log file is 0 bytes** — the session started but produced no output. Check if `claude` CLI is installed and authenticated.
4. **Open PR stuck** — `gh pr list --state open` shows a PR that's been open for multiple sessions. May have merge conflicts.
5. **No new events** — if the latest log hasn't grown in 10+ minutes and the process is alive, the agent may be stuck on a long-running command.

### Quick health check (copy-paste this)

```bash
echo "=== DAEMON ===" && tmux has-session -t nightshift 2>&1 && echo "ALIVE" || echo "DEAD"
echo "=== PROCESS ===" && ps aux | grep "claude -p" | grep -v grep | awk '{print "PID:",$2,"CPU:",$3}' || echo "none"
echo "=== LATEST LOG ===" && ls -la docs/sessions/*.log | tail -1
echo "=== RECENT PRS ===" && gh pr list --state all --limit 3
echo "=== INDEX ===" && tail -5 docs/sessions/index.md
echo "=== TESTS ===" && python3 -m pytest tests/ -q 2>&1 | tail -1
```

---

## Session Lifecycle (What Happens Each Cycle)

```
daemon.sh loop iteration
    |
    v
git fetch + reset --hard origin/main    # clean slate
    |
    v
housekeeping                            # rotate logs, prune branches,
  cleanup_old_logs                      #   compact handoffs, archive tasks,
  cleanup_orphan_branches               #   sync GitHub Issues -> task files
  compact_handoffs
  archive_done_tasks
  sync_github_tasks
    |
    v
check gh pr list --state open           # open-PR recovery
    |
    v
build prompt (evolve-auto.md + evolve.md)
    |
    v
claude -p --max-turns 500               # the autonomous session
  --output-format stream-json            # line-by-line JSON events
  --verbose                              # full tool output
  2>&1 | tee $LOG_FILE                   # capture everything
    |
    v
extract feature + PR from log           # session index update
    |
    v
circuit breaker check                   # stop after 3 consecutive failures
    |
    v
sleep $PAUSE                            # 60s default
    |
    v
next iteration
```

---

## Configuration

| Parameter | Default | How to change |
|-----------|---------|--------------|
| Agent | claude | 1st arg: `./scripts/daemon.sh codex` |
| Pause between sessions | 60s | 2nd arg: `./scripts/daemon.sh claude 120` |
| Max sessions | unlimited (0) | 3rd arg: `./scripts/daemon.sh claude 60 10` |
| Max turns per session | 500 | Edit `MAX_TURNS` in `scripts/daemon.sh` |
| Circuit breaker threshold | 3 failures | Edit `MAX_CONSECUTIVE_FAILURES` in `scripts/daemon.sh` |
| Log directory | `docs/sessions/` | Edit `LOG_DIR` in `scripts/daemon.sh` |

---

## Files

| File | Purpose |
|------|---------|
| `scripts/daemon.sh` | The daemon script |
| `docs/prompt/evolve.md` | The session lifecycle prompt (11 steps) |
| `docs/prompt/evolve-auto.md` | Autonomous override (skip human confirmation) |
| `docs/sessions/*.log` | Stream-json logs (one per session) |
| `docs/sessions/index.md` | Session index (one row per session) |
| `.nightshift-daemon.lock` | Lock directory (prevents two daemons) |

---

## Troubleshooting

### "Another daemon may be running"

The lock directory exists. Either another daemon is running, or a previous one crashed.

```bash
# Check if a daemon process exists
ps aux | grep daemon.sh | grep -v grep

# If no process, remove the stale lock
rmdir .nightshift-daemon.lock
```

### Session fails immediately (exit 1, 0 minutes)

The `claude` CLI may not be authenticated or installed.

```bash
claude --version
claude -p "hello" --output-format json
```

### Agent builds nothing (session succeeds but no PR)

The handoff may be out of date or there are no pending tasks. Check:

```bash
cat docs/handoffs/LATEST.md
ls docs/tasks/*.md
```

### Log file is empty

If you see 0-byte log files, the daemon may be using an old version without `--output-format stream-json`. Update `scripts/daemon.sh` to ensure the claude command includes:

```
--output-format stream-json --verbose
```

---

## Reviewer Daemon (`scripts/daemon-review.sh`)

Loops forever like the builder, but with a different mission: code quality.

### What it does each session

1. Picks ONE file from `nightshift/` that hasn't been reviewed recently
2. Reads every function in that file
3. Fixes: dead code, weak typing, missing error handling, unclear naming, untested paths
4. Commits all fixes for that file, creates PR, sub-agent review, merges
5. Logs the review to `docs/reviews/YYYY-MM-DD-module.md`

### Running it

```bash
# Foreground
./scripts/daemon-review.sh              # interactive setup (prompts for agent + duration)
./scripts/daemon-review.sh claude 60 5  # stop after 5 sessions

# tmux (recommended)
tmux new-session -d -s nightshift-review "bash scripts/daemon-review.sh claude 60"

# make
make review
```

### Session index

Separate index: `docs/sessions/index-review.md`

### Key differences from the builder

- Does NOT read the task queue
- Does NOT read the evolve prompt
- Reviews ONE file per session (not a feature)
- 200 max turns (smaller scope = fewer turns needed)
- Uses `docs/reviews/` to track what's been reviewed

---

## Strategist Daemon (`scripts/daemon-strategist.sh`)

Runs ONCE. Not a loop. Produces a strategy report for the human.

### What it does

1. Reads git log, merged PRs, handoffs, evaluations, learnings, session indices
2. Analyzes: what's working, what's failing, what's missing
3. Writes 3-5 concrete recommendations with evidence
4. Saves report to `docs/strategy/YYYY-MM-DD.md`
5. Presents to the human for decisions

### Running it

```bash
./scripts/daemon-strategist.sh          # interactive setup (prompts for agent)
./scripts/daemon-strategist.sh codex    # codex

# make
make strategist
```

### What happens after

You read the report. For each recommendation:
- "Yes" — create a task in `docs/tasks/` (the strategist can do this for you)
- "No" — explain why, strategist notes the feedback
- "Later" — skip it, it'll come up in the next review

The builder daemon picks up the resulting tasks.

---

## Running All Three (workflow)

You can only run one daemon at a time (shared lockfile). Here's the recommended pattern:

### Daily cycle

```
Morning:   make strategist         → read report, approve tasks
Day:       make daemon             → builder ships features
Evening:   Ctrl+C the builder
           make review             → reviewer hardens code overnight
Next day:  Ctrl+C the reviewer
           make strategist         → check on overnight work
           ... repeat
```

### Weekend / unattended

```bash
# Friday evening: start the builder with a session limit
tmux new-session -d -s nightshift "bash scripts/daemon.sh claude 60 20"

# It runs 20 sessions, stops. Monday: run strategist to see what happened.
make strategist
```

---

## Human Escalation (`notify_human`)

When the daemon hits a situation that requires human attention, it creates a GitHub issue with the `needs-human` label. This happens automatically for:

- **Circuit breaker tripped** -- 3 consecutive session failures (all daemons)
- **Budget limit reached** -- cumulative spending exceeds the configured limit (builder)
- **Builder health concern** -- the builder's "Observe the System" step (Step 6n in evolve.md) flags system health as "concern" in the handoff

### How it works

`notify_human` is a shell function in `scripts/lib-agent.sh`. It:

1. Creates a GitHub issue titled `[Nightshift] <title>` with the `needs-human` label
2. If `notification_webhook` is set in `.nightshift.json`, POSTs to that URL (Slack, Discord, etc.)
3. Fails silently -- never crashes the daemon

### Checking for escalations

```bash
gh issue list --label needs-human
```

### Optional webhook

Add a webhook URL to `.nightshift.json` for real-time notifications:

```json
{
  "notification_webhook": "https://hooks.slack.com/services/T00/B00/xxx"
}
```

The webhook receives a JSON payload: `{"text": "[Nightshift] <title>"}`.

### Observation-driven escalation

The builder's "Observe the System" step (Step 6n in evolve.md) checks system health each session. When health is "concern", the builder notes it prominently in the handoff so the human sees it. Critical patterns that cannot be self-fixed by creating tasks should be escalated via `notify_human` from the daemon scripts.

---

## Files Reference

| File | Purpose |
|------|---------|
| `scripts/daemon.sh` | Builder daemon |
| `scripts/daemon-review.sh` | Reviewer daemon |
| `scripts/daemon-strategist.sh` | Strategist (single run) |
| `docs/prompt/evolve.md` | Builder session prompt |
| `docs/prompt/evolve-auto.md` | Autonomous override for builder |
| `docs/prompt/review.md` | Reviewer session prompt |
| `docs/prompt/strategist.md` | Strategist session prompt |
| `docs/sessions/*.log` | Session logs (all daemons) |
| `docs/sessions/index.md` | Builder session index |
| `docs/sessions/index-review.md` | Reviewer session index |
| `docs/reviews/*.md` | Code review logs |
| `docs/strategy/*.md` | Strategy reports |
| `.nightshift-daemon.lock` | Shared lock (prevents concurrent daemons) |
