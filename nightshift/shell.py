"""Subprocess execution: streaming runner, git helper, shell utilities."""

from __future__ import annotations

import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO

from nightshift.errors import NightshiftError


def _reader_thread(
    stdout: IO[str],
    lines: list[str],
    log_handle: IO[str] | None,
) -> None:
    """Read lines from subprocess stdout until EOF.  Runs in a daemon thread."""
    try:
        for line in iter(stdout.readline, ""):
            if not line:
                break
            sys.stdout.write(line)
            lines.append(line)
            if log_handle is not None:
                log_handle.write(line)
                log_handle.flush()
    except (OSError, ValueError):
        pass


def run_command(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path | None = None,
    env: dict[str, str] | None = None,
    timeout_seconds: int | None = None,
) -> tuple[int, str]:
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: list[str] = []
    log_handle: IO[str] | None = None
    try:
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_handle = log_path.open("a", encoding="utf-8")
        if process.stdout is None:
            raise NightshiftError("subprocess stdout is unexpectedly None")

        reader = threading.Thread(
            target=_reader_thread,
            args=(process.stdout, lines, log_handle),
            daemon=True,
        )
        reader.start()

        # Main thread enforces the timeout - reader thread cannot block us.
        deadline = time.monotonic() + timeout_seconds if timeout_seconds else None
        timed_out = False
        while reader.is_alive():
            remaining = None
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
            reader.join(timeout=min(remaining, 1.0) if remaining is not None else 1.0)

        if timed_out:
            timeout_message = (
                f"\n[nightshift] Agent cycle hit timeout after {timeout_seconds} seconds. "
                "Terminating the agent process.\n"
            )
            sys.stdout.write(timeout_message)
            lines.append(timeout_message)
            if log_handle is not None:
                log_handle.write(timeout_message)
                log_handle.flush()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        else:
            process.wait()
    finally:
        if log_handle is not None:
            log_handle.close()
    return process.returncode, "".join(lines)


def run_capture(cmd: list[str], *, cwd: Path, check: bool = True, timeout: int = 60) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise NightshiftError(
            f"Command failed ({result.returncode}): {' '.join(shlex.quote(part) for part in cmd)}\n"
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


def git(cwd: Path, *args: str, check: bool = True) -> str:
    return run_capture(["git", *args], cwd=cwd, check=check)


def command_exists(name: str) -> bool:
    return (
        subprocess.run(
            ["bash", "-lc", f"command -v {shlex.quote(name)} >/dev/null"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        ).returncode
        == 0
    )


def run_shell_string(command: str, *, cwd: Path, runner_log: Path) -> tuple[int, str]:
    return run_command(["bash", "-lc", command], cwd=cwd, log_path=runner_log)
