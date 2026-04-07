#!/bin/bash
# ----------------------------------------------
# Recursive Watchdog
#
# Keeps the daemon running forever. If it crashes,
# cleans up and restarts. Designed to run via:
#
#   caffeinate -s bash Recursive/engine/watchdog.sh codex 60
#
# Or in tmux:
#   tmux new-session -d -s recursive "caffeinate -s bash Recursive/engine/watchdog.sh codex 60"
#
# The watchdog never exits unless you kill it.
# The daemon inside it handles its own circuit breaker,
# budget limits, and session caps.
# ----------------------------------------------

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RECURSIVE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$RECURSIVE_DIR/.." && pwd)"
LOCKFILE="$REPO_DIR/.recursive-daemon.lock"

AGENT="${1:-codex}"
PAUSE="${2:-60}"
RESTART_DELAY=30
MAX_RESTARTS_PER_HOUR=5
RESTART_COUNT=0
LAST_RESET_TIME=$(date +%s)

echo "=================================================="
echo "  RECURSIVE WATCHDOG"
echo "  Agent:         $AGENT"
echo "  Pause:         ${PAUSE}s"
echo "  Restart delay: ${RESTART_DELAY}s"
echo "  Max restarts:  $MAX_RESTARTS_PER_HOUR per hour"
echo "  Stop:          Ctrl+C"
echo "=================================================="
echo ""

while true; do
    # --- Rate limit restarts ---
    NOW=$(date +%s)
    ELAPSED=$(( NOW - LAST_RESET_TIME ))
    if [ "$ELAPSED" -ge 3600 ]; then
        RESTART_COUNT=0
        LAST_RESET_TIME=$NOW
    fi

    if [ "$RESTART_COUNT" -ge "$MAX_RESTARTS_PER_HOUR" ]; then
        echo "WATCHDOG: $MAX_RESTARTS_PER_HOUR restarts in the last hour. Something is fundamentally broken."
        echo "WATCHDOG: Sleeping 1 hour before retrying."
        sleep 3600
        RESTART_COUNT=0
        LAST_RESET_TIME=$(date +%s)
    fi

    # --- Clean stale lock ---
    if [ -d "$LOCKFILE" ]; then
        echo "WATCHDOG: Cleaning stale lock from previous crash."
        rmdir "$LOCKFILE" 2>/dev/null || true
    fi

    # --- Run the daemon ---
    echo "WATCHDOG: Starting daemon (attempt $((RESTART_COUNT + 1))) --- $(date '+%Y-%m-%d %H:%M:%S') ---"
    bash "$SCRIPT_DIR/daemon.sh" "$AGENT" "$PAUSE"
    EXIT_CODE=$?

    RESTART_COUNT=$((RESTART_COUNT + 1))

    if [ "$EXIT_CODE" -eq 0 ]; then
        echo "WATCHDOG: Daemon exited cleanly (exit 0). Restarting in ${RESTART_DELAY}s."
    else
        echo "WATCHDOG: Daemon crashed (exit $EXIT_CODE). Restarting in ${RESTART_DELAY}s."
    fi

    sleep "$RESTART_DELAY"
done
