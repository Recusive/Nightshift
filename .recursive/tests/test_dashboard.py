"""Tests for .recursive/engine/dashboard.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from dashboard import collect_signals, format_dashboard


class TestCollectSignals:
    def test_returns_dict_with_defaults_on_empty_dir(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        assert isinstance(signals, dict)
        assert signals["eval_score"] == 80  # default
        assert signals["pending_tasks"] == 0
        assert signals["healer_status"] == "good"

    def test_marks_eval_default(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        assert signals["_eval_is_default"] is True
        assert signals["_autonomy_is_default"] is True

    def test_includes_sessions_since_roles(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        assert "sessions_since_build" in signals
        assert "sessions_since_review" in signals
        assert "sessions_since_security_check" in signals


class TestFormatDashboard:
    def test_produces_string(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        output = format_dashboard(signals)
        assert isinstance(output, str)
        assert "System Dashboard" in output

    def test_contains_eval_score(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        output = format_dashboard(signals)
        assert "Eval score:" in output
        assert "80/100" in output  # default

    def test_contains_sessions_since(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        output = format_dashboard(signals)
        assert "Sessions since:" in output
        assert "build" in output
