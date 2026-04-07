# Learning: RepoProfile schema changes cascade into feature fixtures
**Date**: 2026-04-05
**Session**: 0042
**Type**: gotcha

## What happened
Adding `dependencies` and `conventions` to `RepoProfile` worked in profiler-focused tests, but full `make check` failed in `tests/test_feature_build.py` because those fixtures still built the old schema. The runtime rebuild path in `nightshift/feature.py::_build_profile()` also needed the new fields so persisted state stayed backward-compatible.

## The lesson
Treat `RepoProfile` as a shared schema, not a local profiler detail. When it changes, grep `nightshift/feature.py`, `tests/test_feature_build.py`, and `tests/test_nightshift.py` before trusting targeted test subsets.

## Evidence
- `KeyError: 'dependencies'` from `nightshift/decomposer.py:76` during `make check`
- Fixes landed in `nightshift/feature.py`, `tests/test_feature_build.py`, and `tests/test_nightshift.py`
