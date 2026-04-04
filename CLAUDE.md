# CLAUDE.md

## MANDATORY: Session Start

1. **Read `docs/handoffs/LATEST.md`** — What happened last session, what's broken, what to build next. This is your memory.
2. **Read `docs/ops/OPERATIONS.md`** on your first session, or when the handoff tells you to. This is the complete map of every system, folder, and file.
3. **If the human pastes the evolve prompt** — Follow `docs/prompt/evolve.md` step by step.

Do NOT start building until you have read the handoff.

4. **Read `docs/learnings/`** — Hard-won knowledge from previous sessions. Gotchas, patterns, failures. Read all files. These prevent you from repeating mistakes.

## What This Is

Nightshift is an autonomous engineering system. The `nightshift/` package spawns headless agent cycles (Codex or Claude) in an isolated git worktree, enforces guard rails, verifies each cycle, and tracks state. You pick an agent and the same pipeline runs.

Full vision: `docs/vision/00-overview.md`

## Quick Reference

```bash
make test        # run tests
make check       # full CI locally
make dry-run     # preview cycle prompt
make clean       # remove runtime artifacts
```

## Git Workflow

- **Never push to main directly.** Branch, PR, sub-agent review, merge.
- Branch naming: `feat/`, `fix/`, `docs/`, `refactor/`, `release/`
- Full workflow: `docs/ops/OPERATIONS.md` under "Git Workflow"

## Environment

- Python 3.9+. Use `python3`. **Never hardcode absolute paths.**
- Dev tools: `pip install -r requirements-dev.txt`
- Test target: `https://github.com/fazxes/Phractal`

## Code Quality Rules

These are enforced by CI. Non-negotiable.

**Typing (mypy strict):**
- Full type annotations on every function
- All data structures are TypedDicts in `nightshift/types.py`
- Zero `cast()` calls. Zero `# type: ignore` comments.
- `Any` only at JSON deserialization boundaries

**Linting (ruff):**
- Rule sets: `E`, `W`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`, `BLE`, `S`, `T20`, `PT`, `C4`
- Zero `# noqa` in source (one exception in tests for `sys.path.insert`)
- `S603`/`S607` suppressed only in `shell.py`, `cycle.py`, `worktree.py` via per-file-ignores
- `T201` suppressed only in `constants.py` and `cli.py`

**ASCII-only source:**
- No emojis, Unicode, or non-ASCII in `.py`, `.sh`, `.toml` files
- Markdown docs are exempt

**Code Structure (non-negotiable):**
- **One concern per module.** If you're adding >50 lines of new logic to an existing file, it belongs in its own module. cycle.py handles cycle logic — not scoring. cli.py handles CLI — not business logic.
- **No hardcoded data in logic files.** Regex patterns, score maps, category weights, thresholds — these go in `constants.py` or a dedicated `*_patterns.py`. Logic files import them.
- **New module checklist:** create the `.py` file, add to `__init__.py` re-exports, add to `scripts/install.sh` PACKAGE_FILES, add to this file's structure tree.
- **Follow the dependency flow:** `types -> constants -> errors -> shell -> config/state -> worktree -> cycle -> cli`. New modules slot into this chain. No circular imports.
- **Functions over inline code.** If a block of code does one thing and is >10 lines, extract it into a named function. The function name documents the intent.
- **Config over magic numbers.** If a value might change (thresholds, limits, timeouts), put it in `DEFAULT_CONFIG` and `types.py`, not inline.

**Contributors:**
- Run `make check` before pushing
- Don't suppress warnings — fix them
- Dev tool versions pinned in `requirements-dev.txt`

## Editing Conventions

- `nightshift/SKILL.md` uses YAML frontmatter for skill registration
- Shell scripts are thin wrappers in `scripts/`
- Per-repo config: `.nightshift.json` (see `.nightshift.json.example`)
- Before pushing: read `docs/ops/PRE-PUSH-CHECKLIST.md`

## Keeping This File Current

When you change project structure or conventions, update this file. But keep it short — details belong in `docs/ops/OPERATIONS.md`.
