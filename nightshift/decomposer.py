"""Task decomposer for Loop 2 -- converts FeaturePlans into sub-agent work orders."""

from __future__ import annotations

from nightshift.constants import (
    TASK_SCHEMA_PATH,
    WORK_ORDER_PROMPT_TEMPLATE,
)
from nightshift.planner import execution_order
from nightshift.types import (
    DecomposerResult,
    FeaturePlan,
    PlanTask,
    RepoProfile,
    WorkOrder,
)


def _format_frameworks(profile: RepoProfile) -> str:
    """Format framework list for the work order prompt."""
    if not profile["frameworks"]:
        return "none detected"
    parts: list[str] = []
    for fw in profile["frameworks"]:
        if fw["version"]:
            parts.append(f"{fw['name']} ({fw['version']})")
        else:
            parts.append(fw["name"])
    return ", ".join(parts)


def _format_list(items: list[str]) -> str:
    """Format a profile list for prompt output."""
    return ", ".join(items) if items else "none detected"


def _format_acceptance_criteria(criteria: list[str]) -> str:
    """Format acceptance criteria as a numbered list."""
    return "\n".join(f"{i}. {c}" for i, c in enumerate(criteria, 1))


def _format_dependency_context(
    task: PlanTask,
    task_map: dict[int, PlanTask],
) -> str:
    """Describe what predecessor tasks produce so the agent has context."""
    if not task["depends_on"]:
        return "This task has no dependencies. It can start immediately."

    lines: list[str] = []
    lines.append("This task depends on the following completed tasks:")
    for dep_id in sorted(task["depends_on"]):
        dep = task_map.get(dep_id)
        if dep is not None:
            lines.append(f"- Task {dep_id}: {dep['title']} -- {dep['description']}")
    lines.append("")
    lines.append("Assume their work is already merged into the codebase.")
    return "\n".join(lines)


def build_work_order_prompt(
    task: PlanTask,
    plan: FeaturePlan,
    profile: RepoProfile,
) -> str:
    """Build a complete sub-agent prompt for a single task.

    The prompt includes repo context, feature context, the specific task
    details, acceptance criteria, and the expected JSON output schema.
    """
    task_map: dict[int, PlanTask] = {t["id"]: t for t in plan["tasks"]}

    return WORK_ORDER_PROMPT_TEMPLATE.format(
        primary_language=profile["primary_language"],
        frameworks=_format_frameworks(profile),
        dependencies=_format_list(profile["dependencies"]),
        conventions=_format_list(profile["conventions"]),
        package_manager=profile["package_manager"] or "none detected",
        test_runner=profile["test_runner"] or "none detected",
        instruction_files=", ".join(profile["instruction_files"]) or "none",
        feature_name=plan["feature"],
        architecture_overview=plan["architecture"]["overview"],
        task_id=task["id"],
        task_title=task["title"],
        task_description=task["description"],
        acceptance_criteria=_format_acceptance_criteria(task["acceptance_criteria"]),
        dependency_context=_format_dependency_context(task, task_map),
        estimated_files=task["estimated_files"],
    )


def _build_work_order(
    task: PlanTask,
    wave_number: int,
    plan: FeaturePlan,
    profile: RepoProfile,
) -> WorkOrder:
    """Build a single WorkOrder for a task."""
    return WorkOrder(
        task_id=task["id"],
        wave=wave_number,
        title=task["title"],
        prompt=build_work_order_prompt(task, plan, profile),
        acceptance_criteria=list(task["acceptance_criteria"]),
        estimated_files=task["estimated_files"],
        depends_on=list(task["depends_on"]),
        schema_path=TASK_SCHEMA_PATH,
    )


def decompose_plan(
    plan: FeaturePlan,
    profile: RepoProfile,
) -> DecomposerResult:
    """Convert a FeaturePlan into sub-agent work orders grouped by execution wave.

    Each wave contains work orders that can execute in parallel. Waves
    execute sequentially: wave N completes before wave N+1 starts.

    Raises ValueError if the plan has circular dependencies (delegated
    to execution_order()).
    """
    waves = execution_order(plan["tasks"])
    task_map: dict[int, PlanTask] = {t["id"]: t for t in plan["tasks"]}

    result_waves: list[list[WorkOrder]] = []
    for wave_idx, wave_task_ids in enumerate(waves, 1):
        wave_orders: list[WorkOrder] = []
        for tid in wave_task_ids:
            task = task_map[tid]
            order = _build_work_order(task, wave_idx, plan, profile)
            wave_orders.append(order)
        result_waves.append(wave_orders)

    return DecomposerResult(
        feature=plan["feature"],
        total_waves=len(result_waves),
        total_tasks=len(plan["tasks"]),
        waves=result_waves,
    )


def format_work_orders(result: DecomposerResult) -> str:
    """Render a DecomposerResult as human-readable markdown."""
    lines: list[str] = []

    lines.append(f"# Work Orders: {result['feature']}")
    lines.append("")
    lines.append(f"Total waves: {result['total_waves']}")
    lines.append(f"Total tasks: {result['total_tasks']}")
    lines.append("")

    for wave in result["waves"]:
        if not wave:
            continue
        wave_num = wave[0]["wave"]
        lines.append(f"## Wave {wave_num}")
        lines.append("")
        lines.append(f"{len(wave)} task(s) -- can execute in parallel")
        lines.append("")

        for order in wave:
            deps_str = ""
            if order["depends_on"]:
                deps_str = f" (after: {', '.join(str(d) for d in order['depends_on'])})"
            lines.append(f"### Task {order['task_id']}: {order['title']}{deps_str}")
            lines.append("")
            lines.append(f"- Estimated files: {order['estimated_files']}")
            lines.append(f"- Schema: `{order['schema_path']}`")
            lines.append("- Acceptance criteria:")
            for criterion in order["acceptance_criteria"]:
                lines.append(f"  - {criterion}")
            lines.append("")

    return "\n".join(lines)
