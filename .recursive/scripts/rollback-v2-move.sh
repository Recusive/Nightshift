#!/usr/bin/env bash
# Rollback the v2 directory move (Phase 5).
# Restores Recursive/ from the v2-pre-move tag.
# Usage: bash .recursive/scripts/rollback-v2-move.sh
set -euo pipefail

TAG="v2-pre-move"

if ! git tag -l "$TAG" | grep -q "$TAG"; then
    echo "ERROR: Tag $TAG not found. Cannot rollback." >&2
    exit 1
fi

echo "Rolling back to $TAG..."
git reset --hard "$TAG"
echo "Rollback complete. Verify with: make check"
