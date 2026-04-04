#!/bin/bash
# ──────────────────────────────────────────────
# Shared agent invocation for all daemons.
# Source this file, then call run_agent.
#
# Supports: claude, codex
# Both produce JSONL output for log parsing.
# ──────────────────────────────────────────────

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
            # --full-auto: no approval needed, workspace write access
            # --json: JSONL stream to stdout (same as claude stream-json)
            codex exec \
                --full-auto \
                --json \
                "$prompt" \
                2>&1 | tee "$log_file"
            EXIT_CODE=${PIPESTATUS[0]}
            ;;
        claude)
            # Claude non-interactive mode
            # -p: non-interactive (print mode)
            # --output-format stream-json: JSONL stream
            # --max-turns: session turn limit
            claude -p "$prompt" \
                --max-turns "$max_turns" \
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
