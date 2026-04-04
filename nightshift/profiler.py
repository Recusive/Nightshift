"""Repo profiling for Loop 2 -- detects language, framework, structure."""

from __future__ import annotations

import json
from pathlib import Path

from nightshift.config import infer_package_manager, infer_verify_command
from nightshift.constants import (
    DEFAULT_CONFIG,
    FRAMEWORK_MARKERS,
    FRAMEWORK_PACKAGES,
    INSTRUCTION_FILE_NAMES,
    LANGUAGE_EXTENSIONS,
    MONOREPO_MARKERS,
    PROFILER_SKIP_DIRS,
)
from nightshift.types import FrameworkInfo, NightshiftConfig, RepoProfile


def _count_languages(repo_dir: Path) -> dict[str, int]:
    """Walk the repo and count files by language extension."""
    counts: dict[str, int] = {}
    try:
        for path in repo_dir.rglob("*"):
            if not path.is_file():
                continue
            # Skip ignored directories
            parts = path.relative_to(repo_dir).parts
            if any(part in PROFILER_SKIP_DIRS for part in parts):
                continue
            if path.name.startswith("."):
                continue
            ext = path.suffix.lower()
            lang = LANGUAGE_EXTENSIONS.get(ext)
            if lang is not None:
                counts[lang] = counts.get(lang, 0) + 1
    except OSError:
        pass
    return counts


def _primary_language(counts: dict[str, int]) -> str:
    """Return the language with the most files, or 'Unknown'."""
    if not counts:
        return "Unknown"
    return max(counts, key=lambda k: counts[k])


def _detect_frameworks_by_marker(repo_dir: Path) -> list[str]:
    """Detect frameworks by checking for known marker files."""
    found: list[str] = []
    for framework, markers in FRAMEWORK_MARKERS.items():
        for marker in markers:
            if (repo_dir / marker).exists():
                found.append(framework)
                break
    return found


def _read_package_json_deps(repo_dir: Path) -> dict[str, str]:
    """Read dependencies and devDependencies from package.json."""
    pkg_path = repo_dir / "package.json"
    if not pkg_path.exists():
        return {}
    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    deps: dict[str, str] = {}
    for section in ("dependencies", "devDependencies"):
        section_data = data.get(section, {})
        if isinstance(section_data, dict):
            deps.update(section_data)
    return deps


def _detect_frameworks_by_package(repo_dir: Path) -> list[FrameworkInfo]:
    """Detect frameworks from package.json dependencies with versions."""
    deps = _read_package_json_deps(repo_dir)
    if not deps:
        return []
    results: list[FrameworkInfo] = []
    for framework, package in FRAMEWORK_PACKAGES.items():
        if package in deps:
            version = deps[package]
            results.append(FrameworkInfo(name=framework, version=version))
    return results


def _detect_frameworks(repo_dir: Path) -> list[FrameworkInfo]:
    """Combine marker-based and package-based framework detection."""
    marker_names = _detect_frameworks_by_marker(repo_dir)
    pkg_frameworks = _detect_frameworks_by_package(repo_dir)

    # Build set of names already found via packages (with versions)
    pkg_names: set[str] = {fw["name"] for fw in pkg_frameworks}

    # Add marker-detected frameworks that aren't already found via packages
    results = list(pkg_frameworks)
    for name in marker_names:
        if name not in pkg_names:
            results.append(FrameworkInfo(name=name, version=""))
    return results


def _find_instruction_files(repo_dir: Path) -> list[str]:
    """Find AI instruction files in the repo."""
    found: list[str] = []
    for name in INSTRUCTION_FILE_NAMES:
        if (repo_dir / name).exists():
            found.append(name)
    return found


def _list_top_level_dirs(repo_dir: Path) -> list[str]:
    """List non-hidden, non-ignored top-level directories."""
    dirs: list[str] = []
    try:
        for entry in sorted(repo_dir.iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name
            if name.startswith("."):
                continue
            if name in PROFILER_SKIP_DIRS:
                continue
            dirs.append(name)
    except OSError:
        pass
    return dirs


def _has_monorepo_markers(repo_dir: Path) -> bool:
    """Check if the repo has monorepo tooling markers."""
    return any((repo_dir / marker).exists() for marker in MONOREPO_MARKERS)


def _count_total_files(repo_dir: Path) -> int:
    """Count total non-ignored files in the repo."""
    count = 0
    try:
        for path in repo_dir.rglob("*"):
            if not path.is_file():
                continue
            parts = path.relative_to(repo_dir).parts
            if any(part in PROFILER_SKIP_DIRS for part in parts):
                continue
            if path.name.startswith("."):
                continue
            count += 1
    except OSError:
        pass
    return count


def _infer_test_runner(repo_dir: Path) -> str | None:
    """Infer the test runner command for the repo."""
    # Build a minimal config just for verify command inference
    config = NightshiftConfig(
        agent=None,
        hours=DEFAULT_CONFIG["hours"],
        cycle_minutes=DEFAULT_CONFIG["cycle_minutes"],
        verify_command=None,
        blocked_paths=list(DEFAULT_CONFIG["blocked_paths"]),
        blocked_globs=list(DEFAULT_CONFIG["blocked_globs"]),
        max_fixes_per_cycle=DEFAULT_CONFIG["max_fixes_per_cycle"],
        max_files_per_fix=DEFAULT_CONFIG["max_files_per_fix"],
        max_files_per_cycle=DEFAULT_CONFIG["max_files_per_cycle"],
        max_low_impact_fixes_per_shift=DEFAULT_CONFIG["max_low_impact_fixes_per_shift"],
        stop_after_failed_verifications=DEFAULT_CONFIG["stop_after_failed_verifications"],
        stop_after_empty_cycles=DEFAULT_CONFIG["stop_after_empty_cycles"],
        score_threshold=DEFAULT_CONFIG["score_threshold"],
        test_incentive_cycle=DEFAULT_CONFIG["test_incentive_cycle"],
        backend_forcing_cycle=DEFAULT_CONFIG["backend_forcing_cycle"],
        category_balancing_cycle=DEFAULT_CONFIG["category_balancing_cycle"],
    )
    return infer_verify_command(repo_dir, config)


def profile_repo(repo_dir: Path) -> RepoProfile:
    """Build a comprehensive profile of the target repository.

    This is the foundation for Loop 2. Sub-agents receive this profile
    so they know the stack, conventions, and structure of the repo
    they're modifying.
    """
    languages = _count_languages(repo_dir)
    return RepoProfile(
        languages=languages,
        primary_language=_primary_language(languages),
        frameworks=_detect_frameworks(repo_dir),
        package_manager=infer_package_manager(repo_dir),
        test_runner=_infer_test_runner(repo_dir),
        instruction_files=_find_instruction_files(repo_dir),
        top_level_dirs=_list_top_level_dirs(repo_dir),
        has_monorepo_markers=_has_monorepo_markers(repo_dir),
        total_files=_count_total_files(repo_dir),
    )
