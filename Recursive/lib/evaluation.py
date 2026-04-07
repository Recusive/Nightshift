"""Self-evaluation for the Recursive daemon.

Clones a test target, runs the project's tool against it, scores the results,
and writes an evaluation report. Standalone — no dependency on target project code.

NOTE: This module provides the evaluation FRAMEWORK. The actual scoring logic
is project-specific. Each project defines its own test target and verification
commands in .recursive.json.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from config import merge_config


def clone_target_repo(target_url: str, dest: str = "/tmp/recursive-eval") -> Path:
    """Clone a test target repo for evaluation."""
    dest_path = Path(dest)
    if dest_path.exists():
        shutil.rmtree(dest_path)
    subprocess.run(
        ["git", "clone", "--depth", "1", target_url, str(dest_path)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return dest_path


def next_evaluation_id(eval_dir: str | Path) -> int:
    """Find the next evaluation number from existing reports."""
    edir = Path(eval_dir)
    if not edir.is_dir():
        return 1
    nums = []
    for f in edir.glob("[0-9]*.md"):
        try:
            nums.append(int(f.stem.lstrip("0") or "0"))
        except ValueError:
            continue
    return max(nums, default=0) + 1


def run_test_shift(
    repo_dir: str | Path,
    agent: str = "claude",
    cycles: int = 2,
    cycle_minutes: int = 5,
) -> dict[str, Any]:
    """Run the project's tool against the test target.

    Returns a dict with 'exit_code', 'stdout', 'stderr', 'duration_seconds'.
    """
    rd = Path(repo_dir)
    config = merge_config(rd)

    # Build the run command from config — each project defines its own test command
    test_cmd = config.get("commands", {}).get("test", "make test")
    cmd = test_cmd.split()

    start = datetime.now()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=cycles * cycle_minutes * 60 + 300,
            cwd=str(rd),
        )
        duration = (datetime.now() - start).total_seconds()
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": duration,
        }
    except subprocess.TimeoutExpired:
        duration = (datetime.now() - start).total_seconds()
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": "Timeout",
            "duration_seconds": duration,
        }


def format_evaluation_report(
    eval_id: int,
    target: str,
    agent: str,
    scores: dict[str, int],
    notes: dict[str, str],
) -> str:
    """Format an evaluation report as markdown."""
    total = sum(scores.values())
    max_total = len(scores) * 10
    date = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"# Evaluation {eval_id:04d}",
        "",
        f"**Date**: {date}",
        f"**Target**: {target}",
        f"**Agent**: {agent}",
        "",
        "## Scorecard",
        "",
        "| Dimension | Score | Notes |",
        "|-----------|-------|-------|",
    ]
    for dim, score in scores.items():
        note = notes.get(dim, "")
        lines.append(f"| {dim} | {score}/10 | {note} |")
    lines.append(f"| **TOTAL** | **{total}/{max_total}** | |")
    lines.append("")
    return "\n".join(lines)


def write_evaluation_report(
    eval_dir: str | Path,
    eval_id: int,
    content: str,
) -> Path:
    """Write an evaluation report to disk."""
    edir = Path(eval_dir)
    edir.mkdir(parents=True, exist_ok=True)
    report_path = edir / f"{eval_id:04d}.md"
    report_path.write_text(content, encoding="utf-8")
    return report_path


def evaluate(
    repo_dir: str | Path,
    agent: str = "claude",
    after_task: str = "",
) -> dict[str, Any]:
    """Run a full self-evaluation cycle.

    1. Read config for test target
    2. Clone the target
    3. Run the tool against it
    4. Score results
    5. Write report

    Returns dict with 'eval_id', 'total_score', 'report_path', 'error'.
    """
    rd = Path(repo_dir)
    config = merge_config(rd)
    target = config.get("test_target", "")
    eval_dir = rd / "docs" / "evaluations"

    if not target:
        return {"eval_id": 0, "total_score": 0, "report_path": "", "error": "No test_target in config"}

    eval_id = next_evaluation_id(eval_dir)

    try:
        # Clone
        clone_dest = Path("/tmp/recursive-eval")
        clone_target_repo(target, str(clone_dest))

        # Run test shift
        result = run_test_shift(
            clone_dest,
            agent=agent,
            cycles=config.get("cycles", 2),
            cycle_minutes=config.get("cycle_minutes", 5),
        )

        # Basic scoring (project-specific scoring goes here)
        scores = {
            "startup": 5 if result["exit_code"] == 0 else 0,
            "completion": 5 if result["exit_code"] == 0 else 2,
        }
        notes = {
            "startup": f"exit={result['exit_code']}",
            "completion": f"duration={result['duration_seconds']:.0f}s",
        }

        total = sum(scores.values())

        # Write report
        content = format_evaluation_report(eval_id, target, agent, scores, notes)
        report_path = write_evaluation_report(eval_dir, eval_id, content)

        # Cleanup
        if clone_dest.exists():
            shutil.rmtree(clone_dest, ignore_errors=True)

        return {
            "eval_id": eval_id,
            "total_score": total,
            "report_path": str(report_path),
            "error": "",
        }
    except Exception as e:
        return {
            "eval_id": eval_id,
            "total_score": 0,
            "report_path": "",
            "error": str(e),
        }
