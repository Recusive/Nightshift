#!/bin/bash
# ──────────────────────────────────────────────
# Nightshift Daemon -- Self-Improving Loop
#
# Usage:
#   ./scripts/daemon.sh                    # claude, 60s pause, unlimited
#   ./scripts/daemon.sh codex              # codex agent
#   ./scripts/daemon.sh claude 120         # 120s pause between sessions
#   ./scripts/daemon.sh claude 60 10       # stop after 10 sessions
#
# Stop: Ctrl+C or kill the process
# ──────────────────────────────────────────────

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENT="${1:-claude}"
PAUSE="${2:-60}"
MAX_SESSIONS="${3:-0}"
LOG_DIR="$REPO_DIR/docs/sessions"
INDEX_FILE="$LOG_DIR/index.md"
AUTO_PREFIX="$REPO_DIR/docs/prompt/evolve-auto.md"
EVOLVE_PROMPT="$REPO_DIR/docs/prompt/evolve.md"
LOCKFILE="$REPO_DIR/.nightshift-daemon.lock"
MAX_TURNS=100
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
        echo "| Timestamp | Session | Exit | Duration | Status |"
        echo "|-----------|---------|------|----------|--------|"
    } > "$INDEX_FILE"
fi

build_prompt() {
    cat "$AUTO_PREFIX"
    cat "$EVOLVE_PROMPT"
}

echo ""
echo "=================================================="
echo "  NIGHTSHIFT DAEMON"
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
    SESSION_ID=$(date +%Y%m%d-%H%M%S)
    LOG_FILE="$LOG_DIR/$SESSION_ID.log"
    START_TIME=$(date +%s)

    echo "-- Session $CYCLE --- $(date '+%H:%M') --- $SESSION_ID --"

    # --- Clean slate: hard reset to origin/main ---
    cd "$REPO_DIR"
    git fetch origin --quiet 2>/dev/null || true
    git checkout main --quiet 2>/dev/null || true
    git reset --hard origin/main --quiet 2>/dev/null || true
    git clean -fd --quiet 2>/dev/null || true

    # Rebuild prompt each cycle
    PROMPT=$(build_prompt)

    # --- Run the agent ---
    # Use stream-json for line-by-line event output so tee flushes in real-time.
    # Each line is a JSON event (tool calls, messages, results) that can be
    # monitored by reading the log file while the session is running.
    set +e
    if [ "$AGENT" = "codex" ]; then
        codex exec \
            --json \
            -c 'approval_policy="never"' \
            -s "workspace-write" \
            "$PROMPT" \
            2>&1 | tee "$LOG_FILE"
        EXIT_CODE=${PIPESTATUS[0]}
    else
        claude -p "$PROMPT" \
            --max-turns "$MAX_TURNS" \
            --output-format stream-json \
            --verbose \
            2>&1 | tee "$LOG_FILE"
        EXIT_CODE=${PIPESTATUS[0]}
    fi
    set -e

    END_TIME=$(date +%s)
    DURATION=$(( END_TIME - START_TIME ))
    DURATION_MIN=$(( DURATION / 60 ))

    echo ""
    echo "-- Session $CYCLE done (exit: $EXIT_CODE, ${DURATION_MIN}m) --- $(date '+%H:%M') --"

    # --- Session index entry ---
    if [ "$EXIT_CODE" -eq 0 ]; then
        STATUS="success"
    else
        STATUS="failed (exit $EXIT_CODE)"
    fi
    echo "| $(date '+%Y-%m-%d %H:%M') | $SESSION_ID | $EXIT_CODE | ${DURATION_MIN}m | $STATUS |" >> "$INDEX_FILE"

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
            echo "| $(date '+%Y-%m-%d %H:%M') | CIRCUIT-BREAK | - | - | Stopped after $MAX_CONSECUTIVE_FAILURES consecutive failures |" >> "$INDEX_FILE"
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
