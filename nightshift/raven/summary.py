"""Feature summary generation for Loop 2 build output."""

from __future__ import annotations

from nightshift.core.types import FeatureState, FeatureSummary

# Directory segments that indicate API-related code.
_API_DIR_SEGMENTS = {"api", "routes", "endpoints", "handlers", "controllers", "resolvers"}

# Directory segments that indicate CLI code.
_CLI_DIR_SEGMENTS = {"cli", "cmd", "commands"}

# Directory segments that indicate configuration.
_CONFIG_DIR_SEGMENTS = {"config", "settings", "conf"}

# Directory segments that indicate database/model code.
_DB_DIR_SEGMENTS = {"models", "migrations", "db", "database", "schemas"}

# Basename substrings that indicate test files.
_TEST_INDICATORS = {"test_", "_test.", ".test.", "spec.", "_spec."}


def _is_test_file(path: str) -> bool:
    """Return True if *path* looks like a test file."""
    basename = path.rsplit("/", 1)[-1].lower()
    return any(indicator in basename for indicator in _TEST_INDICATORS)


def _detect_patterns(files_created: list[str], files_modified: list[str]) -> list[str]:
    """Detect high-level patterns from the file paths touched during the build."""
    patterns: list[str] = []
    all_files = files_created + files_modified

    lowered_parts: list[set[str]] = []
    for path in all_files:
        lowered_parts.append({segment.lower() for segment in path.replace("\\", "/").split("/")})

    has_api = any(parts & _API_DIR_SEGMENTS for parts in lowered_parts)
    has_cli = any(parts & _CLI_DIR_SEGMENTS for parts in lowered_parts)
    has_config = any(parts & _CONFIG_DIR_SEGMENTS for parts in lowered_parts)
    has_db = any(parts & _DB_DIR_SEGMENTS for parts in lowered_parts)
    new_test_files = [f for f in files_created if _is_test_file(f)]

    new_py_modules = [f for f in files_created if f.endswith(".py") and not _is_test_file(f)]

    if has_api:
        patterns.append("New or modified API endpoints")
    if has_cli:
        patterns.append("New or modified CLI commands")
    if has_config:
        patterns.append("Configuration changes")
    if has_db:
        patterns.append("Database or model changes")
    if new_py_modules:
        patterns.append(f"{len(new_py_modules)} new Python module(s)")
    if new_test_files:
        patterns.append(f"{len(new_test_files)} new test file(s)")

    return patterns


def _collect_files(state: FeatureState) -> tuple[list[str], list[str], list[str]]:
    """Extract deduplicated file lists from all wave results in the state."""
    created_set: set[str] = set()
    modified_set: set[str] = set()
    tests: list[str] = []

    for wave in state["waves"]:
        wave_result = wave["wave_result"]
        if wave_result is None:
            continue
        for task in wave_result["completed"]:
            created_set.update(task["files_created"])
            modified_set.update(task["files_modified"])
            tests.extend(task["tests_written"])

    # Files that appear in both lists should only be in created.
    modified_set -= created_set

    return sorted(created_set), sorted(modified_set), tests


def _build_description(state: FeatureState, summary: FeatureSummary) -> str:
    """Generate a one-paragraph natural language description of the build."""
    feature_name = state["plan"]["feature"]
    status = state["status"]

    file_count = len(summary["files_created"]) + len(summary["files_modified"])
    test_count = len(summary["tests_added"])

    parts: list[str] = [f"Built '{feature_name}'"]

    if status == "completed":
        parts.append(f"({summary['completed_tasks']}/{summary['total_tasks']} tasks completed)")
    else:
        parts.append(f"(build {status}: {summary['completed_tasks']}/{summary['total_tasks']} tasks)")

    if file_count:
        parts.append(f"touching {file_count} file(s)")

    if test_count:
        parts.append(f"with {test_count} test(s) added")

    if summary["patterns_detected"]:
        parts.append(f"-- {', '.join(summary['patterns_detected']).lower()}")

    return ". ".join([" ".join(parts)]) + "."


def generate_feature_summary(state: FeatureState) -> FeatureSummary:
    """Produce a structured summary from a completed (or failed) feature build.

    Extracts files created/modified, tests written, task counts, detected patterns,
    and a natural language description suitable for changelogs and handoffs.
    """
    files_created, files_modified, tests_added = _collect_files(state)

    total_tasks = len(state["plan"]["tasks"])
    completed_tasks = 0
    failed_tasks = 0
    for wave in state["waves"]:
        wave_result = wave["wave_result"]
        if wave_result is None:
            continue
        completed_tasks += len(wave_result["completed"])
        failed_tasks += len(wave_result["failed"])

    patterns = _detect_patterns(files_created, files_modified)

    summary = FeatureSummary(
        files_created=files_created,
        files_modified=files_modified,
        tests_added=tests_added,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        failed_tasks=failed_tasks,
        patterns_detected=patterns,
        description="",
    )
    summary["description"] = _build_description(state, summary)
    return summary
