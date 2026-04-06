---
date: 2026-04-06
topic: Origin guard new-file blind spot
type: security
---

# Origin guard new-file blind spot

`check_origin_integrity` checked only the fixed `PROMPT_GUARD_FILES` list for
changes on `origin/main`.  It never scanned `PROMPT_GUARD_DIRS` for new files,
so an agent could push `scripts/evil.sh` directly to `origin/main` and the
origin guard would exit 0.

The working-tree guard (`check_prompt_integrity`) already had new-file detection
via snapshot directory listings.  The origin guard needed the same treatment:
compare each `PROMPT_GUARD_DIRS` snapshot filelist against the current
`git ls-tree` output for `origin/main:<dir>/`.

New files found only in non-merge commits are flagged (matching the existing
per-file filter).  New files that ARE in merge commits (PR workflow) are allowed
-- the same policy as existing file changes.  New files cannot be auto-reverted
safely (they require knowing whether legitimate commits exist between snap and
current), so detection sets `revert_failed=1` → daemon exits 2 → human
intervenes.

**Why it matters**: PROMPT_GUARD_DIRS includes `docs/evaluations/` and
`docs/autonomy/` (added this session).  Without new-file detection, faking a
100/100 eval report via direct push would bypass the eval gate silently.
