# Vision Tracker

Last updated: 2026-04-05 by agent session #0049 (persistent module map).

This file is the single source of truth for how close Nightshift is to its vision. Updated by the agent every session. The human never edits this — the agent reads the code, checks what exists, and recalculates.

---

## Overall Progress

```
NIGHTSHIFT VISION                              ██████████████████░░  92%
├── Loop 1 — Hardening Loop                    ████████████████████  99%
├── Loop 2 — Feature Builder Loop              ████████████████████ 100%
├── Self-Maintaining Repo                      ██████████████░░░░░░  68%
└── Meta-Prompt System                         ████████████████░░░░  78%
```

---

## Loop 1 — Hardening Loop (99%)

The core loop still works on the happy path, but five real Phractal evaluations now confirm the same false-rejection cluster around shift-log verification, verify-command wiring, and cleanup/reporting on real repos. The latest rerun still needed environment-specific startup help, so Loop 1 remains just below a truthful 100%.

| Component | Status | Progress |
|---|---|---|
| Python orchestrator | Done | ████████████████████ 100% |
| Codex adapter | Done | ████████████████████ 100% |
| Claude adapter | Done | ████████████████████ 100% |
| Worktree isolation | Done | ████████████████████ 100% |
| Runner-enforced guard rails | Done | ████████████████████ 100% |
| Machine-readable state | Done | ████████████████████ 100% |
| Baseline verification | Done | ████████████████████ 100% |
| Post-cycle verification | In progress | ██████████████████░░ 90% |
| Shift log generation | Done | ████████████████████ 100% |
| Category dominance check | Done | ████████████████████ 100% |
| Path bias detection | Done | ████████████████████ 100% |
| Hot-file protection | Done | ████████████████████ 100% |
| Halt conditions | Done | ████████████████████ 100% |
| Test suite (901 tests) | Done | ████████████████████ 100% |
| Post-cycle diff scorer | Done | ████████████████████ 100% |
| Cycle-to-cycle state injection | Done | ████████████████████ 100% |
| Test writing incentives | Done | ████████████████████ 100% |
| Backend exploration forcing | Done | ████████████████████ 100% |
| Category balancing directive | Done | ████████████████████ 100% |
| Multi-repo support | Done | ████████████████████ 100% |
| Deep merge for config | Done | ████████████████████ 100% |
| run_command timeout fix | Done | ████████████████████ 100% |

### Bugs Found (not yet fixed)
- `verify_cycle()` can reject valid shift-log commits when the filesystem folds `docs/` and `Docs/` to the same path (#0098).
- Real evaluations still need a target-specific verify command for Phractal, so baseline/cycle verification is weaker than intended (#0099).
- Rejected evaluation runs still leave the target clone dirty and hide useful findings in the human-readable artifacts, confirming tasks #0100, #0101, and #0102 remain active.

---

## Loop 2 — Feature Builder Loop (100%)

All Loop 2 components are complete: profiling, planning, decomposition, sub-agent spawning, coordination, wave integration, E2E testing, build orchestration, feature summary, production-readiness checking, and state tracking. Repo profiles now include dependency and convention analysis in addition to language/framework detection.

| Component | Status | Progress |
|---|---|---|
| Repo understanding / profiling | Done | ████████████████████ 100% |
| Feature planner | Done | ████████████████████ 100% |
| Task decomposer | Done | ████████████████████ 100% |
| Sub-agent spawner / manager | Done | ████████████████████ 100% |
| Sub-agent coordination | Done | ████████████████████ 100% |
| Integration / merge engine | Done | ████████████████████ 100% |
| E2E test runner | Done | ████████████████████ 100% |
| Feature CLI (`nightshift build`) | Done | ████████████████████ 100% |
| Feature state tracking | Done | ████████████████████ 100% |
| Production-readiness checker | Done | ████████████████████ 100% |
| Feature summary generation | Done | ████████████████████ 100% |

---

## Self-Maintaining Repo (68%)

The infrastructure that lets the agent manage everything without human intervention. Prompt self-refinement and cross-session cost intelligence are now active, but the release/changelog/tracker automation backlog is still the main bottleneck.

| Component | Status | Progress |
|---|---|---|
| Vision docs | Done | ████████████████████ 100% |
| Self-improving prompt (evolve.md) | Done | ████████████████████ 100% |
| Changelog system (per-version) | Done | ████████████████████ 100% |
| Vision tracker (this file) | Done | ████████████████████ 100% |
| CLAUDE.md (agent context) | Done | ████████████████████ 100% |
| CI pipeline (.github/workflows) | Done | ████████████████████ 100% |
| Local CI (scripts/check.sh) | Done | ████████████████████ 100% |
| Feedback loop (docs/prompt/feedback/) | In progress | ██████████████████░░ 90% |
| Auto-release (version bump + gh release) | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Auto-changelog update | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Auto-tracker update | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Auto-CLAUDE.md update | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Prompt self-refinement | Done | ████████████████████ 100% |

---

## Meta-Prompt System (78%)

The reusable prompt and surrounding docs that make the self-improving loop work.
Persistent module-map memory now reduces cold-start rediscovery when sessions touch
the Python package.

| Component | Status | Progress |
|---|---|---|
| evolve.md prompt | Done | ████████████████████ 100% |
| Vision overview doc | Done | ████████████████████ 100% |
| Loop 1 deep dive doc | Done | ████████████████████ 100% |
| Loop 2 deep dive doc | Done | ████████████████████ 100% |
| Feedback ingestion | Not started | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Priority engine (what to build next) | In progress | ████████████░░░░░░░░ 60% |
| Session history / learning | In progress | █████████████████░░░ 85% |

---

## How to Read This

**Progress bars**: `█` = done, `░` = not done. 20 chars = 100%.

**Percentages**: Calculated as the average of component percentages within each section (`Done` = 100, `Not started` = 0, `In progress` = listed percentage). Overall is the weighted average: Loop 1 (40%), Loop 2 (30%), Self-Maintaining (15%), Meta-Prompt (15%).

**"Done" means**: Code exists, tests pass, it works in a real run. Not "planned" or "partially implemented".

---

## Update Instructions (for the agent)

Every session, after you finish building:

1. Read this file
2. Check each component against the actual code (`nightshift/`, `tests/`, `docs/`)
3. Update status and progress bars for anything that changed
4. Recalculate section percentages from the component percentages
5. Recalculate overall percentage
6. Update the "Last updated" date at the top
7. Commit this file alongside your other changes

Do NOT inflate progress. If something is half-done, say "In progress" with an honest percentage. If you broke something, move it back to a lower percentage.
