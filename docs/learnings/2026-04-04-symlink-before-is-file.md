# Learning: Check is_symlink() before is_file() for security

**Date**: 2026-04-04
**Session**: 0025
**Type**: pattern

## What happened

When adding symlink rejection to `read_repo_instructions()`, the key insight is that `Path.is_file()` returns `True` for symlinks pointing to regular files. So the symlink check must come BEFORE the `is_file()` check, not after. If you check `is_file()` first and it returns True, you'd never reach the symlink check.

Also, `Path.is_symlink()` returns True even for broken/dangling symlinks (where the target doesn't exist), while `is_file()` returns False for those. So ordering matters: `is_symlink()` first catches ALL symlinks (valid and broken), then `is_file()` only runs for non-symlink regular files.

## Reusable pattern

```python
if path.is_symlink():
    # reject -- covers both valid and broken symlinks
    continue
if path.is_file():
    # safe to read -- guaranteed not a symlink
```
