#!/bin/bash
# ──────────────────────────────────────────────
# Nightshift Installer
# One-liner: curl -sL https://raw.githubusercontent.com/Recusive/Nightshift/main/install.sh | bash
# ──────────────────────────────────────────────

set -e

SKILL_DIR="$HOME/.claude/skills/nightshift"
REPO="https://raw.githubusercontent.com/Recusive/Nightshift/main"

echo "Installing Nightshift..."

mkdir -p "$SKILL_DIR"

curl -sL "$REPO/SKILL.md" -o "$SKILL_DIR/SKILL.md"
curl -sL "$REPO/run.sh" -o "$SKILL_DIR/run.sh"
chmod +x "$SKILL_DIR/run.sh"

echo ""
echo "Nightshift installed to $SKILL_DIR"
echo ""
echo "Usage:"
echo "  Interactive:  /nightshift  (in a Claude Code session)"
echo "  Overnight:    ~/.claude/skills/nightshift/run.sh"
echo ""
echo "Don't forget to add this to your project's .gitignore:"
echo "  docs/Nightshift/worktree-*/"
