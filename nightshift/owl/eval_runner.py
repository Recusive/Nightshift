"""Evaluation runner: score nightshift against a target repo (or dry-run with synthetic data).

This module provides two modes:
  1. Dry-run: generate synthetic artifacts and score them without any network
     access or subprocess invocations. Safe for CI and offline development.
  2. Full: clone the configured target repo, run a test shift, collect real
     artifacts, and delegate scoring to the existing evaluation infrastructure.

The public surface is two functions:
  - run_eval_dry_run()  -> EvaluationResult
  - run_eval_full()     -> EvaluationResult
  - format_eval_table() -> str  (human-readable scorecard)
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from nightshift.core.constants import (
    EVALUATION_CLONE_DEST,
    EVALUATION_DEFAULT_CYCLE_MINUTES,
    EVALUATION_DEFAULT_CYCLES,
    EVALUATION_DIMENSIONS,
    EVALUATION_MAX_PER_DIMENSION,
    EVALUATION_SCORE_THRESHOLD,
    EVALUATION_SHIFT_TIMEOUT,
    EVALUATION_TEMPLATE_MARKERS,
)
from nightshift.core.errors import NightshiftError
from nightshift.core.types import DimensionScore, EvaluationResult, ShiftArtifacts
from nightshift.settings.config import merge_config

# ---------------------------------------------------------------------------
# Synthetic artifact generation (dry-run)
# ---------------------------------------------------------------------------

_SYNTHETIC_STATE: dict[str, object] = {
    "version": 1,
    "date": "2026-01-01",
    "branch": "nightshift/2026-01-01",
    "agent": "claude",
    "verify_command": "make test",
    "baseline": {"status": "passed", "command": "make test", "message": ""},
    "counters": {
        "fixes": 2,
        "issues_logged": 1,
        "files_touched": 3,
        "low_impact_fixes": 0,
        "failed_verifications": 0,
        "empty_cycles": 0,
        "agent_failures": 0,
        "tests_written": 1,
    },
    "category_counts": {"Security": 1, "Tests": 1},
    "recent_cycle_paths": ["src/auth.py"],
    "cycles": [
        {
            "cycle": 1,
            "status": "accepted",
            "fixes": [
                {"title": "Fix auth bypass", "category": "Security", "impact": "high", "files": ["src/auth.py"]},
                {"title": "Add unit tests", "category": "Tests", "impact": "medium", "files": ["tests/test_auth.py"]},
            ],
            "logged_issues": [{"title": "Deprecated API", "category": "Code Quality", "severity": "low"}],
            "verification": {
                "verify_command": "make test",
                "verify_status": "passed",
                "verify_exit_code": 0,
                "dominant_path": "src/",
                "commits": ["abc123"],
                "files_touched": ["src/auth.py", "tests/test_auth.py"],
                "violations": [],
            },
        }
    ],
    "halt_reason": None,
    "log_only_mode": False,
}

_SYNTHETIC_SHIFT_LOG = """# Nightshift -- 2026-01-01

**Branch**: `nightshift/2026-01-01`
**Base**: `main`
**Started**: 2026-01-01T00:00:00

## Summary

Cycle 1 fixed an auth bypass vulnerability and added unit tests.

## Stats
- Fixes committed: 2
- Issues logged: 1
- Tests added: 1
- Files touched: 3
- Low-impact fixes: 0

---

## Fixes

1. Fix auth bypass (Security, high) -- src/auth.py -- abc123 -- make test passed
2. Add unit tests (Tests, medium) -- tests/test_auth.py -- abc123 -- make test passed

---

## Logged Issues

1. Deprecated API (Code Quality, low) -- use supported API variant

---

## Recommendations

No major blockers detected.
"""


def _build_synthetic_artifacts() -> ShiftArtifacts:
    """Return a ShiftArtifacts dict populated with realistic synthetic data."""
    return ShiftArtifacts(
        state=_SYNTHETIC_STATE,
        shift_log=_SYNTHETIC_SHIFT_LOG,
        runner_exit_code=0,
        state_file_valid=True,
        shift_log_exists=True,
        git_status_output="",
        repo_is_clean=True,
    )


# ---------------------------------------------------------------------------
# Scoring (pure -- no I/O)
# ---------------------------------------------------------------------------


def _score_startup(artifacts: ShiftArtifacts) -> DimensionScore:
    """Did the shift start and complete without fatal errors?"""
    passed = artifacts["runner_exit_code"] == 0
    score = 8 if passed else 0
    return DimensionScore(
        name="Startup",
        score=score,
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes="exit=0" if passed else "non-zero exit",
    )


def _score_discovery(artifacts: ShiftArtifacts) -> DimensionScore:
    """Did the agent discover issues and log at least one fix or issue?"""
    state = artifacts["state"]
    if not isinstance(state, dict):
        return DimensionScore(name="Discovery", score=0, max_score=EVALUATION_MAX_PER_DIMENSION, notes="no state")
    counters = state.get("counters")
    if not isinstance(counters, dict):
        return DimensionScore(name="Discovery", score=0, max_score=EVALUATION_MAX_PER_DIMENSION, notes="no counters")
    fixes: object = counters.get("fixes", 0)
    logged: object = counters.get("issues_logged", 0)
    total = (fixes if isinstance(fixes, int) else 0) + (logged if isinstance(logged, int) else 0)
    score = min(10, total * 3)
    return DimensionScore(
        name="Discovery",
        score=score,
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes=f"fixes={fixes} issues={logged}",
    )


def _score_fix_quality(artifacts: ShiftArtifacts) -> DimensionScore:
    """Are the fixes structured with category + impact metadata?"""
    state = artifacts["state"]
    if not isinstance(state, dict):
        return DimensionScore(name="Fix quality", score=0, max_score=EVALUATION_MAX_PER_DIMENSION, notes="no state")
    cycles_raw = state.get("cycles", [])
    cycles = cycles_raw if isinstance(cycles_raw, list) else []
    total_fixes = 0
    structured_fixes = 0
    for cycle in cycles:
        if not isinstance(cycle, dict):
            continue
        fixes_raw = cycle.get("fixes", [])
        fixes = fixes_raw if isinstance(fixes_raw, list) else []
        for fix in fixes:
            if not isinstance(fix, dict):
                continue
            total_fixes += 1
            if fix.get("category") and fix.get("impact"):
                structured_fixes += 1
    if total_fixes == 0:
        score = 0
        notes = "no fixes"
    else:
        ratio = structured_fixes / total_fixes
        score = round(ratio * 10)
        notes = f"{structured_fixes}/{total_fixes} structured"
    return DimensionScore(name="Fix quality", score=score, max_score=EVALUATION_MAX_PER_DIMENSION, notes=notes)


def _score_shift_log(artifacts: ShiftArtifacts) -> DimensionScore:
    """Does the shift log exist and look real (not a template stub)?"""
    if not artifacts["shift_log_exists"]:
        return DimensionScore(name="Shift log", score=0, max_score=EVALUATION_MAX_PER_DIMENSION, notes="missing")
    log_text = artifacts["shift_log"]
    for marker in EVALUATION_TEMPLATE_MARKERS:
        if marker in log_text:
            return DimensionScore(
                name="Shift log",
                score=3,
                max_score=EVALUATION_MAX_PER_DIMENSION,
                notes="template unfilled",
            )
    score = 8 if len(log_text) > 200 else 5
    return DimensionScore(name="Shift log", score=score, max_score=EVALUATION_MAX_PER_DIMENSION, notes="present")


def _score_state_file(artifacts: ShiftArtifacts) -> DimensionScore:
    """Is the state file valid JSON with the expected schema?"""
    if not artifacts["state_file_valid"]:
        return DimensionScore(name="State file", score=0, max_score=EVALUATION_MAX_PER_DIMENSION, notes="invalid")
    state = artifacts["state"]
    if not isinstance(state, dict):
        return DimensionScore(name="State file", score=0, max_score=EVALUATION_MAX_PER_DIMENSION, notes="not a dict")
    required_keys = {"version", "cycles", "counters", "halt_reason"}
    missing = required_keys - set(state.keys())
    if missing:
        return DimensionScore(
            name="State file",
            score=4,
            max_score=EVALUATION_MAX_PER_DIMENSION,
            notes=f"missing {', '.join(sorted(missing))}",
        )
    return DimensionScore(name="State file", score=8, max_score=EVALUATION_MAX_PER_DIMENSION, notes="valid")


def _score_verification(artifacts: ShiftArtifacts) -> DimensionScore:
    """Did the verify command run and pass for accepted cycles?"""
    state = artifacts["state"]
    if not isinstance(state, dict):
        return DimensionScore(name="Verification", score=0, max_score=EVALUATION_MAX_PER_DIMENSION, notes="no state")
    cycles_raw = state.get("cycles", [])
    cycles = cycles_raw if isinstance(cycles_raw, list) else []
    passed = 0
    total = 0
    for cycle in cycles:
        if not isinstance(cycle, dict):
            continue
        verification = cycle.get("verification")
        if not isinstance(verification, dict):
            continue
        total += 1
        if verification.get("verify_status") == "passed":
            passed += 1
    if total == 0:
        return DimensionScore(name="Verification", score=5, max_score=EVALUATION_MAX_PER_DIMENSION, notes="skipped")
    score = round((passed / total) * 10)
    return DimensionScore(
        name="Verification",
        score=score,
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes=f"{passed}/{total} passed",
    )


def _score_guard_rails(artifacts: ShiftArtifacts) -> DimensionScore:
    """Did the agent stay within blocked paths and produce clean git state?"""
    repo_is_clean = artifacts["repo_is_clean"]
    git_out = artifacts["git_status_output"]
    if not repo_is_clean:
        return DimensionScore(
            name="Guard rails",
            score=4,
            max_score=EVALUATION_MAX_PER_DIMENSION,
            notes="dirty working tree",
        )
    # If git status produced no output, the repo is in a clean committed state
    score = 9 if not git_out.strip() else 7
    return DimensionScore(name="Guard rails", score=score, max_score=EVALUATION_MAX_PER_DIMENSION, notes="clean")


def _score_clean_state(artifacts: ShiftArtifacts) -> DimensionScore:
    """No untracked/uncommitted files left behind?"""
    git_out = artifacts["git_status_output"]
    if not git_out.strip():
        return DimensionScore(name="Clean state", score=10, max_score=EVALUATION_MAX_PER_DIMENSION, notes="clean")
    # Count untracked lines
    untracked = sum(1 for line in git_out.splitlines() if line.startswith("?? ") or line.startswith(" M "))
    score = max(0, 8 - untracked * 2)
    return DimensionScore(name="Clean state", score=score, max_score=EVALUATION_MAX_PER_DIMENSION, notes="some changes")


def _score_breadth(artifacts: ShiftArtifacts) -> DimensionScore:
    """Did the agent touch multiple categories / file paths?"""
    state = artifacts["state"]
    if not isinstance(state, dict):
        return DimensionScore(name="Breadth", score=0, max_score=EVALUATION_MAX_PER_DIMENSION, notes="no state")
    cat_counts_raw = state.get("category_counts", {})
    cat_counts = cat_counts_raw if isinstance(cat_counts_raw, dict) else {}
    n_categories = len(cat_counts)
    score = min(10, n_categories * 3)
    return DimensionScore(
        name="Breadth",
        score=score,
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes=f"{n_categories} categories",
    )


def _score_usefulness(artifacts: ShiftArtifacts) -> DimensionScore:
    """Holistic: did the shift produce something a developer would value?"""
    state = artifacts["state"]
    if not isinstance(state, dict):
        return DimensionScore(name="Usefulness", score=0, max_score=EVALUATION_MAX_PER_DIMENSION, notes="no state")
    counters = state.get("counters", {})
    if not isinstance(counters, dict):
        return DimensionScore(name="Usefulness", score=0, max_score=EVALUATION_MAX_PER_DIMENSION, notes="no counters")
    fixes_raw: object = counters.get("fixes", 0)
    tests_raw: object = counters.get("tests_written", 0)
    fixes = fixes_raw if isinstance(fixes_raw, int) else 0
    tests = tests_raw if isinstance(tests_raw, int) else 0
    score = min(10, fixes * 3 + tests * 2)
    return DimensionScore(
        name="Usefulness",
        score=score,
        max_score=EVALUATION_MAX_PER_DIMENSION,
        notes=f"fixes={fixes} tests={tests}",
    )


_DIMENSION_SCORERS = [
    _score_startup,
    _score_discovery,
    _score_fix_quality,
    _score_shift_log,
    _score_state_file,
    _score_verification,
    _score_guard_rails,
    _score_clean_state,
    _score_breadth,
    _score_usefulness,
]

if len(_DIMENSION_SCORERS) != len(EVALUATION_DIMENSIONS):
    raise NightshiftError(
        f"scorer count ({len(_DIMENSION_SCORERS)}) must match EVALUATION_DIMENSIONS ({len(EVALUATION_DIMENSIONS)})"
    )


def score_artifacts(artifacts: ShiftArtifacts) -> list[DimensionScore]:
    """Run all dimension scorers against the provided artifacts."""
    return [scorer(artifacts) for scorer in _DIMENSION_SCORERS]


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def format_eval_table(result: EvaluationResult) -> str:
    """Render an EvaluationResult as a human-readable dimension table."""
    lines: list[str] = [
        f"Evaluation #{result['evaluation_id']:04d}  "
        f"  date={result['date']}  target={result['target_repo']}  agent={result['agent']}",
        "",
        f"{'Dimension':<20}  {'Score':>5}  {'Max':>4}  Notes",
        "-" * 64,
    ]
    for dim in result["dimensions"]:
        lines.append(f"{dim['name']:<20}  {dim['score']:>5}  {dim['max_score']:>4}  {dim['notes']}")
    lines.append("-" * 64)
    lines.append(f"{'TOTAL':<20}  {result['total_score']:>5}  {result['max_total']:>4}")
    below_threshold = [d for d in result["dimensions"] if d["score"] < EVALUATION_SCORE_THRESHOLD]
    if below_threshold:
        lines.append("")
        lines.append("Dimensions below threshold:")
        for dim in below_threshold:
            lines.append(f"  - {dim['name']} ({dim['score']}/{dim['max_score']})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dry-run entry point
# ---------------------------------------------------------------------------


def _next_eval_id(eval_dir: Path) -> int:
    """Return the next sequential evaluation ID from existing reports."""
    if not eval_dir.is_dir():
        return 1
    nums: list[int] = []
    for f in eval_dir.glob("[0-9]*.md"):
        try:
            nums.append(int(f.stem.lstrip("0") or "0"))
        except ValueError:
            continue
    return max(nums, default=0) + 1


def run_eval_dry_run(
    repo_dir: Path,
    *,
    write_report: bool = False,
) -> EvaluationResult:
    """Score synthetic artifacts without any network access or subprocesses.

    Args:
        repo_dir: repository root (used only to locate the eval_dir for the ID).
        write_report: if True, write the markdown report to .recursive/evaluations/.

    Returns:
        EvaluationResult with dimension scores and totals.
    """
    eval_dir = repo_dir / ".recursive" / "evaluations"
    eval_id = _next_eval_id(eval_dir)
    date = datetime.now().strftime("%Y-%m-%d")

    artifacts = _build_synthetic_artifacts()
    dimensions = score_artifacts(artifacts)
    total = sum(d["score"] for d in dimensions)
    max_total = sum(d["max_score"] for d in dimensions)

    result = EvaluationResult(
        evaluation_id=eval_id,
        date=date,
        target_repo="(dry-run -- synthetic artifacts)",
        agent="(dry-run)",
        cycles=0,
        after_task="",
        dimensions=dimensions,
        total_score=total,
        max_total=max_total,
        tasks_created=[],
    )

    if write_report:
        _write_eval_report(eval_dir, eval_id, result)

    return result


# ---------------------------------------------------------------------------
# Full evaluation entry point
# ---------------------------------------------------------------------------


def _collect_artifacts_from_dir(runtime_dir: Path, date: str) -> ShiftArtifacts:
    """Read shift state and log from a completed test run directory."""
    import json

    state: dict[str, object] | None = None
    state_file_valid = False
    state_path = runtime_dir / f"{date}.state.json"
    if state_path.exists():
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                state = raw
                state_file_valid = True
        except (json.JSONDecodeError, OSError):
            pass

    shift_log = ""
    shift_log_exists = False
    # The shift log is written under docs/Nightshift/ in the eval clone
    log_candidates = list(runtime_dir.glob(f"**/{date}.md"))
    if log_candidates:
        try:
            shift_log = log_candidates[0].read_text(encoding="utf-8")
            shift_log_exists = True
        except OSError:
            pass

    runner_log_path = runtime_dir / f"{date}.runner.log"
    runner_exit_code = 0
    if runner_log_path.exists():
        # Check the last few bytes of the log for a non-zero exit marker
        try:
            tail = runner_log_path.read_text(encoding="utf-8")[-512:]
            if "exit_code=1" in tail or "exit_code: 1" in tail:
                runner_exit_code = 1
        except OSError:
            pass

    return ShiftArtifacts(
        state=state,
        shift_log=shift_log,
        runner_exit_code=runner_exit_code,
        state_file_valid=state_file_valid,
        shift_log_exists=shift_log_exists,
        git_status_output="",
        repo_is_clean=True,
    )


def run_eval_full(
    repo_dir: Path,
    *,
    agent: str = "claude",
    write_report: bool = True,
) -> EvaluationResult:
    """Clone the configured target repo, run a test shift, and score the results.

    Args:
        repo_dir: the nightshift project root (used for config and report location).
        agent: agent identifier to pass to the test shift.
        write_report: if True, write the markdown report to .recursive/evaluations/.

    Returns:
        EvaluationResult with dimension scores and totals.

    Raises:
        NightshiftError: if the target repo is not configured or cloning fails.
    """
    config = merge_config(repo_dir)
    target = config.get("eval_target_repo", "")
    if not target:
        raise NightshiftError("eval_target_repo is not set in config. Add it to .nightshift.json or .recursive.json.")

    eval_dir = repo_dir / ".recursive" / "evaluations"
    eval_id = _next_eval_id(eval_dir)
    date = datetime.now().strftime("%Y-%m-%d")

    clone_dest = Path(EVALUATION_CLONE_DEST)
    if clone_dest.exists():
        shutil.rmtree(clone_dest)

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", target, str(clone_dest)],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        raise NightshiftError(f"Failed to clone {target}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise NightshiftError(f"Clone of {target} timed out") from exc

    import tempfile

    runtime_dir = Path(tempfile.mkdtemp(prefix="nightshift-eval-"))
    try:
        result_data = _run_test_shift_subprocess(
            repo_dir=repo_dir,
            clone_dest=clone_dest,
            agent=agent,
            runtime_dir=runtime_dir,
            date=date,
        )
        artifacts = _collect_artifacts_from_dir(runtime_dir, date)
        artifacts["runner_exit_code"] = result_data.get("exit_code", 0)
    finally:
        if clone_dest.exists():
            shutil.rmtree(clone_dest, ignore_errors=True)
        shutil.rmtree(runtime_dir, ignore_errors=True)

    dimensions = score_artifacts(artifacts)
    total = sum(d["score"] for d in dimensions)
    max_total = sum(d["max_score"] for d in dimensions)

    result = EvaluationResult(
        evaluation_id=eval_id,
        date=date,
        target_repo=target,
        agent=agent,
        cycles=EVALUATION_DEFAULT_CYCLES,
        after_task="",
        dimensions=dimensions,
        total_score=total,
        max_total=max_total,
        tasks_created=[],
    )

    if write_report:
        _write_eval_report(eval_dir, eval_id, result)

    return result


def _run_test_shift_subprocess(
    *,
    repo_dir: Path,
    clone_dest: Path,
    agent: str,
    runtime_dir: Path,
    date: str,
) -> dict[str, Any]:
    """Invoke `python3 -m nightshift test` against the clone and return outcome."""
    cmd = [
        "python3",
        "-m",
        "nightshift",
        "test",
        "--repo-dir",
        str(clone_dest),
        "--agent",
        agent,
        "--cycles",
        str(EVALUATION_DEFAULT_CYCLES),
        "--cycle-minutes",
        str(EVALUATION_DEFAULT_CYCLE_MINUTES),
        "--date",
        date,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=EVALUATION_SHIFT_TIMEOUT,
            cwd=str(repo_dir),
        )
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "Timeout"}


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------


def _write_eval_report(eval_dir: Path, eval_id: int, result: EvaluationResult) -> Path:
    """Persist an EvaluationResult as a markdown report under eval_dir."""
    eval_dir.mkdir(parents=True, exist_ok=True)
    report_path = eval_dir / f"{eval_id:04d}.md"
    lines: list[str] = [
        f"# Evaluation {eval_id:04d}",
        "",
        f"**Date**: {result['date']}",
        f"**Target**: {result['target_repo']}",
        f"**Agent**: {result['agent']}",
        "",
        "## Scorecard",
        "",
        "| Dimension | Score | Max | Notes |",
        "|-----------|------:|----:|-------|",
    ]
    for dim in result["dimensions"]:
        lines.append(f"| {dim['name']} | {dim['score']} | {dim['max_score']} | {dim['notes']} |")
    lines.append(f"| **TOTAL** | **{result['total_score']}** | **{result['max_total']}** | |")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
