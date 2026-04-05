"""Feature planner for Loop 2 -- builds structured plans from repo profiles."""

from __future__ import annotations

from pathlib import Path

from nightshift.constants import (
    PLAN_AGENT_MAX_TURNS,
    PLAN_AGENT_TIMEOUT,
    PLAN_MAX_FILES_PER_TASK,
    PLAN_MAX_TASKS,
    PLAN_MAX_TOTAL_FILES,
    PLAN_PROMPT_TEMPLATE,
    print_status,
)
from nightshift.cycle import extract_json
from nightshift.errors import NightshiftError
from nightshift.shell import command_exists, run_command
from nightshift.types import (
    ArchitectureDoc,
    FeaturePlan,
    PlanTask,
    RepoProfile,
    TestPlan,
)


def _format_frameworks(profile: RepoProfile) -> str:
    """Format framework list for the prompt."""
    if not profile["frameworks"]:
        return "none detected"
    parts: list[str] = []
    for fw in profile["frameworks"]:
        if fw["version"]:
            parts.append(f"{fw['name']} ({fw['version']})")
        else:
            parts.append(fw["name"])
    return ", ".join(parts)


def build_plan_prompt(profile: RepoProfile, feature_description: str) -> str:
    """Build a planning prompt from a repo profile and feature description.

    The prompt instructs an LLM agent to produce a FeaturePlan as JSON.
    """
    return PLAN_PROMPT_TEMPLATE.format(
        primary_language=profile["primary_language"],
        frameworks=_format_frameworks(profile),
        package_manager=profile["package_manager"] or "none detected",
        test_runner=profile["test_runner"] or "none detected",
        instruction_files=", ".join(profile["instruction_files"]) or "none",
        top_level_dirs=", ".join(profile["top_level_dirs"]) or "(empty)",
        is_monorepo="yes" if profile["has_monorepo_markers"] else "no",
        total_files=profile["total_files"],
        feature_description=feature_description,
        max_files_hint=PLAN_MAX_FILES_PER_TASK,
        max_tasks=PLAN_MAX_TASKS,
    )


def _validate_task(task: dict[str, object], all_ids: set[int]) -> list[str]:
    """Validate a single task dict and return a list of errors."""
    errors: list[str] = []
    required_str = ["title", "description"]
    required_list = ["depends_on", "acceptance_criteria"]

    for field in required_str:
        val = task.get(field)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"task {task.get('id', '?')}: missing or empty '{field}'")

    for field in required_list:
        val = task.get(field)
        if not isinstance(val, list):
            errors.append(f"task {task.get('id', '?')}: '{field}' must be a list")

    task_id = task.get("id")
    if not isinstance(task_id, int) or task_id < 1:
        errors.append(f"task {task_id}: 'id' must be a positive integer")

    if "parallel" not in task or not isinstance(task.get("parallel"), bool):
        errors.append(f"task {task.get('id', '?')}: 'parallel' must be a boolean")

    estimated = task.get("estimated_files")
    if not isinstance(estimated, int) or estimated < 0:
        errors.append(f"task {task.get('id', '?')}: 'estimated_files' must be non-negative int")

    acceptance = task.get("acceptance_criteria")
    if isinstance(acceptance, list) and len(acceptance) == 0:
        errors.append(f"task {task.get('id', '?')}: needs at least one acceptance criterion")

    deps = task.get("depends_on")
    if isinstance(deps, list) and isinstance(task_id, int):
        for dep in deps:
            if not isinstance(dep, int):
                errors.append(f"task {task_id}: depends_on contains non-integer: {dep}")
            elif dep == task_id:
                errors.append(f"task {task_id}: depends on itself")
            elif dep not in all_ids:
                errors.append(f"task {task_id}: depends on unknown task {dep}")

    return errors


def _detect_circular_deps(tasks: list[dict[str, object]]) -> list[str]:
    """Detect circular dependencies using DFS cycle detection."""
    graph: dict[int, list[int]] = {}
    for task in tasks:
        task_id = task.get("id")
        deps = task.get("depends_on")
        if isinstance(task_id, int) and isinstance(deps, list):
            graph[task_id] = [d for d in deps if isinstance(d, int)]

    visited: set[int] = set()
    in_stack: set[int] = set()
    errors: list[str] = []

    def dfs(node: int) -> bool:
        visited.add(node)
        in_stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor in in_stack:
                errors.append(f"circular dependency: task {node} -> task {neighbor}")
                return True
            if neighbor not in visited and dfs(neighbor):
                return True
        in_stack.discard(node)
        return False

    for node in graph:
        if node not in visited:
            dfs(node)

    return errors


def validate_plan(raw: dict[str, object]) -> tuple[bool, list[str]]:
    """Validate a raw plan dictionary has all required fields and sane values.

    Returns (is_valid, list_of_errors).
    """
    errors: list[str] = []

    # Top-level feature name
    feature = raw.get("feature")
    if not isinstance(feature, str) or not feature.strip():
        errors.append("missing or empty 'feature' field")

    # Architecture
    arch = raw.get("architecture")
    if not isinstance(arch, dict):
        errors.append("missing 'architecture' object")
    else:
        if not isinstance(arch.get("overview"), str) or not arch["overview"].strip():
            errors.append("architecture: missing or empty 'overview'")
        for field in ["tech_choices", "data_model_changes", "api_changes", "frontend_changes", "integration_points"]:
            if not isinstance(arch.get(field), list):
                errors.append(f"architecture: '{field}' must be a list")

    # Tasks
    tasks = raw.get("tasks")
    if not isinstance(tasks, list) or len(tasks) == 0:
        errors.append("'tasks' must be a non-empty list")
    else:
        all_ids: set[int] = set()
        for task in tasks:
            if isinstance(task, dict):
                tid = task.get("id")
                if isinstance(tid, int):
                    if tid in all_ids:
                        errors.append(f"duplicate task id: {tid}")
                    all_ids.add(tid)

        for task in tasks:
            if isinstance(task, dict):
                errors.extend(_validate_task(task, all_ids))

        errors.extend(_detect_circular_deps(tasks))

    # Test plan
    test_plan = raw.get("test_plan")
    if not isinstance(test_plan, dict):
        errors.append("missing 'test_plan' object")
    else:
        for field in ["unit_tests", "integration_tests", "e2e_tests", "edge_cases"]:
            if not isinstance(test_plan.get(field), list):
                errors.append(f"test_plan: '{field}' must be a list")

    return (len(errors) == 0, errors)


def parse_plan(raw_output: str) -> FeaturePlan | None:
    """Extract a FeaturePlan from agent output (raw text or JSON).

    Returns None if the output cannot be parsed or fails validation.
    """
    extracted = extract_json(raw_output)
    if extracted is None:
        return None

    valid, _ = validate_plan(extracted)
    if not valid:
        return None

    # Build typed structures from validated dict
    arch_raw = extracted["architecture"]
    architecture = ArchitectureDoc(
        overview=str(arch_raw["overview"]),
        tech_choices=[str(c) for c in arch_raw["tech_choices"]],
        data_model_changes=[str(c) for c in arch_raw["data_model_changes"]],
        api_changes=[str(c) for c in arch_raw["api_changes"]],
        frontend_changes=[str(c) for c in arch_raw["frontend_changes"]],
        integration_points=[str(c) for c in arch_raw["integration_points"]],
    )

    tasks: list[PlanTask] = []
    for t in extracted["tasks"]:
        tasks.append(
            PlanTask(
                id=int(t["id"]),
                title=str(t["title"]),
                description=str(t["description"]),
                depends_on=[int(d) for d in t["depends_on"]],
                parallel=bool(t["parallel"]),
                acceptance_criteria=[str(c) for c in t["acceptance_criteria"]],
                estimated_files=int(t["estimated_files"]),
            )
        )

    tp_raw = extracted["test_plan"]
    test_plan = TestPlan(
        unit_tests=[str(t) for t in tp_raw["unit_tests"]],
        integration_tests=[str(t) for t in tp_raw["integration_tests"]],
        e2e_tests=[str(t) for t in tp_raw["e2e_tests"]],
        edge_cases=[str(t) for t in tp_raw["edge_cases"]],
    )

    return FeaturePlan(
        feature=str(extracted["feature"]),
        architecture=architecture,
        tasks=tasks,
        test_plan=test_plan,
    )


def execution_order(tasks: list[PlanTask]) -> list[list[int]]:
    """Compute execution waves from task dependencies (topological sort).

    Returns a list of waves. Each wave is a list of task IDs that can
    run in parallel. Waves execute sequentially: wave N completes before
    wave N+1 starts.

    Raises ValueError if tasks contain circular dependencies.
    """
    if not tasks:
        return []

    graph: dict[int, list[int]] = {}
    in_degree: dict[int, int] = {}
    for task in tasks:
        tid = task["id"]
        graph.setdefault(tid, [])
        in_degree.setdefault(tid, 0)
        for dep in task["depends_on"]:
            graph.setdefault(dep, [])
            graph[dep].append(tid)
            in_degree[tid] = in_degree.get(tid, 0) + 1

    waves: list[list[int]] = []
    remaining = dict(in_degree)

    while remaining:
        wave = sorted(tid for tid, deg in remaining.items() if deg == 0)
        if not wave:
            raise ValueError("circular dependency detected in task graph")
        waves.append(wave)
        for tid in wave:
            del remaining[tid]
            for neighbor in graph.get(tid, []):
                if neighbor in remaining:
                    remaining[neighbor] -= 1

    return waves


def format_plan(plan: FeaturePlan) -> str:
    """Render a FeaturePlan as human-readable markdown."""
    lines: list[str] = []

    lines.append(f"# Feature Plan: {plan['feature']}")
    lines.append("")

    # Architecture
    arch = plan["architecture"]
    lines.append("## Architecture")
    lines.append("")
    lines.append(arch["overview"])
    lines.append("")

    if arch["tech_choices"]:
        lines.append("### Technology Choices")
        for choice in arch["tech_choices"]:
            lines.append(f"- {choice}")
        lines.append("")

    if arch["data_model_changes"]:
        lines.append("### Data Model Changes")
        for change in arch["data_model_changes"]:
            lines.append(f"- {change}")
        lines.append("")

    if arch["api_changes"]:
        lines.append("### API Changes")
        for change in arch["api_changes"]:
            lines.append(f"- {change}")
        lines.append("")

    if arch["frontend_changes"]:
        lines.append("### Frontend Changes")
        for change in arch["frontend_changes"]:
            lines.append(f"- {change}")
        lines.append("")

    if arch["integration_points"]:
        lines.append("### Integration Points")
        for point in arch["integration_points"]:
            lines.append(f"- {point}")
        lines.append("")

    # Task breakdown
    lines.append("## Task Breakdown")
    lines.append("")

    waves = execution_order(plan["tasks"])
    task_map: dict[int, PlanTask] = {t["id"]: t for t in plan["tasks"]}

    for wave_idx, wave in enumerate(waves, 1):
        lines.append(f"### Wave {wave_idx}")
        lines.append("")
        for tid in wave:
            task = task_map[tid]
            mode = "parallel" if task["parallel"] else "sequential"
            deps_str = ""
            if task["depends_on"]:
                deps_str = f" (depends on: {', '.join(str(d) for d in task['depends_on'])})"
            lines.append(f"**Task {task['id']}** [{mode}]: {task['title']}{deps_str}")
            lines.append(f"  {task['description']}")
            lines.append(f"  Files: ~{task['estimated_files']}")
            lines.append("  Acceptance:")
            for criterion in task["acceptance_criteria"]:
                lines.append(f"    - {criterion}")
            lines.append("")

    # Test plan
    tp = plan["test_plan"]
    lines.append("## Test Plan")
    lines.append("")

    if tp["unit_tests"]:
        lines.append("### Unit Tests")
        for test in tp["unit_tests"]:
            lines.append(f"- {test}")
        lines.append("")

    if tp["integration_tests"]:
        lines.append("### Integration Tests")
        for test in tp["integration_tests"]:
            lines.append(f"- {test}")
        lines.append("")

    if tp["e2e_tests"]:
        lines.append("### E2E Tests")
        for test in tp["e2e_tests"]:
            lines.append(f"- {test}")
        lines.append("")

    if tp["edge_cases"]:
        lines.append("### Edge Cases")
        for case in tp["edge_cases"]:
            lines.append(f"- {case}")
        lines.append("")

    return "\n".join(lines)


def scope_check(plan: FeaturePlan) -> str | None:
    """Check if a plan exceeds recommended scope limits.

    Returns a warning message if the plan is too large, or None if within limits.
    """
    task_count = len(plan["tasks"])
    total_files = sum(t["estimated_files"] for t in plan["tasks"])

    if task_count > PLAN_MAX_TASKS:
        return f"Plan has {task_count} tasks (limit: {PLAN_MAX_TASKS}). Consider breaking this feature into phases."
    if total_files > PLAN_MAX_TOTAL_FILES:
        return (
            f"Plan touches ~{total_files} files (limit: {PLAN_MAX_TOTAL_FILES}). "
            "Consider breaking this feature into phases."
        )
    return None


def plan_command_for_agent(agent: str, prompt: str) -> list[str]:
    """Build the CLI command to invoke an agent for plan generation.

    Unlike the cycle command_for_agent, this does not require schema or
    message paths since the plan agent only produces text output.
    """
    if agent == "codex":
        return [
            "codex",
            "exec",
            "-c",
            'approval_policy="never"',
            prompt,
        ]
    if agent == "claude":
        return [
            "claude",
            "-p",
            prompt,
            "--max-turns",
            str(PLAN_AGENT_MAX_TURNS),
            "--verbose",
        ]
    raise NightshiftError(f"Unsupported agent: {agent}")


def run_plan_agent(
    repo_dir: Path,
    feature_description: str,
    agent: str,
    profile: RepoProfile,
) -> FeaturePlan:
    """Invoke an agent to generate a feature plan and return the parsed result.

    Profiles the repo, builds the planning prompt, runs the agent, and parses
    the output into a validated FeaturePlan.

    Raises NightshiftError if the agent is not installed, fails, or produces
    unparseable output.
    """
    if not command_exists(agent):
        raise NightshiftError(f"`{agent}` is not installed or not on PATH.")

    prompt = build_plan_prompt(profile, feature_description)
    cmd = plan_command_for_agent(agent, prompt)

    print_status(f"Running {agent} to generate feature plan...")
    exit_code, raw_output = run_command(
        cmd,
        cwd=repo_dir,
        timeout_seconds=PLAN_AGENT_TIMEOUT,
    )

    if exit_code != 0:
        raise NightshiftError(f"Agent `{agent}` exited with code {exit_code}. Check the output above for details.")

    plan = parse_plan(raw_output)
    if plan is None:
        raise NightshiftError(
            "Agent produced output but it could not be parsed into a valid feature plan. "
            "The output may not contain valid JSON or may be missing required fields."
        )

    return plan
