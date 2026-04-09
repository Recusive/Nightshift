"""Repo profiling for Loop 2 -- detects language, framework, dependencies, structure."""

from __future__ import annotations

import ast
import copy
import importlib
import json
from pathlib import Path
from types import ModuleType

from nightshift.core.constants import (
    DEFAULT_CONFIG,
    FRAMEWORK_MARKERS,
    FRAMEWORK_PACKAGES,
    INSTRUCTION_FILE_NAMES,
    LANGUAGE_EXTENSIONS,
    MONOREPO_MARKERS,
    PROFILER_SKIP_DIRS,
)
from nightshift.core.types import FrameworkInfo, NightshiftConfig, RepoProfile
from nightshift.settings.config import infer_package_manager, infer_verify_command


def _relative_parts(repo_dir: Path, path: Path) -> tuple[str, ...]:
    """Return path parts relative to repo_dir when possible."""
    try:
        return path.relative_to(repo_dir).parts
    except ValueError:
        return path.parts


def _should_skip_nested_scan(repo_dir: Path, path: Path) -> bool:
    """Skip hidden and ignored paths for recursive manifest scans."""
    parts = _relative_parts(repo_dir, path)
    return any(part in PROFILER_SKIP_DIRS or part.startswith(".") for part in parts)


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


def _package_json_paths(repo_dir: Path) -> list[Path]:
    """Find root and nested package.json files, skipping ignored directories."""
    paths: list[Path] = []
    try:
        for path in repo_dir.rglob("package.json"):
            if _should_skip_nested_scan(repo_dir, path):
                continue
            paths.append(path)
    except OSError:
        return []
    return sorted(paths, key=lambda item: str(item.relative_to(repo_dir)))


def _read_package_json_deps(pkg_path: Path) -> dict[str, str]:
    """Read dependencies and devDependencies from one package.json."""
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
            for name, version in section_data.items():
                if isinstance(name, str) and isinstance(version, str):
                    deps[name] = version
    return deps


def _collect_package_json_deps(repo_dir: Path) -> dict[str, str]:
    """Collect dependencies across all package.json files in a repo."""
    deps: dict[str, str] = {}
    for path in _package_json_paths(repo_dir):
        deps.update(_read_package_json_deps(path))
    return deps


def _detect_frameworks_by_package(repo_dir: Path) -> list[FrameworkInfo]:
    """Detect frameworks from package.json dependencies across the repo."""
    deps = _collect_package_json_deps(repo_dir)
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


def _parse_requirement_name(spec: str) -> str | None:
    """Extract a package name from a requirements/pyproject dependency spec."""
    line = spec.strip()
    if not line:
        return None
    line = line.split("#egg=", 1)[1].strip() if "#egg=" in line else line.split("#", 1)[0].strip()
    if not line or line.startswith(("-c", "-r", "--", ".", "/")):
        return None
    if line.startswith("-e "):
        line = line[3:].strip()
    if ";" in line:
        line = line.split(";", 1)[0].strip()
    if "[" in line:
        line = line.split("[", 1)[0].strip()
    for separator in ("==", ">=", "<=", "~=", "!=", ">", "<"):
        if separator in line:
            line = line.split(separator, 1)[0].strip()
            break
    return line or None


def _requirements_paths(repo_dir: Path) -> list[Path]:
    """Return top-level requirements files in stable order."""
    return sorted(path for path in repo_dir.glob("requirements*.txt") if path.is_file())


def _parse_requirements_file(path: Path) -> list[str]:
    """Parse dependency names from a requirements file."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    names: list[str] = []
    for line in lines:
        name = _parse_requirement_name(line)
        if name is not None:
            names.append(name)
    return names


def _load_toml_module() -> ModuleType | None:
    """Load a TOML parser if one is available on this Python version."""
    for name in ("tomllib", "tomli"):
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            continue
    return None


def _string_array_from_lines(lines: list[str], start_index: int) -> tuple[list[str], int]:
    """Parse a TOML array of strings spanning one or more lines."""
    after_equals = lines[start_index].split("=", 1)
    if len(after_equals) != 2:
        return [], start_index + 1
    buffer = after_equals[1].strip()
    index = start_index + 1
    while "]" not in buffer and index < len(lines):
        buffer += "\n" + lines[index].strip()
        index += 1
    try:
        raw = ast.literal_eval(buffer)
    except (SyntaxError, ValueError):
        return [], index
    if not isinstance(raw, list):
        return [], index
    return [item for item in raw if isinstance(item, str)], index


def _poetry_dependency_names(raw: object) -> list[str]:
    """Extract dependency names from a Poetry dependency table."""
    if not isinstance(raw, dict):
        return []
    names: list[str] = []
    for name in raw:
        if isinstance(name, str) and name != "python":
            names.append(name)
    return names


def _dependency_names_from_specs(raw: object) -> list[str]:
    """Extract dependency names from an array of requirement-like specs."""
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for item in raw:
        if isinstance(item, str):
            name = _parse_requirement_name(item)
            if name is not None:
                names.append(name)
    return names


def _dependencies_from_pyproject_data(data: object) -> list[str]:
    """Extract dependency names from parsed pyproject.toml data."""
    if not isinstance(data, dict):
        return []

    names: list[str] = []

    project = data.get("project")
    if isinstance(project, dict):
        names.extend(_dependency_names_from_specs(project.get("dependencies")))
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for deps in optional.values():
                names.extend(_dependency_names_from_specs(deps))

    dependency_groups = data.get("dependency-groups")
    if isinstance(dependency_groups, dict):
        for deps in dependency_groups.values():
            names.extend(_dependency_names_from_specs(deps))

    tool = data.get("tool")
    if isinstance(tool, dict):
        poetry = tool.get("poetry")
        if isinstance(poetry, dict):
            names.extend(_poetry_dependency_names(poetry.get("dependencies")))
            groups = poetry.get("group")
            if isinstance(groups, dict):
                for group in groups.values():
                    if isinstance(group, dict):
                        names.extend(_poetry_dependency_names(group.get("dependencies")))

    return sorted(set(names))


def _fallback_pyproject_dependencies(text: str) -> list[str]:
    """Extract common dependency declarations without a TOML parser."""
    lines = [line.split("#", 1)[0].rstrip() for line in text.splitlines()]
    names: list[str] = []
    section = ""
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            index += 1
            continue
        if section == "project" and stripped.startswith("dependencies"):
            specs, next_index = _string_array_from_lines(lines, index)
            names.extend(_dependency_names_from_specs(specs))
            index = next_index
            continue
        if (section.startswith("project.optional-dependencies") or section == "dependency-groups") and "=" in stripped:
            specs, next_index = _string_array_from_lines(lines, index)
            names.extend(_dependency_names_from_specs(specs))
            index = next_index
            continue
        if (
            section == "tool.poetry.dependencies"
            or (section.startswith("tool.poetry.group.") and section.endswith(".dependencies"))
        ) and "=" in stripped:
            name = stripped.split("=", 1)[0].strip().strip("'\"")
            if name and name != "python":
                names.append(name)
        index += 1
    return sorted(set(names))


def _parse_pyproject_dependencies(path: Path) -> list[str]:
    """Parse dependency names from pyproject.toml."""
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    module = _load_toml_module()
    if module is not None:
        loads = getattr(module, "loads", None)
        if callable(loads):
            try:
                return _dependencies_from_pyproject_data(loads(text))
            except ValueError:
                pass
    return _fallback_pyproject_dependencies(text)


def _detect_dependencies(repo_dir: Path) -> list[str]:
    """Detect dependency names across Python and Node package manifests."""
    names: set[str] = set()
    for path in _requirements_paths(repo_dir):
        names.update(_parse_requirements_file(path))
    names.update(_parse_pyproject_dependencies(repo_dir / "pyproject.toml"))
    names.update(_collect_package_json_deps(repo_dir).keys())
    return sorted(names)


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


def _iter_code_files(repo_dir: Path, suffixes: set[str]) -> list[Path]:
    """Return code files matching suffixes for convention detection."""
    paths: list[Path] = []
    try:
        for path in repo_dir.rglob("*"):
            if not path.is_file():
                continue
            if _should_skip_nested_scan(repo_dir, path):
                continue
            if path.suffix.lower() not in suffixes:
                continue
            paths.append(path)
    except OSError:
        return []
    return sorted(paths, key=lambda item: str(item.relative_to(repo_dir)))


def _naming_style(stem: str) -> str | None:
    """Classify a file stem into a naming convention bucket."""
    if not stem or stem.startswith("__"):
        return None
    if "-" in stem and stem.lower() == stem:
        return "kebab-case"
    if "_" in stem and stem.lower() == stem:
        return "snake_case"
    if stem[0].isupper() and "-" not in stem and "_" not in stem:
        return "PascalCase"
    if stem[0].islower() and any(char.isupper() for char in stem[1:]) and "-" not in stem and "_" not in stem:
        return "camelCase"
    return None


def _language_suffixes(primary_language: str) -> set[str]:
    """Collect file suffixes associated with the repo's primary language."""
    return {suffix for suffix, language in LANGUAGE_EXTENSIONS.items() if language == primary_language}


def _detect_naming_convention(repo_dir: Path, primary_language: str) -> str | None:
    """Infer the dominant file naming convention for the primary language."""
    suffixes = _language_suffixes(primary_language)
    if not suffixes:
        return None
    counts: dict[str, int] = {}
    for path in _iter_code_files(repo_dir, suffixes):
        style = _naming_style(path.stem)
        if style is not None:
            counts[style] = counts.get(style, 0) + 1
    if not counts:
        return None
    dominant = max(counts, key=lambda key: counts[key])
    return f"Naming: {dominant} filenames"


def _javascript_import_target(line: str) -> str | None:
    """Extract the quoted import target from a JS/TS import line."""
    if not line.startswith("import "):
        return None
    fragment = line
    if " from " in line:
        fragment = line.split(" from ", 1)[1].strip()
    for quote in ('"', "'"):
        start = fragment.find(quote)
        if start == -1:
            continue
        end = fragment.find(quote, start + 1)
        if end == -1:
            continue
        return fragment[start + 1 : end]
    return None


def _detect_import_style(repo_dir: Path, primary_language: str) -> str | None:
    """Infer the dominant import style for the primary language."""
    if primary_language == "Python":
        relative = 0
        absolute = 0
        for path in _iter_code_files(repo_dir, {".py"}):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("from ."):
                    relative += 1
                elif stripped.startswith("from ") or stripped.startswith("import "):
                    absolute += 1
        if relative > absolute and relative > 0:
            return "Imports: mostly relative"
        if absolute > 0:
            return "Imports: mostly absolute"
        return None

    if primary_language in {"JavaScript", "TypeScript"}:
        relative = 0
        aliased = 0
        for path in _iter_code_files(repo_dir, {".js", ".jsx", ".ts", ".tsx"}):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                target = _javascript_import_target(line.strip())
                if target is None:
                    continue
                if target.startswith(("./", "../")):
                    relative += 1
                elif target.startswith(("@/", "~/", "$lib/")):
                    aliased += 1
        if aliased >= relative and aliased > 0:
            return "Imports: path aliases"
        if relative > 0:
            return "Imports: mostly relative"
    return None


def _detect_conventions(repo_dir: Path, primary_language: str) -> list[str]:
    """Detect high-level naming and import conventions for the repo."""
    conventions: list[str] = []
    naming = _detect_naming_convention(repo_dir, primary_language)
    if naming is not None:
        conventions.append(naming)
    imports = _detect_import_style(repo_dir, primary_language)
    if imports is not None:
        conventions.append(imports)
    return conventions


def _infer_test_runner(repo_dir: Path) -> str | None:
    """Infer the test runner command for the repo."""
    # Build a minimal config just for verify command inference.
    # Deep-copy DEFAULT_CONFIG so new keys added in the future don't require
    # updating this function.
    config: NightshiftConfig = copy.deepcopy(DEFAULT_CONFIG)
    return infer_verify_command(repo_dir, config)


def profile_repo(repo_dir: Path) -> RepoProfile:
    """Build a comprehensive profile of the target repository.

    This is the foundation for Loop 2. Sub-agents receive this profile
    so they know the stack, conventions, and structure of the repo
    they're modifying.
    """
    languages = _count_languages(repo_dir)
    primary_language = _primary_language(languages)
    return RepoProfile(
        languages=languages,
        primary_language=primary_language,
        frameworks=_detect_frameworks(repo_dir),
        dependencies=_detect_dependencies(repo_dir),
        conventions=_detect_conventions(repo_dir, primary_language),
        package_manager=infer_package_manager(repo_dir),
        test_runner=_infer_test_runner(repo_dir),
        instruction_files=_find_instruction_files(repo_dir),
        top_level_dirs=_list_top_level_dirs(repo_dir),
        has_monorepo_markers=_has_monorepo_markers(repo_dir),
        total_files=_count_total_files(repo_dir),
    )
