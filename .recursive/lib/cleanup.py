"""Daemon housekeeping -- log rotation, branch pruning, healer log trimming.

Standalone -- no dependency on target project code.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any

# Branch prefixes created by the daemon that can be pruned
DAEMON_BRANCH_PREFIXES = (
    "feat/",
    "fix/",
    "docs/",
    "refactor/",
    "release/",
    "review/",
    "overseer/",
    "strategize/",
    "achieve/",
)

PROTECTED_BRANCHES = {"main", "master", "develop"}


def rotate_logs(log_dir: str | Path, keep_days: int = 7) -> dict[str, Any]:
    """Delete session log files older than keep_days.

    Returns dict with 'deleted' (list of filenames) and 'errors' (list of strings).
    """
    result: dict[str, Any] = {"deleted": [], "errors": []}
    log_path = Path(log_dir)
    if not log_path.is_dir():
        return result

    cutoff = time.time() - (keep_days * 86400)
    for f in log_path.glob("*.log"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                result["deleted"].append(f.name)
        except OSError as e:
            result["errors"].append(str(e))
    return result


def rotate_healer_log(log_path: str | Path, keep_entries: int = 50) -> dict[str, Any]:
    """Trim the healer log to the last N entries.

    Entries start with '## ' headers.
    Returns dict with 'trimmed' (bool) and 'entries_before'/'entries_after' counts.
    """
    result: dict[str, Any] = {
        "trimmed": False,
        "entries_before": 0,
        "entries_after": 0,
    }
    p = Path(log_path)
    if not p.exists():
        return result

    text = p.read_text(encoding="utf-8")
    # Split on entry headers (## YYYY-MM-DD ...)
    parts = re.split(r"(?=^## )", text, flags=re.MULTILINE)

    # First part is usually the file header (before any ## entry)
    header = parts[0] if parts and not parts[0].startswith("## ") else ""
    entries = [p for p in parts if p.startswith("## ")]

    result["entries_before"] = len(entries)
    if len(entries) <= keep_entries:
        result["entries_after"] = len(entries)
        return result

    kept = entries[-keep_entries:]
    p.write_text(header + "".join(kept), encoding="utf-8")
    result["trimmed"] = True
    result["entries_after"] = len(kept)
    return result


def prune_orphan_branches(
    repo_dir: str | Path,
) -> dict[str, Any]:
    """Prune remote branches matching daemon prefixes that have no open PR.

    Returns dict with 'pruned' (list of branch names) and 'errors' (list).
    """
    result: dict[str, Any] = {"pruned": [], "errors": []}

    try:
        # Get remote branches
        out = subprocess.run(
            ["git", "branch", "-r", "--list", "origin/*"],
            capture_output=True,
            text=True,
            cwd=str(repo_dir),
            timeout=30,
        )
        if out.returncode != 0:
            return result

        branches = []
        for line in out.stdout.splitlines():
            b = line.strip().removeprefix("origin/")
            if b.startswith("HEAD"):
                continue
            if b in PROTECTED_BRANCHES:
                continue
            if any(b.startswith(prefix) for prefix in DAEMON_BRANCH_PREFIXES):
                branches.append(b)

        if not branches:
            return result

        # Check which have open PRs
        for branch in branches:
            try:
                pr_check = subprocess.run(
                    ["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number"],
                    capture_output=True,
                    text=True,
                    cwd=str(repo_dir),
                    timeout=15,
                )
                has_pr = pr_check.returncode == 0 and pr_check.stdout.strip() not in ("", "[]")
                if not has_pr:
                    # Delete remote branch
                    subprocess.run(
                        ["git", "push", "origin", "--delete", branch],
                        capture_output=True,
                        text=True,
                        cwd=str(repo_dir),
                        timeout=15,
                    )
                    result["pruned"].append(branch)
            except (subprocess.TimeoutExpired, OSError) as e:
                result["errors"].append(f"{branch}: {e}")

    except (subprocess.TimeoutExpired, OSError) as e:
        result["errors"].append(str(e))

    return result
