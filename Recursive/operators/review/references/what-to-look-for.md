# What to Look For

For each function in the file, ask:

## Type Safety
- `dict[str, Any]` used where a TypedDict would be more precise?
- `.get()` on required TypedDict fields? (mypy rejects this)
- Missing return type annotations?
- Broad exception catches (`except Exception`) that should be specific?

## Code Structure
- Functions over 50 lines? (should be split)
- Hardcoded values in logic files? (should be in constants)
- Business logic in CLI files? (should be in domain modules)
- Duplicate logic across modules?

## Error Handling
- Silent failures (catch + pass)?
- Missing error messages in exception raises?
- subprocess calls without timeout?
- File operations without existence checks?

## Behavioral Questions
- Is it doing one thing, or three things crammed together?
- Are edge cases handled?
- Is the error handling at the right level?
- Are types complete and accurate?
- Is the naming clear without comments?
- Does it follow project conventions?

## Tests
- Functions with no test coverage?
- Tests that only check the happy path?
- Tests that test implementation details instead of behavior?
- Missing edge case tests (empty input, None, boundary values)?

## Dead Code
- Unused imports?
- Functions defined but never called?
- Commented-out code?
- Variables assigned but never read?

## Documentation Drift
- Docstrings that don't match function behavior?
- Operations docs out of date with actual functions?
- README examples that don't work?
