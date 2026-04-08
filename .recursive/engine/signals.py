"""Signal readers for the Recursive autonomous framework.

Each function reads a specific system signal from runtime state files
and returns a typed value.  Functions never raise -- they return safe
defaults on missing or invalid data.

Extracted from pick-role.py so that dashboard.py and brain.md can
read signals without importing the v1 scoring engine.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _strip_fenced_code_blocks(text: str) -> str:
    """Remove fenced code blocks (``` ... ```) from text.

    Used by validators to prevent fields embedded inside code blocks
    from satisfying structural requirements that must appear in prose.
    """
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def _is_valid_eval_file(text: str) -> bool:
    """Return True if text looks like a real evaluation report.

    Requires both:
    - A **Date**: metadata line outside any fenced code block
    - At least 3 scored dimension rows (N/10 format) outside any fenced code block

    This prevents a fabricated file with fields embedded inside ``` blocks
    from influencing role selection via the eval score gate.
    """
    prose = _strip_fenced_code_blocks(text)
    if not re.search(r"\*\*Date\*\*:", prose):
        return False
    dimension_rows = re.findall(r"^\|[^|]+\|\s*\d+/10\b", prose, re.MULTILINE)
    return len(dimension_rows) >= 3


def _is_valid_autonomy_file(text: str) -> bool:
    """Return True if text looks like a real autonomy report.

    Requires both:
    - A **Date**: metadata line outside any fenced code block
    - At least one TOTAL: N/100 line anywhere in the file

    **Date**: must be outside a code block to prevent fabricated files from
    embedding the header inside ``` markers to bypass the guard.  TOTAL: is
    checked against the full text because the canonical autonomy report format
    embeds the score table (including TOTAL:) inside a fenced code block.
    """
    prose = _strip_fenced_code_blocks(text)
    if not re.search(r"\*\*Date\*\*:", prose):
        return False
    return bool(re.search(r"TOTAL:\s*\d+\s*/\s*100", text))


def _read_frontmatter(f: Path) -> str | None:
    """Read and return the YAML frontmatter block of a task file.

    Returns the content between the opening and closing '---' delimiters,
    or None if the file cannot be read or has no valid frontmatter block.
    Handles both Unix (LF) and Windows (CRLF) line endings.

    Restricting reads to frontmatter prevents issue body content from
    influencing role-selection signals (task #0167, task #0168).
    """
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return None
    fm_match = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not fm_match:
        return None
    return fm_match.group(1)


# ---------------------------------------------------------------------------
# Evaluation signals
# ---------------------------------------------------------------------------


def read_latest_eval_score(evaluations_dir: Path) -> int | None:
    """Extract total score from the latest evaluation report."""
    files = sorted(evaluations_dir.glob("[0-9]*.md"))
    if not files:
        return None
    try:
        text = files[-1].read_text(encoding="utf-8")
        if not _is_valid_eval_file(text):
            return None
        match = re.search(r"\*\*Total\*\*\s*\|\s*\*\*(\d+)/100\*\*", text)
        if match:
            return int(match.group(1))
    except OSError:
        pass
    return None


def read_latest_autonomy_score(autonomy_dir: Path) -> int | None:
    """Extract autonomy score from the latest autonomy report.

    Uses findall and returns the LAST match so that ACHIEVE reports
    with both a baseline and an updated score return the updated value.
    """
    files = sorted(autonomy_dir.glob("[0-9]*.md"))
    if not files:
        return None
    try:
        text = files[-1].read_text(encoding="utf-8")
        if not _is_valid_autonomy_file(text):
            return None
        matches = re.findall(r"TOTAL:\s*(\d+)\s*/\s*100", text)
        if matches:
            return int(matches[-1])
    except OSError:
        pass
    return None


# ---------------------------------------------------------------------------
# Session index signals
# ---------------------------------------------------------------------------


def parse_session_index(index_path: Path) -> list[dict[str, str]]:
    """Parse the session index markdown table into a list of dicts."""
    rows: list[dict[str, str]] = []
    try:
        lines = index_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    headers: list[str] = []
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not headers:
            headers = [h.lower() for h in cells]
            continue
        if all(c.startswith("-") or c.startswith(":") for c in cells):
            continue
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def count_consecutive_role(rows: list[dict[str, str]], role: str) -> int:
    """Count consecutive sessions of a given role from the end of the index."""
    count = 0
    for row in reversed(rows):
        if row.get("role", "build").lower() == role:
            count += 1
        else:
            break
    return count


def count_sessions_since_role(rows: list[dict[str, str]], role: str) -> int:
    """Count sessions since the last occurrence of a role."""
    for i, row in enumerate(reversed(rows)):
        if row.get("role", "build").lower() == role:
            return i
    return len(rows)


# ---------------------------------------------------------------------------
# Task signals
# ---------------------------------------------------------------------------


def count_pending_tasks(tasks_dir: Path) -> int:
    """Count task files with status: pending in their YAML frontmatter."""
    count = 0
    for f in tasks_dir.glob("[0-9]*.md"):
        frontmatter = _read_frontmatter(f)
        if frontmatter is None:
            continue
        if re.search(r"^status:\s*pending", frontmatter, re.MULTILINE):
            count += 1
    return count


def count_stale_tasks(tasks_dir: Path, threshold: int = 20) -> int:
    """Count pending tasks older than threshold days using YAML frontmatter only."""
    count = 0
    for f in tasks_dir.glob("[0-9]*.md"):
        frontmatter = _read_frontmatter(f)
        if frontmatter is None:
            continue
        if not re.search(r"^status:\s*pending", frontmatter, re.MULTILINE):
            continue
        match = re.search(r"^created:\s*(\d{4}-\d{2}-\d{2})", frontmatter, re.MULTILINE)
        if match:
            from datetime import datetime, timezone

            try:
                created = datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                age_days = (datetime.now(tz=timezone.utc) - created).days
                if age_days >= threshold:
                    count += 1
            except ValueError:
                continue
    return count


def count_pending_pentest_framework_tasks(tasks_dir: Path) -> int:
    """Count pending tasks with source: pentest and target: recursive.

    These tasks represent confirmed security findings that target framework
    code (.recursive/).  They are a security urgency signal, not a friction
    signal, and should activate the evolve agent regardless of friction count.
    """
    count = 0
    for f in tasks_dir.glob("[0-9]*.md"):
        fm = _read_frontmatter(f)
        if not fm:
            continue
        if not re.search(r"^status:\s*pending", fm, re.MULTILINE):
            continue
        if "source: pentest" not in fm:
            continue
        if "target: recursive" not in fm:
            continue
        count += 1
    return count


def count_recent_pentest_tasks(tasks_dir: Path, days: int = 3) -> int:
    """Count archived tasks with source: pentest completed in the last N days.

    Uses the ``completed:`` frontmatter date (durable through git reset)
    rather than file mtime (reset by ``git checkout``).
    """
    from datetime import datetime, timedelta

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    archive = tasks_dir / "archive"
    if not archive.is_dir():
        return 0
    count = 0
    for f in archive.glob("[0-9]*.md"):
        fm = _read_frontmatter(f)
        if not fm or "source: pentest" not in fm:
            continue
        m = re.search(r"^completed:\s*(\d{4}-\d{2}-\d{2})", fm, re.MULTILINE)
        if m and m.group(1) >= cutoff:
            count += 1
    return count


# Security keywords for Feature-field signal (anti-loop).
_SECURITY_KEYWORDS = ("security", "pentest", "injection", "prompt guard", "prompt-guard")


def count_recent_security_sessions(index_rows: list[dict[str, str]], tasks_dir: Path) -> int:
    """Dual-signal count of recent security-driven BUILD sessions.

    Signal A (fast, lossy): Feature field contains security keywords.
    Signal B (robust, structured): archived tasks with source: pentest.
    Returns max(A, B) so the anti-loop activates if either signal fires.
    """
    feature_count = sum(
        1
        for r in index_rows[-5:]
        if r.get("role", "").strip() == "build" and any(kw in r.get("feature", "").lower() for kw in _SECURITY_KEYWORDS)
    )
    task_count = count_recent_pentest_tasks(tasks_dir)
    return max(feature_count, task_count)


def has_urgent_tasks(tasks_dir: Path) -> bool:
    """Check if any pending task has priority: urgent in its YAML frontmatter."""
    for f in tasks_dir.glob("[0-9]*.md"):
        frontmatter = _read_frontmatter(f)
        if frontmatter is None:
            continue
        if re.search(r"^status:\s*pending", frontmatter, re.MULTILINE) and re.search(
            r"^priority:\s*urgent", frontmatter, re.MULTILINE
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# System health signals
# ---------------------------------------------------------------------------


def read_healer_status(healer_path: Path) -> str:
    """Read the last system health rating from the healer log."""
    try:
        text = healer_path.read_text(encoding="utf-8")
        matches = re.findall(r"\*\*System health:\*\*\s*(\w+)", text)
        if matches:
            return str(matches[-1]).lower()
    except OSError:
        pass
    return "good"


def count_friction_entries(friction_path: Path) -> int:
    """Count entries in the friction log (## headers)."""
    try:
        text = friction_path.read_text(encoding="utf-8")
        return len(re.findall(r"^## \d{4}-\d{2}-\d{2}", text, re.MULTILINE))
    except OSError:
        return 0


def count_needs_human_issues() -> int:
    """Count open GitHub issues with the needs-human label."""
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--label", "needs-human", "--state", "open", "--json", "number"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return len(json.loads(result.stdout))
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        pass
    return 0


def read_last_oversee_status(handoff_path: Path) -> str:
    """Read the queue status from the last OVERSEE handoff (CLEAN or NEEDS MORE WORK)."""
    try:
        text = handoff_path.read_text(encoding="utf-8")
        if "Role: OVERSEE" not in text and "role: oversee" not in text.lower():
            return ""  # last session wasn't oversee
        match = re.search(r"Queue status:\s*(CLEAN|NEEDS MORE WORK)", text)
        if match:
            return match.group(1)
    except OSError:
        pass
    return ""


def did_tracker_move(rows: list[dict[str, str]], window: int = 5) -> bool:
    """Check if any recent session reported tracker movement."""
    recent = rows[-window:] if len(rows) >= window else rows
    for row in recent:
        status = row.get("status", "")
        if "%" in status:
            return True
    return False


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULTS: dict[str, int | str | bool] = {
    "eval_score": 80,
    "autonomy_score": 0,
    "consecutive_builds": 0,
    "sessions_since_build": 0,
    "sessions_since_review": 0,
    "sessions_since_strategy": 0,
    "sessions_since_achieve": 0,
    "sessions_since_oversee": 0,
    "pending_tasks": 0,
    "stale_tasks": 0,
    "healer_status": "good",
    "needs_human_issues": 0,
    "tracker_moved": False,
    "urgent_tasks": False,
    "recent_security_sessions": 0,
}
