# Document Update Checklist

Go through each item. Either update it or confirm it doesn't need updating. Do not skip any.

## Always

### Tasks
If you worked from a task file: mark it `status: done` with `completed` date. Create follow-up tasks for what comes next. Use `.next-id` for numbering (read, use, increment, commit). The queue should never be empty.

### Handoff
Write `.recursive/handoffs/NNNN.md` (increment from last). Follow the format in `.recursive/handoffs/README.md`. Required sections:
- "Tracker delta: XX% -> XX%"
- "Learnings applied: [quote + file]"
- "Generated tasks: [list #NNNN titles, or 'none']"
- "Tasks I did NOT pick and why:"

Copy to `.recursive/handoffs/LATEST.md`. If 7+ numbered files exist, compact into weekly.

### Changelog
Add changes under correct section (Added/Changed/Fixed/Removed/Internal). Tag each entry. Describe WHAT and WHY. Skip for docs-only changes.

### Vision Tracker
Update status, progress bars, section percentages, overall percentage (weighted: Loop1 40%, Loop2 30%, Self 15%, Meta 15%), and "Last updated" date. Skip for docs-only changes.

### Observe the System
1. Read `.recursive/sessions/index.md` — last 5 entries. Any patterns? Sessions slower? Same task repeating?
2. Run cost analysis and use it for cost claims
3. Read `.recursive/healer/log.md` — don't repeat previous observations
4. Check task queue — anything pending 5+ sessions? Blocked with weak reasons?
5. Check vision tracker — has it moved?

Think in **trends**, not point failures. Append observations to `.recursive/healer/log.md`.

### Generate Work
Scan across dimensions (meta/pipeline, code quality, repo health, architecture, agent DX, vision progress, security). Create tasks ONLY for genuine gaps — check for duplicates first. Span multiple dimensions. Use honest priorities.

### Learnings
Write at least one to `.recursive/learnings/YYYY-MM-DD-topic.md`. Update `.recursive/learnings/INDEX.md`. Be specific — "mypy is strict" is useless, "mypy rejects .get() on required TypedDict fields" is useful.

## Conditional

| Item | When | What |
|------|------|------|
| Vision Docs | Completed a roadmap item or made a design decision | Mark completed items, answer resolved questions |
| CLAUDE.md | Changed project structure, conventions, or added systems | Update structure tree, conventions |
| README.md | User-facing change | Update features, usage, requirements |
| Operations Guide | Added a system or changed a workflow | Update `Runtime/ops/OPERATIONS.md` |
| Config files | Added config options | Update example, schema, DEFAULT_CONFIG |
| Install Script | Added files that ship to users | Update PACKAGE_FILES, ROOT_FILES, SCRIPT_FILES |
| Module Map | Touched source modules | Refresh the project's module map if it has one |
| Version Assessment | Always | Check for untagged changelog versions |
