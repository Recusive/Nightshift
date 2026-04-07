# Plan: Process Verification Pipeline + Skill Architecture

## Context

The daemon spent 12 straight BUILD sessions on security fixes while eval score stayed at 53/100.

**Root cause:** The pentest preflight generates findings -> overseer creates urgent tasks -> `pick_role()` forces BUILD when urgent tasks exist (line 391 of pick-role.py). The scoring engine worked correctly -- pentest-generated urgency bypassed it.

**Deeper problem:** Even after fixing the urgency loop, the agent's decision-making is fundamentally limited by RLHF training biases. Models trained with RLHF develop sycophancy, action bias, and completion bias -- they optimize for "looking productive" over "being correct." In an autonomous loop, this means the agent rushes to code, skips analysis, picks easy tasks, and rationalizes bad decisions. Hardcoded scoring (if X > 3, subtract 15) just patches symptoms. We need a pipeline that makes the agent reason like a senior engineer -- data-driven, deliberate, accountable.

**Goal:** Build a Process Verification Pipeline that counteracts RLHF biases at every decision point. Organize prompts into skills. Fix the urgency loop. Make the agent's reasoning visible, verifiable, and accountable.

---

## Research Foundation

The pipeline design is grounded in recent alignment research from frontier labs. These sources should be reviewed by auditors for full context:

### RLHF Bias and Sycophancy

- **Anthropic: Towards Understanding Sycophancy in Language Models**
  https://www.anthropic.com/research/towards-understanding-sycophancy-in-language-models
  Finding: Sycophancy is a general behavior of RLHF models driven by human preference judgments favoring sycophantic responses. Humans and preference models sometimes prefer convincingly-written sycophantic responses over correct ones.

- **Anthropic: Natural Emergent Misalignment from Reward Hacking in Production RL**
  https://assets.anthropic.com/m/74342f2c96095771/original/Natural-emergent-misalignment-from-reward-hacking-paper.pdf
  Finding: Reward hacking emerges naturally in production RL training. Penalizing it during training with a dedicated reward-hacking classifier is effective.

- **Anthropic-OpenAI Joint Alignment Evaluation (2025)**
  https://alignment.anthropic.com/2025/openai-findings/
  Finding: Models from both labs showed "disproportionate agreeableness" and would "validate harmful decisions by simulated users who appear to have delusional beliefs." All models studied would sometimes attempt to blackmail operators to secure continued operation.

### Process Reward Models (conceptual inspiration, not direct application)

NOTE: These papers describe training-time reward models and verifiers, not prompt-time checkpoints. Our pipeline is INSPIRED by the principle (reward each step, not just the outcome) but implements it via prompt structure rather than model training. The papers validate the principle; our implementation is a prompt-engineering adaptation, not a reproduction.

- **Process Reward Models That Think (ThinkPRM)**
  https://arxiv.org/abs/2504.16828
  Principle applied: Evaluating each reasoning step independently catches errors that outcome-only evaluation misses. Our adaptation: mandatory checkpoint blocks that make each decision step visible and verifiable in the session log.

- **Rewarding Progress: Scaling Automated Process Verifiers**
  https://openreview.net/forum?id=A6Y7AqlzLW
  Principle applied: Step-level feedback improves credit assignment. Our adaptation: the Post-Session Audit (Checkpoint 4) creates cross-session feedback on whether each session's commitment was met.

- **Beyond Outcome Verification: Verifiable Process Reward Models**
  https://www.arxiv.org/pdf/2601.17223
  Principle applied: Steps that produce checkable evidence outperform steps where the model just claims correctness. Our adaptation: Signal Analysis requires verifiable numbers, Pre-Commitment requires measurable metrics.

### Causal Rewards and Anti-Sycophancy

- **Beyond Reward Hacking: Causal Rewards for LLM Alignment**
  https://arxiv.org/html/2501.09620v1
  Finding: RLHF exploits spurious correlations (longer = better, confident = correct). Causal reward modeling enforces counterfactual invariance -- rewards stay the same when irrelevant variables change.

- **Anthropic: Claude's Constitution (Soul Spec, January 2026)**
  https://www.anthropic.com/constitution
  Finding: Anthropic explicitly does NOT want Claude to treat helpfulness as its core identity because that makes it sycophantic. They want it helpful because it "cares about people, not because it is programmed to please." Positively framed, behavior-based principles align better than rules.

- **C3AI: Crafting and Evaluating Constitutions for Constitutional AI**
  https://dl.acm.org/doi/10.1145/3696410.3714705
  Finding: Positively framed, behavior-based principles align more closely with human preferences than negatively framed or trait-based principles.

### Reward Hacking Mitigation

- **Mitigating Reward Hacking via Advantage Sign Robustness (April 2026)**
  https://arxiv.org/html/2604.02986
  Finding: Optimizing against an imperfect reward model causes the policy to exploit local inaccuracies. Sign-robustness filtering prevents the worst exploits.

- **Mitigating Reward Hacking via Bayesian Non-Negative Reward Modeling (February 2026)**
  https://www.emergentmind.com/papers/2602.10623
  Finding: Bayesian framework addresses vulnerability to reward hacking from noisy annotations and systematic biases like response length or style.

- **Reward Shaping to Mitigate Reward Hacking in RLHF (January 2026)**
  https://arxiv.org/pdf/2502.18770
  Finding: Reward hacking manifests as degenerate behaviors like repetitive or overly verbose outputs. Reward shaping constrains the policy to stay close to the reference model.

---

## RLHF Bias Mapping

How each RLHF bias manifests in our daemon and what the pipeline does about it:

| RLHF Bias | How It Manifests | Research Basis | Pipeline Countermeasure |
|-----------|------------------|----------------|----------------------|
| **Action bias** (rush to code) | Agent skips data analysis, jumps to picking a task | Process Reward Models -- reward the analysis step, not just the outcome | **Checkpoint 1: Signal Analysis** -- must output verifiable numbers before deciding |
| **Sycophancy** (say what sounds good) | Agent claims "this is highest impact" without evidence | Soul Spec -- own the outcome, don't perform helpfulness | **Ownership framing** -- "you are the CTO delivering to the board" not "you are an assistant" |
| **Completion bias** (ship anything) | Agent ships half-done work because shipping = reward | Step-level verification -- each step must be independently correct | **Checkpoint 3: Pre-commitment metric** -- declare measurable success before starting |
| **Rationalization** (confident BS) | Agent writes convincing justification for a bad choice | Causal rewards -- verify the cause, not the correlation | **Checkpoint 4: Post-session audit** -- next session checks if the metric actually moved |
| **Easy task selection** | Agent picks low-impact tasks that are quick to complete | Counterfactual invariance -- reward should be the same regardless of task difficulty | **Checkpoint 2: Forced tradeoff** -- must state what you are NOT doing and the cost of skipping it |
| **Pattern blindness** | Agent can't see it's been doing security work for 12 sessions | Constitutional AI -- principles that reference system state, not just the current task | **Signal injection** -- raw system data in the prompt, not filtered through the agent's preferences |

---

## Architecture: Four Changes

```
BEFORE:  pentest -> pick-role.py (rigid scores) -> load role prompt -> agent follows script
AFTER:   pentest -> pick-role.py (signals + scores) -> load skill + verification pipeline -> agent reasons with checkpoints -> next session audits
```

### Change A: Fix Pentest Urgency Loop

The immediate bug fix. pick-role.py's `pick_role()` has `if urgent: return "build"` that bypasses all scores.

**Bug in prior draft:** Counting "pentest" in the Status field is wrong -- EVERY session has "pentest: success/failed" in Status because the pentest preflight runs every cycle. The count would always be 5. Must use the **Feature** field instead, which only contains security keywords when the BUILD session actually worked on security tasks.

**1. In `main()` of pick-role.py, add signal:**
```python
# Count recent BUILD sessions that worked on security/pentest tasks.
# Uses the Feature field (what was built), NOT the Status field
# (which always contains "pentest: success" from the mandatory preflight).
_SECURITY_KEYWORDS = ("security", "pentest", "injection", "prompt guard", "prompt-guard")
recent_security_sessions = sum(
    1 for r in index_rows[-5:]
    if r.get("role", "").strip() == "build"
    and any(kw in r.get("feature", "").lower() for kw in _SECURITY_KEYWORDS)
)
signals["recent_security_sessions"] = recent_security_sessions
```

**Known limitation (short-term):** The Feature field is best-effort — often `-` or truncated for non-BUILD sessions, and extracted from agent output. This means honest security sessions with missing Feature fields can bypass the anti-loop.

**Structured provenance (same-phase follow-up):** To make the signal robust, also add `source: pentest` tag to task frontmatter when the builder creates tasks from pentest findings. Then add a secondary signal reader:

```python
def count_recent_pentest_tasks(tasks_dir: str, days: int = 3) -> int:
    """Count tasks completed in the last N days with source: pentest in frontmatter.

    Scans the archive directory. Uses the `completed:` frontmatter date, NOT
    file mtime (mtime is unreliable because daemon.sh hard-resets to origin/main
    each cycle, which resets checkout timestamps on all files).

    NOTE: _read_frontmatter() takes a Path and returns a raw string (the YAML
    block between --- markers), not a dict. We parse with string matching.
    """
    import re
    from datetime import datetime, timedelta
    from pathlib import Path

    count = 0
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    archive_dir = Path(tasks_dir) / "archive"
    if not archive_dir.is_dir():
        return 0
    for f in archive_dir.iterdir():
        if f.suffix != ".md":
            continue
        fm = _read_frontmatter(f)
        if not fm or "source: pentest" not in fm:
            continue
        # Extract completed: YYYY-MM-DD from frontmatter string
        m = re.search(r"completed:\s*(\d{4}-\d{2}-\d{2})", fm)
        if m and m.group(1) >= cutoff:
            count += 1
    return count
```

Why not mtime: `daemon.sh` lines 158-160 run `git reset --hard origin/main` every cycle, which resets file timestamps on checkout. A task archived a week ago would appear "recent" after a reset. The `completed:` frontmatter date is durable -- it survives git operations because it's committed content, not filesystem metadata.

Test required: `test_old_archived_pentest_tasks_do_not_trigger_antiloop` -- create archived tasks with `source: pentest` and `completed: 2026-03-01` (old), verify they are NOT counted.

The anti-loop uses BOTH signals -- Feature keywords (fast, lossy) AND task provenance (robust, windowed). If either signal indicates 3+ recent security sessions, the loop breaker activates:

```python
feature_security = sum(
    1 for r in index_rows[-5:]
    if r.get("role", "").strip() == "build"
    and any(kw in r.get("feature", "").lower() for kw in _SECURITY_KEYWORDS)
)
task_security = count_recent_pentest_tasks(tasks_dir, days=3)
recent_security_sessions = max(feature_security, task_security)
```

The `days=3` window prevents old archived pentest tasks from permanently activating the anti-loop. Only tasks completed in the last 3 days count.

**2. In `compute_scores()`, consume it:**
```python
rs = signals.get("recent_security_sessions", 0)
if rs >= 3 and signals["urgent_tasks"]:
    build -= 15
```

**3. In `pick_role()`, respect the anti-loop:**
```python
def pick_role(scores, urgent, recent_security=0):
    if urgent and recent_security < 3:
        return "build"
    # ... rest unchanged (scores-based selection)
```

**4. In `main()`, pass it:**
```python
winner = pick_role(scores, urgent, recent_security_sessions)
```

**5. In evolve-auto.md (not overseer -- the builder creates tasks from pentest data, not the overseer):**

Add to the PENTEST DATA RULE section:
```
When creating follow-up tasks from pentest findings, use priority: normal
by default. Only use priority: urgent for confirmed exploitable
vulnerabilities with a concrete reproduction path -- not theoretical
risks, not "could be exploited if..." scenarios.
```

Also add to `docs/prompt/pentest.md` output format:
```
Severity for each finding: CONFIRMED (reproducible exploit) or THEORETICAL
(possible but unproven). Only CONFIRMED findings warrant urgent tasks.
```

**Files:** `scripts/pick-role.py`, `docs/prompt/evolve-auto.md`, `docs/prompt/pentest.md`
**Tests:** `test_security_loop_demotion`, `test_urgent_bypass_respects_security_loop`, `test_security_signal_uses_feature_not_status`

---

### Change B: Skill Architecture

Organize role prompts into `docs/prompt/skills/` with shared boilerplate removed.

| Skill File | Source | Key Content |
|------------|--------|-------------|
| `skills/build.md` | evolve.md + BUILD rules from evolve-auto.md | 12-step process, task selection, eval gate, release |
| `skills/review.md` | review.md | Pick file, deep read, fix quality |
| `skills/oversee.md` | overseer.md | Triage queue, close/wontfix/reorder |
| `skills/strategize.md` | strategist.md | Big picture, cost intelligence, prompt health |
| `skills/achieve.md` | achieve.md | Autonomy scorecard, eliminate human deps |
| `skills/security-check.md` | pentest.md | Red team scan (unchanged) |

**daemon.sh** `pick_session_role()` points to `skills/` paths.
**evolve-auto.md** keeps universal rules. BUILD-specific rules move to `skills/build.md`.

**PROMPT_GUARD updates:**
```bash
# Add to PROMPT_GUARD_FILES:
"docs/prompt/skills/build.md"
"docs/prompt/skills/review.md"
"docs/prompt/skills/oversee.md"
"docs/prompt/skills/strategize.md"
"docs/prompt/skills/achieve.md"
"docs/prompt/skills/security-check.md"

# Add to PROMPT_GUARD_DIRS:
"docs/prompt/skills"

# KEEP existing entries for original prompts
```

**Contract migration (this is a contract change, not just a file move):**

Hardcoded prompt paths exist in:
- `scripts/daemon.sh` — `pick_session_role()` case statement
- `scripts/daemon-review.sh`, `daemon-overseer.sh`, `daemon-strategist.sh` — load old paths directly
- `tests/test_nightshift.py` — prompt-contract tests reference specific paths
- `docs/ops/DAEMON.md` — prompt table
- `docs/ops/ROLE-SCORING.md` — prompt references

**Strategy: keep originals as-is, skill files are stripped copies.**

Original prompt files stay untouched. Standalone daemons keep loading them. Unified daemon loads skills. No broken references. Standalone daemons are deprecated anyway — removing them is a separate task.

Also retire `docs/prompt/unified.md` — superseded by this architecture. Add a one-line note at the top: "Superseded by the skill architecture. See docs/prompt/skills/."

**Files:** 6 new skill files, `scripts/daemon.sh`, `scripts/lib-agent.sh`, `docs/prompt/evolve-auto.md`
**Tests:** Update prompt-contract tests to verify skill files exist AND original files still exist. Add `test_skill_files_exist` and `test_original_prompts_still_present`.
**Docs:** Update `docs/ops/DAEMON.md` prompt table for unified daemon paths

---

### Change C: Process Verification Pipeline

This is the core innovation. Four mandatory checkpoints embedded in the prompt that counteract RLHF biases by making the agent's reasoning visible, verifiable, and accountable. Based on Process Reward Model research -- reward each step, not just the outcome.

#### Checkpoint 1: Signal Analysis (anti-action-bias)

**What:** Before making any decision, the agent must output a `SIGNAL ANALYSIS` block with specific, verifiable numbers from the system state. Not "eval is low" but "eval is 53/100, down from 58 (eval #0014), lowest dimension: verification 2/10."

**Why (research):** Process Reward Models show that rewarding intermediate steps prevents the model from skipping to conclusions. By requiring the agent to demonstrate it READ the data, we prevent the action bias of jumping straight to coding.

**How:** pick-role.py gains `--with-signals` flag that writes JSON signals to a temp file alongside normal role selection (single invocation). daemon.sh reads the temp file and injects it into the prompt as sanitized structured data. The agent must reference specific numbers from this data.

**Verification:** Grep the session log for the SIGNAL ANALYSIS block. Check that numbers match actual file contents. If the block is missing or numbers don't match, the session is flagged.

**Signals schema: numeric, boolean, and enum ONLY. No free-form strings.**

Free-form strings (feature names, task titles) come from prior agent output and could contain prompt injection. The `<system_signals>` block follows the same trust boundary as `<pentest_data>` / `<open_pr_data>` — data, not instructions.

Signals JSON schema (all fields from existing pick-role.py signal readers):
```json
{
  "eval_score": 53,
  "autonomy_score": 85,
  "consecutive_builds": 4,
  "sessions_since_review": 2,
  "sessions_since_oversee": 3,
  "sessions_since_achieve": 1,
  "sessions_since_strategy": 8,
  "pending_tasks": 47,
  "urgent_tasks": 3,
  "stale_tasks": 5,
  "recent_security_sessions": 4,
  "healer_status": "good",
  "needs_human_issues": 0,
  "tracker_moved": false,
  "recent_roles": ["build", "build", "oversee", "build", "review"]
}
```

Fields excluded (contain agent-authored free text):
- `recent_features` — dropped, not injected
- `task_titles` — dropped, not injected
- `handoff_summary` — dropped, agent reads the file directly

The agent reads the raw files (handoff, tasks, evals) for qualitative context. The signals block provides only structured metrics.

Agent must output a SIGNAL ANALYSIS block referencing these numbers:
```
SIGNAL ANALYSIS
===============
eval_score:          53/100 (from signals)
consecutive_builds:  4
sessions_since_eval: 8 (computed: no eval in last 8 sessions per index)
pending_tasks:       47 (3 urgent)
recent_roles:        [build, build, oversee, build, review]
recent_security:     4 of last 5 builds were security-driven
```

#### Checkpoint 2: Forced Tradeoff Analysis (anti-easy-task / anti-rationalization)

**What:** The agent must state at least 2 options with the cost of NOT doing each. Forces confrontation with tradeoffs instead of rationalizing the first idea.

**Why (research):** Causal reward models enforce counterfactual invariance -- the reward should reflect the actual impact, not the agent's confidence. By forcing the agent to articulate what it's sacrificing, we make the opportunity cost visible. The agent can't just say "I'll do X because it's important" -- it must say "I'm NOT doing Y, and the cost of that is Z."

**How:** Embedded in the skill prompt as a mandatory step before starting work.

```
TRADEOFF ANALYSIS
=================
Option A: Fix eval parsing (task #0139)
  Impact: eval score 53 -> ~65 (fixes verification + fix_quality dimensions)
  Cost of skipping: eval stays at 53, product doesn't improve, stagnation continues
  
Option B: Continue security hardening (task #0194)
  Impact: closes 1 pentest finding, +0 eval points
  Cost of skipping: theoretical vuln stays open, no production impact confirmed

Option C: Review code quality (one module)
  Impact: fewer bugs in one file, +0 eval or tracker
  Cost of skipping: technical debt stays, but not blocking anything

Decision: Option A. Eval has been declining for 5 sessions while security
work consumed 12 consecutive builds. The product is stagnating.
```

#### Checkpoint 3: Pre-Commitment Metric (anti-completion-bias)

**What:** Before starting work, the agent declares a specific, measurable success criterion. This is logged. The next session will check it.

**Why (research):** Completion bias means the agent will declare success regardless of actual quality. Pre-commitment creates accountability -- the agent defines "done" before it can be biased by sunk-cost or desire to finish. ThinkPRM shows that step-level verification with pre-declared criteria outperforms post-hoc evaluation.

**How:** Added to the skill prompt's proposal step.

```
PRE-COMMITMENT
==============
Metric: eval score improves from 53 to 60+ on next evaluation
Verification: run eval against Phractal after merge, score verification dimension
Fallback: if eval doesn't improve, log root cause in handoff for next session
```

#### Checkpoint 4: Post-Session Audit (anti-sycophancy / feedback loop)

**What:** The handoff includes a "Commitment Check" section. The NEXT session reads it and verifies: did the previous session's metric actually move? This creates a cross-session feedback loop.

**Why (research):** Anthropic's soul spec frames the agent as caring about outcomes, not about appearing helpful. The post-session audit makes the agent's track record visible. Over time, a STRATEGIZE session can see: "Builder promised eval improvement 5 times, delivered twice. The pipeline is lying to itself." This is the causal verification -- did the metric ACTUALLY move, not did the agent SAY it moved?

**How:** Added to the handoff template and the next session's Step 0.

In the current session's handoff:
```
## Commitment Check
Pre-commitment: eval score 53 -> 60+
Actual result: [to be verified by next session]
```

In the next session's Step 0:
```
Read the previous handoff's Commitment Check section.
Verify: did the metric actually improve?
If YES: note "Previous commitment: MET" in your status report.
If NO: note "Previous commitment: MISSED — [reason]" and factor this
  into your own decision-making. If the same commitment has been missed
  3+ times, escalate: create a task to investigate why.
```

---

### Change D: Agent Override

pick-role.py still runs and recommends a role. The agent can override with logged justification if the verification pipeline reveals something the scoring engine can't see.

**Critical design: override NEVER poisons the scorer's input.**

The session index gets a new column layout (10 columns):
```
| Timestamp | Session | Role | Exit | Duration | Cost | Status | Feature | PR | Override |
```

- `Role` column: ALWAYS machine-generated by pick-role.py. Never overwritten by agent. This is the scorer's source of truth for `consecutive_builds`, `sessions_since_*`, etc.
- `Override` column: agent-reported effective role + reason. Only for human audit. pick-role.py IGNORES this column entirely.

**Add to evolve-auto.md:**
```
ROLE OVERRIDE: pick-role.py selected your role this cycle. If your
Signal Analysis reveals a different role is more valuable (e.g., eval
declining for 5 sessions while security tasks dominate), you may
override. Requirements:
1. State the recommended role and its score
2. State your chosen role with evidence from your Signal Analysis
3. Output: ROLE OVERRIDE: [recommended] -> [chosen]: [evidence]
4. Read docs/prompt/skills/{chosen-role}.md and follow it instead.
The override is auditable. The next session's Commitment Check applies.
```

**Override precedence (fully defined):**
1. `NIGHTSHIFT_FORCE_ROLE` env var — highest. Human override. Bypasses everything.
2. pick-role.py recommendation — default. Machine-generated, deterministic.
3. Agent override — lowest. Recorded in Override column only. Does NOT change Role column.

**daemon.sh extraction (in `scripts/lib-agent.sh`, following shared-helper pattern):**

Add `extract_role_override()` function to lib-agent.sh (not inline in daemon.sh — repo pattern says cross-cutting helpers go in lib-agent.sh):

```bash
# extract_role_override LOG_FILE
# Extracts the last ROLE OVERRIDE line from a JSONL session log.
# Returns the full override line, or empty string if none.
extract_role_override() {
    local log_file="$1"
    python3 -c "
import json, sys, re
last = ''
for line in open(sys.argv[1]):
    try:
        e = json.loads(line.strip())
        if e.get('type') == 'assistant':
            for b in e['message']['content']:
                if b.get('type') == 'text':
                    m = re.search(r'ROLE OVERRIDE:.*?-> ([a-z]+)', b['text'])
                    if m:
                        last = b['text'][b['text'].index('ROLE OVERRIDE:'):].split(chr(10))[0]
    except Exception:
        pass
print(last)
" "$log_file" 2>/dev/null || true
}
```

In daemon.sh, after run_agent:
```bash
OVERRIDE_NOTE=""
ROLE_OVERRIDE=$(extract_role_override "$LOG_FILE")
if [ -n "$ROLE_OVERRIDE" ]; then
    OVERRIDE_ROLE=$(echo "$ROLE_OVERRIDE" | sed -n 's/.*-> \([a-z]*\).*/\1/p')
    case "$OVERRIDE_ROLE" in
        build|review|oversee|strategize|achieve)
            OVERRIDE_NOTE="$OVERRIDE_ROLE: $(echo "$ROLE_OVERRIDE" | sed 's/ROLE OVERRIDE: //')"
            echo "  Agent overrode role: $ROLE_OVERRIDE"
            ;;
        *) echo "  Invalid override role: $OVERRIDE_ROLE (ignored)" ;;
    esac
fi
# SESSION_ROLE is NEVER modified. OVERRIDE_NOTE goes to the Override column.
```

---

## Ownership Framing (anti-sycophancy)

Inspired by the Soul Spec's principle that Claude should not treat helpfulness as its core identity (which breeds sycophancy). The Soul Spec itself does not prescribe a "CTO" framing — that is our adaptation. C3AI supports the principle that positively framed, behavior-based principles work better than negatively framed rules.

Current framing (sycophancy-prone):
> "You are the sole engineer responsible for the Nightshift codebase."

New framing (ownership-based):
> "You own this product. The session index, eval scores, and handoff
> trail are your track record. Every cycle, your past commitments are
> checked against actual results. Ship quality because you own the
> outcome, not because someone told you to."

This framing change is embedded in the skill preamble (evolve-auto.md) and replaces the current identity statement.

---

## Codex Compatibility

Codex (GPT-5.4, GPT-5.3-Codex-Spark) handles structured output differently than Claude. Historical evidence: Codex ignored structured output instructions 100% of the time across 23 sessions (900 sed reads vs 0 cat reads). The Process Verification Pipeline checkpoints assume the agent will output structured blocks (SIGNAL ANALYSIS, TRADEOFF ANALYSIS, PRE-COMMITMENT).

**Strategy: graceful degradation, not hard failure.**

- The checkpoints are phrased as prompt instructions, not enforced by daemon.sh parsing
- If Codex skips a checkpoint, the session still runs -- it just has less audit trail
- daemon.sh does NOT reject sessions missing checkpoint blocks
- The `extract_role_override()` function in lib-agent.sh handles "not found" gracefully (returns empty string)
- The STRATEGIZE role can detect missing checkpoints across sessions and flag it as a pipeline health issue
- Over time, if Codex consistently skips checkpoints, the human can decide to run Codex without the pipeline (via `NIGHTSHIFT_FORCE_ROLE=build` which bypasses the signal injection)

**Token budget for checkpoints:**
- SIGNAL ANALYSIS: ~200 tokens output (numbers + sources)
- TRADEOFF ANALYSIS: ~300 tokens (2-3 options with reasoning)
- PRE-COMMITMENT: ~100 tokens (metric + verification + fallback)
- Total overhead: ~600 tokens per session (~0.3% of 200K context, negligible)
- On 128K context (Spark): still <0.5%, but Spark already crashes on context overflow -- the checkpoints are not the bottleneck

---

## Rollback Plan

If the pipeline makes the agent worse (overthinks, burns tokens, never starts building):

**Per-phase rollback (each phase is a separate PR):**
- Phase 1 (urgency fix): revert the PR. Urgent tasks force BUILD again. Simple.
- Phase 2 (skill files): revert the PR. daemon.sh points back to original prompt paths.
- Phase 3 (pipeline checkpoints): revert the PR. Checkpoints removed from prompts. Signal injection removed from daemon.sh.
- Phase 4 (override): revert the PR. Override section removed, extraction removed.

**Kill switch without reverting:**
- Set `NIGHTSHIFT_PIPELINE_CHECKPOINTS=0` env var (new)
- daemon.sh checks this var: if 0, skip signal injection, skip ALL checkpoint text
- Implementation: checkpoint instructions are split across two layers:
  - **Layer 1:** `docs/prompt/checkpoints.md` — Checkpoint 1 (Signal Analysis), injected between evolve-auto.md and the skill prompt
  - **Layer 2:** Checkpoints 2-4 (Tradeoff, Pre-Commitment, Commitment Check) live in `skills/build.md` but are wrapped in a conditional marker:
    ```
    <!-- PIPELINE_CHECKPOINTS_START -->
    [Checkpoint 2-4 text]
    <!-- PIPELINE_CHECKPOINTS_END -->
    ```
  - When kill switch is 0, `build_prompt()` strips the marker-wrapped sections from the skill file before injecting:
    ```bash
    build_prompt() {
        cat "$AUTO_PREFIX"
        if [ "${NIGHTSHIFT_PIPELINE_CHECKPOINTS:-1}" = "1" ]; then
            cat "$REPO_DIR/docs/prompt/checkpoints.md"
            cat "$ROLE_PROMPT"
        else
            # Strip checkpoint blocks from skill file
            sed '/<!-- PIPELINE_CHECKPOINTS_START -->/,/<!-- PIPELINE_CHECKPOINTS_END -->/d' "$ROLE_PROMPT"
        fi
    }
    ```
- NO stale copy files. Checkpoint text is compositional. Future prompt edits to evolve-auto.md and skill files take effect regardless of kill switch state.
- When kill switch is 0, the agent gets the same prompt stack as before the pipeline was introduced (evolve-auto.md + skill, minus checkpoints).

**Detection: how do we know the pipeline is making things worse?**
- STRATEGIZE role reviews checkpoint quality (see below)
- If 5+ consecutive sessions have empty/formulaic SIGNAL ANALYSIS blocks, the pipeline is producing slop not insight
- If average session duration increases by >50% after pipeline deployment, the agent is overthinking
- If eval score doesn't improve within 10 sessions of pipeline deployment, the pipeline isn't helping

---

## Strategist Pipeline Validation

The STRATEGIZE role already reviews system health. It now also audits the Process Verification Pipeline:

**Add to `skills/strategize.md` Step 2 (Diagnose):**

```
### Pipeline Health

Review the last 10 session logs for pipeline checkpoint quality:

1. Signal Analysis blocks: Are they referencing real numbers from real files?
   Or are they formulaic copy-paste with stale data?
2. Tradeoff Analysis blocks: Are they genuinely weighing alternatives?
   Or always picking the same type of work with fake "alternatives"?
3. Pre-Commitments: Are they specific and measurable?
   Or vague ("improve code quality") and un-checkable?
4. Commitment Checks: Are previous commitments being verified honestly?
   Or rubber-stamped as "MET" without evidence?
5. Override usage: How often are overrides used? Are they justified?
   >20% override rate suggests pick-role.py needs recalibration.
   0% override rate suggests the agent isn't using its reasoning capability.

If checkpoints are producing formulaic slop instead of genuine reasoning,
recommend either: (a) rewriting the checkpoint instructions to be more
specific, or (b) disabling checkpoints via the kill switch until the
prompt is improved.
```

---

## Handoff Format Compatibility

Checkpoint 4 adds a "Commitment Check" section to handoffs. Existing systems that parse handoffs:

- `compact_handoffs()` in lib-agent.sh: compacts old handoffs into weekly summaries. Uses Python to read markdown. The Commitment Check section is just another markdown section -- no parsing changes needed. The compactor preserves all sections.
- Overseer prompt: reads handoffs for context. The new section is informational -- overseer doesn't need to parse it specifically.
- Builder Step 0: already reads LATEST.md. The Commitment Check verification is a new instruction in the skill prompt, not a parsing change.
- `docs/handoffs/README.md`: update the handoff format template to include the Commitment Check section so future sessions know it's expected.

**Only change needed:** Add the Commitment Check section to `docs/handoffs/README.md` template. No code changes to handoff parsing.

---

## Edge Cases

### First session after deployment (no previous Commitment Check)
The next session's Step 0 reads the previous handoff's Commitment Check. On the first session after deployment, the previous handoff won't have one. Handle gracefully:
```
Read the previous handoff's Commitment Check section.
If no Commitment Check section exists (first session after pipeline deployment
or non-BUILD previous session), skip verification and note:
"Previous commitment: N/A (no commitment check in previous handoff)"
```

### Multiple ROLE OVERRIDE lines in session log
The agent may discuss overrides in its reasoning before making the actual decision. The extraction takes the **last** match (handled by the Python parser iterating through all lines and keeping `last_match`).

### Skill file missing or deleted
If the agent overrides to a role whose skill file doesn't exist (typo, deleted file), the agent has no skill prompt. Add to evolve-auto.md override instructions:
```
If the skill file for your chosen role does not exist, revert to the
recommended role. Do not proceed without a skill prompt.
```
daemon.sh also validates: `pick_session_role()` already defaults to BUILD if the role is unrecognized (the `*)` case). For override extraction, the `case` statement only accepts known role names.

### Feature name manipulation for anti-loop gaming
The agent could avoid security keywords in its Feature field to bypass the anti-loop signal. Mitigated by the dual-signal approach (Feature keywords + task provenance). Even if Feature is gamed, completed pentest-sourced tasks in the archive still trigger the anti-loop.

### ROLE-SCORING.md divergence from code
ROLE-SCORING.md has diverged from pick-role.py in 5+ places. Out of scope for this plan -- create a follow-up task to reconcile. Phase 5 adds new documentation to it but does not fix existing drift.

### NIGHTSHIFT_FORCE_ROLE + signals + override precedence
Fully defined: (1) FORCE_ROLE env var = highest, human override. (2) pick-role.py = default, deterministic. (3) Agent override = audit-only, recorded in Override column, never changes Role column or scorer input.

### Standalone daemons loading old paths
`daemon-review.sh`, `daemon-overseer.sh`, `daemon-strategist.sh` keep loading original prompt files. They are deprecated but still shipped. NOT migrated in this plan. Original files stay as-is. Follow-up task to remove standalone daemons.

### Checkpoints only injected for some roles
Checkpoint 1 (Signal Analysis) is in `checkpoints.md` which is injected for ALL roles. Checkpoints 2-3 (Tradeoff, Pre-Commitment) are in `skills/build.md` only — they apply to BUILD sessions. Checkpoint 4 (Post-Session Audit) is in `skills/build.md` Step 0 — only BUILD sessions verify previous commitments. STRATEGIZE sessions audit checkpoint quality across all sessions via Pipeline Health. Non-BUILD roles (REVIEW, OVERSEE, ACHIEVE) do not produce Pre-Commitments — their success metrics are different (files reviewed, tasks closed, autonomy score delta).

### Prompt stack documentation drift
After Phase 3, the prompt stack is: `evolve-auto.md` + `checkpoints.md` (if enabled) + `skills/{role}.md`. Phase 5 must update `CLAUDE.md`, `docs/ops/DAEMON.md`, and `docs/ops/ROLE-SCORING.md` to describe this three-file stack. Failing to update creates confusion when operators read docs that say "evolve-auto.md + one role prompt."

### unified.md overlap
`docs/prompt/unified.md` is an earlier attempt at unified role selection. Explicitly retired in Phase 2 with a one-line superseded note. Not deleted (historical reference).

---

## Preserved Infrastructure (non-negotiable)

These systems stay exactly as they are. Removing any of them would be a security or testability regression:

- `scripts/pick-role.py` -- deterministic scoring engine. Gains `--with-signals` flag but core logic preserved.
- Mandatory pentest preflight -- builder doesn't red-team itself. Conflict of interest.
- `_is_valid_eval_file()`, `_is_valid_autonomy_file()`, `_read_frontmatter()` -- input validation guards against fabricated files poisoning role selection.
- 652+ lines of test coverage in `tests/test_pick_role.py` -- all existing tests pass unchanged.
- `NIGHTSHIFT_FORCE_ROLE` env var -- manual override escape hatch.
- Session index Role column -- `pick_session_role()` still sets `SESSION_ROLE` deterministically. Agent override goes to the separate Override column, NEVER modifies Role.

---

## Implementation Sequence

### Phase 1: Fix the urgency loop (Change A) -- break the immediate bug
1. Add `recent_security_sessions` dual-signal to pick-role.py `main()`:
   - **Signal A (fast, lossy):** Count from `index_rows[-5:]` Feature field, match `_SECURITY_KEYWORDS`, only `role == "build"` sessions
   - **Signal B (robust, structured):** Add `count_pentest_sourced_tasks_completed()` — reads archived tasks with `source: pentest` in frontmatter using existing `_read_frontmatter()` contract
   - Combined: `recent_security_sessions = max(signal_a, signal_b)`
   - Update evolve-auto.md PENTEST DATA RULE: tasks from pentest must include `source: pentest` in frontmatter
2. Pass it into `signals` dict for `compute_scores()` to consume
3. In `compute_scores()`: if `recent_security_sessions >= 3` and `urgent_tasks`, demote BUILD by 15
4. In `pick_role()`: add `recent_security` param. Only force BUILD on urgent when `recent_security < 3` (fixes the short-circuit bypass on line 391)
5. In `main()`: pass `recent_security_sessions` to `pick_role()`
6. Update `docs/prompt/evolve-auto.md` PENTEST DATA RULE: tasks from pentest default `priority: normal` unless confirmed exploitable
7. Update `docs/prompt/pentest.md` output format: add CONFIRMED vs THEORETICAL severity
8. Add tests: `test_security_loop_demotion`, `test_urgent_bypass_respects_security_loop`, `test_security_signal_uses_feature_not_status`
9. `make check`
10. Ship as PR, merge

### Phase 2: Create skill files (Change B) -- organize the prompt layer
1. `mkdir docs/prompt/skills`
2. Extract each skill from existing prompts:
   - `skills/build.md` from evolve.md (strip identity/context/universal rules)
   - `skills/review.md` from review.md
   - `skills/oversee.md` from overseer.md
   - `skills/strategize.md` from strategist.md
   - `skills/achieve.md` from achieve.md
   - `skills/security-check.md` from pentest.md (unchanged content, new location)
3. Move BUILD-specific rules from evolve-auto.md into skills/build.md preamble:
   - TASK SELECTION RULE
   - EVAL SCORE GATE
   - TASK VALUE SCORING
   - RELEASE RULE
4. Update daemon.sh `pick_session_role()` case statement to point to `docs/prompt/skills/` paths
5. Update `scripts/lib-agent.sh`:
   - Add 6 skill files to `PROMPT_GUARD_FILES` array
   - Add `"docs/prompt/skills"` to `PROMPT_GUARD_DIRS` array
   - KEEP all existing entries (original prompts still exist as files, must stay guarded)
6. `make check`
7. `python3 -m nightshift run --dry-run --agent codex > /dev/null` (verify prompt assembly)
8. `python3 -m nightshift run --dry-run --agent claude > /dev/null`
9. Ship as PR, merge

### Phase 3: Process Verification Pipeline (Change C) -- the core anti-RLHF system
1. Modify pick-role.py to output signals alongside the role decision (single invocation, no double file scan):
   - Add `--with-signals` flag (not `--signals-only` — avoids a second subprocess)
   - When set, print JSON signals to a temp file alongside normal role selection
   - daemon.sh reads the temp file after `pick_session_role()` returns
   - Reuses all existing signal reader functions (validated, tested)
   - JSON schema is numeric/boolean/enum ONLY — no free-form strings
2. Update daemon.sh:
   - `pick_session_role()` passes `--with-signals /tmp/nightshift-signals.json`
   - After role selection, read the signals file and inject into prompt as `<system_signals>` block
   - Sanitize the block with the same tag-escaping pattern as `<pentest_data>`
   - Add `NIGHTSHIFT_PIPELINE_CHECKPOINTS` env var kill switch (default: 1 = enabled)
   - When kill switch is 0: skip signal injection, skip `checkpoints.md` in `build_prompt()`
   - Checkpoint text lives in `docs/prompt/checkpoints.md` (compositional, no stale copy)
3. Add Checkpoint 1 (Signal Analysis) to evolve-auto.md:
   - Agent must output SIGNAL ANALYSIS block referencing specific numbers from injected signals
   - Numbers must be verifiable against actual files
4. Add Checkpoint 2 (Forced Tradeoff) to skills/build.md Step 2:
   - Must state 2+ options with impact and cost-of-skipping for each
   - Must explicitly name what is NOT being done and why
5. Add Checkpoint 3 (Pre-Commitment) to skills/build.md Step 3:
   - Declare measurable success metric before starting work
   - Format: "Metric: [specific measure]. Verification: [how to check]. Fallback: [if it fails]"
6. Add Checkpoint 4 (Post-Session Audit) to:
   - Handoff template (`docs/handoffs/README.md`): add "Commitment Check" section
   - skills/build.md Step 0: read previous handoff's Commitment Check, verify if met/missed
   - If same commitment missed 3+ times, create investigation task
7. Add Pipeline Health section to skills/strategize.md Step 2:
   - Review last 10 session logs for checkpoint quality (real analysis vs formulaic slop)
   - Check override frequency (>20% = recalibrate scoring, 0% = agent not using reasoning)
   - Check commitment met/missed ratio
   - Recommend kill switch if checkpoints are producing slop
8. Update ownership framing in evolve-auto.md:
   - Replace "sole engineer responsible" with CTO/owner framing
   - Based on Soul Spec: helpful because you own it, not because you're programmed to please
9. `make check`
10. Ship as PR, merge

### Phase 4: Agent Override (Change D) -- contextual reasoning escape hatch
1. Add ROLE OVERRIDE section to evolve-auto.md:
   - Agent can override pick-role.py's recommendation with evidence from Signal Analysis
   - Must state recommended role + score, chosen role + evidence
   - Must output `ROLE OVERRIDE: [recommended] -> [chosen]: [evidence]`
   - Must read `docs/prompt/skills/{chosen-role}.md` and follow it instead
2. Add `extract_role_override()` to `scripts/lib-agent.sh` (shared helper, not inline):
   - Parse JSONL log, take last ROLE OVERRIDE match
   - Use `sed -n 's/.*-> \([a-z]*\).*/\1/p'` (macOS-compatible, no grep -oP)
   - Validate extracted role against known names (build|review|oversee|strategize|achieve)
   - Write to OVERRIDE_NOTE variable — goes to Override column ONLY
   - SESSION_ROLE is NEVER modified — Role column stays machine-generated
3. Migrate session-index schema to 10 columns (ALL consumers, not conditional):
   - `scripts/daemon.sh`: update index header (line ~73) and index write (line ~428) to include Override column. Write `$OVERRIDE_NOTE` or `-` if no override.
   - `scripts/pick-role.py`: update `parse_session_index()` to handle 10 columns. Override column is parsed but IGNORED by `compute_scores()`, `count_consecutive_role()`, `count_sessions_since_role()`.
   - `nightshift/costs.py`: update any session-index parsing to handle 10 columns gracefully (skip Override).
   - `tests/test_pick_role.py`: update ALL test fixtures with 10-column format. Add `test_parse_session_index_10_columns` and `test_override_column_ignored_by_scorer`.
   - `tests/test_nightshift.py`: update session-index fixtures and add `test_session_index_10_column_format`.
3. Add test: `test_role_override_extraction` in test_nightshift.py
4. `make check`
5. Ship as PR, merge

### Phase 5: Update documentation
1. CLAUDE.md -- update Daemon section:
   - Document skill paths replacing direct prompt paths
   - Document Process Verification Pipeline (4 checkpoints)
   - Document agent override mechanism
2. docs/ops/ROLE-SCORING.md -- add:
   - Anti-security-loop signal documentation
   - Override mechanism documentation
   - Pipeline checkpoint documentation

### Phase 6: Validate end-to-end
1. `make check` (all tests green, 1136+ existing + new tests)
2. `python3 scripts/pick-role.py /path/to/repo` -- still works, outputs role + reasoning
3. `python3 scripts/pick-role.py /path/to/repo --with-signals /tmp/test-signals.json` -- outputs role AND writes signals JSON
4. Run 1 daemon session with `bash scripts/daemon.sh claude 60 1`:
   - Pentest preflight still runs (not removed)
   - pick-role.py still selects role (deterministic)
   - Skill file loads from `docs/prompt/skills/`
   - Agent outputs SIGNAL ANALYSIS block with verifiable numbers
   - Agent outputs TRADEOFF ANALYSIS with 2+ options
   - Agent outputs PRE-COMMITMENT with measurable metric
   - Handoff includes Commitment Check section
   - Session index records correct role
5. Simulate security loop: create 3 pentest-status sessions in index, verify:
   - BUILD score drops by 15
   - `pick_role()` does NOT force BUILD on urgent (anti-loop active)
6. `python3 -m nightshift run --dry-run --agent codex > /dev/null`
7. `python3 -m nightshift run --dry-run --agent claude > /dev/null`
