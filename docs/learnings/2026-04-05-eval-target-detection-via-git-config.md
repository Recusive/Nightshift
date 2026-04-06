# Eval target detection via git config

**Date**: 2026-04-05
**Type**: code-pattern
**Session**: #0059 (Phractal eval verification metadata)

## What happened

The first implementation of repo-specific evaluation metadata shelled out to
`git config --get remote.origin.url`. `make check` rejected it with Ruff
security rules (`S603`/`S607`), and the subprocess was unnecessary anyway.

## Rule

When behavior depends on repo identity, prefer reading `.git/config` (and
worktree `commondir` indirection when needed) as pure file I/O instead of
shelling out to `git`.

## Apply next time

Key repo-specific metadata by normalized remote URL, and make the detection
helper a pure file reader so lint/security rules stay satisfied without adding
per-file exceptions.
