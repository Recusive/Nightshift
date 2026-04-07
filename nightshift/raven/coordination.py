"""Sub-agent coordination for Loop 2 -- detects file overlaps and generates hints."""

from __future__ import annotations

from nightshift.core.constants import (
    COORDINATION_HINT_TEMPLATE,
    FILE_REFERENCE_PATTERN,
    print_status,
)
from nightshift.core.types import (
    ConflictReport,
    FileConflict,
    FileOverlap,
    WaveResult,
    WorkOrder,
)


def extract_file_references(text: str) -> list[str]:
    """Extract file-path-like references from natural language text.

    Returns deduplicated matches preserving first-occurrence order.
    Matches strings with at least one ``/`` separator and an optional
    file extension, such as ``src/api/auth.py`` or ``tests/unit/``.
    """
    matches = FILE_REFERENCE_PATTERN.findall(text)
    seen: set[str] = set()
    result: list[str] = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            result.append(match)
    return result


def detect_overlaps(wave: list[WorkOrder]) -> list[FileOverlap]:
    """Find file references that appear in 2+ work orders within a wave.

    Scans each work order's prompt and acceptance criteria for path-like
    strings and reports any that are shared across tasks.
    """
    if len(wave) < 2:
        return []

    task_refs: dict[int, set[str]] = {}
    for order in wave:
        refs: set[str] = set(extract_file_references(order["prompt"]))
        for criterion in order["acceptance_criteria"]:
            refs.update(extract_file_references(criterion))
        task_refs[order["task_id"]] = refs

    all_refs: dict[str, list[int]] = {}
    for task_id, refs in task_refs.items():
        for ref in refs:
            all_refs.setdefault(ref, []).append(task_id)

    return [
        FileOverlap(file_pattern=ref, task_ids=sorted(task_ids))
        for ref, task_ids in sorted(all_refs.items())
        if len(task_ids) > 1
    ]


def generate_coordination_hints(
    overlaps: list[FileOverlap],
) -> dict[int, list[str]]:
    """Generate per-task coordination hints based on detected overlaps.

    Returns a mapping of task_id to a list of human-readable hint strings.
    Tasks without overlaps are omitted from the result.
    """
    if not overlaps:
        return {}

    hints: dict[int, list[str]] = {}
    for overlap in overlaps:
        for task_id in overlap["task_ids"]:
            other_ids = [tid for tid in overlap["task_ids"] if tid != task_id]
            if other_ids:
                others_str = ", ".join(f"Task {tid}" for tid in other_ids)
                hint = f"- `{overlap['file_pattern']}` is also being modified by {others_str}"
                hints.setdefault(task_id, []).append(hint)
    return hints


def inject_hints(
    wave: list[WorkOrder],
    hints: dict[int, list[str]],
) -> list[WorkOrder]:
    """Return new work orders with coordination hints appended to prompts.

    Work orders for tasks without hints are returned unchanged.
    """
    if not hints:
        return list(wave)

    result: list[WorkOrder] = []
    for order in wave:
        task_hints = hints.get(order["task_id"])
        if task_hints:
            hint_block = COORDINATION_HINT_TEMPLATE.format(hints="\n".join(task_hints))
            result.append(
                WorkOrder(
                    task_id=order["task_id"],
                    wave=order["wave"],
                    title=order["title"],
                    prompt=order["prompt"] + hint_block,
                    acceptance_criteria=list(order["acceptance_criteria"]),
                    estimated_files=order["estimated_files"],
                    depends_on=list(order["depends_on"]),
                    schema_path=order["schema_path"],
                )
            )
        else:
            result.append(order)
    return result


def detect_file_conflicts(wave_result: WaveResult) -> ConflictReport:
    """Check completed tasks for files created or modified by 2+ tasks.

    This runs after a wave completes but before integration, giving the
    orchestrator visibility into potential merge problems.
    """
    file_to_tasks: dict[str, list[int]] = {}
    for tc in wave_result["completed"]:
        for f in tc["files_created"]:
            file_to_tasks.setdefault(f, []).append(tc["task_id"])
        for f in tc["files_modified"]:
            file_to_tasks.setdefault(f, []).append(tc["task_id"])

    conflicts = [
        FileConflict(file_path=path, task_ids=sorted(task_ids))
        for path, task_ids in sorted(file_to_tasks.items())
        if len(task_ids) > 1
    ]

    return ConflictReport(
        conflicts=conflicts,
        has_conflicts=len(conflicts) > 0,
    )


def format_conflict_report(report: ConflictReport) -> str:
    """Render a conflict report as human-readable text."""
    if not report["has_conflicts"]:
        return "No file conflicts detected."

    lines: list[str] = []
    lines.append(f"WARNING: {len(report['conflicts'])} file conflict(s) detected:")
    lines.append("")
    for conflict in report["conflicts"]:
        task_str = ", ".join(f"Task {tid}" for tid in conflict["task_ids"])
        lines.append(f"  - {conflict['file_path']} (touched by {task_str})")
    return "\n".join(lines)


def coordinate_wave(
    wave: list[WorkOrder],
) -> list[WorkOrder]:
    """Run pre-spawn coordination: detect overlaps, inject hints, return updated orders.

    This is the main entry point for pre-wave coordination. It combines
    overlap detection, hint generation, and prompt injection in one call.
    """
    overlaps = detect_overlaps(wave)
    if not overlaps:
        return list(wave)

    hints = generate_coordination_hints(overlaps)
    coordinated = inject_hints(wave, hints)

    overlap_count = len(overlaps)
    task_count = len(hints)
    print_status(
        f"[coordination] Detected {overlap_count} file overlap(s) across {task_count} task(s) -- hints injected"
    )

    return coordinated


def log_conflicts(wave_result: WaveResult) -> ConflictReport:
    """Run post-wave conflict detection and log results.

    Returns the conflict report for the caller to inspect.
    """
    report = detect_file_conflicts(wave_result)
    if report["has_conflicts"]:
        print_status(f"[coordination] {format_conflict_report(report)}")
    else:
        print_status("[coordination] No file conflicts detected in wave results")
    return report
