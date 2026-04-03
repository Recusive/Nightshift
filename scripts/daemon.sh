#!/bin/bash
# ──────────────────────────────────────────────
# Nightshift Daemon — Self-Improving Loop
#
# Runs the evolve prompt in a continuous loop.
# Each cycle is a fresh Claude session that:
#   reads handoff -> picks highest priority -> builds -> tests -> pushes -> merges
#
# Usage:
#   ./scripts/daemon.sh              # run forever with claude
#   ./scripts/daemon.sh codex        # run forever with codex
#   ./scripts/daemon.sh claude 120   # 120s pause between sessions
#
# Stop: Ctrl+C or kill the process
# ──────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENT="${1:-claude}"
PAUSE="${2:-60}"
LOG_DIR="$REPO_DIR/docs/sessions"
AUTO_PREFIX="$REPO_DIR/docs/prompt/evolve-auto.md"
EVOLVE_PROMPT="$REPO_DIR/docs/prompt/evolve.md"
MAX_TURNS=100
CYCLE=0

mkdir -p "$LOG_DIR"

build_prompt() {
    cat "$AUTO_PREFIX"
    cat "$EVOLVE_PROMPT"
}

echo ""
echo "=================================================="
echo "  NIGHTSHIFT DAEMON"
echo "  Agent:  $AGENT"
echo "  Pause:  ${PAUSE}s between sessions"
echo "  Logs:   $LOG_DIR"
echo "  Stop:   Ctrl+C"
echo "=================================================="
echo ""

while true; do
    CYCLE=$((CYCLE + 1))
    SESSION_ID=$(date +%Y%m%d-%H%M%S)
    LOG_FILE="$LOG_DIR/$SESSION_ID.log"

    echo "-- Session $CYCLE --- $(date '+%H:%M') --- $SESSION_ID --"

    cd "$REPO_DIR"
    git checkout main --quiet 2>/dev/null || true
    git pull origin main --quiet 2>/dev/null || true

    # Rebuild prompt each cycle so it picks up any changes from previous sessions
    PROMPT=$(build_prompt)

    if [ "$AGENT" = "codex" ]; then
        codex exec \
            --json \
            -c 'approval_policy="never"' \
            -s "workspace-write" \
            "$PROMPT" \
            2>&1 | tee "$LOG_FILE"
    else
        claude -p "$PROMPT" \
            --max-turns "$MAX_TURNS" \
            --verbose \
            2>&1 | tee "$LOG_FILE"
    fi

    EXIT_CODE=$?

    echo ""
    echo "-- Session $CYCLE done (exit: $EXIT_CODE) --- $(date '+%H:%M') --"

    if [ $EXIT_CODE -ne 0 ]; then
        echo "Session failed. Waiting 120s before retry."
        sleep 120
    else
        echo "Session complete. Next in ${PAUSE}s."
        sleep "$PAUSE"
    fi
done
