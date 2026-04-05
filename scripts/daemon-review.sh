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
else
    AGENT="${1:-claude}"
    PAUSE="${2:-60}"
    MAX_SESSIONS="${3:-0}"
fi
LOG_DIR="$REPO_DIR/docs/sessions"
INDEX_FILE="$LOG_DIR/index-review.md"
REVIEW_PROMPT="$REPO_DIR/docs/prompt/review.md"
LOCKFILE="$REPO_DIR/.nightshift-daemon.lock"
PROMPT_ALERT="$LOG_DIR/prompt-alert.md"
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
        echo "| Timestamp | Session | Exit | Duration | File Reviewed |"
        echo "|-----------|---------|------|----------|---------------|"
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
    echo "| $(date '+%Y-%m-%d %H:%M') | $SESSION_ID | $EXIT_CODE | ${DURATION_MIN}m | ${REVIEWED}${PROMPT_TAMPERED} |" >> "$INDEX_FILE"

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
