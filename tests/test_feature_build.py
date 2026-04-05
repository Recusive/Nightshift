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
            patch("nightshift.feature.sys.stdin.isatty", return_value=False),
            pytest.raises(nightshift.NightshiftError, match="requires confirmation"),
        ):
            nightshift.confirm_feature_build(state, yes=False)


class TestRunFinalVerification:
    def test_runs_tests_and_lint(self, tmp_path: Path) -> None:
        with patch(
            "nightshift.feature.run_test_command",
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
            "nightshift.feature.run_test_command",
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
            patch("nightshift.feature.command_exists", return_value=True),
            patch("nightshift.feature.profile_repo", return_value=profile),
            patch("nightshift.feature._plan_feature_with_agent", return_value=plan),
            patch("nightshift.feature.spawn_wave", side_effect=spawn_side_effect),
            patch("nightshift.feature.integrate_wave", side_effect=integrate_side_effect),
            patch(
                "nightshift.feature.run_e2e_tests",
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
                "nightshift.feature.run_final_verification",
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
            patch("nightshift.feature.command_exists", return_value=True),
            patch("nightshift.feature.profile_repo", return_value=profile),
            patch("nightshift.feature._plan_feature_with_agent", return_value=plan),
            patch("nightshift.feature.spawn_wave", return_value=_make_wave_result(1, 1)) as mock_spawn,
            patch(
                "nightshift.feature.integrate_wave",
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
            patch("nightshift.feature.command_exists", return_value=True),
            patch("nightshift.feature.spawn_wave", return_value=_make_wave_result(2, 2)) as mock_spawn,
            patch("nightshift.feature.integrate_wave", return_value=_make_integration_result(2)) as mock_integrate,
            patch(
                "nightshift.feature.run_e2e_tests",
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
                "nightshift.feature.run_final_verification",
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
