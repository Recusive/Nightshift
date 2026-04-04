"""Post-cycle diff scoring: evaluates production impact of cycle changes."""

from __future__ import annotations

from pathlib import Path

from nightshift.constants import (
    CATEGORY_SCORES,
    ERROR_HANDLING_PATTERNS,
    SECURITY_PATTERNS,
    print_status,
)
from nightshift.errors import NightshiftError
from nightshift.shell import git
from nightshift.types import CycleResult, DiffScore


def _diff_line_score(diff_text: str) -> int:
    """Scan diff added-lines for high-impact patterns. Return the max signal found."""
    best = 0
    for line in diff_text.splitlines():
        if not line.startswith("+"):
            continue
        for pattern, score in SECURITY_PATTERNS:
            if pattern.search(line):
                best = max(best, score)
        for pattern, score in ERROR_HANDLING_PATTERNS:
            if pattern.search(line):
                best = max(best, score)
    return best


def _has_test_files(files: list[str]) -> bool:
    """Return True if any touched file looks like a test file."""
    for f in files:
        name = f.rsplit("/", 1)[-1].lower()
        if name.startswith("test_") or name.endswith("_test.py") or name.endswith(".test.ts"):
            return True
        if name.endswith(".test.js") or name.endswith(".test.tsx") or name.endswith(".test.jsx"):
            return True
        if name.endswith(".spec.ts") or name.endswith(".spec.js"):
            return True
    return False


def score_diff(
    *,
    worktree_dir: Path,
    pre_head: str,
    cycle_result: CycleResult | None,
    files_touched: list[str],
) -> DiffScore:
    """Score a cycle's changes on a 1-10 scale based on production impact.

    Scoring factors:
    1. Category of fixes (from cycle_result) - higher-priority categories score higher
    2. Diff content analysis - security/error patterns in added lines boost the score
    3. Test bonus - writing tests adds +1
    4. Category breadth bonus - multiple categories in one cycle adds +1
    """
    base = 1  # minimum score for any accepted cycle

    # Factor 1: category scores from structured result
    categories_seen: set[str] = set()
    if cycle_result is not None:
        for fix in cycle_result.get("fixes", []):
            cat = fix.get("category", "")
            if cat:
                categories_seen.add(cat)
                cat_score = CATEGORY_SCORES.get(cat, 3)
                base = max(base, cat_score)

    # Factor 2: diff content analysis
    try:
        diff_text = git(worktree_dir, "diff", f"{pre_head}..HEAD")
    except NightshiftError:
        diff_text = ""
    line_score = _diff_line_score(diff_text)
    base = max(base, line_score)

    # Factor 3: test bonus (+2 to incentivize test writing)
    test_bonus = _has_test_files(files_touched)
    if test_bonus:
        base = min(base + 2, 10)

    # Factor 4: category breadth bonus
    category_bonus = len(categories_seen) >= 2
    if category_bonus:
        base = min(base + 1, 10)

    # Build reason string
    parts: list[str] = []
    if categories_seen:
        parts.append(f"categories: {', '.join(sorted(categories_seen))}")
    if line_score > 0:
        parts.append(f"diff signal: {line_score}")
    if test_bonus:
        parts.append("test file included")
    if category_bonus:
        parts.append("multi-category breadth")
    reason = "; ".join(parts) if parts else "no high-impact signals detected"

    return DiffScore(
        score=min(base, 10),
        reason=reason,
        category_bonus=category_bonus,
        test_bonus=test_bonus,
    )


def log_score(diff_score: DiffScore) -> None:
    """Print the diff score to stdout."""
    print_status(f"Diff score: {diff_score['score']}/10 ({diff_score['reason']})")
