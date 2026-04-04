# ruff import sorting is module-name-alphabetical

**Type**: gotcha
**Date**: 2026-04-03

When adding a new module import to `__init__.py`, the import block must be sorted by module name alphabetically across the entire block (e.g., `errors` before `multi` before `subagent`). Within each `from nightshift.X import (...)` block, names must also be sorted alphabetically.

Inserting a new import right after the related module (e.g., `subagent` after `decomposer`) will fail ruff I001. Use `ruff check --fix` to auto-sort, or manually place the import in the correct alphabetical position by module name.

Also: when adding new constants to an existing import block (e.g., adding `SUBAGENT_DEFAULT_TIMEOUT` to the constants import), they must be inserted in alphabetical order within the block, not appended after the last existing entry.
