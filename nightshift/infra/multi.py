"""Multi-repo shift orchestration: run hardening loops across multiple repos."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Callable

from nightshift.core.constants import now_local, print_status
from nightshift.core.errors import NightshiftError
from nightshift.core.state import load_json
from nightshift.core.types import RepoShiftResult


def _read_repo_metrics(repo_dir: Path, date: str) -> RepoShiftResult:
    """Read shift metrics from a repo's state file after a run."""
    state_path = repo_dir / "docs" / "Nightshift" / f"{date}.state.json"
    base: RepoShiftResult = {
        "repo_dir": str(repo_dir),
        "exit_code": 0,
        "cycles_run": 0,
        "fixes": 0,
        "issues_logged": 0,
        "halt_reason": "",
    }
    if not state_path.exists():
        return base
    state: dict[str, Any] = load_json(state_path)
    base["cycles_run"] = len(state.get("cycles", []))
    counters = state.get("counters", {})
    base["fixes"] = int(counters.get("fixes", 0))
    base["issues_logged"] = int(counters.get("issues_logged", 0))
    base["halt_reason"] = state.get("halt_reason", "") or ""
    return base


def validate_repos(repos: list[Path]) -> None:
    """Validate that all repo paths exist and are git repositories."""
    for repo in repos:
        if not repo.is_dir():
            raise NightshiftError(f"Repository directory does not exist: {repo}")
        if not (repo / ".git").exists() and not (repo / ".git").is_file():
            raise NightshiftError(f"Not a git repository: {repo}")


def format_multi_summary(results: list[RepoShiftResult]) -> str:
    """Format a human-readable summary of multi-repo results."""
    lines: list[str] = []
    lines.append("")
    lines.append("+--------------------------------------------------+")
    lines.append("|         MULTI-REPO SUMMARY                       |")
    lines.append("+--------------------------------------------------+")
    total_cycles = 0
    total_fixes = 0
    total_issues = 0
    for result in results:
        name = Path(result["repo_dir"]).name
        status = "OK" if result["exit_code"] == 0 else "FAIL"
        cycles = result["cycles_run"]
        fixes = result["fixes"]
        issues = result["issues_logged"]
        total_cycles += cycles
        total_fixes += fixes
        total_issues += issues
        lines.append(f"  {name:<30} {status:>4}  {cycles} cycles  {fixes} fixes  {issues} logged")
    lines.append("+--------------------------------------------------+")
    lines.append(f"  Total: {total_cycles} cycles, {total_fixes} fixes, {total_issues} issues logged")
    lines.append("+--------------------------------------------------+")
    return "\n".join(lines)


# Type alias for the runner function injected from cli.py.
ShiftRunner = Callable[[argparse.Namespace], int]


def run_multi_shift(
    args: argparse.Namespace,
    *,
    runner: ShiftRunner,
) -> int:
    """Run a hardening shift on each repo sequentially.

    For each repo, creates a fresh args namespace and delegates to
    *runner* (typically ``run_nightshift`` from ``cli.py``).  The runner
    is injected to avoid a circular import between ``multi.py`` and
    ``cli.py``.  Results are collected from per-repo state files and a
    combined summary is printed at the end.
    """
    repos = [Path(r).resolve() for r in args.repos]
    date = args.date or now_local().strftime("%Y-%m-%d")

    validate_repos(repos)

    results: list[RepoShiftResult] = []
    for i, repo in enumerate(repos):
        print_status("")
        print_status(f"=== Multi-repo: {repo.name} ({i + 1}/{len(repos)}) ===")
        print_status("")

        repo_args = copy.copy(args)
        repo_args.repo_dir = str(repo)
        try:
            exit_code = runner(repo_args)
        except NightshiftError as error:
            print_status(f"Error on {repo.name}: {error}")
            exit_code = 1

        metrics = _read_repo_metrics(repo, date)
        metrics["exit_code"] = exit_code
        results.append(metrics)

    summary = format_multi_summary(results)
    for line in summary.splitlines():
        print_status(line)

    return 0 if all(r["exit_code"] == 0 for r in results) else 1
