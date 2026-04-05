# Vision Tracker

Last updated: 2026-04-05 by agent session #0028 (Healer meta-layer observer).

This file is the single source of truth for how close Nightshift is to its vision. Updated by the agent every session. The human never edits this — the agent reads the code, checks what exists, and recalculates.

---

## Overall Progress

```
NIGHTSHIFT VISION                              ████████████████░░░░  77%
├── Loop 1 — Hardening Loop                    ████████████████████ 100%
├── Loop 2 — Feature Builder Loop              █████████████░░░░░░░  63%
├── Self-Maintaining Repo                      ████████████░░░░░░░░  57%
└── Meta-Prompt System                         █████████████░░░░░░░  61%
```

---

## Loop 1 — Hardening Loop (100%)

The core loop works end-to-end. The orchestrator, agent adapters, verification, and state tracking are functional. What's missing: intelligence improvements that make the agent find better issues.

| Component | Status | Progress |
|---|---|---|
| Python orchestrator | Done | ████████████████████ 100% |
| Codex adapter | Done | ████████████████████ 100% |
| Claude adapter | Done | ████████████████████ 100% |
| Worktree isolation | Done | ████████████████████ 100% |
| Runner-enforced guard rails | Done | ████████████████████ 100% |
| Machine-readable state | Done | ████████████████████ 100% |
| Baseline verification | Done | ████████████████████ 100% |
| Post-cycle verification | Done | ████████████████████ 100% |
| Shift log generation | Done | ████████████████████ 100% |
| Category dominance check | Done | ████████████████████ 100% |
| Path bias detection | Done | ████████████████████ 100% |
| Hot-file protection | Done | ████████████████████ 100% |
| Halt conditions | Done | ████████████████████ 100% |
| Test suite (659 tests) | Done | ████████████████████ 100% |
| Post-cycle diff scorer | Done | ████████████████████ 100% |
| Cycle-to-cycle state injection | Done | ████████████████████ 100% |
| Test writing incentives | Done | ████████████████████ 100% |
| Backend exploration forcing | Done | ████████████████████ 100% |
| Category balancing directive | Done | ████████████████████ 100% |
| Multi-repo support | Done | ████████████████████ 100% |
| Deep merge for config | Done | ████████████████████ 100% |
| run_command timeout fix | Done | ████████████████████ 100% |

### Bugs Found (not yet fixed)
- None

---

## Loop 2 — Feature Builder Loop (63%)

Repo profiling, feature planning, task decomposition, sub-agent spawning, wave integration, and the build orchestrator are complete. Sub-agent coordination, E2E test runner, production-readiness checker, and feature summary generation remain.

| Component | Status | Progress |
|---|---|---|
| Repo understanding / profiling | Done | ████████████████████ 100% |
| Feature planner | Done | ████████████████████ 100% |
| Task decomposer | Done | ████████████████████ 100% |
| Sub-agent spawner / manager | Done | ████████████████████ 100% |
| Sub-agent coordination | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Integration / merge engine | Done | ████████████████████ 100% |
| E2E test runner | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Feature CLI (`nightshift build`) | Done | ████████████████████ 100% |
| Feature state tracking | Done | ████████████████████ 100% |
| Production-readiness checker | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Feature summary generation | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |

---

## Self-Maintaining Repo (57%)

The infrastructure that lets the agent manage everything without human intervention.

| Component | Status | Progress |
|---|---|---|
| Vision docs | Done | ████████████████████ 100% |
| Self-improving prompt (evolve.md) | Done | ████████████████████ 100% |
| Changelog system (per-version) | Done | ████████████████████ 100% |
| Vision tracker (this file) | Done | ████████████████████ 100% |
| CLAUDE.md (agent context) | Done | ████████████████████ 100% |
| CI pipeline (.github/workflows) | Done | ████████████████████ 100% |
| Local CI (scripts/check.sh) | Done | ████████████████████ 100% |
| Feedback loop (docs/prompt/feedback/) | In progress | ████████░░░░░░░░░░░░ 40% |
| Auto-release (version bump + gh release) | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Auto-changelog update | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Auto-tracker update | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Auto-CLAUDE.md update | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Prompt self-refinement | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |

---

## Meta-Prompt System (61%)

The reusable prompt and surrounding docs that make the self-improving loop work.

| Component | Status | Progress |
|---|---|---|
| evolve.md prompt | Done | ████████████████████ 100% |
| Vision overview doc | Done | ████████████████████ 100% |
| Loop 1 deep dive doc | Done | ████████████████████ 100% |
| Loop 2 deep dive doc | Done | ████████████████████ 100% |
| Feedback ingestion | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Priority engine (what to build next) | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Session history / learning | In progress | █████░░░░░░░░░░░░░░░ 25% |

---

## How to Read This

**Progress bars**: `█` = done, `░` = not done. 20 chars = 100%.

**Percentages**: Calculated as (done components / total components) per section. Overall is weighted: Loop 1 (40%), Loop 2 (30%), Self-Maintaining (15%), Meta-Prompt (15%).

**"Done" means**: Code exists, tests pass, it works in a real run. Not "planned" or "partially implemented".

---

## Update Instructions (for the agent)

Every session, after you finish building:

1. Read this file
2. Check each component against the actual code (`nightshift/`, `tests/`, `docs/`)
3. Update status and progress bars for anything that changed
4. Recalculate section percentages
5. Recalculate overall percentage
6. Update the "Last updated" date at the top
7. Commit this file alongside your other changes

Do NOT inflate progress. If something is half-done, say "In progress" with an honest percentage. If you broke something, move it back to a lower percentage.
