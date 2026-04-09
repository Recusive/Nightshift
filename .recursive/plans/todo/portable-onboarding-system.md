# Plan: Portable `.recursive/` Onboarding System

## Context

The `.recursive/` framework is an autonomous brain-delegates-to-sub-agents system that currently only works on the Nightshift repo. 11 framework files contain hardcoded `nightshift/`, `Phractal`, or `task #0243` references that break on any other repo. The goal is to make `.recursive/` installable on ANY repo with an interactive onboarding wizard that generates project-specific docs from user answers.

**Existing foundation:** `init.sh` (300 lines) already scaffolds directories, symlinks agents, and creates starter files. `SKILL.md` defines a 7-step setup wizard. These are solid skeletons to extend, not replace.

---

## Inventory of Hardcoded References (Framework Files Only)

### Engine code (fix: read `.recursive.json` at runtime)

| File | Lines | Reference | Fix |
|------|-------|-----------|-----|
| `lib-agent.sh` | 57 | `notify-orbitweb.yml` in PROMPT_GUARD_FILES | Remove; add `project.guard_files` config array |
| `lib-agent.sh` | 131 | `nightshift/` in `check_zone_compliance()` | Read `project.code_dirs` from config |
| `signals.py` | 554,587,592,601 | `nightshift/` in `compute_eval_staleness()` | Accept `code_dirs` parameter |
| `dashboard.py` | 275 | `nightshift files changed` display text | Read project name from config |
| `dashboard.py` | 291 | `Phractal eval` + `task #0243` in alert text | Read eval command from config |

### Agent prompts (fix: generate from templates)

| File | Lines | Reference |
|------|-------|-----------|
| `brain.md` | 81,83,145,169,170 | `nightshift/` zone rules, Phractal eval, `task #0243` |
| `brain-codex.md` | 71,73,135,159,160 | Same as brain.md (mirror copy) |
| `evolve.md` | 17,21 | `nightshift/` in zone restriction |
| `audit-agent.md` | 26 | `nightshift/` in zone restriction |
| `code-reviewer.md` | 21 | `nightshift/scripts/install.sh PACKAGE_FILES` |

### Ops docs (fix: generate from templates)

| File | Refs | Notes |
|------|------|-------|
| `OPERATIONS.md` | 77 | Heavily Nightshift-specific, especially "System 6: The Product" section |
| `PRE-PUSH-CHECKLIST.md` | 10 | `make check`, version refs, Nightshift paths |
| `DAEMON.md` | 2 | Minor command examples |

---

## Architecture Decisions

**D1: Runtime config vs template generation.** Engine code (`.py`, `.sh`) reads project values from `.recursive.json` at runtime -- ship once, works everywhere. Prompt/doc files (`.md`) are generated from templates because they're injected into LLM context and must read naturally.

**D2: Config schema.** Add to `.recursive.json`:
```json
{
  "project": {
    "code_dirs": ["src/"],
    "guard_files": [".github/workflows/ci.yml"]
  },
  "commands": {
    "eval": ""
  }
}
```
- `code_dirs`: array of project source directories for zone compliance. Empty = relaxed zone checks.
- `guard_files`: project-specific files to add to prompt guard. Extends (not replaces) the framework guard list.
- `commands.eval`: optional eval command. Empty = no eval cadence rule in brain.md.

**D3: Template engine.** Shell `sed` substitution with `{{PLACEHOLDER}}` markers. For multi-line blocks (eval cadence), use a Python helper that reads template + config and produces output. No Jinja2.

**D4: Backward compatibility.** All engine changes default to current behavior when new config fields are absent. Nightshift's existing `.recursive.json` works without modification (auto-detect `nightshift/` as code_dir if it exists).

**D5: What gets copied vs generated.**
- **Copy as-is (generic framework):** daemon.sh, lib-agent.sh, signals.py, dashboard.py, pick-role.py, lib/*.py, scripts/*.sh, prompts/*.md, templates/*, tests/*
- **Generate from templates (project-specific):** brain.md, brain-codex.md, evolve.md, audit-agent.md, code-reviewer.md, CLAUDE.md, OPERATIONS.md, vision/00-overview.md
- **Not copied (runtime state):** handoffs/*, tasks/[0-9]*, sessions/*, learnings/*, evaluations/*, etc.

---

## Implementation Phases

### Phase 1: Config Schema Extension

**Files to modify:**

1. `.recursive/lib/config.py` -- Add `code_dirs`, `guard_files`, `commands.eval` to `DEFAULT_CONFIG`. Ensure `merge_config()` deep-merges nested dicts.

2. `.recursive/templates/project-config.json` -- Add new fields to template schema.

**Reuse:** `merge_config()` in `.recursive/lib/config.py` already handles config loading. Extend it.

### Phase 2: Engine Config-ification

**Files to modify:**

3. `.recursive/engine/signals.py` -- `compute_eval_staleness()` (line ~554): Add `code_dirs: list[str] | None = None` parameter. Replace hardcoded `"nightshift/"` with iteration over `code_dirs`. Return `(sessions_since, 0)` when `code_dirs` is empty.

4. `.recursive/engine/dashboard.py` -- `collect_signals()` and `format_dashboard()`: Accept optional config dict. Read `project.name` for display text. Read `project.code_dirs` and pass to `compute_eval_staleness()`. Replace "Phractal eval" in alert with config-driven text.

5. `.recursive/engine/lib-agent.sh`:
   - Line 57: Remove `notify-orbitweb.yml` from `PROMPT_GUARD_FILES`. Add `_load_project_guard_files()` function that reads `project.guard_files` from `.recursive.json` and appends to array.
   - Lines 130-132: `check_zone_compliance()` reads `project.code_dirs` from config (via python one-liner) instead of hardcoding `nightshift/`. Falls back to empty (no zone check) if config unavailable.

### Phase 3: Template Creation

Create `.recursive/templates/prompts/` directory with template versions:

6. `brain.md.tmpl` -- Copy current `brain.md`, replace:
   - `nightshift/` -> `{{PROJECT_CODE_DIRS_DISPLAY}}` (e.g., "`src/`, `lib/`")
   - Phractal eval block -> `{{EVAL_CADENCE_BLOCK}}` (conditionally included or omitted)
   - `task #0243` -> "the lowest-numbered pending eval task"
   - Zone rule "project code ONLY" -> references configured code dirs

7. `brain-codex.md.tmpl` -- Same substitutions as brain.md.

8. `evolve.md.tmpl` -- Replace `nightshift/` with `{{PROJECT_CODE_DIRS_DISPLAY}}`.

9. `audit-agent.md.tmpl` -- Replace `nightshift/` with `{{PROJECT_CODE_DIRS_DISPLAY}}`.

10. `code-reviewer.md.tmpl` -- Replace Nightshift-specific registration checklist with `{{CODE_REVIEW_CHECKLIST}}` (generic: "New module must be registered in all relevant import/export files").

11. `claude.md.tmpl` -- Template for CLAUDE.md. Sections:
    - Session start rules (GENERIC -- copy as-is)
    - "What This Is" (TEMPLATE -- `{{PROJECT_DESCRIPTION}}`)
    - Quick Reference (TEMPLATE -- `{{COMMANDS}}`)
    - Recursive framework section (GENERIC -- copy as-is)
    - Code quality rules (TEMPLATE -- detected from linter configs)
    - Package structure (TEMPLATE -- `{{PACKAGE_STRUCTURE}}` from file tree scan)

12. `operations.md.tmpl` -- Template for OPERATIONS.md. The "System 6: The Product" section becomes `{{PROJECT_SYSTEM_SECTION}}` (generated from codebase scan). All other systems are 70%+ generic.

### Phase 4: Onboarding Script

13. `.recursive/scripts/onboard.sh` (~250 lines) -- Interactive wizard:

```
Auto-detection functions:
  detect_project_name()   -- package.json/pyproject.toml/Cargo.toml/go.mod/dirname
  detect_language()       -- count file extensions
  detect_test_command()   -- package.json scripts.test / Makefile test / cargo test / pytest
  detect_check_command()  -- package.json scripts.lint / Makefile check / pre-commit
  detect_code_dirs()      -- find top-level dirs with source code

Interactive flow:
  1. Show auto-detected values, ask for confirmation/override
  2. Ask for: description, agent backend, eval command (optional)
  3. Vision + roadmap creation:
     a. "Describe your project goals (or paste a plan):"
     b. "Break it into phases? (y/n)" -- if yes, ask for each phase
     c. Generate vision/00-overview.md from the high-level goals
     d. Generate vision/01-phase-1.md, vision/02-phase-2.md, etc. from phases
     e. Auto-decompose phase 1 into 5-10 concrete tasks in .recursive/tasks/
     f. Generate vision-tracker/TRACKER.md linking phases to tasks
     The brain reads vision/ before every session -- this is its roadmap.
     Tasks from phase 1 are what it builds first. When phase 1 tasks are
     done, the brain (or user) decomposes phase 2 into new tasks.
  4. Run init.sh for directory scaffolding
  5. Generate .recursive.json with all answers
  6. Generate agent prompts from templates (brain.md, evolve.md, etc.)
  7. Generate CLAUDE.md from template (scan file tree for structure)
  8. Generate OPERATIONS.md from template
  9. Backend-specific setup:
     a. If claude: .claude/agents/ symlinks (already in init.sh)
     b. If codex: generate .codex/agents/*.toml from .recursive/agents/*.md
        + create .codex/config.toml with project model/reasoning settings
     c. If both: do both
  10. Verify: valid JSON, all dirs exist, pick-role.py runs, no unresolved {{placeholders}}

Template generation helper (Python):
  generate_from_template(template_path, output_path, substitutions_dict)
  -- handles both single-line sed and multi-line block substitution
```

### Phase 5: Skill + Init Updates

14. `.recursive/skills/setup/SKILL.md` -- Update to reference `onboard.sh`. Add new questions (code_dirs, eval command). Update verification step.

15. `.recursive/scripts/init.sh` -- Minor: add `code_dirs` and `guard_files` to the generated `.recursive.json` skeleton. Keep backward compatible.

### Phase 6: Update Existing Nightshift Config

16. `.recursive.json` (Nightshift) -- Add `code_dirs: ["nightshift/"]` and `guard_files: [".github/workflows/ci.yml", ".github/workflows/notify-orbitweb.yml"]` so Nightshift itself works with the new config-driven engine.

17. Re-generate `brain.md`, `evolve.md`, `audit-agent.md`, `code-reviewer.md` from templates for Nightshift (should produce identical or near-identical output).

---

## Implementation Order & Dependencies

```
Phase 1 (config schema) ─────────────────> Phase 2 (engine config-ification)
                                                       │
Phase 3 (template creation) ──────────────────────────>│
                                                       v
                                              Phase 4 (onboard.sh)
                                                       │
                                                       v
                                              Phase 5 (skill + init updates)
                                                       │
                                                       v
                                              Phase 6 (update Nightshift config)
```

- Phases 1 and 3 can run in parallel (no dependencies)
- Phase 2 depends on Phase 1 (engine reads new config fields)
- Phase 4 depends on Phases 1-3 (uses config schema + templates)
- Phase 6 is last (proves backward compatibility)

---

## Verification

After each phase:
- `make check` passes (Nightshift CI stays green)
- `python3 .recursive/engine/dashboard.py .recursive/` renders without errors

After Phase 4 (full integration test):
```bash
# Test on a fresh temp repo
mkdir /tmp/test-onboard && cd /tmp/test-onboard && git init
cp -r /path/to/.recursive/ .recursive/
bash .recursive/scripts/onboard.sh  # Answer wizard questions
# Verify:
python3 .recursive/engine/pick-role.py .          # Scoring engine works
python3 .recursive/engine/dashboard.py .recursive/ # Dashboard renders
grep -r "nightshift" .recursive/agents/            # Zero matches
grep -r "{{" .recursive/agents/                    # Zero unresolved placeholders
bash .recursive/engine/daemon.sh claude 1 1        # Brain runs 1 session
```

After Phase 6 (backward compatibility):
```bash
# In the Nightshift repo
make check                                          # CI green
python3 .recursive/engine/dashboard.py .recursive/  # Dashboard still works
bash .recursive/engine/daemon.sh claude 1 1         # Brain still works
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Breaking Nightshift daemon | HIGH | Every engine change defaults to current behavior when config fields absent. Phase 6 adds config explicitly. `make check` after every phase. |
| `sed` fails on multi-line blocks | MEDIUM | Use Python helper for multi-line template substitution (eval cadence block). |
| Template drift (brain.md edited directly) | LOW | Add `<!-- Generated from brain.md.tmpl -->` header. Template is source of truth. |
| Projects with code at root (no code_dir) | LOW | `code_dirs: []` relaxes zone checks. Acceptable -- zone compliance is a safety rail, not a hard gate. |
| OPERATIONS.md has 77 Nightshift refs | MEDIUM | The "System 6: The Product" section is entirely project-specific. Template replaces it with `{{PROJECT_SYSTEM_SECTION}}` generated from file tree scan. Other sections are 70%+ generic with light placeholder substitution. |

---

## Critical Files

- `.recursive/lib/config.py` -- config loading (extend)
- `.recursive/engine/signals.py:554-607` -- `compute_eval_staleness()` (parameterize)
- `.recursive/engine/dashboard.py:264-291` -- display text (config-drive)
- `.recursive/engine/lib-agent.sh:57,130-132` -- prompt guard + zone compliance (config-drive)
- `.recursive/agents/brain.md` -- most Nightshift-hardcoded agent prompt (templatize)
- `.recursive/scripts/init.sh` -- existing scaffolding (extend)
- `.recursive/scripts/onboard.sh` -- new wizard (create)
