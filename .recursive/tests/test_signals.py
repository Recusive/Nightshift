"""Tests for .recursive/engine/signals.py signal readers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import signals


class TestDefaults:
    def test_defaults_has_required_keys(self) -> None:
        required = [
            "eval_score",
            "autonomy_score",
            "consecutive_builds",
            "sessions_since_build",
            "sessions_since_review",
            "sessions_since_strategy",
            "sessions_since_achieve",
            "sessions_since_oversee",
            "pending_tasks",
            "stale_tasks",
            "healer_status",
            "needs_human_issues",
            "tracker_moved",
            "urgent_tasks",
            "recent_security_sessions",
        ]
        for key in required:
            assert key in signals.DEFAULTS, f"Missing key: {key}"


class TestStripFencedCodeBlocks:
    def test_removes_fenced_blocks(self) -> None:
        text = "before\n```\nhidden\n```\nafter"
        result = signals._strip_fenced_code_blocks(text)
        assert "hidden" not in result
        assert "before" in result
        assert "after" in result

    def test_no_blocks_unchanged(self) -> None:
        text = "no code blocks here"
        assert signals._strip_fenced_code_blocks(text) == text


class TestReadFrontmatter:
    def test_valid_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "task.md"
        f.write_text("---\nstatus: pending\npriority: normal\n---\n\n# Title\n")
        result = signals._read_frontmatter(f)
        assert result is not None
        assert "status: pending" in result

    def test_no_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "task.md"
        f.write_text("# No frontmatter\n")
        assert signals._read_frontmatter(f) is None

    def test_missing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.md"
        assert signals._read_frontmatter(f) is None


class TestCountPendingTasks:
    def test_counts_pending(self, tmp_path: Path) -> None:
        (tmp_path / "0001.md").write_text("---\nstatus: pending\n---\n")
        (tmp_path / "0002.md").write_text("---\nstatus: done\n---\n")
        (tmp_path / "0003.md").write_text("---\nstatus: pending\n---\n")
        assert signals.count_pending_tasks(tmp_path) == 2

    def test_empty_dir(self, tmp_path: Path) -> None:
        assert signals.count_pending_tasks(tmp_path) == 0


class TestParseSessionIndex:
    def test_parses_table(self, tmp_path: Path) -> None:
        index = tmp_path / "index.md"
        index.write_text(
            "| Session | Role | Status |\n|---------|------|--------|\n| 001 | build | ok |\n| 002 | review | ok |\n"
        )
        rows = signals.parse_session_index(index)
        assert len(rows) == 2
        assert rows[0]["role"] == "build"
        assert rows[1]["role"] == "review"

    def test_missing_file(self, tmp_path: Path) -> None:
        assert signals.parse_session_index(tmp_path / "nope.md") == []


class TestCountConsecutiveRole:
    def test_counts_from_end(self) -> None:
        rows = [{"role": "build"}, {"role": "build"}, {"role": "review"}, {"role": "build"}]
        assert signals.count_consecutive_role(rows, "build") == 1

    def test_all_same(self) -> None:
        rows = [{"role": "build"}, {"role": "build"}, {"role": "build"}]
        assert signals.count_consecutive_role(rows, "build") == 3


class TestCountSessionsSinceRole:
    def test_recent(self) -> None:
        rows = [{"role": "build"}, {"role": "review"}]
        assert signals.count_sessions_since_role(rows, "review") == 0

    def test_never(self) -> None:
        rows = [{"role": "build"}, {"role": "build"}]
        assert signals.count_sessions_since_role(rows, "review") == 2


class TestHasUrgentTasks:
    def test_urgent_found(self, tmp_path: Path) -> None:
        (tmp_path / "0001.md").write_text("---\nstatus: pending\npriority: urgent\n---\n")
        assert signals.has_urgent_tasks(tmp_path) is True

    def test_no_urgent(self, tmp_path: Path) -> None:
        (tmp_path / "0001.md").write_text("---\nstatus: pending\npriority: normal\n---\n")
        assert signals.has_urgent_tasks(tmp_path) is False


class TestReadHealerStatus:
    def test_reads_status(self, tmp_path: Path) -> None:
        log = tmp_path / "log.md"
        log.write_text("**System health:** good\n\n**System health:** concern\n")
        assert signals.read_healer_status(log) == "concern"

    def test_missing_file(self, tmp_path: Path) -> None:
        assert signals.read_healer_status(tmp_path / "nope.md") == "good"


class TestDidTrackerMove:
    def test_moved(self) -> None:
        rows = [{"status": "ok"}, {"status": "92%"}, {"status": "ok"}]
        assert signals.did_tracker_move(rows) is True

    def test_not_moved(self) -> None:
        rows = [{"status": "ok"}, {"status": "ok"}]
        assert signals.did_tracker_move(rows) is False


def _make_task(tmp_path: Path, name: str, frontmatter: str, body: str = "") -> Path:
    """Write a numbered task file with YAML frontmatter to tmp_path."""
    f = tmp_path / name
    f.write_text(f"---\n{frontmatter}\n---\n{body}")
    return f


class TestCountPendingPentestFrameworkTasks:
    def test_exact_match_counted(self, tmp_path: Path) -> None:
        _make_task(
            tmp_path,
            "0001.md",
            "status: pending\nsource: pentest\ntarget: recursive\n",
        )
        assert signals.count_pending_pentest_framework_tasks(tmp_path) == 1

    def test_suffixed_source_not_counted(self, tmp_path: Path) -> None:
        # "source: pentest-runner" must NOT match the anchored pattern
        _make_task(
            tmp_path,
            "0001.md",
            "status: pending\nsource: pentest-runner\ntarget: recursive\n",
        )
        assert signals.count_pending_pentest_framework_tasks(tmp_path) == 0

    def test_prefixed_source_not_counted(self, tmp_path: Path) -> None:
        _make_task(
            tmp_path,
            "0001.md",
            "status: pending\nsource: manual-pentest\ntarget: recursive\n",
        )
        assert signals.count_pending_pentest_framework_tasks(tmp_path) == 0

    def test_crlf_line_endings_counted(self, tmp_path: Path) -> None:
        f = tmp_path / "0001.md"
        f.write_bytes(b"---\r\nstatus: pending\r\nsource: pentest\r\ntarget: recursive\r\n---\r\n")
        assert signals.count_pending_pentest_framework_tasks(tmp_path) == 1

    def test_wrong_target_excluded(self, tmp_path: Path) -> None:
        # target: v0.0.8 is a product task, not a framework task
        _make_task(
            tmp_path,
            "0001.md",
            "status: pending\nsource: pentest\ntarget: v0.0.8\n",
        )
        assert signals.count_pending_pentest_framework_tasks(tmp_path) == 0

    def test_done_task_excluded(self, tmp_path: Path) -> None:
        _make_task(
            tmp_path,
            "0001.md",
            "status: done\nsource: pentest\ntarget: recursive\n",
        )
        assert signals.count_pending_pentest_framework_tasks(tmp_path) == 0

    def test_multiple_tasks_counted(self, tmp_path: Path) -> None:
        _make_task(
            tmp_path,
            "0001.md",
            "status: pending\nsource: pentest\ntarget: recursive\n",
        )
        _make_task(
            tmp_path,
            "0002.md",
            "status: pending\nsource: pentest\ntarget: recursive\n",
        )
        _make_task(
            tmp_path,
            "0003.md",
            "status: pending\nsource: code-review\ntarget: recursive\n",
        )
        assert signals.count_pending_pentest_framework_tasks(tmp_path) == 2

    def test_empty_dir_returns_zero(self, tmp_path: Path) -> None:
        assert signals.count_pending_pentest_framework_tasks(tmp_path) == 0


class TestCountRecentPentestTasks:
    def _make_archive_task(self, archive_dir: Path, name: str, frontmatter: str) -> Path:
        return _make_task(archive_dir, name, frontmatter)

    def test_recent_task_counted(self, tmp_path: Path) -> None:
        archive = tmp_path / "archive"
        archive.mkdir()
        # completed today -- within any positive day window
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        self._make_archive_task(
            archive,
            "0001.md",
            f"status: done\nsource: pentest\ncompleted: {today}\n",
        )
        assert signals.count_recent_pentest_tasks(tmp_path, days=3) >= 1

    def test_old_task_excluded(self, tmp_path: Path) -> None:
        archive = tmp_path / "archive"
        archive.mkdir()
        # completed 30 days ago -- beyond the 3-day window
        self._make_archive_task(
            archive,
            "0001.md",
            "status: done\nsource: pentest\ncompleted: 2020-01-01\n",
        )
        assert signals.count_recent_pentest_tasks(tmp_path, days=3) == 0

    def test_suffixed_source_not_counted(self, tmp_path: Path) -> None:
        archive = tmp_path / "archive"
        archive.mkdir()
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        self._make_archive_task(
            archive,
            "0001.md",
            f"status: done\nsource: pentest-runner\ncompleted: {today}\n",
        )
        assert signals.count_recent_pentest_tasks(tmp_path, days=3) == 0

    def test_crlf_line_endings_counted(self, tmp_path: Path) -> None:
        archive = tmp_path / "archive"
        archive.mkdir()
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        content = f"---\r\nstatus: done\r\nsource: pentest\r\ncompleted: {today}\r\n---\r\n"
        (archive / "0001.md").write_bytes(content.encode("utf-8"))
        assert signals.count_recent_pentest_tasks(tmp_path, days=3) >= 1

    def test_no_archive_dir_returns_zero(self, tmp_path: Path) -> None:
        # archive subdir does not exist
        assert signals.count_recent_pentest_tasks(tmp_path, days=3) == 0

    def test_date_cutoff_boundary(self, tmp_path: Path) -> None:
        archive = tmp_path / "archive"
        archive.mkdir()
        from datetime import datetime, timedelta

        # exactly on the boundary date (same as cutoff) -- should be counted
        boundary = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        self._make_archive_task(
            archive,
            "0001.md",
            f"status: done\nsource: pentest\ncompleted: {boundary}\n",
        )
        # one day before the boundary -- should NOT be counted
        before = (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d")
        self._make_archive_task(
            archive,
            "0002.md",
            f"status: done\nsource: pentest\ncompleted: {before}\n",
        )
        assert signals.count_recent_pentest_tasks(tmp_path, days=3) == 1
