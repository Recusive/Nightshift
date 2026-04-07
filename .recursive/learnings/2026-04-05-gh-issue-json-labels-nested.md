# gh issue list labels are nested objects

**Category**: Code Pattern
**Date**: 2026-04-05

## What happened
GitHub CLI `gh issue list --json labels` returns labels as an array of objects: `[{"name": "task", "description": "...", "color": "..."}]`, not an array of strings. You must access `label["name"]` in Python, not just check `if "task" in labels`.

## Key takeaway
When working with `gh` JSON output, always check the actual structure with a sample call first. The fields are objects, not primitives.

## How it saved time
Knowing this upfront avoided a debugging loop where label matching silently fails because you're comparing strings to dicts.
