"""Tests for nightshift.infra.release -- auto-release version tagging."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import nightshift
from nightshift.infra.release import (
    _all_tasks_done,
    _create_github_release,
    _extract_tag,
    _is_already_released,
    _list_versions,
    _read_changelog,
    _tasks_for_version,
    _version_ready,
    check_and_release,
    find_releasable_version,
)

# --- Fixtures and helpers ----------------------------------------------------


def _make_changelog(
    tmp_path: Path,
    version: str,
    status: str = "In progress",
    tag: str | None = None,
) -> Path:
    """Write a minimal changelog file and return the directory."""
    changelog_dir = tmp_path / ".recursive" / "changelog"
    changelog_dir.mkdir(parents=True, exist_ok=True)

    effective_tag = tag or version
    content = (
        f"# {version} -- Test Release\n\n"
        f"**Released**: TBD\n"
        f"**Tag**: `{effective_tag}`\n"
        f"**Status**: {status}\n\n"
        "## Added\n\n- something\n"
    )
    (changelog_dir / f"{version}.md").write_text(content, encoding="utf-8")
    return changelog_dir


def _make_task(
    tmp_path: Path,
    number: str,
    target_version: str,
    status: str = "pending",
) -> Path:
    """Write a minimal task file and return the tasks directory."""
    tasks_dir = tmp_path / ".recursive" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    content = (
        f"---\n"
        f"status: {status}\n"
        f"priority: normal\n"
        f"target: {target_version}\n"
        f"created: 2026-01-01\n"
        f"completed:\n"
        f"---\n\n"
        f"# Task {number}\n"
    )
    (tasks_dir / f"{number}.md").write_text(content, encoding="utf-8")
    return tasks_dir


# --- _list_versions -----------------------------------------------------------


class TestListVersions:
    def test_returns_sorted_versions(self, tmp_path: Path) -> None:
        changelog_dir = tmp_path / "changelog"
        changelog_dir.mkdir()
        for v in ("v0.0.3", "v0.0.1", "v0.0.2"):
            (changelog_dir / f"{v}.md").write_text("# release\n", encoding="utf-8")
        result = _list_versions(changelog_dir)
        assert result == ["v0.0.1", "v0.0.2", "v0.0.3"]

    def test_ignores_non_version_files(self, tmp_path: Path) -> None:
        changelog_dir = tmp_path / "changelog"
        changelog_dir.mkdir()
        (changelog_dir / "README.md").write_text("# readme\n", encoding="utf-8")
        (changelog_dir / "v0.0.1.md").write_text("# release\n", encoding="utf-8")
        result = _list_versions(changelog_dir)
        assert result == ["v0.0.1"]

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        changelog_dir = tmp_path / "changelog"
        changelog_dir.mkdir()
        assert _list_versions(changelog_dir) == []

    def test_numeric_sort_v0_0_9_before_v0_0_10(self, tmp_path: Path) -> None:
        """v0.0.10 must sort after v0.0.9 (numeric, not lexicographic)."""
        changelog_dir = tmp_path / "changelog"
        changelog_dir.mkdir()
        for v in ("v0.0.10", "v0.0.9"):
            (changelog_dir / f"{v}.md").write_text("# release\n", encoding="utf-8")
        result = _list_versions(changelog_dir)
        assert result.index("v0.0.9") < result.index("v0.0.10")


# --- _read_changelog ---------------------------------------------------------


class TestReadChangelog:
    def test_reads_existing_changelog(self, tmp_path: Path) -> None:
        d = _make_changelog(tmp_path, "v0.0.1")
        content = _read_changelog(d, "v0.0.1")
        assert "v0.0.1" in content

    def test_raises_when_missing(self, tmp_path: Path) -> None:
        d = _make_changelog(tmp_path, "v0.0.1")
        with pytest.raises(nightshift.NightshiftError, match="Changelog not found"):
            _read_changelog(d, "v0.0.99")


# --- _is_already_released ---------------------------------------------------


class TestIsAlreadyReleased:
    def test_returns_true_for_released_status(self) -> None:
        content = "**Status**: Released\n"
        assert _is_already_released(content) is True

    def test_returns_false_for_in_progress(self) -> None:
        content = "**Status**: In progress\n"
        assert _is_already_released(content) is False

    def test_returns_false_when_no_status_line(self) -> None:
        content = "# changelog\nsome content\n"
        assert _is_already_released(content) is False

    def test_handles_trailing_whitespace(self) -> None:
        content = "**Status**: Released   \n"
        assert _is_already_released(content) is True


# --- _extract_tag -----------------------------------------------------------


class TestExtractTag:
    def test_extracts_tag_from_header(self) -> None:
        content = "**Tag**: `v0.0.8`\n"
        assert _extract_tag(content, "v0.0.8") == "v0.0.8"

    def test_fallback_to_version_when_no_tag_line(self) -> None:
        content = "# changelog\nno tag here\n"
        assert _extract_tag(content, "v0.0.8") == "v0.0.8"

    def test_extracts_custom_tag(self) -> None:
        content = "**Tag**: `release-2026`\n"
        assert _extract_tag(content, "v0.0.1") == "release-2026"


# --- _tasks_for_version -----------------------------------------------------


class TestTasksForVersion:
    def test_returns_tasks_matching_version(self, tmp_path: Path) -> None:
        tasks_dir = _make_task(tmp_path, "0001", "v0.0.8", "done")
        _make_task(tmp_path, "0002", "v0.0.7", "done")
        result = _tasks_for_version(tasks_dir, "v0.0.8")
        assert len(result) == 1
        assert result[0].name == "0001.md"

    def test_returns_empty_when_no_matches(self, tmp_path: Path) -> None:
        tasks_dir = _make_task(tmp_path, "0001", "v0.0.7", "done")
        result = _tasks_for_version(tasks_dir, "v0.0.8")
        assert result == []

    def test_returns_empty_when_tasks_dir_missing(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "tasks"
        result = _tasks_for_version(nonexistent, "v0.0.8")
        assert result == []

    def test_ignores_non_task_files(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / ".recursive" / "tasks"
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "GUIDE.md").write_text(
            "---\nstatus: pending\ntarget: v0.0.8\n---\n# guide\n",
            encoding="utf-8",
        )
        result = _tasks_for_version(tasks_dir, "v0.0.8")
        assert result == []


# --- _all_tasks_done --------------------------------------------------------


class TestAllTasksDone:
    def test_returns_true_when_all_done(self, tmp_path: Path) -> None:
        tasks_dir = _make_task(tmp_path, "0001", "v0.0.8", "done")
        _make_task(tmp_path, "0002", "v0.0.8", "done")
        task_files = list(tasks_dir.glob("[0-9]*.md"))
        all_done, pending = _all_tasks_done(task_files)
        assert all_done is True
        assert pending == []

    def test_returns_false_when_some_pending(self, tmp_path: Path) -> None:
        tasks_dir = _make_task(tmp_path, "0001", "v0.0.8", "done")
        _make_task(tmp_path, "0002", "v0.0.8", "pending")
        task_files = list(tasks_dir.glob("[0-9]*.md"))
        all_done, pending = _all_tasks_done(task_files)
        assert all_done is False
        assert "0002" in pending

    def test_returns_false_for_in_progress(self, tmp_path: Path) -> None:
        tasks_dir = _make_task(tmp_path, "0001", "v0.0.8", "in-progress")
        task_files = list(tasks_dir.glob("[0-9]*.md"))
        all_done, pending = _all_tasks_done(task_files)
        assert all_done is False
        assert "0001" in pending

    def test_empty_file_list_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="requires at least one task file"):
            _all_tasks_done([])


# --- _version_ready ---------------------------------------------------------


class TestVersionReady:
    def test_ready_when_all_tasks_done(self, tmp_path: Path) -> None:
        changelog_dir = _make_changelog(tmp_path, "v0.0.8", status="In progress")
        tasks_dir = _make_task(tmp_path, "0001", "v0.0.8", "done")
        ready, tag, reason = _version_ready(changelog_dir, tasks_dir, "v0.0.8")
        assert ready is True
        assert tag == "v0.0.8"
        assert "done" in reason

    def test_not_ready_when_already_released(self, tmp_path: Path) -> None:
        changelog_dir = _make_changelog(tmp_path, "v0.0.7", status="Released")
        tasks_dir = _make_task(tmp_path, "0001", "v0.0.7", "done")
        ready, _tag, reason = _version_ready(changelog_dir, tasks_dir, "v0.0.7")
        assert ready is False
        assert "already released" in reason

    def test_not_ready_when_tasks_pending(self, tmp_path: Path) -> None:
        changelog_dir = _make_changelog(tmp_path, "v0.0.8", status="In progress")
        tasks_dir = _make_task(tmp_path, "0001", "v0.0.8", "pending")
        ready, _tag, reason = _version_ready(changelog_dir, tasks_dir, "v0.0.8")
        assert ready is False
        assert "not done" in reason

    def test_not_ready_when_no_tasks(self, tmp_path: Path) -> None:
        changelog_dir = _make_changelog(tmp_path, "v0.0.8", status="In progress")
        tasks_dir = tmp_path / ".recursive" / "tasks"
        tasks_dir.mkdir(parents=True)
        ready, _tag, reason = _version_ready(changelog_dir, tasks_dir, "v0.0.8")
        assert ready is False
        assert "No tasks found" in reason

    def test_not_ready_when_changelog_missing(self, tmp_path: Path) -> None:
        changelog_dir = tmp_path / ".recursive" / "changelog"
        changelog_dir.mkdir(parents=True)
        tasks_dir = tmp_path / ".recursive" / "tasks"
        tasks_dir.mkdir(parents=True)
        ready, _tag, reason = _version_ready(changelog_dir, tasks_dir, "v0.0.99")
        assert ready is False
        assert "not found" in reason.lower()

    def test_raises_when_tag_is_shell_flag(self, tmp_path: Path) -> None:
        """A tag of '--delete' must be rejected with NightshiftError."""
        changelog_dir = tmp_path / ".recursive" / "changelog"
        changelog_dir.mkdir(parents=True)
        # Write a changelog whose Tag header contains a shell-flag-like value.
        content = (
            "# v0.0.8 -- Test\n\n"
            "**Released**: TBD\n"
            "**Tag**: `--delete`\n"
            "**Status**: In progress\n\n"
            "## Added\n\n- something\n"
        )
        (changelog_dir / "v0.0.8.md").write_text(content, encoding="utf-8")
        tasks_dir = _make_task(tmp_path, "0001", "v0.0.8", "done")
        with pytest.raises(nightshift.NightshiftError, match="Invalid tag"):
            _version_ready(changelog_dir, tasks_dir, "v0.0.8")

    def test_valid_tag_does_not_raise(self, tmp_path: Path) -> None:
        """A well-formed tag like 'v0.0.8' passes validation."""
        changelog_dir = _make_changelog(tmp_path, "v0.0.8", status="In progress", tag="v0.0.8")
        tasks_dir = _make_task(tmp_path, "0001", "v0.0.8", "done")
        # Should not raise -- valid tag passes through.
        ready, tag, _reason = _version_ready(changelog_dir, tasks_dir, "v0.0.8")
        assert ready is True
        assert tag == "v0.0.8"


# --- check_and_release -------------------------------------------------------


class TestCheckAndRelease:
    def test_dry_run_reports_would_release(self, tmp_path: Path) -> None:
        _make_changelog(tmp_path, "v0.0.8", status="In progress")
        _make_task(tmp_path, "0001", "v0.0.8", "done")

        result = check_and_release(tmp_path, version="v0.0.8", dry_run=True)

        assert result["released"] is False
        assert "[dry-run]" in result["reason"]
        assert result["version"] == "v0.0.8"
        assert result["tag"] == "v0.0.8"
        assert result["release_url"] == ""

    def test_not_released_when_tasks_pending(self, tmp_path: Path) -> None:
        _make_changelog(tmp_path, "v0.0.8", status="In progress")
        _make_task(tmp_path, "0001", "v0.0.8", "pending")

        result = check_and_release(tmp_path, version="v0.0.8", dry_run=True)

        assert result["released"] is False
        assert "not done" in result["reason"]

    def test_not_released_when_already_released(self, tmp_path: Path) -> None:
        _make_changelog(tmp_path, "v0.0.8", status="Released")
        _make_task(tmp_path, "0001", "v0.0.8", "done")

        result = check_and_release(tmp_path, version="v0.0.8", dry_run=True)

        assert result["released"] is False
        assert "already released" in result["reason"]

    def test_not_released_when_changelog_dir_missing(self, tmp_path: Path) -> None:
        result = check_and_release(tmp_path, version="v0.0.8", dry_run=True)

        assert result["released"] is False
        assert "not found" in result["reason"].lower()

    def test_not_released_when_missing_changelog_for_version(self, tmp_path: Path) -> None:
        _make_changelog(tmp_path, "v0.0.7", status="Released")
        _make_task(tmp_path, "0001", "v0.0.8", "done")

        result = check_and_release(tmp_path, version="v0.0.8", dry_run=True)

        assert result["released"] is False

    def test_auto_selects_highest_unreleased_version(self, tmp_path: Path) -> None:
        _make_changelog(tmp_path, "v0.0.7", status="Released")
        _make_changelog(tmp_path, "v0.0.8", status="In progress")
        _make_task(tmp_path, "0001", "v0.0.8", "done")

        result = check_and_release(tmp_path, dry_run=True)

        assert result["version"] == "v0.0.8"
        assert "[dry-run]" in result["reason"]

    def test_returns_not_released_when_no_unreleased_versions(self, tmp_path: Path) -> None:
        _make_changelog(tmp_path, "v0.0.7", status="Released")

        result = check_and_release(tmp_path, dry_run=True)

        assert result["released"] is False
        assert "No unreleased" in result["reason"]

    def test_raises_on_path_traversal_version(self, tmp_path: Path) -> None:
        """version='../../etc/passwd' must raise NightshiftError immediately."""
        with pytest.raises(nightshift.NightshiftError, match="Invalid version format"):
            check_and_release(tmp_path, version="../../etc/passwd")

    def test_raises_on_shell_flag_version(self, tmp_path: Path) -> None:
        """version='--delete' must raise NightshiftError immediately."""
        with pytest.raises(nightshift.NightshiftError, match="Invalid version format"):
            check_and_release(tmp_path, version="--delete")

    def test_performs_release_when_ready(self, tmp_path: Path) -> None:
        _make_changelog(tmp_path, "v0.0.8", status="In progress")
        _make_task(tmp_path, "0001", "v0.0.8", "done")

        with (
            patch("nightshift.infra.release._create_tag") as mock_tag,
            patch("nightshift.infra.release._push_tag") as mock_push,
            patch(
                "nightshift.infra.release._create_github_release",
                return_value="https://github.com/test/repo/releases/tag/v0.0.8",
            ) as mock_gh,
        ):
            result = check_and_release(tmp_path, version="v0.0.8", dry_run=False)

        assert result["released"] is True
        assert result["version"] == "v0.0.8"
        assert result["tag"] == "v0.0.8"
        assert "github.com" in result["release_url"]

        mock_tag.assert_called_once_with(tmp_path, "v0.0.8")
        mock_push.assert_called_once_with(tmp_path, "v0.0.8")
        mock_gh.assert_called_once()


# --- find_releasable_version ------------------------------------------------


class TestFindReleasableVersion:
    def test_returns_version_when_ready(self, tmp_path: Path) -> None:
        _make_changelog(tmp_path, "v0.0.8", status="In progress")
        _make_task(tmp_path, "0001", "v0.0.8", "done")

        result = find_releasable_version(tmp_path)

        assert result == "v0.0.8"

    def test_returns_none_when_all_released(self, tmp_path: Path) -> None:
        _make_changelog(tmp_path, "v0.0.7", status="Released")

        result = find_releasable_version(tmp_path)

        assert result is None

    def test_returns_none_when_tasks_pending(self, tmp_path: Path) -> None:
        _make_changelog(tmp_path, "v0.0.8", status="In progress")
        _make_task(tmp_path, "0001", "v0.0.8", "pending")

        result = find_releasable_version(tmp_path)

        assert result is None

    def test_returns_none_when_no_changelog_dir(self, tmp_path: Path) -> None:
        result = find_releasable_version(tmp_path)
        assert result is None

    def test_returns_highest_ready_version(self, tmp_path: Path) -> None:
        _make_changelog(tmp_path, "v0.0.7", status="In progress")
        _make_changelog(tmp_path, "v0.0.8", status="In progress")
        _make_task(tmp_path, "0001", "v0.0.7", "done")
        _make_task(tmp_path, "0002", "v0.0.8", "done")

        result = find_releasable_version(tmp_path)

        # The highest ready version is returned.
        assert result == "v0.0.8"


# --- _create_github_release --------------------------------------------------


class TestCreateGithubRelease:
    def test_uses_notes_file_not_notes_flag(self, tmp_path: Path) -> None:
        """--notes-file must be used; --notes must NOT appear in the command."""
        captured_cmd: list[list[str]] = []

        def fake_run_capture(cmd: list[str], **kwargs: object) -> str:
            captured_cmd.append(cmd)
            return "https://github.com/test/releases/tag/v0.0.8\n"

        with patch("nightshift.infra.release.run_capture", side_effect=fake_run_capture):
            _create_github_release(tmp_path, "v0.0.8", "## Notes\n- something\n")

        assert len(captured_cmd) == 1
        cmd = captured_cmd[0]
        assert "--notes-file" in cmd
        assert "--notes" not in cmd

    def test_notes_file_path_passed_to_command(self, tmp_path: Path) -> None:
        """The argument after --notes-file must be a real file path."""
        captured_cmd: list[list[str]] = []

        def fake_run_capture(cmd: list[str], **kwargs: object) -> str:
            captured_cmd.append(list(cmd))
            return "https://github.com/test/releases/tag/v0.0.8\n"

        with patch("nightshift.infra.release.run_capture", side_effect=fake_run_capture):
            _create_github_release(tmp_path, "v0.0.8", "## Notes\n")

        cmd = captured_cmd[0]
        idx = cmd.index("--notes-file")
        notes_path = cmd[idx + 1]
        # The path must look like a temp file (non-empty string ending in .md).
        assert notes_path.endswith(".md")
        assert len(notes_path) > 0

    def test_tempfile_is_cleaned_up_on_success(self, tmp_path: Path) -> None:
        """The tempfile must be deleted after a successful gh call."""
        created_path: list[str] = []

        original_unlink = os.unlink

        def tracking_unlink(path: str) -> None:
            created_path.append(path)
            original_unlink(path)

        def fake_run_capture(cmd: list[str], **kwargs: object) -> str:
            return "https://github.com/test/releases/tag/v0.0.8\n"

        with (
            patch("nightshift.infra.release.run_capture", side_effect=fake_run_capture),
            patch("nightshift.infra.release.os.unlink", side_effect=tracking_unlink),
        ):
            _create_github_release(tmp_path, "v0.0.8", "## Notes\n")

        assert len(created_path) == 1
        # The file must have been removed.
        assert not os.path.exists(created_path[0])

    def test_tempfile_is_cleaned_up_on_gh_failure(self, tmp_path: Path) -> None:
        """The tempfile must be deleted even when gh release create fails."""
        from nightshift.core.errors import NightshiftError

        deleted_path: list[str] = []
        original_unlink = os.unlink

        def tracking_unlink(path: str) -> None:
            deleted_path.append(path)
            original_unlink(path)

        def fake_run_capture(cmd: list[str], **kwargs: object) -> str:
            raise NightshiftError("gh not found")

        with (
            patch("nightshift.infra.release.run_capture", side_effect=fake_run_capture),
            patch("nightshift.infra.release.os.unlink", side_effect=tracking_unlink),
            pytest.raises(NightshiftError, match="gh release create failed"),
        ):
            _create_github_release(tmp_path, "v0.0.8", "## Notes\n")

        # Cleanup must still have run.
        assert len(deleted_path) == 1

    def test_changelog_beginning_with_at_does_not_leak_file(self, tmp_path: Path) -> None:
        """A changelog that starts with '@/etc/passwd' must be sent literally.

        With --notes, some gh versions read the file at that path.
        With --notes-file, gh reads the temp file we wrote -- the '@' string
        is simply the content of that file, never treated as a path reference.
        """
        captured_cmd: list[list[str]] = []
        captured_tempfile_content: list[str] = []

        def fake_run_capture(cmd: list[str], **kwargs: object) -> str:
            captured_cmd.append(list(cmd))
            # Read whatever the temp file contains so we can assert on it.
            idx = cmd.index("--notes-file")
            notes_path = cmd[idx + 1]
            with open(notes_path, encoding="utf-8") as fh:
                captured_tempfile_content.append(fh.read())
            return "https://github.com/test/releases/tag/v0.0.8\n"

        malicious_changelog = "@/etc/passwd\nsome content\n"
        with patch("nightshift.infra.release.run_capture", side_effect=fake_run_capture):
            _create_github_release(tmp_path, "v0.0.8", malicious_changelog)

        # The command uses --notes-file, not --notes.
        assert "--notes-file" in captured_cmd[0]
        assert "--notes" not in captured_cmd[0]
        # The tempfile holds the original content unmodified.
        assert captured_tempfile_content[0] == malicious_changelog


# --- Exports check -----------------------------------------------------------


class TestReleaseExports:
    def test_check_and_release_is_exported(self) -> None:
        assert hasattr(nightshift, "check_and_release")
        assert callable(nightshift.check_and_release)

    def test_find_releasable_version_is_exported(self) -> None:
        assert hasattr(nightshift, "find_releasable_version")
        assert callable(nightshift.find_releasable_version)

    def test_release_result_typeddict_is_exported(self) -> None:
        assert hasattr(nightshift, "ReleaseResult")
