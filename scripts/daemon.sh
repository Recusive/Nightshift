#!/bin/bash
# ----------------------------------------------
# Nightshift Daemon -- Self-Improving Loop
#
# Usage:
#   ./scripts/daemon.sh                    # interactive setup (prompts for agent + duration)
#   ./scripts/daemon.sh codex              # codex agent
#   ./scripts/daemon.sh claude 120         # 120s pause between sessions
#   ./scripts/daemon.sh claude 60 10       # stop after 10 sessions
#
# Budget: set NIGHTSHIFT_BUDGET=50 to stop after $50 spent
#
# Stop: Ctrl+C or kill the process
# ----------------------------------------------

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib-agent.sh"
if [ $# -eq 0 ]; then
    PAUSE=60
    interactive_setup "builder daemon"
    # BUDGET set by interactive_setup
else
    AGENT="${1:-claude}"
    PAUSE="${2:-60}"
    MAX_SESSIONS="${3:-0}"
    BUDGET="${NIGHTSHIFT_BUDGET:-0}"
fi
KEEP_LOGS="${NIGHTSHIFT_KEEP_LOGS:-7}"
KEEP_HEALER_ENTRIES="${NIGHTSHIFT_KEEP_HEALER_ENTRIES:-50}"
LOG_DIR="$REPO_DIR/docs/sessions"
INDEX_FILE="$LOG_DIR/index.md"
AUTO_PREFIX="$REPO_DIR/docs/prompt/evolve-auto.md"
UNIFIED_PROMPT="$REPO_DIR/docs/prompt/unified.md"
EVOLVE_PROMPT="$REPO_DIR/docs/prompt/evolve.md"
PENTEST_PROMPT_FILE="$REPO_DIR/docs/prompt/pentest.md"
LOCKFILE="$REPO_DIR/.nightshift-daemon.lock"
PROMPT_ALERT="$LOG_DIR/prompt-alert.md"
COST_FILE="$LOG_DIR/costs.json"
MAX_TURNS=500
PENTEST_MAX_TURNS="${NIGHTSHIFT_PENTEST_MAX_TURNS:-120}"
CYCLE=0
CONSECUTIVE_FAILURES=0
MAX_CONSECUTIVE_FAILURES=3

mkdir -p "$LOG_DIR"

# --- Lock (portable, works on macOS + Linux) ---
if [ -d "$LOCKFILE" ]; then
    echo "ERROR: Another daemon may be running (lockdir: $LOCKFILE)"
    echo "If no other daemon is running, remove it: rmdir $LOCKFILE"
    exit 1
fi
if ! mkdir "$LOCKFILE" 2>/dev/null; then
    echo "ERROR: Could not acquire lock (lockdir: $LOCKFILE)"
    exit 1
fi

cleanup() {
    rmdir "$LOCKFILE" 2>/dev/null || true
    echo "Lock released. Daemon stopped."
}
trap cleanup EXIT INT TERM

echo "Lock acquired. PID $$."

# --- Session index header ---
if [ ! -f "$INDEX_FILE" ]; then
    {
        echo "# Session Index"
        echo ""
        echo "| Timestamp | Session | Role | Exit | Duration | Cost | Status | Feature | PR |"
        echo "|-----------|---------|------|------|----------|------|--------|---------|-----|"
    } > "$INDEX_FILE"
fi

build_prompt() {
    cat "$AUTO_PREFIX"
    cat "$UNIFIED_PROMPT"
}

build_pentest_prompt() {
    cat "$PENTEST_PROMPT_FILE"
}

reset_repo_state() {
    git fetch origin --quiet 2>/dev/null || true
    git checkout main --quiet 2>/dev/null || true
    git reset --hard origin/main --quiet 2>/dev/null || true
    git clean -fd --quiet 2>/dev/null || true
}

echo ""
echo "=================================================="
echo "  NIGHTSHIFT DAEMON"
echo "  Agent:       $AGENT"
echo "  Pentest:     ${NIGHTSHIFT_PENTEST_AGENT:-$AGENT} (${PENTEST_MAX_TURNS} turns)"
echo "  Pause:       ${PAUSE}s between sessions"
if [ "$MAX_SESSIONS" -gt 0 ]; then
    echo "  Max sessions: $MAX_SESSIONS"
else
    echo "  Max sessions: unlimited"
fi
if [ "$BUDGET" != "0" ]; then
    echo "  Budget:      \$$BUDGET"
else
    echo "  Budget:      unlimited"
fi
echo "  Circuit:     stops after $MAX_CONSECUTIVE_FAILURES consecutive failures"
echo "  Logs:        $LOG_DIR"
echo "  Stop:        Ctrl+C"
echo "=================================================="
echo ""

while true; do
    # --- Check session limit ---
    if [ "$MAX_SESSIONS" -gt 0 ] && [ "$CYCLE" -ge "$MAX_SESSIONS" ]; then
        echo "Reached max sessions ($MAX_SESSIONS). Stopping."
        break
    fi

    CYCLE=$((CYCLE + 1))
    SESSION_ID=$(date +%Y%m%d-%H%M%S)
    LOG_FILE="$LOG_DIR/$SESSION_ID.log"
    START_TIME=$(date +%s)

    echo "-- Session $CYCLE --- $(date '+%H:%M') --- $SESSION_ID --"

    # --- Clean slate: hard reset to origin/main ---
    cd "$REPO_DIR"
    reset_repo_state

    # --- Hot reload: re-source lib-agent.sh to pick up new functions ---
    source "$SCRIPT_DIR/lib-agent.sh"

    # --- Self-restart: if daemon.sh changed, exec into new version ---
    NEW_HASH=$(md5 -q "$SCRIPT_DIR/daemon.sh" 2>/dev/null || md5sum "$SCRIPT_DIR/daemon.sh" 2>/dev/null | cut -d' ' -f1)
    if [ -n "${_DAEMON_HASH:-}" ] && [ "$NEW_HASH" != "$_DAEMON_HASH" ]; then
        echo "  daemon.sh changed on main -- restarting with new code..."
        exec bash "$SCRIPT_DIR/daemon.sh" "$AGENT" "$PAUSE" "$MAX_SESSIONS"
    fi
    export _DAEMON_HASH="$NEW_HASH"

    # --- Housekeeping: rotate old logs, prune stale branches, compact handoffs, archive tasks, sync issues ---
    cleanup_old_logs "$LOG_DIR" "$KEEP_LOGS"
    cleanup_healer_log "$REPO_DIR/docs/healer/log.md" "$KEEP_HEALER_ENTRIES"
    cleanup_orphan_branches
    compact_handoffs "$REPO_DIR/docs/handoffs"
    archive_done_tasks "$REPO_DIR/docs/tasks"
    sync_github_tasks "$REPO_DIR/docs/tasks"

    # --- Check for open PRs from previous sessions ---
    OPEN_PR=""
    OPEN_PR_INFO=$(gh pr list --state open --json number,title,headRefName --jq '.[0] // empty' 2>/dev/null || true)
    if [ -n "$OPEN_PR_INFO" ]; then
        PR_NUM=$(echo "$OPEN_PR_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin)['number'])" 2>/dev/null || true)
        PR_TITLE=$(echo "$OPEN_PR_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin)['title'])" 2>/dev/null || true)
        PR_BRANCH=$(echo "$OPEN_PR_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin)['headRefName'])" 2>/dev/null || true)
        if [ -n "$PR_NUM" ]; then
            OPEN_PR="OPEN PR FROM PREVIOUS SESSION: PR #${PR_NUM} (${PR_TITLE}) on branch ${PR_BRANCH}. Check its CI status. If CI passes, merge it with: gh pr merge ${PR_NUM} --merge --delete-branch --admin. If CI fails, checkout the branch, fix the issue, push, and merge. Do NOT rebuild this feature from scratch."
            echo "  Found open PR #${PR_NUM}: ${PR_TITLE}"
        fi
    fi

    PENTEST_AGENT="${NIGHTSHIFT_PENTEST_AGENT:-$AGENT}"
    PENTEST_LOG_FILE="$LOG_DIR/${SESSION_ID}-pentest.log"
    PENTEST_PROMPT=$(build_pentest_prompt)

    if [ -n "$OPEN_PR" ]; then
        PENTEST_PROMPT="${OPEN_PR}

---

${PENTEST_PROMPT}"
    fi

    # --- Pentest preflight: red-team before the builder starts ---
    PENTEST_REPORT=""
    PENTEST_STATUS=""
    SNAP_DIR=$(save_prompt_snapshots "$REPO_DIR")
    echo "  Pentest preflight (${PENTEST_AGENT})..."
    run_agent "$PENTEST_AGENT" "$PENTEST_PROMPT" "$PENTEST_LOG_FILE" "$PENTEST_MAX_TURNS"
    PENTEST_EXIT_CODE=$EXIT_CODE
    if [ "$PENTEST_EXIT_CODE" -eq 0 ]; then
        PENTEST_STATUS="success"
    else
        PENTEST_STATUS="failed (exit $PENTEST_EXIT_CODE)"
    fi
    PENTEST_REPORT=$(extract_result_summary "$PENTEST_LOG_FILE")
    if ! check_prompt_integrity "$REPO_DIR" "$SNAP_DIR" "$PROMPT_ALERT"; then
        echo "  Pentest preflight modified prompt/control files; reset to origin/main and alerting builder."
    fi
    cleanup_prompt_snapshots "$SNAP_DIR"
    reset_repo_state

    # --- Force role override (env var) ---
    if [ -n "${NIGHTSHIFT_FORCE_ROLE:-}" ]; then
        echo "  FORCE_ROLE=$NIGHTSHIFT_FORCE_ROLE (overriding unified scoring)"
    fi

    # Rebuild prompt each cycle
    PROMPT=$(build_prompt)

    # --- Prompt guard: snapshot before builder cycle ---
    SNAP_DIR=$(save_prompt_snapshots "$REPO_DIR")

    # --- Prompt guard: inject alert from previous cycle or pentest preflight ---
    if [ -f "$PROMPT_ALERT" ]; then
        PROMPT="$(cat "$PROMPT_ALERT")

---

${PROMPT}"
        rm "$PROMPT_ALERT"
        echo "  Injected prompt modification alert."
    fi

    if [ -n "$OPEN_PR" ]; then
        PROMPT="${OPEN_PR}

${PROMPT}"
    fi

    if [ -n "$PENTEST_REPORT" ]; then
        PROMPT="PENTEST REPORT FROM PRE-BUILD RED TEAM (${PENTEST_STATUS})
====================================================
${PENTEST_REPORT}

Treat the Fix now / Builder handoff items above as your highest-priority internal work.
Validate them, fix what is real, and explicitly explain any false positives in the handoff.

${PROMPT}"
    else
        PROMPT="PENTEST REPORT FROM PRE-BUILD RED TEAM (${PENTEST_STATUS})
====================================================
No structured pentest report was produced. Spend a few minutes validating the most fragile
automation paths yourself before taking on lower-priority work.

${PROMPT}"
    fi

    # --- Force role override: inject at top of prompt ---
    if [ -n "${NIGHTSHIFT_FORCE_ROLE:-}" ]; then
        PROMPT="FORCED ROLE OVERRIDE: Skip unified scoring. Your role this session is ${NIGHTSHIFT_FORCE_ROLE^^}. Read the corresponding prompt file and execute immediately.

${PROMPT}"
    fi

    # --- Run the agent ---
    run_agent "$AGENT" "$PROMPT" "$LOG_FILE" "$MAX_TURNS"

    # --- Prompt guard: check for self-modification ---
    PROMPT_TAMPERED=""
    if ! check_prompt_integrity "$REPO_DIR" "$SNAP_DIR" "$PROMPT_ALERT"; then
        PROMPT_TAMPERED=" [PROMPT MODIFIED]"
    fi
    cleanup_prompt_snapshots "$SNAP_DIR"

    END_TIME=$(date +%s)
    DURATION=$(( END_TIME - START_TIME ))
    DURATION_MIN=$(( DURATION / 60 ))

    echo ""
    echo "-- Session $CYCLE done (exit: $EXIT_CODE, ${DURATION_MIN}m) --- $(date '+%H:%M') --"

    # --- Cost tracking ---
    SESSION_COST=$(PYTHONPATH="$REPO_DIR" python3 -c "
from nightshift.costs import format_session_cost, record_session_bundle, total_cost
entry = record_session_bundle(
    ['$PENTEST_LOG_FILE', '$LOG_FILE'],
    '$COST_FILE',
    '$SESSION_ID',
    '$AGENT',
    part_agents=['$PENTEST_AGENT', '$AGENT'],
)
cumulative = total_cost('$COST_FILE')
print(f\"{entry['total_cost_usd']:.4f}\")
print(f\"  Cost: \${entry['total_cost_usd']:.4f} (cumulative: \${cumulative:.2f})\")
print(format_session_cost(entry))
" 2>/dev/null || echo "0.0000")

    # First line is the numeric cost, rest is human-readable
    COST_USD=$(echo "$SESSION_COST" | head -1)
    echo "$SESSION_COST" | tail -n +2

    # --- Session index entry ---
    if [ "$EXIT_CODE" -eq 0 ]; then
        STATUS="success (pentest: ${PENTEST_STATUS})"
    else
        STATUS="failed (exit $EXIT_CODE; pentest: ${PENTEST_STATUS})"
    fi

    # Extract role from log (best-effort, works for both Claude and Codex)
    SESSION_ROLE=$(python3 -c "
import json, sys, re
for line in open('$LOG_FILE'):
    try:
        e = json.loads(line.strip())
        # Claude format
        if e.get('type') == 'assistant':
            for b in e.get('message', {}).get('content', []):
                t = b.get('text', '')
                m = re.search(r'EXECUTING ROLE:\s*(BUILD|REVIEW|OVERSEE|STRATEGIZE|ACHIEVE)', t)
                if m:
                    print(m.group(1).lower())
                    sys.exit(0)
        # Codex format
        if e.get('type') == 'item.completed':
            item = e.get('item', {})
            if item.get('type') == 'agent_message':
                t = item.get('text', '')
                m = re.search(r'EXECUTING ROLE:\s*(BUILD|REVIEW|OVERSEE|STRATEGIZE|ACHIEVE)', t)
                if m:
                    print(m.group(1).lower())
                    sys.exit(0)
    except: pass
print('build')
" 2>/dev/null || echo "build")

    # Extract feature name and PR from log (best-effort)
    FEATURE=$(python3 -c "
import json, sys
for line in open('$LOG_FILE'):
    try:
        e = json.loads(line.strip())
        if e.get('type') == 'result':
            r = e.get('result', '')
            for l in r.splitlines():
                if l.startswith('Built:'):
                    print(l.replace('Built:', '').strip()[:50])
                    sys.exit(0)
    except: pass
print('-')
" 2>/dev/null || echo "-")

    PR_URL=$(python3 -c "
import json, sys
for line in open('$LOG_FILE'):
    try:
        e = json.loads(line.strip())
        if e.get('type') == 'result':
            r = e.get('result', '')
            for l in r.splitlines():
                if l.startswith('PR:'):
                    print(l.replace('PR:', '').strip()[:60])
                    sys.exit(0)
    except: pass
print('-')
" 2>/dev/null || echo "-")

    # --- Self-evaluation check ---
    if [ "$EXIT_CODE" -eq 0 ] && should_evaluate "$CYCLE"; then
        run_evaluation "$AGENT" "$FEATURE"
    fi

    echo "| $(date '+%Y-%m-%d %H:%M') | $SESSION_ID | $SESSION_ROLE | $EXIT_CODE | ${DURATION_MIN}m | \$$COST_USD | ${STATUS}${PROMPT_TAMPERED} | $FEATURE | $PR_URL |" >> "$INDEX_FILE"

    # --- Budget check ---
    if [ "$BUDGET" != "0" ]; then
        CUMULATIVE=$(PYTHONPATH="$REPO_DIR" python3 -c "
from nightshift.costs import total_cost
print(f'{total_cost(\"$COST_FILE\"):.2f}')
" 2>/dev/null || echo "0.00")
        OVER_BUDGET=$(python3 -c "print('yes' if float('$CUMULATIVE') >= float('$BUDGET') else 'no')" 2>/dev/null || echo "no")
        if [ "$OVER_BUDGET" = "yes" ]; then
            echo ""
            echo "BUDGET LIMIT REACHED: \$$CUMULATIVE spent (limit: \$$BUDGET)"
            echo "| $(date '+%Y-%m-%d %H:%M') | BUDGET-STOP | - | - | - | \$$CUMULATIVE | Budget limit reached (\$$BUDGET) | - | - |" >> "$INDEX_FILE"
            notify_human "Budget limit reached" "Daemon stopped after spending \$$CUMULATIVE (limit: \$$BUDGET). Review spending at docs/sessions/costs.json."
            break
        fi
    fi

    # --- Circuit breaker ---
    if [ "$EXIT_CODE" -ne 0 ]; then
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        echo "Consecutive failures: $CONSECUTIVE_FAILURES / $MAX_CONSECUTIVE_FAILURES"

        if [ "$CONSECUTIVE_FAILURES" -ge "$MAX_CONSECUTIVE_FAILURES" ]; then
            echo ""
            echo "CIRCUIT BREAKER TRIPPED: $MAX_CONSECUTIVE_FAILURES consecutive failures."
            echo "Something is fundamentally broken. Check the logs:"
            echo "  $LOG_DIR"
            echo ""
            echo "| $(date '+%Y-%m-%d %H:%M') | CIRCUIT-BREAK | - | - | - | - | Stopped after $MAX_CONSECUTIVE_FAILURES consecutive failures | - | - |" >> "$INDEX_FILE"
            notify_human "Circuit breaker tripped" "Builder daemon stopped after $MAX_CONSECUTIVE_FAILURES consecutive failures. Check logs in $LOG_DIR."
            break
        fi

        echo "Waiting 120s before retry."
        sleep 120
    else
        CONSECUTIVE_FAILURES=0
        echo "Session complete. Next in ${PAUSE}s."
        sleep "$PAUSE"
    fi
done

echo ""
echo "=================================================="
echo "  DAEMON STOPPED"
echo "  Sessions run: $CYCLE"
echo "  Index:        $INDEX_FILE"
echo "=================================================="
