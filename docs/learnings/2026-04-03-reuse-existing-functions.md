---
type: optimization
date: 2026-04-03
area: nightshift/decomposer.py
---

# Reuse planner functions instead of reimplementing

When building decomposer.py, the natural instinct was to reimplement wave computation inside the decomposer. But `execution_order()` already exists in planner.py and does exactly this (Kahn's algorithm, deterministic wave ordering, circular dep detection). Importing and reusing it saved ~30 lines of code and ensured both modules produce identical wave groupings.

**Pattern**: Before building a new module, check what the upstream module already exports. The dependency flow (planner -> decomposer) means decomposer can freely import from planner.

**Gotcha**: The `_format_frameworks()` helper is duplicated between planner.py and decomposer.py because both build agent prompts. If a third module needs it, extract to a shared utility. Two copies is fine; three copies means refactor.
