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

## 2026-04-08 -- Session #0109
**Advisory**: build (score 105), security-check (score 75), audit (score 75)
**Decision**: Overrode to EVOLVE (#0202) + SECURITY in parallel. Rationale: (1) Security scan never done in 78 sessions -- most overdue activity. Previous handoff explicitly recommended it as #1 priority. (2) #0202 fixes the security-to-framework gap documented in friction log -- structural fix needed before next security findings arrive. (3) These tasks don't overlap: evolve touches .recursive/engine/ (framework), security scans nightshift/ (read-only). (4) Build deferred because both security debt items are higher priority than feature work.
**Delegations**: evolve (fix #0202 security-evolve path), security (first comprehensive pentest)
**Outcome**: PR #199 merged (pick-role.py + signals.py + brain.md updated for pentest→evolve path). PR #200 merged (pentest report: 2 CONFIRMED, 4 THEORETICAL findings; 2 tasks created). 4 follow-up tasks created (#0208-#0211). make check passes (882 tests).

## 2026-04-08 -- Session #0110
**Advisory**: build (score 110, reason: eval=86, urgent=True, since_build=5)
**Decision**: Followed advisory -- BUILD #0208 (URGENT verify_command injection) + EVOLVE #0209 (IFS injection in lib-agent.sh) in parallel. Both are CONFIRMED pentest findings. No override needed. Different zones (project vs framework), no file overlap.
**Delegations**: build (#0208 verify_command fix), evolve (#0209 IFS sanitization), build-fix (PR #202 newline bypass fix after reviewer FAIL)
**Outcome**: PR #201 merged (IFS fix, first try). PR #202 merged (verify_command fix, needed 1 fix cycle for newline bypass). 2 follow-up tasks created (#0212-#0213). 919 tests pass. Both dry-runs pass. Both CONFIRMED pentest findings now closed.

## 2026-04-08 -- Session #0111
**Advisory**: build (score 105, reason: eval=86, urgent=False, since_build=5)
**Decision**: Followed advisory -- BUILD #0084 (path traversal guard in readiness.py) + EVOLVE #0210 (pentest signal in safe_signals). Both are non-overlapping tasks in different zones.
**Delegations**: build (#0084 path traversal guard), evolve (#0210 safe_signals consistency)
**Outcome**: PR #203 merged (#0210 was already fixed -- task closed). PR #204 merged (path traversal guard with 6 new tests, both reviewers PASS). 1 follow-up task created (#0214). 925 tests pass. Make check passes.
