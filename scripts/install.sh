#!/bin/bash

set -euo pipefail

CLAUDE_DIR="$HOME/.claude/skills/nightshift"
CODEX_DIR="$HOME/.codex/skills/nightshift"
REPO="https://raw.githubusercontent.com/Recusive/Nightshift/main"

SCRIPT_FILES=(
  "scripts/list-tasks.sh"
  "scripts/run.sh"
  "scripts/test.sh"
  "scripts/validate-tasks.sh"
)
ROOT_FILES=(
  "nightshift/SKILL.md"
  "nightshift.schema.json"
  ".nightshift.json.example"
)
SCHEMA_FILES=(
  "schemas/feature.schema.json"
  "schemas/task.schema.json"
)
PACKAGE_FILES=(
  "nightshift/__init__.py"
  "nightshift/__main__.py"
  "nightshift/types.py"
  "nightshift/constants.py"
  "nightshift/errors.py"
  "nightshift/shell.py"
  "nightshift/config.py"
  "nightshift/state.py"
  "nightshift/worktree.py"
  "nightshift/cycle.py"
  "nightshift/scoring.py"
  "nightshift/costs.py"
  "nightshift/cleanup.py"
  "nightshift/compact.py"
  "nightshift/module_map.py"
  "nightshift/multi.py"
  "nightshift/profiler.py"
  "nightshift/planner.py"
  "nightshift/decomposer.py"
  "nightshift/subagent.py"
  "nightshift/integrator.py"
  "nightshift/summary.py"
  "nightshift/readiness.py"
  "nightshift/e2e.py"
  "nightshift/coordination.py"
  "nightshift/evaluation.py"
  "nightshift/feature.py"
  "nightshift/cli.py"
)

install_into() {
  local target="$1"
  mkdir -p "$target/nightshift" "$target/scripts" "$target/schemas"

  for file in "${SCRIPT_FILES[@]}"; do
    curl -sfL "$REPO/$file" -o "$target/$file"
  done
  for file in "${ROOT_FILES[@]}"; do
    curl -sfL "$REPO/$file" -o "$target/$file"
  done
  for file in "${SCHEMA_FILES[@]}"; do
    curl -sfL "$REPO/$file" -o "$target/$file"
  done
  for file in "${PACKAGE_FILES[@]}"; do
    curl -sfL "$REPO/$file" -o "$target/$file"
  done

  chmod +x "$target/scripts/list-tasks.sh" "$target/scripts/run.sh" "$target/scripts/test.sh" \
    "$target/scripts/validate-tasks.sh"
}

echo "Installing Nightshift..."
install_into "$CLAUDE_DIR"
install_into "$CODEX_DIR"

echo ""
echo "Nightshift installed to:"
echo "  Claude: $CLAUDE_DIR"
echo "  Codex:  $CODEX_DIR"
echo ""
echo "Usage:"
echo "  Overnight:   ~/.codex/skills/nightshift/scripts/run.sh"
echo "  Test run:    ~/.codex/skills/nightshift/scripts/test.sh"
echo ""
echo "Optional repo config:"
echo "  cp ~/.codex/skills/nightshift/.nightshift.json.example .nightshift.json"
echo ""
echo "Add this to your project's .gitignore:"
echo "  docs/Nightshift/worktree-*/"
echo "  docs/Nightshift/*.runner.log"
echo "  docs/Nightshift/*.state.json"
