# Handoff #0001
**Date**: 2026-04-03
**Version**: v0.0.2 (in progress)
**Session duration**: ~3h

## What I Built

### 1. Equal Agent Adapters
- Codex and Claude are now equal — no primary/secondary
- `resolve_agent()` priority chain: CLI → config → interactive picker → error
- Stripped all "Codex-first" language from README, nightshift/SKILL.md, CLAUDE.md
- Files: `nightshift/config.py`, `nightshift/constants.py`, `README.md`, `nightshift/SKILL.md`, `.nightshift.json.example`

### 2. Package Refactor
- Split `nightshift.py` (1,134 lines) into `nightshift/` package (10 modules)
- Modules: `types.py`, `constants.py`, `errors.py`, `shell.py`, `config.py`, `state.py`, `worktree.py`, `cycle.py`, `cli.py`, `__main__.py`
- Shell scripts now use `python3 -m nightshift`
- Tests: 123 written before refactor, all pass after
- Files: entire `nightshift/` package, `scripts/run.sh`, `scripts/test.sh`, `scripts/install.sh`, `tests/test_nightshift.py`

### 3. Vision + Self-Maintaining Infrastructure
- Created `docs/vision/` (3 docs: overview, loop1, loop2)
- Created `docs/prompt/evolve.md` (the self-improving prompt — full lifecycle)
- Created `docs/changelog/` (per-version files: v0.0.1, v0.0.2)
- Created `docs/vision-tracker/TRACKER.md` (progress bars for every component)
- Created `docs/handoffs/` (this system)
- Created `docs/prompt/feedback/` (human feedback loop)

### 4. First Autonomous Test Run
- Ran 2-cycle validation with Claude adapter against this repo
- Baseline failed (tests/ not on main yet) → log-only mode
- Agent found 2 real bugs: `merge_config` shallow update, `run_command` timeout race
- Branch pushed: `nightshift/2026-04-03`, PR #2 created

### 5. Template Fix
- Removed placeholder example entries from `SHIFT_LOG_TEMPLATE` in `constants.py`

## Decisions Made
- Agent adapters are equal — no "default" agent. User must choose.
- Package structure follows dependency graph: constants -> errors -> shell -> config/state -> worktree -> cycle -> cli
- Claude cycles don't get rejected for missing structured JSON (Claude doesn't support `--output-schema`)
- Handoff system replaces full-repo reads at session start
- Git workflow: always branch, always PR, always sub-agent review before merge. Never push to main directly.
- Release strategy: agent decides based on change type (patch for bugs, minor for features). See ops guide.
- No hardcoded paths. Use `python3` everywhere in committed files.
- Test target repo: https://github.com/fazxes/Phractal (cloned to /tmp/nightshift-test-target for local testing)
- Version milestones defined in ops guide: v0.0.2 (control plane), v0.0.3 (intelligence), v0.0.4 (agent quality), v0.0.5 (loop 2 scaffold)

## Known Issues
- `merge_config()` shallow update: `.nightshift.json` overrides replace default `blocked_paths` instead of extending. Security bug. Not fixed. Target: v0.0.3.
- `run_command()` timeout race: `readline()` blocks so timeout never fires on hung process. Not fixed. Target: v0.0.3.
- NOTHING is committed to main yet. All work from this session is unstaged. First action next session: commit everything, push, tag v0.0.2, release.

## Current State
- Loop 1: 60% — Core loop works e2e. Missing: diff scorer, state injection, test incentives, backend forcing, multi-repo, config deep merge
- Loop 2: 0% — Vision docs describe architecture. No code.
- Self-Maintaining: 20% — Vision docs, changelog, tracker, prompt exist. Auto-update not built.
- Version: v0.0.2 — Feature-complete for the control plane. Needs commit + push + release.

## Systems Created This Session
- `docs/handoffs/` — Short-term memory. Read LATEST.md first every session.
- `docs/vision/` — Long-term direction. 3 docs: overview, loop1, loop2.
- `docs/vision-tracker/TRACKER.md` — Progress scoreboard with bars.
- `docs/changelog/` — Per-version release notes (v0.0.1, v0.0.2).
- `docs/prompt/evolve.md` — The self-improving prompt (full lifecycle, 10 steps).
- `docs/prompt/feedback/` — Human feedback loop.
- `docs/ops/OPERATIONS.md` — Complete operations guide (the map of everything). Includes: git workflow, release strategy, version milestones, error recovery, test target, environment rules.
- `docs/ops/PRE-PUSH-CHECKLIST.md` — 14-part mandatory checklist before every push. Covers ALL documentation.
- `scripts/` — Moved run.sh, test.sh, install.sh, check.sh out of root.
- `nightshift/SKILL.md` — Moved from root into the package.
- `Makefile` — make test, make check, make dry-run, make clean.
- `.nightshift.json` — Fixed: no more hardcoded Python path. Uses `python3`.
- CLAUDE.md updated to mandate reading ops guide + handoff first every session. Git workflow and environment rules added.
- Test target: Phractal repo (https://github.com/fazxes/Phractal) cloned for e2e validation.

## Next Session Should
1. **Commit and push v0.0.2 to main** — Create a branch, PR, review, merge. All code, tests, docs, everything. Then tag v0.0.2 and `gh release create`.
2. **Fix `merge_config` shallow update** — Deep-merge list fields. Security bug. This starts v0.0.3.
3. **Fix `run_command` timeout race** — Thread-based readline with timeout. Reliability bug.
4. **Test against Phractal** — Clone to /tmp, run `nightshift test --agent claude --cycles 2`. Document results.

## Where to Look
- `docs/ops/OPERATIONS.md` — If confused about any system, read this first
- `nightshift/config.py:merge_config()` — the shallow update bug
- `nightshift/shell.py:run_command()` — the timeout race
- `nightshift/cycle.py:verify_cycle()` — where diff scorer would be called
- `docs/vision/01-loop1-hardening.md` — full roadmap for Loop 1 improvements
