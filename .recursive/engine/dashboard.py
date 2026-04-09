"""Dashboard data aggregator for the Recursive autonomous framework.

Collects all system signals into a structured dict and formats them as
a human-readable dashboard.  Used by the v2 brain prompt to understand
system state before delegating to sub-agents.

Usage:
    python3 .recursive/engine/dashboard.py .recursive/
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure signals.py is importable regardless of working directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from signals import (
    DEFAULTS,
    compute_agent_diversity,
    compute_commitment_quality,
    compute_eval_staleness,
    compute_queue_trend,
    count_consecutive_role,
    count_friction_entries,
    count_needs_human_issues,
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

# All roles tracked by sessions_since
_ROLES = (
    "build",
    "review",
    "strategize",
    "achieve",
    "oversee",
    "security-check",
    "evolve",
    "audit",
)


def collect_signals(recursive_dir: Path) -> dict[str, object]:
    """Read all system signals from the .recursive/ runtime directory.

    Returns a dict matching the DEFAULTS schema with live values.
    Gracefully handles missing files/directories by returning defaults.

    All reads are done at call time (snapshot semantics). If .recursive/
    state is modified by a concurrent process during collection, the
    dashboard may mix old and new data. The brain should treat dashboard
    values as approximate, not exact.
    """
    evaluations_dir = recursive_dir / "evaluations"
    autonomy_dir = recursive_dir / "autonomy"
    index_path = recursive_dir / "sessions" / "index.md"
    tasks_dir = recursive_dir / "tasks"
    healer_path = recursive_dir / "healer" / "log.md"
    friction_path = recursive_dir / "friction" / "log.md"
    eval_score = read_latest_eval_score(evaluations_dir)
    autonomy_score = read_latest_autonomy_score(autonomy_dir)
    index_rows = parse_session_index(index_path)
    healer_status = read_healer_status(healer_path)
    pending = count_pending_tasks(tasks_dir)
    stale = count_stale_tasks(tasks_dir)
    urgent = has_urgent_tasks(tasks_dir)
    needs_human = count_needs_human_issues()
    tracker_moved = did_tracker_move(index_rows)
    recent_security = count_recent_security_sessions(index_rows, tasks_dir)

    # Parse decisions log once -- used for both delegation-aware counters and
    # active experiment counting.
    decisions_path = recursive_dir / "decisions" / "log.md"
    delegations = parse_delegations_from_decisions_log(decisions_path)

    signals: dict[str, object] = {
        "eval_score": eval_score if eval_score is not None else DEFAULTS["eval_score"],
        "autonomy_score": autonomy_score if autonomy_score is not None else DEFAULTS["autonomy_score"],
        "consecutive_builds": count_consecutive_role(index_rows, "build"),
        "pending_tasks": pending,
        "stale_tasks": stale,
        "healer_status": healer_status,
        "needs_human_issues": needs_human,
        "tracker_moved": tracker_moved,
        "urgent_tasks": urgent,
        "recent_security_sessions": recent_security,
        "friction_entries": count_friction_entries(friction_path),
        "total_sessions": len(index_rows),
        "recent_roles": [r.get("role", "unknown").strip() for r in index_rows[-5:]],
    }

    # Add sessions_since for each role using delegation-aware counting.
    # In v2 brain sessions every session is recorded as role=brain in the
    # index.  The decisions log records which sub-agents were actually
    # delegated.  count_sessions_since_delegation() takes the minimum of
    # the raw index count and the delegation-log count so that sessions
    # appear up-to-date regardless of whether they ran v1 standalone or
    # v2 sub-agent style.
    for role in _ROLES:
        key = f"sessions_since_{role.replace('-', '_')}"
        signals[key] = count_sessions_since_delegation(index_rows, role, delegations)

    # Mark which signals are using defaults (for dashboard display)
    signals["_eval_is_default"] = eval_score is None
    signals["_autonomy_is_default"] = autonomy_score is None

    # Count active experiments from decisions log (reuse the already-read file)
    active_experiments = 0
    if decisions_path.is_file():
        try:
            content = decisions_path.read_text(encoding="utf-8")
            active_experiments = content.count("**Status**: ACTIVE")
        except OSError:
            pass
    signals["active_experiments"] = active_experiments

    # Budget awareness
    costs_path = recursive_dir / "sessions" / "costs.json"
    budget_spent = 0.0
    if costs_path.is_file():
        try:
            entries = json.loads(costs_path.read_text(encoding="utf-8"))
            if isinstance(entries, list):
                budget_spent = sum(e.get("cost_usd", 0) for e in entries)
        except (json.JSONDecodeError, OSError):
            pass
    signals["budget_spent"] = round(budget_spent, 2)

    # Task composition (what KIND of work is pending, not just how much)
    task_composition: dict[str, int] = {}
    human_tasks = 0
    if tasks_dir.is_dir():
        for tf in tasks_dir.glob("[0-9]*.md"):
            try:
                text = tf.read_text(encoding="utf-8")
                if "status: pending" not in text:
                    continue
                if "source: github-issue" in text:
                    human_tasks += 1
                # Categorize by source
                for cat in ("pentest", "code-review", "audit", "github-issue"):
                    if f"source: {cat}" in text:
                        task_composition[cat] = task_composition.get(cat, 0) + 1
                        break
                else:
                    task_composition["feature/other"] = task_composition.get("feature/other", 0) + 1
            except OSError:
                continue
    signals["task_composition"] = task_composition
    signals["human_tasks"] = human_tasks

    # Blocked tasks (brain should periodically reassess these)
    blocked_count = 0
    if tasks_dir.is_dir():
        for tf in tasks_dir.glob("[0-9]*.md"):
            try:
                text = tf.read_text(encoding="utf-8")
                if "status: blocked" in text:
                    blocked_count += 1
            except OSError:
                continue
    signals["blocked_tasks"] = blocked_count

    # Decision-consequence signals (self-awareness)
    signals["queue_trend"] = compute_queue_trend(decisions_path)
    signals["agent_diversity"] = compute_agent_diversity(delegations)
    eval_sessions, eval_files = compute_eval_staleness(evaluations_dir, index_rows)
    signals["eval_sessions_since"] = eval_sessions
    signals["eval_files_changed"] = eval_files
    commitments_path = recursive_dir / "commitments" / "log.md"
    signals["commitment_quality"] = compute_commitment_quality(commitments_path)

    return signals


def format_dashboard(signals: dict[str, object]) -> str:
    """Format collected signals as a human-readable dashboard.

    Output is intended for injection into the brain prompt as a
    <dashboard> block.
    """
    lines: list[str] = []
    lines.append("=== System Dashboard ===")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")

    # Health
    eval_note = " (default)" if signals.get("_eval_is_default") else ""
    auto_note = " (default)" if signals.get("_autonomy_is_default") else ""
    lines.append(f"Eval score:     {signals['eval_score']}/100{eval_note}")
    lines.append(f"Autonomy score: {signals['autonomy_score']}/100{auto_note}")
    lines.append(f"Healer status:  {signals['healer_status']}")
    nh_note = " (may be inaccurate if gh unavailable)" if signals["needs_human_issues"] == 0 else ""
    lines.append(f"Needs-human:    {signals['needs_human_issues']} open issues{nh_note}")
    lines.append("")

    # Budget
    spent = signals.get("budget_spent", 0)
    lines.append(f"Budget spent:   ${spent}")
    lines.append("")

    # Queue
    lines.append(f"Pending tasks:  {signals['pending_tasks']}")
    comp = signals.get("task_composition", {})
    if isinstance(comp, dict) and comp:
        comp_str = ", ".join(f"{k}: {v}" for k, v in sorted(comp.items(), key=lambda x: -x[1]))
        lines.append(f"  Breakdown:    {comp_str}")
    human = signals.get("human_tasks", 0)
    if isinstance(human, int) and human > 0:
        lines.append(f"  From human:   {human} (prioritize these)")
    blocked = signals.get("blocked_tasks", 0)
    if isinstance(blocked, int) and blocked > 0:
        lines.append(f"Blocked tasks:  {blocked} (reassess -- blockers may be resolved)")
    lines.append(f"Stale tasks:    {signals['stale_tasks']}")
    lines.append(f"Urgent tasks:   {signals['urgent_tasks']}")
    lines.append(f"Friction:       {signals['friction_entries']} entries")
    lines.append("")

    # Session history
    lines.append(f"Total sessions: {signals['total_sessions']}")
    lines.append(f"Consec builds:  {signals['consecutive_builds']}")
    recent = signals.get("recent_roles", [])
    lines.append(f"Recent roles:   {', '.join(str(r) for r in (recent if isinstance(recent, list) else []))}")
    lines.append(f"Tracker moved:  {signals['tracker_moved']}")
    lines.append(f"Recent security:{signals['recent_security_sessions']}")
    lines.append("")

    # Sessions since each role
    lines.append("Sessions since:")
    for role in _ROLES:
        key = f"sessions_since_{role.replace('-', '_')}"
        val = signals.get(key, "?")
        lines.append(f"  {role:16s} {val}")

    # Experiments
    lines.append("")
    exp_count = signals.get("active_experiments", 0)
    lines.append(f"Experiments:    {exp_count} active")

    # Decision patterns -- the mirror
    lines.append("")
    lines.append("Decision patterns (recent sessions):")
    queue_trend = signals.get("queue_trend", [])
    if isinstance(queue_trend, list) and queue_trend:
        trend_str = ", ".join(f"{d:+d}" for d in queue_trend)
        net = sum(queue_trend)
        direction = "growing" if net > 0 else "shrinking" if net < 0 else "stable"
        lines.append(f"  Queue trend:    {trend_str} (net: {net:+d} {direction})")
    else:
        lines.append("  Queue trend:    no data")

    diversity = signals.get("agent_diversity", {})
    if isinstance(diversity, dict) and diversity:
        used = ", ".join(f"{k}={v}" for k, v in diversity.items())
        all_agents = {"build", "evolve", "oversee", "strategize", "achieve", "security", "audit", "review"}
        unused = all_agents - set(diversity.keys())
        unused_str = ", ".join(sorted(unused)) if unused else "none"
        lines.append(f"  Agent mix:      {used}")
        lines.append(f"  Never used:     {unused_str}")
    else:
        lines.append("  Agent mix:      no data")

    eval_since = signals.get("eval_sessions_since", 0)
    eval_files = signals.get("eval_files_changed", 0)
    if isinstance(eval_since, int) and eval_since > 0:
        lines.append(f"  Eval staleness: {eval_since} sessions, {eval_files} nightshift files changed since last eval")
    else:
        lines.append("  Eval staleness: up to date")

    commit_q = signals.get("commitment_quality", "no data")
    lines.append(f"  Commitments:    {commit_q}")

    # Alerts
    lines.append("")
    lines.append("Alerts:")
    alerts: list[str] = []
    audit_since = signals.get("sessions_since_audit", 0)
    if isinstance(audit_since, int) and audit_since >= 25:
        alerts.append(f"  Framework audit overdue ({audit_since} sessions since last)")
    evolve_since = signals.get("sessions_since_evolve", 0)
    friction = signals.get("friction_entries", 0)
    if isinstance(friction, int) and friction >= 3:
        alerts.append(f"  Friction threshold met ({friction} entries -- evolve recommended)")
    if isinstance(evolve_since, int) and evolve_since >= 25:
        alerts.append(f"  Evolve overdue ({evolve_since} sessions since last)")
    strat_since = signals.get("sessions_since_strategize", 0)
    if isinstance(strat_since, int) and strat_since >= 15:
        alerts.append(f"  Strategize overdue ({strat_since} sessions since last)")
    if not alerts:
        alerts.append("  None")
    lines.extend(alerts)

    return "\n".join(lines)


def main() -> None:
    """CLI entry point: print dashboard for a given .recursive/ directory."""
    if len(sys.argv) < 2:
        print("Usage: python3 .recursive/engine/dashboard.py .recursive/", file=sys.stderr)
        sys.exit(1)

    recursive_dir = Path(sys.argv[1])
    if not recursive_dir.is_dir():
        print(f"Error: {recursive_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    signals = collect_signals(recursive_dir)
    print(format_dashboard(signals))

    # Also emit JSON for machine consumption if --json flag
    if "--json" in sys.argv:
        # Strip internal keys
        clean = {k: v for k, v in signals.items() if not k.startswith("_")}
        print("\n--- JSON ---")
        print(json.dumps(clean, indent=2, default=str))


if __name__ == "__main__":
    main()
