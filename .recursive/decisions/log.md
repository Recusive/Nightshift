# Decision Journal

## 2026-04-07 -- Phase 0 Step 0: Agent() Pipe Mode Spike
**Test**: Launched `claude -p` with a prompt that used the Agent tool to spawn a sub-agent. Sub-agent read AGENTS.md and returned `SPIKE-RESULT: # AGENTS.md ## MANDATORY: Session`.
**Result**: SPIKE-PASS. Agent() tool is available in pipe mode, sub-agents execute and return results to parent. No zombie worktrees created.
**Decision**: Proceed with plan as-is. Agent() with `isolation: "worktree"` confirmed working for sub-agent delegation.
