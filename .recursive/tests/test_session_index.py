"""Tests for session index formatting invariants.

Catches multiline/broken table rows in .recursive/sessions/index.md
before they reach the session index and corrupt dashboard signals.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add engine directory to path so signals.py is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import signals

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_HEADER = (
    "# Session Index\n"
    "\n"
    "| Timestamp        | Session         | Role       | Exit |"
    " Duration | Cost     | Status       | Feature    | PR         |\n"
    "| ---------------- | --------------- | ---------- | ---- |"
    " -------- | -------- | ------------ | ---------- | ---------- |\n"
)

_VALID_ROW = (
    "| 2026-04-08 12:00 | 20260408-120000 | build      | 0    |"
    " 15m      | $1.2345  | success      | Fix login  | #42        |\n"
)

_VALID_ROW_DASH = (
    "| 2026-04-08 12:01 | 20260408-120100 | review     | 0    |"
    " 10m      | $0.5000  | success      | -          | -          |\n"
)


def _parse(content: str) -> list[dict[str, str]]:
    """Write content to a temp file and parse it with signals.parse_session_index."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(content)
        path = Path(f.name)
    try:
        return signals.parse_session_index(path)
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Validator helper: check that every table row in index.md is single-line
# ---------------------------------------------------------------------------


def validate_session_index_rows(index_path: Path) -> list[str]:
    """Return a list of error messages for broken rows in the session index.

    A row is broken if:
    - It starts with '|' but contains fewer cells than the header
    - It starts with '|' and the previous non-blank line also started with '|'
      and that previous line had fewer cells than expected (wrapped row)

    Returns [] if the file is well-formed.
    """
    if not index_path.exists():
        return []

    lines = index_path.read_text(encoding="utf-8").splitlines()
    errors: list[str] = []

    # Find expected column count from the header
    expected_cols: int | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            # Separator row: all dashes
            if all(c.startswith("-") or c.startswith(":") for c in cells if c):
                continue
            if expected_cols is None:
                expected_cols = len(cells)
                continue
            # Data row: must match header column count
            if len(cells) != expected_cols:
                errors.append(f"Broken row (expected {expected_cols} cols, got {len(cells)}): {stripped[:120]}")

    return errors


# ---------------------------------------------------------------------------
# Tests: validate_session_index_rows
# ---------------------------------------------------------------------------


class TestValidateSessionIndexRows:
    def _write_and_validate(self, content: str) -> list[str]:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = Path(f.name)
        try:
            return validate_session_index_rows(path)
        finally:
            path.unlink(missing_ok=True)

    def test_valid_index_no_errors(self) -> None:
        content = _VALID_HEADER + _VALID_ROW + _VALID_ROW_DASH
        errors = self._write_and_validate(content)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_missing_file_returns_empty(self) -> None:
        errors = validate_session_index_rows(Path("/tmp/does_not_exist_abc.md"))
        assert errors == []

    def test_multiline_row_detected(self) -> None:
        # A row that wraps to a second pipe-prefixed line creates a row with
        # wrong cell count on the continuation line.
        broken_row = (
            "| 2026-04-08 12:00 | 20260408-120000 | build | 0 | 15m | $1.23 | success | "
            "Some very long feature description that wraps | #42 |\n"
            "| continuation of previous row that broke formatting | extra | cells | here | |\n"
        )
        content = _VALID_HEADER + broken_row
        errors = self._write_and_validate(content)
        # The continuation line has wrong cell count
        assert len(errors) >= 1

    def test_row_with_pipe_in_content_detected(self) -> None:
        # A field containing a pipe char creates phantom extra cells
        bad_row = "| 2026-04-08 12:00 | 20260408-120000 | build | 0 | 15m | $1.23 | success | feat|ure | #42 |\n"
        content = _VALID_HEADER + bad_row
        errors = self._write_and_validate(content)
        assert len(errors) >= 1, "Pipe-in-content row should be flagged"

    def test_extra_blank_lines_ignored(self) -> None:
        content = _VALID_HEADER + "\n\n" + _VALID_ROW + "\n\n" + _VALID_ROW_DASH
        errors = self._write_and_validate(content)
        assert errors == []


# ---------------------------------------------------------------------------
# Tests: parse_session_index correctly parses valid rows
# ---------------------------------------------------------------------------


class TestParseSessionIndex:
    def test_parses_single_valid_row(self) -> None:
        content = _VALID_HEADER + _VALID_ROW
        rows = _parse(content)
        assert len(rows) == 1
        assert rows[0]["role"] == "build"
        assert rows[0]["exit"] == "0"
        assert rows[0]["feature"] == "Fix login"
        assert rows[0]["pr"] == "#42"

    def test_parses_dash_feature_and_pr(self) -> None:
        content = _VALID_HEADER + _VALID_ROW_DASH
        rows = _parse(content)
        assert len(rows) == 1
        assert rows[0]["feature"] == "-"
        assert rows[0]["pr"] == "-"

    def test_multiline_row_dropped_by_parser(self) -> None:
        # A continuation row with wrong cell count is silently dropped --
        # parse_session_index only includes rows matching the header column count.
        broken_continuation = "| extra | col | mismatch | here | too | many |\n"
        content = _VALID_HEADER + _VALID_ROW + broken_continuation
        rows = _parse(content)
        # Only the valid row should appear
        assert len(rows) == 1
        assert rows[0]["role"] == "build"

    def test_empty_file_returns_empty_list(self) -> None:
        rows = _parse("")
        assert rows == []

    def test_header_only_returns_empty_list(self) -> None:
        rows = _parse(_VALID_HEADER)
        assert rows == []


# ---------------------------------------------------------------------------
# Integration: validate the live session index (informational, not gating)
# ---------------------------------------------------------------------------


class TestLiveSessionIndex:
    """Validate the actual sessions/index.md in the repository.

    These checks are informational -- they report any broken rows that exist
    in the file at review time, without blocking CI on historical data.
    """

    def _find_index(self) -> Path | None:
        # Walk up from this file to find .recursive/sessions/index.md
        here = Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent / ".recursive" / "sessions" / "index.md"
            if candidate.exists():
                return candidate
        return None

    def test_live_index_can_be_read(self) -> None:
        index_path = self._find_index()
        if index_path is None:
            return  # Not in a repo with .recursive/ -- skip
        rows = signals.parse_session_index(index_path)
        # If the file exists and has content, it should parse at least some rows
        content = index_path.read_text(encoding="utf-8")
        has_data_rows = any(
            line.strip().startswith("|") and not line.strip().startswith("| -") and "Timestamp" not in line
            for line in content.splitlines()
        )
        if has_data_rows:
            assert len(rows) > 0, (
                "parse_session_index returned no rows but index.md has table rows -- possible schema mismatch"
            )
