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
- v0.0.2 is committed to main (commit 2802c51) but NOT tagged or released on GitHub yet. Next session should tag and release.
- Phractal test target: verify_command returns None for monorepos. Needs `.nightshift.json` with explicit verify_command, or monorepo detection in infer_verify_command().

## Current State
- Loop 1: 67% (14/21 components) — Core loop works e2e. Missing: diff scorer, state injection, test incentives, backend forcing, multi-repo, config deep merge, run_command timeout fix
- Loop 2: 0% (0/11) — Vision docs describe architecture. No code.
- Self-Maintaining: 54% (7/13) — Vision docs, changelog, tracker, prompt, CI, handoffs, ops guide done. Auto-update not built.
- Meta-Prompt: 57% (4/7) — Evolve prompt, all 3 vision docs done. Feedback ingestion, priority engine, session history not built.
- Overall: 43% (weighted)
- Version: v0.0.2 on main, not tagged. Ready to release.

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
1. **Tag and release v0.0.2** — Code is on main. Run `make release VERSION=0.0.2 CODENAME="Control Plane"`. Create v0.0.3.md skeleton.
2. **Fix `merge_config` shallow update** — Deep-merge list fields. Security bug. This starts v0.0.3.
3. **Fix `run_command` timeout race** — Thread-based readline with timeout. Reliability bug.
4. **Test against Phractal** — Create a `.nightshift.json` for it with explicit verify_command. Run a test shift. Document results.

## Where to Look
- `docs/ops/OPERATIONS.md` — If confused about any system, read this first
- `nightshift/config.py:merge_config()` — the shallow update bug
- `nightshift/shell.py:run_command()` — the timeout race
- `nightshift/cycle.py:verify_cycle()` — where diff scorer would be called
- `docs/vision/01-loop1-hardening.md` — full roadmap for Loop 1 improvements
