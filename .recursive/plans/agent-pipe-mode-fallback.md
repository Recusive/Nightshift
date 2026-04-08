# Agent() Pipe Mode Fallback Architecture

## Problem

The v2 architecture assumes the brain (Opus) can use `Agent()` with `isolation: "worktree"` to spawn sub-agents from within a `claude -p` pipe mode session. If this doesn't work, we need an alternative delegation mechanism.

## Recommended Fallback: Daemon-Level Subprocess Delegation

Instead of the brain spawning sub-agents via Agent(), the brain writes delegation instructions to a structured file. The daemon reads them and launches sub-agents as separate `claude -p` subprocess calls.

### Flow

```
daemon.sh                    brain (Opus)              sub-agent (Sonnet)
    |                            |                          |
    |--- launch brain ---------->|                          |
    |                            |-- thinks, decides ------>|
    |                            |-- writes delegation.json |
    |                            |-- exits with code 0      |
    |<-- brain exits ------------|                          |
    |                                                       |
    |--- reads delegation.json                              |
    |--- for each delegation:                               |
    |       launch claude -p --->|------------------------->|
    |       wait for exit        |    sub-agent works       |
    |<-- sub-agent exits --------|<-------------------------|
    |                                                       |
    |--- launch brain (review phase) ---------------------->|
    |                            |-- reviews PRs            |
    |                            |-- writes merge decisions |
    |<-- brain exits ------------|                          |
```

### Delegation File Format

The brain writes `.recursive/delegation.json`:

```json
{
  "session_id": "20260408-120000",
  "delegations": [
    {
      "agent": "build",
      "prompt": "Build task #0042. Read CLAUDE.md first. Create a PR.",
      "model": "claude-sonnet-4-6",
      "isolation": "worktree",
      "zone": "project",
      "priority": 1
    },
    {
      "agent": "security",
      "prompt": "Run pentest. Read .recursive/handoffs/LATEST.md first.",
      "model": "claude-sonnet-4-6",
      "isolation": "worktree",
      "zone": "project",
      "priority": 2
    }
  ]
}
```

### Daemon Implementation

```bash
# After brain exits, check for delegation file
DELEGATION_FILE="$REPO_DIR/.recursive/delegation.json"
if [ -f "$DELEGATION_FILE" ]; then
    # Parse delegations
    DELEGATION_COUNT=$(python3 -c "
import json
with open('$DELEGATION_FILE') as f:
    print(len(json.load(f)['delegations']))
")

    for i in $(seq 0 $((DELEGATION_COUNT - 1))); do
        # Extract delegation details
        AGENT_NAME=$(python3 -c "import json; d=json.load(open('$DELEGATION_FILE')); print(d['delegations'][$i]['agent'])")
        AGENT_PROMPT=$(python3 -c "import json; d=json.load(open('$DELEGATION_FILE')); print(d['delegations'][$i]['prompt'])")
        AGENT_MODEL=$(python3 -c "import json; d=json.load(open('$DELEGATION_FILE')); print(d['delegations'][$i].get('model','claude-sonnet-4-6'))")

        # Launch sub-agent in worktree
        WORKTREE_DIR=$(mktemp -d /tmp/recursive-worktree-XXXXXX)
        git worktree add "$WORKTREE_DIR" origin/main -b "agent/${AGENT_NAME}-${SESSION_ID}" 2>/dev/null

        claude -p "$AGENT_PROMPT" \
            --model "$AGENT_MODEL" \
            --max-turns 200 \
            --output-format stream-json \
            --allowedTools "Bash,Read,Write,Edit,Glob,Grep" \
            --cwd "$WORKTREE_DIR" \
            > "$SESSION_DIR/raw/${SESSION_ID}-${AGENT_NAME}.log" 2>&1

        # Clean up worktree
        git worktree remove "$WORKTREE_DIR" 2>/dev/null || true
    done

    # Re-launch brain for review phase
    claude -p "Review phase. Check open PRs created by sub-agents. Review and merge." \
        --agent brain --model "$BRAIN_MODEL" --max-turns 50 \
        > "$SESSION_DIR/raw/${SESSION_ID}-review.log" 2>&1

    rm -f "$DELEGATION_FILE"
fi
```

### Trade-offs vs Agent()

| Aspect | Agent() (primary) | Subprocess (fallback) |
|--------|-------------------|----------------------|
| Context sharing | Brain sees sub-agent output inline | Brain reads sub-agent output from files |
| Parallelism | Brain launches parallel Agent() calls | Daemon serializes or uses `&` + `wait` |
| Review loop | Brain reviews immediately after sub-agent returns | Separate review phase after all sub-agents finish |
| Error handling | Brain catches errors inline | Daemon checks exit codes between launches |
| Cost tracking | Single session cost | Must aggregate across subprocess logs |
| Complexity | Lower (single process) | Higher (multi-process orchestration) |

### When to Use

Run the spike test first:
```bash
claude -p "Launch a sub-agent: Agent(subagent_type: 'build', prompt: 'echo hello', isolation: 'worktree')" \
    --model claude-opus-4-6 --output-format stream-json
```

If Agent() returns results: use Agent() (primary path).
If Agent() errors or is unavailable: implement this fallback in daemon.sh.
