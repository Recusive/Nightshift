# Plan: Sub-Agent Driven Architecture (v2)

## Context

The Recursive autonomous framework is trapped in a rigid single-agent model. A Python scoring engine (pick-role.py) picks one of 8 operators per session. The agent is locked into that role. In live testing, the agent overrides its role every session because it makes better decisions than the scoring engine. The agent can't distinguish between the framework (Recursive/) and the project (nightshift/) — it treats them as one repo and modifies framework files despite being told not to. The evolve/audit operators (meant for self-improvement) never fire because triggering conditions are too strict.

**Goal:** Rebuild as a sub-agent driven system where a brain agent (Opus) reads a dashboard, thinks, delegates to sub-agents (Sonnet) in git worktrees, reviews their PRs, and merges. Move Recursive/ into .recursive/ so the agent's code and memory live in one place.

**Audits:**
1. Opus 4.6 auditor (2026-04-07): APPROVE WITH CHANGES — 5 critical, 8 recommendations. Incorporated.
2. Second audit (2026-04-07): NEEDS REWORK — 5 critical sequencing issues. Fixed.
3. Third audit (2026-04-07): APPROVE WITH CHANGES — 4 remaining gaps. Fixed.
4. Fourth audit (2026-04-07): APPROVE WITH CHANGES — 4 operational gaps. Fixed.
5. Fifth audit (2026-04-07): APPROVE WITH CHANGES — 2 gaps. Fixed.
6. Sixth audit (2026-04-07): APPROVE WITH CHANGES — 2 final gaps. Fixed.
7. Seventh audit (2026-04-07): APPROVE WITH CHANGES — 1 gap (--help probe invalid). Fixed.
8. Eighth audit (2026-04-07): APPROVE WITH CHANGES — 1 gap (test reliability). Fixed.

---

## Phase 0: Spike Test + Foundation (no existing changes)

### Step 0: Agent() Pipe Mode Spike (audit2 #5 — moved to FIRST)
The entire architecture depends on `Agent()` with `isolation: "worktree"` working inside `claude -p` pipe mode. Test this BEFORE building anything.
- Write a minimal test prompt that launches one sub-agent in a worktree
- Run: `claude -p "$PROMPT" --output-format stream-json --model claude-opus-4-6`
- Confirm: Agent() tool is available, worktree is created, sub-agent runs, results return
- **If it works:** proceed with plan as-is
- **If NOT available:** redesign delegation as daemon-level subprocess calls (`claude -p` per sub-agent), brain communicates via files. Document the alternative architecture before proceeding.
- This spike takes 10 minutes and gates $50+ of implementation work

### Runtime Files (safe — these go in `.recursive/` runtime dirs, already auto-committed)
- `.recursive/decisions/log.md` — decision journal (append-only)
- `.recursive/commitments/log.md` — commitment tracking
- `.recursive/incidents/log.md` — incident log

### Signal Reader Extraction
- Extract signal-reading functions from `Recursive/engine/pick-role.py` into `Recursive/engine/signals.py` (NOT `Recursive/lib/`) (audit2 #1 fix: `Recursive/engine/` is already in PROMPT_GUARD_FILES)
  - All signal readers + validation functions
- Refactor pick-role.py to import from `signals.py`
- Add `Recursive/engine/signals.py` to `PROMPT_GUARD_FILES` in lib-agent.sh

### Dashboard
- `Recursive/engine/dashboard.py` — data aggregator (audit2 #2 fix: lives in `Recursive/engine/`, NOT `.recursive/engine/`, because v1 daemon auto-commits all `.recursive/`)
  - Imports signal readers from `Recursive/engine/signals.py`
  - Outputs structured dashboard text
  - Gracefully handles missing task frontmatter fields
- Add `Recursive/engine/dashboard.py` to `PROMPT_GUARD_FILES` in lib-agent.sh

### Task Frontmatter Expansion
- Add optional fields: `touched_by`, `last_touched`, `attempts`
- Update `.recursive/tasks/GUIDE.md`

### Extend `make check` + CI Coverage (audit3 #1 + audit4 #1)
- Update `nightshift/scripts/check.sh` to include ALL framework Python and shell:
  - `Recursive/engine/*.py` — ruff + mypy
  - `Recursive/lib/*.py` — ruff + mypy
  - `Recursive/engine/*.sh` + `Recursive/scripts/*.sh` — shell syntax check (`bash -n`) (audit5 #1)
  - ASCII check on `Recursive/engine/` and `Recursive/lib/`
- Update `pyproject.toml` tool sections to cover `Recursive/engine/` and `Recursive/lib/`
- Update `.github/workflows/ci.yml` to match local check.sh coverage (same paths)
- This must happen BEFORE adding signals.py and dashboard.py so they're covered from creation

### Verification
- Spike: Agent() works in pipe mode (or alternative architecture documented)
- `python3 Recursive/engine/dashboard.py .recursive/` produces valid output
- Signal parity: dashboard.py values match pick-role.py values
- `make check` passes AND covers signals.py + dashboard.py (ruff, mypy)
- `Recursive/engine/signals.py` and `dashboard.py` are in PROMPT_GUARD_FILES

---

## Phase 1: Sub-Agent Definitions (additive only)

All new agent definitions go in `Recursive/agents/` (NOT `.recursive/agents/`) — the guarded framework directory. They move to `.recursive/` in Phase 5.

### Canonical Template (audit R2)
Write `Recursive/agents/TEMPLATE.md` with mandatory sections:
Identity, Zone Rules, Process Steps, Verification, Output Format, Gotchas

Write `build.md` first as exemplar. Review. Derive others.

### New Agent Definitions (8 new, rewritten from operators)
Project agents (zone: target, worktree: yes):
- `Recursive/agents/build.md` — from operators/build/SKILL.md (NEW content)
- `Recursive/agents/review.md` — from operators/review/SKILL.md (NEW)
- `Recursive/agents/oversee.md` — from operators/oversee/SKILL.md (NEW)
- `Recursive/agents/achieve.md` — from operators/achieve/SKILL.md (NEW)

Project agents (zone: target, worktree: no):
- `Recursive/agents/strategize.md` — from operators/strategize/SKILL.md (NEW)
- `Recursive/agents/security.md` — from operators/security-check/SKILL.md (NEW)

Framework agents (zone: framework, worktree: yes):
- `Recursive/agents/evolve.md` — from operators/evolve/SKILL.md (NEW)
- `Recursive/agents/audit-agent.md` — from operators/audit/SKILL.md (NEW)

### Existing Review Agents (5 existing, already in Recursive/agents/)
- `code-reviewer.md`, `safety-reviewer.md`, `architecture-reviewer.md`, `docs-reviewer.md`, `meta-reviewer.md`
- Already guarded. No changes needed — they stay where they are.

### Format
```yaml
---
name: build
zone: project
worktree: true
model: sonnet
schema_version: 1
---
```

### Verification
- All 8 new files parse valid YAML frontmatter
- Diff against original SKILL.md confirms no operational content lost
- New agents added to PROMPT_GUARD_FILES in lib-agent.sh
- `make check` passes

---

## Phase 2: Brain Prompt (additive only)

### Files Created
- `Recursive/prompts/brain.md` (~250 lines) — lives in `Recursive/prompts/` (guarded), NOT `.recursive/prompts/` (auto-committed) (audit2 #2 fix)

### Brain Prompt Structure
| Section | Lines | Content |
|---------|-------|---------|
| Identity | ~20 | Orchestrator, not coder |
| Context Gathering | ~15 | Read handoff, dashboard, friction, tasks |
| Thinking Framework | ~30 | 4 checkpoints |
| Agent Catalog | ~25 | 13 agents with zone, worktree, model |
| Delegation Protocol | ~20 | Launch syntax, worktree, parallel rules |
| Review Protocol | ~20 | Code-reviewer launch, zone compliance |
| Sub-Agent Output Handling | ~15 | Injection hardening (audit C5) |
| Merge + Report | ~20 | Merge, mandatory friction, decision journal |
| Zone Rules | ~15 | One zone per delegation, conflict resolution |
| Tier Rules | ~15 | Tier 1 reject, Tier 2 evolve/audit only |
| Thinking Budget | ~5 | 15 turns max before delegating |

### autonomous.md → brain.md (audit M1)
brain.md is the full replacement for autonomous.md. Different identity model (orchestrator vs hands-on coder). NOT a path substitution — a conceptual rewrite. daemon-v2.sh loads brain.md. autonomous.md stays for v1.

### Verification
- brain.md reviewed for completeness
- Added to PROMPT_GUARD_FILES
- `make check` passes

---

## Phase 3: v2 Daemon + Selective Commit (audit2 #2 critical fix)

### Files Created
- `Recursive/engine/daemon-v2.sh` (~350 lines) — separate file (audit R1)
  - **Immediately add to `PROMPT_GUARD_FILES` in lib-agent.sh** (audit4 #2 — control-plane file must be guarded from creation)
  - Sources same lib-agent.sh
  - `run_dashboard()`: calls dashboard.py
  - `build_brain_prompt()`: project_context + brain.md + `<dashboard>`
  - SESSION_ROLE extracted from brain's ROLE DECISION block
  - Guard: if brain.md not found → abort with error
  - **Selective git add** (audit2 #2): commits ONLY runtime state dirs, never framework:
    ```bash
    # Runtime state only — framework changes go through PRs
    for dir in handoffs tasks sessions learnings evaluations autonomy \
               strategy healer reviews friction decisions commitments \
               incidents vision vision-tracker changelog architecture plans; do
        git add ".recursive/$dir/" 2>/dev/null || true
    done
    ```

### Files Modified
- `Recursive/engine/lib-agent.sh`
  - Add `PROMPT_GUARD_FILES_V2` array covering `.recursive/engine/`, `.recursive/prompts/`, `.recursive/agents/` (for post-move Phase 5)
  - Add tiered `check_prompt_integrity_v2()`: Tier 1 → revert, Tier 2 → gated, Tier 3 → log
  - Add `check_zone_compliance(pr_number, agent_zone)` — mechanical enforcement (created here, called in Phase 4):
    - Reads PR diff via `gh pr diff`
    - Uses `$FRAMEWORK_DIR` variable (not hardcoded path) so it works both pre-move (`Recursive/`) and post-move (`.recursive/`) (audit3 #2)
    - Project-zone PR touching ANY framework dir → return FAIL (audit4 #3 — covers all, not just engine/prompts):
      - `$FRAMEWORK_DIR/engine/`, `$FRAMEWORK_DIR/prompts/`, `$FRAMEWORK_DIR/agents/`, `$FRAMEWORK_DIR/operators/`, `$FRAMEWORK_DIR/skills/`, `$FRAMEWORK_DIR/lib/`, `$FRAMEWORK_DIR/ops/`, `$FRAMEWORK_DIR/scripts/`, `$FRAMEWORK_DIR/tests/`, `$FRAMEWORK_DIR/templates/`, `$FRAMEWORK_DIR/CLAUDE.md`, `$FRAMEWORK_DIR/AGENTS.md` (audit6 #1 — every framework surface covered, including skills/ and root docs)
    - Framework-zone PR touching `nightshift/` → return FAIL
    - **Path matching uses repo-relative paths** (audit5 edge case): `$FRAMEWORK_DIR` stripped to repo-relative before comparing against `gh pr diff` output (which is always repo-relative)

### Guard Recursive/lib/ Before Modifying (audit3 #3)
- Add `Recursive/lib/` to `PROMPT_GUARD_DIRS` in lib-agent.sh
- Add `Recursive/lib/costs.py` to `PROMPT_GUARD_FILES` in lib-agent.sh
- This MUST happen before touching costs.py — the daemon uses it for budget enforcement

### Mixed-Model Cost Accounting (audit2 #4)
- Update `Recursive/lib/costs.py` to support multi-model sessions:
  - `record_session_bundle()` accepts optional `sub_sessions` list
  - Each sub-session has its own model, token counts, cost
  - Session total = brain cost + sum(sub-session costs)
  - Budget check uses the aggregate total
- daemon-v2.sh passes sub-agent JSONL logs to cost tracking

### Verification
- `bash Recursive/engine/daemon.sh claude 60 1` — v1 unchanged
- `bash Recursive/engine/daemon-v2.sh claude 60 1` — brain runs, produces handoff
- Selective git add: `git status` after commit shows framework dirs NOT staged
- Mixed-model cost test: brain (Opus) + sub-agent (Sonnet) correctly summed
- `make check` passes

---

## Phase 4: Sub-Agent Worktree Execution (core change)

### Files Modified
- `Recursive/prompts/brain.md` — add real Agent() syntax (confirmed working from Phase 0 spike)
- `Recursive/agents/*.md` — add worktree instructions
- `Recursive/engine/daemon-v2.sh`:
  - Worktree cleanup in housekeeping
  - Multi-agent cost aggregation
  - Call `check_zone_compliance()` on each sub-agent PR before brain review
  - Multiple open PR recovery: `gh pr list` with `.[0:5]` not `.[0]`
- `Recursive/engine/lib-agent.sh` — add `cleanup_worktrees()` function

### Symlink Update
- `.claude/agents/*.md` — add symlinks for new agent definitions (build, review, etc.)
- Keep existing review agent symlinks
- Update `Recursive/scripts/init.sh` symlink creation

### Edge Cases
- Worktree creation failure → retry with different branch name, or single-agent fallback
- Parallel conflicts → brain must not launch parallel agents on overlapping files
- Brain crash → daemon-v2.sh recovers up to 5 open PRs
- Framework-zone agent also needs to persist runtime docs → zone rules allow writing to `.recursive/` runtime dirs regardless of zone (handoffs, tasks, friction are always writable)

### Verification
- Brain launches build sub-agent in worktree → PR created
- Brain launches code-reviewer → PASS/FAIL returned
- `check_zone_compliance()` mechanically catches cross-zone PRs
- Brain merges approved PR
- Cost tracking: session total = brain + sub-agents (mixed model)
- Worktrees cleaned up
- Full cycle: think → delegate → review → merge → report

---

## Phase 5: Physical Directory Move

### Step 0: Rollback Anchor (audit C3)
- `git tag v2-pre-move`
- Write `Recursive/scripts/rollback-v2-move.sh`
- Rule: `make check` fails after any substep → `git reset --hard v2-pre-move`

### Steps
1. Stop daemon
2. `git mv` each subdirectory (verify after each):
   - `Recursive/engine/` → `.recursive/engine/` (merge with existing dashboard.py, daemon-v2.sh, signals.py)
   - `Recursive/lib/` → `.recursive/lib/`
   - `Recursive/ops/` → `.recursive/ops/`
   - `Recursive/scripts/` → `.recursive/scripts/`
   - `Recursive/templates/` → `.recursive/templates/`
   - `Recursive/tests/` → `.recursive/tests/`
   - `Recursive/agents/` → `.recursive/agents/` (merge with existing review agents)
   - `Recursive/prompts/` → `.recursive/prompts/` (merge with brain.md)
   - `Recursive/skills/` → `.recursive/skills/`
   - `Recursive/operators/` → `.recursive/operators-v1/` (archive)
3. Handle root-level `Recursive/` files (audit3 #4):
   - `Recursive/CLAUDE.md` → delete (root `CLAUDE.md` is authoritative, already covers framework)
   - `Recursive/AGENTS.md` → delete (root `AGENTS.md` is authoritative)
   - `Recursive/README.md` → delete if exists (setup docs updated in root CLAUDE.md)
   - Update root `CLAUDE.md` to replace all "see `Recursive/CLAUDE.md`" references
   - Update root `AGENTS.md` to replace all "see `Recursive/AGENTS.md`" references
4. Delete `Recursive/` directory (now empty)
5. Rename `daemon-v2.sh` → `daemon.sh`, delete old v1 daemon
6. Update path discovery in daemon.sh
7. Update ALL prompt guard arrays (audit C1):
   - `PROMPT_GUARD_FILES` → all `.recursive/` paths
   - `PROMPT_GUARD_DIRS` → all `.recursive/` paths (including `.recursive/lib/`)
   - `PROMPT_GUARD_CONTENT_DIRS` → all `.recursive/` paths
   - Verify: `grep -c 'Recursive/' lib-agent.sh` = 0
8. Update ALL path consumers (audit2 #3 + audit3 #4 + audit4 #4 — complete list):
   - `CLAUDE.md` — ~20 references + absorb content from deleted `Recursive/CLAUDE.md`
   - `AGENTS.md` — ~15 references + absorb content from deleted `Recursive/AGENTS.md`
   - `README.md` — setup instructions, getting started commands (audit4 #4)
   - `Makefile` — 6 references
   - `pyproject.toml` — tool paths, test paths
   - `nightshift/scripts/check.sh` — 6 references
   - `.github/workflows/ci.yml` — framework test paths
   - `.recursive/engine/watchdog.sh` — process monitoring paths
   - `.recursive/engine/format-stream.py` — report paths
   - `.recursive/scripts/init.sh` — setup paths, symlink targets, setup instructions
   - `.recursive/skills/setup/SKILL.md` — first-run wizard paths and commands (audit4 #4)
   - `.recursive/ops/*.md` — ~100 references
   - `.gitignore` — verify coverage
9. Re-target symlinks: `.claude/agents/` → `../.recursive/agents/`

### Automated Path Verification (audit R7)
```bash
# Path grep — must return zero lines
grep -rn 'Recursive/' --include='*.md' --include='*.sh' --include='*.py' \
  --include='*.yml' --include='*.toml' --include='Makefile' . \
  | grep -v '.git/' | grep -v '.recursive/tasks/' | grep -v '.recursive/sessions/' \
  | grep -v '.recursive/learnings/' | grep -v '.recursive/reviews/' \
  | grep -v 'operators-v1/' | grep -v 'Runtime/'
```

### Startup/Setup Command Regression Test (audit6 #2 + audit7 #1 + audit8 #1)
```bash
#!/bin/bash
# verify-move.sh — run after Phase 5, exit non-zero on any failure
set -euo pipefail
fail=0
# Verify framework files exist at new paths (test -f, not -x — scripts invoked via bash)
for f in .recursive/engine/daemon.sh .recursive/engine/lib-agent.sh \
         .recursive/engine/dashboard.py .recursive/engine/signals.py \
         .recursive/scripts/init.sh .recursive/scripts/list-tasks.sh; do
    test -f "$f" || { echo "MISSING: $f"; fail=1; }
done
# Shell syntax check (parse without executing)
for f in .recursive/engine/daemon.sh .recursive/engine/lib-agent.sh \
         .recursive/scripts/init.sh .recursive/scripts/list-tasks.sh; do
    bash -n "$f" || { echo "SYNTAX ERROR: $f"; fail=1; }
done
# Makefile targets work
make check || { echo "make check failed"; fail=1; }
make tasks || { echo "make tasks failed"; fail=1; }
# No docs reference stale paths
stale=$(grep -rn 'bash Recursive/' CLAUDE.md AGENTS.md README.md \
  .recursive/skills/setup/SKILL.md .recursive/ops/*.md 2>/dev/null || true)
if [ -n "$stale" ]; then
    echo "STALE REFERENCES:"; echo "$stale"; fail=1
fi
exit $fail
```

### Verification
- `bash .recursive/engine/daemon.sh claude 60 1` runs
- `make check` passes
- Path verification returns zero lines
- All symlinks resolve
- Prompt guard arrays have zero `Recursive/` references

---

## Phase 6: Cleanup + Hardening

- Delete `.recursive/operators-v1/`
- Delete pick-role.py scoring functions (signal readers stay in signals.py)
- Update tests: `test_pick_role.py` → `test_dashboard.py` + `test_signals.py`
- Update `init.sh` for new directory structure
- Set up `.codex/agents/` equivalent
- Update `.recursive/learnings/` entries with stale `Recursive/` paths
- Cross-phase integration: 3 consecutive v2 cycles end-to-end
- 10+ daemon cycles for stability

---

## Critical Files

| File | What Changes | Phase |
|------|-------------|-------|
| `Recursive/engine/daemon.sh` (23K) | Stays v1 until Phase 5 | 5 |
| `Recursive/engine/daemon-v2.sh` | NEW — v2 daemon | 3 |
| `Recursive/engine/lib-agent.sh` (47K) | Tiered guard, zone check, guard arrays | 0,3,5 |
| `Recursive/engine/pick-role.py` (22K) | Signal extraction | 0 |
| `Recursive/engine/signals.py` | NEW — shared signal readers | 0 |
| `Recursive/engine/dashboard.py` | NEW — data aggregator | 0 |
| `Recursive/prompts/brain.md` | NEW — orchestrator prompt | 2 |
| `Recursive/agents/*.md` (8 new) | NEW — sub-agent definitions | 1 |
| `Recursive/lib/costs.py` | Mixed-model cost accounting | 3 |
| `CLAUDE.md` | Path updates | 5 |
| `Makefile` | Path updates | 5 |
| `pyproject.toml` | Path updates | 5 |

---

## Key Design Decisions (audit2 fixes)

1. **All new v2 files live in `Recursive/` (guarded) during Phases 0-4, NOT in `.recursive/` (auto-committed).** They only move to `.recursive/` in Phase 5. This prevents v1's `git add .recursive/` from auto-committing framework code. (audit2 #2)

2. **signals.py goes in `Recursive/engine/` (already guarded), not `Recursive/lib/` (unguarded).** (audit2 #1)

3. **Spike test is Phase 0 Step 0.** If Agent() doesn't work in pipe mode, the architecture changes before any work is done. (audit2 #5)

4. **costs.py updated in Phase 3** to handle mixed Opus+Sonnet sessions. Budget check uses aggregate cost. (audit2 #4)

5. **Complete path consumer inventory** includes pyproject.toml, watchdog.sh, format-stream.py, init.sh. (audit2 #3)

6. **`make check` extended to cover `Recursive/engine/*.py`** before adding new Python files there. Prevents silent lint/type defects in framework code. (audit3 #1)

7. **`check_zone_compliance()` uses `$FRAMEWORK_DIR` variable**, not hardcoded paths. Works both pre-move (`Recursive/`) and post-move (`.recursive/`). (audit3 #2)

8. **`Recursive/lib/` added to prompt guard** before modifying costs.py. Closes the gap where a target operator could modify budget enforcement code. (audit3 #3)

9. **Root-level `Recursive/CLAUDE.md` and `Recursive/AGENTS.md` explicitly deleted** in Phase 5 with content absorbed into root docs. No orphaned files after directory deletion. (audit3 #4)

10. **`make check` + CI cover ALL framework code** — `Recursive/engine/*.py`, `Recursive/lib/*.py`, shell syntax, ASCII. Local and CI match. (audit4 #1)

11. **`daemon-v2.sh` added to prompt guard on creation**, not deferred. Control-plane files are guarded from the moment they exist. (audit4 #2)

12. **Zone compliance covers ALL framework dirs**, not just engine/prompts. Agents, lib, ops, scripts, tests, templates all protected from project-zone workers. (audit4 #3)

13. **README.md and setup skill updated** in Phase 5 path migration. Users following setup docs won't hit deleted paths. (audit4 #4)

---

## Verification (end-to-end)

1. Spike: Agent() works in pipe mode (Phase 0, gates everything)
2. `make check` passes at every phase
3. v1 daemon unchanged through Phases 0-4
4. v2 brain completes: think → delegate → review → merge → report
5. Sub-agents create PRs in worktrees, never touch local tree
6. Zone compliance mechanically rejects cross-zone PRs
7. Selective git add: framework dirs never auto-committed
8. Cost tracking: mixed-model aggregate correct, budget enforced
9. Rollback: `git reset --hard v2-pre-move` recovers from Phase 5 failure
10. 10+ consecutive v2 cycles without failure after Phase 5
