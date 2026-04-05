"""Daemon housekeeping -- log rotation and orphan branch pruning."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from nightshift.constants import (
    DAEMON_BRANCH_PREFIXES,
    DEFAULT_KEEP_LOGS_DAYS,
    PROTECTED_BRANCHES,
)
from nightshift.errors import NightshiftError
from nightshift.shell import run_capture
from nightshift.types import BranchPruneResult, LogRotationResult


def rotate_logs(log_dir: str, keep_days: int = DEFAULT_KEEP_LOGS_DAYS) -> LogRotationResult:
    """Delete ``.log`` files in *log_dir* older than *keep_days* days.

    Returns a :class:`LogRotationResult` with the list of deleted paths,
    count of kept files, and any errors encountered.
    """
    deleted: list[str] = []
    errors: list[str] = []
    kept = 0
    cutoff = time.time() - (keep_days * 86400)
    log_path = Path(log_dir)

    if not log_path.is_dir():
        return {"deleted": [], "kept": 0, "errors": [f"log_dir does not exist: {log_dir}"]}

    for entry in log_path.iterdir():
        if not entry.is_file() or entry.suffix != ".log":
            continue
        try:
            mtime = entry.stat().st_mtime
            if mtime < cutoff:
                entry.unlink()
                deleted.append(str(entry))
            else:
                kept += 1
        except OSError as exc:
            errors.append(f"Failed to process {entry}: {exc}")

    return {"deleted": deleted, "kept": kept, "errors": errors}


def _remote_branch_names(repo_dir: str) -> list[str]:
    """Return remote branch names (without ``origin/`` prefix), excluding HEAD."""
    raw = run_capture(
        ["git", "branch", "-r", "--format=%(refname:short)"],
        cwd=Path(repo_dir),
        check=False,
        timeout=30,
    )
    branches: list[str] = []
    for line in raw.splitlines():
        name = line.strip()
        if not name or name.endswith("/HEAD"):
            continue
        # Strip 'origin/' prefix
        if name.startswith("origin/"):
            name = name[len("origin/") :]
        branches.append(name)
    return branches


def _open_pr_branches(repo_dir: str) -> set[str]:
    """Return the set of branch names that have an open pull request."""
    raw = run_capture(
        ["gh", "pr", "list", "--state", "open", "--json", "headRefName", "--jq", ".[].headRefName"],
        cwd=Path(repo_dir),
        check=False,
        timeout=30,
    )
    return {line.strip() for line in raw.splitlines() if line.strip()}


def _is_daemon_branch(name: str) -> bool:
    """Return True if *name* matches a nightshift daemon branch prefix."""
    return any(name.startswith(prefix) for prefix in DAEMON_BRANCH_PREFIXES)


def prune_orphan_branches(repo_dir: str = ".") -> BranchPruneResult:
    """Delete remote branches created by nightshift that have no open PR.

    Only branches matching :data:`DAEMON_BRANCH_PREFIXES` are considered.
    Branches in :data:`PROTECTED_BRANCHES` are never deleted.

    Returns a :class:`BranchPruneResult` with pruned names, skipped names,
    and any errors.
    """
    pruned: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    try:
        all_remote = _remote_branch_names(repo_dir)
    except (OSError, subprocess.SubprocessError, NightshiftError) as exc:
        return {"pruned": [], "skipped": [], "errors": [f"Failed to list remote branches: {exc}"]}

    try:
        open_branches = _open_pr_branches(repo_dir)
    except (OSError, subprocess.SubprocessError, NightshiftError) as exc:
        return {"pruned": [], "skipped": [], "errors": [f"Failed to list open PRs: {exc}"]}

    for branch in all_remote:
        if branch in PROTECTED_BRANCHES:
            continue
        if not _is_daemon_branch(branch):
            skipped.append(branch)
            continue
        if branch in open_branches:
            skipped.append(branch)
            continue

        # Branch is a daemon branch with no open PR -- prune it
        try:
            run_capture(
                ["git", "push", "origin", "--delete", branch],
                cwd=Path(repo_dir),
                check=True,
                timeout=30,
            )
            pruned.append(branch)
        except (OSError, subprocess.SubprocessError, NightshiftError) as exc:
            errors.append(f"Failed to delete branch {branch}: {exc}")

    return {"pruned": pruned, "skipped": skipped, "errors": errors}
