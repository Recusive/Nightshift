#!/bin/bash
# ──────────────────────────────────────────────
# Shared agent invocation for all daemons.
# Source this file, then call run_agent.
#
# Supports: claude, codex
# Both produce JSONL output for log parsing.
#
# Model config via environment variables:
#   NIGHTSHIFT_CLAUDE_MODEL   (default: opus)
#   NIGHTSHIFT_CODEX_MODEL    (default: o3)
#   NIGHTSHIFT_CODEX_THINKING (default: extra_high)
# ──────────────────────────────────────────────

# Configurable models -- override via environment
CLAUDE_MODEL="${NIGHTSHIFT_CLAUDE_MODEL:-claude-opus-4-6}"
CODEX_MODEL="${NIGHTSHIFT_CODEX_MODEL:-gpt-5.4}"
CODEX_THINKING="${NIGHTSHIFT_CODEX_THINKING:-extra_high}"

# run_agent AGENT PROMPT LOG_FILE MAX_TURNS
# Sets EXIT_CODE as a side effect.
run_agent() {
    local agent="$1"
    local prompt="$2"
    local log_file="$3"
    local max_turns="${4:-500}"

    set +e
    case "$agent" in
        codex)
            # Codex non-interactive mode
            # --dangerously-bypass-approvals-and-sandbox: skip approvals + full filesystem/git access
            #   NOTE: --full-auto forces --sandbox workspace-write which blocks .git/ lock files
            #   in worktrees. We need true full access for git commit/push inside worktrees.
            # --json: JSONL stream to stdout
            # --model: configurable (default gpt-5.4)
            # -c reasoning_effort: thinking level
            codex exec \
                --dangerously-bypass-approvals-and-sandbox \
                --json \
                --model "$CODEX_MODEL" \
                -c "reasoning_effort=\"$CODEX_THINKING\"" \
                "$prompt" \
                2>&1 | tee "$log_file"
            EXIT_CODE=${PIPESTATUS[0]}
            ;;
        claude)
            # Claude non-interactive mode
            # -p: non-interactive (print mode)
            # --output-format stream-json: JSONL stream
            # --max-turns: session turn limit
            # --model: configurable (default opus)
            claude -p "$prompt" \
                --max-turns "$max_turns" \
                --model "$CLAUDE_MODEL" \
                --effort max \
                --output-format stream-json \
                --verbose \
                2>&1 | tee "$log_file"
            EXIT_CODE=${PIPESTATUS[0]}
            ;;
        *)
            echo "ERROR: Unknown agent '$agent'. Supported: claude, codex"
            EXIT_CODE=1
            ;;
    esac
    set -e
}
