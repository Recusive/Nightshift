"""Shift state: read, write, mutate counters, JSON I/O."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nightshift.core.constants import DATA_VERSION, VALID_CATEGORIES
from nightshift.core.errors import NightshiftError
from nightshift.core.types import (
    Baseline,
    Counters,
    CycleResult,
    CycleVerification,
    FeatureState,
    ShiftState,
)

# Re-export for use within this module. VALID_CATEGORIES is defined once in
# constants.py; this avoids a duplicated frozenset(CATEGORY_ORDER) here.
_VALID_CATEGORIES = VALID_CATEGORIES


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise NightshiftError(f"{path} must contain a JSON object, got {type(data).__name__}")
    return data


def write_json(path: Path, payload: dict[str, Any] | ShiftState | FeatureState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


_REQUIRED_STATE_KEYS = {"version", "date", "branch", "agent", "baseline", "counters", "cycles"}


def _safe_int(value: object, default: int = 0) -> int:
    """Convert numeric values to int and fall back for corrupt data."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return default


def _build_state(raw: dict[str, Any], state_path: Path) -> ShiftState:
    """Construct a ShiftState from a validated raw dict, field by field."""
    baseline_raw = raw.get("baseline", {})
    if not isinstance(baseline_raw, dict):
        raise NightshiftError(f"Corrupt state file {state_path}: 'baseline' must be an object")
    counters_raw = raw.get("counters", {})
    if not isinstance(counters_raw, dict):
        raise NightshiftError(f"Corrupt state file {state_path}: 'counters' must be an object")

    baseline = Baseline(
        status=str(baseline_raw.get("status", "pending")),
        command=baseline_raw.get("command"),
        message=str(baseline_raw.get("message", "")),
    )
    counters = Counters(
        fixes=_safe_int(counters_raw.get("fixes", 0)),
        issues_logged=_safe_int(counters_raw.get("issues_logged", 0)),
        files_touched=_safe_int(counters_raw.get("files_touched", 0)),
        low_impact_fixes=_safe_int(counters_raw.get("low_impact_fixes", 0)),
        failed_verifications=_safe_int(counters_raw.get("failed_verifications", 0)),
        empty_cycles=_safe_int(counters_raw.get("empty_cycles", 0)),
        agent_failures=_safe_int(counters_raw.get("agent_failures", 0)),
        tests_written=_safe_int(counters_raw.get("tests_written", 0)),
    )
    cycles_raw = raw.get("cycles", [])
    if not isinstance(cycles_raw, list):
        cycles_raw = []

    raw_category_counts = raw.get("category_counts", {})
    if not isinstance(raw_category_counts, dict):
        raw_category_counts = {}
    category_counts: dict[str, int] = {
        k: int(v)
        for k, v in raw_category_counts.items()
        if isinstance(k, str) and k in _VALID_CATEGORIES and isinstance(v, (int, float))
    }

    return ShiftState(
        version=int(raw["version"]),
        date=str(raw["date"]),
        branch=str(raw["branch"]),
        agent=str(raw["agent"]),
        verify_command=raw.get("verify_command"),
        baseline=baseline,
        counters=counters,
        category_counts=category_counts,
        recent_cycle_paths=raw.get("recent_cycle_paths", []),
        cycles=cycles_raw,
        halt_reason=raw.get("halt_reason"),
        log_only_mode=bool(raw.get("log_only_mode", False)),
    )


def read_state(
    state_path: Path,
    *,
    today: str,
    branch: str,
    agent: str,
    verify_command: str | None,
) -> ShiftState:
    if state_path.exists():
        payload = load_json(state_path)
        if payload.get("version") != DATA_VERSION:
            raise NightshiftError(f"Unsupported state version in {state_path}")
        missing = _REQUIRED_STATE_KEYS - payload.keys()
        if missing:
            raise NightshiftError(f"Corrupt state file {state_path}: missing keys {missing}")
        return _build_state(payload, state_path)
    return ShiftState(
        version=DATA_VERSION,
        date=today,
        branch=branch,
        agent=agent,
        verify_command=verify_command,
        baseline=Baseline(status="pending", command=verify_command, message=""),
        counters=Counters(
            fixes=0,
            issues_logged=0,
            files_touched=0,
            low_impact_fixes=0,
            failed_verifications=0,
            empty_cycles=0,
            agent_failures=0,
            tests_written=0,
        ),
        category_counts={},
        recent_cycle_paths=[],
        cycles=[],
        halt_reason=None,
        log_only_mode=False,
    )


def top_path(files: list[str]) -> str:
    top_level: dict[str, int] = {}
    for entry in files:
        if not entry:
            continue
        part = entry.split("/", 1)[0]
        top_level[part] = top_level.get(part, 0) + 1
    if not top_level:
        return "(none)"
    return sorted(top_level.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _is_test_file(name: str) -> bool:
    """Return True if a filename looks like a test file."""
    basename = name.rsplit("/", 1)[-1].lower()
    if basename.startswith("test_") or basename.endswith("_test.py"):
        return True
    for suffix in (".test.ts", ".test.js", ".test.tsx", ".test.jsx", ".spec.ts", ".spec.js"):
        if basename.endswith(suffix):
            return True
    return False


def append_cycle_state(
    *,
    state: ShiftState,
    cycle_number: int,
    cycle_result: CycleResult | None,
    verification: CycleVerification,
) -> None:
    fixes = cycle_result.get("fixes", []) if cycle_result else []
    logged_issues = cycle_result.get("logged_issues", []) if cycle_result else []
    low_impact = sum(1 for fix in fixes if fix.get("impact") == "low")
    inferred_fix_count = len(fixes)
    if not fixes:
        count_only = cycle_result.get("fixes_count_only", 0) if cycle_result is not None else 0
        if count_only:
            # Agent used count-only payload (fixes_committed/fixes_applied): honour it directly.
            inferred_fix_count = count_only
        elif not logged_issues and verification["commits"] and not state["log_only_mode"]:
            # No structured or count-only data: fall back to commit count as a last resort.
            inferred_fix_count = len(verification["commits"])

    for fix in fixes:
        category = fix.get("category")
        if category is not None and category in _VALID_CATEGORIES:
            state["category_counts"][category] = state["category_counts"].get(category, 0) + 1

    # When the agent used count-only payload (no structured fix objects), extract
    # categories from the agent's "categories" list field so category_counts is
    # populated even when fixes[] is empty.
    if not fixes and cycle_result is not None:
        count_only = cycle_result.get("fixes_count_only", 0)
        if count_only:
            agent_categories = cycle_result.get("categories") or []
            if isinstance(agent_categories, list):
                for cat in agent_categories:
                    if isinstance(cat, str) and cat in _VALID_CATEGORIES:
                        state["category_counts"][cat] = state["category_counts"].get(cat, 0) + 1

    test_files_count = sum(1 for f in verification["files_touched"] if _is_test_file(f))
    state["counters"]["tests_written"] += test_files_count

    state["counters"]["fixes"] += inferred_fix_count
    state["counters"]["issues_logged"] += len(logged_issues)
    state["counters"]["files_touched"] += len(verification["files_touched"])
    state["counters"]["low_impact_fixes"] += low_impact

    if not fixes and not logged_issues and not verification["commits"]:
        state["counters"]["empty_cycles"] += 1
    else:
        state["counters"]["empty_cycles"] = 0

    state["recent_cycle_paths"].append(verification["dominant_path"])
    state["recent_cycle_paths"] = state["recent_cycle_paths"][-4:]

    # Determine cycle status: prefer the agent's reported status; fall back to
    # inferred status when the agent returned a count-only payload (no "status"
    # field or "unknown").  A cycle with committed fixes is "completed".
    reported_status = cycle_result.get("status", "unknown") if cycle_result else "unknown"
    if reported_status == "unknown" and cycle_result is not None:
        count_only = cycle_result.get("fixes_count_only", 0)
        if count_only and verification["commits"]:
            reported_status = "completed"
        elif logged_issues and not verification["commits"]:
            reported_status = "log_only"

    state["cycles"].append(
        {
            "cycle": cycle_number,
            "status": reported_status,
            "fixes": fixes,
            "logged_issues": logged_issues,
            "verification": verification,
        }
    )
