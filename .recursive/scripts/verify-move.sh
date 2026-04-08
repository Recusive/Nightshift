#!/usr/bin/env bash
# verify-move.sh -- run after Phase 5 directory move, exit non-zero on any failure
set -euo pipefail
fail=0

echo "=== Verifying v2 directory move ==="

# Verify framework files exist at new paths
for f in .recursive/engine/daemon.sh .recursive/engine/lib-agent.sh \
         .recursive/engine/dashboard.py .recursive/engine/signals.py \
         .recursive/scripts/init.sh .recursive/scripts/list-tasks.sh; do
    if [ ! -f "$f" ]; then
        echo "MISSING: $f"; fail=1
    fi
done

# Shell syntax check (parse without executing)
for f in .recursive/engine/daemon.sh .recursive/engine/lib-agent.sh \
         .recursive/scripts/init.sh .recursive/scripts/list-tasks.sh; do
    if ! bash -n "$f" 2>/dev/null; then
        echo "SYNTAX ERROR: $f"; fail=1
    fi
done

# Makefile targets work
if ! make check > /dev/null 2>&1; then
    echo "make check failed"; fail=1
fi
if ! make tasks > /dev/null 2>&1; then
    echo "make tasks failed"; fail=1
fi

# No docs reference stale paths
stale=$(grep -rn 'bash Recursive/' CLAUDE.md AGENTS.md README.md \
  .recursive/skills/setup/SKILL.md .recursive/ops/*.md 2>/dev/null || true)
if [ -n "$stale" ]; then
    echo "STALE REFERENCES:"; echo "$stale"; fail=1
fi

# Old directory gone
if [ -d "Recursive" ]; then
    echo "ERROR: Recursive/ directory still exists"; fail=1
fi

# Symlinks resolve
if [ ! -L ".claude/agents/brain.md" ]; then
    echo "ERROR: .claude/agents/brain.md symlink missing"; fail=1
fi

if [ "$fail" -eq 0 ]; then
    echo "=== All move verification checks passed ==="
else
    echo "=== VERIFICATION FAILED ==="
fi
exit $fail
