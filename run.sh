#!/bin/bash
# ──────────────────────────────────────────────
# Nightshift Runner (Worktree Edition)
# Runs nightshift in an isolated git worktree.
# Your main working directory is never touched.
#
# Usage:
#   ./run.sh                  # 8 hours (default)
#   ./run.sh 10               # 10 hours
#   ./run.sh 6 45             # 6 hours, 45 min per cycle
# ──────────────────────────────────────────────

set -e

HOURS="${1:-8}"
CYCLE_MINUTES="${2:-30}"
TODAY=$(date +%Y-%m-%d)
START_TIME=$(date +%s)
END_TIME=$((START_TIME + HOURS * 3600))
CYCLE=0

REPO_DIR="$PWD"
REPO_NAME=$(basename "$REPO_DIR")
WORKTREE_DIR="${REPO_DIR}/docs/Nightshift/worktree-${TODAY}"
BRANCH="nightshift/${TODAY}"
SHIFT_LOG="docs/Nightshift/${TODAY}.md"
RUNNER_LOG="docs/Nightshift/${TODAY}-runner.log"

# ── Set up worktree ──────────────────────────
if [ -d "$WORKTREE_DIR" ]; then
    echo "Resuming existing worktree at: $WORKTREE_DIR"
else
    echo "Creating worktree at: $WORKTREE_DIR"
    git worktree add "$WORKTREE_DIR" -b "$BRANCH" 2>/dev/null || \
    git worktree add "$WORKTREE_DIR" "$BRANCH"
fi

# Install dependencies in worktree if needed
if [ -f "$WORKTREE_DIR/package.json" ]; then
    echo "Installing dependencies in worktree..."
    cd "$WORKTREE_DIR" && bun install --frozen-lockfile 2>/dev/null || npm install 2>/dev/null || true
fi

mkdir -p "$WORKTREE_DIR/docs/Nightshift"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║         NIGHTSHIFT STARTING                      ║"
echo "║                                                  ║"
echo "║  Duration:   ${HOURS} hours                              ║"
echo "║  Cycle:      ${CYCLE_MINUTES} min per session                     ║"
echo "║  Worktree:   ${WORKTREE_DIR}  ║"
echo "║  Branch:     ${BRANCH}                    ║"
echo "║  Started:    $(date '+%H:%M')                               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

while [ "$(date +%s)" -lt "$END_TIME" ]; do
    CYCLE=$((CYCLE + 1))
    REMAINING=$(( (END_TIME - $(date +%s)) / 60 ))

    echo "── Cycle ${CYCLE} ─── $(date '+%H:%M') ─── ${REMAINING} min remaining ──"

    if [ "$CYCLE" -eq 1 ]; then
        PROMPT="Run /nightshift on this codebase. You are already inside the nightshift worktree — do NOT create a new worktree or switch branches. This is the start of an overnight shift. Do reconnaissance, then start the discovery-fix-document loop. Work for about ${CYCLE_MINUTES} minutes worth of fixes, then wrap up this cycle cleanly — update the shift log stats and make a final commit. Do NOT write a Summary or Recommendations yet — there are more cycles coming."
    else
        PROMPT="Run /nightshift on this codebase. You are already inside the nightshift worktree — do NOT create a new worktree or switch branches. This is cycle ${CYCLE} of an ongoing overnight shift. Read the existing shift log at ${SHIFT_LOG} to see what's been done so far. CONTINUE from where the last cycle left off — pick different files and strategies than what's already in the log. Work for about ${CYCLE_MINUTES} minutes worth of fixes, then wrap up this cycle cleanly — update the shift log stats and commit. Do NOT write a Summary or Recommendations yet unless fewer than 30 minutes remain in the shift."
    fi

    # Add wrap-up instructions for the last cycle
    if [ "$REMAINING" -lt "$((CYCLE_MINUTES + 10))" ]; then
        PROMPT="Run /nightshift on this codebase. You are already inside the nightshift worktree — do NOT create a new worktree or switch branches. This is the FINAL cycle of an overnight shift. Read the existing shift log at ${SHIFT_LOG}. Your PRIORITY this cycle is wrapping up the shift log — do 1-2 more fixes if quick, but focus on: (1) REWRITE the Summary paragraph to reflect the ENTIRE shift across all cycles — what areas were explored, most impactful fixes, what needs attention. (2) Add or update Recommendations. (3) Make sure all fix entries have correct commit hashes. (4) Update final stats. (5) Run the test suite one last time. (6) Final commit with the completed log. The day team reads this first thing — make it worth their time."
    fi

    # Run Claude from INSIDE the worktree
    cd "$WORKTREE_DIR"
    claude -p "$PROMPT" --max-turns 50 --verbose 2>&1 | tee -a "$WORKTREE_DIR/$RUNNER_LOG"

    EXIT_CODE=$?

    # Copy shift log back to main repo after each cycle
    mkdir -p "$REPO_DIR/docs/Nightshift"
    if [ -f "$WORKTREE_DIR/$SHIFT_LOG" ]; then
        cp "$WORKTREE_DIR/$SHIFT_LOG" "$REPO_DIR/$SHIFT_LOG"
    fi
    if [ -f "$WORKTREE_DIR/$RUNNER_LOG" ]; then
        cp "$WORKTREE_DIR/$RUNNER_LOG" "$REPO_DIR/$RUNNER_LOG"
    fi

    if [ $EXIT_CODE -ne 0 ]; then
        echo ""
        echo "⚠ Cycle ${CYCLE} exited with code ${EXIT_CODE}"
        echo "  Waiting 30s before retry..."
        sleep 30
    fi

    echo ""
    echo "── Cycle ${CYCLE} complete ─── $(date '+%H:%M') ──"
    echo ""

    sleep 10
done

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║         NIGHTSHIFT COMPLETE                      ║"
echo "║                                                  ║"
echo "║  Cycles run: ${CYCLE}                                    ║"
echo "║  Ended:      $(date '+%H:%M')                               ║"
echo "║  Worktree:   ${WORKTREE_DIR}  ║"
echo "║  Branch:     ${BRANCH}                    ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Review the shift log:"
echo "  cat ${WORKTREE_DIR}/${SHIFT_LOG}"
echo ""
echo "Review the commits:"
echo "  git log ${BRANCH} --oneline"
echo ""
echo "Merge when ready:"
echo "  cd ${REPO_DIR}"
echo "  git merge ${BRANCH}"
echo "  git worktree remove ${WORKTREE_DIR}"
