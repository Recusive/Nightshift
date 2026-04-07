"""Wave integrator for Loop 2 -- merges sub-agent work, runs tests, handles failures."""

from __future__ import annotations

from pathlib import Path

from nightshift.core.constants import (
    INTEGRATOR_MAX_FIX_ATTEMPTS,
    INTEGRATOR_TEST_TIMEOUT,
    print_status,
)
from nightshift.core.shell import git, run_test_command
from nightshift.core.types import (
    FixAttempt,
    IntegrationResult,
    NightshiftConfig,
    TaskCompletion,
    WaveResult,
    WorkOrder,
)
from nightshift.raven.subagent import spawn_task


def collect_wave_files(wave_result: WaveResult) -> list[str]:
    """Gather all files created or modified by completed tasks in a wave.

    Returns a deduplicated, sorted list of file paths.
    """
    seen: set[str] = set()
    for tc in wave_result["completed"]:
        for f in tc["files_created"]:
            seen.add(f)
        for f in tc["files_modified"]:
            seen.add(f)
    return sorted(seen)


def stage_files(repo_dir: Path, files: list[str]) -> list[str]:
    """Stage files that exist on disk via git add.

    Returns the list of files that were actually staged (exist on disk).
    """
    staged: list[str] = []
    for f in files:
        full_path = repo_dir / f
        if full_path.exists():
            git(repo_dir, "add", f, check=False)
            staged.append(f)
        else:
            print_status(f"[integrator] Skipping missing file: {f}")
    return staged


def run_test_suite(
    repo_dir: Path,
    test_command: str | None,
    *,
    timeout: int = INTEGRATOR_TEST_TIMEOUT,
) -> tuple[int, str]:
    """Run the repo's test suite and return (exit_code, output).

    If test_command is None, returns (0, "") -- no tests to run.
    """
    if test_command is None:
        return 0, ""

    return run_test_command(test_command, cwd=repo_dir, timeout=timeout)


def diagnose_failure(
    test_output: str,
    wave_result: WaveResult,
) -> tuple[int | None, str]:
    """Try to identify which task caused a test failure.

    Matches file paths mentioned in the test output against files touched
    by each completed task. Returns (task_id, diagnosis) or (None, diagnosis)
    if the responsible task cannot be determined.
    """
    if not test_output:
        return None, "No test output to diagnose"

    # Build a map of file -> task_id for all completed tasks.
    file_to_task: dict[str, int] = {}
    for tc in wave_result["completed"]:
        for f in tc["files_created"]:
            file_to_task[f] = tc["task_id"]
        for f in tc["files_modified"]:
            file_to_task[f] = tc["task_id"]

    # Count how many times each task's files appear in the test output.
    task_mentions: dict[int, int] = {}
    for filepath, task_id in file_to_task.items():
        # Check both the full path and the basename (test output varies).
        basename = Path(filepath).name
        count = test_output.count(filepath) + test_output.count(basename)
        if count > 0:
            task_mentions[task_id] = task_mentions.get(task_id, 0) + count

    if not task_mentions:
        return None, "Could not match test failures to any specific task"

    # The task with the most mentions is the likely culprit.
    suspect_id = max(task_mentions, key=lambda tid: task_mentions[tid])
    mention_count = task_mentions[suspect_id]
    return suspect_id, f"Task {suspect_id} files mentioned {mention_count} time(s) in test output"


def _build_fix_prompt(
    task_id: int,
    test_output: str,
    original_completion: TaskCompletion | None,
) -> str:
    """Build a prompt for a fix agent to repair failing tests."""
    notes = ""
    if original_completion is not None:
        notes = original_completion["notes"]

    return (
        f"The test suite is failing after task {task_id} was integrated.\n\n"
        f"## Test Output\n\n```\n{test_output[:4000]}\n```\n\n"
        f"## Original Task Notes\n\n{notes}\n\n"
        "## Your Job\n\n"
        "Fix the failing tests. Do NOT delete or weaken tests -- fix the "
        "underlying code so the tests pass. Return a task completion JSON "
        "when done."
    )


def _find_completion(wave_result: WaveResult, task_id: int) -> TaskCompletion | None:
    """Find a TaskCompletion by task_id in a wave result."""
    for tc in wave_result["completed"]:
        if tc["task_id"] == task_id:
            return tc
    return None


def integrate_wave(
    wave_result: WaveResult,
    *,
    repo_dir: Path,
    test_command: str | None,
    agent: str,
    log_dir: Path,
    config: NightshiftConfig,
    schema_path: str = "nightshift/schemas/task.schema.json",
    max_fix_attempts: int = INTEGRATOR_MAX_FIX_ATTEMPTS,
    test_timeout: int = INTEGRATOR_TEST_TIMEOUT,
) -> IntegrationResult:
    """Integrate a wave of sub-agent work into the repo.

    1. Collect all files from completed tasks.
    2. Stage them with git add.
    3. Run the test suite.
    4. If tests fail, diagnose and spawn fix agents (up to max_fix_attempts).
    5. Return an IntegrationResult.
    """
    wave_number = wave_result["wave"]
    print_status(f"[integrator] Integrating wave {wave_number}")

    # Step 1: Collect files.
    all_files = collect_wave_files(wave_result)
    print_status(f"[integrator] Collected {len(all_files)} file(s) from wave {wave_number}")

    # Step 2: Stage files.
    staged = stage_files(repo_dir, all_files)
    print_status(f"[integrator] Staged {len(staged)} file(s)")

    # Step 3: Handle no test runner.
    if test_command is None:
        print_status("[integrator] No test command configured -- skipping tests")
        return IntegrationResult(
            wave=wave_number,
            status="no_test_runner",
            tests_run=False,
            test_exit_code=0,
            test_output="",
            files_staged=staged,
            fix_attempts=[],
            failure_diagnosis="",
        )

    # Step 4: Run tests.
    exit_code, test_output = run_test_suite(repo_dir, test_command, timeout=test_timeout)
    print_status(f"[integrator] Test suite exit code: {exit_code}")

    if exit_code == 0:
        return IntegrationResult(
            wave=wave_number,
            status="passed",
            tests_run=True,
            test_exit_code=0,
            test_output=test_output,
            files_staged=staged,
            fix_attempts=[],
            failure_diagnosis="",
        )

    # Step 5: Tests failed -- diagnose and attempt fixes.
    fix_attempts: list[FixAttempt] = []
    diagnosis = ""

    for attempt in range(1, max_fix_attempts + 1):
        suspect_id, diag = diagnose_failure(test_output, wave_result)
        diagnosis = diag
        print_status(f"[integrator] Fix attempt {attempt}/{max_fix_attempts}: {diag}")

        if suspect_id is None:
            # Cannot identify the culprit -- give up on targeted fixes.
            print_status("[integrator] Cannot identify failing task -- stopping fix attempts")
            fix_attempts.append(
                FixAttempt(
                    task_id=0,
                    test_output=test_output[:2000],
                    fix_agent_notes="Could not identify responsible task",
                    tests_passed=False,
                )
            )
            break

        original = _find_completion(wave_result, suspect_id)
        fix_prompt = _build_fix_prompt(suspect_id, test_output, original)

        fix_order = WorkOrder(
            task_id=suspect_id,
            wave=wave_number,
            title=f"Fix failing tests for task {suspect_id}",
            prompt=fix_prompt,
            acceptance_criteria=["All tests pass"],
            estimated_files=3,
            depends_on=[],
            schema_path=schema_path,
        )

        fix_result = spawn_task(
            fix_order,
            agent=agent,
            repo_dir=repo_dir,
            log_dir=log_dir,
            timeout_seconds=test_timeout,
            config=config,
        )

        fix_notes = ""
        if fix_result is not None:
            fix_notes = fix_result["notes"]

        # Re-run tests after fix attempt.
        exit_code, test_output = run_test_suite(repo_dir, test_command, timeout=test_timeout)
        tests_passed = exit_code == 0

        fix_attempts.append(
            FixAttempt(
                task_id=suspect_id,
                test_output=test_output[:2000],
                fix_agent_notes=fix_notes,
                tests_passed=tests_passed,
            )
        )

        if tests_passed:
            print_status(f"[integrator] Fix attempt {attempt} succeeded -- tests pass")
            return IntegrationResult(
                wave=wave_number,
                status="passed",
                tests_run=True,
                test_exit_code=0,
                test_output=test_output,
                files_staged=staged,
                fix_attempts=fix_attempts,
                failure_diagnosis=diagnosis,
            )

        print_status(f"[integrator] Fix attempt {attempt} did not resolve failures")

    # All fix attempts exhausted.
    print_status(f"[integrator] Wave {wave_number} integration failed after {len(fix_attempts)} fix attempt(s)")
    return IntegrationResult(
        wave=wave_number,
        status="failed",
        tests_run=True,
        test_exit_code=exit_code,
        test_output=test_output,
        files_staged=staged,
        fix_attempts=fix_attempts,
        failure_diagnosis=diagnosis,
    )


def format_integration_result(result: IntegrationResult) -> str:
    """Render an IntegrationResult as human-readable markdown."""
    lines: list[str] = []

    lines.append(f"# Wave {result['wave']} Integration")
    lines.append("")
    lines.append(f"**Status**: {result['status']}")
    lines.append(f"**Tests run**: {result['tests_run']}")
    lines.append(f"**Files staged**: {len(result['files_staged'])}")
    lines.append("")

    if result["files_staged"]:
        lines.append("## Files Staged")
        lines.append("")
        for f in result["files_staged"]:
            lines.append(f"- {f}")
        lines.append("")

    if result["fix_attempts"]:
        lines.append(f"## Fix Attempts ({len(result['fix_attempts'])})")
        lines.append("")
        for i, fa in enumerate(result["fix_attempts"], 1):
            lines.append(f"### Attempt {i}")
            lines.append(f"- Target task: {fa['task_id']}")
            lines.append(f"- Tests passed: {fa['tests_passed']}")
            if fa["fix_agent_notes"]:
                lines.append(f"- Notes: {fa['fix_agent_notes']}")
            lines.append("")

    if result["failure_diagnosis"]:
        lines.append("## Diagnosis")
        lines.append("")
        lines.append(result["failure_diagnosis"])
        lines.append("")

    return "\n".join(lines)
