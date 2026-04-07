# Plan Audit: Process Verification Pipeline + Skill Architecture

**Date**: 2026-04-07
**Plan Document**: `docs/plans/todo/unified-master-prompt.md`
**Branch**: `main`

## Plan Summary

The latest revision is now implementation-ready. It fixes the prior audit blockers by replacing the unstable mtime-based pentest signal with a frontmatter-based `completed:` window, keeping scorer-selected roles separate from agent overrides, migrating the session index to a 10-column contract explicitly, and making the checkpoint kill switch apply to the full pipeline.

The remaining issues are minor rollout and consistency items, not architectural blockers. The overall shape now matches the repo's existing daemon patterns and is concrete enough to implement safely.

## Files Reviewed

| File | Role | Risk |
|------|------|------|
| `docs/plans/todo/unified-master-prompt.md` | Updated refactor plan | High |
| `scripts/pick-role.py` | Current signal readers, frontmatter parser, role selector | High |
| `scripts/daemon.sh` | Current reset loop and session-index writer | High |
| `scripts/lib-agent.sh` | Shared daemon helper location referenced by the plan | High |
| `nightshift/costs.py` | Session-index consumer for strategist/healer cost analysis | High |
| `docs/prompt/evolve-auto.md` | Current daemon prefix prompt | High |
| `docs/prompt/evolve.md` | BUILD prompt source | Medium |
| `docs/prompt/review.md` | REVIEW prompt source | Medium |
| `docs/prompt/overseer.md` | OVERSEE prompt source | Medium |
| `docs/prompt/strategist.md` | STRATEGIZE prompt source | Medium |
| `docs/prompt/achieve.md` | ACHIEVE prompt source | Medium |
| `docs/prompt/pentest.md` | Pentest prompt contract | Medium |
| `docs/prompt/unified.md` | Earlier unified prompt being retired | Medium |
| `docs/handoffs/README.md` | Handoff template contract | Medium |
| `docs/ops/DAEMON.md` | Prompt-stack and daemon docs contract | Medium |
| `docs/ops/ROLE-SCORING.md` | Scoring reference contract | Medium |
| `tests/test_pick_role.py` | Scoring/index parser contract tests | Medium |
| `tests/test_nightshift.py` | Session-index and prompt contract fixtures | Medium |
| `docs/tasks/0177.md` | Live task frontmatter shape | Low |
| `docs/tasks/archive/0130.md` | Archived task frontmatter shape | Low |
| `docs/tasks/archive/0154.md` | Archived pentest-sourced task example | Low |
| `docs/learnings/2026-04-05-prompt-contracts-need-tests.md` | Prompt contract regression rule | Low |
| `docs/learnings/2026-04-04-preload-instructions-not-agent-read.md` | Prompt-data trust-boundary pattern | Low |
| `docs/learnings/2026-04-04-prompt-guard-in-shared-lib.md` | Shared daemon helper placement rule | Low |

_Risk: High (core logic, many dependents), Medium (feature code), Low (utilities, tests)_

## Verdict: APPROVE

The plan is now production-ready as a refactor plan. The prior correctness blocker is resolved, the trust-boundary design is coherent, and the migration surface is explicitly called out. The remaining items are polish-level improvements rather than must-fix blockers.

## Critical Issues (Must Fix Before Implementation)

None.

## Recommended Improvements (Should Consider)

| # | Section | Problem | Recommendation |
|---|---------|---------|----------------|
| 1 | 2.1 / 2.8 | The design section uses `count_recent_pentest_tasks()` while the execution checklist still names `count_pentest_sourced_tasks_completed()` in Phase 1. The underlying intent is now clear, but the plan should use one name consistently. | Rename the function consistently throughout the document so the implementation checklist matches the final design. |
| 2 | 2.2 / 2.8 | The ownership-framing prose is now behavior-based, but the execution checklist still says "Replace `sole engineer responsible` with CTO/owner framing." | Update the Phase 3 wording so it matches the final ownership text and does not accidentally reintroduce the earlier CTO/board framing. |
| 3 | 2.2 / 2.8 | The skills split preserves old prompt files and adds stripped copies under `docs/prompt/skills/`. This is the right migration choice, but it introduces ongoing duplication risk. | Add a synchronization test or explicit source-of-truth note for shared sections so originals and skills do not drift silently. |
| 4 | 2.7 | The edge-case section correctly calls out prompt-stack documentation drift, but the implementation checklist only explicitly names `CLAUDE.md` and `docs/ops/ROLE-SCORING.md`. | Add [docs/ops/DAEMON.md](/Users/no9labs/Developer/Recursive/Nightshift/docs/ops/DAEMON.md) explicitly to the Phase 5 docs update list so the three-file prompt stack is documented in the main daemon guide. |
| 5 | 2.5 | The plan says missing or incorrect `SIGNAL ANALYSIS` blocks cause a session to be "flagged", but the mechanism remains intentionally informal. | Either define a deterministic validator later or explicitly scope "flagged" to strategist/manual audit so operators do not expect automatic enforcement. |

## Nice-to-Haves (Optional Enhancements)

| # | Section | Idea | Benefit |
|---|---------|------|---------|
| 1 | 2.6 | Rename `docs/prompt/skills/` to `docs/prompt/roles/` or similar | Reduces confusion with Nightshift's actual skill bundle terminology. |
| 2 | 2.8 | Add a schema fixture for the `--with-signals` JSON payload | Makes future signal additions safer and easier to review. |

## Edge Cases Not Addressed

- What happens when daemon sessions are infrequent enough that the last 5 BUILD sessions span more than 3 calendar days? The plan intentionally uses a 3-day task window, but a note explaining why that window is acceptable would make the heuristic easier to maintain.
- What happens when pentest-generated tasks use source values that drift from the exact `source: pentest` string? The current design assumes the builder will write a stable value going forward; that should stay explicit in the prompt contract.
- What happens when the kill switch is used but the skill file markers are malformed or missing? The `sed`-based stripping path should have a direct regression test.
- What happens when docs still describe the prompt stack as `evolve-auto.md` plus one role prompt after `checkpoints.md` is introduced? The edge-case note catches this, but the Phase 5 docs pass needs to enforce it.

## Code Suggestions

Keep the task-window logic aligned with the repo's actual task metadata:

```python
def _frontmatter_has_source(frontmatter: str, source: str) -> bool:
    return bool(re.search(rf"^source:\\s*{re.escape(source)}\\b", frontmatter, re.MULTILINE))


def _frontmatter_completed_date(frontmatter: str) -> date | None:
    match = re.search(r"^completed:\\s*(\\d{4}-\\d{2}-\\d{2})\\b", frontmatter, re.MULTILINE)
    if not match:
        return None
    return date.fromisoformat(match.group(1))
```

Then scope the task-based signal to a real recent window:

```python
recent_cutoff = date.today() - timedelta(days=3)
task_security = sum(
    1
    for task_path in archive_dir.glob("[0-9]*.md")
    if (fm := _read_frontmatter(task_path))
    and _frontmatter_has_source(fm, "pentest")
    and (completed := _frontmatter_completed_date(fm))
    and completed >= recent_cutoff
)
```

## Verdict Details

### Correctness: PASS

The previous blocker is fixed. The plan now explicitly rejects mtime as a signal source, uses durable `completed:` frontmatter dates, and aligns the helper with the actual `_read_frontmatter(Path) -> str | None` contract in `scripts/pick-role.py`. The anti-loop design is now materially sound.

### Architecture: PASS

Keeping existing prompt files while moving only the unified daemon onto `docs/prompt/skills/` is the right migration shape for this repo. Separating `Role` from `Override`, using `lib-agent.sh` for shared extraction helpers, and making the kill switch compositional all match current Nightshift patterns.

Skipped as not applicable:
- `docs/architecture/MODULE_MAP.md` refresh requirements, because this plan does not modify `nightshift/*.py`.

### Performance: PASS

The `--with-signals` path avoids the earlier extra scorer subprocess. Token overhead remains small, and the plan does not introduce meaningful new hot-path work beyond the intended signal write/read.

### Production Readiness: PASS

The trust-boundary story is coherent: structured signals, no free-form injected feature strings, override data separated from scorer inputs, and shared helpers in `lib-agent.sh`. The session-index migration is now explicit across consumers, and the kill switch is designed to disable the full checkpoint pipeline rather than only part of it.

### Extensibility: PASS

Separating `Role` from `Override`, defining a structured signals payload, and keeping old prompt paths stable while adding new skill files all support future daemon roles and prompt iterations without destabilizing the existing system.

### Test Coverage: PASS WITH NOTES

The plan now explicitly covers the key contract migrations:

- `--with-signals` signal output
- 10-column session-index parsing
- scorer ignoring the new Override column
- the old archived-pentest-task regression
- kill-switch behavior

`make check` remains the correct final verification gate.
