#!/bin/bash
# ──────────────────────────────────────────────
# Nightshift Review Daemon -- Code Quality Loop
#
# Separate from the feature daemon. This one reads code
# file by file and makes it better. No features, just quality.
#
# Usage:
#   ./scripts/daemon-review.sh              # interactive setup (prompts for agent + duration)
#   ./scripts/daemon-review.sh codex        # codex agent
#   ./scripts/daemon-review.sh claude 120   # 120s pause
#   ./scripts/daemon-review.sh claude 60 10 # stop after 10 sessions
#
# Budget: set NIGHTSHIFT_BUDGET=50 to stop after $50 spent
#
# Stop: Ctrl+C or kill the process
# Cannot run simultaneously with daemon.sh (shared lockfile).
# ──────────────────────────────────────────────

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib-agent.sh"
if [ $# -eq 0 ]; then
    PAUSE=60
    interactive_setup "review daemon"
    # BUDGET set by interactive_setup
else
    AGENT="${1:-claude}"
    PAUSE="${2:-60}"
    MAX_SESSIONS="${3:-0}"
    BUDGET="${NIGHTSHIFT_BUDGET:-0}"
fi
KEEP_LOGS="${NIGHTSHIFT_KEEP_LOGS:-7}"
LOG_DIR="$REPO_DIR/docs/sessions"
INDEX_FILE="$LOG_DIR/index-review.md"
REVIEW_PROMPT="$REPO_DIR/docs/prompt/review.md"
LOCKFILE="$REPO_DIR/.nightshift-daemon.lock"
PROMPT_ALERT="$LOG_DIR/prompt-alert.md"
COST_FILE="$LOG_DIR/costs.json"
MAX_TURNS=200
CYCLE=0
CONSECUTIVE_FAILURES=0
MAX_CONSECUTIVE_FAILURES=3

mkdir -p "$LOG_DIR"

# --- Lock (shared with daemon.sh -- prevents both running) ---
if [ -d "$LOCKFILE" ]; then
    echo "ERROR: Another daemon (build or review) is already running."
    echo "If not, remove: rmdir $LOCKFILE"
    exit 1
fi
if ! mkdir "$LOCKFILE" 2>/dev/null; then
    echo "ERROR: Could not acquire lock."
    exit 1
fi

cleanup() {
    rmdir "$LOCKFILE" 2>/dev/null || true
    echo "Lock released. Review daemon stopped."
}
trap cleanup EXIT INT TERM

echo "Lock acquired. PID $$."

# --- Session index header ---
if [ ! -f "$INDEX_FILE" ]; then
    {
        echo "# Review Session Index"
        echo ""
        echo "| Timestamp | Session | Exit | Duration | Cost | File Reviewed |"
        echo "|-----------|---------|------|----------|------|---------------|"
    } > "$INDEX_FILE"
fi

echo ""
echo "=================================================="
echo "  NIGHTSHIFT REVIEW DAEMON"
echo "  Agent:       $AGENT"
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
    SESSION_ID="review-$(date +%Y%m%d-%H%M%S)"
    LOG_FILE="$LOG_DIR/$SESSION_ID.log"
    START_TIME=$(date +%s)

    echo "-- Review $CYCLE --- $(date '+%H:%M') --- $SESSION_ID --"

    # --- Clean slate ---
    cd "$REPO_DIR"
    git fetch origin --quiet 2>/dev/null || true
    git checkout main --quiet 2>/dev/null || true
    git reset --hard origin/main --quiet 2>/dev/null || true
    git clean -fd --quiet 2>/dev/null || true

    # --- Housekeeping: rotate old logs, prune stale branches ---
    cleanup_old_logs "$LOG_DIR" "$KEEP_LOGS"
    cleanup_orphan_branches

    # --- Prompt guard: snapshot before cycle ---
    SNAP_DIR=$(save_prompt_snapshots "$REPO_DIR")

    # Read prompt fresh each cycle
    PROMPT=$(cat "$REVIEW_PROMPT")

    # --- Prompt guard: inject alert from previous cycle ---
    if [ -f "$PROMPT_ALERT" ]; then
        PROMPT="$(cat "$PROMPT_ALERT")

---

${PROMPT}"
        rm "$PROMPT_ALERT"
        echo "  Injected prompt modification alert from previous cycle."
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
    echo "-- Review $CYCLE done (exit: $EXIT_CODE, ${DURATION_MIN}m) --- $(date '+%H:%M') --"

    # --- Cost tracking ---
    SESSION_COST=$(PYTHONPATH="$REPO_DIR" python3 -c "
from nightshift.costs import record_session, format_session_cost, total_cost
entry = record_session('$LOG_FILE', '$COST_FILE', '$SESSION_ID', '$AGENT')
cumulative = total_cost('$COST_FILE')
print(f\"{entry['total_cost_usd']:.4f}\")
print(f\"  Cost: \${entry['total_cost_usd']:.4f} (cumulative: \${cumulative:.2f})\")
print(format_session_cost(entry))
" 2>/dev/null || echo "0.0000")

    COST_USD=$(echo "$SESSION_COST" | head -1)
    echo "$SESSION_COST" | tail -n +2

    # --- Extract reviewed file from log (best-effort) ---
    REVIEWED=$(python3 -c "
import json, sys
for line in open('$LOG_FILE'):
    try:
        e = json.loads(line.strip())
        if e.get('type') == 'result':
            r = e.get('result', '')
            for l in r.splitlines():
                if 'Review:' in l or 'nightshift/' in l:
                    print(l.strip()[:60])
                    sys.exit(0)
    except: pass
print('-')
" 2>/dev/null || echo "-")

    # --- Session index entry ---
    if [ "$EXIT_CODE" -eq 0 ]; then
        ST="success"
    else
        ST="failed"
    fi
    echo "| $(date '+%Y-%m-%d %H:%M') | $SESSION_ID | $EXIT_CODE | ${DURATION_MIN}m | \$$COST_USD | ${REVIEWED}${PROMPT_TAMPERED} |" >> "$INDEX_FILE"

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
            echo "| $(date '+%Y-%m-%d %H:%M') | BUDGET-STOP | - | - | \$$CUMULATIVE | Budget limit reached (\$$BUDGET) |" >> "$INDEX_FILE"
            break
        fi
    fi

    # --- Circuit breaker ---
    if [ "$EXIT_CODE" -ne 0 ]; then
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        echo "Consecutive failures: $CONSECUTIVE_FAILURES / $MAX_CONSECUTIVE_FAILURES"

        if [ "$CONSECUTIVE_FAILURES" -ge "$MAX_CONSECUTIVE_FAILURES" ]; then
            echo ""
            echo "CIRCUIT BREAKER: $MAX_CONSECUTIVE_FAILURES consecutive failures."
            echo "| $(date '+%Y-%m-%d %H:%M') | CIRCUIT-BREAK | - | - | Stopped |" >> "$INDEX_FILE"
            break
        fi

        sleep 120
    else
        CONSECUTIVE_FAILURES=0
        echo "Review complete. Next in ${PAUSE}s."
        sleep "$PAUSE"
    fi
done

echo ""
echo "=================================================="
echo "  REVIEW DAEMON STOPPED"
echo "  Sessions run: $CYCLE"
echo "  Index:        $INDEX_FILE"
echo "=================================================="
