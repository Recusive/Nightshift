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
# Delegation history signals (v2 brain architecture)
# ---------------------------------------------------------------------------

# Maps delegation tokens in decisions log to canonical role names.
# "build-fix" and "evolve-fix" are fix-cycle sub-agents still counted toward
# their parent role so that the sessions-since counter resets correctly.
_DELEGATION_ROLE_MAP: dict[str, str] = {
    "build": "build",
    "build-fix": "build",
    "review": "review",
    "oversee": "oversee",
    "strategize": "strategize",
    "achieve": "achieve",
    "security": "security-check",
    "security-check": "security-check",
    "evolve": "evolve",
    "evolve-fix": "evolve",
    "audit": "audit",
    "audit-agent": "audit",
}


def parse_delegations_from_decisions_log(log_path: Path) -> list[set[str]]:
    """Parse the decisions log and return delegation sets in chronological order.

    Each entry in the returned list represents one brain session (one
    ``## YYYY-MM-DD -- Session #NNNN`` block) and contains the canonical
    role names that were delegated in that session.

    If a session entry has no ``**Delegations**:`` line it is included as an
    empty set so that the list length reflects the total number of logged brain
    sessions.

    Returns an empty list if the file cannot be read or has no session headers.
    """
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return []

    # Split on session headers -- each block starts with "## " followed by a date
    # and optional session identifier (e.g. "## 2026-04-08 -- Session #0107").
    blocks = re.split(r"(?=^## \d{4}-\d{2}-\d{2})", text, flags=re.MULTILINE)
    result: list[set[str]] = []
    for block in blocks:
        if not re.match(r"^## \d{4}-\d{2}-\d{2}", block):
            continue
        delegations: set[str] = set()
        # Match "**Delegations**: token1 (desc), token2 (desc), ..."
        deleg_match = re.search(r"^\*\*Delegations\*\*:\s*(.+)$", block, re.MULTILINE)
        if deleg_match:
            raw = deleg_match.group(1)
            # The delegation list is comma-separated.  Each item is a role token
            # optionally followed by a parenthesised description, e.g.:
            #   "build (#0208 fix), evolve (#0209 IFS), build-fix (PR review)"
            # We split on commas, then extract only the *first* word of each
            # segment (before any space or parenthesis) to avoid picking up
            # words from inside the description text.
            for segment in raw.split(","):
                token_match = re.match(r"\s*([A-Za-z][\w-]*)", segment)
                if token_match:
                    canonical = _DELEGATION_ROLE_MAP.get(token_match.group(1).lower())
                    if canonical:
                        delegations.add(canonical)
        result.append(delegations)
    return result


def count_sessions_since_delegation(
    index_rows: list[dict[str, str]],
    role: str,
    delegations: list[set[str]],
) -> int:
    """Count sessions since the last occurrence of a role, including delegations.

    In the v2 brain architecture every session appears in the session index as
    role=brain.  The actual sub-agents dispatched are recorded in the decisions
    log.  This function returns the minimum of:

    - ``count_sessions_since_role(index_rows, role)`` -- the raw index count
      (correct for v1/standalone sessions)
    - the number of brain sessions since the role was last delegated
      (correct for v2 brain sessions)

    Taking the minimum means that if *either* source knows the role ran
    recently, the counter reflects that fact.
    """
    index_count = count_sessions_since_role(index_rows, role)
    if not delegations:
        return index_count
    # Count brain sessions since the last delegation of this role.
    delegation_count = len(delegations)
    for i, deleg_set in enumerate(reversed(delegations)):
        if role in deleg_set:
            delegation_count = i
            break
    return min(index_count, delegation_count)


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
        if re.search(r"^status:\s*pending\s*$", frontmatter, re.MULTILINE):
            count += 1
    return count


def count_stale_tasks(tasks_dir: Path, threshold: int = 20) -> int:
    """Count pending tasks older than threshold days using YAML frontmatter only."""
    count = 0
    for f in tasks_dir.glob("[0-9]*.md"):
        frontmatter = _read_frontmatter(f)
        if frontmatter is None:
            continue
        if not re.search(r"^status:\s*pending\s*$", frontmatter, re.MULTILINE):
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
        if not re.search(r"^status:\s*pending\s*$", fm, re.MULTILINE):
            continue
        if not re.search(r"^source:\s*pentest\s*$", fm, re.MULTILINE):
            continue
        if not re.search(r"^target:\s*recursive\s*$", fm, re.MULTILINE):
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
        if not fm or not re.search(r"^source:\s*pentest\s*$", fm, re.MULTILINE):
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
        if re.search(r"^status:\s*pending\s*$", frontmatter, re.MULTILINE) and re.search(
            r"^priority:\s*urgent\s*$", frontmatter, re.MULTILINE
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
# Decision-consequence signals (self-awareness for the brain)
# ---------------------------------------------------------------------------


def compute_queue_trend(decisions_log: Path, window: int = 5) -> list[int]:
    """Extract net task delta per session from decisions log outcomes.

    Parses 'N follow-up tasks created' and 'tasks completed' from each
    session outcome. Returns a list of net deltas (created - completed)
    for the last `window` sessions. Positive = queue growing.
    """
    try:
        text = decisions_log.read_text(encoding="utf-8")
    except OSError:
        return []
    blocks = re.split(r"(?=^## \d{4}-\d{2}-\d{2})", text, flags=re.MULTILINE)
    deltas: list[int] = []
    for block in blocks:
        if not re.match(r"^## \d{4}-\d{2}-\d{2}", block):
            continue
        outcome = re.search(r"^\*\*Outcome\*\*:\s*(.+)", block, re.MULTILINE)
        if not outcome:
            continue
        line = outcome.group(1)
        created = 0
        m = re.search(r"(\d+)\s+follow-up\s+task", line)
        if m:
            created = int(m.group(1))
        # Count tasks marked done in outcome text
        completed_count = line.lower().count("merged")
        # Each merged PR roughly = 1 task completed
        deltas.append(created - completed_count)
    return deltas[-window:]


def compute_agent_diversity(delegations: list[set[str]], window: int = 10) -> dict[str, int]:
    """Count how many times each agent type was delegated over last N sessions.

    Returns a dict of {role: count} for roles that were used, sorted by
    frequency descending.
    """
    recent = delegations[-window:] if len(delegations) > window else delegations
    counts: dict[str, int] = {}
    for session_set in recent:
        for role in session_set:
            counts[role] = counts.get(role, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def compute_eval_staleness(evaluations_dir: Path, sessions_index: list[dict[str, str]]) -> tuple[int, int]:
    """How stale is the eval? Returns (sessions_since_eval, files_changed).

    sessions_since_eval: number of sessions since the last evaluation report.
    files_changed: number of nightshift/ files modified since the eval date
    (approximated by counting commits touching nightshift/ since the eval).
    """
    # Find the latest eval report by file modification time
    eval_date = ""
    eval_mtime = ""
    if evaluations_dir.is_dir():
        evals = sorted(evaluations_dir.glob("[0-9]*.md"))
        if evals:
            latest = evals[-1]
            try:
                text = latest.read_text(encoding="utf-8")
                dm = re.search(r"\*?\*?[Dd]ate\*?\*?:\s*(\d{4}-\d{2}-\d{2})", text)
                if dm:
                    eval_date = dm.group(1)
                # Use file mtime for precise timestamp (YYYY-MM-DD HH:MM)
                mt = latest.stat().st_mtime
                from datetime import datetime as _dt

                eval_mtime = _dt.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M")
            except OSError:
                pass

    # Count sessions that happened AFTER the eval
    sessions_since = len(sessions_index)
    compare_ts = eval_mtime if eval_mtime else eval_date
    if compare_ts:
        sessions_since = 0
        for row in reversed(sessions_index):
            ts = row.get("timestamp", "")
            if ts > compare_ts:
                sessions_since += 1
            else:
                break

    # Count nightshift files changed since eval via git
    files_changed = 0
    if eval_date:
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", f"--since={eval_date}", "--name-only", "--", "nightshift/"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                paths = {
                    line.strip()
                    for line in result.stdout.splitlines()
                    if line.strip().startswith("nightshift/") and line.strip().endswith(".py")
                }
                files_changed = len(paths)
        except (OSError, subprocess.SubprocessError):
            pass

    return sessions_since, files_changed


def compute_commitment_quality(commitments_log: Path, window: int = 10) -> str:
    """Assess whether the brain's predictions are genuinely risky or always safe.

    Reads the last N commitment entries and classifies them as:
    - 'safe' if predictions are vague ('PR will merge', 'make check passes')
    - 'specific' if predictions include numbers or specific outcomes
    Returns a summary string like '8/10 MET, mostly safe predictions'.
    """
    try:
        text = commitments_log.read_text(encoding="utf-8")
    except OSError:
        return "no data"
    blocks = re.split(r"(?=^## \d{4}-\d{2}-\d{2})", text, flags=re.MULTILINE)
    entries: list[dict[str, str]] = []
    for block in blocks:
        if not re.match(r"^## \d{4}-\d{2}-\d{2}", block):
            continue
        result_m = re.search(r"^\*\*Result\*\*:\s*(\w+)", block, re.MULTILINE)
        pred_m = re.search(r"^\*\*Prediction\*\*:\s*(.+)", block, re.MULTILINE)
        if result_m:
            entries.append(
                {
                    "result": result_m.group(1).upper(),
                    "prediction": pred_m.group(1) if pred_m else "",
                }
            )
    recent = entries[-window:]
    if not recent:
        return "no data"
    met = sum(1 for e in recent if e["result"] == "MET")
    total = len(recent)
    # A prediction is 'specific' if it contains a number or comparison
    specific = sum(
        1 for e in recent if re.search(r"\d+|>=|<=|improve|decrease|rise|fall", e["prediction"], re.IGNORECASE)
    )
    safe = total - specific
    quality = "mostly specific" if specific > safe else "mostly safe"
    return f"{met}/{total} MET, {quality} predictions"


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
