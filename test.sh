#!/bin/bash
# ──────────────────────────────────────────────
# Nightshift Test Runner — 4 short cycles
# Runs in a git worktree. Your working directory
# is never touched.
# ──────────────────────────────────────────────

set -e

CYCLES=4
TODAY=$(date +%Y-%m-%d)
REPO_DIR="$PWD"
REPO_NAME=$(basename "$REPO_DIR")
WORKTREE_DIR="${REPO_DIR}/docs/Nightshift/worktree-${TODAY}"
BRANCH="nightshift/${TODAY}"
SHIFT_LOG="docs/Nightshift/${TODAY}.md"

# ── Set up worktree ──────────────────────────
if [ -d "$WORKTREE_DIR" ]; then
    echo "Resuming existing worktree at: $WORKTREE_DIR"
else
    echo "Creating worktree at: $WORKTREE_DIR"
    git worktree add "$WORKTREE_DIR" -b "$BRANCH" 2>/dev/null || \
    git worktree add "$WORKTREE_DIR" "$BRANCH"
fi

# Install dependencies in worktree
if [ -f "$WORKTREE_DIR/package.json" ]; then
    echo "Installing dependencies in worktree..."
    cd "$WORKTREE_DIR" && bun install --frozen-lockfile 2>/dev/null || true
fi

mkdir -p "$WORKTREE_DIR/docs/Nightshift"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║     NIGHTSHIFT TEST RUN                          ║"
echo "║     ${CYCLES} cycles, ~5-10 min each                      ║"
echo "║     Worktree: ${WORKTREE_DIR}  ║"
echo "║     Started:  $(date '+%H:%M')                               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

for CYCLE in $(seq 1 $CYCLES); do
    echo "── Cycle ${CYCLE}/${CYCLES} ─── $(date '+%H:%M') ──"

    if [ "$CYCLE" -eq 1 ]; then
        PROMPT="Run /nightshift on this codebase. You are already inside the nightshift worktree — do NOT create a new worktree or switch branches. This is a SHORT test run. Follow the skill exactly: do recon, then find and fix 2-3 small issues. IMPORTANT: After EACH fix, immediately update the shift log (docs/Nightshift/${TODAY}.md) with a new entry and update the stats, then commit both the fix and the log update together. Do NOT write Summary or Recommendations yet."
    elif [ "$CYCLE" -eq "$CYCLES" ]; then
        PROMPT="Run /nightshift on this codebase. You are already inside the nightshift worktree — do NOT create a new worktree or switch branches. This is the FINAL cycle (${CYCLE}/${CYCLES}) of a test run. Read the existing shift log at ${SHIFT_LOG}. Your PRIORITY this cycle is wrapping up the shift log — do 1-2 more fixes if quick, but focus on: (1) REWRITE the Summary paragraph to reflect the ENTIRE shift across all cycles — what areas were explored, most impactful fixes, what needs attention. (2) Add or update Recommendations. (3) Make sure all fix entries have correct commit hashes. (4) Update final stats. (5) Run the test suite. (6) Final commit with the completed log."
    else
        PROMPT="Run /nightshift on this codebase. You are already inside the nightshift worktree — do NOT create a new worktree or switch branches. This is cycle ${CYCLE}/${CYCLES} of a test run. Read the existing shift log at ${SHIFT_LOG} to see what's done so far. Find and fix 2-3 MORE issues — pick different files and strategies than what's already in the log. IMPORTANT: After EACH fix, immediately update the shift log with a new entry and update the stats, then commit both the fix and the log update together. Do NOT write Summary or Recommendations yet."
    fi

    cd "$WORKTREE_DIR"
    claude -p "$PROMPT" --max-turns 45 2>&1 | tee -a "$WORKTREE_DIR/docs/Nightshift/${TODAY}-runner.log"

    EXIT_CODE=$?

    # Copy shift log back to main repo after each cycle
    if [ -f "$WORKTREE_DIR/$SHIFT_LOG" ]; then
        cp "$WORKTREE_DIR/$SHIFT_LOG" "$REPO_DIR/$SHIFT_LOG"
    fi
    if [ -f "$WORKTREE_DIR/docs/Nightshift/${TODAY}-runner.log" ]; then
        cp "$WORKTREE_DIR/docs/Nightshift/${TODAY}-runner.log" "$REPO_DIR/docs/Nightshift/${TODAY}-runner.log"
    fi

    echo ""
    echo "── Cycle ${CYCLE} done (exit: ${EXIT_CODE}) ─── $(date '+%H:%M') ──"
    echo ""

    if [ "$CYCLE" -lt "$CYCLES" ]; then
        sleep 5
    fi
done

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║     NIGHTSHIFT TEST COMPLETE                     ║"
echo "║     Ended: $(date '+%H:%M')                                ║"
echo "║     Worktree: ${WORKTREE_DIR}  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Review:"
echo "  cat ${WORKTREE_DIR}/${SHIFT_LOG}"
echo "  git log ${BRANCH} --oneline"
echo ""
echo "Merge when ready:"
echo "  git merge ${BRANCH}"
echo "  git worktree remove ${WORKTREE_DIR}"
