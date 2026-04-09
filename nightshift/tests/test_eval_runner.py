"""Tests for nightshift.owl.eval_runner -- dry-run evaluation and CLI argument parsing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import nightshift  # noqa: I001

from nightshift.cli import build_parser, eval_cli
from nightshift.core.constants import EVALUATION_DIMENSIONS, EVALUATION_MAX_PER_DIMENSION
from nightshift.core.types import EvaluationResult, ShiftArtifacts
from nightshift.core.errors import NightshiftError
from nightshift.owl.eval_runner import (
    _build_synthetic_artifacts,
    _next_eval_id,
    _safe_rmtree,
    _score_breadth,
    _score_clean_state,
    _score_discovery,
    _score_fix_quality,
    _score_guard_rails,
    _score_shift_log,
    _score_startup,
    _score_state_file,
    _score_usefulness,
    _score_verification,
    format_eval_table,
    run_eval_dry_run,
    score_artifacts,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _make_minimal_artifacts(
    state: dict[str, object] | None = None,
    shift_log: str = "",
    runner_exit_code: int = 0,
    state_file_valid: bool = False,
    shift_log_exists: bool = False,
    git_status_output: str = "",
    repo_is_clean: bool = True,
) -> ShiftArtifacts:
    """Return a minimal valid ShiftArtifacts dict with explicit overridable fields."""
    return ShiftArtifacts(
        state=state,
        shift_log=shift_log,
        runner_exit_code=runner_exit_code,
        state_file_valid=state_file_valid,
        shift_log_exists=shift_log_exists,
        git_status_output=git_status_output,
        repo_is_clean=repo_is_clean,
    )


def _make_full_state(
    fixes: int = 2,
    issues: int = 1,
    tests_written: int = 1,
    categories: list[str] | None = None,
    verify_status: str = "passed",
) -> dict[str, object]:
    cat_list = categories or ["Security", "Tests"]
    cat_counts: dict[str, int] = dict.fromkeys(cat_list, 1)
    first_cat = cat_list[0]
    return {
        "version": 1,
        "date": "2026-01-01",
        "branch": "nightshift/2026-01-01",
        "agent": "claude",
        "verify_command": "make test",
        "baseline": {"status": "passed", "command": "make test", "message": ""},
        "counters": {
            "fixes": fixes,
            "issues_logged": issues,
            "files_touched": fixes + 1,
            "low_impact_fixes": 0,
            "failed_verifications": 0,
            "empty_cycles": 0,
            "agent_failures": 0,
            "tests_written": tests_written,
        },
        "category_counts": cat_counts,
        "recent_cycle_paths": ["src/auth.py"],
        "cycles": [
            {
                "cycle": 1,
                "status": "accepted",
                "fixes": [
                    {
                        "title": "Fix auth bypass",
                        "category": first_cat,
                        "impact": "high",
                        "files": ["src/auth.py"],
                    }
                ],
                "logged_issues": [],
                "verification": {
                    "verify_command": "make test",
                    "verify_status": verify_status,
                    "verify_exit_code": 0 if verify_status == "passed" else 1,
                    "dominant_path": "src/",
                    "commits": ["abc123"],
                    "files_touched": ["src/auth.py"],
                    "violations": [],
                },
            }
        ],
        "halt_reason": None,
        "log_only_mode": False,
    }


# ---------------------------------------------------------------------------
# Synthetic artifact generation
# ---------------------------------------------------------------------------


class TestBuildSyntheticArtifacts:
    def test_returns_shift_artifacts_shape(self) -> None:
        art = _build_synthetic_artifacts()
        assert "state" in art
        assert "shift_log" in art
        assert "runner_exit_code" in art
        assert "state_file_valid" in art
        assert "shift_log_exists" in art
        assert "git_status_output" in art
        assert "repo_is_clean" in art

    def test_state_is_dict(self) -> None:
        art = _build_synthetic_artifacts()
        assert isinstance(art["state"], dict)

    def test_shift_log_is_nonempty(self) -> None:
        art = _build_synthetic_artifacts()
        assert isinstance(art["shift_log"], str)
        assert len(art["shift_log"]) > 100

    def test_runner_exit_code_is_zero(self) -> None:
        art = _build_synthetic_artifacts()
        assert art["runner_exit_code"] == 0


# ---------------------------------------------------------------------------
# Individual dimension scorers
# ---------------------------------------------------------------------------


class TestScoreStartup:
    def test_exit_zero_scores_nonzero(self) -> None:
        art = _make_minimal_artifacts(runner_exit_code=0)
        result = _score_startup(art)
        assert result["score"] > 0
        assert result["name"] == "Startup"

    def test_nonzero_exit_scores_zero(self) -> None:
        art = _make_minimal_artifacts(runner_exit_code=1)
        result = _score_startup(art)
        assert result["score"] == 0


class TestScoreDiscovery:
    def test_no_state_scores_zero(self) -> None:
        art = _make_minimal_artifacts()
        result = _score_discovery(art)
        assert result["score"] == 0

    def test_fixes_and_issues_add_to_score(self) -> None:
        state = _make_full_state(fixes=2, issues=1)
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_discovery(art)
        assert result["score"] > 0

    def test_score_capped_at_ten(self) -> None:
        state = _make_full_state(fixes=10, issues=10)
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_discovery(art)
        assert result["score"] <= 10


class TestScoreFixQuality:
    def test_no_state_scores_zero(self) -> None:
        art = _make_minimal_artifacts()
        result = _score_fix_quality(art)
        assert result["score"] == 0

    def test_structured_fixes_score_high(self) -> None:
        state = _make_full_state(fixes=2)
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_fix_quality(art)
        assert result["score"] > 0

    def test_unstructured_fixes_score_zero(self) -> None:
        state: dict[str, object] = {
            "cycles": [{"cycle": 1, "fixes": [{"title": "Something"}]}],
            "counters": {"fixes": 1},
            "category_counts": {},
        }
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_fix_quality(art)
        assert result["score"] == 0


class TestScoreShiftLog:
    def test_missing_log_scores_zero(self) -> None:
        art = _make_minimal_artifacts(shift_log_exists=False)
        result = _score_shift_log(art)
        assert result["score"] == 0

    def test_template_log_scores_low(self) -> None:
        art = _make_minimal_artifacts(
            shift_log_exists=True,
            shift_log="will be rewritten as the overnight run accumulates",
        )
        result = _score_shift_log(art)
        assert result["score"] < 5

    def test_real_log_scores_higher(self) -> None:
        long_log = "# Nightshift\n\n## Summary\n\nFixed 2 things.\n\n## Fixes\n\n1. thing\n2. thing\n" * 5
        art = _make_minimal_artifacts(shift_log_exists=True, shift_log=long_log)
        result = _score_shift_log(art)
        assert result["score"] >= 5


class TestScoreStateFile:
    def test_invalid_state_file_scores_zero(self) -> None:
        art = _make_minimal_artifacts(state_file_valid=False)
        result = _score_state_file(art)
        assert result["score"] == 0

    def test_valid_state_with_all_keys_scores_high(self) -> None:
        state = _make_full_state()
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_state_file(art)
        assert result["score"] >= 6

    def test_missing_required_keys_scores_partial(self) -> None:
        state: dict[str, object] = {"version": 1, "cycles": []}
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_state_file(art)
        assert 0 < result["score"] < 8

    def test_count_only_regression_detected_scores_below_8(self) -> None:
        """Regression for eval #0091: count-only payload gives fixes_counter > 0
        but cycles[*].fixes=[] -- scorer must detect this and return score < 8.
        """
        state: dict[str, object] = {
            "version": 1,
            "date": "2026-04-09",
            "branch": "nightshift/2026-04-09",
            "agent": "claude",
            "counters": {
                "fixes": 2,
                "issues_logged": 0,
                "files_touched": 2,
                "low_impact_fixes": 0,
                "failed_verifications": 0,
                "empty_cycles": 0,
                "agent_failures": 0,
                "tests_written": 0,
            },
            "category_counts": {},
            "cycles": [
                {
                    "cycle": 1,
                    "status": "unknown",
                    "fixes": [],  # empty: count-only regression
                    "logged_issues": [],
                    "verification": {
                        "verify_command": None,
                        "verify_status": "skipped",
                        "verify_exit_code": None,
                        "dominant_path": "apps",
                        "commits": ["abc123"],
                        "files_touched": ["apps/web/auth.ts"],
                        "violations": [],
                    },
                }
            ],
            "halt_reason": None,
            "log_only_mode": False,
        }
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_state_file(art)
        # Count-only payload: fixes=2 in counters but cycles[*].fixes=[] must be penalized
        assert result["score"] < 8
        assert "cycles[*].fixes=[]" in result["notes"]

    def test_structured_fixes_with_category_counts_scores_ten(self) -> None:
        """State with fully structured fixes and populated category_counts scores 10."""
        state: dict[str, object] = {
            "version": 1,
            "date": "2026-04-09",
            "branch": "nightshift/2026-04-09",
            "agent": "claude",
            "counters": {
                "fixes": 1,
                "issues_logged": 0,
                "files_touched": 1,
                "low_impact_fixes": 0,
                "failed_verifications": 0,
                "empty_cycles": 0,
                "agent_failures": 0,
                "tests_written": 0,
            },
            "category_counts": {"Security": 1},
            "cycles": [
                {
                    "cycle": 1,
                    "status": "completed",
                    "fixes": [
                        {
                            "title": "Fix auth bypass",
                            "category": "Security",
                            "impact": "high",
                            "files": ["apps/web/auth.ts"],
                            "commit": "abc123",
                        }
                    ],
                    "logged_issues": [],
                    "verification": {
                        "verify_command": None,
                        "verify_status": "skipped",
                        "verify_exit_code": None,
                        "dominant_path": "apps",
                        "commits": ["abc123"],
                        "files_touched": ["apps/web/auth.ts"],
                        "violations": [],
                    },
                }
            ],
            "halt_reason": None,
            "log_only_mode": False,
        }
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_state_file(art)
        assert result["score"] == 10

    def test_structured_fixes_without_category_counts_scores_nine(self) -> None:
        """State with structured fixes but no category_counts scores 9 (not 10)."""
        state: dict[str, object] = {
            "version": 1,
            "date": "2026-04-09",
            "branch": "nightshift/2026-04-09",
            "agent": "claude",
            "counters": {
                "fixes": 1,
                "issues_logged": 0,
                "files_touched": 1,
                "low_impact_fixes": 0,
                "failed_verifications": 0,
                "empty_cycles": 0,
                "agent_failures": 0,
                "tests_written": 0,
            },
            "category_counts": {},  # empty despite structured fixes
            "cycles": [
                {
                    "cycle": 1,
                    "status": "completed",
                    "fixes": [
                        {
                            "title": "Fix auth bypass",
                            "category": "Security",
                            "impact": "high",
                            "files": ["apps/web/auth.ts"],
                            "commit": "abc123",
                        }
                    ],
                    "logged_issues": [],
                    "verification": {
                        "verify_command": None,
                        "verify_status": "skipped",
                        "verify_exit_code": None,
                        "dominant_path": "apps",
                        "commits": ["abc123"],
                        "files_touched": ["apps/web/auth.ts"],
                        "violations": [],
                    },
                }
            ],
            "halt_reason": None,
            "log_only_mode": False,
        }
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_state_file(art)
        assert result["score"] == 9

    def test_partially_structured_fixes_scores_eight(self) -> None:
        """Partial structuredness: 2 fixes, 1 with category+impact, 1 without.

        Task #0261: when total_fixes_in_cycles > 0 but structured_fixes_in_cycles
        is less than total (partial), neither the count-only regression branch nor
        the all-structured branch is triggered. The scorer falls through to the
        base score of 8 with notes='valid'.
        """
        state: dict[str, object] = {
            "version": 1,
            "date": "2026-04-09",
            "branch": "nightshift/2026-04-09",
            "agent": "claude",
            "counters": {
                "fixes": 2,
                "issues_logged": 0,
                "files_touched": 2,
                "low_impact_fixes": 0,
                "failed_verifications": 0,
                "empty_cycles": 0,
                "agent_failures": 0,
                "tests_written": 0,
            },
            "category_counts": {"Security": 1},
            "cycles": [
                {
                    "cycle": 1,
                    "status": "completed",
                    "fixes": [
                        {
                            "title": "Fix auth bypass",
                            "category": "Security",
                            "impact": "high",
                            "files": ["apps/web/auth.ts"],
                        },
                        {
                            "title": "Rename variable",
                            # no category or impact fields
                            "files": ["apps/web/utils.ts"],
                        },
                    ],
                    "logged_issues": [],
                    "verification": {
                        "verify_command": None,
                        "verify_status": "skipped",
                        "verify_exit_code": None,
                        "dominant_path": "apps",
                        "commits": ["abc123"],
                        "files_touched": ["apps/web/auth.ts", "apps/web/utils.ts"],
                        "violations": [],
                    },
                }
            ],
            "halt_reason": None,
            "log_only_mode": False,
        }
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_state_file(art)
        # 1/2 structured: falls through to base score 8 with notes="valid"
        assert result["score"] == 8
        assert result["notes"] == "valid"


class TestScoreVerification:
    def test_no_state_scores_zero(self) -> None:
        art = _make_minimal_artifacts()
        result = _score_verification(art)
        assert result["score"] == 0

    def test_no_cycles_returns_skipped_score(self) -> None:
        state: dict[str, object] = {"cycles": []}
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_verification(art)
        assert result["score"] == 5
        assert "skipped" in result["notes"]

    def test_all_passed_scores_ten(self) -> None:
        state = _make_full_state(verify_status="passed")
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_verification(art)
        assert result["score"] == 10


class TestScoreGuardRails:
    def test_dirty_tree_scores_partial(self) -> None:
        art = _make_minimal_artifacts(repo_is_clean=False)
        result = _score_guard_rails(art)
        assert result["score"] < 8

    def test_clean_no_git_output_scores_high(self) -> None:
        art = _make_minimal_artifacts(repo_is_clean=True, git_status_output="")
        result = _score_guard_rails(art)
        assert result["score"] >= 8


class TestScoreCleanState:
    def test_empty_git_output_scores_ten(self) -> None:
        art = _make_minimal_artifacts(git_status_output="")
        result = _score_clean_state(art)
        assert result["score"] == 10

    def test_many_untracked_files_lowers_score(self) -> None:
        git_out = "\n".join(f"?? file{i}.py" for i in range(5))
        art = _make_minimal_artifacts(git_status_output=git_out)
        result = _score_clean_state(art)
        assert result["score"] < 8


class TestScoreBreadth:
    def test_no_state_scores_zero(self) -> None:
        art = _make_minimal_artifacts()
        result = _score_breadth(art)
        assert result["score"] == 0

    def test_multiple_categories_scores_higher(self) -> None:
        state = _make_full_state(categories=["Security", "Tests", "Performance"])
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_breadth(art)
        assert result["score"] >= 6


class TestScoreUsefulness:
    def test_no_state_scores_zero(self) -> None:
        art = _make_minimal_artifacts()
        result = _score_usefulness(art)
        assert result["score"] == 0

    def test_fixes_and_tests_scores_higher(self) -> None:
        state = _make_full_state(fixes=2, tests_written=2)
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_usefulness(art)
        assert result["score"] > 0

    def test_score_capped_at_ten(self) -> None:
        state = _make_full_state(fixes=10, tests_written=10)
        art = _make_minimal_artifacts(state=state, state_file_valid=True)
        result = _score_usefulness(art)
        assert result["score"] <= 10


# ---------------------------------------------------------------------------
# score_artifacts: all 10 dimensions covered
# ---------------------------------------------------------------------------


class TestScoreArtifacts:
    def test_returns_ten_dimensions(self) -> None:
        art = _build_synthetic_artifacts()
        scores = score_artifacts(art)
        assert len(scores) == len(EVALUATION_DIMENSIONS)

    def test_dimension_names_match_constants(self) -> None:
        art = _build_synthetic_artifacts()
        scores = score_artifacts(art)
        names = [s["name"] for s in scores]
        assert names == EVALUATION_DIMENSIONS

    def test_all_scores_in_range(self) -> None:
        art = _build_synthetic_artifacts()
        scores = score_artifacts(art)
        for s in scores:
            assert 0 <= s["score"] <= s["max_score"]
            assert s["max_score"] == EVALUATION_MAX_PER_DIMENSION

    def test_synthetic_artifacts_produce_nonzero_total(self) -> None:
        art = _build_synthetic_artifacts()
        scores = score_artifacts(art)
        total = sum(s["score"] for s in scores)
        assert total > 0


# ---------------------------------------------------------------------------
# format_eval_table
# ---------------------------------------------------------------------------


class TestFormatEvalTable:
    def _make_result(self) -> EvaluationResult:
        art = _build_synthetic_artifacts()
        dimensions = score_artifacts(art)
        total = sum(d["score"] for d in dimensions)
        max_total = sum(d["max_score"] for d in dimensions)
        return EvaluationResult(
            evaluation_id=1,
            date="2026-01-01",
            target_repo="https://example.com/repo",
            agent="claude",
            cycles=2,
            after_task="",
            dimensions=dimensions,
            total_score=total,
            max_total=max_total,
            tasks_created=[],
        )

    def test_output_contains_all_dimension_names(self) -> None:
        result = self._make_result()
        table = format_eval_table(result)
        for dim_name in EVALUATION_DIMENSIONS:
            assert dim_name in table

    def test_output_contains_total(self) -> None:
        result = self._make_result()
        table = format_eval_table(result)
        assert "TOTAL" in table

    def test_output_contains_target(self) -> None:
        result = self._make_result()
        table = format_eval_table(result)
        assert "example.com" in table

    def test_output_is_ascii_only(self) -> None:
        result = self._make_result()
        table = format_eval_table(result)
        assert table.isascii()


# ---------------------------------------------------------------------------
# run_eval_dry_run
# ---------------------------------------------------------------------------


class TestRunEvalDryRun:
    def test_returns_evaluation_result(self, tmp_path: Path) -> None:
        result = run_eval_dry_run(tmp_path)
        assert isinstance(result, dict)
        assert "evaluation_id" in result
        assert "dimensions" in result
        assert "total_score" in result

    def test_has_ten_dimensions(self, tmp_path: Path) -> None:
        result = run_eval_dry_run(tmp_path)
        assert len(result["dimensions"]) == 10

    def test_target_repo_is_dry_run_label(self, tmp_path: Path) -> None:
        result = run_eval_dry_run(tmp_path)
        assert "dry-run" in result["target_repo"]

    def test_exit_zero_no_network(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            run_eval_dry_run(tmp_path)
            mock_run.assert_not_called()

    def test_write_report_creates_file(self, tmp_path: Path) -> None:
        result = run_eval_dry_run(tmp_path, write_report=True)
        eval_dir = tmp_path / ".recursive" / "evaluations"
        report = eval_dir / f"{result['evaluation_id']:04d}.md"
        assert report.exists()
        content = report.read_text(encoding="utf-8")
        assert "Scorecard" in content

    def test_evaluation_id_increments(self, tmp_path: Path) -> None:
        r1 = run_eval_dry_run(tmp_path, write_report=True)
        r2 = run_eval_dry_run(tmp_path, write_report=True)
        assert r2["evaluation_id"] == r1["evaluation_id"] + 1

    def test_total_score_within_bounds(self, tmp_path: Path) -> None:
        result = run_eval_dry_run(tmp_path)
        assert 0 <= result["total_score"] <= result["max_total"]

    def test_max_total_is_100(self, tmp_path: Path) -> None:
        result = run_eval_dry_run(tmp_path)
        assert result["max_total"] == 100


# ---------------------------------------------------------------------------
# _safe_rmtree
# ---------------------------------------------------------------------------


class TestSafeRmtree:
    def test_removes_existing_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "to_remove"
        target.mkdir()
        (target / "file.txt").write_text("content", encoding="utf-8")
        _safe_rmtree(target)
        assert not target.exists()

    def test_silently_skips_nonexistent_path(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        # Should not raise
        _safe_rmtree(missing)

    def test_raises_on_symlink_target(self, tmp_path: Path) -> None:
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real_dir)
        with pytest.raises(NightshiftError, match="symlink"):
            _safe_rmtree(link)
        # The real directory must not be touched
        assert real_dir.exists()

    def test_raises_on_symlink_regardless_of_ignore_errors(self, tmp_path: Path) -> None:
        real_dir = tmp_path / "real2"
        real_dir.mkdir()
        link = tmp_path / "link2"
        link.symlink_to(real_dir)
        with pytest.raises(NightshiftError, match="symlink"):
            _safe_rmtree(link, ignore_errors=True)
        assert real_dir.exists()


# ---------------------------------------------------------------------------
# _next_eval_id
# ---------------------------------------------------------------------------


class TestNextEvalId:
    def test_empty_dir_returns_one(self, tmp_path: Path) -> None:
        assert _next_eval_id(tmp_path) == 1

    def test_nonexistent_dir_returns_one(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing"
        assert _next_eval_id(missing) == 1

    def test_increments_past_existing(self, tmp_path: Path) -> None:
        (tmp_path / "0003.md").write_text("", encoding="utf-8")
        assert _next_eval_id(tmp_path) == 4

    def test_handles_leading_zeros(self, tmp_path: Path) -> None:
        (tmp_path / "0010.md").write_text("", encoding="utf-8")
        assert _next_eval_id(tmp_path) == 11


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------


class TestEvalCLIParsing:
    def _parse(self, *args: str) -> argparse.Namespace:
        parser = build_parser()
        return parser.parse_args(["eval", *args])

    def test_eval_command_parses(self) -> None:
        args = self._parse()
        assert args.command == "eval"

    def test_dry_run_flag(self) -> None:
        args = self._parse("--dry-run")
        assert args.dry_run is True

    def test_write_flag(self) -> None:
        args = self._parse("--write")
        assert args.write is True

    def test_dry_run_defaults_false(self) -> None:
        args = self._parse()
        assert args.dry_run is False

    def test_write_defaults_false(self) -> None:
        args = self._parse()
        assert args.write is False

    def test_repo_dir_from_common(self) -> None:
        args = self._parse("--repo-dir", "/tmp/myrepo")
        assert args.repo_dir == "/tmp/myrepo"

    def test_func_is_set(self) -> None:
        args = self._parse("--dry-run")
        assert callable(args.func)


# ---------------------------------------------------------------------------
# CLI integration: eval --dry-run
# ---------------------------------------------------------------------------


class TestEvalCLIIntegration:
    def _make_args(self, tmp_path: Path, dry_run: bool = True, write: bool = False) -> argparse.Namespace:
        return argparse.Namespace(
            dry_run=dry_run,
            write=write,
            repo_dir=str(tmp_path),
            agent=None,
        )

    def test_eval_dry_run_exits_zero(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path)
        exit_code = eval_cli(args)
        assert exit_code == 0

    def test_eval_dry_run_prints_table(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(tmp_path)
        eval_cli(args)
        captured = capsys.readouterr()
        assert "TOTAL" in captured.out
        assert "Startup" in captured.out

    def test_eval_dry_run_all_dimensions_present(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = self._make_args(tmp_path)
        eval_cli(args)
        captured = capsys.readouterr()
        for dim in EVALUATION_DIMENSIONS:
            assert dim in captured.out

    def test_nightshift_package_exports_eval_cli(self) -> None:
        assert hasattr(nightshift, "eval_cli")
        assert callable(nightshift.eval_cli)

    def test_nightshift_package_exports_run_eval_dry_run(self) -> None:
        assert hasattr(nightshift, "run_eval_dry_run")
        assert callable(nightshift.run_eval_dry_run)
