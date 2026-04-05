# E2E as a gate before final verification

**Date**: 2026-04-05
**Category**: Code Patterns
**Type**: pattern

## Context

When adding the E2E test runner to the build_feature() pipeline, I placed it between the wave loop and run_final_verification(). The question was whether E2E should be a gate (failure stops the pipeline) or advisory (failure is logged but pipeline continues).

## Learning

Making E2E a gate that prevents final verification from running when E2E fails is the right design. Final verification runs both tests AND lint. If the test suite already failed in E2E, running it again in final verification wastes time and produces confusing output (two failure reports for the same tests). Gate early, fail fast.

The pattern: when pipeline steps share a common check (both E2E and final verification run the test suite), the earlier step should be the gate. The later step should focus on what the earlier step does NOT check (in this case, lint).

## Gotcha

The existing `test_feature_build.py` integration tests did not mock the new E2E step, so they broke. When adding a new step to a pipeline, grep for ALL integration tests that exercise that pipeline end-to-end and add mocks for the new step.
