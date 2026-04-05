# Readiness checks as pure file scanners

**Date**: 2026-04-05
**Category**: Code Patterns
**Type**: pattern

## Learning

Production-readiness checks (secret detection, debug print scanning, test coverage verification) work best as pure file-content scanners that take a list of relative paths + a repo_dir, not as shell-command wrappers. The check functions read files directly with Path.read_text() and apply compiled regex patterns from constants.py. This keeps the module testable with tmp_path fixtures (no subprocesses, no mocks) and fast (all 40 tests run in under 0.5s).

The key design choice: extract changed file paths from FeatureState (which already has them in wave results), then pass those paths to individual check functions. Each check is independent and returns a ReadinessCheck TypedDict with name/passed/details. The orchestrator just collects results and computes a verdict.

## Why it matters

Shell-command-based checks (running ruff, mypy, etc.) would couple the readiness module to the target repo's toolchain. Pure file scanning works on any repo regardless of what tools are installed.
