"""Tests for scripts/pick-role.py role scoring engine."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from importlib import import_module

pick_role_mod = import_module("pick-role")

compute_scores = pick_role_mod.compute_scores
pick_role = pick_role_mod.pick_role
DEFAULTS = pick_role_mod.DEFAULTS
parse_session_index = pick_role_mod.parse_session_index
count_consecutive_role = pick_role_mod.count_consecutive_role
count_sessions_since_role = pick_role_mod.count_sessions_since_role
read_latest_eval_score = pick_role_mod.read_latest_eval_score
read_latest_autonomy_score = pick_role_mod.read_latest_autonomy_score
read_healer_status = pick_role_mod.read_healer_status
count_pending_tasks = pick_role_mod.count_pending_tasks
count_stale_tasks = pick_role_mod.count_stale_tasks
has_urgent_tasks = pick_role_mod.has_urgent_tasks
_read_frontmatter = pick_role_mod._read_frontmatter


def make_signals(**overrides: object) -> dict:
    """Create a signals dict with defaults, overriding specific values."""
    signals = dict(DEFAULTS)
    signals.update(overrides)
    return signals


# ---------------------------------------------------------------------------
# Stress test scenarios from the 6-agent audit
# ---------------------------------------------------------------------------


class TestScenario1ColdStart:
    def test_build_wins_on_cold_start(self) -> None:
        signals = make_signals()  # all defaults
        scores = compute_scores(signals)
        winner = pick_role(scores, urgent=False)
        assert winner == "build"
        assert scores["build"] == 80  # 50 + 30 (eval default 80 >= 80)

    def test_achieve_scores_55_on_cold_start(self) -> None:
        signals = make_signals()
        scores = compute_scores(signals)
        assert scores["achieve"] == -1  # capped (sessions_since_achieve=0 < 5)


class TestScenario2EvalGate:
    def test_eval_79_reduces_build(self) -> None:
        signals = make_signals(eval_score=79, sessions_since_achieve=10)
        scores = compute_scores(signals)
        assert scores["build"] == 30  # 50 - 20 (softer gate)
        assert scores["achieve"] == 55  # 5 + 50
        winner = pick_role(scores, urgent=False)
        assert winner == "achieve"

    def test_eval_80_ungates_build(self) -> None:
        signals = make_signals(eval_score=80)
        scores = compute_scores(signals)
        assert scores["build"] == 80  # 50 + 30


class TestScenario3ExactThresholds:
    def test_5_consecutive_builds_triggers_review(self) -> None:
        signals = make_signals(consecutive_builds=5, sessions_since_review=5)
        scores = compute_scores(signals)
        assert scores["review"] >= 60  # 10 + 40 + 10

    def test_80_pending_triggers_oversee_hard(self) -> None:
        signals = make_signals(pending_tasks=80, sessions_since_oversee=5)
        scores = compute_scores(signals)
        assert scores["oversee"] >= 55  # 5 + 50

    def test_50_pending_only_triggers_if_not_recent(self) -> None:
        signals = make_signals(pending_tasks=55, sessions_since_oversee=5)
        scores = compute_scores(signals)
        assert scores["oversee"] >= 40  # 5 + 35

    def test_50_pending_with_recent_oversee_gets_small_bonus(self) -> None:
        signals = make_signals(pending_tasks=55, sessions_since_oversee=2)
        scores = compute_scores(signals)
        assert scores["oversee"] == 25  # 5 + 20 (recent but still large)

    def test_50_pending_suppressed_if_just_ran(self) -> None:
        signals = make_signals(pending_tasks=55, sessions_since_oversee=0)
        scores = compute_scores(signals)
        assert scores["oversee"] == 5  # just ran, give others a turn

    def test_5_stale_triggers_oversee(self) -> None:
        signals = make_signals(stale_tasks=5, sessions_since_oversee=5)
        scores = compute_scores(signals)
        assert scores["oversee"] >= 30  # 5 + 25


class TestHealerCautionTriggers:
    def test_caution_with_gap_triggers_full_bonus(self) -> None:
        signals = make_signals(healer_status="caution", consecutive_builds=5, sessions_since_review=3)
        scores = compute_scores(signals)
        assert scores["review"] >= 60  # 10 + 40 + 30 (gap >= 2)

    def test_caution_right_after_review_diminished(self) -> None:
        signals = make_signals(healer_status="caution", consecutive_builds=5, sessions_since_review=1)
        scores = compute_scores(signals)
        assert scores["review"] == 60  # 10 + 40 + 10 (diminished)

    def test_good_does_not_trigger(self) -> None:
        signals = make_signals(healer_status="good", consecutive_builds=5)
        scores = compute_scores(signals)
        assert scores["review"] == 50  # 10 + 40 only


class TestScenario4OverseeMax:
    def test_oversee_beats_build_with_critical_queue(self) -> None:
        signals = make_signals(eval_score=95, pending_tasks=80, stale_tasks=5, sessions_since_oversee=10)
        scores = compute_scores(signals)
        assert scores["oversee"] >= 85  # 5 + 50 + 30
        assert scores["build"] == 80
        winner = pick_role(scores, urgent=False)
        assert winner == "oversee"


class TestScenario5EverythingBroken:
    def test_achieve_dominates_when_broken(self) -> None:
        signals = make_signals(
            eval_score=40,
            autonomy_score=30,
            needs_human_issues=5,
            sessions_since_achieve=10,
        )
        scores = compute_scores(signals)
        assert scores["achieve"] == 85  # 5 + 50 + 30
        assert scores["build"] == 30  # 50 - 20 (softer gate)
        winner = pick_role(scores, urgent=False)
        assert winner == "achieve"


class TestBuildEscapeHatch:
    def test_build_gets_boost_after_5_non_build_sessions(self) -> None:
        signals = make_signals(eval_score=69, sessions_since_build=5)
        scores = compute_scores(signals)
        assert scores["build"] == 55  # 50 - 20 + 25

    def test_build_gets_critical_boost_after_10(self) -> None:
        signals = make_signals(eval_score=69, sessions_since_build=10)
        scores = compute_scores(signals)
        assert scores["build"] == 70  # 50 - 20 + 25 + 15

    def test_build_escapes_review_dominance(self) -> None:
        signals = make_signals(
            eval_score=69,
            sessions_since_build=6,
            healer_status="caution",
            sessions_since_review=0,
        )
        scores = compute_scores(signals)
        # BUILD: 50 - 20 + 25 = 55
        # REVIEW: 10 + 10 (diminished healer, sr < 2) = 20
        assert scores["build"] > scores["review"]


class TestScenario6TieBreak:
    def test_oversee_beats_review_on_tie(self) -> None:
        # Tie-break priority: build, oversee, review, achieve, strategize
        scores = {"build": 10, "review": 40, "oversee": 40, "strategize": 5, "achieve": -1}
        assert pick_role(scores, urgent=False) == "oversee"


class TestScenario7ReviewVsAchieve:
    def test_15_builds_review_ties_build_build_wins(self) -> None:
        signals = make_signals(
            eval_score=85,
            consecutive_builds=15,
            sessions_since_review=15,
            autonomy_score=60,
            sessions_since_achieve=10,
        )
        scores = compute_scores(signals)
        assert scores["build"] == 80
        assert scores["review"] == 80  # 10 + 40 + 20 + 10
        winner = pick_role(scores, urgent=False)
        assert winner == "build"  # ties go to build


class TestScenario8StrategizeThreshold:
    def test_strategy_15_sessions_with_tracker_moved_loses_to_build(self) -> None:
        signals = make_signals(
            eval_score=90,
            sessions_since_strategy=15,
            pending_tasks=55,
            tracker_moved=True,
        )
        scores = compute_scores(signals)
        assert scores["build"] == 80
        assert scores["strategize"] == 65  # 5 + 60 (no +30 since tracker moved)
        winner = pick_role(scores, urgent=False)
        assert winner == "build"

    def test_strategy_with_stalled_tracker_beats_build(self) -> None:
        signals = make_signals(
            eval_score=90,
            sessions_since_strategy=15,
            tracker_moved=False,
        )
        scores = compute_scores(signals)
        assert scores["strategize"] == 95  # 5 + 60 + 30
        assert scores["build"] == 80
        winner = pick_role(scores, urgent=False)
        assert winner == "strategize"


class TestScenario9ForceRole:
    def test_urgent_forces_build(self) -> None:
        signals = make_signals(eval_score=30, urgent_tasks=True, sessions_since_achieve=10)
        scores = compute_scores(signals)
        winner = pick_role(scores, urgent=True)
        assert winner == "build"


class TestScenario10AchieveCap:
    def test_achieve_capped_within_5_sessions(self) -> None:
        signals = make_signals(
            autonomy_score=20,
            needs_human_issues=5,
            sessions_since_achieve=3,  # < 5
        )
        scores = compute_scores(signals)
        assert scores["achieve"] == -1

    def test_achieve_uncapped_after_5_sessions(self) -> None:
        signals = make_signals(
            autonomy_score=20,
            needs_human_issues=5,
            sessions_since_achieve=5,
        )
        scores = compute_scores(signals)
        assert scores["achieve"] > 0


# ---------------------------------------------------------------------------
# Signal readers
# ---------------------------------------------------------------------------


class TestReadEvalScore:
    def test_reads_latest_eval(self, tmp_path: Path) -> None:
        d = tmp_path / "evaluations"
        d.mkdir()
        (d / "0001.md").write_text("| **Total** | **51/100** |")
        (d / "0014.md").write_text("| **Total** | **69/100** |")
        assert read_latest_eval_score(d) == 69

    def test_no_files_returns_none(self, tmp_path: Path) -> None:
        d = tmp_path / "evaluations"
        d.mkdir()
        assert read_latest_eval_score(d) is None

    def test_missing_dir_returns_none(self, tmp_path: Path) -> None:
        assert read_latest_eval_score(tmp_path / "nope") is None


class TestReadAutonomyScore:
    def test_reads_score(self, tmp_path: Path) -> None:
        d = tmp_path / "autonomy"
        d.mkdir()
        (d / "2026-04-06.md").write_text("TOTAL:           72/100")
        assert read_latest_autonomy_score(d) == 72

    def test_no_files_returns_none(self, tmp_path: Path) -> None:
        d = tmp_path / "autonomy"
        d.mkdir()
        assert read_latest_autonomy_score(d) is None


class TestParseSessionIndex:
    def test_parses_9_column_table(self, tmp_path: Path) -> None:
        idx = tmp_path / "index.md"
        idx.write_text(
            "# Index\n\n"
            "| Timestamp | Session | Role | Exit | Duration | Cost | Status | Feature | PR |\n"
            "|-----------|---------|------|------|----------|------|--------|---------|----|\n"
            "| 2026-04-06 01:00 | s1 | build | 0 | 15m | $3 | success | feat | #1 |\n"
            "| 2026-04-06 01:20 | s2 | review | 0 | 10m | $2 | success | cycle.py | - |\n"
            "| 2026-04-06 01:35 | s3 | build | 0 | 18m | $4 | success | fix | #2 |\n"
        )
        rows = parse_session_index(idx)
        assert len(rows) == 3
        assert rows[0]["role"] == "build"
        assert rows[1]["role"] == "review"

    def test_empty_file(self, tmp_path: Path) -> None:
        idx = tmp_path / "index.md"
        idx.write_text("# Index\n")
        assert parse_session_index(idx) == []

    def test_missing_file(self, tmp_path: Path) -> None:
        assert parse_session_index(tmp_path / "nope.md") == []


class TestCountConsecutiveRole:
    def test_3_builds_in_a_row(self) -> None:
        rows = [
            {"role": "review"},
            {"role": "build"},
            {"role": "build"},
            {"role": "build"},
        ]
        assert count_consecutive_role(rows, "build") == 3

    def test_broken_by_review(self) -> None:
        rows = [
            {"role": "build"},
            {"role": "review"},
            {"role": "build"},
        ]
        assert count_consecutive_role(rows, "build") == 1

    def test_empty_rows(self) -> None:
        assert count_consecutive_role([], "build") == 0


class TestCountSessionsSinceRole:
    def test_review_2_sessions_ago(self) -> None:
        rows = [
            {"role": "review"},
            {"role": "build"},
            {"role": "build"},
        ]
        assert count_sessions_since_role(rows, "review") == 2

    def test_never_reviewed(self) -> None:
        rows = [{"role": "build"}, {"role": "build"}]
        assert count_sessions_since_role(rows, "review") == 2

    def test_empty(self) -> None:
        assert count_sessions_since_role([], "review") == 0


class TestReadHealerStatus:
    def test_reads_last_status(self, tmp_path: Path) -> None:
        log = tmp_path / "log.md"
        log.write_text("## 2026-04-05\n**System health:** good\n\n## 2026-04-06\n**System health:** concern\n")
        assert read_healer_status(log) == "concern"

    def test_missing_file(self, tmp_path: Path) -> None:
        assert read_healer_status(tmp_path / "nope.md") == "good"


class TestCountPendingTasks:
    def test_counts_pending(self, tmp_path: Path) -> None:
        d = tmp_path / "tasks"
        d.mkdir()
        (d / "0001.md").write_text("---\nstatus: pending\n---\n# Task")
        (d / "0002.md").write_text("---\nstatus: done\n---\n# Task")
        (d / "0003.md").write_text("---\nstatus: pending\n---\n# Task")
        assert count_pending_tasks(d) == 2

    def test_empty_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "tasks"
        d.mkdir()
        assert count_pending_tasks(d) == 0


class TestHasUrgentTasks:
    def test_finds_urgent(self, tmp_path: Path) -> None:
        d = tmp_path / "tasks"
        d.mkdir()
        (d / "0001.md").write_text("---\nstatus: pending\npriority: urgent\n---\n")
        assert has_urgent_tasks(d) is True

    def test_no_urgent(self, tmp_path: Path) -> None:
        d = tmp_path / "tasks"
        d.mkdir()
        (d / "0001.md").write_text("---\nstatus: pending\npriority: normal\n---\n")
        assert has_urgent_tasks(d) is False


class TestPickRoleTiebreaker:
    def test_ties_go_to_build(self) -> None:
        scores = {"build": 10, "review": 10, "oversee": 10, "strategize": 5, "achieve": -1}
        assert pick_role(scores, urgent=False) == "build"

    def test_urgent_always_build(self) -> None:
        scores = {"build": 10, "review": 100, "oversee": 100, "strategize": 100, "achieve": 100}
        assert pick_role(scores, urgent=True) == "build"


# ---------------------------------------------------------------------------
# Frontmatter helper and body-injection regression tests (tasks #0167, #0168)
# ---------------------------------------------------------------------------


class TestReadFrontmatter:
    """Unit tests for the _read_frontmatter helper."""

    def test_returns_frontmatter_content(self, tmp_path: Path) -> None:
        f = tmp_path / "0001.md"
        f.write_text("---\nstatus: pending\npriority: normal\n---\n# Body\n")
        fm = _read_frontmatter(f)
        assert fm == "status: pending\npriority: normal"

    def test_no_frontmatter_returns_none(self, tmp_path: Path) -> None:
        f = tmp_path / "0001.md"
        f.write_text("# No frontmatter\nstatus: pending\n")
        assert _read_frontmatter(f) is None

    def test_crlf_line_endings_parsed(self, tmp_path: Path) -> None:
        f = tmp_path / "0001.md"
        f.write_bytes(b"---\r\nstatus: pending\r\npriority: urgent\r\n---\r\n# Body\r\n")
        fm = _read_frontmatter(f)
        assert fm is not None
        assert "status: pending" in fm
        assert "priority: urgent" in fm

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert _read_frontmatter(tmp_path / "nonexistent.md") is None


class TestCountPendingTasksFrontmatterScope:
    """Regression: count_pending_tasks must not count body content (task #0167)."""

    def test_counts_pending_in_frontmatter(self, tmp_path: Path) -> None:
        (tmp_path / "0001.md").write_text("---\nstatus: pending\n---\n# Task")
        (tmp_path / "0002.md").write_text("---\nstatus: done\n---\n# Task")
        assert count_pending_tasks(tmp_path) == 1

    def test_body_status_pending_is_not_counted(self, tmp_path: Path) -> None:
        # Task is done in frontmatter; body happens to contain 'status: pending'
        (tmp_path / "0001.md").write_text("---\nstatus: done\n---\n\nstatus: pending\nSome body text.\n")
        assert count_pending_tasks(tmp_path) == 0

    def test_no_frontmatter_not_counted(self, tmp_path: Path) -> None:
        (tmp_path / "0001.md").write_text("status: pending\nNo delimiters.\n")
        assert count_pending_tasks(tmp_path) == 0

    def test_crlf_task_file_counted(self, tmp_path: Path) -> None:
        (tmp_path / "0001.md").write_bytes(b"---\r\nstatus: pending\r\n---\r\n# Task\r\n")
        assert count_pending_tasks(tmp_path) == 1


class TestCountStaleTasksFrontmatterScope:
    """Regression: count_stale_tasks must not count body content (task #0167)."""

    def test_body_status_pending_not_counted_as_stale(self, tmp_path: Path) -> None:
        # Frontmatter says done; body has 'status: pending' AND old created date
        (tmp_path / "0001.md").write_text(
            "---\nstatus: done\ncreated: 2020-01-01\n---\n\nstatus: pending\ncreated: 2020-01-01\n"
        )
        assert count_stale_tasks(tmp_path, threshold=1) == 0

    def test_old_pending_task_counted(self, tmp_path: Path) -> None:
        (tmp_path / "0001.md").write_text("---\nstatus: pending\ncreated: 2020-01-01\n---\n# Old task\n")
        assert count_stale_tasks(tmp_path, threshold=1) == 1

    def test_new_pending_task_not_counted(self, tmp_path: Path) -> None:
        from datetime import date

        today = date.today().isoformat()
        (tmp_path / "0001.md").write_text(f"---\nstatus: pending\ncreated: {today}\n---\n# New task\n")
        assert count_stale_tasks(tmp_path, threshold=20) == 0


class TestHasUrgentTasksCRLF:
    """Regression: has_urgent_tasks must detect urgent tasks in CRLF files (task #0168)."""

    def test_crlf_urgent_task_detected(self, tmp_path: Path) -> None:
        (tmp_path / "0001.md").write_bytes(b"---\r\nstatus: pending\r\npriority: urgent\r\n---\r\n# Body\r\n")
        assert has_urgent_tasks(tmp_path) is True

    def test_crlf_non_urgent_task_not_detected(self, tmp_path: Path) -> None:
        (tmp_path / "0001.md").write_bytes(b"---\r\nstatus: pending\r\npriority: normal\r\n---\r\n# Body\r\n")
        assert has_urgent_tasks(tmp_path) is False
