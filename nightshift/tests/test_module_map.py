from __future__ import annotations

from pathlib import Path

import nightshift


def _run_git(repo: Path, *args: str) -> str:
    return nightshift.git(repo, *args)


def _commit_all(repo: Path, message: str) -> None:
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-m", message)


def _write_module(repo: Path, name: str, content: str) -> None:
    path = repo / "nightshift" / name
    path.write_text(content, encoding="utf-8")


def _make_session_index(repo: Path, row_count: int) -> None:
    """Write a minimal session index with *row_count* real session rows."""
    index_dir = repo / ".recursive" / "sessions"
    index_dir.mkdir(parents=True, exist_ok=True)
    header = (
        "# Session Index\n\n"
        "| Timestamp        | Session         | Role    | Exit | Duration | Cost    | Status  | Feature | PR |\n"
        "| ---------------- | --------------- | ------- | ---- | -------- | ------- | ------- | ------- | -- |\n"
    )
    rows = "".join(
        f"| 2026-04-{i + 1:02d} 00:00 | 2026040{i + 1}-000000 | build   | 0    | 10m      | $1.00   | success | -       | - |\n"
        for i in range(row_count)
    )
    (index_dir / "index.md").write_text(header + rows, encoding="utf-8")


def _init_module_repo(tmp_path: Path) -> Path:
    repo = tmp_path
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test User")

    (repo / "nightshift").mkdir()
    # Create the session index (monotonic source) with 3 completed sessions so
    # the expected label is #0004 (same value the old handoff-counting logic
    # would have produced with 3 numbered handoff files).
    _make_session_index(repo, row_count=3)
    # Also create numbered handoff files so the fallback path is exercisable.
    (repo / ".recursive" / "handoffs").mkdir(parents=True, exist_ok=True)
    for number in ("0001", "0002", "0003"):
        (repo / ".recursive" / "handoffs" / f"{number}.md").write_text(f"# Handoff #{number}\n", encoding="utf-8")

    _write_module(
        repo,
        "types.py",
        '"""Shared types."""\n\nclass Config:\n    pass\n',
    )
    _write_module(
        repo,
        "constants.py",
        '"""Configuration defaults."""\n\nfrom nightshift.types import Config\n\nDEFAULT_CONFIG = {"enabled": True}\n',
    )
    _write_module(
        repo,
        "cycle.py",
        '"""Cycle orchestration."""\n\nfrom nightshift.constants import DEFAULT_CONFIG\n\n\ndef run_cycle() -> dict[str, bool]:\n    return DEFAULT_CONFIG\n',
    )
    _write_module(
        repo,
        "__init__.py",
        '"""Package exports."""\n\nfrom nightshift.cycle import run_cycle\n\n__all__ = ["run_cycle"]\n',
    )

    _commit_all(repo, "init")
    return repo


class TestModuleMap:
    def test_generate_module_map_collects_dependency_order_and_recent_changes(self, tmp_path: Path) -> None:
        repo = _init_module_repo(tmp_path)
        default_branch = _run_git(repo, "branch", "--show-current")

        _run_git(repo, "checkout", "-b", "feat/pr12")
        _write_module(
            repo,
            "cycle.py",
            '"""Cycle orchestration."""\n\nfrom nightshift.constants import DEFAULT_CONFIG\n\n\ndef run_cycle() -> dict[str, bool]:\n    return DEFAULT_CONFIG\n\n\ndef run_once() -> dict[str, bool]:\n    return run_cycle()\n',
        )
        _commit_all(repo, "feat: add cycle runner")
        _run_git(repo, "checkout", default_branch)
        _run_git(repo, "merge", "--no-ff", "feat/pr12", "-m", "Merge pull request #12 from example/feat/pr12")

        snapshot = nightshift.generate_module_map(repo)
        rendered = nightshift.render_module_map(snapshot)

        assert snapshot["session_label"] == "#0004"
        assert snapshot["dependency_order"] == ["types", "constants", "cycle"]

        modules = {entry["module"]: entry for entry in snapshot["modules"]}
        assert modules["types.py"]["purpose"] == "Shared types."
        assert modules["constants.py"]["key_symbols"] == ["DEFAULT_CONFIG"]
        assert modules["cycle.py"]["last_changed"].startswith("PR #12 (")

        assert "## Recent Shipped Sessions" in rendered
        assert "PR #12: feat: add cycle runner" in rendered
        assert "`types -> constants -> cycle`" in rendered

    def test_module_map_cli_write_creates_expected_file(self, tmp_path: Path) -> None:
        repo = _init_module_repo(tmp_path)

        parser = nightshift.build_parser()
        args = parser.parse_args(["module-map", "--repo-dir", str(repo), "--write"])
        result = args.func(args)

        output_path = repo / ".recursive" / "architecture" / "MODULE_MAP.md"
        content = output_path.read_text(encoding="utf-8")

        assert result == 0
        assert args.command == "module-map"
        assert output_path.exists()
        assert "## Modules (4)" in content
        assert "| `cycle.py` |" in content

    def test_generate_module_map_skips_symlinked_python_files(self, tmp_path: Path) -> None:
        repo = _init_module_repo(tmp_path)
        outside = tmp_path / "outside.py"
        outside.write_text('"""Outside."""\n', encoding="utf-8")
        (repo / "nightshift" / "escape.py").symlink_to(outside)

        snapshot = nightshift.generate_module_map(repo)

        modules = {entry["module"] for entry in snapshot["modules"]}
        assert "escape.py" not in modules
        assert snapshot["module_count"] == 4

    def test_generate_module_map_survives_per_file_syntax_error(self, tmp_path: Path) -> None:
        repo = _init_module_repo(tmp_path)
        _write_module(repo, "broken.py", "def bad_syntax(\n")

        snapshot = nightshift.generate_module_map(repo)

        module_names = {entry["module"] for entry in snapshot["modules"]}
        assert "broken.py" not in module_names
        assert snapshot["module_count"] == 5
        assert len(snapshot["parse_errors"]) == 1
        assert snapshot["parse_errors"][0]["module"] == "broken.py"
        assert snapshot["parse_errors"][0]["error"] != ""

    def test_generate_module_map_no_parse_errors_when_all_valid(self, tmp_path: Path) -> None:
        repo = _init_module_repo(tmp_path)

        snapshot = nightshift.generate_module_map(repo)

        assert snapshot["parse_errors"] == []

    def test_render_module_map_includes_parse_errors_section(self, tmp_path: Path) -> None:
        repo = _init_module_repo(tmp_path)
        _write_module(repo, "broken.py", "def bad_syntax(\n")

        snapshot = nightshift.generate_module_map(repo)
        rendered = nightshift.render_module_map(snapshot)

        assert "## Parse Errors" in rendered
        assert "`broken.py`" in rendered

    def test_render_module_map_omits_parse_errors_section_when_clean(self, tmp_path: Path) -> None:
        repo = _init_module_repo(tmp_path)

        snapshot = nightshift.generate_module_map(repo)
        rendered = nightshift.render_module_map(snapshot)

        assert "## Parse Errors" not in rendered

    def test_generate_module_map_survives_invalid_utf8(self, tmp_path: Path) -> None:
        repo = _init_module_repo(tmp_path)
        bad_path = repo / "nightshift" / "corrupt.py"
        bad_path.write_bytes(b"\xff\xfe\x00")

        snapshot = nightshift.generate_module_map(repo)

        module_names = {entry["module"] for entry in snapshot["modules"]}
        assert "corrupt.py" not in module_names
        assert snapshot["module_count"] == 5
        assert len(snapshot["parse_errors"]) == 1
        assert snapshot["parse_errors"][0]["module"] == "corrupt.py"
        assert snapshot["parse_errors"][0]["error"] != ""

    def test_module_map_cli_write_succeeds_with_syntax_error(self, tmp_path: Path) -> None:
        repo = _init_module_repo(tmp_path)
        _write_module(repo, "broken.py", "class Bad(\n")

        parser = nightshift.build_parser()
        args = parser.parse_args(["module-map", "--repo-dir", str(repo), "--write"])
        result = args.func(args)

        assert result == 0
        output_path = repo / ".recursive" / "architecture" / "MODULE_MAP.md"
        content = output_path.read_text(encoding="utf-8")
        assert "## Parse Errors" in content
        assert "`broken.py`" in content

    def test_dependency_order_no_cycles_returns_empty_cycle_list(self, tmp_path: Path) -> None:
        repo = _init_module_repo(tmp_path)

        snapshot = nightshift.generate_module_map(repo)

        assert snapshot["dependency_cycles"] == []
        assert snapshot["dependency_order"] == ["types", "constants", "cycle"]

    def test_dependency_order_cycle_is_reported_in_snapshot(self, tmp_path: Path) -> None:
        """A package where alpha imports beta and beta imports alpha must surface as a cycle."""
        repo = _init_module_repo(tmp_path)
        _write_module(
            repo,
            "alpha.py",
            '"""Alpha module."""\n\nfrom nightshift.beta import something\n',
        )
        _write_module(
            repo,
            "beta.py",
            '"""Beta module."""\n\nfrom nightshift.alpha import other\n',
        )

        snapshot = nightshift.generate_module_map(repo)

        assert "alpha" in snapshot["dependency_cycles"]
        assert "beta" in snapshot["dependency_cycles"]
        assert sorted(snapshot["dependency_cycles"]) == ["alpha", "beta"]

    def test_dependency_order_cycle_fallback_is_alphabetical(self, tmp_path: Path) -> None:
        """Cycle members must be appended in deterministic alphabetical order."""
        repo = _init_module_repo(tmp_path)
        _write_module(
            repo,
            "zeta.py",
            '"""Zeta module."""\n\nfrom nightshift.omega import x\n',
        )
        _write_module(
            repo,
            "omega.py",
            '"""Omega module."""\n\nfrom nightshift.zeta import y\n',
        )

        snapshot = nightshift.generate_module_map(repo)

        cycle_positions = [snapshot["dependency_order"].index(m) for m in ["omega", "zeta"]]
        assert cycle_positions[0] < cycle_positions[1], "omega must appear before zeta (alphabetical)"

    def test_render_module_map_includes_cycle_warning_when_cycle_detected(self, tmp_path: Path) -> None:
        """Rendered markdown must warn the reader when a dependency cycle was detected."""
        repo = _init_module_repo(tmp_path)
        _write_module(
            repo,
            "alpha.py",
            '"""Alpha module."""\n\nfrom nightshift.beta import something\n',
        )
        _write_module(
            repo,
            "beta.py",
            '"""Beta module."""\n\nfrom nightshift.alpha import other\n',
        )

        snapshot = nightshift.generate_module_map(repo)
        rendered = nightshift.render_module_map(snapshot)

        assert "WARNING: dependency cycle detected" in rendered
        assert "`alpha, beta`" in rendered

    def test_render_module_map_omits_cycle_warning_when_no_cycle(self, tmp_path: Path) -> None:
        """Rendered markdown must not mention cycles when the graph is acyclic."""
        repo = _init_module_repo(tmp_path)

        snapshot = nightshift.generate_module_map(repo)
        rendered = nightshift.render_module_map(snapshot)

        assert "WARNING: dependency cycle detected" not in rendered

    def test_render_module_map_includes_dependency_order_legend(self, tmp_path: Path) -> None:
        """Dependency Order section must include a legend explaining arrow direction."""
        repo = _init_module_repo(tmp_path)

        snapshot = nightshift.generate_module_map(repo)
        rendered = nightshift.render_module_map(snapshot)

        assert "A -> B means A must be loaded before B (A is a dependency of B)." in rendered

    def test_module_map_cli_write_includes_cycle_warning_in_file(self, tmp_path: Path) -> None:
        """The written MODULE_MAP.md must include the cycle warning when a cycle exists."""
        repo = _init_module_repo(tmp_path)
        _write_module(
            repo,
            "alpha.py",
            '"""Alpha module."""\n\nfrom nightshift.beta import something\n',
        )
        _write_module(
            repo,
            "beta.py",
            '"""Beta module."""\n\nfrom nightshift.alpha import other\n',
        )

        parser = nightshift.build_parser()
        args = parser.parse_args(["module-map", "--repo-dir", str(repo), "--write"])
        result = args.func(args)

        assert result == 0
        output_path = repo / ".recursive" / "architecture" / "MODULE_MAP.md"
        content = output_path.read_text(encoding="utf-8")
        assert "WARNING: dependency cycle detected" in content

    def test_session_label_uses_session_index_not_handoffs(self, tmp_path: Path) -> None:
        """Session label must come from the session index, not handoff file count."""
        repo = _init_module_repo(tmp_path)
        # The fixture has 3 session rows -> next label is #0004.
        snapshot = nightshift.generate_module_map(repo)
        assert snapshot["session_label"] == "#0004"

    def test_session_label_stable_after_handoff_compaction(self, tmp_path: Path) -> None:
        """Deleting all numbered handoff files must NOT change the session label.

        This is the core regression test: compaction removes older numbered
        handoffs from .recursive/handoffs/ but the session index is untouched.
        The label must stay at the session-index-derived value.
        """
        repo = _init_module_repo(tmp_path)
        # Confirm baseline label from session index (3 rows -> #0004).
        snapshot_before = nightshift.generate_module_map(repo)
        assert snapshot_before["session_label"] == "#0004"

        # Simulate compaction: remove all numbered handoff files.
        for f in (repo / ".recursive" / "handoffs").glob("[0-9][0-9][0-9][0-9].md"):
            f.unlink()

        # Label must remain #0004 because the session index still has 3 rows.
        snapshot_after = nightshift.generate_module_map(repo)
        assert snapshot_after["session_label"] == "#0004"

    def test_session_label_fallback_to_handoffs_when_no_index(self, tmp_path: Path) -> None:
        """When no session index exists, fall back to numbered handoff files."""
        repo = _init_module_repo(tmp_path)
        # Remove the session index entirely.
        (repo / ".recursive" / "sessions" / "index.md").unlink()

        # With 3 numbered handoff files (0001-0003) the fallback gives #0004.
        snapshot = nightshift.generate_module_map(repo)
        assert snapshot["session_label"] == "#0004"

    def test_session_label_fallback_safe_with_no_handoffs_and_no_index(self, tmp_path: Path) -> None:
        """With neither a session index nor any handoff files, label is #0001."""
        repo = _init_module_repo(tmp_path)
        # Remove the session index.
        (repo / ".recursive" / "sessions" / "index.md").unlink()
        # Remove all numbered handoff files.
        for f in (repo / ".recursive" / "handoffs").glob("[0-9][0-9][0-9][0-9].md"):
            f.unlink()

        snapshot = nightshift.generate_module_map(repo)
        assert snapshot["session_label"] == "#0001"

    def test_session_label_ignores_circuit_break_rows(self, tmp_path: Path) -> None:
        """CIRCUIT-BREAK pseudo-rows in the session index must not be counted."""
        repo = _init_module_repo(tmp_path)
        # Overwrite the session index with 2 real rows plus 1 CIRCUIT-BREAK row.
        index_path = repo / ".recursive" / "sessions" / "index.md"
        index_path.write_text(
            "# Session Index\n\n"
            "| Timestamp        | Session         | Role  | Exit | Duration | Cost  | Status  | Feature | PR |\n"
            "| ---------------- | --------------- | ----- | ---- | -------- | ----- | ------- | ------- | -- |\n"
            "| 2026-04-01 00:00 | 20260401-000000 | build | 0    | 10m      | $1.00 | success | -       | - |\n"
            "| 2026-04-02 00:00 | 20260402-000000 | build | 0    | 10m      | $1.00 | success | -       | - |\n"
            "| 2026-04-02 00:30 | CIRCUIT-BREAK   | -     | -    | -        | -     | Stopped after 3 consecutive failures | - | - |\n",
            encoding="utf-8",
        )

        snapshot = nightshift.generate_module_map(repo)
        # 2 real rows -> next label is #0003, not #0004.
        assert snapshot["session_label"] == "#0003"

    def test_subpackage_modules_are_included(self, tmp_path: Path) -> None:
        """Modules in known subpackage dirs (core, owl, etc.) appear in the snapshot."""
        repo = _init_module_repo(tmp_path)
        # Create a core/ subpackage with one module
        core_dir = repo / "nightshift" / "core"
        core_dir.mkdir()
        (core_dir / "__init__.py").write_text('"""Core subpackage."""\n', encoding="utf-8")
        (core_dir / "errors.py").write_text(
            '"""Core error types."""\n\n\nclass NightshiftError(Exception):\n    pass\n',
            encoding="utf-8",
        )
        _commit_all(repo, "add core subpackage")

        snapshot = nightshift.generate_module_map(repo)

        module_names = {entry["module"] for entry in snapshot["modules"]}
        assert "core/errors.py" in module_names
        # __init__.py inside subpackages should be excluded
        assert "core/__init__.py" not in module_names

    def test_subpackage_module_count_includes_subpkg_files(self, tmp_path: Path) -> None:
        """module_count reflects both top-level and subpackage files."""
        repo = _init_module_repo(tmp_path)
        core_dir = repo / "nightshift" / "core"
        core_dir.mkdir()
        (core_dir / "__init__.py").write_text('"""Core."""\n', encoding="utf-8")
        (core_dir / "errors.py").write_text('"""Errors."""\n', encoding="utf-8")
        (core_dir / "types.py").write_text('"""Types."""\n', encoding="utf-8")
        _commit_all(repo, "add core subpackage")

        snapshot = nightshift.generate_module_map(repo)

        # 4 top-level (types, constants, cycle, __init__) + 2 subpackage (errors, types)
        assert snapshot["module_count"] == 6

    def test_subpackage_dependency_order_uses_slash_keys(self, tmp_path: Path) -> None:
        """Dependency order shows subpackage keys like 'core/types' not bare 'types'."""
        repo = _init_module_repo(tmp_path)
        core_dir = repo / "nightshift" / "core"
        core_dir.mkdir()
        (core_dir / "__init__.py").write_text('"""Core."""\n', encoding="utf-8")
        (core_dir / "errors.py").write_text(
            '"""Errors."""\n\n\nclass NightshiftError(Exception):\n    pass\n',
            encoding="utf-8",
        )
        # Add a module that imports from the subpackage
        (repo / "nightshift" / "runner.py").write_text(
            '"""Runner."""\n\nfrom nightshift.core.errors import NightshiftError\n\n\ndef run() -> None:\n    raise NightshiftError\n',
            encoding="utf-8",
        )
        _commit_all(repo, "add subpackage dep")

        snapshot = nightshift.generate_module_map(repo)

        order = snapshot["dependency_order"]
        assert "core/errors" in order
        assert "runner" in order
        # core/errors must come before runner in the dependency order
        assert order.index("core/errors") < order.index("runner")

    def test_subpackage_module_display_uses_relative_path(self, tmp_path: Path) -> None:
        """Module column shows 'core/errors.py' not bare 'errors.py'."""
        repo = _init_module_repo(tmp_path)
        core_dir = repo / "nightshift" / "core"
        core_dir.mkdir()
        (core_dir / "__init__.py").write_text('"""Core."""\n', encoding="utf-8")
        (core_dir / "errors.py").write_text(
            '"""Core error types."""\n\n\nclass Err(Exception):\n    pass\n',
            encoding="utf-8",
        )
        _commit_all(repo, "add core/errors")

        snapshot = nightshift.generate_module_map(repo)
        rendered = nightshift.render_module_map(snapshot)

        assert "| `core/errors.py` |" in rendered
        # Should not appear as bare errors.py
        assert "| `errors.py` |" not in rendered

    def test_tests_subpackage_is_not_scanned(self, tmp_path: Path) -> None:
        """Files in nightshift/tests/ are not included in the module map."""
        repo = _init_module_repo(tmp_path)
        tests_dir = repo / "nightshift" / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text('"""Tests."""\n', encoding="utf-8")
        (tests_dir / "test_foo.py").write_text(
            '"""Tests for foo."""\n\n\ndef test_something() -> None:\n    pass\n',
            encoding="utf-8",
        )
        _commit_all(repo, "add tests dir")

        snapshot = nightshift.generate_module_map(repo)

        module_names = {entry["module"] for entry in snapshot["modules"]}
        assert "tests/test_foo.py" not in module_names
        assert "tests/__init__.py" not in module_names
