# Pre-Push Checklist

You are about to push. Stop. Run through EVERY item below. If ANY item fails, fix it before pushing. No exceptions. No "I'll do it next session." Now or never.

This checklist exists because you will forget. You just spent hours building. Your context is full of code. That's exactly when you skip a doc update, forget the handoff, or leave the tracker stale. This checklist is the last line of defense.

---

## Part 1: What Did You Change?

Before going through the checklist, categorize your work. Check all that apply:

- [ ] New feature (new module, new function, new capability)
- [ ] Bug fix (changed existing behavior)
- [ ] Refactor (restructured without changing behavior)
- [ ] Docs only (no code changes)
- [ ] New config option (added to DEFAULT_CONFIG or schema)
- [ ] New file or module (created a new .py, .sh, .md, or .json)
- [ ] Renamed or moved a file
- [ ] Changed project structure (folders, entry points)

Your answers determine which sections below are mandatory.

---

## Part 1b: Branch Safety (ALWAYS — check this FIRST)

- [ ] NOT on main: `git branch --show-current` must NOT be `main`
- [ ] Branch has correct prefix: `feat/`, `fix/`, `docs/`, `refactor/`, `release/`
- [ ] If you are on main: STOP. Create a branch before doing anything else.

---

## Part 2: Code Quality (ALWAYS)

- [ ] Full CI passes locally: `make check` (includes mypy strict + ruff + pytest + integration)
- [ ] Doc validator passes: `bash .recursive/scripts/validate-docs.sh` (catches stale test counts, missing registrations, percentage drift)
- [ ] If `make check` is unavailable: `make test` + dry-run both agents + `bash -n` scripts
- [ ] Test coverage for changes: every changed `.py` file in `nightshift/` has corresponding test changes in `nightshift/tests/`
- [ ] No junk staged: `git status` shows no `.pyc`, `__pycache__`, `.state.json`, `.runner.log`, `worktree-*/`
- [ ] Commit message follows convention: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `release:`
- [ ] No hardcoded absolute paths in any committed file

---

## Part 2b: Task Status (IF working from a task)

- [ ] Task file set to `status: done` with `completed: YYYY-MM-DD`
- [ ] If task was too big and you only did part of it: mark done, create follow-up task(s)
- [ ] Handoff references the next pending task numbers

## Part 2c: Code Review Notes (AFTER sub-agent review)

- [ ] If the review flagged advisory notes, known limitations, or follow-up suggestions: each one has EITHER been fixed before merging OR has a new task in `.recursive/tasks/` with acceptance criteria
- [ ] "Known limitation" or "not blocking" is NOT a valid reason to skip creating a task — the task queue tracks deferred work
- [ ] Handoff "Known Issues" or "Next Session Should" references any new follow-up tasks created from review notes

---

## Part 3: Handoff (ALWAYS)

- [ ] New handoff written: `.recursive/handoffs/NNNN.md` (next sequential number)
- [ ] Format matches the template in `.recursive/handoffs/README.md` exactly
- [ ] "What I Built" section filled with specific files and changes
- [ ] "Known Issues" carried forward from previous handoff (if not fixed this session)
- [ ] Resolved issues from previous handoff DROPPED (don't carry fixed bugs)
- [ ] "Next Session Should" filled with actionable recommendation
- [ ] "Where to Look" lists specific files relevant to the next task
- [ ] `.recursive/handoffs/LATEST.md` is an exact copy of the new handoff
- [ ] "Learnings applied" section present in handoff — quotes a specific learning file and explains how it affected this session's approach
- [ ] If 7+ numbered handoff files exist: compacted into `.recursive/handoffs/weekly/week-YYYY-WNN.md`

---

## Part 4: Changelog (ALWAYS except docs-only)

- [ ] Entry added to current version file in `.recursive/changelog/vX.X.X.md`
- [ ] Entry is under the correct section: `Added`, `Changed`, `Fixed`, `Removed`, `Internal`
- [ ] Entry tagged correctly: `[feat]`, `[fix]`, `[refactor]`, `[test]`, `[docs]`, `[meta]`, `[remove]`
- [ ] Entry describes WHAT changed and WHY (not just "updated file.py")

---

## Part 5: Vision Tracker (ALWAYS except docs-only)

- [ ] Read `.recursive/vision-tracker/TRACKER.md`
- [ ] Every component you affected: status updated (`Not started` / `In progress` / `Done`)
- [ ] Every component you affected: progress bar updated (`█` for done, `░` for not done)
- [ ] Section percentages recalculated: `(done / total) * 100`
- [ ] Overall percentage recalculated: weighted (Loop1 40%, Loop2 30%, Self 15%, Meta 15%)
- [ ] "Last updated" date at the top changed to today
- [ ] If you completed a roadmap item in vision docs: marked as done there too

---

## Part 6: CLAUDE.md (IF structure changed)

Required when: you added/removed/renamed files, modules, folders, or entry points.

- [ ] Project structure tree updated
- [ ] Any new conventions documented
- [ ] Any new systems added to the listing

---

## Part 7: Operations Guide (IF new system or changed workflow)

Required when: you created a new folder, new doc system, new script, or changed how an existing system works.

- [ ] `.recursive/ops/OPERATIONS.md` updated with new/changed system
- [ ] Quick-reference table at the bottom updated

---

## Part 8: README.md (IF user-facing change)

Required when: you added a feature users would care about, changed install process, changed CLI interface, or changed requirements.

- [ ] Feature described in README
- [ ] Usage examples updated if CLI changed
- [ ] Requirements section updated if dependencies changed
- [ ] Roadmap updated (check items done, add new items)

---

## Part 9: Vision Docs (IF roadmap item completed or design decision made)

Required when: you completed something listed in the vision docs, or made an architectural decision.

- [ ] `.recursive/vision/00-overview.md` — success criteria or architecture updated if relevant
- [ ] `.recursive/vision/01-loop1-hardening.md` — roadmap item marked done if completed
- [ ] `.recursive/vision/02-loop2-feature-builder.md` — open question answered if resolved

---

## Part 10: Config + Schema (IF new config option)

Required when: you added a new field to `DEFAULT_CONFIG`, changed the schema, or added a new config key.

- [ ] `.nightshift.json.example` updated with new key
- [ ] `nightshift.schema.json` updated if structured output changed
- [ ] `nightshift/constants.py` DEFAULT_CONFIG updated

---

## Part 11: Install Script (IF new file ships)

Required when: you added a new Python module, a new script, or any file that users need when they install Nightshift.

- [ ] New module added to `PACKAGE_FILES` in `nightshift/scripts/install.sh`
- [ ] New root file added to `ROOT_FILES` in `nightshift/scripts/install.sh`
- [ ] New script added to `SCRIPT_FILES` in `nightshift/scripts/install.sh`
- [ ] New public functions re-exported from `nightshift/__init__.py`

---

## Part 12: Evolve Prompt (IF you learned something)

Required when: you discovered a gotcha, a pattern, or something that would help future sessions work better.

- [ ] `.recursive/operators/build/SKILL.md` updated with the new knowledge
- [ ] OR added to vision docs if it's architectural
- [ ] OR added to OPERATIONS.md if it's procedural

---

## Part 13: Release Check (AFTER EVERY MERGE)

After merging your PR, evaluate:

- [ ] What type of change was this? Bug fix → patch. Feature → minor.
- [ ] Check `.recursive/ops/OPERATIONS.md` version milestones — is the current version complete?
- [ ] If ALL milestone items are done:
  - [ ] Update current version changelog status to "Released"
  - [ ] Create new version changelog file with "In progress" status
  - [ ] Update `.recursive/changelog/README.md` table
  - [ ] Create git tag: `git tag vX.X.X`
  - [ ] Push tag: `git push origin vX.X.X`
  - [ ] Create GitHub release: `gh release create vX.X.X --title "vX.X.X -- Codename" --notes-file .recursive/changelog/vX.X.X.md`
- [ ] If NOT a release: note in handoff what's still needed for the current version

---

## Part 14: Proof of Work

You must paste output as evidence. Checking a box without running the command is a failure.

- [ ] Paste the last line of `make check` output (should show "passed" or equivalent)
- [ ] If `make check` is unavailable: paste `make test` output showing test count
- [ ] If neither is available (e.g., missing dev deps): paste `python3 -m pytest nightshift/tests/ -q` output

## Part 15: Cross-Document Consistency

- [ ] Handoff "Current State" percentages match `.recursive/vision-tracker/TRACKER.md` exactly
- [ ] Handoff version matches changelog current version
- [ ] Handoff "Known Issues" is a subset of (or equal to) the previous handoff's issues minus what you fixed

## Part 16: Final Sanity Check

- [ ] `git diff --staged --stat` — does the list of changed files make sense? Nothing extra? Nothing missing?
- [ ] Read your own handoff one more time — would a brand new agent understand exactly where things stand?
- [ ] The branch name matches the work: `feat/`, `fix/`, `docs/`, `refactor/`, `release/`

---

## How to Run This

At the end of your session, before `git push`:

1. Answer Part 1 + 1b (change type + branch safety)
2. Go through Parts 2-5 (mandatory for all sessions)
3. Go through Parts 6-12 (only the ones that apply based on Part 1)
4. Part 13 (after merging — release check)
5. Part 14 (proof of work — paste command output)
6. Part 15 (cross-document consistency)
7. Part 16 (final sanity)

Output your results in the session so there's a visible record:

```
PRE-PUSH CHECKLIST — [date]
════════════════════════════

Change type: [feat / fix / refactor / docs]

Part 1b — Branch:              [branch name] (not main)
Part 2 — Code Quality:         ALL PASS
Part 3 — Handoff:              Handoff #NNNN written, LATEST updated
Part 4 — Changelog:            Entry added to vX.X.X.md
Part 5 — Tracker:              Updated (XX% -> XX%)
Part 6 — CLAUDE.md:            [Updated / No changes needed]
Part 7 — Ops Guide:            [Updated / No changes needed]
Part 8 — README:               [Updated / No changes needed]
Part 9 — Vision Docs:          [Updated / No changes needed]
Part 10 — Config/Schema:       [Updated / No changes needed]
Part 11 — Install Script:      [Updated / No changes needed]
Part 12 — Evolve Prompt:       [Updated / No changes needed]
Part 13 — Release:             [vX.X.X released / Not a milestone]
Part 14 — Proof:               make check output: [paste last line]
Part 15 — Consistency:         Handoff matches tracker: YES
Part 16 — Sanity:              PASS

READY TO PUSH.
```

If you can't output "READY TO PUSH" — you're not done. Fix what failed.
