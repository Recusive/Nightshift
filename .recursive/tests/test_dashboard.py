"""Tests for .recursive/engine/dashboard.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from dashboard import collect_signals, format_dashboard
from signals import (
    compute_agent_diversity,
    compute_commitment_quality,
    compute_queue_trend,
)


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


class TestDelegationAwareSessions:
    """collect_signals uses delegation-aware counting for sessions_since_* keys.

    When the session index only shows role=brain (v2 architecture), the
    decisions log must be consulted to find the last time each sub-agent
    was actually delegated.  The counter should reflect the more recent
    of the two sources (index vs decisions log).
    """

    _DECISIONS_LOG = (
        "# Decision Journal\n\n"
        "## 2026-04-01 -- Session #0100\n"
        "**Delegations**: build (#0100 feature)\n"
        "## 2026-04-02 -- Session #0101\n"
        "**Delegations**: evolve (#0101 friction fix)\n"
        "## 2026-04-03 -- Session #0102\n"
        "**Delegations**: build (#0102 feature)\n"
        "## 2026-04-04 -- Session #0103\n"
        "**Delegations**: build (#0103 feature)\n"
    )

    _SESSION_INDEX = (
        "| Timestamp | Session | Role | Exit | Duration | Cost | Status | Feature | PR |\n"
        "|-----------|---------|------|------|----------|------|--------|---------|----|\n"
        "| 2026-04-01 | s100 | brain | 0 | 15m | $3 | success | - | - |\n"
        "| 2026-04-02 | s101 | brain | 0 | 10m | $2 | success | - | - |\n"
        "| 2026-04-03 | s102 | brain | 0 | 18m | $4 | success | - | - |\n"
        "| 2026-04-04 | s103 | brain | 0 | 12m | $3 | success | - | - |\n"
    )

    def _setup(self, tmp_path: Path) -> None:
        """Write session index and decisions log fixtures."""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        (sessions_dir / "index.md").write_text(self._SESSION_INDEX)

        decisions_dir = tmp_path / "decisions"
        decisions_dir.mkdir()
        (decisions_dir / "log.md").write_text(self._DECISIONS_LOG)

    def test_sessions_since_evolve_reflects_delegation(self, tmp_path: Path) -> None:
        """When index shows all brain sessions, decisions log drives evolve counter."""
        self._setup(tmp_path)
        signals = collect_signals(tmp_path)
        # Evolve was delegated in session #0101 (index position 1).
        # Two brain sessions (#0102, #0103) happened after it.
        # The index count would be 4 (evolve never appears in index).
        # The delegation count is 2 (two sessions after the evolve delegation).
        assert signals["sessions_since_evolve"] == 2

    def test_sessions_since_evolve_not_stale_with_all_brain_index(self, tmp_path: Path) -> None:
        """sessions_since_evolve must NOT equal len(index_rows) when decisions log has delegation."""
        self._setup(tmp_path)
        signals = collect_signals(tmp_path)
        # Without the fix, count_sessions_since_role would return 4 (all rows are brain).
        # With the fix, the delegation log drives it down to 2.
        assert signals["sessions_since_evolve"] < 4

    def test_sessions_since_build_reflects_recent_delegation(self, tmp_path: Path) -> None:
        """Build was last delegated in session #0103 (the most recent), so counter is 0."""
        self._setup(tmp_path)
        signals = collect_signals(tmp_path)
        assert signals["sessions_since_build"] == 0

    def test_sessions_since_audit_unrun_equals_total_sessions(self, tmp_path: Path) -> None:
        """Audit was never delegated; counter should equal number of decisions log entries."""
        self._setup(tmp_path)
        signals = collect_signals(tmp_path)
        # Audit never appears in index or decisions log.
        # min(index_count=4, delegation_count=4) = 4
        assert signals["sessions_since_audit"] == 4

    def test_decision_patterns_in_output(self, tmp_path: Path) -> None:
        """Dashboard output includes the decision patterns mirror section."""
        self._setup(tmp_path)
        signals = collect_signals(tmp_path)
        output = format_dashboard(signals)
        assert "Decision patterns" in output
        assert "Agent mix:" in output
        assert "Never used:" in output

    def test_delegation_aware_alerts_suppress_false_overdue(self, tmp_path: Path) -> None:
        """Alerts should NOT fire for roles delegated recently via decisions log."""
        self._setup(tmp_path)
        # Add a recent evolve entry so sessions_since_evolve stays below 25
        decisions_dir = tmp_path / "decisions"
        # Overwrite with a log where evolve was just delegated
        recent_log = "# Decision Journal\n\n" + "\n".join(
            f"## 2026-04-{i + 1:02d} -- Session #{i}\n**Delegations**: evolve (friction fix)\n" for i in range(1, 5)
        )
        (decisions_dir / "log.md").write_text(recent_log)
        signals = collect_signals(tmp_path)
        output = format_dashboard(signals)
        # evolve was delegated last session (0 since), so no overdue alert
        assert "Evolve overdue" not in output


class TestQueueTrend:
    def test_empty_log(self, tmp_path: Path) -> None:
        assert compute_queue_trend(tmp_path / "missing.md") == []

    def test_extracts_deltas(self, tmp_path: Path) -> None:
        log = tmp_path / "log.md"
        log.write_text(
            "## 2026-04-01 -- Session #1\n"
            "**Outcome**: PR #10 merged. 3 follow-up tasks created.\n\n"
            "## 2026-04-02 -- Session #2\n"
            "**Outcome**: PR #11 merged. PR #12 merged. 1 follow-up task created.\n"
        )
        deltas = compute_queue_trend(log)
        # Session 1: 3 created - 1 merged = +2
        # Session 2: 1 created - 2 merged = -1
        assert deltas == [2, -1]


class TestAgentDiversity:
    def test_empty_delegations(self) -> None:
        assert compute_agent_diversity([]) == {}

    def test_counts_frequency(self) -> None:
        delegations = [
            {"build", "evolve"},
            {"build", "evolve"},
            {"build", "security"},
        ]
        result = compute_agent_diversity(delegations)
        assert result["build"] == 3
        assert result["evolve"] == 2
        assert result["security"] == 1

    def test_respects_window(self) -> None:
        delegations = [{"audit"}] + [{"build"}] * 10
        result = compute_agent_diversity(delegations, window=5)
        assert "audit" not in result
        assert result["build"] == 5


class TestCommitmentQuality:
    def test_empty_log(self, tmp_path: Path) -> None:
        assert compute_commitment_quality(tmp_path / "missing.md") == "no data"

    def test_classifies_safe_vs_specific(self, tmp_path: Path) -> None:
        log = tmp_path / "log.md"
        log.write_text(
            "## 2026-04-01 -- Session #1\n"
            "**Prediction**: PR will merge and make check passes\n"
            "**Result**: MET\n\n"
            "## 2026-04-02 -- Session #2\n"
            "**Prediction**: Eval score will improve from 53 to >= 65\n"
            "**Result**: MET\n"
        )
        result = compute_commitment_quality(log)
        assert "2/2 MET" in result


class TestEvalStalenessAlert:
    """Dashboard alert fires when sessions_since_eval >= 5 (task #0242)."""

    def test_alert_fires_at_threshold(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        signals["sessions_since_eval"] = 5
        output = format_dashboard(signals)
        assert "eval_staleness" in output
        assert "STALE" in output  # top-level staleness indicator
        assert "5 sessions since last Phractal eval" in output  # alert text

    def test_alert_fires_above_threshold(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        signals["sessions_since_eval"] = 14
        output = format_dashboard(signals)
        assert "eval_staleness" in output
        assert "14 sessions since last Phractal eval" in output

    def test_no_alert_below_threshold(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        signals["sessions_since_eval"] = 3
        output = format_dashboard(signals)
        # Alert text should not appear when below threshold
        assert "sessions since last Phractal eval" not in output

    def test_staleness_shown_in_health_section(self, tmp_path: Path) -> None:
        """Eval staleness appears next to Eval score in the Health section."""
        signals = collect_signals(tmp_path)
        signals["sessions_since_eval"] = 7
        output = format_dashboard(signals)
        assert "Eval staleness:" in output
        assert "7 sessions" in output
        assert "STALE" in output

    def test_up_to_date_message_when_zero(self, tmp_path: Path) -> None:
        signals = collect_signals(tmp_path)
        signals["sessions_since_eval"] = 0
        output = format_dashboard(signals)
        assert "up to date" in output

    def test_sessions_since_eval_in_collect_signals(self, tmp_path: Path) -> None:
        """collect_signals includes sessions_since_eval key."""
        signals = collect_signals(tmp_path)
        assert "sessions_since_eval" in signals
        assert isinstance(signals["sessions_since_eval"], int)
