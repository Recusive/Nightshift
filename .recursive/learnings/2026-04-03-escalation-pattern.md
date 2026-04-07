# Learning: The escalation pattern is the right abstraction for prompt directives
**Date**: 2026-04-03
**Session**: 0009
**Type**: pattern

## What happened
Category balancing was built in under 20 minutes by following the exact same pattern as test escalation and backend forcing: a standalone function returns a directive string (or empty), and `build_prompt()` injects it as a labeled block. No new abstractions needed.

## The lesson
When adding agent steering logic, follow the established escalation pattern:
1. Standalone function with `(cycle, config, state, ...)` signature
2. Returns empty string when not triggered
3. Caller passes result to `build_prompt()` as a named `str` parameter
4. `build_prompt()` wraps it in a labeled block if non-empty

This keeps `build_prompt()` as a pure assembler and makes each directive independently testable. Don't put detection logic inside `build_prompt()`.

## Evidence
- `build_test_escalation()`, `build_backend_escalation()`, `build_category_balancing()` all follow this pattern
- 11 tests added with zero test infrastructure changes
