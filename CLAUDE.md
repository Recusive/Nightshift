# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## MANDATORY: Read These First

Every session, before doing anything else:

1. **Read `docs/ops/OPERATIONS.md`** — The complete operations guide. Explains every system, folder, file, and how to use/update/maintain each one. This is your map.
2. **Read `docs/handoffs/LATEST.md`** — What happened last session, what's broken, what to build next. This is your short-term memory.
3. **If the human pastes the evolve prompt** — Follow `docs/prompt/evolve.md` step by step.

Do NOT start building, fixing, or proposing anything until you have read the operations guide and the latest handoff. These two files replace reading the entire repo.

## Keeping This File Current

When you add, remove, or significantly change files, architecture, scripts, or conventions in this repo, update this CLAUDE.md to reflect those changes before finishing your work. This file is the source of truth for future Claude Code sessions — if it's stale, they start wrong. Treat it like a living document, not a snapshot.

## What This Is

Nightshift is an autonomous overnight codebase improvement agent. The `nightshift/` package spawns headless agent cycles in an isolated git worktree, enforces guard rails, verifies each cycle, and tracks state. It supports Codex and Claude as equal pluggable adapters — you pick one and the same pipeline runs.

Built by Recursive Labs as part of the Orbit ecosystem.

## Project Structure

```
nightshift/              # Python package — the orchestrator
  __init__.py            # Re-exports all public names
  __main__.py            # Entry point for python3 -m nightshift
  types.py               # TypedDicts for all data structures (strict typing)
  constants.py           # DATA_VERSION, DEFAULT_CONFIG, SHIFT_LOG_TEMPLATE, etc.
  errors.py              # NightshiftError
  shell.py               # run_command, run_capture, git, command_exists, run_shell_string
  config.py              # merge_config, resolve_agent, infer_package_manager, infer_verify_command
  state.py               # read_state, write_json, load_json, append_cycle_state, top_path
  worktree.py            # ensure_worktree, ensure_shift_log, sync_shift_log, revert_cycle, cleanup
  cycle.py               # build_prompt, command_for_agent, verify_cycle, evaluate_baseline, extract_json
  cli.py                 # run_nightshift, summarize, verify_cycle_cli, build_parser, main
nightshift.schema.json   # JSON Schema for structured agent cycle output
pyproject.toml           # Project config: mypy strict, ruff lint/format, pytest
requirements-dev.txt     # Pinned dev tool versions (mypy, ruff, pytest)
scripts/check.sh         # Local CI — runs all checks (mirrors GitHub Actions)
nightshift/SKILL.md      # The skill prompt — discovery strategies, safety rails, shift log template
scripts/run.sh           # Thin wrapper: python3 -m nightshift run "$@"
scripts/test.sh          # Thin wrapper: python3 -m nightshift test "$@"
scripts/install.sh       # One-liner installer for both ~/.codex/ and ~/.claude/ skill dirs
.nightshift.json.example # Per-repo config template
.github/workflows/ci.yml # CI pipeline: lint → typecheck + test → integration + artifact validation
tests/                   # pytest suite — 123 tests covering all pure functions and CLI
docs/context/            # Architecture decisions and lessons from test runs
```

## Key Architecture Concepts

**Worktree isolation**: All work happens in `docs/Nightshift/worktree-YYYY-MM-DD/`. The user's main checkout, branch, and uncommitted changes are never touched.

**Multi-cycle design**: A single agent session drifts or hits context limits. The orchestrator spawns fresh headless sessions in a loop. The shift log (`docs/Nightshift/YYYY-MM-DD.md`) plus the state file (`docs/Nightshift/YYYY-MM-DD.state.json`) are the shared memory between cycles.

**Runner-enforced guard rails**: The orchestrator enforces max fixes/cycle, max files/fix, blocked paths, low-impact caps, category dominance limits, and clean-worktree requirements. Cycles that violate policy are reverted.

**Agent adapters**: `command_for_agent()` in `nightshift/cycle.py` constructs the CLI command for each agent. Codex uses `codex exec` with `--output-schema`. Claude uses `claude -p` with `--max-turns`. Both are headless, both go through the same verification.

## CI Pipeline

GitHub Actions runs on every push/PR to main. The pipeline has five stages:

1. **Lint** — `ruff check` + `ruff format --check` (fast gate, blocks everything else)
2. **Type check** — `mypy --strict` (runs after lint passes)
3. **Test** — `pytest` on Python 3.9 + 3.12 matrix (runs after lint passes)
4. **Integration** — dry-run both agents, verify CLI entry points (runs after typecheck + test pass)
5. **Validate artifacts** — schema/config JSON parsing, install.sh file references, shell syntax

Run the full pipeline locally with:

```bash
bash scripts/check.sh
```

## Testing Changes

The test suite lives in `tests/test_nightshift.py` (123 tests). Run with:

```bash
python3 -m pytest tests/ -v
```

For end-to-end validation against a real repo:

```bash
python3 -m nightshift test --agent codex --cycles 2
python3 -m nightshift test --agent claude --cycles 2
python3 -m nightshift run --dry-run --agent codex  # preview the prompt
```

Success criteria: all unit tests pass, shift log is populated with varied fixes, commits are clean, target project's tests still pass.

## Code Quality Rules

This codebase enforces strict typing and linting with zero suppressions in source code. These rules are non-negotiable — CI will reject violations.

### Strict typing (mypy)

- mypy runs in `strict` mode. Every function has full type annotations.
- All data structures are TypedDicts in `nightshift/types.py`.
- **Zero `cast()` calls.** Every TypedDict is constructed explicitly, field by field, so mypy verifies each assignment. No escape hatches.
- **Zero `# type: ignore` comments.** If mypy complains, fix the code — don't suppress it.
- The only `Any` usage is at JSON deserialization boundaries (`extract_json`, `load_json`). These return `dict[str, Any]` because `json.loads` inherently returns `Any`. The `Any` is immediately consumed by builder functions (`_build_config`, `_build_state`, `_as_cycle_result`) that validate and construct typed dicts — it never leaks into the rest of the codebase.

### Linting (ruff)

- Rule sets: `E`, `W`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`, `BLE`, `S`, `T20`, `PT`, `C4`.
- **Zero `# noqa` comments in source code.** The one `# noqa: I001` in tests is a structural necessity (`sys.path.insert` must precede the import).
- `S603`/`S607` (subprocess security) are suppressed only in the three files that legitimately spawn subprocesses (`shell.py`, `cycle.py`, `worktree.py`) via `per-file-ignores`. They are not suppressed globally.
- `T201` (print) is suppressed only in `constants.py` and `cli.py` where `print_status()` and CLI output are intentional.
- `E501` (line length) is ignored because `ruff format` enforces line length instead.

### ASCII-only source

- **No emojis, no Unicode, no non-ASCII characters** in any source file (.py, .sh, .toml). CI enforces this with a scanner that rejects any character outside the printable ASCII range (U+0000-U+007E).
- Use `--` instead of em dashes, `->` instead of arrows, `+--+` instead of box-drawing characters.
- Markdown docs (CLAUDE.md, README.md, SKILL.md) are exempt since they are human-facing documentation, not executed code.

### What this means for contributors

- Don't add `cast()`. Construct TypedDicts explicitly with builder functions that validate each field.
- Don't add `# type: ignore` or `# noqa`. If a check fails, fix the underlying issue.
- Don't add global ruff ignores. If a rule fires in a specific file, use `per-file-ignores` with a comment explaining why.
- Don't use emojis, Unicode arrows, box-drawing characters, or any non-ASCII in source files. ASCII only.
- Run `bash scripts/check.sh` before pushing. It mirrors CI exactly.
- Dev tool versions are pinned in `requirements-dev.txt` -- bump intentionally, not by accident.

## Git Workflow

- **Never push to main directly.** Always create a feature branch, PR, review with sub-agent, merge.
- Branch naming: `feat/`, `fix/`, `docs/`, `refactor/`, `release/`
- Use `--squash` merge for features, regular merge for releases.
- Full workflow documented in `docs/ops/OPERATIONS.md` under "Git Workflow".

## Environment

- Python 3.9+ (minimum supported). Use whatever `python3` resolves to.
- **Never hardcode absolute Python paths** in committed files. Use `python3` everywhere.
- Dev tools: `pip install -r requirements-dev.txt`
- Quick commands: `make test`, `make check`, `make dry-run`, `make clean`
- Test target repo for validation: `https://github.com/fazxes/Phractal`

## Editing Conventions

- nightshift/SKILL.md uses YAML frontmatter (`name`, `description`) for skill registration. The `description` field controls when the skill triggers — it must list trigger phrases.
- Shell scripts use `set -euo pipefail` and are thin wrappers that set `PYTHONPATH` and run `python3 -m nightshift`.
- The `nightshift/` package infers package manager and install command from lockfiles. It infers the verification command from `package.json`, `Cargo.toml`, `go.mod`, or `pyproject.toml`.
- Per-repo config lives in `.nightshift.json` (optional). See `.nightshift.json.example`.

## Known Behavioral Issues

These are documented in `docs/context/development-history.md` and mitigated by runner-enforced guard rails:

- Agent gravitates toward easy accessibility fixes — mitigated by low-impact cap and category dominance check
- Frontend tunnel vision — mitigated by path bias detection (rejects 3 consecutive cycles in same top-level dir)
- Later cycles sometimes rediscover issues — mitigated by state file tracking what was already done
- Test writing rarely happens in practice despite being priority #3
