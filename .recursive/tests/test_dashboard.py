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

    def test_contains_timestamp(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        output = format_dashboard(signals)
        assert "Generated:" in output
        assert "UTC" in output

    def test_contains_alerts_section(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        output = format_dashboard(signals)
        assert "Alerts:" in output

    def test_contains_experiments_section(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        output = format_dashboard(signals)
        assert "Experiments:" in output


class TestExperimentCounting:
    def test_zero_experiments_on_empty_dir(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        assert signals["active_experiments"] == 0

    def test_counts_active_experiments(self, tmp_path: Path) -> None:
        decisions_dir = tmp_path / "decisions"
        decisions_dir.mkdir()
        log = decisions_dir / "log.md"
        log.write_text(
            "## EXPERIMENT: test-a\n**Status**: ACTIVE\n\n"
            "## EXPERIMENT: test-b\n**Status**: ACTIVE\n\n"
            "## EXPERIMENT: test-c\n**Status**: REVERTED\n"
        )
        signals = collect_signals(tmp_path)
        assert signals["active_experiments"] == 2

    def test_zero_when_no_active(self, tmp_path: Path) -> None:
        decisions_dir = tmp_path / "decisions"
        decisions_dir.mkdir()
        log = decisions_dir / "log.md"
        log.write_text("## EXPERIMENT: old\n**Status**: REVERTED\n")
        signals = collect_signals(tmp_path)
        assert signals["active_experiments"] == 0


class TestAlerts:
    def test_audit_overdue_alert(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        signals["sessions_since_audit"] = 30
        output = format_dashboard(signals)
        assert "audit overdue" in output.lower()

    def test_friction_threshold_alert(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        signals["friction_entries"] = 5
        output = format_dashboard(signals)
        assert "friction" in output.lower()
        assert "evolve recommended" in output.lower()

    def test_no_alerts_when_healthy(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        signals["sessions_since_audit"] = 2
        signals["sessions_since_evolve"] = 2
        signals["friction_entries"] = 0
        output = format_dashboard(signals)
        assert "None" in output
