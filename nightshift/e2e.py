"""End-to-end test runner for Loop 2 feature builds.

Runs the project's full test suite and optional smoke tests after all waves
complete but before final verification.  Returns a structured E2EResult.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from nightshift.config import infer_package_manager
from nightshift.constants import E2E_SMOKE_CANDIDATES, E2E_TEST_TIMEOUT
from nightshift.shell import run_test_command
from nightshift.types import E2EResult

_MAKEFILE_TEST_TARGET = re.compile(r"^test\s*:", re.MULTILINE)


def infer_test_command(repo_dir: Path) -> str | None:
    """Detect the project's test command from build files.

    Checks Makefile, package.json, pyproject.toml/pytest.ini,
    Cargo.toml, and go.mod in priority order.
    """
    makefile = repo_dir / "Makefile"
    if makefile.exists() and not makefile.is_symlink():
        try:
            content = makefile.read_text(encoding="utf-8")
        except OSError:
            content = ""
        if _MAKEFILE_TEST_TARGET.search(content):
            return "make test"

    package_json = repo_dir / "package.json"
    if package_json.exists() and not package_json.is_symlink():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
        scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
        if "test" in scripts:
            pm = infer_package_manager(repo_dir) or "npm"
            return f"{pm} test"

    if (repo_dir / "pyproject.toml").exists() or (repo_dir / "pytest.ini").exists():
        return "python3 -m pytest"

    if (repo_dir / "Cargo.toml").exists():
        return "cargo test"

    if (repo_dir / "go.mod").exists():
        return "go test ./..."

    return None


def detect_smoke_test(repo_dir: Path) -> str | None:
    """Find a smoke test script in the repo, if one exists."""
    for candidate in E2E_SMOKE_CANDIDATES:
        path = repo_dir / candidate
        if path.is_symlink():
            continue
        if path.is_file():
            return f"bash {candidate}"
    return None


def run_e2e_tests(
    *,
    repo_dir: Path,
    test_command: str | None = None,
    timeout_seconds: int = E2E_TEST_TIMEOUT,
) -> E2EResult:
    """Run end-to-end tests and optional smoke test after all waves complete.

    If *test_command* is ``None``, the test command is inferred from
    the repo's build files via :func:`infer_test_command`.
    """
    effective_test = test_command or infer_test_command(repo_dir)

    test_exit_code = 0
    test_output = ""
    if effective_test is not None:
        test_exit_code, test_output = run_test_command(effective_test, cwd=repo_dir, timeout=timeout_seconds)

    smoke_command = detect_smoke_test(repo_dir)
    smoke_exit_code = 0
    smoke_output = ""
    if smoke_command is not None:
        smoke_exit_code, smoke_output = run_test_command(smoke_command, cwd=repo_dir, timeout=timeout_seconds)

    if effective_test is None and smoke_command is None:
        status = "skipped"
    elif test_exit_code == 0 and smoke_exit_code == 0:
        status = "passed"
    else:
        status = "failed"

    return E2EResult(
        status=status,
        test_command=effective_test,
        test_exit_code=test_exit_code,
        test_output=test_output,
        smoke_test_command=smoke_command,
        smoke_test_exit_code=smoke_exit_code,
        smoke_test_output=smoke_output,
    )
