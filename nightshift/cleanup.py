"""Daemon housekeeping -- log rotation, healer archiving, and branch pruning."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from nightshift.constants import (
    DAEMON_BRANCH_PREFIXES,
    DEFAULT_KEEP_HEALER_ENTRIES,
    DEFAULT_KEEP_LOGS_DAYS,
    PROTECTED_BRANCHES,
)
from nightshift.errors import NightshiftError
from nightshift.shell import run_capture
from nightshift.types import BranchPruneResult, HealerRotationResult, LogRotationResult

_HEALER_ENTRY_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s+--\s+.*$", re.MULTILINE)


def _split_healer_log(content: str) -> tuple[str, list[str]]:
    """Return the static preamble and each top-level healer entry section."""
    matches = list(_HEALER_ENTRY_RE.finditer(content))
    if not matches:
        return content, []

    preamble = content[: matches[0].start()]
    entries: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        entries.append(content[match.start() : end].strip())
    return preamble, entries


def _render_healer_log(preamble: str, entries: list[str]) -> str:
    """Rebuild healer log content from the preamble and entry blocks."""
    content = preamble.rstrip()
    if not content:
        content = "# Healer Log"

    if entries:
        content = f"{content}\n\n" + "\n\n".join(entry.strip() for entry in entries)
    return f"{content}\n"


def _archive_preamble(month: str) -> str:
    return (
        f"# Healer Log Archive -- {month}\n\nRotated entries from `docs/healer/log.md` in chronological order.\n\n---\n"
    )


def rotate_healer_log(
    log_path: str,
    keep_entries: int = DEFAULT_KEEP_HEALER_ENTRIES,
    archive_dir: str | None = None,
) -> HealerRotationResult:
    """Archive older healer sections and keep only the most recent entries live."""
    errors: list[str] = []
    archived_files: list[str] = []
    log_file = Path(log_path)

    if keep_entries < 1:
        return {
            "archived_files": [],
            "rotated_entries": 0,
            "kept_entries": 0,
            "errors": [f"keep_entries must be >= 1: {keep_entries}"],
        }

    if not log_file.is_file():
        return {
            "archived_files": [],
            "rotated_entries": 0,
            "kept_entries": 0,
            "errors": [f"log_path does not exist: {log_path}"],
        }

    try:
        content = log_file.read_text()
    except OSError as exc:
        return {
            "archived_files": [],
            "rotated_entries": 0,
            "kept_entries": 0,
            "errors": [f"Failed to read healer log {log_path}: {exc}"],
        }

    preamble, entries = _split_healer_log(content)
    if len(entries) <= keep_entries:
        return {
            "archived_files": [],
            "rotated_entries": 0,
            "kept_entries": len(entries),
            "errors": [],
        }

    rotated_entries = entries[:-keep_entries]
    kept_entries = entries[-keep_entries:]
    archive_path = Path(archive_dir) if archive_dir is not None else log_file.parent / "archive"

    try:
        archive_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {
            "archived_files": [],
            "rotated_entries": 0,
            "kept_entries": len(entries),
            "errors": [f"Failed to create archive dir {archive_path}: {exc}"],
        }

    grouped_entries: dict[str, list[str]] = {}
    for entry in rotated_entries:
        match = _HEALER_ENTRY_RE.match(entry)
        if match is None:
            return {
                "archived_files": archived_files,
                "rotated_entries": 0,
                "kept_entries": len(entries),
                "errors": ["Failed to parse healer entry date for archival"],
            }
        month = match.group(1)[:7]
        grouped_entries.setdefault(month, []).append(entry.strip())

    for month, month_entries in grouped_entries.items():
        monthly_archive = archive_path / f"{month}.md"
        existing_entries: list[str] = []
        if monthly_archive.exists():
            try:
                _, existing_entries = _split_healer_log(monthly_archive.read_text())
            except OSError as exc:
                return {
                    "archived_files": archived_files,
                    "rotated_entries": 0,
                    "kept_entries": len(entries),
                    "errors": [f"Failed to read archive {monthly_archive}: {exc}"],
                }

        merged_entries = existing_entries + month_entries
        try:
            monthly_archive.write_text(_render_healer_log(_archive_preamble(month), merged_entries))
            archived_files.append(str(monthly_archive))
        except OSError as exc:
            return {
                "archived_files": archived_files,
                "rotated_entries": 0,
                "kept_entries": len(entries),
                "errors": [f"Failed to write archive {monthly_archive}: {exc}"],
            }

    try:
        log_file.write_text(_render_healer_log(preamble, kept_entries))
    except OSError as exc:
        return {
            "archived_files": archived_files,
            "rotated_entries": 0,
            "kept_entries": len(entries),
            "errors": [f"Failed to rewrite healer log {log_file}: {exc}"],
        }

    return {
        "archived_files": archived_files,
        "rotated_entries": len(rotated_entries),
        "kept_entries": len(kept_entries),
        "errors": errors,
    }


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
    """Return the set of branch names that have an open pull request.

    Uses ``check=True`` so that ``gh`` auth failures or network errors raise
    rather than returning an empty set (which would cause every daemon branch
    to look orphaned and get deleted).
    """
    raw = run_capture(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            "1000",
            "--json",
            "headRefName",
            "--jq",
            ".[].headRefName",
        ],
        cwd=Path(repo_dir),
        check=True,
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
