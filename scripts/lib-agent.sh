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

# ──────────────────────────────────────────────
# Prompt Self-Modification Guard
#
# Detects if the agent modified prompt/control files during a cycle.
# These files control agent behavior -- unauthorized changes could
# corrupt all future sessions.
# ──────────────────────────────────────────────

PROMPT_GUARD_FILES=(
    "CLAUDE.md"
    "docs/prompt/evolve.md"
    "docs/prompt/evolve-auto.md"
    "docs/prompt/review.md"
    "docs/prompt/overseer.md"
    "docs/prompt/strategist.md"
    "docs/prompt/harden-daemon.md"
)

# save_prompt_snapshots REPO_DIR
# Copies all prompt files to a temp directory for comparison after the cycle.
# Outputs the temp directory path.
save_prompt_snapshots() {
    local repo_dir="$1"
    local snap_dir
    snap_dir=$(mktemp -d "${TMPDIR:-/tmp}/nightshift-prompt-guard.XXXXXX")
    for f in "${PROMPT_GUARD_FILES[@]}"; do
        local src="$repo_dir/$f"
        if [ -f "$src" ]; then
            local dst="$snap_dir/$f"
            mkdir -p "$(dirname "$dst")"
            cp "$src" "$dst"
        fi
    done
    echo "$snap_dir"
}

# check_prompt_integrity REPO_DIR SNAPSHOT_DIR [ALERT_FILE]
# Compares current prompt files against pre-cycle snapshots.
# Logs diffs to stdout. Writes alert file if ALERT_FILE is provided.
# Returns 0 if unchanged, 1 if any file was modified.
check_prompt_integrity() {
    local repo_dir="$1"
    local snap_dir="$2"
    local alert_file="${3:-}"
    local changed=0
    local alert_body=""

    for f in "${PROMPT_GUARD_FILES[@]}"; do
        local current="$repo_dir/$f"
        local snapshot="$snap_dir/$f"

        if [ -f "$snapshot" ] && [ -f "$current" ]; then
            if ! diff -q "$snapshot" "$current" >/dev/null 2>&1; then
                if [ "$changed" -eq 0 ]; then
                    echo ""
                    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                    echo "  PROMPT SELF-MODIFICATION DETECTED"
                    echo "  The agent modified files that control its behavior."
                    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                fi
                echo ""
                echo "CHANGED: $f"
                local file_diff
                file_diff=$(diff -u "$snapshot" "$current" 2>/dev/null || true)
                echo "$file_diff"
                alert_body="${alert_body}CHANGED: ${f}"$'\n'"${file_diff}"$'\n\n'
                changed=1
            fi
        elif [ -f "$snapshot" ] && [ ! -f "$current" ]; then
            if [ "$changed" -eq 0 ]; then
                echo ""
                echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                echo "  PROMPT SELF-MODIFICATION DETECTED"
                echo "  The agent modified files that control its behavior."
                echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            fi
            echo ""
            echo "DELETED: $f"
            alert_body="${alert_body}DELETED: ${f}"$'\n\n'
            changed=1
        fi
    done

    if [ "$changed" -ne 0 ]; then
        echo ""
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"

        if [ -n "$alert_file" ]; then
            {
                echo "PROMPT MODIFICATION ALERT"
                echo "========================="
                echo "The previous session modified prompt/control files."
                echo "Review these changes before building. If they look"
                echo "malicious or accidental, revert them."
                echo ""
                echo "$alert_body"
            } > "$alert_file"
        fi
    fi

    return "$changed"
}

# cleanup_prompt_snapshots SNAPSHOT_DIR
# Removes the temporary snapshot directory.
cleanup_prompt_snapshots() {
    local snap_dir="$1"
    if [ -n "$snap_dir" ] && [ -d "$snap_dir" ]; then
        rm -rf "$snap_dir"
    fi
}

# ──────────────────────────────────────────────
# Agent Configuration
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
