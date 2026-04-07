---
date: 2026-04-06
topic: prompt-alert-pre-poison-guard
category: Security
---

# Gitignored alert files need explicit rm before integrity check

`docs/sessions/` is gitignored. `git clean -fd` only removes untracked,
non-ignored files. Any file the pentest agent creates under `docs/sessions/`
(including `prompt-alert.md`) survives `reset_repo_state` intact.

`check_prompt_integrity` is designed to be the sole writer of `$PROMPT_ALERT`.
But if the pentest agent pre-writes the file during its turn window,
`check_prompt_integrity` will see an existing file and — finding no integrity
violations — leave it untouched. The builder then injects the poisoned content.

**Fix pattern**: Add `rm -f "$PROMPT_ALERT"` immediately before the
`check_prompt_integrity` call. This clears any pentest-agent-written content
so the integrity check starts from a known-empty state and only writes the
file when it actually detects a real violation.

**General rule**: Any mechanism that "writes only on condition" must also have
an unconditional clear before it runs, if an adversary had write access to the
file in the intervening window.
