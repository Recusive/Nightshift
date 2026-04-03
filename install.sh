#!/bin/bash

set -euo pipefail

CLAUDE_DIR="$HOME/.claude/skills/nightshift"
CODEX_DIR="$HOME/.codex/skills/nightshift"
REPO="https://raw.githubusercontent.com/Recusive/Nightshift/main"
FILES=(
  "SKILL.md"
  "run.sh"
  "test.sh"
  "nightshift.py"
  "nightshift.schema.json"
  ".nightshift.json.example"
)

install_into() {
  local target="$1"
  mkdir -p "$target"
  for file in "${FILES[@]}"; do
    curl -sL "$REPO/$file" -o "$target/$file"
  done
  chmod +x "$target/run.sh" "$target/test.sh" "$target/nightshift.py"
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
echo "  Codex overnight:   ~/.codex/skills/nightshift/run.sh"
echo "  Codex test run:    ~/.codex/skills/nightshift/test.sh"
echo "  Claude overnight:  ~/.claude/skills/nightshift/run.sh"
echo ""
echo "Optional repo config:"
echo "  cp ~/.codex/skills/nightshift/.nightshift.json.example .nightshift.json"
echo ""
echo "Add this to your project's .gitignore:"
echo "  docs/Nightshift/worktree-*/"
echo "  docs/Nightshift/*.runner.log"
echo "  docs/Nightshift/*.state.json"
