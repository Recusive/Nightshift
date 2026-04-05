"""Production-readiness checks for Loop 2 feature builds."""

from __future__ import annotations

import re
from pathlib import Path

from nightshift.constants import DEBUG_PRINT_PATTERNS, READINESS_ALL_CHECKS, SECRET_PATTERNS
from nightshift.types import FeatureState, NightshiftConfig, ReadinessCheck, ReadinessReport

# Basename substrings that indicate test files.
_TEST_INDICATORS = {"test_", "_test.", ".test.", "spec.", "_spec."}

# Extensions considered source code for readiness scanning.
_SOURCE_EXTENSIONS = frozenset({".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".php"})


def _is_test_file(path: str) -> bool:
    """Return True if *path* looks like a test file."""
    basename = path.rsplit("/", 1)[-1].lower()
    return any(indicator in basename for indicator in _TEST_INDICATORS)


def _is_source_file(path: str) -> bool:
    """Return True if *path* is a code file worth scanning."""
    dot_idx = path.rfind(".")
    if dot_idx < 0:
        return False
    return path[dot_idx:].lower() in _SOURCE_EXTENSIONS


def collect_changed_files(state: FeatureState) -> tuple[list[str], list[str]]:
    """Extract deduplicated (files_created, files_modified) from feature state."""
    created: set[str] = set()
    modified: set[str] = set()
    for wave in state["waves"]:
        wave_result = wave["wave_result"]
        if wave_result is None:
            continue
        for task in wave_result["completed"]:
            created.update(task["files_created"])
            modified.update(task["files_modified"])
    modified -= created
    return sorted(created), sorted(modified)


def _scan_file_for_patterns(
    file_path: Path,
    patterns: list[re.Pattern[str]],
) -> list[str]:
    """Return list of 'path:line' strings for lines matching any pattern."""
    hits: list[str] = []
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits
    for line_number, line in enumerate(text.splitlines(), 1):
        for pattern in patterns:
            if pattern.search(line):
                hits.append(f"{file_path}:{line_number}")
                break
    return hits


def check_secrets(
    files: list[str],
    repo_dir: Path,
) -> ReadinessCheck:
    """Scan changed files for potential secrets and credentials."""
    all_hits: list[str] = []
    for rel_path in files:
        abs_path = repo_dir / rel_path
        if not abs_path.is_file():
            continue
        if not _is_source_file(rel_path):
            continue
        all_hits.extend(_scan_file_for_patterns(abs_path, SECRET_PATTERNS))

    if all_hits:
        detail_lines = [f"Potential secrets found in {len(all_hits)} location(s):"]
        detail_lines.extend(all_hits[:10])
        if len(all_hits) > 10:
            detail_lines.append(f"... and {len(all_hits) - 10} more")
        return ReadinessCheck(name="secrets", passed=False, details="\n".join(detail_lines))

    return ReadinessCheck(name="secrets", passed=True, details="No secrets detected in changed files.")


def check_debug_prints(
    files: list[str],
    repo_dir: Path,
) -> ReadinessCheck:
    """Scan changed files for debug print/log statements."""
    all_hits: list[str] = []
    for rel_path in files:
        abs_path = repo_dir / rel_path
        if not abs_path.is_file():
            continue
        if not _is_source_file(rel_path):
            continue
        if _is_test_file(rel_path):
            continue
        all_hits.extend(_scan_file_for_patterns(abs_path, DEBUG_PRINT_PATTERNS))

    if all_hits:
        detail_lines = [f"Debug statements found in {len(all_hits)} location(s):"]
        detail_lines.extend(all_hits[:10])
        if len(all_hits) > 10:
            detail_lines.append(f"... and {len(all_hits) - 10} more")
        return ReadinessCheck(name="debug_prints", passed=False, details="\n".join(detail_lines))

    return ReadinessCheck(name="debug_prints", passed=True, details="No debug statements found in production code.")


def _test_file_candidates(rel_path: str) -> list[str]:
    """Return candidate test file paths for a given production source file."""
    parts = rel_path.replace("\\", "/").split("/")
    basename = parts[-1]
    name_stem, _, ext_no_dot = basename.rpartition(".")
    if not name_stem:
        return []
    ext = f".{ext_no_dot}"
    test_basename = f"test_{name_stem}{ext}"

    candidates: list[str] = []
    parent = "/".join(parts[:-1])
    if parent:
        candidates.append(f"{parent}/{test_basename}")
    else:
        candidates.append(test_basename)

    for test_dir in ("tests", "test"):
        if len(parts) > 1:
            sub = "/".join(parts[1:-1])
            if sub:
                candidates.append(f"{test_dir}/{sub}/{test_basename}")
        candidates.append(f"{test_dir}/{test_basename}")

    return candidates


def check_test_coverage(
    files_created: list[str],
    files_modified: list[str],
    repo_dir: Path,
) -> ReadinessCheck:
    """Check that changed production source files have corresponding test files."""
    production_files: list[str] = []
    for rel_path in files_created + files_modified:
        if _is_source_file(rel_path) and not _is_test_file(rel_path):
            production_files.append(rel_path)

    if not production_files:
        return ReadinessCheck(name="test_coverage", passed=True, details="No production source files to check.")

    uncovered: list[str] = []
    for rel_path in production_files:
        candidates = _test_file_candidates(rel_path)
        found = any((repo_dir / c).is_file() for c in candidates)
        if not found:
            uncovered.append(rel_path)

    if uncovered:
        detail_lines = [f"{len(uncovered)} production file(s) without test coverage:"]
        detail_lines.extend(uncovered[:10])
        if len(uncovered) > 10:
            detail_lines.append(f"... and {len(uncovered) - 10} more")
        return ReadinessCheck(name="test_coverage", passed=False, details="\n".join(detail_lines))

    return ReadinessCheck(
        name="test_coverage",
        passed=True,
        details=f"All {len(production_files)} production file(s) have corresponding tests.",
    )


def check_production_readiness(
    state: FeatureState,
    repo_dir: Path,
    config: NightshiftConfig,
) -> ReadinessReport:
    """Run all enabled production-readiness checks and return an aggregate report."""
    enabled = set(config["readiness_checks"]) & READINESS_ALL_CHECKS
    files_created, files_modified = collect_changed_files(state)
    all_files = files_created + files_modified

    checks: list[ReadinessCheck] = []

    if "secrets" in enabled:
        checks.append(check_secrets(all_files, repo_dir))

    if "debug_prints" in enabled:
        checks.append(check_debug_prints(all_files, repo_dir))

    if "test_coverage" in enabled:
        checks.append(check_test_coverage(files_created, files_modified, repo_dir))

    passed_count = sum(1 for c in checks if c["passed"])
    failed_count = len(checks) - passed_count
    verdict = "ready" if failed_count == 0 else "not_ready"

    return ReadinessReport(
        checks=checks,
        verdict=verdict,
        passed_count=passed_count,
        failed_count=failed_count,
    )
