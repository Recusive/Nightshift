#!/bin/bash
# ──────────────────────────────────────────────
# Rollback — Revert a merged PR cleanly
#
# Creates a revert branch, revert commit, and new PR.
#
# Usage:
#   ./scripts/rollback.sh <merge-commit-hash>
#   ./scripts/rollback.sh <PR-number>
# ──────────────────────────────────────────────

set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: ./scripts/rollback.sh <merge-commit-hash-or-PR-number>"
    echo ""
    echo "Examples:"
    echo "  ./scripts/rollback.sh abc1234"
    echo "  ./scripts/rollback.sh 5"
    exit 1
fi

INPUT="$1"

# If input looks like a PR number, get the merge commit
if echo "$INPUT" | grep -qE '^[0-9]+$'; then
    echo "Looking up PR #$INPUT..."
    MERGE_COMMIT=$(gh pr view "$INPUT" --json mergeCommit --jq '.mergeCommit.oid' 2>/dev/null || echo "")
    if [ -z "$MERGE_COMMIT" ]; then
        echo "Error: PR #$INPUT not found or not merged."
        exit 1
    fi
    echo "PR #$INPUT merge commit: $MERGE_COMMIT"
else
    MERGE_COMMIT="$INPUT"
fi

SHORT=$(echo "$MERGE_COMMIT" | cut -c1-7)
BRANCH="revert/$SHORT"

echo ""
echo "Reverting commit $SHORT..."
echo ""

git checkout main
git pull origin main
git checkout -b "$BRANCH"

# Try to revert (handles both merge and regular commits)
if ! git revert --no-edit "$MERGE_COMMIT" 2>/dev/null; then
    echo ""
    echo "Revert had conflicts. Resolve them, then:"
    echo "  git add . && git revert --continue"
    echo "  git push origin $BRANCH"
    echo "  gh pr create --title 'revert: $SHORT' --body 'Reverts $MERGE_COMMIT'"
    exit 1
fi

git push origin "$BRANCH"

gh pr create \
    --title "revert: $SHORT" \
    --body "Reverts commit $MERGE_COMMIT. See the original commit for context."

echo ""
echo "Revert PR created. Review and merge with: gh pr merge --merge --admin"
