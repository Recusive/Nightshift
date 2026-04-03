You are reviewing a PR in the Nightshift repo. You know this codebase intimately.

## What to check

### Structure
- Does every new `.py` file follow the dependency flow? `types -> constants -> errors -> shell -> config/state -> worktree -> cycle -> scorer -> cli`
- Is new logic in the RIGHT module? Scoring logic in `scorer.py`, not `cycle.py`. CLI integration in `cli.py`, not in business logic modules. Constants in `constants.py`, not inline.
- Is any module getting too big (>200 lines of logic)? Should it be split?
- Are hardcoded values (regex patterns, score maps, thresholds) in constants or config, not inline in logic?

### Registration
- New `.py` module? Must be in: `__init__.py` re-exports, `scripts/install.sh` PACKAGE_FILES, CLAUDE.md structure tree, OPERATIONS.md module table.
- New config key? Must be in: `DEFAULT_CONFIG` in `constants.py`, `NightshiftConfig` in `types.py`, `.nightshift.json.example`.
- New public function? Must be re-exported from `__init__.py`.

### Types
- All function parameters and returns have type annotations?
- New data structures use TypedDicts in `types.py`, not raw dicts?
- No `cast()`, no `# type: ignore`, no `Any` outside JSON boundaries?

### Tests
- Every changed function has corresponding test changes?
- Tests use real assertions, not just "doesn't crash"?
- Edge cases covered (empty input, None, boundary values)?

### Safety
- No hardcoded absolute paths?
- No secrets, tokens, or credentials?
- No `subprocess` calls outside `shell.py` and `worktree.py`?
- No force push, no destructive git operations?

### Docs
- If the PR changes behavior, is the changelog updated?
- If the PR adds files, is CLAUDE.md structure tree updated?
- Does the handoff exist and is LATEST.md a copy of it?

## How to review

1. Read the PR diff: `gh pr diff <number>`
2. Check each item above
3. Report: **PASS** (merge it) or **FAIL** (list what needs fixing with specific file:line references)
