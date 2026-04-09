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

## 2026-04-08 -- Session #0112
**Advisory**: build (score 105, reason: eval=86, urgent=False, since_build=5)
**Decision**: Followed advisory -- BUILD #0085 (IndexError fix in feature.py) + EVOLVE #0211 (tighten pentest regex in signals.py). Both non-overlapping (project vs framework zone). Advisory alternatives were security-check (75) and audit (75), but both ran in recent sessions (known tracker gap).
**Delegations**: build (#0085 IndexError fix), evolve (#0211 regex tightening)
**Outcome**: PR #206 merged (feature.py defensive fix, 1 new test). PR #205 merged (3 substring→regex replacements in signals.py). 4 reviewers all PASS. 2 follow-up tasks created (#0215, #0216). 926 tests pass. Make check + dry-runs green.

## 2026-04-08 -- Session #0113
**Advisory**: build (score 105, reason: eval=86, urgent=False, since_build=5)
**Decision**: Followed advisory -- BUILD #0079 (wire feature summary into CLI) + EVOLVE #0216 (trailing anchor for status regex). Both non-overlapping zones (project vs framework). Advisory alternatives were security-check (75) and audit (75), both showing 78 sessions since last (known tracker gap).
**Delegations**: build (#0079 feature summary CLI), evolve (#0216 status regex anchor)
**Outcome**: PR #207 merged (5 regex patterns anchored in signals.py). PR #208 merged (write_summary_md function, 7 new tests). Build agent also duplicated signals.py changes (zone violation, no harm -- #207 merged first). 1 follow-up task created (#0217). 933 tests pass. Make check + dry-runs green.

## 2026-04-08 -- Session #0114
**Advisory**: build (score 105, reason: eval=86, urgent=False, since_build=5)
**Decision**: Followed advisory -- BUILD #0066 (auto-release module) + EVOLVE #0215 (pentest signal tests). Both non-overlapping zones (project vs framework). Advisory alternatives were security-check (75) and audit (75), both showing 78 sessions since last (known tracker gap).
**Delegations**: build (#0066 auto-release), evolve (#0215 pentest signal tests), build-fix (PR #218 round 2 after reviewer FAIL)
**Outcome**: PR #217 merged (14 pentest signal tests, meta-reviewer PASS). PR #218 merged (auto-release module, needed 1 fix cycle for tag injection + path traversal + sort bug, then both reviewers PASS). 3 follow-up tasks created (#0218-#0220). 993 tests pass. Make check green.

## 2026-04-08 -- Session #0115
**Advisory**: build (score 105, reason: eval=86, urgent=False, since_build=5)
**Decision**: Followed advisory -- BUILD #0082 (profiler config deepcopy) + EVOLVE #0218 (release.py doc update). Both non-overlapping zones (project nightshift/raven/ vs framework CLAUDE.md+OPERATIONS.md). Advisory alternatives were security-check (75) and audit (75), both showing 78 sessions since last (known tracker gap).
**Delegations**: build (#0082 profiler config), evolve (#0218 doc update)
**Outcome**: PR #219 merged (CLAUDE.md + OPERATIONS.md Tier 1 update, all 3 reviewers PASS). PR #220 merged (profiler.py deepcopy + 4 tests, both reviewers PASS). 1 follow-up task created (#0229). 997 tests pass. Make check + dry-runs green. No fix cycles needed.

## 2026-04-08 -- Session #0116
**Advisory**: build (score 105, reason: eval=86, urgent=False, since_build=5)
**Decision**: Followed advisory -- BUILD #0219 (rename RELEASE_TASK_STATUS_RE constant) + EVOLVE #0229 (CLAUDE.md dep flow chain + alphabetical ordering). Both non-overlapping zones (project nightshift/core+infra vs framework CLAUDE.md). Advisory alternatives were security-check (75) and audit (75), both showing 78 sessions since last (known tracker gap).
**Delegations**: build (#0219 constant rename), evolve (#0229 CLAUDE.md dep flow)
**Outcome**: PR #221 merged (CLAUDE.md dep flow + alphabetical, all 3 reviewers PASS). PR #222 merged (constant rename in constants.py + release.py, both reviewers PASS). 0 follow-up tasks created. 997 tests pass. Make check + dry-runs green. No fix cycles needed.

## 2026-04-08 -- Session #0117
**Advisory**: build (score 105, reason: eval=86, urgent=False, since_build=5)
**Decision**: Followed advisory -- BUILD #0090 (detect_file_conflicts failed-task scan) + EVOLVE #0222 (sessions-since counters parse delegation history). #0222 is a user-filed GitHub issue (#215) and the ROOT CAUSE of the perpetual "78 sessions since evolve/audit/security" tracker gap noted in every handoff for 10+ sessions. Non-overlapping zones (project nightshift/raven/ vs framework .recursive/engine/).
**Delegations**: build (#0090 detect_file_conflicts), evolve (#0222 sessions-since delegation parsing)
**Outcome**: PR #229 merged (coordination.py scans failed tasks, 3 new tests, both reviewers PASS). PR #230 merged (signals.py + pick-role.py delegation parsing, 13 new tests, meta-reviewer + safety-reviewer PASS). 1 follow-up task created (#0230 -- keep delegation role map in sync). 1025 tests pass. Make check + dry-runs green. No fix cycles needed.

## 2026-04-08 -- Session #0118
**Advisory**: build (score 80, reason: eval=86, urgent=False, since_build=0)
**Decision**: Followed advisory -- BUILD #0091 (eval dry-run CLI). Single task this session (no strong parallel candidate). Tracker fix from #0222 confirmed working: advisory JSON shows correct sessions-since values. No override needed.
**Delegations**: build (#0091 eval dry-run CLI), build-fix-231 (CLAUDE.md zone violation revert), build-fix-231-r2 (3 code review fixes), code-reviewer x2, safety-reviewer
**Outcome**: PR #231 merged (eval_runner.py + CLI integration, 55 new tests, needed 2 fix cycles: zone violation + code review issues). 3 follow-up tasks created (#0231-#0233). 1087 tests pass. Make check green.

## 2026-04-09 -- Session #0119
**Advisory**: build (score 80, reason: eval=86, urgent=False, since_build=0)
**Decision**: Followed handoff recommendation -- EVOLVE #0231 (Tier 1 doc update) + BUILD #0092 (score calibration) in parallel. #0231 was the #1 recommendation from last handoff (framework docs stale after PR #231 added eval_runner). #0092 naturally follows #0091 (eval CLI built last session). Non-overlapping zones.
**Delegations**: evolve (#0231 CLAUDE.md + OPERATIONS.md + MODULE_MAP.md), build (#0092 score calibration), code-reviewer x2, meta-reviewer, safety-reviewer x2
**Outcome**: PR #232 merged (Tier 1 doc update, all 3 reviewers PASS first try). PR #233 merged (4 fixtures + 25 calibration tests, both reviewers PASS first try). 2 follow-up tasks created (#0234-#0235). 1112 tests pass. Make check + dry-runs green. No fix cycles needed.

## 2026-04-09 -- Session #0120
**Advisory**: build (score 80, reason: eval=86, urgent=False, since_build=0)
**Decision**: Overrode to EVOLVE #0227 + BUILD #0234 in parallel. Rationale: (1) #0227 fixes stale session-since counters flagged 3+ sessions -- force multiplier for every future brain decision. (2) #0234 is a clean project-zone follow-up from last session's PR #232 review. (3) Non-overlapping zones (framework vs project). Advisory BUILD deferred because #0227's impact on decision quality outweighs one more feature build.
**Delegations**: evolve (#0227 delegation-aware dashboard counters), build (#0234 module map legend), meta-reviewer, safety-reviewer, code-reviewer
**Outcome**: PR #235 merged (dashboard.py + 5 new tests, both reviewers PASS first try). PR #234 merged (module_map.py + 1 new test, code-reviewer PASS first try). 1 follow-up task created (#0236). 1118 tests pass. Make check + dry-runs green. No fix cycles needed.

## 2026-04-09 -- Session #0121
**Advisory**: build (score 80, reason: eval=86, urgent=False, since_build=0)
**Decision**: Followed handoff recommendations -- EVOLVE #0095 + BUILD #0235 in parallel. Rationale: (1) #0095 stabilizes session index formatting (Tier 1 daemon files, framework zone). Broken multiline rows corrupt dashboard signals. (2) #0235 is a quick typing fix in test_score_calibration.py (project zone). (3) Non-overlapping zones, safe for parallel. Advisory BUILD aligned with this choice.
**Delegations**: evolve (#0095 session index formatting), build (#0235 typing fix), code-reviewer (x2), meta-reviewer, safety-reviewer
**Outcome**: PR #237 merged (Tier 1: lib-agent.sh + daemon.sh + brain.md + DAEMON.md + 11 new tests, all 3 reviewers PASS, all 8 safety invariants preserved). PR #236 merged (test_score_calibration.py annotation, code-reviewer PASS). 3 follow-up tasks created (#0237-#0239). 1128 tests pass. Make check + dry-runs green. No fix cycles needed.

## 2026-04-09 -- Session #0122
**Advisory**: build (score 80, reason: eval=86, urgent=False, since_build=0)
**Decision**: Overrode to OVERSEE + BUILD #0110. Rationale: (1) The human filed 6 GitHub issues (#0221, #0223-#0226, #0228) explicitly calling out that the brain always picks build+evolve and never uses oversee/strategize/achieve. This is direct human feedback that cannot be ignored. (2) Queue is 77 pending and growing (net +1 per session). Oversee is the most obviously needed maintenance agent. (3) BUILD #0110 ships a clean project-zone feature (module map monotonic labels) so we don't lose throughput entirely. (4) Non-overlapping: oversee touches .recursive/tasks/ (runtime state), build touches nightshift/infra/ (project zone).
**Delegations**: oversee (queue triage), build (#0110 monotonic session labels), code-reviewer, safety-reviewer, docs-reviewer
**Outcome**: PR #240 merged (10 tasks closed: 8 done + 2 blocked, queue 77->69). PR #239 merged (module_map.py monotonic source + 5 tests). 1 follow-up task created (#0240). 1142 tests pass. Make check + dry-runs green. No fix cycles needed.

## 2026-04-09 -- Session #0123
**Advisory**: strategize (score 95, reason: since_strategy=15, tracker_moved=False)
**Decision**: Followed advisory -- STRATEGIZE + BUILD #0240 in parallel. Rationale: (1) Strategize 15 sessions overdue (alert in dashboard). (2) Human filed 7 GitHub issues expressing systemic brain behavior concerns -- these are strategic problems, not tactical. (3) BUILD #0240 is a clean project-zone follow-up from last session's PR #239 review (no file overlap with strategy). (4) This is the first strategize delegation in the entire v2 brain era.
**Delegations**: strategize (first v2 strategy analysis), build (#0240 comment + test fix), docs-reviewer (x2, including re-review after fix), code-reviewer, build-fix (PR #242 missing report file)
**Outcome**: PR #241 merged (comment + test fix, code-reviewer PASS). PR #242 merged (strategy report + 3 tasks + #0223 closed, needed 1 fix cycle for missing report file, docs-reviewer PASS on re-review). 4 follow-up tasks created (#0241-#0244). 1142 tests pass. Make check + dry-runs green.

## 2026-04-09 -- Session #0124
**Advisory**: build (score 85, reason: eval=86, urgent=True, since_build=0)
**Decision**: Overrode to EVOLVE x2 (#0241 + #0242) in parallel. Rationale: (1) Both tasks are urgent, created from strategy analysis last session. (2) #0241 fixes 17 stale worktrees leaking disk space every session — the #1 operational issue. (3) #0242 fixes the broken build-measure-build feedback loop — addresses multiple human-filed issues (#0094, #0228). (4) These infrastructure fixes improve all future sessions. (5) Tasks touch different files (daemon.sh/lib-agent.sh vs signals.py/dashboard.py/brain.md), so parallel is safe.
**Delegations**: evolve (#0241 worktree cleanup), evolve (#0242 eval signal), evolve-fix (PR #244 current_wt guard fix), code-reviewer (x2 — initial FAIL + re-review PASS), meta-reviewer (x2 — #243 PASS, #244 PASS), safety-reviewer (x2 — both PASS)
**Outcome**: PR #243 closed (duplicate — lib-agent.sh changes subsumed by PR #244). PR #244 merged (worktree cleanup + eval staleness signal + brain rule + 14 new tests; needed 1 fix cycle for current_wt guard bug). 2 follow-up tasks created (#0245-#0246). 1156 tests pass. Make check green.
