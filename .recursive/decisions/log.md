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

## 2026-04-09 -- Session #0125
**Advisory**: build (score 80, reason: eval=86, urgent=False, since_build=1)
**Decision**: Followed advisory + handoff recommendation -- BUILD #0243 (eval rerun) + EVOLVE #0245 (dead code cleanup) in parallel. Rationale: (1) Eval #0243 is the #1 handoff recommendation, 4 sessions stale with 20 files changed, addresses 3 human-filed issues (#0094, #0224, #0228). (2) #0245 is a clean framework follow-up from last session's PR #244 review (dead code in signals.py). (3) Non-overlapping zones (nightshift eval vs .recursive/engine/). Advisory BUILD aligned.
**Delegations**: build (#0243 eval rerun), evolve (#0245 dead code cleanup), meta-reviewer (PR #245), safety-reviewer (PR #245), code-reviewer (PR #246)
**Outcome**: PR #245 merged (signals.py import cleanup + dead fallback removal + test constant removal, all reviewers PASS first try). PR #246 merged (eval #0017: 83/100, 2 real fixes, 2 follow-up tasks). 0 fix cycles needed. 1156 tests pass. Make check + dry-runs green.

## 2026-04-09 -- Session #0126
**Advisory**: build (score 80, reason: eval=83, urgent=False, since_build=0)
**Decision**: Followed advisory + handoff recommendations -- BUILD #0247 (count-only payload fix) + AUDIT (18 sessions since last). Rationale: (1) #0247 is the #1 handoff recommendation -- root cause of -3 eval regression (state counter inflated by commit count instead of fix count). (2) Audit 18 sessions overdue -- framework docs stale after eval signal, worktree cleanup, release module, and 241 new tests added since last audit (#0107). (3) Non-overlapping zones (project nightshift/core/ vs framework .recursive/). Advisory BUILD aligned.
**Delegations**: build (#0247 count-only payload), audit-agent (18-session framework audit), evolve-fix (PR #248 dependency flow ordering), code-reviewer (x2: PR #247, PR #248 re-review), safety-reviewer (x2: PR #247, PR #248 re-review), meta-reviewer (x2: initial FAIL + re-review PASS), code-reviewer (PR #248 re-review)
**Outcome**: PR #247 merged (state.py count-only fix + 3 tests, both reviewers PASS first try). PR #248 merged (8 doc fixes + 2 tasks, needed 1 fix cycle for dependency flow ordering, all 3 Tier 1 reviewers PASS on re-review, all 8 safety invariants preserved). 3 follow-up tasks created (#0249-#0251). 1159 tests pass. Make check green.

## 2026-04-09 -- Session #0127
**Advisory**: build (score 80, reason: eval=83, urgent=False, since_build=0)
**Decision**: Followed advisory + handoff recommendations -- BUILD #0249 (regenerate MODULE_MAP.md) + EVOLVE #0250 (fix DAEMON.md lifecycle commands). Rationale: (1) Both are concrete, well-scoped tasks recommended by last session's audit. (2) Different zones (project nightshift/ vs framework .recursive/ops/), no file overlap, safe to parallel. (3) MODULE_MAP was stale since session #0001 -- every session reading it gets wrong orientation data. (4) DAEMON.md had inaccurate git commands misleading agents.
**Delegations**: build (#0249 MODULE_MAP regen), evolve (#0250 DAEMON.md fix), code-reviewer (PR #250), safety-reviewer (PR #250), docs-reviewer (PR #249)
**Outcome**: PR #250 merged (module_map.py extended for subpackage scanning, 27 modules now visible, 5 new tests). PR #249 merged (DAEMON.md lifecycle corrected). Both merged first try. 3 follow-up tasks created (#0252-#0254). 1164 tests pass. Make check green.

## 2026-04-09 -- Session #0128
**Advisory**: build (score 80, reason: eval=83, urgent=False, since_build=0)
**Decision**: Overrode to OVERSEE + BUILD in parallel. Rationale: (1) Human filed #0225 (queue growing) and #0226 (brain never uses oversee) -- these are direct human priorities that override the advisory. (2) This is the first OVERSEE delegation in the v2 brain era. (3) BUILD on #0252/#0253/#0254 is a clean project-zone batch that pairs well with OVERSEE (no file overlap). (4) Queue at 72 and growing +4 net recently -- needs trimming.
**Delegations**: oversee (first v2 triage, queue 72->63), build (#0252+#0253+#0254 module_map followups), code-reviewer (PR #251), safety-reviewer (PR #251), docs-reviewer (PR #252)
**Outcome**: PR #251 merged (module_map docstring + ParseError + comment, 1 new test). PR #252 merged (7 pending closed, 9 wontfix->done). 0 fix cycles. 1 follow-up task created (#0255). Queue: 72->63 (-9 net). 1165 tests pass.

## 2026-04-09 -- Session #0129
**Advisory**: build (score 80, reason: eval=83, urgent=False, since_build=0)
**Decision**: Followed handoff recommendation -- EVOLVE #0251 + BUILD #0255 in parallel. Rationale: (1) #0251 is the handoff's #1 recommendation: hardening daemon.sh role extractor to prevent corrupted SESSION_ROLE values visible in dashboard recent_roles. (2) #0255 is a quick project-zone follow-up from last session's PR #251 review advisory. (3) Non-overlapping zones (framework daemon.sh vs project tests/), safe to parallel. Advisory BUILD aligned (build via evolve for framework zone).
**Delegations**: evolve (#0251 daemon.sh role hardening), build (#0255 test comment fix), code-reviewer (PR #254 + PR #253), meta-reviewer (PR #254), safety-reviewer (PR #254)
**Outcome**: PR #254 merged (daemon.sh role extractor hardened with awk+tr+case validation, Tier 1 full review, all 3 reviewers PASS, all 8 safety invariants preserved). PR #253 merged (test comment fix). 0 fix cycles. 1 follow-up task created (#0256). Queue: 63->62 (-1 net). 1165 tests pass.

## 2026-04-09 -- Session #0130
**Advisory**: build (score 80, reason: eval=83, urgent=False, since_build=0)
**Decision**: Followed advisory + handoff recommendations -- EVOLVE #0237 (mktemp in daemon.sh) + BUILD #0233 (symlink check in eval_runner) in parallel. Rationale: (1) Both are security hardening follow-ups from prior PR reviews. (2) #0237 fixes a predictable temp path in Tier 1 daemon.sh. (3) #0233 prevents symlink-based path traversal in eval_runner.py. (4) Non-overlapping zones (framework daemon.sh vs project eval_runner.py), safe to parallel. (5) Eval rerun deferred: 0 nightshift files changed since last eval, so no delta to measure.
**Delegations**: evolve (#0237 mktemp fix), build (#0233 symlink guard), code-reviewer (PR #255 + PR #256), meta-reviewer (PR #255), safety-reviewer (PR #255 + PR #256)
**Outcome**: PR #255 merged (daemon.sh mktemp, Tier 1 full review, all 3 reviewers PASS, all 8 safety invariants preserved). PR #256 merged (eval_runner symlink guard, 4 new tests, both reviewers PASS). 0 fix cycles. 1 follow-up task created (#0257). Queue: 62->61 (-1 net). 1169 tests pass.

## 2026-04-09 -- Session #0131
**Advisory**: build (score 80, reason: eval=83, urgent=False, since_build=0)
**Decision**: Followed advisory + handoff recommendations -- EVOLVE #0257 (EXIT trap cleanup in daemon.sh) + BUILD #0248 (auto-clone eval target) in parallel. Rationale: (1) #0248 is an eval-derived finding that improves UX for running nightshift against Phractal -- directly addresses human-filed #0224's core concern. (2) #0257 is a Tier 1 daemon.sh improvement from all 3 reviewers' advisory notes on PR #255. (3) Non-overlapping zones (framework daemon.sh vs project cli.py/worktree.py), safe to parallel. (4) Eval rerun deferred: 0 nightshift files changed since last eval, but auto-clone makes future evals easier.
**Delegations**: evolve (#0257 EXIT trap), build (#0248 auto-clone), code-reviewer (PR #257 + PR #258 x2), meta-reviewer (PR #257), safety-reviewer (PR #257 + PR #258), build-fix (PR #258 test_mode gate)
**Outcome**: PR #257 merged (daemon.sh EXIT trap, Tier 1 full review, all 3 reviewers PASS, all 8 safety invariants preserved). PR #258 merged (auto-clone + test_mode gate, needed 1 fix cycle for unconditional _ensure_repo_dir). 5 new tests. 1 follow-up task created (#0258). Queue: 61->60 (-1 net). 1174 tests pass.

## 2026-04-09 -- Session #0132
**Advisory**: build (score 80, reason: eval=83, urgent=False, since_build=0)
**Decision**: Followed advisory + eval_staleness alert -- BUILD eval rerun against Phractal + EVOLVE #0258 (SNAP_DIR cleanup) in parallel. Rationale: (1) eval_staleness alert at 7 sessions is the primary signal -- dashboard explicitly says to run eval. (2) Human tasks #0224 and #0228 both ask for Phractal eval runs. (3) #0258 is a quick Tier 1 follow-up from all 3 reviewers on PR #257. (4) Non-overlapping zones (project eval output vs framework daemon.sh), safe to parallel.
**Delegations**: build (eval rerun against Phractal), evolve (#0258 SNAP_DIR trap), code-reviewer (PR #259 + PR #260), meta-reviewer (PR #259), safety-reviewer (PR #259), docs-reviewer (PR #260)
**Outcome**: PR #259 merged (SNAP_DIR cleanup, Tier 1 full review, all 3 reviewers PASS, all 8 safety invariants preserved). PR #260 merged (eval 84/100, auto-clone validated, #0224 done). 0 fix cycles. 2 follow-up tasks created (#0259, #0260). Queue: 61->61 (net 0). 1174 tests pass.

## 2026-04-09 -- Session #0133
**Advisory**: build (score 80, reason: eval=84, urgent=False, since_build=0)
**Decision**: Followed advisory + handoff recommendations -- BUILD #0260 (count-only payload regression) + EVOLVE #0259 (SNAP_DIR quoting) in parallel. Rationale: (1) #0260 is the #1 handoff recommendation -- primary obstacle to Loop 1 reaching 100%. State file scored 6/10 in eval #0091. (2) #0259 is a quick Tier 1 consistency fix from last session's safety review advisory. (3) Non-overlapping zones (project nightshift/ vs framework daemon.sh), safe to parallel. Advisory BUILD aligned.
**Delegations**: build (#0260 count-only payload regression), evolve (#0259 SNAP_DIR quoting), code-reviewer (PR #261 + PR #262), meta-reviewer (PR #261), safety-reviewer (PR #261 + PR #262)
**Outcome**: PR #261 merged (SNAP_DIR quoting, Tier 1 full review, all 3 reviewers PASS, all 8 safety invariants preserved). PR #262 merged (count-only regression: state.py fallback + cycle.py schema embed + eval_runner.py 5-tier scoring + 12 tests). 0 fix cycles. 3 follow-up tasks created (#0261-#0263). Queue: 61->62 (net +1). 1186 tests pass.
