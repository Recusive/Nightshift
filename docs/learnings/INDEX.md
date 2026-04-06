# Learnings Index

Read this file FIRST. Only open individual learning files when they are relevant to your current task. Do NOT read every learning file every session — that wastes context.

## How to use this index

1. Scan the one-line summaries below
2. If a learning is relevant to what you're about to build, read that specific file
3. When you write a new learning, add it to this index in the correct category
4. When you find a learning is obsolete (bug was fixed, workaround no longer needed), move it to the Retired section

---

## Process

- [CONTRIBUTING.md: synthesize, not copy](2026-04-05-contributing-md-synthesis-not-copy.md) — Write external view only; reference CLAUDE.md for details, mirror review-agent gates as checklist
- [Daemon hot-reload for autonomy](2026-04-05-daemon-hot-reload.md) — Re-source lib-agent.sh every loop; exec self-restart when daemon.sh changes. Never require manual restart.
- [Review notes must become tasks](2026-04-04-review-notes-must-become-tasks.md) — Code review advisory notes must get follow-up tasks, never dismissed as "known limitation"
- [Always use make check](2026-04-04-always-make-check-never-partial-lint.md) — Never run ruff/mypy individually; `make check` covers nightshift/ AND tests/
- [Task selection is mesa-optimization](2026-04-04-task-selection-mesa-optimization.md) — Agent optimizes session success over project progress; queue order is authoritative, handoff is advisory
- [Merge strategy: --merge never --squash](2026-04-03-merge-never-squash.md) — Always --merge --admin, preserve all commits on main
- [Turn budget kills good sessions](2026-04-03-turn-budget-kills-sessions.md) — 500 max turns = silent death mid-work; keep context lean
- [New evolve steps go inside Step 6](2026-04-05-generate-work-placement.md) — Add as subsection (6n, 6o) to avoid renumbering and breaking cross-references
- [Learnings verification needs three touchpoints](2026-04-05-learnings-verification-scope.md) — Process enforcement requires production, persistence, AND verification points; missing any one makes it toothless
- [Vision alignment reveals drift](2026-04-05-vision-alignment-prevents-drift.md) — Last 5 tasks all targeted self-maintaining/meta-prompt, zero loop2; explicit section counting catches invisible clustering
- [Open PR recovery](2026-04-03-open-pr-recovery.md) — Daemon detects open PRs from crashed sessions and recovers them
- [Evaluation reruns should reuse existing tasks](2026-04-05-evaluation-reruns-reuse-existing-tasks.md) — Repeated low-scoring eval dimensions can duplicate queue entries; reference existing pending tasks instead of minting another copy
- [Default eval run before overrides](2026-04-05-evaluation-default-run-before-overrides.md) — Tool/env behavior drifts; score the prescribed evaluation command first and only use temporary overrides in a fresh rerun when the default run fails
- [Strategist prompt-health reviews need line numbers](2026-04-05-strategist-prompt-health-needs-line-numbers.md) — Prompt-quality audits need `nl -ba` prompt reads or the recommendations lose actionable file:line references
- [Cost analysis needs tolerant session parsing](2026-04-05-cost-analysis-needs-tolerant-session-parsing.md) — Analytics must handle legacy session-index rows and both Claude `result` logs and Codex final agent messages
- [Generated docs need session labels](2026-04-05-generated-docs-need-session-labels.md) — Pre-commit generated metadata should label dirty files with the current session, not `working tree`, or the committed doc is stale on merge
- [Stale doc tasks need a reality check](2026-04-05-stale-doc-tasks-need-reality-check.md) — When docs tasks lag architecture, update the task text first and document the replacement flow, not the removed behavior
- [Refresh module map before writing the current handoff](2026-04-05-module-map-before-handoff.md) — `module-map --write` uses the next numbered handoff as its session label, so run it before creating the current handoff file
- [Prompt contracts need tests](2026-04-05-prompt-contracts-need-tests.md) — If a control doc carries an exact command or flag, add a regression test for the doc text and a code-side test for the executing helper
- [README must match shipped entry points](2026-04-05-readme-must-match-shipped-entrypoints.md) — If there is no console script, document the real module/wrapper entry points and treat README commands as contracts

## Code Patterns

- [Escalation pattern for prompt directives](2026-04-03-escalation-pattern.md) — Standalone function returns directive string; build_prompt() assembles
- [Thread config through callers](2026-04-04-thread-config-through-callers.md) — Pass NightshiftConfig down the call chain, don't read inside builders
- [RepoProfile schema changes cascade into feature fixtures](2026-04-05-repoprofile-schema-cascade.md) — Expanding RepoProfile means updating feature.py rebuild logic and test fixture helpers, not just profiler.py
- [Pre-load instructions in runner not agent](2026-04-04-preload-instructions-not-agent-read.md) — Runner reads repo instruction files and injects into prompt
- [Prompt guard in shared lib](2026-04-04-prompt-guard-in-shared-lib.md) — Cross-cutting daemon concerns go in lib-agent.sh
- [notify_human must fail silently](2026-04-05-notify-human-silent-failure.md) — Daemon helper functions must use `|| true`; notification is best-effort, not blocking
- [Healer persistence needs workflow](2026-04-05-healer-persistence-needs-workflow.md) — Daemon sub-agent outputs need branch+PR+merge; git reset wipes uncommitted files
- [gh issue labels are nested objects](2026-04-05-gh-issue-json-labels-nested.md) — `gh issue list --json labels` returns `[{"name":...}]` not strings; access `.name`
- [Shell expansion mangles markdown](2026-04-05-shell-expansion-mangles-markdown.md) — Never use `$(cat file.md)` for prompts containing backticks/$; merge into agent step or use heredoc
- [Dry-run integration tests need isolated runtime artifacts](2026-04-05-dry-run-tests-need-isolated-runtime-artifacts.md) — Repo-root dry-run tests must not depend on `docs/Nightshift/` being empty
- [Reuse planner functions](2026-04-03-reuse-existing-functions.md) — Don't reimplement; import from existing modules
- [Agent scope separation mirrors module separation](2026-04-05-agent-scope-separation-mirrors-module-separation.md) — If a review agent needs "skip these checks when X" fast paths, it should be split into specialists
- [Pattern detection via path segments](2026-04-05-summary-module-pattern-detection.md) — Split paths into segment sets and intersect with keyword sets; more robust than regex for file categorization
- [Readiness checks as pure file scanners](2026-04-05-readiness-checks-pure-computation.md) — Pure Path.read_text() + regex beats shell-command wrappers; testable with tmp_path, no mocks needed
- [Pure scorer pattern for evaluation](2026-04-05-pure-scorer-pattern-for-evaluation.md) — Scorers take typed artifacts, return scores; I/O at edges only; 66 tests with zero mocks
- [E2E as gate before final verify](2026-04-05-e2e-gate-before-final-verify.md) — New pipeline steps sharing checks with later steps should gate; grep for integration tests to update
- [Code structure rules work](2026-04-03-code-structure-rules-work.md) — CLAUDE.md structure rules catch real violations at review time
- [Plan agent is simpler than cycle agent](2026-04-04-plan-agent-simpler-than-cycle.md) — Plan invocation needs fewer args than full cycle
- [Symlink check before is_file](2026-04-04-symlink-before-is-file.md) — Check is_symlink() first for security; symlinks pass is_file()
- [gitignored dirs survive git clean](2026-04-04-costs-json-survives-git-clean.md) — git clean -fd does NOT remove gitignored files

## Type System / Linting

- [mypy rejects .get() on required TypedDict](2026-04-03-mypy-typeddict-get.md) — Use direct key access on required fields, not .get()
- [TypedDict refactors must update aggregate containers too](2026-04-05-typeddict-refactor-updates-containers.md) — Changing a helper return type is not enough; retune every list/parameter storing that TypedDict in the same patch
- [ruff import sort is alphabetical](2026-04-03-ruff-import-sort-trap.md) — Module names sorted alphabetically; can break runtime if reordered
- [ruff format before push](2026-04-03-ruff-format-before-push.md) — Always run ruff format; CI catches formatting drift
- [ruff auto-fix import sorting](2026-04-04-ruff-autofix-import-sorting.md) — Let ruff --fix handle __init__.py import ordering
- [ruff BLE001 requires specific exceptions](2026-04-04-ble001-specific-exceptions.md) — Catch specific exception types, not bare Exception
- [Per-commit verification rejects valid work](2026-04-03-per-commit-vs-per-cycle-verification.md) — Per-cycle verification is more reliable than per-commit

- [Helper name collision in tests](2026-04-05-helper-name-collision-in-tests.md) -- Module-level helpers with same name silently shadow each other; grep before adding

## Agent / Tool Quirks

- [CI detached HEAD breaks tests](2026-04-03-ci-detached-head-breaks-tests.md) — PR checkouts use detached HEAD; git tests that assume a branch name fail
- [Codex skips shift log in commits](2026-04-03-codex-skips-shift-log-in-commits.md) — Codex adapter doesn't include shift log; verify explicitly
- [tee buffers claude output](2026-04-03-tee-buffers-claude-output.md) — Use --output-format stream-json for real-time logging; tee buffers plain output
- [extract_json has limits](2026-04-03-extract-json-embedded-limits.md) — raw_decode doesn't reliably find deeply nested JSON in arbitrary text
- [run_capture has no exit code](2026-04-03-run-capture-no-exit-code.md) — run_capture() returns stdout only; check exit code separately
- [Stale PR branches accumulate](2026-04-03-stale-pr-branches.md) — Always --delete-branch; orphan branches revert merged work
- [OpenAI cached tokens in total](2026-04-04-openai-cached-tokens-include-total.md) — OpenAI input_tokens includes cached; Claude separates them
- [Interactive shell testing with pipes](2026-04-04-interactive-shell-testing.md) — Test interactive functions by piping input
- [Per-file cap before total cap](2026-04-04-per-file-before-total-truncation.md) — Instruction file truncation: per-file limit fires before total
- [Case-insensitive shift-log paths](2026-04-05-case-insensitive-shift-log-paths.md) — `docs/` vs `Docs/` can falsely fail shift-log verification on macOS; compare canonical paths, not raw strings

## Data / Profiling

- [Profiler file count vs language](2026-04-03-profiler-file-count-vs-language.md) — Config files skew language detection; filter by code extensions

## Retired

<!-- Move learnings here when the underlying issue is permanently fixed -->
