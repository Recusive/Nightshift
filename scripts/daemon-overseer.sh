#!/bin/bash
# ──────────────────────────────────────────────
# Nightshift Overseer -- System Health Loop
#
# Audits the task queue, handoffs, learnings, and
# direction. Fixes systemic issues the builder can't see.
#
# Usage:
#   ./scripts/daemon-overseer.sh              # claude, 120s pause, unlimited
#   ./scripts/daemon-overseer.sh codex        # codex agent
#   ./scripts/daemon-overseer.sh claude 300   # 5min pause between audits
#   ./scripts/daemon-overseer.sh claude 120 5 # stop after 5 audits
#
# Stop: Ctrl+C or kill the process
# Shares lockfile with other daemons -- only one runs at a time.
# ──────────────────────────────────────────────

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib-agent.sh"
AGENT="${1:-claude}"
PAUSE="${2:-120}"
MAX_SESSIONS="${3:-0}"
LOG_DIR="$REPO_DIR/docs/sessions"
INDEX_FILE="$LOG_DIR/index-overseer.md"
OVERSEER_PROMPT="$REPO_DIR/docs/prompt/overseer.md"
LOCKFILE="$REPO_DIR/.nightshift-daemon.lock"
MAX_TURNS=200
CYCLE=0
CONSECUTIVE_FAILURES=0
MAX_CONSECUTIVE_FAILURES=3

mkdir -p "$LOG_DIR"

# --- Lock (shared with other daemons) ---
if [ -d "$LOCKFILE" ]; then
    echo "ERROR: Another daemon is already running."
    echo "If not, remove: rmdir $LOCKFILE"
    exit 1
fi
if ! mkdir "$LOCKFILE" 2>/dev/null; then
    echo "ERROR: Could not acquire lock."
    exit 1
fi

cleanup() {
    rmdir "$LOCKFILE" 2>/dev/null || true
    echo "Lock released. Overseer stopped."
}
trap cleanup EXIT INT TERM

echo "Lock acquired. PID $$."

# --- Session index header ---
if [ ! -f "$INDEX_FILE" ]; then
    {
        echo "# Overseer Audit Index"
        echo ""
        echo "| Timestamp | Session | Exit | Duration | Issue Fixed |"
        echo "|-----------|---------|------|----------|-------------|"
    } > "$INDEX_FILE"
fi

echo ""
echo "=================================================="
echo "  NIGHTSHIFT OVERSEER"
echo "  Agent:       $AGENT"
echo "  Pause:       ${PAUSE}s between audits"
if [ "$MAX_SESSIONS" -gt 0 ]; then
    echo "  Max audits:  $MAX_SESSIONS"
else
    echo "  Max audits:  unlimited"
fi
echo "  Circuit:     stops after $MAX_CONSECUTIVE_FAILURES consecutive failures"
echo "  Logs:        $LOG_DIR"
echo "  Stop:        Ctrl+C"
echo "=================================================="
echo ""

while true; do
    # --- Check session limit ---
    if [ "$MAX_SESSIONS" -gt 0 ] && [ "$CYCLE" -ge "$MAX_SESSIONS" ]; then
        echo "Reached max audits ($MAX_SESSIONS). Stopping."
        break
    fi

    CYCLE=$((CYCLE + 1))
    SESSION_ID="overseer-$(date +%Y%m%d-%H%M%S)"
    LOG_FILE="$LOG_DIR/$SESSION_ID.log"
    START_TIME=$(date +%s)

    echo "-- Audit $CYCLE --- $(date '+%H:%M') --- $SESSION_ID --"

    # --- Clean slate ---
    cd "$REPO_DIR"
    git fetch origin --quiet 2>/dev/null || true
    git checkout main --quiet 2>/dev/null || true
    git reset --hard origin/main --quiet 2>/dev/null || true
    git clean -fd --quiet 2>/dev/null || true

    # Read prompt fresh each cycle
    PROMPT=$(cat "$OVERSEER_PROMPT")

    # --- Run the agent ---
    run_agent "$AGENT" "$PROMPT" "$LOG_FILE" "$MAX_TURNS"

    END_TIME=$(date +%s)
    DURATION=$(( END_TIME - START_TIME ))
    DURATION_MIN=$(( DURATION / 60 ))

    echo ""
    echo "-- Audit $CYCLE done (exit: $EXIT_CODE, ${DURATION_MIN}m) --- $(date '+%H:%M') --"

    # --- Extract what was fixed from log ---
    FIXED=$(python3 -c "
import json, sys
for line in open('$LOG_FILE'):
    try:
        e = json.loads(line.strip())
        if e.get('type') == 'result':
            r = e.get('result', '')
            for l in r.splitlines():
                if l.startswith('Fixed:'):
                    print(l.replace('Fixed:', '').strip()[:60])
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
    echo "| $(date '+%Y-%m-%d %H:%M') | $SESSION_ID | $EXIT_CODE | ${DURATION_MIN}m | $FIXED |" >> "$INDEX_FILE"

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
        echo "Audit complete. Next in ${PAUSE}s."
        sleep "$PAUSE"
    fi
done

echo ""
echo "=================================================="
echo "  OVERSEER STOPPED"
echo "  Audits run: $CYCLE"
echo "  Index:      $INDEX_FILE"
echo "=================================================="
