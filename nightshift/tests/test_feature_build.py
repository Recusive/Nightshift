"""Tests for the Loop 2 feature-build orchestrator."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nightshift


def _make_profile(**overrides: object) -> nightshift.RepoProfile:
    defaults: dict[str, object] = {
        "languages": {"Python": 12},
        "primary_language": "Python",
        "frameworks": [],
        "dependencies": [],
        "conventions": [],
        "package_manager": None,
        "test_runner": "python3 -m pytest",
        "instruction_files": ["CLAUDE.md"],
        "top_level_dirs": ["nightshift", "tests"],
        "has_monorepo_markers": False,
        "total_files": 42,
    }
    defaults.update(overrides)
    return nightshift.RepoProfile(**defaults)


def _make_plan() -> nightshift.FeaturePlan:
    return nightshift.FeaturePlan(
        feature="Add audit trail",
        architecture=nightshift.ArchitectureDoc(
            overview="Add an audit trail model and expose it in the admin UI.",
            tech_choices=["Reuse the existing SQLAlchemy models"],
            data_model_changes=["Add audit_events table"],
            api_changes=["GET /api/audit-events"],
            frontend_changes=["Add audit events page"],
            integration_points=["Admin navigation"],
        ),
        tasks=[
            nightshift.PlanTask(
                id=1,
                title="Create audit storage",
                description="Add the data model and persistence helpers",
                depends_on=[],
                parallel=True,
                acceptance_criteria=["Model persists audit events"],
                estimated_files=3,
            ),
            nightshift.PlanTask(
                id=2,
                title="Expose audit UI",
                description="Render stored events in the admin area",
                depends_on=[1],
                parallel=False,
                acceptance_criteria=["Admin page lists stored events"],
                estimated_files=2,
            ),
        ],
        test_plan=nightshift.TestPlan(
            unit_tests=["Model serializes audit events"],
            integration_tests=["API returns audit events"],
            e2e_tests=["Admin can load the audit page"],
            edge_cases=["Empty event list renders gracefully"],
        ),
    )


def _make_wave_result(wave: int, task_id: int) -> nightshift.WaveResult:
    completion = nightshift.TaskCompletion(
        task_id=task_id,
        status="done",
        files_created=[f"file-{task_id}.py"],
        files_modified=[],
        tests_written=[f"test task {task_id}"],
        tests_passed=True,
        notes="done",
    )
    return nightshift.WaveResult(
        wave=wave,
        completed=[completion],
        failed=[],
        total_tasks=1,
    )


def _make_integration_result(wave: int) -> nightshift.IntegrationResult:
    return nightshift.IntegrationResult(
        wave=wave,
        status="passed",
        tests_run=True,
        test_exit_code=0,
        test_output="ok",
        files_staged=[f"file-{wave}.py"],
        fix_attempts=[],
        failure_diagnosis="",
    )


class TestInferLintCommand:
    def test_prefers_package_json_lint_ci(self, tmp_path: Path) -> None:
        package_json = {
            "scripts": {
                "lint:ci": "eslint . --max-warnings=0",
                "lint": "eslint .",
            }
        }
        (tmp_path / "package.json").write_text(json.dumps(package_json), encoding="utf-8")
        assert nightshift.infer_lint_command(tmp_path) == "npm run lint:ci"

    def test_detects_ruff_in_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n", encoding="utf-8")
        assert nightshift.infer_lint_command(tmp_path) == "python3 -m ruff check ."

    def test_returns_none_without_signal(self, tmp_path: Path) -> None:
        assert nightshift.infer_lint_command(tmp_path) is None


class TestBuildParser:
    def test_build_subcommand_accepts_feature(self) -> None:
        parser = nightshift.build_parser()
        args = parser.parse_args(["build", "Add auth", "--yes"])
        assert args.command == "build"
        assert args.feature == "Add auth"
        assert args.yes is True

    def test_build_subcommand_supports_resume(self) -> None:
        parser = nightshift.build_parser()
        args = parser.parse_args(["build", "--resume"])
        assert args.resume is True
        assert args.feature is None

    def test_build_subcommand_supports_status(self) -> None:
        parser = nightshift.build_parser()
        args = parser.parse_args(["build", "--status"])
        assert args.status is True
        assert args.feature is None


class TestFeatureStateRoundTrip:
    def test_round_trip_preserves_plan_and_waves(self, tmp_path: Path) -> None:
        state = nightshift.new_feature_state(
            feature_description="Add audit trail",
            agent="claude",
            profile=_make_profile(),
            plan=_make_plan(),
            scope_warning="",
        )

        state_path = nightshift.feature_state_path(tmp_path)
        nightshift.write_feature_state(state_path, state)
        loaded = nightshift.read_feature_state(state_path)

        assert loaded["feature_description"] == "Add audit trail"
        assert loaded["plan"]["feature"] == "Add audit trail"
        assert len(loaded["waves"]) == 2
        assert loaded["waves"][0]["task_ids"] == [1]
        assert loaded["waves"][1]["task_ids"] == [2]


class TestConfirmFeatureBuild:
    def test_requires_yes_when_not_interactive(self) -> None:
        state = nightshift.new_feature_state(
            feature_description="Add audit trail",
            agent="claude",
            profile=_make_profile(),
            plan=_make_plan(),
            scope_warning="",
        )
        with (
            patch("nightshift.raven.feature.sys.stdin.isatty", return_value=False),
            pytest.raises(nightshift.NightshiftError, match="requires confirmation"),
        ):
            nightshift.confirm_feature_build(state, yes=False)


class TestRunFinalVerification:
    def test_runs_tests_and_lint(self, tmp_path: Path) -> None:
        with patch(
            "nightshift.raven.feature.run_test_command",
            side_effect=[(0, "tests ok"), (0, "lint ok")],
        ) as mock_run:
            result = nightshift.run_final_verification(
                repo_dir=tmp_path,
                test_command="python3 -m pytest",
                lint_command="python3 -m ruff check .",
            )

        assert result["status"] == "passed"
        assert result["tests_run"] is True
        assert result["lint_run"] is True
        assert mock_run.call_count == 2

    def test_fails_when_lint_fails(self, tmp_path: Path) -> None:
        with patch(
            "nightshift.raven.feature.run_test_command",
            side_effect=[(0, "tests ok"), (1, "lint failed")],
        ):
            result = nightshift.run_final_verification(
                repo_dir=tmp_path,
                test_command="python3 -m pytest",
                lint_command="python3 -m ruff check .",
            )

        assert result["status"] == "failed"
        assert result["lint_exit_code"] == 1


class TestBuildFeature:
    def test_runs_waves_in_order_then_verifies(self, tmp_path: Path) -> None:
        plan = _make_plan()
        profile = _make_profile()
        events: list[str] = []
        wave_results = [_make_wave_result(1, 1), _make_wave_result(2, 2)]
        integration_results = [_make_integration_result(1), _make_integration_result(2)]

        def spawn_side_effect(*args: object, **kwargs: object) -> nightshift.WaveResult:
            wave = kwargs["wave"] if "wave" in kwargs else args[0]
            wave_number = wave[0]["wave"]
            events.append(f"spawn-{wave_number}")
            return wave_results[wave_number - 1]

        def integrate_side_effect(*args: object, **kwargs: object) -> nightshift.IntegrationResult:
            wave_result = args[0]
            events.append(f"integrate-{wave_result['wave']}")
            return integration_results[wave_result["wave"] - 1]

        with (
            patch("nightshift.raven.feature.command_exists", return_value=True),
            patch("nightshift.raven.feature.profile_repo", return_value=profile),
            patch("nightshift.raven.feature._plan_feature_with_agent", return_value=plan),
            patch("nightshift.raven.feature.spawn_wave", side_effect=spawn_side_effect),
            patch("nightshift.raven.feature.integrate_wave", side_effect=integrate_side_effect),
            patch(
                "nightshift.raven.feature.run_e2e_tests",
                return_value=nightshift.E2EResult(
                    status="passed",
                    test_command="python3 -m pytest",
                    test_exit_code=0,
                    test_output="ok",
                    smoke_test_command=None,
                    smoke_test_exit_code=0,
                    smoke_test_output="",
                ),
            ),
            patch(
                "nightshift.raven.feature.run_final_verification",
                return_value=nightshift.FinalVerificationResult(
                    status="passed",
                    tests_run=True,
                    lint_run=True,
                    test_command="python3 -m pytest",
                    lint_command="python3 -m ruff check .",
                    test_exit_code=0,
                    lint_exit_code=0,
                    test_output="ok",
                    lint_output="ok",
                ),
            ),
        ):
            result = nightshift.build_feature(
                repo_dir=tmp_path,
                feature_description="Add audit trail",
                agent="claude",
                yes=True,
                resume=False,
                status_only=False,
            )

        state = nightshift.read_feature_state(nightshift.feature_state_path(tmp_path))
        assert result == 0
        assert state["status"] == "completed"
        assert events == ["spawn-1", "integrate-1", "spawn-2", "integrate-2"]
        assert state["waves"][0]["status"] == "passed"
        assert state["waves"][1]["status"] == "passed"
        assert state["e2e_result"] is not None
        assert state["e2e_result"]["status"] == "passed"
        assert state["final_verification"] is not None
        assert state["final_verification"]["status"] == "passed"

    def test_stops_when_a_wave_fails(self, tmp_path: Path) -> None:
        plan = _make_plan()
        profile = _make_profile()

        with (
            patch("nightshift.raven.feature.command_exists", return_value=True),
            patch("nightshift.raven.feature.profile_repo", return_value=profile),
            patch("nightshift.raven.feature._plan_feature_with_agent", return_value=plan),
            patch("nightshift.raven.feature.spawn_wave", return_value=_make_wave_result(1, 1)) as mock_spawn,
            patch(
                "nightshift.raven.feature.integrate_wave",
                return_value=nightshift.IntegrationResult(
                    wave=1,
                    status="failed",
                    tests_run=True,
                    test_exit_code=1,
                    test_output="broken",
                    files_staged=["file-1.py"],
                    fix_attempts=[],
                    failure_diagnosis="Task 1 broke tests",
                ),
            ) as mock_integrate,
        ):
            result = nightshift.build_feature(
                repo_dir=tmp_path,
                feature_description="Add audit trail",
                agent="claude",
                yes=True,
                resume=False,
                status_only=False,
            )

        state = nightshift.read_feature_state(nightshift.feature_state_path(tmp_path))
        assert result == 1
        assert state["status"] == "failed"
        assert state["waves"][0]["status"] == "failed"
        assert mock_spawn.call_count == 1
        assert mock_integrate.call_count == 1

    def test_resume_skips_completed_waves(self, tmp_path: Path) -> None:
        state = nightshift.new_feature_state(
            feature_description="Add audit trail",
            agent="claude",
            profile=_make_profile(),
            plan=_make_plan(),
            scope_warning="",
        )
        state["status"] = "building"
        state["current_wave"] = 2
        state["waves"][0]["status"] = "passed"
        state["waves"][0]["wave_result"] = _make_wave_result(1, 1)
        state["waves"][0]["integration_result"] = _make_integration_result(1)
        nightshift.write_feature_state(nightshift.feature_state_path(tmp_path), state)

        with (
            patch("nightshift.raven.feature.command_exists", return_value=True),
            patch("nightshift.raven.feature.spawn_wave", return_value=_make_wave_result(2, 2)) as mock_spawn,
            patch(
                "nightshift.raven.feature.integrate_wave", return_value=_make_integration_result(2)
            ) as mock_integrate,
            patch(
                "nightshift.raven.feature.run_e2e_tests",
                return_value=nightshift.E2EResult(
                    status="passed",
                    test_command="python3 -m pytest",
                    test_exit_code=0,
                    test_output="ok",
                    smoke_test_command=None,
                    smoke_test_exit_code=0,
                    smoke_test_output="",
                ),
            ),
            patch(
                "nightshift.raven.feature.run_final_verification",
                return_value=nightshift.FinalVerificationResult(
                    status="passed",
                    tests_run=True,
                    lint_run=False,
                    test_command="python3 -m pytest",
                    lint_command=None,
                    test_exit_code=0,
                    lint_exit_code=0,
                    test_output="ok",
                    lint_output="",
                ),
            ),
        ):
            result = nightshift.build_feature(
                repo_dir=tmp_path,
                feature_description=None,
                agent=None,
                yes=True,
                resume=True,
                status_only=False,
            )

        loaded = nightshift.read_feature_state(nightshift.feature_state_path(tmp_path))
        assert result == 0
        assert loaded["status"] == "completed"
        assert mock_spawn.call_count == 1
        assert mock_integrate.call_count == 1

    def test_status_prints_persisted_progress(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        state = nightshift.new_feature_state(
            feature_description="Add audit trail",
            agent="claude",
            profile=_make_profile(),
            plan=_make_plan(),
            scope_warning="Break into phases if the admin UI grows beyond five files.",
        )
        nightshift.write_feature_state(nightshift.feature_state_path(tmp_path), state)

        result = nightshift.build_feature(
            repo_dir=tmp_path,
            feature_description=None,
            agent=None,
            yes=False,
            resume=False,
            status_only=True,
        )

        captured = capsys.readouterr()
        assert result == 0
        assert "Add audit trail" in captured.out
        assert "awaiting_confirmation" in captured.out
        assert "Scope warning" in captured.out

    def test_status_includes_summary_section_when_present(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        state = nightshift.new_feature_state(
            feature_description="Add audit trail",
            agent="claude",
            profile=_make_profile(),
            plan=_make_plan(),
            scope_warning="",
        )
        state["status"] = "completed"
        state["summary"] = nightshift.FeatureSummary(
            files_created=["audit/models.py"],
            files_modified=["settings/config.py"],
            tests_added=["test audit model"],
            total_tasks=2,
            completed_tasks=2,
            failed_tasks=0,
            patterns_detected=["New or modified API endpoints"],
            description="Built 'Add audit trail' (2/2 tasks completed) touching 2 file(s).",
        )
        nightshift.write_feature_state(nightshift.feature_state_path(tmp_path), state)

        result = nightshift.build_feature(
            repo_dir=tmp_path,
            feature_description=None,
            agent=None,
            yes=False,
            resume=False,
            status_only=True,
        )

        captured = capsys.readouterr()
        assert result == 0
        assert "## Summary" in captured.out
        assert "audit/models.py" in captured.out
        assert "settings/config.py" in captured.out
        assert "New or modified API endpoints" in captured.out

    def test_completed_build_writes_summary_md(self, tmp_path: Path) -> None:
        plan = _make_plan()
        profile = _make_profile()
        wave_results = [_make_wave_result(1, 1), _make_wave_result(2, 2)]
        integration_results = [_make_integration_result(1), _make_integration_result(2)]

        def spawn_side_effect(*args: object, **kwargs: object) -> nightshift.WaveResult:
            work_orders = args[0] if args else kwargs.get("work_orders", [])
            assert isinstance(work_orders, list)
            wave_number = work_orders[0]["wave"]
            return wave_results[wave_number - 1]

        def integrate_side_effect(*args: object, **kwargs: object) -> nightshift.IntegrationResult:
            wave_result = args[0]
            assert isinstance(wave_result, dict)
            return integration_results[wave_result["wave"] - 1]

        with (
            patch("nightshift.raven.feature.command_exists", return_value=True),
            patch("nightshift.raven.feature.profile_repo", return_value=profile),
            patch("nightshift.raven.feature._plan_feature_with_agent", return_value=plan),
            patch("nightshift.raven.feature.spawn_wave", side_effect=spawn_side_effect),
            patch("nightshift.raven.feature.integrate_wave", side_effect=integrate_side_effect),
            patch(
                "nightshift.raven.feature.run_e2e_tests",
                return_value=nightshift.E2EResult(
                    status="passed",
                    test_command=None,
                    test_exit_code=0,
                    test_output="",
                    smoke_test_command=None,
                    smoke_test_exit_code=0,
                    smoke_test_output="",
                ),
            ),
            patch(
                "nightshift.raven.feature.run_final_verification",
                return_value=nightshift.FinalVerificationResult(
                    status="passed",
                    tests_run=True,
                    lint_run=False,
                    test_command="python3 -m pytest",
                    lint_command=None,
                    test_exit_code=0,
                    lint_exit_code=0,
                    test_output="ok",
                    lint_output="",
                ),
            ),
        ):
            result = nightshift.build_feature(
                repo_dir=tmp_path,
                feature_description="Add audit trail",
                agent="claude",
                yes=True,
                resume=False,
                status_only=False,
            )

        assert result == 0
        summary_path = nightshift.feature_log_dir(tmp_path) / "summary.md"
        assert summary_path.exists(), "summary.md should be written after a successful build"
        content = summary_path.read_text(encoding="utf-8")
        assert "## Feature Build Summary" in content
        assert "Tasks" in content


class TestWriteSummaryMd:
    def test_writes_summary_md_to_log_dir(self, tmp_path: Path) -> None:
        summary = nightshift.FeatureSummary(
            files_created=["auth/models.py", "auth/views.py"],
            files_modified=["settings/config.py"],
            tests_added=["test login", "test logout"],
            total_tasks=3,
            completed_tasks=3,
            failed_tasks=0,
            patterns_detected=["New or modified API endpoints", "2 new Python module(s)"],
            description="Built 'Add auth' (3/3 tasks completed) touching 3 file(s).",
        )
        log_dir = tmp_path / "feature-build"
        path = nightshift.write_summary_md(summary, log_dir)

        assert path == log_dir / "summary.md"
        assert path.exists()

    def test_summary_md_contains_expected_sections(self, tmp_path: Path) -> None:
        summary = nightshift.FeatureSummary(
            files_created=["auth/models.py"],
            files_modified=["settings/config.py"],
            tests_added=["test login"],
            total_tasks=2,
            completed_tasks=2,
            failed_tasks=0,
            patterns_detected=["New or modified API endpoints"],
            description="Built 'Add auth' (2/2 tasks completed) touching 2 file(s).",
        )
        log_dir = tmp_path / "feature-build"
        nightshift.write_summary_md(summary, log_dir)
        content = (log_dir / "summary.md").read_text(encoding="utf-8")

        assert "## Feature Build Summary" in content
        assert "Built 'Add auth'" in content
        assert "### Files Created" in content
        assert "`auth/models.py`" in content
        assert "### Files Modified" in content
        assert "`settings/config.py`" in content
        assert "### Tests Added" in content
        assert "test login" in content
        assert "### Patterns" in content
        assert "New or modified API endpoints" in content

    def test_summary_md_omits_empty_sections(self, tmp_path: Path) -> None:
        summary = nightshift.FeatureSummary(
            files_created=[],
            files_modified=["settings/config.py"],
            tests_added=[],
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            patterns_detected=[],
            description="Built 'Tweak config' (1/1 tasks completed) touching 1 file(s).",
        )
        log_dir = tmp_path / "feature-build"
        nightshift.write_summary_md(summary, log_dir)
        content = (log_dir / "summary.md").read_text(encoding="utf-8")

        assert "### Files Created" not in content
        assert "### Tests Added" not in content
        assert "### Patterns" not in content
        assert "### Files Modified" in content

    def test_summary_md_creates_log_dir_if_missing(self, tmp_path: Path) -> None:
        summary = nightshift.FeatureSummary(
            files_created=[],
            files_modified=[],
            tests_added=[],
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            patterns_detected=[],
            description="Built 'X' (1/1 tasks completed).",
        )
        nested_dir = tmp_path / "nested" / "log" / "dir"
        assert not nested_dir.exists()
        nightshift.write_summary_md(summary, nested_dir)
        assert (nested_dir / "summary.md").exists()

    def test_summary_md_includes_failed_tasks_when_nonzero(self, tmp_path: Path) -> None:
        summary = nightshift.FeatureSummary(
            files_created=[],
            files_modified=[],
            tests_added=[],
            total_tasks=3,
            completed_tasks=2,
            failed_tasks=1,
            patterns_detected=[],
            description="Built 'X' (build failed: 2/3 tasks).",
        )
        nightshift.write_summary_md(summary, tmp_path)
        content = (tmp_path / "summary.md").read_text(encoding="utf-8")
        assert "Failed tasks" in content
