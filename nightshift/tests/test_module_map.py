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


def _init_module_repo(tmp_path: Path) -> Path:
    repo = tmp_path
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test User")

    (repo / "nightshift").mkdir()
    (repo / "docs" / "handoffs").mkdir(parents=True)
    for number in ("0001", "0002", "0003"):
        (repo / "docs" / "handoffs" / f"{number}.md").write_text(f"# Handoff #{number}\n", encoding="utf-8")

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
