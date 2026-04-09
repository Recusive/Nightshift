#!/bin/bash
# ----------------------------------------------
# Recursive Init — Set up a project for Recursive
#
# Usage:
#   bash .recursive/scripts/init.sh
#   bash .recursive/scripts/init.sh --name "My Project"
#
# Creates:
#   .recursive.json          — project configuration
#   .recursive/              — all runtime state directories with starter files
# ----------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RECURSIVE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$RECURSIVE_DIR/.." && pwd)"

# Parse args
PROJECT_NAME=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --name) PROJECT_NAME="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# Auto-detect project name from directory if not provided
if [ -z "$PROJECT_NAME" ]; then
    PROJECT_NAME=$(basename "$REPO_DIR")
    echo "Project name (auto-detected): $PROJECT_NAME"
    echo "  Override with: bash .recursive/scripts/init.sh --name \"Your Name\""
fi

echo ""
echo "Setting up Recursive for: $PROJECT_NAME"
echo ""

# --- Create all runtime directories ---
echo "Creating .recursive/ directories..."
mkdir -p "$REPO_DIR/.recursive"/{handoffs,tasks,sessions/raw,sessions/structured,evaluations,learnings,strategy,autonomy,healer,reviews,plans,architecture,changelog,vision,vision-tracker,friction,security}
echo "  Created 16 subdirectories (sessions has raw/ + structured/)"

# --- Symlink agents for Claude Code ---
echo "Setting up .claude/agents/ symlinks..."
mkdir -p "$REPO_DIR/.claude/agents"
for f in "$RECURSIVE_DIR/agents/"*.md; do
    name=$(basename "$f")
    target="../../.recursive/agents/$name"
    link="$REPO_DIR/.claude/agents/$name"
    if [ -L "$link" ] || [ ! -f "$link" ]; then
        ln -sf "$target" "$link"
    fi
done
echo "  Symlinked $(ls "$RECURSIVE_DIR/agents/"*.md | wc -l | tr -d ' ') agent definitions"

# --- Project config ---
CONFIG="$REPO_DIR/.recursive.json"
if [ -f "$CONFIG" ]; then
    echo "  Config exists: $CONFIG (skipping)"
else
    cat > "$CONFIG" << JSONEOF
{
  "project": {
    "name": "$PROJECT_NAME",
    "description": "",
    "test_target": ""
  },
  "commands": {
    "check": "make check",
    "test": "make test",
    "dry_run": ""
  },
  "agents": {
    "default": "claude",
    "model": "claude-sonnet-4-6",
    "effort": "high"
  },
  "daemon": {
    "pause_seconds": 60,
    "max_sessions": 0,
    "budget": "0"
  }
}
JSONEOF
    echo "  Created .recursive.json"
fi

# --- Starter files (only if they don't exist) ---

_create() {
    local path="$1"
    if [ -f "$path" ]; then
        return
    fi
    cat > "$path"
    echo "  Created $(echo "$path" | sed "s|$REPO_DIR/||")"
}

# Handoffs — session memory
_create "$REPO_DIR/.recursive/handoffs/LATEST.md" << 'EOF'
# Initial Handoff

First session. No previous work. Read the project's vision and task queue to decide what to build.
EOF

# Tasks — work queue
if [ ! -f "$REPO_DIR/.recursive/tasks/.next-id" ]; then
    echo "1" > "$REPO_DIR/.recursive/tasks/.next-id"
    echo "  Created .recursive/tasks/.next-id"
fi

_create "$REPO_DIR/.recursive/tasks/GUIDE.md" << 'EOF'
# Task Guide

Tasks live here as numbered markdown files: `NNNN-short-name.md`

## Frontmatter

```yaml
---
title: Descriptive title
status: pending        # pending | in-progress | blocked | done | wontfix
priority: normal       # urgent | normal | low
created: YYYY-MM-DD
---
```

## Lifecycle

1. Agent reads `.next-id`, creates task file, increments counter
2. Agent picks lowest-numbered pending task each session
3. Completed tasks get `status: done` + `completed: YYYY-MM-DD`
4. Done tasks are archived to `archive/` by the daemon's housekeeping
EOF

# Healer — system health observations
_create "$REPO_DIR/.recursive/healer/log.md" << 'EOF'
# Healer Log

System health observations from daemon sessions.
EOF

# Friction — framework feedback from target operators
_create "$REPO_DIR/.recursive/friction/log.md" << 'EOF'
# Friction Log

Framework friction reported by agents during sessions.
Read by the evolve and audit operators to improve the framework.
EOF

# Learnings — cross-session knowledge
_create "$REPO_DIR/.recursive/learnings/INDEX.md" << 'EOF'
# Learnings Index

One-line summaries of hard-won knowledge. Open individual files only when relevant.
EOF

# Changelog — version history
_create "$REPO_DIR/.recursive/changelog/README.md" << CHEOF
# Changelog

Version history for $PROJECT_NAME. Each version gets its own file: \`vX.X.X.md\`

## Format

\`\`\`markdown
# vX.X.X -- Codename

Status: In progress | Released YYYY-MM-DD

## Added
- [tag] Description

## Changed
- [tag] Description

## Fixed
- [tag] Description
\`\`\`
CHEOF

# Vision — human input: what to build
_create "$REPO_DIR/.recursive/vision/00-overview.md" << VEOF
# $PROJECT_NAME — Vision

## What is $PROJECT_NAME?
[Describe what this project does and why it exists]

## Success Criteria
[What does "done" look like? When can you stop building?]

## Architecture
[High-level design — components, data flow, key decisions]
VEOF

# Vision tracker — progress scoreboard
_create "$REPO_DIR/.recursive/vision-tracker/TRACKER.md" << TEOF
# Vision Tracker

Progress toward the $PROJECT_NAME vision.

Last updated: $(date +%Y-%m-%d)

## Overall Progress

\`\`\`
Overall:  ░░░░░░░░░░░░░░░░░░░░  0%
\`\`\`

## Components

| Component | Status | Progress |
|-----------|--------|----------|
| [Component 1] | Not started | 0% |
| [Component 2] | Not started | 0% |
TEOF

# Sessions — index + costs ledger
_create "$REPO_DIR/.recursive/sessions/index.md" << 'EOF'
# Session Index

| Timestamp | Session | Role | Exit | Duration | Cost | Status | Feature | PR | Override |
|-----------|---------|------|------|----------|------|--------|---------|-----|----------|
EOF

if [ ! -f "$REPO_DIR/.recursive/sessions/costs.json" ]; then
    echo "[]" > "$REPO_DIR/.recursive/sessions/costs.json"
    echo "  Created .recursive/sessions/costs.json"
fi

# Reviews — code review logs
_create "$REPO_DIR/.recursive/reviews/README.md" << 'EOF'
# Code Reviews

Review session logs. Created by the review operator.
EOF

# Strategy — strategy reports
_create "$REPO_DIR/.recursive/strategy/README.md" << 'EOF'
# Strategy Reports

Strategic analysis reports. Created by the strategize operator.
EOF

echo ""
echo "=================================================="
echo "  Recursive initialized for: $PROJECT_NAME"
echo ""
echo "  Config:    .recursive.json"
echo "  Runtime:   .recursive/ (framework + runtime state)"
echo "  Vision:    .recursive/vision/00-overview.md  <-- EDIT THIS"
echo ""
echo "  Next steps:"
echo "    1. Edit .recursive.json (description, test_target, commands)"
echo "    2. Edit .recursive/vision/00-overview.md (what to build)"
echo "    3. Start: bash .recursive/engine/daemon.sh claude 60"
echo "=================================================="
