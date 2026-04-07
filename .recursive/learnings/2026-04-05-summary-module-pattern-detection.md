# Pattern detection via path segment analysis

**Category**: Code Patterns
**Date**: 2026-04-05

## Learning

When detecting high-level patterns from file paths (e.g., "this build touched API endpoints"), splitting the path into segments and checking against keyword sets is more robust than regex matching against the full path. A file at `src/api/users.py` and one at `api/v2/routes.py` both match `{"api", "routes", "endpoints"}` via set intersection, without needing separate regex patterns for each nesting depth.

## Context

Built `nightshift/summary.py` which needs to detect patterns like "API changes", "CLI modifications", "database changes" from the list of files a feature build touched. The path-segment-set approach handles Windows backslashes, varying nesting depths, and case differences cleanly in a few lines.

## Applicability

Any code that needs to categorize files by purpose based on their paths. The profiler (`nightshift/profiler.py`) and cycle module both do similar path-based classification. This pattern could unify those.
