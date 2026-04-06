"""Self-evaluation loop: score nightshift runs against real repos."""

from __future__ import annotations

import contextlib
import datetime as dt
import glob
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from nightshift.constants import (
    EVALUATION_DEFAULT_CYCLE_MINUTES,
    EVALUATION_DEFAULT_CYCLES,
    EVALUATION_DIMENSIONS,
    EVALUATION_MAX_PER_DIMENSION,
    EVALUATION_SCORE_THRESHOLD,
    EVALUATION_SHIFT_TIMEOUT,
)
from nightshift.types import DimensionScore, EvaluationResult, ShiftArtifacts
from nightshift.worktree import resolve_runtime_dir

# ---------------------------------------------------------------------------
# Clone / run helpers
# ---------------------------------------------------------------------------


def clone_target_repo(url: str, dest: Path) -> Path:
    """Shallow-clone *url* into *dest*.  Returns the clone directory."""
    dest.mkdir(parents=True, exist_ok=True)
    repo_name = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    clone_dir = dest / repo_name
    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    subprocess.run(
        ["git", "clone", "--depth", "1", url, str(clone_dir)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return clone_dir


def run_test_shift(
    repo_dir: Path,
    nightshift_dir: Path,
    agent: str,
    cycles: int = EVALUATION_DEFAULT_CYCLES,
    cycle_minutes: int = EVALUATION_DEFAULT_CYCLE_MINUTES,
) -> int:
    """Run ``nightshift test`` against *repo_dir*.  Returns the exit code."""
    env = {**os.environ, "PYTHONPATH": str(nightshift_dir)}
    result = subprocess.run(
        [
            "python3",
            "-m",
            "nightshift",
            "test",
            "--agent",
            agent,
            "--cycles",
            str(cycles),
            "--cycle-minutes",
            str(cycle_minutes),
            "--repo-dir",
            str(repo_dir),
        ],
        capture_output=True,
        timeout=EVALUATION_SHIFT_TIMEOUT,
        env=env,
        cwd=str(repo_dir),
    )
    return result.returncode


# ---------------------------------------------------------------------------
# Artifact parsing
# ---------------------------------------------------------------------------


def parse_shift_artifacts(repo_dir: Path) -> ShiftArtifacts:
    """Read state file and shift log from a completed test shift."""
    runtime_dirs = _runtime_artifact_dirs(repo_dir)

    # State file
    state_files = _glob_runtime_candidates(runtime_dirs, "*.state.json")
    state: dict[str, object] | None = None
    state_valid = False
    if state_files:
        try:
            raw = Path(state_files[-1]).read_text(encoding="utf-8")
            state = json.loads(raw)
            state_valid = isinstance(state, dict)
        except (json.JSONDecodeError, OSError):
            pass

    # Shift log
    shift_log = ""
    shift_log_exists = False
    log_candidates = _shift_log_candidates(runtime_dirs)
    if log_candidates:
        try:
            shift_log = Path(log_candidates[-1]).read_text(encoding="utf-8")
            shift_log_exists = True
        except OSError:
            pass

    return ShiftArtifacts(
        state=state,
        shift_log=shift_log,
        runner_exit_code=-1,
        state_file_valid=state_valid,
        shift_log_exists=shift_log_exists,
    )


_DATED_SHIFT_LOG_GLOB = "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md"


def _runtime_artifact_dirs(repo_dir: Path) -> list[Path]:
    runtime_dirs: list[Path] = []
    for test_mode in (False, True):
        candidate = resolve_runtime_dir(repo_dir, test_mode=test_mode)
        if candidate not in runtime_dirs:
            runtime_dirs.append(candidate)
    return runtime_dirs


def _glob_runtime_candidates(runtime_dirs: list[Path], pattern: str) -> list[str]:
    matches: list[str] = []
    for runtime_dir in runtime_dirs:
        matches.extend(glob.glob(str(runtime_dir / pattern)))
    return sorted(set(matches))


def _shift_log_candidates(runtime_dirs: list[Path]) -> list[str]:
    patterns = [
        "SHIFT-LOG*.md",
        _DATED_SHIFT_LOG_GLOB,
        "worktree-*/*/Nightshift/SHIFT-LOG*.md",
        f"worktree-*/*/Nightshift/{_DATED_SHIFT_LOG_GLOB}",
    ]
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(_glob_runtime_candidates(runtime_dirs, pattern))
    return sorted(set(matches))


# ---------------------------------------------------------------------------
# Dimension scorers -- pure functions
# ---------------------------------------------------------------------------


def _get_state_dict(artifacts: ShiftArtifacts) -> dict[str, object]:
    """Return the state dict, or empty dict if None."""
    return artifacts["state"] if artifacts["state"] is not None else {}


def _get_cycles(state: dict[str, object]) -> list[object]:
    """Extract cycles list from state, defaulting to empty."""
    cycles = state.get("cycles")
    return list(cycles) if isinstance(cycles, list) else []


def _get_counters(state: dict[str, object]) -> dict[str, object]:
    """Extract counters dict from state, defaulting to empty."""
    counters = state.get("counters")
    return dict(counters) if isinstance(counters, dict) else {}


def score_startup(artifacts: ShiftArtifacts) -> DimensionScore:
    """Score: did the runner start correctly?"""
    score = 0
    notes_parts: list[str] = []

    if artifacts["state_file_valid"]:
        score += 3
    else:
        notes_parts.append("state file missing or invalid")

    state = _get_state_dict(artifacts)
    baseline = state.get("baseline")
    if isinstance(baseline, dict) and baseline.get("status") != "pending":
        score += 3
    else:
        notes_parts.append("baseline not run")

    cycles = _get_cycles(state)
    if len(cycles) >= 1:
        score += 2
    else:
        notes_parts.append("no cycles recorded")

    if artifacts["runner_exit_code"] == 0:
        score += 2
    else:
        notes_parts.append(f"exit code {artifacts['runner_exit_code']}")

    return DimensionScore(
        name="Startup",
        score=min(score, EVALUATION_MAX_PER_DIMENSION),
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes="; ".join(notes_parts) if notes_parts else "clean startup",
    )


def score_discovery(artifacts: ShiftArtifacts) -> DimensionScore:
    """Score: did the agent find real issues?"""
    score = 0
    notes_parts: list[str] = []

    state = _get_state_dict(artifacts)
    counters = _get_counters(state)

    fixes = counters.get("fixes", 0)
    fixes_count = int(fixes) if isinstance(fixes, (int, float)) else 0
    issues = counters.get("issues_logged", 0)
    issues_count = int(issues) if isinstance(issues, (int, float)) else 0

    if fixes_count >= 1:
        score += 3
        notes_parts.append(f"{fixes_count} fix(es)")
    else:
        notes_parts.append("no fixes")

    if issues_count >= 1:
        score += 3
        notes_parts.append(f"{issues_count} issue(s) logged")
    else:
        notes_parts.append("no issues logged")

    # Check fix quality in cycle data
    cycles = _get_cycles(state)
    has_real_titles = False
    for cycle in cycles:
        if isinstance(cycle, dict):
            cycle_fixes = cycle.get("fixes")
            if isinstance(cycle_fixes, list):
                for fix in cycle_fixes:
                    if isinstance(fix, dict):
                        title = fix.get("title", "")
                        if isinstance(title, str) and len(title) > 5:
                            has_real_titles = True

    if has_real_titles:
        score += 4
    elif fixes_count > 0:
        score += 2
        notes_parts.append("fix titles may be template placeholders")

    return DimensionScore(
        name="Discovery",
        score=min(score, EVALUATION_MAX_PER_DIMENSION),
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes="; ".join(notes_parts) if notes_parts else "good discovery",
    )


def score_fix_quality(artifacts: ShiftArtifacts) -> DimensionScore:
    """Score: are the fixes well-formed and meaningful?"""
    score = 0
    notes_parts: list[str] = []

    state = _get_state_dict(artifacts)
    cycles = _get_cycles(state)

    all_fixes: list[dict[str, object]] = []
    for cycle in cycles:
        if isinstance(cycle, dict):
            cycle_fixes = cycle.get("fixes")
            if isinstance(cycle_fixes, list):
                for fix in cycle_fixes:
                    if isinstance(fix, dict):
                        all_fixes.append(fix)

    if not all_fixes:
        return DimensionScore(
            name="Fix quality",
            score=0,
            max_score=EVALUATION_MAX_PER_DIMENSION,
            notes="no fixes to evaluate",
        )

    # Has categories
    categorized = sum(1 for f in all_fixes if f.get("category"))
    if categorized == len(all_fixes):
        score += 3
    elif categorized > 0:
        score += 1
        notes_parts.append(f"{len(all_fixes) - categorized} fix(es) missing category")

    # Has files
    with_files = sum(1 for f in all_fixes if f.get("files"))
    if with_files == len(all_fixes):
        score += 3
    elif with_files > 0:
        score += 1
        notes_parts.append(f"{len(all_fixes) - with_files} fix(es) missing files")

    # Impact distribution
    impacts = [f.get("impact") for f in all_fixes if f.get("impact")]
    non_low = sum(1 for i in impacts if i != "low")
    if non_low > 0:
        score += 2
    else:
        notes_parts.append("all fixes low impact")

    # Reasonable file counts
    for fix in all_fixes:
        files = fix.get("files")
        if isinstance(files, list) and len(files) > 10:
            notes_parts.append("fix touches 10+ files")
            break
    else:
        score += 2

    return DimensionScore(
        name="Fix quality",
        score=min(score, EVALUATION_MAX_PER_DIMENSION),
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes="; ".join(notes_parts) if notes_parts else f"{len(all_fixes)} well-formed fix(es)",
    )


_TEMPLATE_MARKERS = [
    "will be rewritten as the overnight run accumulates",
    "Number sequentially",
    "Issues too large to fix autonomously",
]


def score_shift_log(artifacts: ShiftArtifacts) -> DimensionScore:
    """Score: is the shift log useful?"""
    score = 0
    notes_parts: list[str] = []

    if not artifacts["shift_log_exists"]:
        return DimensionScore(
            name="Shift log",
            score=0,
            max_score=EVALUATION_MAX_PER_DIMENSION,
            notes="shift log not found",
        )

    log = artifacts["shift_log"]

    if len(log.strip()) > 100:
        score += 2
    else:
        notes_parts.append("shift log very short")

    # Check template was replaced
    is_template = any(marker in log for marker in _TEMPLATE_MARKERS)
    if not is_template:
        score += 3
    else:
        notes_parts.append("shift log still has template content")

    # Has fix entries
    if re.search(r"##\s*Fix", log) and re.search(r"\d+\.\s+", log):
        score += 3
    elif re.search(r"##\s*Fix", log):
        score += 1
        notes_parts.append("Fixes section exists but may be empty")

    # Has stats section
    if re.search(r"Fixes committed:\s*\d+", log):
        score += 2
    else:
        notes_parts.append("no stats section")

    return DimensionScore(
        name="Shift log",
        score=min(score, EVALUATION_MAX_PER_DIMENSION),
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes="; ".join(notes_parts) if notes_parts else "well-formed shift log",
    )


def score_state_file(artifacts: ShiftArtifacts) -> DimensionScore:
    """Score: is the state file valid and complete?"""
    score = 0
    notes_parts: list[str] = []

    if not artifacts["state_file_valid"]:
        return DimensionScore(
            name="State file",
            score=0,
            max_score=EVALUATION_MAX_PER_DIMENSION,
            notes="state file missing or invalid JSON",
        )

    state = _get_state_dict(artifacts)

    # Exists and valid JSON
    score += 2

    # Has expected keys
    expected = {"version", "date", "cycles", "counters", "baseline"}
    present = expected & set(state.keys())
    if len(present) == len(expected):
        score += 3
    else:
        missing = expected - present
        notes_parts.append(f"missing keys: {', '.join(sorted(missing))}")
        score += max(0, len(present) - 1)

    # Counters have values
    counters = _get_counters(state)
    positive = sum(1 for v in counters.values() if isinstance(v, (int, float)) and v > 0)
    if positive >= 2:
        score += 3
    elif positive >= 1:
        score += 1
        notes_parts.append("few active counters")
    else:
        notes_parts.append("all counters zero")

    # Halt reason sensible
    halt = state.get("halt_reason")
    if halt is None or halt == "max_cycles":
        score += 2
    else:
        notes_parts.append(f"halt_reason: {halt}")
        score += 1

    return DimensionScore(
        name="State file",
        score=min(score, EVALUATION_MAX_PER_DIMENSION),
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes="; ".join(notes_parts) if notes_parts else "valid state file",
    )


def score_verification(artifacts: ShiftArtifacts) -> DimensionScore:
    """Score: did verification run?"""
    score = 0
    notes_parts: list[str] = []

    state = _get_state_dict(artifacts)
    baseline = state.get("baseline")
    if isinstance(baseline, dict) and baseline.get("status") not in (None, "pending"):
        score += 3
    else:
        notes_parts.append("baseline not run")

    cycles = _get_cycles(state)
    verified_count = 0
    failed_count = 0
    for cycle in cycles:
        if isinstance(cycle, dict):
            v = cycle.get("verification")
            if isinstance(v, dict):
                vs = v.get("verify_status")
                if vs is not None and vs != "skipped":
                    verified_count += 1
                if vs == "failed":
                    failed_count += 1

    if verified_count >= 1:
        score += 3
        notes_parts.append(f"{verified_count} cycle(s) verified")
    else:
        notes_parts.append("no cycles had verification")

    if verified_count > 0 and failed_count == 0:
        score += 4
    elif verified_count > 0:
        score += 2
        notes_parts.append(f"{failed_count} verification failure(s)")

    return DimensionScore(
        name="Verification",
        score=min(score, EVALUATION_MAX_PER_DIMENSION),
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes="; ".join(notes_parts) if notes_parts else "verification ran cleanly",
    )


def score_guard_rails(artifacts: ShiftArtifacts) -> DimensionScore:
    """Score: were limits respected?"""
    score = 0
    notes_parts: list[str] = []

    state = _get_state_dict(artifacts)
    counters = _get_counters(state)

    # Check files per cycle limit
    files_touched = counters.get("files_touched", 0)
    files_count = int(files_touched) if isinstance(files_touched, (int, float)) else 0
    if files_count <= 50:
        score += 3
    else:
        notes_parts.append(f"high file count: {files_count}")
        score += 1

    # Check low impact limit
    low_impact = counters.get("low_impact_fixes", 0)
    low_count = int(low_impact) if isinstance(low_impact, (int, float)) else 0
    if low_count <= 4:
        score += 3
    else:
        notes_parts.append(f"too many low-impact fixes: {low_count}")

    # Check agent failures
    agent_failures = counters.get("agent_failures", 0)
    failure_count = int(agent_failures) if isinstance(agent_failures, (int, float)) else 0
    if failure_count == 0:
        score += 2
    else:
        notes_parts.append(f"{failure_count} agent failure(s)")

    # Check failed verifications
    failed_verifs = counters.get("failed_verifications", 0)
    fv_count = int(failed_verifs) if isinstance(failed_verifs, (int, float)) else 0
    if fv_count <= 1:
        score += 2
    else:
        notes_parts.append(f"{fv_count} failed verifications")

    return DimensionScore(
        name="Guard rails",
        score=min(score, EVALUATION_MAX_PER_DIMENSION),
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes="; ".join(notes_parts) if notes_parts else "all limits respected",
    )


def score_clean_state(artifacts: ShiftArtifacts) -> DimensionScore:
    """Score: did the session end cleanly?"""
    score = 0
    notes_parts: list[str] = []

    if artifacts["runner_exit_code"] == 0:
        score += 5
    else:
        notes_parts.append(f"non-zero exit: {artifacts['runner_exit_code']}")
        if artifacts["runner_exit_code"] == -1:
            score += 2
            notes_parts[-1] = "exit code unknown"

    state = _get_state_dict(artifacts)
    halt = state.get("halt_reason")
    if halt is None or halt == "max_cycles":
        score += 5
    elif isinstance(halt, str) and "empty" in halt:
        score += 3
        notes_parts.append(f"halt: {halt}")
    else:
        notes_parts.append(f"halt: {halt}")
        score += 1

    return DimensionScore(
        name="Clean state",
        score=min(score, EVALUATION_MAX_PER_DIMENSION),
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes="; ".join(notes_parts) if notes_parts else "clean exit",
    )


def score_breadth(artifacts: ShiftArtifacts) -> DimensionScore:
    """Score: did the agent explore multiple areas?"""
    score = 0
    notes_parts: list[str] = []

    state = _get_state_dict(artifacts)

    # Check directory diversity from files touched across cycles
    all_dirs: set[str] = set()
    cycles = _get_cycles(state)
    for cycle in cycles:
        if isinstance(cycle, dict):
            files = cycle.get("files_touched") or cycle.get("verification", {})
            if isinstance(files, dict):
                files = files.get("files_touched", [])
            if isinstance(files, list):
                for f in files:
                    if isinstance(f, str) and "/" in f:
                        all_dirs.add(f.rsplit("/", 1)[0])

    if len(all_dirs) >= 3:
        score += 5
        notes_parts.append(f"{len(all_dirs)} directories touched")
    elif len(all_dirs) >= 2:
        score += 3
        notes_parts.append(f"only {len(all_dirs)} directories")
    elif len(all_dirs) == 1:
        score += 1
        notes_parts.append("single directory only")
    else:
        notes_parts.append("no directory info available")

    # Check category diversity
    cats = state.get("category_counts")
    if isinstance(cats, dict):
        active_cats = sum(1 for v in cats.values() if isinstance(v, (int, float)) and v > 0)
        if active_cats >= 3:
            score += 5
            notes_parts.append(f"{active_cats} categories")
        elif active_cats >= 2:
            score += 3
            notes_parts.append(f"only {active_cats} categories")
        elif active_cats == 1:
            score += 1
            notes_parts.append("single category")
        else:
            notes_parts.append("no categories recorded")
    else:
        notes_parts.append("no category data")

    return DimensionScore(
        name="Breadth",
        score=min(score, EVALUATION_MAX_PER_DIMENSION),
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes="; ".join(notes_parts) if notes_parts else "good breadth",
    )


def score_usefulness(artifacts: ShiftArtifacts) -> DimensionScore:
    """Score: overall utility of the session output."""
    score = 0
    notes_parts: list[str] = []

    state = _get_state_dict(artifacts)
    counters = _get_counters(state)

    # Produced actionable output
    raw_fixes = counters.get("fixes", 0)
    fixes = int(raw_fixes) if isinstance(raw_fixes, (int, float)) else 0
    raw_issues = counters.get("issues_logged", 0)
    issues = int(raw_issues) if isinstance(raw_issues, (int, float)) else 0
    if fixes + issues >= 3:
        score += 4
    elif fixes + issues >= 1:
        score += 2
        notes_parts.append("few actionable items")
    else:
        notes_parts.append("no actionable output")

    # Shift log has recommendations
    log = artifacts["shift_log"]
    if re.search(r"##\s*Recommend", log):
        score += 3
    elif artifacts["shift_log_exists"]:
        score += 1
        notes_parts.append("no recommendations section")

    # Tests written
    raw_tests = counters.get("tests_written", 0)
    tests = int(raw_tests) if isinstance(raw_tests, (int, float)) else 0
    if tests >= 1:
        score += 3
        notes_parts.append(f"{tests} test(s) written")
    else:
        notes_parts.append("no tests written")

    return DimensionScore(
        name="Usefulness",
        score=min(score, EVALUATION_MAX_PER_DIMENSION),
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes="; ".join(notes_parts) if notes_parts else "useful session",
    )


# ---------------------------------------------------------------------------
# Aggregate scorer
# ---------------------------------------------------------------------------

_SCORERS = [
    score_startup,
    score_discovery,
    score_fix_quality,
    score_shift_log,
    score_state_file,
    score_verification,
    score_guard_rails,
    score_clean_state,
    score_breadth,
    score_usefulness,
]


def score_all_dimensions(artifacts: ShiftArtifacts) -> list[DimensionScore]:
    """Run all 10 dimension scorers and return the list of scores."""
    return [scorer(artifacts) for scorer in _SCORERS]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def next_evaluation_id(eval_dir: Path) -> int:
    """Return the next sequential evaluation number."""
    existing = sorted(eval_dir.glob("[0-9][0-9][0-9][0-9].md"))
    if not existing:
        return 1
    last = existing[-1].stem
    return int(last) + 1


def format_evaluation_report(result: EvaluationResult) -> str:
    """Format an evaluation result as markdown."""
    lines = [
        f"# Evaluation #{result['evaluation_id']:04d}",
        f"**Date**: {result['date']}",
        f"**Target**: {result['target_repo']}",
        f"**Agent**: {result['agent']}",
        f"**Cycles**: {result['cycles']}",
        f"**After task**: {result['after_task']}",
        "",
        "## Scores",
        "",
        "| Dimension | Score | Notes |",
        "|-----------|-------|-------|",
    ]

    for dim in result["dimensions"]:
        lines.append(f"| {dim['name']} | {dim['score']}/{dim['max_score']} | {dim['notes']} |")

    lines.extend(
        [
            f"| **Total** | **{result['total_score']}/{result['max_total']}** | |",
            "",
        ]
    )

    if result["tasks_created"]:
        lines.append("## Tasks Created")
        for task_ref in result["tasks_created"]:
            lines.append(f"- {task_ref}")
        lines.append("")

    return "\n".join(lines) + "\n"


def write_evaluation_report(eval_dir: Path, result: EvaluationResult) -> Path:
    """Write evaluation report to docs/evaluations/NNNN.md."""
    eval_dir.mkdir(parents=True, exist_ok=True)
    report_path = eval_dir / f"{result['evaluation_id']:04d}.md"
    report_path.write_text(format_evaluation_report(result), encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# Follow-up task creation
# ---------------------------------------------------------------------------


def create_followup_tasks(
    task_dir: Path,
    result: EvaluationResult,
    threshold: int = EVALUATION_SCORE_THRESHOLD,
) -> list[str]:
    """Create task files for dimensions scoring below *threshold*.

    Returns a list of ``"#NNNN: title"`` strings for the tasks created.
    """
    low_dims = [d for d in result["dimensions"] if d["score"] < threshold]
    if not low_dims:
        return []

    next_id_file = task_dir / ".next-id"
    try:
        next_id = int(next_id_file.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        next_id = 1

    today = dt.date.today().isoformat()
    created: list[str] = []

    for dim in low_dims:
        task_num = f"{next_id:04d}"
        task_path = task_dir / f"{task_num}.md"

        title = f"Evaluation #{result['evaluation_id']:04d}: improve {dim['name']} ({dim['score']}/{dim['max_score']})"
        body = (
            f"---\n"
            f"status: pending\n"
            f"priority: normal\n"
            f"target:\n"
            f"vision_section: loop1\n"
            f"created: {today}\n"
            f"source: evaluation-{result['evaluation_id']:04d}\n"
            f"completed:\n"
            f"---\n"
            f"\n"
            f"# {title}\n"
            f"\n"
            f"Evaluation #{result['evaluation_id']:04d} scored **{dim['name']}** "
            f"at {dim['score']}/{dim['max_score']} (below threshold {threshold}).\n"
            f"\n"
            f"**Notes**: {dim['notes']}\n"
            f"**Target repo**: {result['target_repo']}\n"
            f"**Agent**: {result['agent']}\n"
            f"\n"
            f"## Acceptance Criteria\n"
            f"\n"
            f"- [ ] Re-run evaluation against same target; {dim['name']} scores >= {threshold}\n"
        )

        task_path.write_text(body, encoding="utf-8")
        created.append(f"#{task_num}: {title}")
        next_id += 1

    next_id_file.write_text(f"{next_id}\n", encoding="utf-8")
    return created


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def evaluate(
    target_repo: str,
    agent: str,
    nightshift_dir: Path,
    eval_dir: Path,
    task_dir: Path,
    after_task: str = "",
    cycles: int = EVALUATION_DEFAULT_CYCLES,
    cycle_minutes: int = EVALUATION_DEFAULT_CYCLE_MINUTES,
) -> EvaluationResult:
    """Run a full evaluation cycle: clone, run, score, report, create tasks.

    This is the daemon's main evaluation entry point.  It is designed to
    never raise -- errors are captured as low scores.
    """
    today = dt.date.today().isoformat()
    eval_id = next_evaluation_id(eval_dir)

    # Clone
    clone_dir: Path | None = None
    clone_dest = Path("/tmp/nightshift-eval")
    try:
        clone_dir = clone_target_repo(target_repo, clone_dest)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        # Cannot clone -- score everything at 0
        empty_dims = [
            DimensionScore(name=name, score=0, max_score=EVALUATION_MAX_PER_DIMENSION, notes="clone failed")
            for name in EVALUATION_DIMENSIONS
        ]
        return EvaluationResult(
            evaluation_id=eval_id,
            date=today,
            target_repo=target_repo,
            agent=agent,
            cycles=cycles,
            after_task=after_task,
            dimensions=empty_dims,
            total_score=0,
            max_total=EVALUATION_MAX_PER_DIMENSION * len(EVALUATION_DIMENSIONS),
            tasks_created=[],
        )

    # Run test shift
    exit_code = -1
    with contextlib.suppress(subprocess.TimeoutExpired, OSError):
        exit_code = run_test_shift(clone_dir, nightshift_dir, agent, cycles, cycle_minutes)

    # Parse artifacts
    artifacts = parse_shift_artifacts(clone_dir)
    artifacts["runner_exit_code"] = exit_code

    # Score
    dimensions = score_all_dimensions(artifacts)
    total = sum(d["score"] for d in dimensions)
    max_total = EVALUATION_MAX_PER_DIMENSION * len(dimensions)

    # Build result
    result = EvaluationResult(
        evaluation_id=eval_id,
        date=today,
        target_repo=target_repo,
        agent=agent,
        cycles=cycles,
        after_task=after_task,
        dimensions=dimensions,
        total_score=total,
        max_total=max_total,
        tasks_created=[],
    )

    # Write report
    write_evaluation_report(eval_dir, result)

    # Create follow-up tasks
    tasks_created = create_followup_tasks(task_dir, result)
    result["tasks_created"] = tasks_created

    # Re-write report with task references
    if tasks_created:
        write_evaluation_report(eval_dir, result)

    # Cleanup clone
    try:
        if clone_dir is not None:
            shutil.rmtree(clone_dir, ignore_errors=True)
    except OSError:
        pass

    return result
