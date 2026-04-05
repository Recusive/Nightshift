# Learning: Case-insensitive filesystems break naive shift-log path checks
**Date**: 2026-04-05
**Session**: 0043
**Type**: gotcha

## What happened
The first real Phractal evaluation on macOS produced valid shift-log commits under `Docs/Nightshift/2026-04-05.md`, but `verify_cycle()` still rejected both cycles because it was checking for the literal configured path `docs/Nightshift/2026-04-05.md`.

## The lesson
When verification cares about "did this file get updated", do not rely on raw path-string equality alone. Canonicalize or compare resolved paths so `docs/` vs `Docs/` does not create false rejections on case-insensitive filesystems.

## Evidence
- `/tmp/nightshift-eval-20260405c/docs/Nightshift/2026-04-05.state.json` recorded `No commit in this cycle includes the shift log update.`
- Commits `1ea27a9` and `7ac6bd9` both updated `Docs/Nightshift/2026-04-05.md`
- `docs/evaluations/0001.md` documents the failed real-world run
