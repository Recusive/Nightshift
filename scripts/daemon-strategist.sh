#!/bin/bash
# ----------------------------------------------
# Nightshift Strategist -- Big Picture Review
#
# Unlike the other daemons, this one runs ONCE.
# It reviews what's happened, produces a strategy report,
# and presents it to the human for decisions.
#
# Run it when you want to check on the system:
#   ./scripts/daemon-strategist.sh           # interactive setup (prompts for agent)
#   ./scripts/daemon-strategist.sh codex     # skip prompts, use codex
#
# It does NOT loop. It does NOT build. It advises.
# ----------------------------------------------

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib-agent.sh"
if [ $# -eq 0 ]; then
    interactive_setup_strategist
else
    AGENT="${1:-claude}"
fi
LOG_DIR="$REPO_DIR/docs/sessions"
STRATEGIST_PROMPT="$REPO_DIR/docs/prompt/strategist.md"
PROMPT_ALERT="$LOG_DIR/prompt-alert.md"
MAX_TURNS=200

mkdir -p "$LOG_DIR"

SESSION_ID="strategist-$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/$SESSION_ID.log"

echo ""
echo "=================================================="
echo "  NIGHTSHIFT STRATEGIST"
echo "  Agent:  $AGENT"
echo "  Mode:   single run (interactive)"
echo "=================================================="
echo ""

cd "$REPO_DIR"
git checkout main --quiet 2>/dev/null || true
git pull origin main --quiet 2>/dev/null || true

# --- Prompt guard: snapshot before run ---
SNAP_DIR=$(save_prompt_snapshots "$REPO_DIR")

PROMPT=$(cat "$STRATEGIST_PROMPT")

# --- Prompt guard: inject alert from previous session ---
if [ -f "$PROMPT_ALERT" ]; then
    PROMPT="$(cat "$PROMPT_ALERT")

---

${PROMPT}"
    rm "$PROMPT_ALERT"
    echo "  Injected prompt modification alert from previous session."
fi

run_agent "$AGENT" "$PROMPT" "$LOG_FILE" "$MAX_TURNS"

# --- Prompt guard: check for self-modification ---
if ! check_prompt_integrity "$REPO_DIR" "$SNAP_DIR" "$PROMPT_ALERT"; then
    echo "WARNING: Strategist modified prompt files. See alert above."
fi
cleanup_prompt_snapshots "$SNAP_DIR"

echo ""
echo "=================================================="
echo "  STRATEGIST COMPLETE"
echo "  Report: docs/strategy/$(date +%Y-%m-%d).md"
echo "  Log:    $LOG_FILE"
echo "=================================================="
