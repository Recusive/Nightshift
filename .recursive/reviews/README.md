# Code Reviews

The review daemon logs what it reviewed and what it fixed. One file per review session.

## Files
- `YYYY-MM-DD-module.md` — review log for a specific module

## Purpose
- Track which files have been reviewed (so the daemon doesn't re-review the same file)
- Document what was found and fixed
- Log anything skipped and why
