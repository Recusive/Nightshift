# Learning: TypedDict refactors must update aggregate containers too

**Date**: 2026-04-05
**Session**: #0046
**Type**: type-system

## What happened

Task `#0044` changed `compact.py:_parse_handoff()` from `dict[str, str]` to a
private `_ParsedHandoff` `TypedDict`. The helper itself type-checked, but
`make check` still failed because `compact_handoffs()` kept `parsed` annotated
as `list[dict[str, str]]`, and `_build_weekly_summary()` expected
`list[_ParsedHandoff]`.

## Why it matters

Mypy treats `list[dict[str, str]]` and `list[TypedDict]` as incompatible even
when the element values are all strings. Changing a helper return type is not
enough; every aggregate container and downstream function signature has to move
with it.

## Rule

When converting a loose dict contract to a `TypedDict`, grep for every list,
parameter, and local variable that stores the helper result and retype those in
the same patch before trusting mypy.
