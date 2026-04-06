"""Unified daemon role selector.

Reads system signal files, computes scores for each role, and prints
the winning role name to stdout.  The daemon shell script calls this
at the start of every cycle to decide which prompt to load.

Usage:
    python3 scripts/pick-role.py /path/to/repo

Prints one of: build, review, oversee, strategize, achieve
Also prints a human-readable scoring breakdown to stderr.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Signal readers — each returns a typed value, never raises
# ---------------------------------------------------------------------------

def read_latest_eval_score(evaluations_dir: Path) -> int | None:
    """Extract total score from the latest evaluation report."""
    files = sorted(evaluations_dir.glob("[0-9]*.md"))
    if not files:
        return None
    try:
        text = files[-1].read_text(encoding="utf-8")
        match = re.search(r"\*\*Total\*\*\s*\|\s*\*\*(\d+)/100\*\*", text)
        if match:
            return int(match.group(1))
        match = re.search(r"Total.*?(\d+)\s*/\s*100", text)
        if match:
            return int(match.group(1))
    except OSError:
        pass
    return None


def read_latest_autonomy_score(autonomy_dir: Path) -> int | None:
    """Extract autonomy score from the latest autonomy report."""
    files = sorted(autonomy_dir.glob("[0-9]*.md"))
    if not files:
        return None
    try:
        text = files[-1].read_text(encoding="utf-8")
        match = re.search(r"TOTAL:\s*(\d+)\s*/\s*100", text)
        if match:
            return int(match.group(1))
    except OSError:
        pass
    return None


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


def count_pending_tasks(tasks_dir: Path) -> int:
    """Count task files with status: pending."""
    count = 0
    for f in tasks_dir.glob("[0-9]*.md"):
        try:
            head = f.read_text(encoding="utf-8")[:500]
            if re.search(r"^status:\s*pending", head, re.MULTILINE):
                count += 1
        except OSError:
            continue
    return count


def count_stale_tasks(tasks_dir: Path, threshold: int = 20) -> int:
    """Count pending tasks older than threshold sessions."""
    count = 0
    for f in tasks_dir.glob("[0-9]*.md"):
        try:
            head = f.read_text(encoding="utf-8")[:500]
            if not re.search(r"^status:\s*pending", head, re.MULTILINE):
                continue
            # Rough staleness: check created date vs today
            match = re.search(r"^created:\s*(\d{4}-\d{2}-\d{2})", head, re.MULTILINE)
            if match:
                from datetime import datetime, timezone

                created = datetime.strptime(match.group(1), "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                age_days = (datetime.now(tz=timezone.utc) - created).days
                if age_days >= threshold:
                    count += 1
        except (OSError, ValueError):
            continue
    return count


def has_urgent_tasks(tasks_dir: Path) -> bool:
    """Check if any pending task has priority: urgent."""
    for f in tasks_dir.glob("[0-9]*.md"):
        try:
            head = f.read_text(encoding="utf-8")[:500]
            if re.search(r"^status:\s*pending", head, re.MULTILINE) and re.search(
                r"^priority:\s*urgent", head, re.MULTILINE
            ):
                return True
        except OSError:
            continue
    return False


def read_healer_status(healer_path: Path) -> str:
    """Read the last system health rating from the healer log."""
    try:
        text = healer_path.read_text(encoding="utf-8")
        matches = re.findall(r"\*\*System health:\*\*\s*(\w+)", text)
        if matches:
            return matches[-1].lower()
    except OSError:
        pass
    return "good"


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
# Scoring engine
# ---------------------------------------------------------------------------

DEFAULTS = {
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
}


def compute_scores(signals: dict) -> dict[str, int]:
    """Compute role scores from signals. Returns {role: score}."""
    ev = signals["eval_score"]
    auto = signals["autonomy_score"]
    cb = signals["consecutive_builds"]
    sr = signals["sessions_since_review"]
    ss = signals["sessions_since_strategy"]
    sa = signals["sessions_since_achieve"]
    sb = signals.get("sessions_since_build", 0)
    pt = signals["pending_tasks"]
    st = signals["stale_tasks"]
    hs = signals["healer_status"]
    nh = signals["needs_human_issues"]
    tm = signals["tracker_moved"]
    so = signals["sessions_since_oversee"]

    # BUILD — the default workhorse
    build = 50
    if ev >= 80:
        build += 30  # healthy eval, build freely
    else:
        build -= 20  # eval gated, but NOT locked out (-20 not -40)
    if signals["urgent_tasks"]:
        build += 20
    # Escape hatch: if BUILD hasn't run for 5+ cycles, boost it
    if sb >= 5:
        build += 25  # system needs to make progress, override other roles
    if sb >= 10:
        build += 15  # critical: nothing has been built in 10 sessions

    # REVIEW — code quality
    review = 10
    if cb >= 5:
        review += 40
    # Healer bonus decays after consecutive reviews
    if hs in ("concern", "caution") and sr >= 2:
        review += 30  # only if we haven't JUST reviewed
    elif hs in ("concern", "caution") and sr < 2:
        review += 10  # diminished: reviewed recently, healer may not have updated
    if sr >= 10:
        review += 20
    if sr >= 5:
        review += 10

    # OVERSEE — close tasks, reduce the queue
    oversee = 5
    if pt >= 80:
        oversee += 60  # critical queue size, must beat healthy BUILD (80)
    elif pt >= 50 and so >= 3:
        oversee += 45  # large queue, not recently overseen
    elif pt >= 50 and so >= 1:
        oversee += 20  # large queue but was recently overseen
    if st >= 5:
        oversee += 25
    # Cap: don't re-run immediately after a CLEAN signal
    if so == 0:
        oversee = 5  # just ran last cycle, give others a turn

    # STRATEGIZE — big picture
    strategize = 5
    if ss >= 15:
        strategize += 60
    if not tm:
        strategize += 30

    # ACHIEVE — autonomy engineering
    achieve = 5
    if auto < 70:
        achieve += 50
    if nh >= 3:
        achieve += 30
    if ev < 80 and sr >= 10:
        achieve += 20
    if cb >= 10:
        achieve += 15

    # Hard constraints: caps
    if sa < 5:
        achieve = -1
    if ss < 10:
        strategize = min(strategize, 5)

    return {
        "build": build,
        "review": review,
        "oversee": oversee,
        "strategize": strategize,
        "achieve": achieve,
    }


def pick_role(scores: dict[str, int], urgent: bool) -> str:
    """Pick the winning role. Urgent forces BUILD. Ties go to BUILD."""
    if urgent:
        return "build"
    # Sort by score descending, then prefer build on ties
    priority = ["build", "oversee", "review", "achieve", "strategize"]
    best_score = max(scores.values())
    for role in priority:
        if scores[role] == best_score:
            return role
    return "build"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/pick-role.py /path/to/repo", file=sys.stderr)
        print("build")
        sys.exit(0)

    repo = Path(sys.argv[1])
    force_role = os.environ.get("NIGHTSHIFT_FORCE_ROLE", "").lower().strip()
    if force_role in ("build", "review", "oversee", "strategize", "achieve"):
        print(f"ROLE DECISION (pick-role.py)", file=sys.stderr)
        print(f"============================", file=sys.stderr)
        print(f"FORCED: {force_role} (via NIGHTSHIFT_FORCE_ROLE)", file=sys.stderr)
        print(force_role)
        sys.exit(0)

    # Read signals
    eval_score = read_latest_eval_score(repo / "docs" / "evaluations")
    autonomy_score = read_latest_autonomy_score(repo / "docs" / "autonomy")
    index_rows = parse_session_index(repo / "docs" / "sessions" / "index.md")
    healer_status = read_healer_status(repo / "docs" / "healer" / "log.md")
    tasks_dir = repo / "docs" / "tasks"
    pending = count_pending_tasks(tasks_dir)
    stale = count_stale_tasks(tasks_dir)
    urgent = has_urgent_tasks(tasks_dir)
    needs_human = count_needs_human_issues()
    tracker_moved = did_tracker_move(index_rows)

    signals = {
        "eval_score": eval_score if eval_score is not None else DEFAULTS["eval_score"],
        "autonomy_score": autonomy_score if autonomy_score is not None else DEFAULTS["autonomy_score"],
        "consecutive_builds": count_consecutive_role(index_rows, "build"),
        "sessions_since_build": count_sessions_since_role(index_rows, "build"),
        "sessions_since_review": count_sessions_since_role(index_rows, "review"),
        "sessions_since_strategy": count_sessions_since_role(index_rows, "strategize"),
        "sessions_since_achieve": count_sessions_since_role(index_rows, "achieve"),
        "sessions_since_oversee": count_sessions_since_role(index_rows, "oversee"),
        "pending_tasks": pending,
        "stale_tasks": stale,
        "healer_status": healer_status,
        "needs_human_issues": needs_human,
        "tracker_moved": tracker_moved,
        "urgent_tasks": urgent,
    }

    scores = compute_scores(signals)
    winner = pick_role(scores, urgent)

    # Log reasoning to stderr (daemon captures this)
    print("ROLE DECISION (pick-role.py)", file=sys.stderr)
    print("============================", file=sys.stderr)
    for key, val in signals.items():
        src = ""
        if key == "eval_score" and eval_score is None:
            src = " (default)"
        elif key == "autonomy_score" and autonomy_score is None:
            src = " (default: no reports)"
        print(f"  {key:28s} {val}{src}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Scoring:", file=sys.stderr)
    for role, score in scores.items():
        marker = " <-- WINNER" if role == winner else ""
        cap = " (CAPPED)" if score == -1 else ""
        print(f"  {role:14s} {score:4d}{cap}{marker}", file=sys.stderr)
    print(f"\n-> {winner}", file=sys.stderr)

    # Print just the role name to stdout for the daemon
    print(winner)


if __name__ == "__main__":
    main()
