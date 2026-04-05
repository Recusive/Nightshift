# Handoff #0024
**Date**: 2026-04-04
**Version**: v0.0.7 in progress
**Session duration**: ~10m

## What I Built
- **Task #0036** (instruction file size cap): Added per-file and total size caps to `read_repo_instructions()`. Files exceeding 10 KB are truncated; total across all files capped at 30 KB. Truncation warnings injected into output so agent knows content was cut. Files that would push past total budget are skipped entirely with a warning.
- Files modified: `nightshift/constants.py`, `nightshift/cycle.py`, `tests/test_nightshift.py`
- Tests: +7 new (per-file truncation, total-cap truncation, total-cap skip, UTF-8 safety, multiple truncated, within-limit, total budget assertion), 607 total passing

## Decisions Made
- Per-file limit 10 KB, total limit 30 KB (3x per-file) -- enough for real instruction files, small enough to prevent context flooding
- Truncation at byte boundary with `errors="ignore"` to avoid broken UTF-8 from multi-byte char splits
- Warning text not counted against size budget (only significant content is tracked)
- Per-file truncation runs before total-cap check, so a 50 KB file is first cut to 10 KB then measured against the total

## Known Issues
- Task #0012 (Phractal re-validation) still pending
- v0.0.6 release not yet tagged
- Codex `.git/` sandbox issue untested
- Codex model pricing not yet added (task #0039)
- Task #0037 (symlink + new file detection in prompt guard) still pending

## Current State
- Loop 1: 100% (22/22)
- Loop 2: 63% (7/11) -- unchanged
- Self-Maintaining: 54% (7/13) -- unchanged
- Meta-Prompt: 57% (4/7) -- unchanged
- Overall: 76% (weighted) -- unchanged
- Version: v0.0.7 in progress
- Test count: 607

## Evaluate
Run evaluation against Phractal for the changes merged this session.

## Next Session Should
Tasks: #0037, #0039, #0012
1. **Task #0037** (normal) -- Prompt guard: detect new file creation and symlink attacks (security, pairs with #0036)
2. **Task #0039** (low) -- Codex model pricing in cost tracker
3. **Task #0012** -- Phractal re-validation (needs API access)

## Where to Look
- `nightshift/cycle.py` lines 71-119 -- `read_repo_instructions()` with truncation logic
- `nightshift/constants.py` -- `MAX_INSTRUCTION_FILE_BYTES`, `MAX_INSTRUCTION_TOTAL_BYTES`
- `tests/test_nightshift.py` class `TestReadRepoInstructionsTruncation` -- 6 truncation tests
