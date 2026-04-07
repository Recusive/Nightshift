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
                created = datetime.strptime(match.group(1), "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                age_days = (datetime.now(tz=timezone.utc) - created).days
                if age_days >= threshold:
                    count += 1
            except ValueError:
                continue
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


def count_recent_security_sessions(
    index_rows: list[dict[str, str]], tasks_dir: Path
) -> int:
    """Dual-signal count of recent security-driven BUILD sessions.

    Signal A (fast, lossy): Feature field contains security keywords.
    Signal B (robust, structured): archived tasks with source: pentest.
    Returns max(A, B) so the anti-loop activates if either signal fires.
    """
    feature_count = sum(
        1
        for r in index_rows[-5:]
        if r.get("role", "").strip() == "build"
        and any(kw in r.get("feature", "").lower() for kw in _SECURITY_KEYWORDS)
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
    "recent_security_sessions": 0,
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
    # Anti-loop: demote BUILD when recent sessions are security-dominated
    rs = signals.get("recent_security_sessions", 0)
    if rs >= 3 and signals["urgent_tasks"]:
        build -= 15  # still eligible, but not automatically dominant

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
    elif pt >= 30 and so >= 5:
        oversee += 25  # medium queue, hasn't been overseen in a while
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
    elif auto < 90:
        achieve += 20  # room for improvement even above 70
    if nh >= 3:
        achieve += 30
    if sa >= 15:
        achieve += 25  # hasn't run in a long time, system needs autonomy check
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


def pick_role(scores: dict[str, int], urgent: bool, recent_security: int = 0) -> str:
    """Pick the winning role. Urgent forces BUILD unless in security loop."""
    if urgent and recent_security < 3:
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
    force_role = os.environ.get("RECURSIVE_FORCE_ROLE", "").lower().strip()
    if force_role in ("build", "review", "oversee", "strategize", "achieve"):
        print(f"ROLE DECISION (pick-role.py)", file=sys.stderr)
        print(f"============================", file=sys.stderr)
        print(f"FORCED: {force_role} (via RECURSIVE_FORCE_ROLE)", file=sys.stderr)
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

    recent_security = count_recent_security_sessions(index_rows, tasks_dir)

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
        "recent_security_sessions": recent_security,
    }

    scores = compute_scores(signals)
    winner = pick_role(scores, urgent, recent_security)

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

    # --with-signals: write JSON signals to a file for prompt injection
    # The daemon reads this file and injects it as <system_signals> in the prompt.
    # Schema is numeric/boolean/enum ONLY — no free-form strings (trust boundary).
    signals_path = None
    for i, arg in enumerate(sys.argv):
        if arg == "--with-signals" and i + 1 < len(sys.argv):
            signals_path = sys.argv[i + 1]
    if signals_path:
        import json

        # Build safe signals (no free-form text that could be prompt injection)
        safe_signals = {
            "eval_score": signals["eval_score"],
            "autonomy_score": signals["autonomy_score"],
            "consecutive_builds": signals["consecutive_builds"],
            "sessions_since_review": signals["sessions_since_review"],
            "sessions_since_strategy": signals["sessions_since_strategy"],
            "sessions_since_achieve": signals["sessions_since_achieve"],
            "sessions_since_oversee": signals["sessions_since_oversee"],
            "pending_tasks": signals["pending_tasks"],
            "stale_tasks": signals["stale_tasks"],
            "urgent_tasks": signals["urgent_tasks"],
            "recent_security_sessions": signals["recent_security_sessions"],
            "healer_status": signals["healer_status"],
            "needs_human_issues": signals["needs_human_issues"],
            "tracker_moved": signals["tracker_moved"],
            "recent_roles": [
                r.get("role", "unknown").strip()
                for r in index_rows[-5:]
            ],
        }
        try:
            with open(signals_path, "w") as f:
                json.dump(safe_signals, f, indent=2)
            print(f"  Signals written to {signals_path}", file=sys.stderr)
        except OSError as e:
            print(f"  WARN: could not write signals: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
