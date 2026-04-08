# Decision Journal

## 2026-04-07 -- Phase 0 Step 0: Agent() Pipe Mode Spike
**Test**: Launched `claude -p` with a prompt that used the Agent tool to spawn a sub-agent. Sub-agent read AGENTS.md and returned `SPIKE-RESULT: # AGENTS.md ## MANDATORY: Session`.
**Result**: SPIKE-PASS. Agent() tool is available in pipe mode, sub-agents execute and return results to parent. No zombie worktrees created.
**Decision**: Proceed with plan as-is. Agent() with `isolation: "worktree"` confirmed working for sub-agent delegation.

## 2026-04-08 -- Session #0107
**Advisory**: security-check (score 75), audit (score 75, tied)
**Decision**: Overrode to AUDIT + EVOLVE in parallel. Rationale: (1) Audit never run in 76 sessions -- framework docs severely stale. (2) Last session already fixed security findings; running another scan before fixing #0201 would re-find the same lib-agent.sh issue. (3) Evolve fixes #0201 (confirmed security vuln in Tier 1 file) which hardens the codebase for the NEXT security scan. Security-check deferred to next session against a cleaner codebase.
**Delegations**: evolve (fix #0201 lib-agent.sh PYTHONPATH), audit-agent (76-session framework audit)
**Outcome**: PR #195 merged (lib-agent.sh hardened), PR #196 merged (7 doc fixes, 4 new tasks). 5 follow-up tasks created (#0202-#0206). make check passes (882 tests).

## 2026-04-08 -- Session #0108
**Advisory**: security-check (score 75), audit (score 75, tied)
**Decision**: Overrode to BUILD (eval rerun #0177) + EVOLVE (ROLE-SCORING.md #0203) in parallel. Rationale: (1) Eval at 53/100 is stale and below 80 gate -- blocking all BUILD tasks. Rerunning eval is the highest-impact unblock. (2) ROLE-SCORING.md is a v1 document actively misleading agents -- audit found this last session. (3) These tasks touch completely different files (nightshift eval vs .recursive/ops/), so parallel is safe. (4) Security-check deferred to next session now that eval gate is clear.
**Delegations**: build (eval rerun #0177), evolve (ROLE-SCORING.md #0203), evolve-fix (PR #197 review fixes)
**Outcome**: PR #198 merged (eval 53->86, gate clear), PR #197 merged (ROLE-SCORING.md v2 rewrite with fix cycle). 1 follow-up task created (#0207). make check passes (882 tests). Both dry-runs pass.
