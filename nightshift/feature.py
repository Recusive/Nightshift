"""Loop 2 feature-build orchestration and persisted build state."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from nightshift.config import infer_lint_command, merge_config
from nightshift.constants import (
    DATA_VERSION,
    FEATURE_LOG_DIR,
    FEATURE_SCHEMA_PATH,
    FEATURE_STATE_PATH,
    FEATURE_VERIFY_TIMEOUT,
    print_status,
)
from nightshift.coordination import coordinate_wave, log_conflicts
from nightshift.cycle import command_for_agent
from nightshift.decomposer import decompose_plan
from nightshift.e2e import run_e2e_tests
from nightshift.errors import NightshiftError
from nightshift.integrator import integrate_wave
from nightshift.planner import build_plan_prompt, format_plan, parse_plan, scope_check
from nightshift.profiler import profile_repo
from nightshift.readiness import check_production_readiness
from nightshift.shell import command_exists, run_command, run_test_command
from nightshift.state import load_json, write_json
from nightshift.subagent import spawn_wave
from nightshift.summary import generate_feature_summary
from nightshift.types import (
    E2EResult,
    FeaturePlan,
    FeatureState,
    FeatureSummary,
    FeatureWaveState,
    FinalVerificationResult,
    FixAttempt,
    FrameworkInfo,
    IntegrationResult,
    NightshiftConfig,
    ReadinessCheck,
    ReadinessReport,
    RepoProfile,
    TaskCompletion,
    WaveResult,
)

SCRIPT_DIR = Path(__file__).resolve().parent


def feature_state_path(repo_dir: Path) -> Path:
    """Return the persisted feature-build state path for a repo."""
    return repo_dir / FEATURE_STATE_PATH


def feature_log_dir(repo_dir: Path) -> Path:
    """Return the log directory for feature-build orchestration."""
    return repo_dir / FEATURE_LOG_DIR


def _bundled_schema_path(relative_path: str) -> Path:
    """Resolve a bundled schema path in either repo or installed layouts."""
    primary = (SCRIPT_DIR / ".." / relative_path).resolve()
    if primary.exists():
        return primary
    fallback = (SCRIPT_DIR / relative_path).resolve()
    if fallback.exists():
        return fallback
    raise NightshiftError(f"Missing bundled schema file at {relative_path}")


def _build_profile(raw: dict[str, Any]) -> RepoProfile:
    languages: dict[str, int] = {}
    raw_languages = raw.get("languages")
    if isinstance(raw_languages, dict):
        for key, value in raw_languages.items():
            if isinstance(key, str) and isinstance(value, int):
                languages[key] = value

    frameworks: list[FrameworkInfo] = []
    raw_frameworks = raw.get("frameworks")
    if isinstance(raw_frameworks, list):
        for item in raw_frameworks:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            version = item.get("version")
            if isinstance(name, str) and isinstance(version, str):
                frameworks.append(FrameworkInfo(name=name, version=version))

    instruction_files = raw.get("instruction_files")
    top_level_dirs = raw.get("top_level_dirs")
    dependencies = raw.get("dependencies")
    conventions = raw.get("conventions")
    return RepoProfile(
        languages=languages,
        primary_language=str(raw.get("primary_language", "Unknown")),
        frameworks=frameworks,
        dependencies=[item for item in dependencies if isinstance(item, str)] if isinstance(dependencies, list) else [],
        conventions=[item for item in conventions if isinstance(item, str)] if isinstance(conventions, list) else [],
        package_manager=str(raw["package_manager"]) if isinstance(raw.get("package_manager"), str) else None,
        test_runner=str(raw["test_runner"]) if isinstance(raw.get("test_runner"), str) else None,
        instruction_files=[item for item in instruction_files if isinstance(item, str)]
        if isinstance(instruction_files, list)
        else [],
        top_level_dirs=[item for item in top_level_dirs if isinstance(item, str)]
        if isinstance(top_level_dirs, list)
        else [],
        has_monorepo_markers=bool(raw.get("has_monorepo_markers", False)),
        total_files=int(raw.get("total_files", 0)) if isinstance(raw.get("total_files"), int) else 0,
    )


def _build_task_completion(raw: dict[str, Any]) -> TaskCompletion:
    files_created = raw.get("files_created")
    files_modified = raw.get("files_modified")
    tests_written = raw.get("tests_written")
    return TaskCompletion(
        task_id=int(raw.get("task_id", 0)) if isinstance(raw.get("task_id"), int) else 0,
        status=str(raw.get("status", "blocked")),
        files_created=[item for item in files_created if isinstance(item, str)]
        if isinstance(files_created, list)
        else [],
        files_modified=[item for item in files_modified if isinstance(item, str)]
        if isinstance(files_modified, list)
        else [],
        tests_written=[item for item in tests_written if isinstance(item, str)]
        if isinstance(tests_written, list)
        else [],
        tests_passed=bool(raw.get("tests_passed", False)),
        notes=str(raw.get("notes", "")),
    )


def _build_wave_result(raw: object) -> WaveResult | None:
    if not isinstance(raw, dict):
        return None

    completed: list[TaskCompletion] = []
    raw_completed = raw.get("completed")
    if isinstance(raw_completed, list):
        for item in raw_completed:
            if isinstance(item, dict):
                completed.append(_build_task_completion(item))

    failed: list[TaskCompletion] = []
    raw_failed = raw.get("failed")
    if isinstance(raw_failed, list):
        for item in raw_failed:
            if isinstance(item, dict):
                failed.append(_build_task_completion(item))

    return WaveResult(
        wave=int(raw.get("wave", 0)) if isinstance(raw.get("wave"), int) else 0,
        completed=completed,
        failed=failed,
        total_tasks=int(raw.get("total_tasks", 0)) if isinstance(raw.get("total_tasks"), int) else 0,
    )


def _build_fix_attempt(raw: dict[str, Any]) -> FixAttempt:
    return FixAttempt(
        task_id=int(raw.get("task_id", 0)) if isinstance(raw.get("task_id"), int) else 0,
        test_output=str(raw.get("test_output", "")),
        fix_agent_notes=str(raw.get("fix_agent_notes", "")),
        tests_passed=bool(raw.get("tests_passed", False)),
    )


def _build_integration_result(raw: object) -> IntegrationResult | None:
    if not isinstance(raw, dict):
        return None

    files_staged = raw.get("files_staged")
    raw_fix_attempts = raw.get("fix_attempts")
    fix_attempts: list[FixAttempt] = []
    if isinstance(raw_fix_attempts, list):
        for item in raw_fix_attempts:
            if isinstance(item, dict):
                fix_attempts.append(_build_fix_attempt(item))

    return IntegrationResult(
        wave=int(raw.get("wave", 0)) if isinstance(raw.get("wave"), int) else 0,
        status=str(raw.get("status", "failed")),
        tests_run=bool(raw.get("tests_run", False)),
        test_exit_code=int(raw.get("test_exit_code", 1)) if isinstance(raw.get("test_exit_code"), int) else 1,
        test_output=str(raw.get("test_output", "")),
        files_staged=[item for item in files_staged if isinstance(item, str)] if isinstance(files_staged, list) else [],
        fix_attempts=fix_attempts,
        failure_diagnosis=str(raw.get("failure_diagnosis", "")),
    )


def _build_feature_wave_state(raw: dict[str, Any]) -> FeatureWaveState:
    raw_task_ids = raw.get("task_ids")
    return FeatureWaveState(
        wave=int(raw.get("wave", 0)) if isinstance(raw.get("wave"), int) else 0,
        task_ids=[item for item in raw_task_ids if isinstance(item, int)] if isinstance(raw_task_ids, list) else [],
        status=str(raw.get("status", "pending")),
        wave_result=_build_wave_result(raw.get("wave_result")),
        integration_result=_build_integration_result(raw.get("integration_result")),
    )


def _build_final_verification(raw: object) -> FinalVerificationResult | None:
    if not isinstance(raw, dict):
        return None
    return FinalVerificationResult(
        status=str(raw.get("status", "failed")),
        tests_run=bool(raw.get("tests_run", False)),
        lint_run=bool(raw.get("lint_run", False)),
        test_command=str(raw["test_command"]) if isinstance(raw.get("test_command"), str) else None,
        lint_command=str(raw["lint_command"]) if isinstance(raw.get("lint_command"), str) else None,
        test_exit_code=int(raw.get("test_exit_code", 1)) if isinstance(raw.get("test_exit_code"), int) else 1,
        lint_exit_code=int(raw.get("lint_exit_code", 1)) if isinstance(raw.get("lint_exit_code"), int) else 1,
        test_output=str(raw.get("test_output", "")),
        lint_output=str(raw.get("lint_output", "")),
    )


def _build_feature_summary(raw: object) -> FeatureSummary | None:
    if not isinstance(raw, dict):
        return None

    files_created = raw.get("files_created")
    files_modified = raw.get("files_modified")
    tests_added = raw.get("tests_added")
    patterns_detected = raw.get("patterns_detected")

    return FeatureSummary(
        files_created=[item for item in files_created if isinstance(item, str)]
        if isinstance(files_created, list)
        else [],
        files_modified=[item for item in files_modified if isinstance(item, str)]
        if isinstance(files_modified, list)
        else [],
        tests_added=[item for item in tests_added if isinstance(item, str)] if isinstance(tests_added, list) else [],
        total_tasks=int(raw.get("total_tasks", 0)) if isinstance(raw.get("total_tasks"), int) else 0,
        completed_tasks=int(raw.get("completed_tasks", 0)) if isinstance(raw.get("completed_tasks"), int) else 0,
        failed_tasks=int(raw.get("failed_tasks", 0)) if isinstance(raw.get("failed_tasks"), int) else 0,
        patterns_detected=[item for item in patterns_detected if isinstance(item, str)]
        if isinstance(patterns_detected, list)
        else [],
        description=str(raw.get("description", "")),
    )


def _build_readiness_check(raw: dict[str, Any]) -> ReadinessCheck:
    return ReadinessCheck(
        name=str(raw.get("name", "")),
        passed=bool(raw.get("passed", False)),
        details=str(raw.get("details", "")),
    )


def _build_readiness_report(raw: object) -> ReadinessReport | None:
    if not isinstance(raw, dict):
        return None

    checks: list[ReadinessCheck] = []
    raw_checks = raw.get("checks")
    if isinstance(raw_checks, list):
        for item in raw_checks:
            if isinstance(item, dict):
                checks.append(_build_readiness_check(item))

    return ReadinessReport(
        checks=checks,
        verdict=str(raw.get("verdict", "not_ready")),
        passed_count=int(raw.get("passed_count", 0)) if isinstance(raw.get("passed_count"), int) else 0,
        failed_count=int(raw.get("failed_count", 0)) if isinstance(raw.get("failed_count"), int) else 0,
    )


def _build_e2e_result(raw: object) -> E2EResult | None:
    if not isinstance(raw, dict):
        return None
    return E2EResult(
        status=str(raw.get("status", "skipped")),
        test_command=str(raw["test_command"]) if isinstance(raw.get("test_command"), str) else None,
        test_exit_code=int(raw.get("test_exit_code", 0)) if isinstance(raw.get("test_exit_code"), int) else 0,
        test_output=str(raw.get("test_output", "")),
        smoke_test_command=str(raw["smoke_test_command"]) if isinstance(raw.get("smoke_test_command"), str) else None,
        smoke_test_exit_code=int(raw.get("smoke_test_exit_code", 0))
        if isinstance(raw.get("smoke_test_exit_code"), int)
        else 0,
        smoke_test_output=str(raw.get("smoke_test_output", "")),
    )


def read_feature_state(state_path: Path) -> FeatureState:
    """Read and validate persisted feature-build state from disk."""
    raw = load_json(state_path)
    if not isinstance(raw, dict):
        raise NightshiftError(f"Feature state at {state_path} must be a JSON object")

    raw_plan = raw.get("plan")
    if not isinstance(raw_plan, dict):
        raise NightshiftError(f"Feature state at {state_path} is missing a valid plan")
    plan = parse_plan(json.dumps(raw_plan))
    if plan is None:
        raise NightshiftError(f"Feature state at {state_path} contains an invalid plan")

    raw_waves = raw.get("waves")
    waves: list[FeatureWaveState] = []
    if isinstance(raw_waves, list):
        for item in raw_waves:
            if isinstance(item, dict):
                waves.append(_build_feature_wave_state(item))

    return FeatureState(
        version=int(raw.get("version", DATA_VERSION)) if isinstance(raw.get("version"), int) else DATA_VERSION,
        feature_description=str(raw.get("feature_description", "")),
        agent=str(raw.get("agent", "")),
        status=str(raw.get("status", "failed")),
        scope_warning=str(raw.get("scope_warning", "")),
        current_wave=int(raw.get("current_wave", 0)) if isinstance(raw.get("current_wave"), int) else 0,
        profile=_build_profile(raw.get("profile", {}) if isinstance(raw.get("profile"), dict) else {}),
        plan=plan,
        waves=waves,
        e2e_result=_build_e2e_result(raw.get("e2e_result")),
        final_verification=_build_final_verification(raw.get("final_verification")),
        readiness=_build_readiness_report(raw.get("readiness")),
        summary=_build_feature_summary(raw.get("summary")),
    )


def write_feature_state(state_path: Path, state: FeatureState) -> None:
    """Persist feature-build state to disk."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(state_path, state)


def _plan_feature_with_agent(
    *,
    repo_dir: Path,
    profile: RepoProfile,
    feature_description: str,
    agent: str,
    log_dir: Path,
    config: NightshiftConfig,
) -> FeaturePlan:
    if not command_exists(agent):
        raise NightshiftError(f"`{agent}` is not installed or not on PATH.")

    prompt = build_plan_prompt(profile, feature_description)
    schema_path = _bundled_schema_path(FEATURE_SCHEMA_PATH)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "plan.log"
    message_path = log_dir / "plan.msg.json"

    cmd = command_for_agent(
        agent=agent,
        prompt=prompt,
        cwd=repo_dir,
        schema_path=schema_path,
        message_path=message_path,
        config=config,
    )
    exit_code, raw_output = run_command(cmd, cwd=repo_dir, log_path=log_path, timeout_seconds=FEATURE_VERIFY_TIMEOUT)
    if exit_code != 0:
        raise NightshiftError(f"Feature planner agent exited with code {exit_code}")

    parse_source = raw_output
    if agent == "codex" and message_path.exists():
        parse_source = message_path.read_text(encoding="utf-8")

    plan = parse_plan(parse_source)
    if plan is None:
        raise NightshiftError("Could not parse a valid feature plan from the agent output.")
    return plan


def _build_wave_states(plan: FeaturePlan, profile: RepoProfile) -> list[FeatureWaveState]:
    waves = decompose_plan(plan, profile)["waves"]
    return [
        FeatureWaveState(
            wave=index,
            task_ids=[order["task_id"] for order in wave],
            status="pending",
            wave_result=None,
            integration_result=None,
        )
        for index, wave in enumerate(waves, 1)
    ]


def new_feature_state(
    *,
    feature_description: str,
    agent: str,
    profile: RepoProfile,
    plan: FeaturePlan,
    scope_warning: str,
) -> FeatureState:
    """Create initial persisted state for a feature build."""
    return FeatureState(
        version=DATA_VERSION,
        feature_description=feature_description,
        agent=agent,
        status="awaiting_confirmation",
        scope_warning=scope_warning,
        current_wave=0,
        profile=profile,
        plan=plan,
        waves=_build_wave_states(plan, profile),
        e2e_result=None,
        final_verification=None,
        readiness=None,
        summary=None,
    )


def format_feature_status(state: FeatureState) -> str:
    """Render feature-build state as human-readable markdown."""
    lines: list[str] = []
    completed_waves = sum(1 for wave in state["waves"] if wave["status"] == "passed")
    total_waves = len(state["waves"])
    completed_tasks = 0
    failed_tasks = 0
    total_tasks = len(state["plan"]["tasks"])

    for wave in state["waves"]:
        if wave["wave_result"] is not None:
            completed_tasks += len(wave["wave_result"]["completed"])
            failed_tasks += len(wave["wave_result"]["failed"])

    lines.append(f"# Feature Build: {state['plan']['feature']}")
    lines.append("")
    lines.append(f"**Status**: {state['status']}")
    lines.append(f"**Agent**: {state['agent']}")
    lines.append(f"**Current wave**: {state['current_wave'] or '-'}")
    lines.append(f"**Waves**: {completed_waves}/{total_waves} passed")
    lines.append(f"**Tasks**: {completed_tasks}/{total_tasks} completed")
    if failed_tasks:
        lines.append(f"**Failed tasks**: {failed_tasks}")
    if state["scope_warning"]:
        lines.append(f"**Scope warning**: {state['scope_warning']}")
    lines.append("")

    for wave in state["waves"]:
        lines.append(f"## Wave {wave['wave']} -- {wave['status']}")
        lines.append("")
        lines.append(f"Tasks: {', '.join(str(task_id) for task_id in wave['task_ids']) or '(none)'}")
        if wave["integration_result"] is not None:
            lines.append(f"Integration: {wave['integration_result']['status']}")
        if wave["wave_result"] is not None and wave["wave_result"]["failed"]:
            failed_ids = ", ".join(str(item["task_id"]) for item in wave["wave_result"]["failed"])
            lines.append(f"Blocked tasks: {failed_ids}")
        lines.append("")

    e2e = state["e2e_result"]
    if e2e is not None:
        lines.append("## E2E Tests")
        lines.append("")
        lines.append(f"Status: {e2e['status']}")
        if e2e["test_command"] is not None:
            lines.append(f"Tests: exit {e2e['test_exit_code']} via `{e2e['test_command']}`")
        if e2e["smoke_test_command"] is not None:
            lines.append(f"Smoke test: exit {e2e['smoke_test_exit_code']} via `{e2e['smoke_test_command']}`")
        lines.append("")

    final = state["final_verification"]
    if final is not None:
        lines.append("## Final Verification")
        lines.append("")
        lines.append(f"Status: {final['status']}")
        if final["test_command"] is not None:
            lines.append(f"Tests: exit {final['test_exit_code']} via `{final['test_command']}`")
        if final["lint_command"] is not None:
            lines.append(f"Lint: exit {final['lint_exit_code']} via `{final['lint_command']}`")
        lines.append("")

    readiness = state["readiness"]
    if readiness is not None:
        lines.append("## Production Readiness")
        lines.append("")
        lines.append(
            f"Verdict: **{readiness['verdict']}** ({readiness['passed_count']} passed, {readiness['failed_count']} failed)"
        )
        for check in readiness["checks"]:
            mark = "PASS" if check["passed"] else "FAIL"
            lines.append(f"  [{mark}] {check['name']}: {check['details'].splitlines()[0]}")
        lines.append("")

    summary = state["summary"]
    if summary is not None:
        lines.append("## Summary")
        lines.append("")
        lines.append(summary["description"])
        if summary["files_created"]:
            lines.append(f"**Files created**: {', '.join(summary['files_created'])}")
        if summary["files_modified"]:
            lines.append(f"**Files modified**: {', '.join(summary['files_modified'])}")
        if summary["tests_added"]:
            lines.append(f"**Tests added**: {len(summary['tests_added'])}")
        if summary["patterns_detected"]:
            lines.append(f"**Patterns**: {', '.join(summary['patterns_detected'])}")
        lines.append("")

    return "\n".join(lines)


def confirm_feature_build(state: FeatureState, *, yes: bool) -> None:
    """Display the plan and require confirmation before spawning sub-agents."""
    print_status(format_plan(state["plan"]))
    if state["scope_warning"]:
        print_status("")
        print_status(f"WARNING: {state['scope_warning']}")

    if yes:
        return

    if not sys.stdin.isatty():
        raise NightshiftError("Feature build requires confirmation. Re-run with --yes.")

    try:
        choice = input("Proceed with build? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt) as exc:
        raise NightshiftError("Feature build cancelled.") from exc

    if choice not in {"y", "yes"}:
        raise NightshiftError("Feature build cancelled.")


def run_final_verification(
    *,
    repo_dir: Path,
    test_command: str | None,
    lint_command: str | None,
    timeout_seconds: int = FEATURE_VERIFY_TIMEOUT,
) -> FinalVerificationResult:
    """Run final tests and linting after all waves have integrated."""
    tests_run = test_command is not None
    lint_run = lint_command is not None
    test_exit_code = 0
    lint_exit_code = 0
    test_output = ""
    lint_output = ""

    if test_command is not None:
        test_exit_code, test_output = run_test_command(test_command, cwd=repo_dir, timeout=timeout_seconds)
    if lint_command is not None:
        lint_exit_code, lint_output = run_test_command(lint_command, cwd=repo_dir, timeout=timeout_seconds)

    status = "passed" if test_exit_code == 0 and lint_exit_code == 0 else "failed"
    return FinalVerificationResult(
        status=status,
        tests_run=tests_run,
        lint_run=lint_run,
        test_command=test_command,
        lint_command=lint_command,
        test_exit_code=test_exit_code,
        lint_exit_code=lint_exit_code,
        test_output=test_output,
        lint_output=lint_output,
    )


def build_feature(
    *,
    repo_dir: Path,
    feature_description: str | None,
    agent: str | None,
    yes: bool,
    resume: bool,
    status_only: bool,
) -> int:
    """Run the full Loop 2 feature-build pipeline."""
    config = merge_config(repo_dir)
    state_path = feature_state_path(repo_dir)

    if status_only:
        state = read_feature_state(state_path)
        print_status(format_feature_status(state))
        return 0

    if resume:
        state = read_feature_state(state_path)
        effective_agent = agent or state["agent"]
    else:
        if not feature_description:
            raise NightshiftError("Feature description is required unless using --resume or --status.")
        if agent is None:
            raise NightshiftError("Agent is required for a new feature build.")
        profile = profile_repo(repo_dir)
        plan = _plan_feature_with_agent(
            repo_dir=repo_dir,
            profile=profile,
            feature_description=feature_description,
            agent=agent,
            log_dir=feature_log_dir(repo_dir),
            config=config,
        )
        state = new_feature_state(
            feature_description=feature_description,
            agent=agent,
            profile=profile,
            plan=plan,
            scope_warning=scope_check(plan) or "",
        )
        write_feature_state(state_path, state)
        effective_agent = agent

    if not effective_agent:
        raise NightshiftError("Could not determine which agent should run this feature build.")
    if not command_exists(effective_agent):
        raise NightshiftError(f"`{effective_agent}` is not installed or not on PATH.")

    if state["status"] == "completed":
        print_status(format_feature_status(state))
        return 0

    if state["status"] == "awaiting_confirmation":
        confirm_feature_build(state, yes=yes)
        state["status"] = "building"
        write_feature_state(state_path, state)

    decomposition = decompose_plan(state["plan"], state["profile"])
    wave_states = state["waves"]
    if len(wave_states) != len(decomposition["waves"]):
        raise NightshiftError("Feature state is out of sync with the stored plan.")

    log_dir = feature_log_dir(repo_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    for wave_index, work_orders in enumerate(decomposition["waves"], 1):
        wave_state = wave_states[wave_index - 1]
        if wave_state["status"] == "passed":
            continue

        state["current_wave"] = wave_index
        wave_state["status"] = "running"
        write_feature_state(state_path, state)

        coordinated_orders = coordinate_wave(work_orders)

        wave_log_dir = log_dir / f"wave-{wave_index}"
        wave_result = spawn_wave(
            coordinated_orders,
            agent=effective_agent,
            repo_dir=repo_dir,
            log_dir=wave_log_dir,
            config=config,
        )

        log_conflicts(wave_result)

        integration_result = integrate_wave(
            wave_result,
            repo_dir=repo_dir,
            test_command=state["profile"]["test_runner"],
            agent=effective_agent,
            log_dir=wave_log_dir,
            config=config,
        )

        wave_state["wave_result"] = wave_result
        wave_state["integration_result"] = integration_result

        if wave_result["failed"] or integration_result["status"] != "passed":
            wave_state["status"] = "failed"
            state["status"] = "failed"
            write_feature_state(state_path, state)
            print_status(format_feature_status(state))
            return 1

        wave_state["status"] = "passed"
        write_feature_state(state_path, state)

    state["current_wave"] = 0
    e2e = run_e2e_tests(repo_dir=repo_dir)
    state["e2e_result"] = e2e
    write_feature_state(state_path, state)

    if e2e["status"] == "failed":
        state["status"] = "failed"
        write_feature_state(state_path, state)
        print_status(format_feature_status(state))
        return 1

    state["final_verification"] = run_final_verification(
        repo_dir=repo_dir,
        test_command=state["profile"]["test_runner"],
        lint_command=infer_lint_command(repo_dir),
    )
    fv = state["final_verification"]
    state["status"] = "completed" if fv is not None and fv["status"] == "passed" else "failed"
    state["readiness"] = check_production_readiness(state, repo_dir, config)
    state["summary"] = generate_feature_summary(state)
    write_feature_state(state_path, state)
    print_status(format_feature_status(state))
    return 0 if state["status"] == "completed" else 1
