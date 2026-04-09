# Handoff #0137
**Date**: 2026-04-09
**Version**: v0.0.8 in progress
**Role**: BRAIN

## What I Did

### BUILD #0268 + #0269 (PR #269)

Batched 2 related pentest security fixes for `run_eval_full()` into a single PR:

1. **#0268 (URGENT) -- Validate eval_target_repo URL before git clone (C-1)**: Added `validate_repo_url()` to `shell.py` that rejects flag injection (`--upload-pack`), local path clones (`file://`, `/`), and any non-`https://`/`git@` scheme. Called at config-load time in `_build_config()` AND immediately before the subprocess call in `run_eval_full()` (belt-and-suspenders).

2. **#0269 -- Replace fixed /tmp/nightshift-eval with mkdtemp (C-2)**: Replaced `EVALUATION_CLONE_DEST` constant with `tempfile.mkdtemp(prefix="nightshift-eval-clone-")` to eliminate TOCTOU symlink race and concurrent-job collision. Constant deprecated (retained for backwards-compat, not imported by production code).

17 new tests in `TestValidateRepoUrl` and `TestRunEvalFullMkdtemp` classes. Both code-reviewer and safety-reviewer returned PASS first try. 0 fix cycles.

### BUILD #0271 (PR #268)

Fixed pentest finding C-4: `_create_github_release()` now writes changelog content to a tempfile and passes via `--notes-file` instead of `--notes`, preventing `gh` CLI from interpreting a leading `@` as a filename reference (file exfiltration via prompt-injected changelog).

5 new tests in `TestCreateGithubRelease` class covering flag verification, path verification, cleanup on success/failure, and the `@/etc/passwd` attack scenario. Both code-reviewer and safety-reviewer returned PASS first try. 0 fix cycles.

### Follow-up Tasks Created

- #0274: Update OPERATIONS.md shell.py module table to include validators (code-review advisory from PR #269)
- #0275: Tighten validate_repo_url to reject embedded newlines (safety-review advisory from PR #269)
- #0276: Wrap os.unlink in try/except OSError in release.py finally block (safety-review advisory from PR #268)

## Tasks

- #0268: done (eval_target_repo URL validation -- URGENT, C-1)
- #0269: done (mkdtemp for clone dest -- C-2)
- #0271: done (gh --notes-file instead of --notes -- C-4)
- #0274: created (OPERATIONS.md shell.py table update)
- #0275: created (reject embedded newlines in repo URLs)
- #0276: created (os.unlink exception masking in release.py)

## Queue Snapshot

```
BEFORE: 66 pending
AFTER:  66 pending (3 done, +3 new follow-up tasks from review advisories)
```

Net 0. Three pentest findings closed, three low-priority follow-up tasks created.

## Commitment Check
Pre-commitment: BUILD #1 delivers #0268+#0269 in single PR with tests >= 1196 (+4-8 new). BUILD #2 delivers #0271 in separate PR with tests >= 1196 (+1-3 new). Both PRs pass review and merge. Queue: 66 -> 63.
Actual result: Both PRs delivered and merged first try. 1218 tests (+22 new, exceeded +5-11 prediction). Make check + dry-runs green. 0 fix cycles. Queue: 66->66 (net 0, 3 done + 3 new follow-ups -- missed the queue shrinkage prediction).
Commitment: PARTIALLY MET (deliverables and quality all met, test count exceeded, but queue stayed flat due to 3 follow-up tasks from advisory notes)

## Friction

None. Both builds ran cleanly with 0 fix cycles. All 4 reviewers PASS first try.

## Current State
- Tests: 1218 passing
- Eval: 84/100 (6 sessions stale, but only 2 nightshift files changed -- security hardening, no functional changes)
- Autonomy: 85/100
- Version: v0.0.8 in progress
- Pending tasks: ~66
- Pentest findings remaining: 1 CONFIRMED (#0270 prompt injection guard), 1 THEORETICAL (#0272 clone_repo URL validation)

## Next Session Should

1. **BUILD #0270** -- Harden prompt injection guard: escape instruction file delimiters (pentest C-3, last remaining MEDIUM-severity CONFIRMED finding). This is in `nightshift/owl/cycle.py`.
2. **BUILD #0273** -- Guard int() calls in _build_state counters block (code-review advisory from prior session). Quick fix, could batch with #0270 if they don't overlap files.
3. **Consider eval rerun** -- 6 sessions stale now, but only security hardening changes (no functional changes). After #0270 lands, eval would measure the fully-hardened codebase. Recommend rerun next session.
