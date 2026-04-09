"""Generate a persistent module map for fast cross-session orientation."""

from __future__ import annotations

import ast
import datetime as dt
import re
from pathlib import Path

from nightshift.core.constants import MODULE_MAP_PATH, MODULE_MAP_STALE_AFTER_SESSIONS
from nightshift.core.shell import git
from nightshift.core.types import ModuleMapEntry, ModuleMapSnapshot, ParseError, RecentSessionChange


def module_map_path(repo_dir: Path) -> Path:
    """Return the canonical output path for the persistent module map."""
    return repo_dir / MODULE_MAP_PATH


def _parse_modules(
    module_paths: list[Path],
) -> tuple[dict[str, ast.Module], list[ParseError]]:
    """Attempt to parse each module file, recording per-file syntax errors."""
    parsed: dict[str, ast.Module] = {}
    errors: list[ParseError] = []
    for path in module_paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            errors.append(ParseError(module=path.name, error=str(exc)))
            continue
        parsed[path.stem] = tree
    return parsed, errors


def generate_module_map(repo_dir: Path) -> ModuleMapSnapshot:
    """Collect module metadata, dependency order, and recent-session summaries."""
    package_dir = repo_dir / "nightshift"
    module_paths = _module_paths(package_dir)
    parsed, parse_errors = _parse_modules(module_paths)
    dependency_order = _dependency_order(parsed)

    ordered_names = [*dependency_order]
    if "__init__" in parsed:
        ordered_names.append("__init__")
    for name in sorted(parsed):
        if name not in ordered_names:
            ordered_names.append(name)

    modules = [
        _module_entry(repo_dir, package_dir / f"{name}.py", parsed[name])
        for name in ordered_names
        if (package_dir / f"{name}.py").exists()
    ]
    return ModuleMapSnapshot(
        generated_on=dt.date.today().isoformat(),
        session_label=_next_session_label(repo_dir),
        stale_after_sessions=MODULE_MAP_STALE_AFTER_SESSIONS,
        module_count=len(module_paths),
        modules=modules,
        dependency_order=dependency_order,
        recent_changes=_recent_session_changes(repo_dir),
        parse_errors=parse_errors,
    )


def render_module_map(snapshot: ModuleMapSnapshot) -> str:
    """Render *snapshot* as markdown for .recursive/architecture/MODULE_MAP.md."""
    lines = [
        "# Module Map",
        "",
        f"Last updated: {snapshot['generated_on']} by session {snapshot['session_label']}",
        "Generated via: `python3 -m nightshift module-map --write`",
        f"Stale after: {snapshot['stale_after_sessions']} newer sessions without a refresh",
        "",
        "This file is generated from the current `nightshift/*.py` sources plus git history.",
        "Read it before opening modules one by one when you need fast orientation.",
        "",
        f"## Modules ({snapshot['module_count']})",
        "",
        "| Module | Lines | Purpose | Key symbols | Last changed |",
        "|---|---:|---|---|---|",
    ]
    for module in snapshot["modules"]:
        purpose = _escape_table_cell(module["purpose"])
        key_symbols = ", ".join(f"`{symbol}`" for symbol in module["key_symbols"]) or "-"
        lines.append(
            f"| `{module['module']}` | {module['lines']} | {purpose} | {key_symbols} | {module['last_changed']} |"
        )

    lines.extend(
        [
            "",
            "## Dependency Order",
            "",
            "Topological order derived from internal `nightshift.*` imports.",
            "`__init__.py` is excluded because it re-exports the package surface.",
            "",
            f"`{' -> '.join(snapshot['dependency_order'])}`",
            "",
            "## Recent Shipped Sessions",
            "",
        ]
    )
    if snapshot["recent_changes"]:
        for change in snapshot["recent_changes"]:
            lines.append(f"- {change['reference']}: {change['summary']}")
    else:
        lines.append("- No merged sessions recorded yet.")

    if snapshot["parse_errors"]:
        lines.extend(["", "## Parse Errors", ""])
        lines.append("The following modules could not be parsed due to syntax errors:")
        lines.append("")
        for err in snapshot["parse_errors"]:
            lines.append(f"- `{err['module']}`: {err['error']}")

    return "\n".join(lines) + "\n"


def write_module_map(repo_dir: Path, *, snapshot: ModuleMapSnapshot | None = None) -> Path:
    """Write the module map to .recursive/architecture/MODULE_MAP.md and return the path."""
    target = module_map_path(repo_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    resolved = snapshot if snapshot is not None else generate_module_map(repo_dir)
    target.write_text(render_module_map(resolved), encoding="utf-8")
    return target


def _module_entry(repo_dir: Path, path: Path, tree: ast.Module) -> ModuleMapEntry:
    """Build a single module-map row from an AST and git metadata."""
    return ModuleMapEntry(
        module=path.name,
        lines=len(path.read_text(encoding="utf-8").splitlines()),
        purpose=_module_purpose(tree, path),
        key_symbols=_key_symbols(tree),
        last_changed=_last_changed_label(repo_dir, path),
    )


def _module_paths(package_dir: Path) -> list[Path]:
    """Return safe top-level package modules, excluding symlinks and escaped paths."""
    resolved_dir = package_dir.resolve()
    paths: list[Path] = []
    for path in sorted(package_dir.glob("*.py")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            resolved_path = path.resolve(strict=True)
        except OSError:
            continue
        if resolved_path.parent != resolved_dir:
            continue
        paths.append(path)
    return paths


def _module_purpose(tree: ast.Module, path: Path) -> str:
    """Return the first non-empty module-docstring line, or a fallback."""
    docstring = ast.get_docstring(tree)
    if docstring:
        for line in docstring.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
    return f"Module `{path.stem}`."


def _key_symbols(tree: ast.Module) -> list[str]:
    """Return a small list of top-level symbols that help orient a new reader."""
    exported = _exported_symbols(tree)
    if exported:
        return exported[:4]

    public_defs: list[str] = []
    imported_entrypoints: list[str] = []
    constants: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                public_defs.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    constants.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.isupper():
                constants.append(node.target.id)
        elif isinstance(node, ast.ImportFrom) and node.module == "nightshift.cli":
            for alias in node.names:
                if not alias.name.startswith("_"):
                    imported_entrypoints.append(alias.asname or alias.name)

    ordered = _dedupe([*public_defs, *imported_entrypoints, *constants])
    return ordered[:4] if ordered else ["(entrypoint only)"]


def _exported_symbols(tree: ast.Module) -> list[str]:
    """Extract __all__ entries when a module uses explicit package exports."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    return _string_literals(node.value)
    return []


def _string_literals(node: ast.AST) -> list[str]:
    """Extract string literals from a simple list/tuple assignment."""
    if isinstance(node, (ast.List, ast.Tuple)):
        values: list[str] = []
        for item in node.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                values.append(item.value)
        return values
    return []


def _dependency_order(parsed_modules: dict[str, ast.Module]) -> list[str]:
    """Topologically sort internal module dependencies, leaving __init__ out."""
    pending: dict[str, set[str]] = {}
    for name, tree in parsed_modules.items():
        if name == "__init__":
            continue
        pending[name] = set(_internal_dependencies(tree)) - {name, "__init__"}

    order: list[str] = []
    while pending:
        ready = sorted(name for name, deps in pending.items() if not deps)
        if not ready:
            order.extend(sorted(pending))
            break
        order.extend(ready)
        for name in ready:
            pending.pop(name)
        for deps in pending.values():
            deps.difference_update(ready)
    return order


def _internal_dependencies(tree: ast.Module) -> list[str]:
    """Return direct internal imports from `nightshift.<module>` references."""
    deps: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("nightshift."):
            deps.append(node.module.split(".", 1)[1].split(".", 1)[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("nightshift."):
                    deps.append(alias.name.split(".", 1)[1].split(".", 1)[0])
    return _dedupe(deps)


def _last_changed_label(repo_dir: Path, path: Path) -> str:
    """Return a concise PR/commit label for the last change to *path*."""
    status = _git_output(repo_dir, "status", "--short", "--", str(path))
    if status:
        return f"session {_next_session_label(repo_dir)}"

    merge = _git_output(repo_dir, "log", "--merges", "--first-parent", "-1", "--format=%h\t%s", "--", str(path))
    if merge:
        hash_part, subject = _split_tabbed_line(merge)
        match = re.search(r"#(\d+)", subject)
        if match:
            return f"PR #{match.group(1)} ({hash_part})"
        return hash_part

    commit = _git_output(repo_dir, "log", "-1", "--format=%h", "--", str(path))
    return commit or f"session {_next_session_label(repo_dir)}"


def _recent_session_changes(repo_dir: Path) -> list[RecentSessionChange]:
    """Summarize the last five merged builder sessions from first-parent history."""
    merge_lines = _git_output(repo_dir, "log", "--merges", "--first-parent", "-5", "--format=%h\t%s").splitlines()
    changes: list[RecentSessionChange] = []
    for line in merge_lines:
        if not line.strip():
            continue
        hash_part, subject = _split_tabbed_line(line)
        branch_tip_subject = _git_output(repo_dir, "log", "-1", "--format=%s", f"{hash_part}^2")
        match = re.search(r"#(\d+)", subject)
        reference = f"PR #{match.group(1)}" if match else hash_part
        summary = branch_tip_subject or subject
        changes.append(RecentSessionChange(reference=reference, summary=summary))
    return changes


def _next_session_label(repo_dir: Path) -> str:
    """Infer the current session's handoff number from existing numbered handoffs."""
    handoff_dir = repo_dir / "docs" / "handoffs"
    numbers = [int(path.stem) for path in handoff_dir.glob("[0-9][0-9][0-9][0-9].md")]
    next_number = max(numbers, default=0) + 1
    return f"#{next_number:04d}"


def _git_output(repo_dir: Path, *args: str) -> str:
    """Run a git command and return stripped stdout, tolerating missing history."""
    return git(repo_dir, *args, check=False)


def _split_tabbed_line(line: str) -> tuple[str, str]:
    """Split a git log line that uses a tab separator."""
    if "\t" not in line:
        return line, ""
    left, right = line.split("\t", 1)
    return left, right


def _dedupe(items: list[str]) -> list[str]:
    """Preserve order while removing duplicates and blank strings."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _escape_table_cell(value: str) -> str:
    """Avoid breaking markdown tables with raw pipe characters."""
    return value.replace("|", "\\|")
