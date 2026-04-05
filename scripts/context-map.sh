#!/bin/bash
# ----------------------------------------------
# Context Map Generator
#
# Generates a slim context file that agents can read
# instead of grepping the whole codebase. Shows:
# - Module list with line counts
# - Function signatures (no bodies)
# - Dependency graph
# - Test count per module
#
# Output: docs/context-map.md (auto-generated, not committed)
# ----------------------------------------------

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT="$REPO_DIR/docs/context-map.md"

{
    echo "# Context Map (auto-generated)"
    echo ""
    echo "Generated: $(date '+%Y-%m-%d %H:%M')"
    echo ""

    # Module sizes
    echo "## Modules"
    echo ""
    echo "| Module | Lines | Functions |"
    echo "|--------|-------|-----------|"
    for pyfile in "$REPO_DIR"/nightshift/*.py; do
        name=$(basename "$pyfile" .py)
        if [ "$name" = "__init__" ] || [ "$name" = "__main__" ]; then
            continue
        fi
        lines=$(wc -l < "$pyfile" | tr -d ' ')
        funcs=$(grep -c "^def \|^    def " "$pyfile" 2>/dev/null || echo "0")
        echo "| $name | $lines | $funcs |"
    done

    # Function signatures
    echo ""
    echo "## Public Functions"
    echo ""
    for pyfile in "$REPO_DIR"/nightshift/*.py; do
        name=$(basename "$pyfile" .py)
        if [ "$name" = "__init__" ] || [ "$name" = "__main__" ]; then
            continue
        fi
        publics=$(grep "^def " "$pyfile" 2>/dev/null | grep -v "^def _" || true)
        if [ -n "$publics" ]; then
            echo "### $name"
            echo '```python'
            echo "$publics"
            echo '```'
            echo ""
        fi
    done

    # Dependency graph
    echo "## Import Graph"
    echo ""
    echo '```'
    for pyfile in "$REPO_DIR"/nightshift/*.py; do
        name=$(basename "$pyfile" .py)
        if [ "$name" = "__init__" ] || [ "$name" = "__main__" ]; then
            continue
        fi
        deps=$(grep "^from nightshift\." "$pyfile" 2>/dev/null \
            | sed 's/from nightshift\.\([a-z_]*\).*/\1/' \
            | sort -u \
            | tr '\n' ', ' \
            | sed 's/,$//')
        if [ -n "$deps" ]; then
            echo "$name -> $deps"
        else
            echo "$name -> (none)"
        fi
    done
    echo '```'

    # Test coverage
    echo ""
    echo "## Test Coverage"
    echo ""
    TOTAL=$(grep -c "def test_" "$REPO_DIR/tests/test_nightshift.py" 2>/dev/null || echo "0")
    echo "Total test functions: $TOTAL"
    echo ""
    echo "| Test Class | Count |"
    echo "|------------|-------|"
    grep "^class Test" "$REPO_DIR/tests/test_nightshift.py" 2>/dev/null | while read -r line; do
        classname=$(echo "$line" | sed 's/class \(Test[a-zA-Z]*\).*/\1/')
        # Count test methods in this class (approximate)
        count=$(awk "/^class $classname/,/^class Test/" "$REPO_DIR/tests/test_nightshift.py" \
            | grep -c "def test_" 2>/dev/null || echo "0")
        echo "| $classname | $count |"
    done

} > "$OUTPUT"

echo "Context map written to: $OUTPUT"
echo "$(wc -l < "$OUTPUT" | tr -d ' ') lines"
