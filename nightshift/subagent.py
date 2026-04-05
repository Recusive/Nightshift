"""Sub-agent spawner for Loop 2 -- executes work orders via codex or claude CLI."""

from __future__ import annotations

import contextlib
from pathlib import Path

from nightshift.constants import (
    DECOMPOSER_MAX_RETRIES,
    SUBAGENT_DEFAULT_TIMEOUT,
    SUBAGENT_MAX_TURNS,
    print_status,
)
from nightshift.cycle import extract_json
from nightshift.errors import NightshiftError
from nightshift.shell import run_command
from nightshift.types import NightshiftConfig, TaskCompletion, WaveResult, WorkOrder

_TASK_COMPLETION_REQUIRED_KEYS = {
    "task_id",
    "status",
    "files_created",
    "files_modified",
    "tests_written",
    "tests_passed",
    "notes",
}


def _build_subagent_command(
    *,
    agent: str,
    prompt: str,
    cwd: Path,
    message_path: Path,
    schema_path: str,
    config: NightshiftConfig,
) -> list[str]:
    """Build the CLI command to invoke a sub-agent for a work order."""
    if agent == "codex":
        full_schema_path = cwd / schema_path
        return [
            "codex",
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--json",
            "--output-schema",
            str(full_schema_path),
            "--output-last-message",
            str(message_path),
            "--model",
            config["codex_model"],
            "-c",
            f'reasoning_effort="{config["codex_thinking"]}"',
            prompt,
        ]
    if agent == "claude":
        return [
            "claude",
            "-p",
            prompt,
            "--max-turns",
            str(SUBAGENT_MAX_TURNS),
            "--model",
            config["claude_model"],
            "--effort",
            config["claude_effort"],
            "--verbose",
        ]
    raise NightshiftError(f"Unsupported agent: {agent}")


def _validate_task_completion(data: dict[str, object], task_id: int) -> bool:
    """Check that parsed JSON has all required TaskCompletion fields."""
    if not _TASK_COMPLETION_REQUIRED_KEYS.issubset(data.keys()):
        return False
    if data.get("task_id") != task_id:
        return False
    if data.get("status") not in ("done", "blocked"):
        return False
    return all(isinstance(data.get(key), list) for key in ("files_created", "files_modified", "tests_written"))


def _parse_task_completion(
    raw_output: str,
    task_id: int,
) -> TaskCompletion | None:
    """Parse agent output into a TaskCompletion.

    Returns None if the output cannot be parsed or is invalid.
    """
    parsed = extract_json(raw_output)
    if parsed is None:
        return None
    if not _validate_task_completion(parsed, task_id):
        return None
    return TaskCompletion(
        task_id=int(parsed["task_id"]),
        status=str(parsed["status"]),
        files_created=list(parsed.get("files_created", [])),
        files_modified=list(parsed.get("files_modified", [])),
        tests_written=list(parsed.get("tests_written", [])),
        tests_passed=bool(parsed.get("tests_passed", False)),
        notes=str(parsed.get("notes", "")),
    )


def _make_error_completion(task_id: int, reason: str) -> TaskCompletion:
    """Create a synthetic blocked TaskCompletion for agent failures."""
    return TaskCompletion(
        task_id=task_id,
        status="blocked",
        files_created=[],
        files_modified=[],
        tests_written=[],
        tests_passed=False,
        notes=reason,
    )


def spawn_task(
    work_order: WorkOrder,
    *,
    agent: str,
    repo_dir: Path,
    log_dir: Path,
    config: NightshiftConfig,
    timeout_seconds: int | None = None,
) -> TaskCompletion | None:
    """Spawn a single sub-agent to execute a work order.

    Returns a parsed TaskCompletion on success, or None if the agent
    process failed or produced unparseable output.
    """
    task_id = work_order["task_id"]
    effective_timeout = timeout_seconds if timeout_seconds is not None else SUBAGENT_DEFAULT_TIMEOUT

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"task-{task_id}.log"
    message_path = log_dir / f"task-{task_id}.msg.json"

    cmd = _build_subagent_command(
        agent=agent,
        prompt=work_order["prompt"],
        cwd=repo_dir,
        message_path=message_path,
        schema_path=work_order["schema_path"],
        config=config,
    )

    print_status(f"[subagent] Spawning {agent} for task {task_id}: {work_order['title']}")

    exit_code, output = run_command(
        cmd,
        cwd=repo_dir,
        log_path=log_path,
        timeout_seconds=effective_timeout,
    )

    if exit_code != 0:
        print_status(f"[subagent] Task {task_id}: agent exited with code {exit_code}")

    # For codex, prefer the structured message file if it exists.
    raw_for_parse = output
    if agent == "codex" and message_path.exists():
        with contextlib.suppress(OSError):
            raw_for_parse = message_path.read_text(encoding="utf-8")

    return _parse_task_completion(raw_for_parse, task_id)


def spawn_wave(
    wave: list[WorkOrder],
    *,
    agent: str,
    repo_dir: Path,
    log_dir: Path,
    config: NightshiftConfig,
    timeout_seconds: int | None = None,
    max_retries: int = DECOMPOSER_MAX_RETRIES,
) -> WaveResult:
    """Spawn sub-agents for all work orders in a wave.

    Tasks execute sequentially within the wave. If an agent fails to
    produce parseable output, it is retried up to ``max_retries`` times.
    Tasks that report ``status: blocked`` are NOT retried -- the agent
    made an explicit decision.

    Returns a WaveResult with completed and failed lists.
    """
    if not wave:
        return WaveResult(wave=0, completed=[], failed=[], total_tasks=0)

    wave_number = wave[0]["wave"]
    completed: list[TaskCompletion] = []
    failed: list[TaskCompletion] = []

    print_status(f"[subagent] Starting wave {wave_number} with {len(wave)} task(s)")

    for order in wave:
        task_id = order["task_id"]
        result: TaskCompletion | None = None

        for attempt in range(1, max_retries + 1):
            result = spawn_task(
                order,
                agent=agent,
                repo_dir=repo_dir,
                log_dir=log_dir,
                config=config,
                timeout_seconds=timeout_seconds,
            )
            if result is not None:
                # Agent produced parseable output -- accept it regardless of status.
                break
            print_status(
                f"[subagent] Task {task_id}: attempt {attempt}/{max_retries} failed to produce parseable output"
            )

        if result is None:
            result = _make_error_completion(
                task_id,
                f"Agent failed to produce parseable output after {max_retries} attempt(s)",
            )

        if result["status"] == "done":
            completed.append(result)
            print_status(f"[subagent] Task {task_id}: done")
        else:
            failed.append(result)
            print_status(f"[subagent] Task {task_id}: {result['status']} -- {result['notes']}")

    print_status(f"[subagent] Wave {wave_number} complete: {len(completed)} done, {len(failed)} failed")

    return WaveResult(
        wave=wave_number,
        completed=completed,
        failed=failed,
        total_tasks=len(wave),
    )


def format_wave_result(result: WaveResult) -> str:
    """Render a WaveResult as human-readable markdown."""
    lines: list[str] = []

    lines.append(f"# Wave {result['wave']} Results")
    lines.append("")
    lines.append(
        f"**{len(result['completed'])}** completed, "
        f"**{len(result['failed'])}** failed, "
        f"**{result['total_tasks']}** total"
    )
    lines.append("")

    if result["completed"]:
        lines.append("## Completed")
        lines.append("")
        for tc in result["completed"]:
            lines.append(f"### Task {tc['task_id']}")
            if tc["files_created"]:
                lines.append(f"- Files created: {', '.join(tc['files_created'])}")
            if tc["files_modified"]:
                lines.append(f"- Files modified: {', '.join(tc['files_modified'])}")
            if tc["tests_written"]:
                lines.append(f"- Tests written: {len(tc['tests_written'])}")
            lines.append(f"- Tests passed: {tc['tests_passed']}")
            if tc["notes"]:
                lines.append(f"- Notes: {tc['notes']}")
            lines.append("")

    if result["failed"]:
        lines.append("## Failed")
        lines.append("")
        for tc in result["failed"]:
            lines.append(f"### Task {tc['task_id']}")
            lines.append(f"- Status: {tc['status']}")
            lines.append(f"- Reason: {tc['notes']}")
            lines.append("")

    return "\n".join(lines)
