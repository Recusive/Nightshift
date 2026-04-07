# Autonomy Scorecard

Score each check: 0 (not present), 3 (partially working), 5 (fully working). Use ONLY file evidence.

## Self-Healing (25 points)

| Check | How to verify |
|-------|---------------|
| Daemon auto-recovers from agent crashes (circuit breaker) | Does daemon.sh have circuit breaker? |
| Prompt guard detects unauthorized modifications | Does lib-agent.sh have save/check prompt snapshots? |
| CI failures auto-create fix branches (not push to main) | Does autonomous mode have CI FAILURE RULE? Ever triggered? |
| Eval score gates task selection (low score = fix eval first) | Does autonomous mode have EVAL SCORE GATE? Working? |
| Daemon self-restarts when its own code changes | Does daemon.sh have hash-based exec restart? |

## Self-Directing (25 points)

| Check | How to verify |
|-------|---------------|
| Daemon picks its own role each cycle | Does pick-role.py exist? Is daemon.sh calling it? |
| Task queue self-generates from system observation | Does build operator Step 6 (Generate Work) exist? Tasks being created? |
| Releases cut automatically (no release tasks needed) | Does build operator Step 11 have release algorithm? Has it released? |
| Stale tasks get attention (staleness multiplier or overseer culling) | Do stale tasks get picked or culled? |
| Strategy reviews trigger automatically | Does scoring trigger STRATEGIZE? Has it run? |

## Self-Validating (25 points)

| Check | How to verify |
|-------|---------------|
| E2E eval runs against a real external repo | Do evaluation report files exist with real scores? |
| Eval score trending toward 80+ (not stuck) | Last 3 eval reports — is score improving? |
| Post-merge smoke test runs (dry-run both agents) | Does Step 9 require dry-runs? |
| Code review sub-agents run on every PR | Does Step 8 specify sub-agent reviews? Logs show them? |
| Test count does not regress across sessions | Last 5 handoffs — test count stable or growing? |

## Self-Improving (25 points)

| Check | How to verify |
|-------|---------------|
| Learnings written and indexed after every session | Does INDEX.md have entries from recent sessions? |
| Healer observations identify trends (not just point failures) | Does healer log have recent trend entries? |
| Prompts refined based on session outcomes | Has the build prompt been modified in last 10 sessions? |
| Cost per session trending down or stable | Compare last 10 sessions in cost data |
| Session success rate above 90% | Count non-zero exit codes in session index |
