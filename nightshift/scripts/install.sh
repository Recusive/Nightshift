#!/bin/bash

set -euo pipefail

CLAUDE_DIR="$HOME/.claude/skills/nightshift"
CODEX_DIR="$HOME/.codex/skills/nightshift"
REPO="https://raw.githubusercontent.com/Recusive/Nightshift/main"

SCRIPT_FILES=(
  "nightshift/scripts/run.sh"
  "nightshift/scripts/test.sh"
)
ROOT_FILES=(
  "nightshift/SKILL.md"
  "nightshift/schemas/nightshift.schema.json"
  ".nightshift.json.example"
)
SCHEMA_FILES=(
  "nightshift/schemas/feature.schema.json"
  "nightshift/schemas/task.schema.json"
)
PACKAGE_FILES=(
  "nightshift/__init__.py"
  "nightshift/__main__.py"
  "nightshift/cli.py"
  "nightshift/core/__init__.py"
  "nightshift/core/errors.py"
  "nightshift/core/types.py"
  "nightshift/core/constants.py"
  "nightshift/core/shell.py"
  "nightshift/core/state.py"
  "nightshift/settings/__init__.py"
  "nightshift/settings/config.py"
  "nightshift/settings/eval_targets.py"
  "nightshift/owl/__init__.py"
  "nightshift/owl/cycle.py"
  "nightshift/owl/eval_runner.py"
  "nightshift/owl/scoring.py"
  "nightshift/owl/readiness.py"
  "nightshift/raven/__init__.py"
  "nightshift/raven/feature.py"
  "nightshift/raven/planner.py"
  "nightshift/raven/decomposer.py"
  "nightshift/raven/subagent.py"
  "nightshift/raven/integrator.py"
  "nightshift/raven/coordination.py"
  "nightshift/raven/summary.py"
  "nightshift/raven/e2e.py"
  "nightshift/raven/profiler.py"
  "nightshift/infra/__init__.py"
  "nightshift/infra/release.py"
  "nightshift/infra/worktree.py"
  "nightshift/infra/module_map.py"
  "nightshift/infra/multi.py"
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

  chmod +x "$target/nightshift/scripts/run.sh" "$target/nightshift/scripts/test.sh"
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
echo "  Overnight:   ~/.codex/skills/nightshift/nightshift/scripts/run.sh"
echo "  Test run:    ~/.codex/skills/nightshift/nightshift/scripts/test.sh"
echo ""
echo "Optional repo config:"
echo "  cp ~/.codex/skills/nightshift/.nightshift.json.example .nightshift.json"
echo ""
echo "Add this to your project's .gitignore:"
echo "  docs/Nightshift/worktree-*/"
echo "  docs/Nightshift/*.runner.log"
echo "  docs/Nightshift/*.state.json"
