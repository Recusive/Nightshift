#!/bin/bash
# ──────────────────────────────────────────────
# Smoke Test — Run Nightshift against a real repo
#
# Clones the test target, runs a 1-cycle test shift,
# and verifies the system actually works end-to-end.
#
# Usage:
#   ./scripts/smoke-test.sh                    # default: Phractal repo
#   ./scripts/smoke-test.sh https://github.com/user/repo.git
# ──────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_REPO="${1:-https://github.com/fazxes/Phractal.git}"
TARGET_DIR="/tmp/nightshift-smoke-test-$(date +%s)"
AGENT="${2:-claude}"

echo "=== Nightshift Smoke Test ==="
echo "Target: $TARGET_REPO"
echo "Agent:  $AGENT"
echo ""

# Clone target
echo "-- Cloning target repo --"
git clone --depth 1 "$TARGET_REPO" "$TARGET_DIR" 2>&1 | tail -2

# Create a minimal .nightshift.json if none exists
if [ ! -f "$TARGET_DIR/.nightshift.json" ]; then
    echo '{"verify_command": null}' > "$TARGET_DIR/.nightshift.json"
    echo "  Created minimal .nightshift.json (no verify command)"
fi

# Run dry-run first to make sure the prompt generates
echo ""
echo "-- Dry-run check --"
cd "$TARGET_DIR"
PYTHONPATH="$REPO_DIR" python3 -m nightshift test \
    --agent "$AGENT" \
    --cycles 1 \
    --cycle-minutes 5 \
    --dry-run > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "  Dry-run: PASS"
else
    echo "  Dry-run: FAIL"
    rm -rf "$TARGET_DIR"
    exit 1
fi

# Run actual 1-cycle test
echo ""
echo "-- Running 1-cycle test shift --"
PYTHONPATH="$REPO_DIR" python3 -m nightshift test \
    --agent "$AGENT" \
    --cycles 1 \
    --cycle-minutes 5 \
    2>&1 | tail -20

# Check results
echo ""
echo "-- Verifying results --"
TODAY=$(date +%Y-%m-%d)
SHIFT_LOG="$TARGET_DIR/docs/Nightshift/$TODAY.md"
STATE_FILE="$TARGET_DIR/docs/Nightshift/$TODAY.state.json"

PASS=true

if [ -f "$SHIFT_LOG" ]; then
    echo "  Shift log exists: PASS"
    # Check it has at least some content beyond the template
    LINES=$(wc -l < "$SHIFT_LOG")
    if [ "$LINES" -gt 30 ]; then
        echo "  Shift log has content ($LINES lines): PASS"
    else
        echo "  Shift log looks empty ($LINES lines): WARN"
    fi
else
    echo "  Shift log missing: FAIL"
    PASS=false
fi

if [ -f "$STATE_FILE" ]; then
    echo "  State file exists: PASS"
else
    echo "  State file missing: FAIL"
    PASS=false
fi

# Check worktree is clean or removed
WORKTREE_DIR="$TARGET_DIR/docs/Nightshift/worktree-$TODAY"
if [ -d "$WORKTREE_DIR" ]; then
    DIRTY=$(cd "$WORKTREE_DIR" && git status --porcelain 2>/dev/null | wc -l || echo "0")
    if [ "$DIRTY" -eq 0 ]; then
        echo "  Worktree clean: PASS"
    else
        echo "  Worktree dirty ($DIRTY files): WARN"
    fi
fi

# Cleanup
echo ""
echo "-- Cleaning up --"
if [ -d "$WORKTREE_DIR" ]; then
    cd "$TARGET_DIR"
    git worktree remove "$WORKTREE_DIR" --force 2>/dev/null || true
fi
rm -rf "$TARGET_DIR"
echo "  Cleaned up $TARGET_DIR"

echo ""
if [ "$PASS" = true ]; then
    echo "=== Smoke test PASSED ==="
    exit 0
else
    echo "=== Smoke test FAILED ==="
    exit 1
fi
