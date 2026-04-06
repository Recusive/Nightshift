#!/bin/bash
# ----------------------------------------------
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
# ----------------------------------------------

# ----------------------------------------------
# Prompt Self-Modification Guard
#
# Detects if the agent modified prompt/control files during a cycle.
# These files control agent behavior -- unauthorized changes could
# corrupt all future sessions.
# ----------------------------------------------

PROMPT_GUARD_FILES=(
    "AGENTS.md"
    "CLAUDE.md"
    "docs/prompt/evolve.md"
    "docs/prompt/evolve-auto.md"
    "docs/prompt/pentest.md"
    "docs/prompt/review.md"
    "docs/prompt/overseer.md"
    "docs/prompt/strategist.md"
    "docs/prompt/achieve.md"
    "docs/prompt/harden-daemon.md"
    "scripts/daemon.sh"
    "scripts/lib-agent.sh"
    "scripts/pick-role.py"
    "scripts/check.sh"
    "scripts/format-stream.py"
    ".nightshift.json"
    ".github/workflows/ci.yml"
    ".github/workflows/notify-orbitweb.yml"
    # docs/prompt/healer.md is a reference doc, not a control file (healer merged into builder step)
)

# Directories to scan for new prompt-like files post-cycle.
PROMPT_GUARD_DIRS=(
    "docs/prompt"
    "docs/prompt/feedback"
    "scripts"
    ".github/workflows"
)

# save_prompt_snapshots REPO_DIR
# Copies all prompt files to a temp directory for comparison after the cycle.
# Also saves a directory listing of watched directories to detect new files.
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
    # Save directory listings for new-file detection
    for d in "${PROMPT_GUARD_DIRS[@]}"; do
        local src_dir="$repo_dir/$d"
        if [ -d "$src_dir" ]; then
            local listing="$snap_dir/${d}.filelist"
            mkdir -p "$(dirname "$listing")"
            LC_ALL=C ls -1 "$src_dir" 2>/dev/null | LC_ALL=C sort > "$listing"
        fi
    done
    # Record origin/main commit hash so check_origin_integrity can detect pushes
    # that bypass the working-tree guard (blind spot described in pentest #0072).
    git -C "$repo_dir" rev-parse origin/main 2>/dev/null > "$snap_dir/origin-main-hash" || true
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

    # Detect new files in watched directories
    for d in "${PROMPT_GUARD_DIRS[@]}"; do
        local current_dir="$repo_dir/$d"
        local listing="$snap_dir/${d}.filelist"
        if [ -d "$current_dir" ] && [ -f "$listing" ]; then
            local current_listing
            current_listing=$(LC_ALL=C ls -1 "$current_dir" 2>/dev/null | LC_ALL=C sort)
            local new_files
            new_files=$(comm -13 "$listing" <(printf '%s\n' "$current_listing"))
            if [ -n "$new_files" ]; then
                if [ "$changed" -eq 0 ]; then
                    echo ""
                    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                    echo "  PROMPT SELF-MODIFICATION DETECTED"
                    echo "  The agent modified files that control its behavior."
                    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                fi
                echo ""
                echo "NEW FILES in $d/:"
                echo "$new_files"
                alert_body="${alert_body}NEW FILES in ${d}/:"$'\n'"${new_files}"$'\n\n'
                changed=1
            fi
        elif [ -d "$current_dir" ] && [ ! -f "$listing" ]; then
            # Directory was created during the cycle (did not exist at snapshot time)
            local new_files
            new_files=$(ls -1 "$current_dir" 2>/dev/null)
            if [ -n "$new_files" ]; then
                if [ "$changed" -eq 0 ]; then
                    echo ""
                    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                    echo "  PROMPT SELF-MODIFICATION DETECTED"
                    echo "  The agent modified files that control its behavior."
                    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                fi
                echo ""
                echo "NEW DIRECTORY $d/ with files:"
                echo "$new_files"
                alert_body="${alert_body}NEW DIRECTORY ${d}/ with files:"$'\n'"${new_files}"$'\n\n'
                changed=1
            fi
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

# check_origin_integrity REPO_DIR SNAPSHOT_DIR [ALERT_FILE]
# Blind-spot guard: detects if the agent pushed prompt/control file changes to
# origin/main without touching the working tree, which bypasses check_prompt_integrity
# (which only diffs the working tree against the snapshot).
#
# Algorithm:
#   1. Read the origin/main commit hash saved by save_prompt_snapshots.
#   2. Fetch latest origin state.
#   3. If the hash changed, diff each PROMPT_GUARD_FILE on origin/main against
#      the snapshot copy taken before the agent ran.
#   4. If any guard file changed: log details, write to ALERT_FILE, restore the
#      snapshot version of each changed file, and force-push the revert to
#      origin/main so that the subsequent reset_repo_state pulls a clean state.
#
# Returns 0 if clean (or PR merge -- legitimate workflow),
#         1 if tampering detected and revert succeeded,
#         2 if tampering detected but revert FAILED.
check_origin_integrity() {
    local repo_dir="$1"
    local snap_dir="$2"
    local alert_file="${3:-}"
    local changed=0
    local alert_body=""

    # Read the pre-session origin/main hash
    local snap_hash
    snap_hash=$(cat "$snap_dir/origin-main-hash" 2>/dev/null || true)
    if [ -z "$snap_hash" ]; then
        # No hash recorded (e.g., no remote configured) -- skip silently
        return 0
    fi

    # Fetch latest origin state
    git -C "$repo_dir" fetch origin --quiet 2>/dev/null || true

    # Get current origin/main hash
    local current_hash
    current_hash=$(git -C "$repo_dir" rev-parse origin/main 2>/dev/null || true)

    # If hash unchanged, no push occurred during the agent cycle
    if [ -z "$current_hash" ] || [ "$snap_hash" = "$current_hash" ]; then
        return 0
    fi

    # Distinguish PR merges from direct pushes.  gh pr merge --merge creates
    # merge commits (2+ parents).  If every first-parent commit between snap
    # and current is a merge commit, the changes came through the PR workflow
    # and should NOT be reverted.  --no-merges excludes merge commits, so an
    # empty result means all mainline commits are merges.
    local direct_push_commits
    direct_push_commits=$(git -C "$repo_dir" rev-list --first-parent --no-merges \
        "$snap_hash..$current_hash" 2>/dev/null || true)
    if [ -z "$direct_push_commits" ]; then
        return 0
    fi

    # Hash changed -- inspect which guard files were modified on origin/main.
    # Use a single temp file (truncated per iteration) to avoid trailing-newline
    # stripping from command substitution and mktemp-failure leak in a loop.
    local files_to_restore=()
    local origin_tmp
    origin_tmp=$(mktemp) || return 0  # Can't create tmpfile; skip check
    for f in "${PROMPT_GUARD_FILES[@]}"; do
        local snapshot="$snap_dir/$f"
        [ -f "$snapshot" ] || continue
        : > "$origin_tmp"  # truncate between iterations
        git -C "$repo_dir" show "origin/main:$f" > "$origin_tmp" 2>/dev/null || continue
        if ! diff -q "$snapshot" "$origin_tmp" >/dev/null 2>&1; then
            if [ "$changed" -eq 0 ]; then
                echo ""
                echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                echo "  PROMPT GUARD: origin/main MODIFIED DURING AGENT CYCLE"
                echo "  An agent pushed prompt/control file changes to origin/main"
                echo "  without touching the working tree (blind spot attack)."
                echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            fi
            echo ""
            echo "ORIGIN/MAIN CHANGED: $f"
            local file_diff
            file_diff=$(diff -u "$snapshot" "$origin_tmp" 2>/dev/null || true)
            echo "$file_diff"
            alert_body="${alert_body}ORIGIN/MAIN CHANGED: ${f}"$'\n'"${file_diff}"$'\n\n'
            changed=1
            files_to_restore+=("$f")
        fi
    done
    rm -f "$origin_tmp"

    if [ "$changed" -ne 0 ]; then
        echo ""
        echo "  Reverting origin/main guard files to pre-session snapshot..."
        local revert_failed=0
        for f in "${files_to_restore[@]}"; do
            cp "$snap_dir/$f" "$repo_dir/$f" 2>/dev/null || revert_failed=1
        done
        if [ "$revert_failed" -eq 0 ]; then
            git -C "$repo_dir" add -- "${files_to_restore[@]}" 2>/dev/null || true
            git -C "$repo_dir" \
                commit -m "security: revert prompt guard files pushed by agent session" \
                --quiet 2>/dev/null || true
            # Force-push is intentional here: the tampered origin/main commit is
            # ahead of the pre-session hash, so a regular push would be rejected
            # as non-fast-forward. This is an emergency exception to the no-direct-
            # push-to-main rule, analogous to the housekeeping carve-out.
            if git -C "$repo_dir" push origin main --force --quiet 2>/dev/null; then
                echo "  Reverted origin/main to pre-session state."
            else
                echo "  WARNING: Revert push failed -- origin/main may still contain tampered files."
                revert_failed=1
            fi
        else
            echo "  WARNING: Could not restore snapshot files -- revert push skipped."
        fi
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"

        if [ -n "$alert_file" ]; then
            {
                printf '\n'
                echo "PROMPT GUARD: ORIGIN/MAIN MODIFICATION DETECTED"
                echo "================================================="
                echo "An agent pushed prompt/control file changes to origin/main"
                echo "without touching the working tree (blind spot attack)."
                echo "Revert was attempted -- see daemon log for result."
                printf '\n'
                echo "$alert_body"
            } >> "$alert_file"
        fi
    fi

    if [ "$changed" -ne 0 ]; then
        # 1 = tampered + reverted OK, 2 = tampered + revert failed
        [ "$revert_failed" -ne 0 ] && return 2
        return 1
    fi
    return 0
}

# ----------------------------------------------
# Cleanup: Log Rotation + Orphan Branch Pruning
#
# Called at the start of each daemon cycle to
# bound disk usage and clean up stale branches.
# ----------------------------------------------

# cleanup_old_logs LOG_DIR KEEP_DAYS
# Deletes .log files older than KEEP_DAYS days.
cleanup_old_logs() {
    local log_dir="$1"
    local keep_days="${2:-7}"
    local result

    case "$keep_days" in
        ''|*[!0-9]*)
            echo "  Log rotation error: keep_days must be numeric: $keep_days"
            return 0
            ;;
    esac

    result=$(PYTHONPATH="$REPO_DIR" python3 -c "
from nightshift.cleanup import rotate_logs
r = rotate_logs('$log_dir', $keep_days)
if r['deleted']:
    print(f\"  Rotated {len(r['deleted'])} old log(s) (>${keep_days}d)\")
for e in r['errors']:
    print(f\"  Log rotation error: {e}\")
" 2>/dev/null) || true
    if [ -n "$result" ]; then
        echo "$result"
    fi
}

# cleanup_healer_log LOG_PATH KEEP_ENTRIES
# Archives old healer entries and keeps only the most recent sections live.
cleanup_healer_log() {
    local log_path="$1"
    local keep_entries="${2:-50}"
    local result

    case "$keep_entries" in
        ''|*[!0-9]*)
            echo "  Healer rotation error: keep_entries must be numeric: $keep_entries"
            return 0
            ;;
    esac

    result=$(PYTHONPATH="$REPO_DIR" python3 - "$log_path" "$keep_entries" <<'PY' 2>/dev/null
from pathlib import Path
import sys

from nightshift.cleanup import rotate_healer_log

log_path = sys.argv[1]
keep_entries = int(sys.argv[2])
result = rotate_healer_log(log_path, keep_entries=keep_entries)
if result["rotated_entries"]:
    archived = ", ".join(Path(path).name for path in result["archived_files"])
    print(
        f"  Archived {result['rotated_entries']} healer entr"
        f"{'y' if result['rotated_entries'] == 1 else 'ies'} "
        f"(kept {result['kept_entries']})"
        + (f" -> {archived}" if archived else "")
    )
for error in result["errors"]:
    print(f"  Healer rotation error: {error}")
PY
) || true

    if [ -n "$result" ]; then
        echo "$result"
    fi
}

# cleanup_orphan_branches
# Prunes remote branches from nightshift that have no open PR.
cleanup_orphan_branches() {
    local result
    result=$(PYTHONPATH="$REPO_DIR" python3 -c "
from nightshift.cleanup import prune_orphan_branches
r = prune_orphan_branches('$REPO_DIR')
if r['pruned']:
    print(f\"  Pruned {len(r['pruned'])} orphan branch(es): {', '.join(r['pruned'])}\")
for e in r['errors']:
    print(f\"  Branch prune error: {e}\")
" 2>/dev/null) || true
    if [ -n "$result" ]; then
        echo "$result"
    fi
}

# ----------------------------------------------
# Task Archival
#
# Moves done tasks to archive/ to keep the
# active directory small.
# ----------------------------------------------

# archive_done_tasks TASKS_DIR
# Moves status: done task files to TASKS_DIR/archive/.
archive_done_tasks() {
    local tasks_dir="$1"
    local archive_dir="$tasks_dir/archive"
    local count=0

    mkdir -p "$archive_dir"

    for f in "$tasks_dir"/0*.md; do
        [ -f "$f" ] || continue
        if head -7 "$f" | grep -q "^status: done" 2>/dev/null; then
            mv "$f" "$archive_dir/"
            count=$((count + 1))
        fi
    done

    if [ "$count" -gt 0 ]; then
        echo "  Archived $count done task(s) to archive/"
        git add -A "$tasks_dir/" 2>/dev/null || true
        git commit -m "task: archive $count done task(s)" --quiet 2>/dev/null || true
        git push origin main --quiet 2>/dev/null || true
    fi
}

# ----------------------------------------------
# Handoff Compaction
#
# Compacts numbered handoff files into weekly
# summaries when 7+ files accumulate.
# ----------------------------------------------

# compact_handoffs HANDOFFS_DIR
# Runs Python-backed compaction on numbered handoff files.
compact_handoffs() {
    local handoffs_dir="$1"
    local result
    result=$(_NIGHTSHIFT_HDIR="$handoffs_dir" PYTHONPATH="$REPO_DIR" python3 -c "
import os
from nightshift.compact import compact_handoffs
r = compact_handoffs(os.environ['_NIGHTSHIFT_HDIR'])
if r['compacted']:
    print(f\"  Compacted {len(r['compacted'])} handoff(s) into {r['weekly_file']}\")
for e in r['errors']:
    print(f\"  Compaction error: {e}\")
" 2>/dev/null) || true
    if [ -n "$result" ]; then
        echo "$result"
        git add -A "$handoffs_dir/" 2>/dev/null || true
        git commit -m "docs: compact old handoffs" --quiet 2>/dev/null || true
        git push origin main --quiet 2>/dev/null || true
    fi
}

# ----------------------------------------------
# GitHub Issues -> Task Sync
#
# Converts GitHub Issues labeled "task" into
# docs/tasks/ files. Humans create issues, the
# daemon converts them to task files on startup.
# ----------------------------------------------

# sync_github_tasks TASKS_DIR
# Syncs GitHub Issues labeled "task" to docs/tasks/ files.
# Closes each issue with a "Converted to task #NNNN" comment.
# Fails silently on all errors -- never crashes the daemon.
sync_github_tasks() {
    local tasks_dir="$1"
    local next_id_file="$tasks_dir/.next-id"
    local count=0

    # Bail if gh is not available or not authenticated
    if ! command -v gh >/dev/null 2>&1; then
        return 0
    fi

    # Fetch open issues labeled "task" as JSON
    local issues_json
    issues_json=$(gh issue list --label "task" --state open --json number,title,body,labels --limit 50 2>/dev/null) || return 0

    # Check if there are any issues
    local issue_count
    issue_count=$(printf '%s' "$issues_json" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null) || return 0
    if [ "$issue_count" = "0" ] || [ -z "$issue_count" ]; then
        return 0
    fi

    # Process each issue via Python (handles JSON safely, avoids shell expansion)
    local new_files
    new_files=$(printf '%s' "$issues_json" | _TASKS_DIR="$tasks_dir" _NEXT_ID_FILE="$next_id_file" python3 -c "
import json, os, sys, datetime

tasks_dir = os.environ['_TASKS_DIR']
next_id_file = os.environ['_NEXT_ID_FILE']
issues = json.load(sys.stdin)
today = datetime.date.today().isoformat()
created_files = []

for issue in issues:
    # Read next-id
    try:
        with open(next_id_file) as f:
            next_id = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        next_id = 1

    task_num = f'{next_id:04d}'
    task_file = os.path.join(tasks_dir, f'{task_num}.md')

    # Guard: skip if task file already exists (stale .next-id)
    if os.path.exists(task_file):
        continue

    # Map labels to frontmatter fields
    label_names = [lb.get('name', '') for lb in issue.get('labels', [])]

    priority = 'normal'
    if 'urgent' in label_names:
        priority = 'urgent'
    elif 'low' in label_names:
        priority = 'low'

    environment = ''
    if 'integration' in label_names:
        environment = 'integration'

    vision_section = ''
    for vs in ('loop1', 'loop2', 'self-maintaining', 'meta-prompt'):
        if vs in label_names:
            vision_section = vs
            break

    # Build frontmatter
    fm_lines = [
        '---',
        'status: pending',
        f'priority: {priority}',
        'target:',
    ]
    if environment:
        fm_lines.append(f'environment: {environment}')
    if vision_section:
        fm_lines.append(f'vision_section: {vision_section}')
    fm_lines.extend([
        f'created: {today}',
        f'source: github-issue-{issue[\"number\"]}',
        'completed:',
        '---',
    ])

    # Build body
    title = issue.get('title', 'Untitled')
    body = issue.get('body', '') or ''

    content = '\\n'.join(fm_lines) + f'\\n\\n# {title}\\n'
    if body.strip():
        content += f'\\n{body.strip()}\\n'

    # Write task file
    with open(task_file, 'w') as f:
        f.write(content)

    # Increment next-id
    with open(next_id_file, 'w') as f:
        f.write(str(next_id + 1) + '\\n')

    created_files.append((task_num, issue['number'], title))

for task_num, issue_num, title in created_files:
    print(f'{task_num}:{issue_num}:{title}')
" 2>/dev/null) || return 0

    if [ -z "$new_files" ]; then
        return 0
    fi

    # Close each issue with a comment and commit the task files
    local task_files_to_add=""
    while IFS=: read -r task_num issue_num title; do
        [ -z "$task_num" ] && continue
        gh issue comment "$issue_num" --body "Converted to task #${task_num}" 2>/dev/null || true
        gh issue close "$issue_num" 2>/dev/null || true
        task_files_to_add="$task_files_to_add $tasks_dir/${task_num}.md"
        count=$((count + 1))
    done <<< "$new_files"

    # Commit the new task files (on main, before the session starts)
    if [ "$count" -gt 0 ] && [ -n "$task_files_to_add" ]; then
        # shellcheck disable=SC2086
        git add $task_files_to_add "$next_id_file" 2>/dev/null || true
        git commit -m "task: sync $count GitHub issue(s) to task files" --quiet 2>/dev/null || true
        git push origin main --quiet 2>/dev/null || true
        echo "  Synced $count GitHub issue(s) to task files"
    fi
}

# ----------------------------------------------
# Self-Evaluation
#
# Runs nightshift against a test target every N
# sessions to score quality and create follow-up
# tasks for low-scoring dimensions.
# ----------------------------------------------

# should_evaluate SESSION_COUNT
# Returns 0 (true) if it's time for an evaluation.
# Reads eval_frequency from .nightshift.json (default 5, 0=disabled).
should_evaluate() {
    local session_count="${1:-0}"
    local freq
    freq=$(PYTHONPATH="$REPO_DIR" python3 -c "
from nightshift.config import merge_config
from pathlib import Path
c = merge_config(Path('${REPO_DIR:-.}'))
print(c['eval_frequency'])
" 2>/dev/null) || freq="5"

    if [ "$freq" = "0" ] || [ -z "$freq" ]; then
        return 1  # disabled
    fi

    if [ "$session_count" -gt 0 ] && [ $(( session_count % freq )) -eq 0 ]; then
        return 0  # time to evaluate
    fi
    return 1
}

# run_evaluation AGENT [AFTER_TASK]
# Runs a self-evaluation cycle. Non-blocking: logs errors and returns 0.
run_evaluation() {
    local agent="$1"
    local after_task="${2:-}"
    echo "  Running self-evaluation..."
    local result
    result=$(PYTHONPATH="$REPO_DIR" _AFTER_TASK="$after_task" python3 -c "
import os, json
from pathlib import Path
from nightshift.evaluation import evaluate
from nightshift.config import merge_config

cfg = merge_config(Path('${REPO_DIR:-.}'))
r = evaluate(
    target_repo=cfg['eval_target_repo'],
    agent='$agent',
    nightshift_dir=Path('${REPO_DIR:-.}'),
    eval_dir=Path('${REPO_DIR:-.}/docs/evaluations'),
    task_dir=Path('${REPO_DIR:-.}/docs/tasks'),
    after_task=os.environ.get('_AFTER_TASK', ''),
)
print(f\"  Evaluation #{r['evaluation_id']:04d}: {r['total_score']}/{r['max_total']}\")
if r['tasks_created']:
    print(f\"  Created {len(r['tasks_created'])} follow-up task(s)\")
" 2>/dev/null) || result="  Evaluation failed (non-blocking)"
    echo "$result"
}

# ----------------------------------------------
# Agent Configuration
# ----------------------------------------------

# Configurable models -- override via environment
CLAUDE_MODEL="${NIGHTSHIFT_CLAUDE_MODEL:-claude-opus-4-6}"
CODEX_MODEL="${NIGHTSHIFT_CODEX_MODEL:-gpt-5.4}"
CODEX_THINKING="${NIGHTSHIFT_CODEX_THINKING:-extra_high}"

# ----------------------------------------------
# Interactive Setup
#
# Prompts user for agent and duration when daemon
# is run without arguments. Sets global variables.
# ----------------------------------------------

# interactive_setup DAEMON_LABEL
# Prompts for agent choice and duration, then confirms.
# Sets globals: AGENT, MAX_SESSIONS
# Skipped when the daemon is called with positional args.
interactive_setup() {
    local daemon_label="${1:-daemon}"
    local agent_choice
    local duration_choice
    local hours

    echo ""
    echo "Which agent should run this shift?"
    echo "  1) claude"
    echo "  2) codex"
    printf "Enter choice [1]: "
    read -r agent_choice
    case "${agent_choice:-1}" in
        1) AGENT="claude" ;;
        2) AGENT="codex" ;;
        *) echo "Invalid choice. Using claude."; AGENT="claude" ;;
    esac

    echo ""
    echo "How long should the daemon run?"
    echo "  1) 2 hours"
    echo "  2) 4 hours"
    echo "  3) 6 hours"
    echo "  4) 8 hours (overnight)"
    echo "  5) Unlimited (until you stop it)"
    printf "Enter choice [4]: "
    read -r duration_choice
    case "${duration_choice:-4}" in
        1) hours=2 ;;
        2) hours=4 ;;
        3) hours=6 ;;
        4) hours=8 ;;
        5) hours=0 ;;
        *) echo "Invalid choice. Using 8 hours."; hours=8 ;;
    esac

    if [ "$hours" -gt 0 ]; then
        MAX_SESSIONS=$(( hours * 2 ))
        local est_label="${hours} hours (~${MAX_SESSIONS} sessions)"
    else
        MAX_SESSIONS=0
        local est_label="Unlimited (until you stop it)"
    fi

    local budget_choice
    echo ""
    echo "Set a spending limit? (USD, stops daemon when reached)"
    echo "  1) \$25"
    echo "  2) \$50"
    echo "  3) \$100"
    echo "  4) No limit"
    printf "Enter choice [4]: "
    read -r budget_choice
    case "${budget_choice:-4}" in
        1) BUDGET=25 ;;
        2) BUDGET=50 ;;
        3) BUDGET=100 ;;
        4) BUDGET=0 ;;
        *) echo "Invalid choice. No limit set."; BUDGET=0 ;;
    esac

    if [ "$BUDGET" != "0" ]; then
        local budget_label="\$$BUDGET"
    else
        local budget_label="Unlimited"
    fi

    echo ""
    echo "Starting Nightshift ${daemon_label}:"
    echo "  Agent:    $AGENT"
    echo "  Duration: $est_label"
    echo "  Budget:   $budget_label"
    echo ""
    printf "Press Enter to start or Ctrl+C to cancel. "
    read -r
}

# interactive_setup_strategist
# Prompts for agent choice only (strategist runs once).
# Sets global: AGENT
interactive_setup_strategist() {
    local agent_choice

    echo ""
    echo "Which agent should run this review?"
    echo "  1) claude"
    echo "  2) codex"
    printf "Enter choice [1]: "
    read -r agent_choice
    case "${agent_choice:-1}" in
        1) AGENT="claude" ;;
        2) AGENT="codex" ;;
        *) echo "Invalid choice. Using claude."; AGENT="claude" ;;
    esac

    echo ""
    echo "Starting Nightshift strategist:"
    echo "  Agent: $AGENT"
    echo "  Mode:  single run (advisory)"
    echo ""
    printf "Press Enter to start or Ctrl+C to cancel. "
    read -r
}

# ----------------------------------------------
# Agent Runner
# ----------------------------------------------

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
                2>&1 | tee "$log_file" | python3 -u "$SCRIPT_DIR/format-stream.py"
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
                --effort "${CLAUDE_EFFORT:-max}" \
                --output-format stream-json \
                --verbose \
                2>&1 | tee "$log_file" | python3 -u "$SCRIPT_DIR/format-stream.py"
            EXIT_CODE=${PIPESTATUS[0]}
            ;;
        *)
            echo "ERROR: Unknown agent '$agent'. Supported: claude, codex"
            EXIT_CODE=1
            ;;
    esac
    set -e
}

# extract_result_summary LOG_FILE [MAX_CHARS] [MAX_LINES]
# Pull the final result text out of a stream-json session log and trim it for
# safe prompt injection into a follow-up agent run.
extract_result_summary() {
    local log_file="$1"
    local max_chars="${2:-4000}"
    local max_lines="${3:-40}"

    python3 - "$log_file" "$max_chars" "$max_lines" <<'PY'
import json
import sys
from pathlib import Path

log_path = Path(sys.argv[1])
max_chars = int(sys.argv[2])
max_lines = int(sys.argv[3])

if not log_path.exists():
    raise SystemExit(0)

result_text = ""
for raw_line in log_path.read_text(encoding="utf-8").splitlines():
    stripped = raw_line.strip()
    if not stripped:
        continue
    try:
        event = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        continue
    if event.get("type") != "result":
        continue
    payload = event.get("result")
    if isinstance(payload, str) and payload.strip():
        result_text = payload.strip()

if not result_text:
    raise SystemExit(0)

lines = [line.rstrip() for line in result_text.splitlines()]
trimmed = "\n".join(lines[:max_lines]).strip()
if len(trimmed) > max_chars:
    trimmed = trimmed[: max_chars - 3].rstrip() + "..."

print(trimmed)
PY
}

# ----------------------------------------------
# Human Escalation
#
# Creates a GitHub issue (and optionally fires a
# webhook) when the system needs human attention.
# Fails silently -- never crashes the daemon.
# ----------------------------------------------

# notify_human TITLE BODY
# Creates a GitHub issue with the "needs-human" label.
# If .nightshift.json contains "notification_webhook", also POSTs there.
notify_human() {
    local title="$1"
    local body="${2:-No additional details.}"

    # Always: create GitHub issue
    gh issue create \
        --title "[Nightshift] $title" \
        --label "needs-human" \
        --body "$body" 2>/dev/null || true

    # Optional: webhook (Slack, Discord, etc.)
    local webhook
    webhook=$(python3 -c "
import json, pathlib
p = pathlib.Path('${REPO_DIR:-.}') / '.nightshift.json'
if p.exists():
    cfg = json.loads(p.read_text())
    print(cfg.get('notification_webhook', ''))
" 2>/dev/null || true)
    if [ -n "$webhook" ]; then
        local payload
        payload=$(python3 -c "
import json, sys
print(json.dumps({'text': '[Nightshift] ' + sys.argv[1]}))
" "$title" 2>/dev/null) || payload='{"text":"[Nightshift] notification"}'
        curl -s -X POST \
            -H 'Content-Type: application/json' \
            -d "$payload" \
            "$webhook" >/dev/null 2>&1 || true
    fi
}
