"""Cost tracking for daemon sessions -- parse token usage from logs and maintain a ledger."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

from nightshift.constants import AGENT_DEFAULT_MODELS, COST_LEDGER_FILENAME, MODEL_PRICING
from nightshift.types import CostAnalysis, CostLedger, CostOutlier, ModelEfficiency, SessionCost, TaskTypeCostStats


class _SessionIndexEntry(TypedDict):
    duration_minutes: int
    feature: str


class _SessionSummary(TypedDict):
    task_type: str
    tests_added: int
    tracker_delta_points: float


def parse_session_tokens(log_path: str, *, model_hint: str = "") -> SessionCost:
    """Parse a stream-json session log and sum token usage across all messages.

    Supports two log formats:

    * **Claude** (``type: "assistant"``): usage nested under ``message.usage``
      with ``input_tokens``, ``cache_creation_input_tokens``,
      ``cache_read_input_tokens``, and ``output_tokens``.
    * **Codex/OpenAI** (``type: "turn.completed"``): usage at the event top
      level with ``input_tokens`` (total, including cached),
      ``cached_input_tokens``, and ``output_tokens``.

    For Codex events, ``input_tokens`` includes cached tokens.  The parser
    subtracts ``cached_input_tokens`` so the returned ``input_tokens`` field
    reflects only non-cached input (charged at full rate).

    *model_hint* is used as the model when the log itself does not contain a
    model identifier (common for Codex logs).
    """
    input_tokens = 0
    cache_creation_tokens = 0
    cache_read_tokens = 0
    output_tokens = 0
    model = ""

    path = Path(log_path)
    if not path.exists():
        return _empty_cost("", "", model_hint or "")

    with path.open() as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                continue

            event_type = event.get("type")

            # --- Claude format: type="assistant", usage under message ---
            if event_type == "assistant":
                msg = event.get("message")
                if not isinstance(msg, dict):
                    continue

                if not model:
                    msg_model = msg.get("model", "")
                    if isinstance(msg_model, str) and msg_model:
                        model = msg_model

                usage = msg.get("usage")
                if not isinstance(usage, dict):
                    continue

                input_tokens += _int(usage.get("input_tokens"))
                cache_creation_tokens += _int(usage.get("cache_creation_input_tokens"))
                cache_read_tokens += _int(usage.get("cache_read_input_tokens"))
                output_tokens += _int(usage.get("output_tokens"))

            # --- Codex/OpenAI format: type="turn.completed", usage at top ---
            elif event_type == "turn.completed":
                usage = event.get("usage")
                if not isinstance(usage, dict):
                    continue

                raw_input = _int(usage.get("input_tokens"))
                cached = _int(usage.get("cached_input_tokens"))
                input_tokens += max(0, raw_input - cached)
                cache_read_tokens += cached
                output_tokens += _int(usage.get("output_tokens"))

    resolved_model = model or model_hint
    return _empty_cost(
        "",
        "",
        resolved_model,
        input_tokens,
        cache_creation_tokens,
        cache_read_tokens,
        output_tokens,
    )


def calculate_cost(
    model: str,
    input_tokens: int,
    cache_creation_tokens: int,
    cache_read_tokens: int,
    output_tokens: int,
) -> float:
    """Calculate estimated USD cost for the given token counts.

    Uses :data:`MODEL_PRICING` for known models.  Returns ``0.0`` for
    unrecognised models (tokens are still tracked).
    """
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return 0.0

    per_m = 1_000_000.0
    cost = (
        input_tokens * pricing["input"] / per_m
        + cache_creation_tokens * pricing["cache_creation"] / per_m
        + cache_read_tokens * pricing["cache_read"] / per_m
        + output_tokens * pricing["output"] / per_m
    )
    return round(cost, 6)


def read_ledger(ledger_path: str) -> CostLedger:
    """Read the cost ledger from disk.  Returns an empty ledger if the file is missing."""
    path = Path(ledger_path)
    if not path.exists():
        return {"total_cost_usd": 0.0, "sessions": []}

    try:
        with path.open() as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, ValueError, OSError):
        return {"total_cost_usd": 0.0, "sessions": []}

    if not isinstance(data, dict):
        return {"total_cost_usd": 0.0, "sessions": []}

    return {
        "total_cost_usd": float(data.get("total_cost_usd", 0.0)),
        "sessions": list(data.get("sessions", [])),
    }


def write_ledger(ledger_path: str, ledger: CostLedger) -> None:
    """Write the cost ledger to disk, creating parent directories if needed."""
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        json.dump(ledger, fh, indent=2)
        fh.write("\n")


def record_session(
    log_path: str,
    ledger_path: str,
    session_id: str,
    agent: str,
) -> SessionCost:
    """Parse a session log, calculate cost, append to the ledger, and return the cost entry."""
    model_hint = AGENT_DEFAULT_MODELS.get(agent, "")
    tokens = parse_session_tokens(log_path, model_hint=model_hint)
    entry = _session_entry_from_parts(session_id, agent, [tokens])

    ledger = read_ledger(ledger_path)
    ledger["sessions"].append(entry)
    ledger["total_cost_usd"] = round(ledger["total_cost_usd"] + entry["total_cost_usd"], 6)
    write_ledger(ledger_path, ledger)

    return entry


def record_session_bundle(
    log_paths: Sequence[str],
    ledger_path: str,
    session_id: str,
    agent: str,
    *,
    part_agents: Sequence[str] | None = None,
) -> SessionCost:
    """Record one logical session whose work spans multiple stream-json logs.

    This is used when the daemon runs a short red-team/pentest preflight before
    the main builder session. The bundle is recorded as a single ledger row so
    session costs stay aligned with the builder index.
    """
    model_hint = AGENT_DEFAULT_MODELS.get(agent, "")
    hints: list[str] = []
    if part_agents is None:
        hints = [model_hint] * len(log_paths)
    else:
        hints = [AGENT_DEFAULT_MODELS.get(part_agent, model_hint) for part_agent in part_agents]
        if len(hints) < len(log_paths):
            hints.extend([model_hint] * (len(log_paths) - len(hints)))
        else:
            hints = hints[: len(log_paths)]

    parts = [parse_session_tokens(path, model_hint=hint) for path, hint in zip(log_paths, hints)]
    entry = _session_entry_from_parts(session_id, agent, parts)

    ledger = read_ledger(ledger_path)
    ledger["sessions"].append(entry)
    ledger["total_cost_usd"] = round(ledger["total_cost_usd"] + entry["total_cost_usd"], 6)
    write_ledger(ledger_path, ledger)

    return entry


def total_cost(ledger_path: str) -> float:
    """Return the cumulative cost computed by summing session entries.

    This recomputes from the sessions[] list rather than trusting the cached
    total_cost_usd field.  A pre-poisoned total field cannot trigger a false
    budget stop or disable enforcement -- only real recorded sessions count.
    """
    ledger = read_ledger(ledger_path)
    return round(sum(s["total_cost_usd"] for s in ledger["sessions"]), 6)


def cost_analysis(sessions_dir: str) -> CostAnalysis:
    """Analyze cost patterns across recorded daemon sessions.

    Reads the cost ledger, session index, and per-session logs from *sessions_dir*.
    The returned structure groups average spend by task type, computes model
    efficiency against tests added and tracker movement, and flags sessions that
    cost at least 2x their same-type peers.
    """
    ledger = read_ledger(default_ledger_path(sessions_dir))
    index_entries = _parse_session_index(Path(sessions_dir) / "index.md")

    task_rows: list[tuple[str, str, float, int]] = []
    model_rows: dict[str, dict[str, float | int]] = {}

    for session in ledger["sessions"]:
        session_id = session["session_id"]
        index_entry = index_entries.get(session_id, {"duration_minutes": 0, "feature": "-"})
        summary = _parse_session_summary(Path(sessions_dir) / f"{session_id}.log", index_entry["feature"])
        task_rows.append(
            (
                session_id,
                summary["task_type"],
                session["total_cost_usd"],
                index_entry["duration_minutes"],
            )
        )

        model = session["model"] or AGENT_DEFAULT_MODELS.get(session["agent"], "")
        model_entry = model_rows.setdefault(
            model,
            {
                "sessions": 0,
                "total_cost_usd": 0.0,
                "tests_added": 0,
                "tracker_delta_points": 0.0,
            },
        )
        model_entry["sessions"] += 1
        model_entry["total_cost_usd"] += session["total_cost_usd"]
        model_entry["tests_added"] += summary["tests_added"]
        model_entry["tracker_delta_points"] += summary["tracker_delta_points"]

    task_type_breakdown = _build_task_type_breakdown(task_rows)
    outliers = _detect_outliers(task_rows, index_entries)
    model_efficiency = _build_model_efficiency(model_rows)

    return {
        "total_cost_usd": round(ledger["total_cost_usd"], 6),
        "sessions_analyzed": len(ledger["sessions"]),
        "task_type_breakdown": task_type_breakdown,
        "model_efficiency": model_efficiency,
        "outliers": outliers,
        "recommendations": _build_recommendations(task_type_breakdown, model_efficiency, outliers),
    }


def format_session_cost(cost: SessionCost) -> str:
    """Format a session cost as a human-readable one-liner."""
    total_tokens = (
        cost["input_tokens"] + cost["cache_creation_tokens"] + cost["cache_read_tokens"] + cost["output_tokens"]
    )
    return (
        f"Tokens: {total_tokens:,} "
        f"(in={cost['input_tokens']:,} "
        f"cache_w={cost['cache_creation_tokens']:,} "
        f"cache_r={cost['cache_read_tokens']:,} "
        f"out={cost['output_tokens']:,}) "
        f"Cost: ${cost['total_cost_usd']:.4f}"
    )


def default_ledger_path(sessions_dir: str) -> str:
    """Return the default ledger path for a sessions directory."""
    return os.path.join(sessions_dir, COST_LEDGER_FILENAME)


# --- Helpers -----------------------------------------------------------------


def _int(value: object) -> int:
    """Safely coerce a value to int, returning 0 for non-numeric values."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _empty_cost(
    session_id: str,
    agent: str,
    model: str,
    input_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
    output_tokens: int = 0,
) -> SessionCost:
    """Build a SessionCost dict."""
    return {
        "session_id": session_id,
        "agent": agent,
        "model": model,
        "input_tokens": input_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "cache_read_tokens": cache_read_tokens,
        "output_tokens": output_tokens,
        "total_cost_usd": 0.0,
    }


def _session_entry_from_parts(session_id: str, agent: str, parts: Sequence[SessionCost]) -> SessionCost:
    """Build a single ledger entry from one or more parsed log parts."""
    total_cost_usd = 0.0
    input_tokens = 0
    cache_creation_tokens = 0
    cache_read_tokens = 0
    output_tokens = 0
    models: list[str] = []

    for part in parts:
        if part["model"]:
            models.append(part["model"])
        input_tokens += part["input_tokens"]
        cache_creation_tokens += part["cache_creation_tokens"]
        cache_read_tokens += part["cache_read_tokens"]
        output_tokens += part["output_tokens"]
        total_cost_usd += calculate_cost(
            part["model"],
            part["input_tokens"],
            part["cache_creation_tokens"],
            part["cache_read_tokens"],
            part["output_tokens"],
        )

    return {
        "session_id": session_id,
        "agent": agent,
        "model": _merge_models(models),
        "input_tokens": input_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "cache_read_tokens": cache_read_tokens,
        "output_tokens": output_tokens,
        "total_cost_usd": round(total_cost_usd, 6),
    }


def _merge_models(models: Sequence[str]) -> str:
    """Collapse per-log model labels into a single ledger-friendly value."""
    unique_models = sorted({model for model in models if model})
    if not unique_models:
        return ""
    if len(unique_models) == 1:
        return unique_models[0]
    return f"mixed:{','.join(unique_models)}"


def _parse_session_index(index_path: Path) -> dict[str, _SessionIndexEntry]:
    """Parse the builder session index, tolerating legacy rows without a Cost column."""
    if not index_path.exists():
        return {}

    entries: dict[str, _SessionIndexEntry] = {}
    for line in index_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---"):
            continue

        cells = [cell.strip() for cell in stripped.split("|")[1:-1]]
        if len(cells) < 7 or cells[0] == "Timestamp":
            continue

        session_id = cells[1]
        if not re.fullmatch(r"[A-Za-z0-9-]+", session_id):
            continue

        feature = "-"
        if len(cells) >= 8:
            feature = cells[6] or "-"
        elif len(cells) == 7:
            feature = cells[5] or "-"

        entries[session_id] = {
            "duration_minutes": _parse_duration_minutes(cells[3]),
            "feature": feature,
        }

    return entries


def _parse_duration_minutes(value: str) -> int:
    """Parse duration strings like ``22m`` or ``1h 5m`` into minutes."""
    hours = 0
    minutes = 0
    match_hours = re.search(r"(\d+)h", value)
    match_minutes = re.search(r"(\d+)m", value)
    if match_hours:
        hours = int(match_hours.group(1))
    if match_minutes:
        minutes = int(match_minutes.group(1))
    if hours == 0 and minutes == 0 and value.isdigit():
        return int(value)
    return hours * 60 + minutes


def _parse_session_summary(log_path: Path, feature: str) -> _SessionSummary:
    """Extract task type, tests added, and tracker delta from a session log."""
    report_text = ""
    task_type = "unknown"

    if log_path.exists():
        for line in log_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                continue

            event_type = event.get("type")
            if event_type == "result":
                result = event.get("result")
                if isinstance(result, str) and result:
                    report_text = result
            elif event_type == "item.completed":
                item = event.get("item")
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type")
                if item_type == "agent_message":
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        report_text = text
                elif item_type == "command_execution":
                    command = item.get("command")
                    if isinstance(command, str):
                        parsed_type = _parse_task_type_from_command(command)
                        if parsed_type:
                            task_type = parsed_type

    if task_type == "unknown":
        task_type = _infer_task_type_from_feature(feature)

    return {
        "task_type": task_type,
        "tests_added": _extract_tests_added(report_text),
        "tracker_delta_points": _extract_tracker_delta(report_text),
    }


def _parse_task_type_from_command(command: str) -> str | None:
    """Extract a commit/PR type prefix from a shell command string."""
    patterns = (
        r"git commit -m [\"']([a-z]+):",
        r"gh pr create --title [\"']([a-z]+):",
        r"git checkout -b ([a-z]+)/",
    )
    for pattern in patterns:
        match = re.search(pattern, command)
        if match:
            return match.group(1)
    return None


def _infer_task_type_from_feature(feature: str) -> str:
    """Best-effort task-type classification when logs do not expose commit metadata."""
    lowered = feature.lower()
    if not feature or feature == "-":
        return "unknown"
    if "release" in lowered:
        return "release"
    if any(word in lowered for word in ("doc", "readme", "prompt", "handoff", "strategy", "changelog")):
        return "docs"
    if any(word in lowered for word in ("test", "assert", "coverage")):
        return "test"
    if any(word in lowered for word in ("fix", "repair", "cleanup", "harden")):
        return "fix"
    if any(word in lowered for word in ("refactor", "typed", "rename", "parity")):
        return "refactor"
    return "feat"


def _extract_tests_added(report_text: str) -> int:
    """Extract the number of newly added tests from a final session report."""
    patterns = (
        r"Tests:\s*\+?(\d+)\s+new",
        r"(\d+)\s+new tests",
    )
    for pattern in patterns:
        match = re.search(pattern, report_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0


def _extract_tracker_delta(report_text: str) -> float:
    """Extract overall tracker movement in percentage points from a final report."""
    patterns = (
        r"Tracker delta:\s*`?(\d+(?:\.\d+)?)%\s*->\s*(\d+(?:\.\d+)?)%`?",
        r"Overall:\s*(\d+(?:\.\d+)?)%\s*->\s*(\d+(?:\.\d+)?)%",
    )
    for pattern in patterns:
        match = re.search(pattern, report_text)
        if match:
            start = float(match.group(1))
            end = float(match.group(2))
            return round(end - start, 2)
    return 0.0


def _build_task_type_breakdown(task_rows: list[tuple[str, str, float, int]]) -> list[TaskTypeCostStats]:
    """Compute average cost and duration per task type."""
    grouped: dict[str, dict[str, float | int]] = {}
    for _, task_type, cost_usd, duration_minutes in task_rows:
        group = grouped.setdefault(
            task_type,
            {
                "sessions": 0,
                "total_cost_usd": 0.0,
                "total_duration_minutes": 0,
            },
        )
        group["sessions"] += 1
        group["total_cost_usd"] += cost_usd
        group["total_duration_minutes"] += duration_minutes

    breakdown: list[TaskTypeCostStats] = []
    for task_type, values in sorted(grouped.items()):
        sessions = int(values["sessions"])
        average_cost = float(values["total_cost_usd"]) / sessions if sessions else 0.0
        average_duration = int(values["total_duration_minutes"]) / sessions if sessions else 0.0
        breakdown.append(
            {
                "task_type": task_type,
                "sessions": sessions,
                "average_cost_usd": round(average_cost, 4),
                "average_duration_minutes": round(average_duration, 2),
            }
        )
    return breakdown


def _build_model_efficiency(model_rows: dict[str, dict[str, float | int]]) -> list[ModelEfficiency]:
    """Compute per-model cost efficiency against tests and tracker movement."""
    efficiency: list[ModelEfficiency] = []
    for model, values in sorted(model_rows.items()):
        total_cost_usd = float(values["total_cost_usd"])
        tests_added = int(values["tests_added"])
        tracker_delta_points = float(values["tracker_delta_points"])
        efficiency.append(
            {
                "model": model,
                "sessions": int(values["sessions"]),
                "total_cost_usd": round(total_cost_usd, 4),
                "tests_added": tests_added,
                "tracker_delta_points": round(tracker_delta_points, 2),
                "cost_per_test_added_usd": round(total_cost_usd / tests_added, 4) if tests_added else None,
                "cost_per_tracker_delta_usd": (
                    round(total_cost_usd / tracker_delta_points, 4) if tracker_delta_points > 0 else None
                ),
            }
        )
    return efficiency


def _detect_outliers(
    task_rows: list[tuple[str, str, float, int]],
    index_entries: dict[str, _SessionIndexEntry],
) -> list[CostOutlier]:
    """Flag sessions that cost at least 2x the peer average for their task type."""
    grouped: dict[str, list[tuple[str, float]]] = {}
    for session_id, task_type, cost_usd, _ in task_rows:
        grouped.setdefault(task_type, []).append((session_id, cost_usd))

    outliers: list[CostOutlier] = []
    for task_type, sessions in grouped.items():
        if len(sessions) < 2:
            continue
        total = sum(cost for _, cost in sessions)
        for session_id, cost_usd in sessions:
            peer_average = (total - cost_usd) / (len(sessions) - 1)
            if peer_average <= 0 or cost_usd < (2 * peer_average):
                continue
            outliers.append(
                {
                    "session_id": session_id,
                    "task_type": task_type,
                    "feature": index_entries.get(session_id, {"duration_minutes": 0, "feature": "-"})["feature"],
                    "cost_usd": round(cost_usd, 4),
                    "peer_average_cost_usd": round(peer_average, 4),
                    "ratio_to_peer_average": round(cost_usd / peer_average, 2),
                }
            )
    return sorted(outliers, key=lambda item: item["ratio_to_peer_average"], reverse=True)


def _build_recommendations(
    task_types: list[TaskTypeCostStats],
    models: list[ModelEfficiency],
    outliers: list[CostOutlier],
) -> list[str]:
    """Generate terse human-readable recommendations from the analysis."""
    if not task_types:
        return ["No cost data available yet."]

    recommendations: list[str] = []

    most_expensive = max(task_types, key=lambda item: item["average_cost_usd"])
    recommendations.append(
        f"Highest average spend is {most_expensive['task_type']} "
        f"(${most_expensive['average_cost_usd']:.2f}/session across {most_expensive['sessions']} sessions)."
    )

    tracker_models = [item for item in models if item["cost_per_tracker_delta_usd"] is not None]
    if tracker_models:
        best_tracker = min(
            tracker_models,
            key=lambda item: (
                item["cost_per_tracker_delta_usd"] if item["cost_per_tracker_delta_usd"] is not None else 0.0
            ),
        )
        recommendations.append(
            f"Best tracker efficiency is {best_tracker['model']} at "
            f"${best_tracker['cost_per_tracker_delta_usd']:.2f} per tracker point."
        )

    test_models = [item for item in models if item["cost_per_test_added_usd"] is not None]
    if test_models:
        best_tests = min(
            test_models,
            key=lambda item: item["cost_per_test_added_usd"] if item["cost_per_test_added_usd"] is not None else 0.0,
        )
        recommendations.append(
            f"Best test-writing efficiency is {best_tests['model']} at "
            f"${best_tests['cost_per_test_added_usd']:.2f} per added test."
        )

    if outliers:
        worst = outliers[0]
        recommendations.append(
            f"Review outlier session {worst['session_id']} ({worst['task_type']}) at "
            f"{worst['ratio_to_peer_average']:.2f}x peer average spend."
        )

    return recommendations[:4]
