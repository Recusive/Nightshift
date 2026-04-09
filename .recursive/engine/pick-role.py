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
import sys
from pathlib import Path
from typing import Any

from signals import (
    DEFAULTS,
    count_consecutive_role,
    count_friction_entries,
    count_needs_human_issues,
    count_pending_pentest_framework_tasks,
    count_pending_tasks,
    count_recent_security_sessions,
    count_sessions_since_delegation,
    count_stale_tasks,
    did_tracker_move,
    has_urgent_tasks,
    parse_delegations_from_decisions_log,
    parse_session_index,
    read_healer_status,
    read_latest_autonomy_score,
    read_latest_eval_score,
)

# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------


def compute_scores(signals: dict[str, Any]) -> dict[str, int]:
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

    # BUILD -- the default workhorse
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

    # REVIEW -- code quality
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

    # OVERSEE -- close tasks, reduce the queue
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

    # STRATEGIZE -- big picture
    strategize = 5
    if ss >= 15:
        strategize += 60
    if not tm:
        strategize += 30

    # ACHIEVE -- autonomy engineering
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

    # SECURITY-CHECK -- red team / adversarial audit
    sc = signals.get("sessions_since_security", 0)
    security = 5
    if sc >= 10:
        security += 50  # overdue for security review
    if sc >= 5:
        security += 20  # getting stale
    if cb >= 5 and sc >= 3:
        security += 15  # lots of builds without security review

    # EVOLVE -- framework improvement (reads friction log)
    se = signals.get("sessions_since_evolve", 0)
    fe = signals.get("friction_entries", 0)
    pf = signals.get("pentest_framework_tasks", 0)
    evolve = 5
    if fe >= 5:
        evolve += 50  # lots of friction accumulated
    if fe >= 3 and se >= 5:
        evolve += 30  # moderate friction, hasn't evolved recently
    if se >= 20:
        evolve += 20  # overdue regardless of friction count
    if pf >= 1:
        evolve += 40  # pending pentest findings targeting .recursive/ -- security urgency

    # AUDIT -- framework quality review
    saud = signals.get("sessions_since_audit", 0)
    audit = 5
    if saud >= 25:
        audit += 50  # overdue for framework audit
    if saud >= 15:
        audit += 20  # getting stale

    # Hard constraints: caps
    if sa < 5:
        achieve = -1
    if ss < 10:
        strategize = min(strategize, 5)
    if sc < 3:
        security = min(security, 5)  # don't re-run too frequently
    if se < 5 and pf == 0:
        evolve = min(evolve, 5)  # don't re-run too frequently (unless pentest tasks pending)
    if saud < 10:
        audit = min(audit, 5)  # don't re-run too frequently
    if fe == 0 and pf == 0:
        evolve = min(evolve, 5)  # no friction and no pentest tasks = nothing to evolve

    return {
        "build": build,
        "review": review,
        "oversee": oversee,
        "strategize": strategize,
        "achieve": achieve,
        "security-check": security,
        "evolve": evolve,
        "audit": audit,
    }


def pick_role(scores: dict[str, int], urgent: bool, recent_security: int = 0) -> str:
    """Pick the winning role. Urgent forces BUILD unless in security loop."""
    if urgent and recent_security < 3:
        return "build"
    # Sort by score descending, then prefer build on ties
    priority = ["build", "oversee", "review", "security-check", "evolve", "achieve", "strategize", "audit"]
    best_score = max(scores.values())
    for role in priority:
        if scores[role] == best_score:
            return role
    return "build"


# ---------------------------------------------------------------------------
# Advisory helpers
# ---------------------------------------------------------------------------


def _score_note(role: str, signals: dict[str, Any]) -> str:
    """Return a short human-readable reason for a role's score."""
    notes = {
        "build": f"eval={signals['eval_score']}, urgent={signals['urgent_tasks']}, since_build={signals.get('sessions_since_build', 0)}",
        "review": f"consec_builds={signals['consecutive_builds']}, healer={signals['healer_status']}",
        "oversee": f"pending={signals['pending_tasks']}, stale={signals['stale_tasks']}",
        "strategize": f"since_strategy={signals.get('sessions_since_strategy', 0)}, tracker_moved={signals['tracker_moved']}",
        "achieve": f"autonomy={signals['autonomy_score']}, needs_human={signals['needs_human_issues']}",
        "security-check": f"since_security={signals.get('sessions_since_security', 0)}, consec_builds={signals['consecutive_builds']}",
        "evolve": f"friction={signals.get('friction_entries', 0)}, pentest_framework={signals.get('pentest_framework_tasks', 0)}, since_evolve={signals.get('sessions_since_evolve', 0)}",
        "audit": f"since_audit={signals.get('sessions_since_audit', 0)}",
    }
    return notes.get(role, "")


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
    if force_role in ("build", "review", "oversee", "strategize", "achieve", "security-check", "evolve", "audit"):
        print("ROLE DECISION (pick-role.py)", file=sys.stderr)
        print("============================", file=sys.stderr)
        print(f"FORCED: {force_role} (via RECURSIVE_FORCE_ROLE)", file=sys.stderr)
        print(force_role)
        sys.exit(0)

    # Read signals
    eval_score = read_latest_eval_score(repo / ".recursive" / "evaluations")
    autonomy_score = read_latest_autonomy_score(repo / ".recursive" / "autonomy")
    index_rows = parse_session_index(repo / ".recursive" / "sessions" / "index.md")
    delegations = parse_delegations_from_decisions_log(repo / ".recursive" / "decisions" / "log.md")
    healer_status = read_healer_status(repo / ".recursive" / "healer" / "log.md")
    tasks_dir = repo / ".recursive" / "tasks"
    pending = count_pending_tasks(tasks_dir)
    stale = count_stale_tasks(tasks_dir)
    urgent = has_urgent_tasks(tasks_dir)
    needs_human = count_needs_human_issues()
    tracker_moved = did_tracker_move(index_rows)

    recent_security = count_recent_security_sessions(index_rows, tasks_dir)
    pentest_framework = count_pending_pentest_framework_tasks(tasks_dir)

    signals = {
        "eval_score": eval_score if eval_score is not None else DEFAULTS["eval_score"],
        "autonomy_score": autonomy_score if autonomy_score is not None else DEFAULTS["autonomy_score"],
        "consecutive_builds": count_consecutive_role(index_rows, "build"),
        "sessions_since_build": count_sessions_since_delegation(index_rows, "build", delegations),
        "sessions_since_review": count_sessions_since_delegation(index_rows, "review", delegations),
        "sessions_since_strategy": count_sessions_since_delegation(index_rows, "strategize", delegations),
        "sessions_since_achieve": count_sessions_since_delegation(index_rows, "achieve", delegations),
        "sessions_since_security": count_sessions_since_delegation(index_rows, "security-check", delegations),
        "sessions_since_oversee": count_sessions_since_delegation(index_rows, "oversee", delegations),
        "sessions_since_evolve": count_sessions_since_delegation(index_rows, "evolve", delegations),
        "sessions_since_audit": count_sessions_since_delegation(index_rows, "audit", delegations),
        "friction_entries": count_friction_entries(repo / ".recursive" / "friction" / "log.md"),
        "pentest_framework_tasks": pentest_framework,
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

    # --advise: output JSON advisory for the v2 brain (recommended + alternatives)
    if "--advise" in sys.argv:
        sorted_roles = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top = sorted_roles[0]
        alternatives = [{"role": r, "score": s, "note": _score_note(r, signals)} for r, s in sorted_roles[1:4] if s > 0]
        recent_roles = [r.get("role", "unknown").strip() for r in index_rows[-10:]]
        build_pct = sum(1 for r in recent_roles if r == "build") * 10
        drift_warning = ""
        if build_pct >= 80:
            drift_warning = f"{build_pct}% of last 10 sessions were BUILD"

        advisory = {
            "recommended": winner,
            "score": top[1],
            "reason": _score_note(winner, signals),
            "alternatives": alternatives,
            "drift_warning": drift_warning,
            "signals": {k: v for k, v in signals.items() if isinstance(v, (int, float, bool, str))},
            "recent_roles": [r.get("role", "unknown").strip() for r in index_rows[-5:]],
        }
        print(json.dumps(advisory, indent=2))
        sys.exit(0)

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
    # Schema is numeric/boolean/enum ONLY -- no free-form strings (trust boundary).
    signals_path = None
    for i, arg in enumerate(sys.argv):
        if arg == "--with-signals" and i + 1 < len(sys.argv):
            signals_path = sys.argv[i + 1]
    if signals_path:
        # Build safe signals (no free-form text that could be prompt injection)
        safe_signals = {
            "eval_score": signals["eval_score"],
            "autonomy_score": signals["autonomy_score"],
            "consecutive_builds": signals["consecutive_builds"],
            "sessions_since_review": signals["sessions_since_review"],
            "sessions_since_strategy": signals["sessions_since_strategy"],
            "sessions_since_achieve": signals["sessions_since_achieve"],
            "sessions_since_oversee": signals["sessions_since_oversee"],
            "sessions_since_security": signals["sessions_since_security"],
            "sessions_since_evolve": signals["sessions_since_evolve"],
            "sessions_since_audit": signals["sessions_since_audit"],
            "friction_entries": signals["friction_entries"],
            "pentest_framework_tasks": signals["pentest_framework_tasks"],
            "pending_tasks": signals["pending_tasks"],
            "stale_tasks": signals["stale_tasks"],
            "urgent_tasks": signals["urgent_tasks"],
            "recent_security_sessions": signals["recent_security_sessions"],
            "healer_status": signals["healer_status"],
            "needs_human_issues": signals["needs_human_issues"],
            "tracker_moved": signals["tracker_moved"],
            "recent_roles": [r.get("role", "unknown").strip() for r in index_rows[-5:]],
        }
        try:
            with open(signals_path, "w") as f:
                json.dump(safe_signals, f, indent=2)
            print(f"  Signals written to {signals_path}", file=sys.stderr)
        except OSError as e:
            print(f"  WARN: could not write signals: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
