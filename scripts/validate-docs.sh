#!/bin/bash
# ──────────────────────────────────────────────
# Doc Consistency Validator
#
# Checks that documentation matches code reality.
# Exits non-zero if any check fails.
# Run in CI or as a pre-commit hook.
# ──────────────────────────────────────────────

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ERRORS=0

fail() {
    echo "FAIL: $1"
    ERRORS=$((ERRORS + 1))
}

pass() {
    echo "  ok: $1"
}

echo "=== Doc Consistency Validator ==="
echo ""

# --- Check 1: Every .py module in nightshift/ is in __init__.py ---
echo "-- Module registration --"
for pyfile in "$REPO_DIR"/nightshift/*.py; do
    name=$(basename "$pyfile" .py)
    if [ "$name" = "__init__" ] || [ "$name" = "__main__" ]; then
        continue
    fi
    if grep -q "from nightshift\.$name import" "$REPO_DIR/nightshift/__init__.py" 2>/dev/null; then
        pass "$name in __init__.py"
    else
        fail "$name is NOT imported in __init__.py"
    fi
done

# --- Check 2: Every .py module is in install.sh PACKAGE_FILES ---
echo ""
echo "-- Install script coverage --"
for pyfile in "$REPO_DIR"/nightshift/*.py; do
    name=$(basename "$pyfile")
    if grep -q "nightshift/$name" "$REPO_DIR/scripts/install.sh" 2>/dev/null; then
        pass "$name in install.sh"
    else
        fail "$name is NOT in scripts/install.sh PACKAGE_FILES"
    fi
done

# --- Check 3: Test count matches across docs ---
echo ""
echo "-- Test count consistency --"
ACTUAL_TESTS=$(grep -c "def test_" "$REPO_DIR/tests/test_nightshift.py" 2>/dev/null || echo "0")
echo "  Actual test count: $ACTUAL_TESTS"

for doc in \
    "$REPO_DIR/docs/vision-tracker/TRACKER.md" \
    "$REPO_DIR/CLAUDE.md"; do
    if [ -f "$doc" ]; then
        docname=$(basename "$doc")
        # Look for patterns like "123 tests" or "134 tests"
        claimed=$(grep -oE '[0-9]+ tests' "$doc" 2>/dev/null | head -1 | grep -oE '[0-9]+' || echo "")
        if [ -n "$claimed" ]; then
            if [ "$claimed" = "$ACTUAL_TESTS" ]; then
                pass "$docname claims $claimed tests (matches)"
            else
                fail "$docname claims $claimed tests but actual is $ACTUAL_TESTS"
            fi
        fi
    fi
done

# --- Check 4: Tracker percentages match component counts ---
echo ""
echo "-- Tracker percentage accuracy --"
if [ -f "$REPO_DIR/docs/vision-tracker/TRACKER.md" ]; then
    for section in "Loop 1" "Loop 2" "Self-Maintaining" "Meta-Prompt"; do
        # Count Done vs total components in the section's table
        # This is approximate — looks for "| Done |" and "| Not started |" and "| In progress |"
        done_count=$(awk "/## $section/,/^---/" "$REPO_DIR/docs/vision-tracker/TRACKER.md" \
            | grep -c "| Done |" 2>/dev/null || true)
        done_count=$(echo "$done_count" | tr -dc '0-9')
        done_count=${done_count:-0}
        total_count=$(awk "/## $section/,/^---/" "$REPO_DIR/docs/vision-tracker/TRACKER.md" \
            | grep -cE "\| (Done|Not started|In progress|Scaffolded) \|" 2>/dev/null || true)
        total_count=$(echo "$total_count" | tr -dc '0-9')
        total_count=${total_count:-0}
        if [ "$total_count" -gt 0 ]; then
            expected=$((done_count * 100 / total_count))
            # Extract claimed percentage from the section header
            claimed=$(grep "## $section" "$REPO_DIR/docs/vision-tracker/TRACKER.md" \
                | grep -oE '[0-9]+%' | head -1 | tr -d '%' || true)
            claimed=$(echo "$claimed" | tr -dc '0-9')
            claimed=${claimed:-0}
            if [ "$claimed" != "0" ] || [ "$expected" != "0" ]; then
                abs_diff=$((claimed - expected))
                if [ "$abs_diff" -lt 0 ]; then abs_diff=$((-abs_diff)); fi
                if [ "$abs_diff" -le 2 ]; then
                    pass "$section: claimed ${claimed}%, calculated ${expected}% (close enough)"
                else
                    fail "$section: claimed ${claimed}% but calculated ${expected}% (${done_count}/${total_count} done)"
                fi
            fi
        fi
    done
fi

# --- Check 5: Every file path in CLAUDE.md exists ---
echo ""
echo "-- CLAUDE.md path references --"
if [ -f "$REPO_DIR/CLAUDE.md" ]; then
    # Extract paths that look like nightshift/something.py or scripts/something.sh
    grep -oE '(nightshift|scripts|docs|tests)/[a-zA-Z0-9_./-]+' "$REPO_DIR/CLAUDE.md" \
        | sort -u | while read -r path; do
        if [ -e "$REPO_DIR/$path" ]; then
            pass "$path exists"
        else
            fail "$path referenced in CLAUDE.md does NOT exist"
        fi
    done
fi

# --- Check 6: Handoff percentages match tracker ---
echo ""
echo "-- Handoff vs tracker consistency --"
if [ -f "$REPO_DIR/docs/handoffs/LATEST.md" ] && [ -f "$REPO_DIR/docs/vision-tracker/TRACKER.md" ]; then
    # Extract Loop 1 percentage from both
    handoff_l1=$(grep -oE 'Loop 1: [0-9]+%' "$REPO_DIR/docs/handoffs/LATEST.md" \
        | grep -oE '[0-9]+' | head -1 || echo "")
    tracker_l1=$(grep "Loop 1" "$REPO_DIR/docs/vision-tracker/TRACKER.md" \
        | grep -oE '[0-9]+%' | head -1 | tr -d '%' || echo "")
    if [ -n "$handoff_l1" ] && [ -n "$tracker_l1" ]; then
        diff=$((handoff_l1 - tracker_l1))
        if [ "$diff" -lt 0 ]; then diff=$((-diff)); fi
        if [ "$diff" -le 2 ]; then
            pass "Loop 1: handoff ${handoff_l1}% matches tracker ${tracker_l1}%"
        else
            fail "Loop 1: handoff says ${handoff_l1}% but tracker says ${tracker_l1}%"
        fi
    fi
fi

echo ""
echo "=== Results: $ERRORS failures ==="

if [ "$ERRORS" -gt 0 ]; then
    echo "Doc validation FAILED. Fix the above issues before pushing."
    exit 1
fi

echo "All doc checks passed."
exit 0
