#!/usr/bin/env bash
# Recursive daemon v2 -- brain-delegates-to-sub-agents architecture.
#
# Instead of picking one operator per cycle, runs a brain agent (Opus)
# that reads the dashboard, thinks, and delegates to sub-agents (Sonnet)
# in git worktrees.
#
# Usage:
#   bash .recursive/engine/daemon.sh claude [duration_hours] [max_sessions]
#
# Environment variables:
#   RECURSIVE_CLAUDE_MODEL   Brain model (default: claude-opus-4-6)
#   RECURSIVE_BUDGET_USD     Budget limit (default: 50)
#   RECURSIVE_FORCE_ROLE     Force a specific role (bypasses brain)
#   FRAMEWORK_DIR            Framework directory (default: .recursive)
set -euo pipefail

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$SCRIPT_DIR"
RECURSIVE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$RECURSIVE_DIR/.." && pwd)"

# Source the shared library (prompt guard, housekeeping, agent execution)
# shellcheck source=lib-agent.sh
source "$ENGINE_DIR/lib-agent.sh"

# Ensure framework dir is set for zone compliance
export FRAMEWORK_DIR="${FRAMEWORK_DIR:-.recursive}"

PICK_ROLE="$ENGINE_DIR/pick-role.py"
DASHBOARD="$ENGINE_DIR/dashboard.py"

# Agent and model config
AGENT="${1:-claude}"
DURATION_HOURS="${2:-8}"
MAX_SESSIONS="${3:-0}"  # 0 = unlimited (use duration)
BRAIN_MODEL="${RECURSIVE_CLAUDE_MODEL:-claude-opus-4-6}"
BUDGET_LIMIT="${RECURSIVE_BUDGET_USD:-50}"

# Paths
LOCKFILE="$REPO_DIR/.recursive-daemon.lock"
SESSION_DIR="$REPO_DIR/.recursive/sessions"
COST_FILE="$SESSION_DIR/costs.json"
INDEX_FILE="$SESSION_DIR/index.md"
DECISIONS_LOG="$REPO_DIR/.recursive/decisions/log.md"

# Timing
START_TIME=$(date +%s)
END_TIME=$((START_TIME + DURATION_HOURS * 3600))
CYCLE=0
CONSECUTIVE_FAILURES=0
MAX_CONSECUTIVE_FAILURES=3

# ---------------------------------------------------------------------------
# Lock
# ---------------------------------------------------------------------------

if [ -f "$LOCKFILE" ]; then
    existing_pid=$(cat "$LOCKFILE" 2>/dev/null || echo "")
    if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
        echo "ERROR: daemon already running (PID $existing_pid)" >&2
        exit 1
    fi
    echo "WARN: stale lockfile, removing" >&2
    rm -f "$LOCKFILE"
fi
echo $$ > "$LOCKFILE"

# ---------------------------------------------------------------------------
# Cleanup trap -- covers lock file and any mktemp files created during session.
# Uses ${VAR:-} so the function is safe even if a variable was never set
# (e.g. the script aborts before a mktemp assignment).
# ---------------------------------------------------------------------------
_daemon_cleanup() {
    rm -f "${LOCKFILE:-}"
    rm -f "${CONTEXT_FILE:-}"
    rm -f "${COST_MSG_TMP:-}"
    rm -rf "${SNAP_DIR:-}"
}
trap '_daemon_cleanup' EXIT

echo "=== Recursive Daemon v2 ==="
echo "Agent: $AGENT | Brain: $BRAIN_MODEL | Budget: \$$BUDGET_LIMIT"
echo "Duration: ${DURATION_HOURS}h | Max sessions: ${MAX_SESSIONS:-unlimited}"
echo "Repo: $REPO_DIR"
echo ""

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

while true; do
    # --- Check time/session limits ---
    NOW=$(date +%s)
    if [ "$NOW" -ge "$END_TIME" ]; then
        echo "Duration limit reached. Stopping."
        break
    fi
    if [ "$MAX_SESSIONS" -gt 0 ] && [ "$CYCLE" -ge "$MAX_SESSIONS" ]; then
        echo "Session limit reached ($MAX_SESSIONS). Stopping."
        break
    fi

    CYCLE=$((CYCLE + 1))
    SESSION_ID=$(date +%Y%m%d-%H%M%S)
    SESSION_START=$(date +%s)
    echo ""
    echo "--- Cycle $CYCLE | $SESSION_ID ---"

    # --- Reset to origin/main ---
    echo "  Resetting to origin/main..."
    git -C "$REPO_DIR" fetch origin main --quiet 2>/dev/null || true
    git -C "$REPO_DIR" reset --hard origin/main --quiet 2>/dev/null || true

    # --- Hot-reload lib-agent.sh ---
    source "$ENGINE_DIR/lib-agent.sh"

    # --- Housekeeping ---
    echo "  Running housekeeping..."
    cleanup_old_logs "$SESSION_DIR/raw" 7 2>/dev/null || true
    cleanup_orphan_branches 2>/dev/null || true
    cleanup_worktrees 2>/dev/null || true
    archive_done_tasks "$REPO_DIR/.recursive/tasks" 2>/dev/null || true
    compact_handoffs "$REPO_DIR/.recursive/handoffs" 2>/dev/null || true
    sync_github_tasks "$REPO_DIR/.recursive/tasks" 2>/dev/null || true

    # --- Check for open PRs from previous sessions ---
    OPEN_PRS=$(gh pr list --state open --json number,title,headRefName --limit 5 2>/dev/null || echo "[]")
    OPEN_PR_COUNT=$(echo "$OPEN_PRS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    if [ "$OPEN_PR_COUNT" -gt 0 ]; then
        echo "  Found $OPEN_PR_COUNT open PR(s) from previous sessions"
    fi

    # --- Get advisory recommendation ---
    echo "  Getting advisory recommendation..."
    ADVISORY_JSON=$(python3 "$PICK_ROLE" "$REPO_DIR" --advise 2>/dev/null || echo '{"recommended":"build","score":50,"reason":"fallback"}')
    ADVISORY_ROLE=$(echo "$ADVISORY_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('recommended','build'))" 2>/dev/null || echo "build")
    echo "  Advisory: $ADVISORY_ROLE"

    # --- Guard: brain definition must exist ---
    if [ "$AGENT" = "codex" ]; then
        if [ ! -f "$REPO_DIR/.codex/agents/brain.toml" ]; then
            echo "ERROR: brain.toml not found. Run: bash .recursive/scripts/init.sh" >&2
            break
        fi
    else
        if [ ! -f "$REPO_DIR/.claude/agents/brain.md" ] && [ ! -f "$REPO_DIR/.recursive/agents/brain.md" ]; then
            echo "ERROR: brain.md not found. Run: bash .recursive/scripts/init.sh" >&2
            break
        fi
    fi

    # --- Generate dashboard ---
    echo "  Generating dashboard..."
    DASHBOARD_TEXT=$(python3 "$DASHBOARD" "$REPO_DIR/.recursive" 2>/dev/null || echo "Dashboard unavailable")

    # --- Prompt guard snapshot ---
    echo "  Taking prompt guard snapshot..."
    SNAP_DIR=$(save_prompt_snapshots "$REPO_DIR")

    # --- Pre-create worktrees for Codex sub-agents ---
    # Claude Code has built-in isolation: "worktree" via Agent(). Codex does not.
    # We create worktrees here and pass paths to the brain via context.
    WORKTREE_PATHS=""
    if [ "$AGENT" = "codex" ]; then
        echo "  Creating worktrees for Codex sub-agents..."
        for i in 1 2 3; do
            WT_PATH="/tmp/recursive-worktree-${SESSION_ID}-${i}"
            WT_BRANCH="worktree-${SESSION_ID}-${i}"
            git -C "$REPO_DIR" worktree add "$WT_PATH" -b "$WT_BRANCH" origin/main --quiet 2>/dev/null || true
            if [ -d "$WT_PATH" ]; then
                WORKTREE_PATHS="${WORKTREE_PATHS}${WT_PATH}\n"
            fi
        done
    fi

    # --- Build brain context file ---
    # The brain reads this file for system state before thinking.
    CONTEXT_FILE=$(mktemp)
    cat > "$CONTEXT_FILE" << CTXEOF
<dashboard>
$DASHBOARD_TEXT
</dashboard>

<advisory_recommendation>
$ADVISORY_JSON
</advisory_recommendation>

<session_context>
Session ID: $SESSION_ID
Cycle: $CYCLE
Agent: $AGENT
Brain model: $BRAIN_MODEL
</session_context>

<open_prs>
$OPEN_PRS
</open_prs>
CTXEOF

    # Append worktree paths for Codex sessions
    if [ -n "$WORKTREE_PATHS" ] && [ "$AGENT" = "codex" ]; then
        printf '\n<worktree_paths>\n%b</worktree_paths>\n' "$WORKTREE_PATHS" >> "$CONTEXT_FILE"
    fi

    # For Codex: prepend brain instructions to the context file.
    # Claude loads brain.md via --agent brain; Codex has no equivalent flag,
    # so we inject the brain identity into the prompt itself.
    # developer_instructions (additive) preserves built-in tool knowledge
    # (spawn_agent, send_input, wait_agent) while adding brain identity.
    if [ "$AGENT" = "codex" ]; then
        BRAIN_PROMPT_FILE="$REPO_DIR/.recursive/prompts/brain-codex.md"
        if [ -f "$BRAIN_PROMPT_FILE" ]; then
            BRAIN_TMP=$(mktemp)
            cat "$BRAIN_PROMPT_FILE" > "$BRAIN_TMP"
            printf '\n\n' >> "$BRAIN_TMP"
            cat "$CONTEXT_FILE" >> "$BRAIN_TMP"
            mv "$BRAIN_TMP" "$CONTEXT_FILE"
        fi
    fi

    # --- Run brain agent ---
    LOG_FILE="$SESSION_DIR/raw/${SESSION_ID}.log"
    mkdir -p "$SESSION_DIR/raw"

    set +e
    # Unset CLAUDECODE so nested agent invocations (e.g. nightshift test
    # --agent claude) don't fail with "cannot be launched inside another
    # Claude Code session".  Claude --agent handles this internally;
    # Codex does not, so we clear it for both backends.
    unset CLAUDECODE 2>/dev/null || true

    if [ "$AGENT" = "codex" ]; then
        BRAIN_MODEL="${RECURSIVE_CODEX_MODEL:-gpt-5.4}"
        echo "  Running brain agent ($BRAIN_MODEL via Codex)..."
        # Brain model + reasoning set in .codex/config.toml, NOT CLI flags.
        # Per Codex docs: "Codex reapplies the parent turn's live runtime
        # overrides when it spawns a child... even if the selected custom
        # agent file sets different defaults." CLI --model/-c flags count
        # as runtime overrides and cascade to sub-agents, forcing them onto
        # gpt-5.4/xhigh instead of gpt-5.4-mini/high from their TOML.
        # Config.toml sets the brain model; sub-agent TOMLs override it.
        codex exec \
            --dangerously-bypass-approvals-and-sandbox \
            --json \
            "$(cat "$CONTEXT_FILE")" \
            2>&1 | tee "$LOG_FILE" | python3 -u "$ENGINE_DIR/format-stream.py"
        EXIT_CODE=${PIPESTATUS[0]}
    else
        echo "  Running brain agent ($BRAIN_MODEL via Claude)..."
        claude --agent brain \
            --model "$BRAIN_MODEL" \
            --max-turns 200 \
            --output-format stream-json \
            --verbose \
            -p "$(cat "$CONTEXT_FILE")" \
            2>&1 | tee "$LOG_FILE" | python3 -u "$ENGINE_DIR/format-stream.py"
        EXIT_CODE=${PIPESTATUS[0]}
    fi
    set -e

    rm -f "$CONTEXT_FILE"
    SESSION_END=$(date +%s)
    DURATION_MIN=$(( (SESSION_END - SESSION_START) / 60 ))
    echo "  Brain exited with code $EXIT_CODE (${DURATION_MIN}m)"

    # --- Extract SESSION_ROLE from brain output ---
    # Safety: use awk (not sed) to avoid metacharacter injection from agent-controlled log content.
    # Then restrict to [a-z-] only and validate against the known role list.
    SESSION_ROLE="brain"
    if [ -f "$LOG_FILE" ]; then
        _role_line=$(grep -o 'ROLE DECISION:.*' "$LOG_FILE" 2>/dev/null | tail -1 || true)
        if [ -n "$_role_line" ]; then
            # awk splits on 'ROLE DECISION:' literal -- no metacharacter exposure
            _role_raw=$(echo "$_role_line" | awk -F'ROLE DECISION:' '{print $2}')
            # Strip to [a-z-] only (no spaces, digits, symbols, or shell metacharacters)
            _role_clean=$(echo "$_role_raw" | tr -cd 'a-z-' | head -c 20)
            # Validate against known role list; default to 'unknown' if unrecognised
            case "$_role_clean" in
                build|review|oversee|strategize|achieve|security-check|evolve|audit|brain)
                    SESSION_ROLE="$_role_clean"
                    ;;
                *)
                    SESSION_ROLE="unknown"
                    ;;
            esac
        fi
    fi

    # --- Generate session metadata + structured report ---
    SESSION_META="$SESSION_DIR/raw/${SESSION_ID}.meta.json"
    STRUCTURED_DIR="$SESSION_DIR/structured"
    mkdir -p "$STRUCTURED_DIR"
    _NS_SID="$SESSION_ID" _NS_ROLE="$SESSION_ROLE" _NS_CYCLE="$CYCLE" \
    _NS_EXIT="$EXIT_CODE" _NS_DUR="$DURATION_MIN" _NS_ADV="$ADVISORY_ROLE" \
    _NS_MODEL="$BRAIN_MODEL" _NS_META="$SESSION_META" python3 -c "
import os, json
meta = {
    'session_id': os.environ['_NS_SID'],
    'role': os.environ['_NS_ROLE'],
    'cycle': int(os.environ['_NS_CYCLE']),
    'exit_code': int(os.environ['_NS_EXIT']),
    'duration_min': int(os.environ['_NS_DUR']),
    'advisory': os.environ['_NS_ADV'],
    'model': os.environ['_NS_MODEL'],
}
json.dump(meta, open(os.environ['_NS_META'], 'w'), indent=2)
" 2>/dev/null || true
    STRUCTURED_FILE="$STRUCTURED_DIR/${SESSION_ID}.md"
    echo "  Generating structured report..."
    python3 "$ENGINE_DIR/format-stream.py" --report "$LOG_FILE" --meta "$SESSION_META" > "$STRUCTURED_FILE" 2>/dev/null || true

    # --- Prompt guard check ---
    echo "  Checking prompt integrity..."
    PROMPT_TAMPERED=""
    if ! check_prompt_integrity "$REPO_DIR" "$SNAP_DIR"; then
        echo "  WARNING: Prompt files modified during session!"
        PROMPT_TAMPERED=" [PROMPT MODIFIED]"
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
    fi
    if ! check_origin_integrity "$REPO_DIR" "$SNAP_DIR"; then
        echo "  WARNING: origin/main prompt tampering detected!"
        PROMPT_TAMPERED="${PROMPT_TAMPERED} [ORIGIN MODIFIED]"
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
    fi
    rm -rf "${SNAP_DIR:-}"

    # --- Cost tracking ---
    echo "  Recording costs..."
    COST_MSG_TMP=$(mktemp)
    SESSION_COST_USD=$(_NS_LIB="$RECURSIVE_DIR/lib" _LOG_FILE="$LOG_FILE" \
    _COST_FILE="$COST_FILE" _SESSION_ID="$SESSION_ID" \
    _BRAIN_MODEL="$BRAIN_MODEL" _AGENT_TYPE="$AGENT" python3 -c "
import sys, os
sys.path.insert(0, os.environ['_NS_LIB'])
from costs import record_multi_model_session, total_cost
entry = record_multi_model_session(
    [(os.environ['_LOG_FILE'], os.environ['_BRAIN_MODEL'])],
    os.environ['_COST_FILE'], os.environ['_SESSION_ID'],
    agent_type=os.environ['_AGENT_TYPE'])
cumulative = total_cost(os.environ['_COST_FILE'])
print(entry['cost_usd'])
import sys as _sys
print(f'  Session: \${entry[\"cost_usd\"]:.4f} | Cumulative: \${cumulative:.2f}', file=_sys.stderr)
" 2>"$COST_MSG_TMP" || echo "0.0000")
    cat "$COST_MSG_TMP" 2>/dev/null || true
    rm -f "$COST_MSG_TMP"

    # --- Session index row ---
    echo "  Appending session index row..."
    append_session_index_row \
        "$INDEX_FILE" \
        "$LOG_FILE" \
        "$SESSION_ID" \
        "$SESSION_ROLE" \
        "$EXIT_CODE" \
        "$DURATION_MIN" \
        "${SESSION_COST_USD:-0.0000}" \
        "${PROMPT_TAMPERED:-}" \
        2>/dev/null || true

    # --- Selective git add (runtime state only, not framework) ---
    echo "  Committing runtime state..."
    for dir in handoffs tasks sessions learnings evaluations autonomy \
               strategy healer reviews friction decisions commitments \
               incidents vision vision-tracker changelog architecture plans \
               security; do
        git -C "$REPO_DIR" add ".recursive/$dir/" 2>/dev/null || true
    done
    git -C "$REPO_DIR" commit -m "session: brain #$CYCLE ($SESSION_ID)" --quiet 2>/dev/null || true
    git -C "$REPO_DIR" push origin main --quiet 2>/dev/null || true

    # --- Budget check ---
    CUMULATIVE=$(_NS_LIB="$RECURSIVE_DIR/lib" _COST_FILE="$COST_FILE" python3 -c "
import sys, os
sys.path.insert(0, os.environ['_NS_LIB'])
from costs import total_cost
print(f'{total_cost(os.environ[\"_COST_FILE\"]):.2f}')
" 2>/dev/null || echo "0.00")
    echo "  Budget: \$$CUMULATIVE / \$$BUDGET_LIMIT"
    if _CUMULATIVE="$CUMULATIVE" _BUDGET_LIMIT="$BUDGET_LIMIT" python3 -c "
import os; exit(0 if float(os.environ['_CUMULATIVE']) >= float(os.environ['_BUDGET_LIMIT']) else 1)
" 2>/dev/null; then
        echo "Budget limit reached (\$$CUMULATIVE >= \$$BUDGET_LIMIT). Stopping."
        break
    fi

    # --- Circuit breaker ---
    if [ "$EXIT_CODE" -ne 0 ]; then
        if is_auth_failure "$LOG_FILE" 2>/dev/null; then
            echo "  Auth failure detected -- not counting toward circuit breaker"
        else
            CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        fi
    else
        CONSECUTIVE_FAILURES=0
    fi

    if [ "$CONSECUTIVE_FAILURES" -ge "$MAX_CONSECUTIVE_FAILURES" ]; then
        echo "Circuit breaker: $CONSECUTIVE_FAILURES consecutive failures. Stopping."
        break
    fi

    # --- Worktree cleanup ---
    echo "  Cleaning up worktrees..."
    cleanup_worktrees

    echo "  Cycle $CYCLE complete."
done

echo ""
echo "=== Daemon v2 stopped after $CYCLE cycles ==="
