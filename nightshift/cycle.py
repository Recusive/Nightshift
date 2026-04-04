"""Per-cycle logic: prompt building, agent dispatch, verification, evaluation."""

from __future__ import annotations

import fnmatch
import json
import re
import textwrap
from pathlib import Path
from typing import Any

from nightshift.constants import FORBIDDEN_CYCLE_COMMANDS, print_status
from nightshift.errors import NightshiftError
from nightshift.shell import git, run_shell_string
from nightshift.state import top_path
from nightshift.types import (
    CycleResult,
    CycleVerification,
    NightshiftConfig,
    ShiftState,
)
from nightshift.worktree import (
    cleanup_safe_artifacts,
    git_changed_files_for_commit,
    git_name_status_for_commit,
)


def extract_json(text: str) -> dict[str, Any] | None:
    payload = text.strip()
    if not payload:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", payload, re.DOTALL)
    if fenced:
        payload = fenced.group(1)
    try:
        loaded = json.loads(payload)
        if isinstance(loaded, dict):
            return loaded
        return None
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for index in range(len(payload)):
        if payload[index] != "{":
            continue
        try:
            loaded, end_index = decoder.raw_decode(payload[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict) and payload[index + end_index :].strip() == "":
            return loaded
    return None


def command_for_agent(
    *,
    agent: str,
    prompt: str,
    cwd: Path,
    schema_path: Path,
    message_path: Path,
) -> list[str]:
    if agent == "codex":
        return [
            "codex",
            "exec",
            "--json",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(message_path),
            "-c",
            'approval_policy="never"',
            "-s",
            "workspace-write",
            prompt,
        ]
    if agent == "claude":
        return [
            "claude",
            "-p",
            prompt,
            "--max-turns",
            "50",
            "--verbose",
        ]
    raise NightshiftError(f"Unsupported agent: {agent}")


def build_prompt(
    *,
    cycle: int,
    is_final: bool,
    config: NightshiftConfig,
    state: ShiftState,
    shift_log_relative: str,
    blocked_summary: str,
    hot_files: list[str],
    prior_path_bias: list[str],
    test_mode: bool,
) -> str:
    hot_files_lines = "\n".join(f"- `{entry}`" for entry in hot_files[:10]) or "- None"
    prior_paths = "\n".join(f"- `{entry}`" for entry in prior_path_bias[-2:]) or "- None"
    blocked_lines = textwrap.indent(blocked_summary, "        ")
    hot_lines = textwrap.indent(hot_files_lines, "        ")
    prior_lines = textwrap.indent(prior_paths, "        ")
    log_only = state["log_only_mode"]
    return textwrap.dedent(
        f"""
        You are Nightshift running inside an isolated git worktree. Do not create a worktree, do not switch branches, and do not touch the user's original checkout.

        Read these first:
        1. The repo's AGENTS.md / CLAUDE.md / equivalent instructions.
        2. The existing shift log at `{shift_log_relative}`.

        Cycle context:
        - Cycle: {cycle}
        - Final cycle: {"yes" if is_final else "no"}
        - Agent: {config["agent"]}
        - Log-only mode: {"yes" if log_only else "no"}

        Hard limits enforced by the runner:
        - At most {config["max_fixes_per_cycle"]} fixes this cycle.
        - At most {config["max_files_per_fix"]} files per fix.
        - At most {config["max_files_per_cycle"]} total files touched this cycle.
        - Low-impact fixes remaining this shift: {max(config["max_low_impact_fixes_per_shift"] - state["counters"]["low_impact_fixes"], 0)}.
        - Do not edit blocked paths or lockfiles:
{blocked_lines}
        - Avoid files with recent team activity unless you are only logging the issue:
{hot_lines}
        - Avoid staying in the same top-level area for more than two cycles. Recent dominant paths:
{prior_lines}

        Required behavior:
        - If a fix would exceed the limits, log the issue instead of editing.
        - If baseline verification is failing, do not make code changes; update the shift log with logged issues only.
        - One commit per accepted fix. Each fix commit must include the shift log update.
        - If you only add logged issues to the shift log, commit that shift-log update so the worktree ends clean.
        - Update the shift log immediately after every fix or logged issue.
        - Every fix entry must include `Impact` and `Verification`.
        - Do not run the repo's full verification or lint commands yourself. The Nightshift runner already executed baseline verification and will run final verification after your cycle.
        - If you need extra confidence, only run narrow, file-scoped checks that do not require background IPC servers or long-lived watchers.
        - Avoid package-manager test commands like `npm test`, `pnpm test`, `yarn test`, or `bun test` inside the cycle unless they are clearly file-scoped and sandbox-safe. Many JavaScript test runners spawn IPC servers and will fail under sandboxing even when the runner's own verification succeeds.
        - Do not add dependencies, do not delete files, and do not edit CI/deploy/generated artifacts.
        - Do not invoke Nightshift recursively. Never run `nightshift.py`, `run.sh`, `test.sh`, `codex exec`, or `claude -p` from inside this cycle.

        Category mix guidance:
        - Prefer breadth across Security, Error Handling, Tests, A11y, Code Quality, Performance, and Polish.
        - If you find repetitive low-value cleanup, fix a small representative sample and log the broader pattern.

        {"This is a short validation run. Finish quickly. Prefer exactly one small fix or one logged issue. If nothing clearly safe is found within a few minutes, log one issue and stop." if test_mode else ""}

        {"Final cycle instructions: wrap up the Summary and Recommendations sections, make sure commit hashes are correct, and run the full verification command one last time." if is_final else "Do not rewrite the final Summary yet unless there is less than one cycle left."}

        End your work with a single JSON object and nothing else. The JSON must satisfy the provided schema exactly.
        """
    ).strip()


def recent_hot_files(repo_dir: Path) -> list[str]:
    try:
        output = git(
            repo_dir,
            "log",
            "--since=7 days ago",
            "--name-only",
            "--pretty=format:",
            "-n",
            "50",
        )
    except NightshiftError:
        return []
    counts: dict[str, int] = {}
    for line in output.splitlines():
        entry = line.strip()
        if not entry:
            continue
        counts[entry] = counts.get(entry, 0) + 1
    hot: list[str] = []
    for entry, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        if count < 2:
            continue
        hot.append(entry)
        if len(hot) >= 20:
            break
    return hot


def blocked_file(path: str, config: NightshiftConfig) -> str | None:
    normalized = path.strip()
    if not normalized:
        return None
    for prefix in config["blocked_paths"]:
        if normalized.startswith(prefix):
            return f"blocked path prefix `{prefix}`"
    for pattern in config["blocked_globs"]:
        if fnmatch.fnmatch(normalized, pattern):
            return f"blocked glob `{pattern}`"
    return None


def _as_cycle_result(data: dict[str, Any]) -> CycleResult:
    """Construct a CycleResult from a raw JSON dict, field by field."""
    result = CycleResult()
    if "cycle" in data and isinstance(data["cycle"], int):
        result["cycle"] = data["cycle"]
    if "status" in data:
        result["status"] = str(data["status"])
    fixes = data.get("fixes")
    result["fixes"] = fixes if isinstance(fixes, list) else []
    logged = data.get("logged_issues")
    result["logged_issues"] = logged if isinstance(logged, list) else []
    categories = data.get("categories")
    result["categories"] = categories if isinstance(categories, list) else []
    touched = data.get("files_touched")
    result["files_touched"] = touched if isinstance(touched, list) else []
    tests_run = data.get("tests_run")
    result["tests_run"] = tests_run if isinstance(tests_run, list) else []
    if "notes" in data:
        result["notes"] = str(data["notes"])
    return result


def parse_cycle_result(
    *,
    agent: str,
    message_path: Path,
    raw_output: str,
) -> CycleResult | None:
    if agent == "codex" and message_path.exists():
        parsed = extract_json(message_path.read_text(encoding="utf-8"))
        if parsed is not None:
            return _as_cycle_result(parsed)
    result = extract_json(raw_output)
    if result is None:
        return None
    return _as_cycle_result(result)


def _extract_shell_command(command: str) -> str:
    shell_match = re.search(r"-lc\s+['\"](?P<body>.+?)['\"]$", command)
    if shell_match:
        return shell_match.group("body").strip()
    return command.strip()


def forbidden_cycle_commands(raw_output: str) -> list[str]:
    seen: list[str] = []
    for line in raw_output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        item = payload.get("item")
        if not isinstance(item, dict):
            continue
        if item.get("type") != "command_execution":
            continue
        command = item.get("command")
        if not isinstance(command, str):
            continue
        shell_command = _extract_shell_command(command)
        if shell_command in FORBIDDEN_CYCLE_COMMANDS and shell_command not in seen:
            seen.append(shell_command)
    return seen


def forbidden_reported_commands(cycle_result: CycleResult | None) -> list[str]:
    if cycle_result is None:
        return []
    seen: list[str] = []
    for entry in cycle_result.get("tests_run", []):
        for command in FORBIDDEN_CYCLE_COMMANDS:
            if entry.startswith(command) and command not in seen:
                seen.append(command)
    return seen


def expected_cycle_commits(cycle_result: CycleResult | None) -> int | None:
    if cycle_result is None:
        return None
    fixes = cycle_result.get("fixes", [])
    logged_issues = cycle_result.get("logged_issues", [])
    return len(fixes) + (1 if logged_issues else 0)


def evaluate_baseline(
    *,
    worktree_dir: Path,
    runner_log: Path,
    state: ShiftState,
) -> None:
    if state["baseline"]["status"] != "pending":
        return
    verify_command = state["verify_command"]
    if not verify_command:
        state["baseline"] = {
            "status": "skipped",
            "command": None,
            "message": "No verification command detected.",
        }
        return
    print_status(f"Running baseline verification: {verify_command}")
    exit_code, _ = run_shell_string(verify_command, cwd=worktree_dir, runner_log=runner_log)
    if exit_code == 0:
        state["baseline"] = {
            "status": "passed",
            "command": verify_command,
            "message": "Baseline verification passed.",
        }
        return
    state["baseline"] = {
        "status": "failed",
        "command": verify_command,
        "message": "Baseline verification failed; switching Nightshift into log-only mode.",
    }
    state["log_only_mode"] = True


def verify_cycle(
    *,
    worktree_dir: Path,
    shift_log_relative: str,
    pre_head: str,
    cycle_result: CycleResult | None,
    config: NightshiftConfig,
    state: ShiftState,
    runner_log: Path,
    agent_output: str = "",
) -> tuple[bool, CycleVerification]:
    verify_command = state["verify_command"]
    commit_output = git(worktree_dir, "rev-list", "--reverse", f"{pre_head}..HEAD", check=False)
    commits = [entry for entry in commit_output.splitlines() if entry.strip()]
    union_files: list[str] = []
    violations: list[str] = []
    for commit in commits:
        commit_files = git_changed_files_for_commit(worktree_dir, commit)
        name_status = git_name_status_for_commit(worktree_dir, commit)
        if shift_log_relative not in commit_files:
            violations.append(f"Commit {commit[:7]} does not include the shift log update.")
        for line in name_status:
            if line.startswith("D\t"):
                deleted_file = line.split("\t", 1)[1]
                violations.append(f"File deletion is not allowed: {deleted_file}")
        for file_path in commit_files:
            reason = blocked_file(file_path, config)
            if reason:
                violations.append(f"Blocked file touched: {file_path} ({reason})")
        union_files.extend(commit_files)
    unique_files = sorted(set(union_files))
    non_log_files = [entry for entry in unique_files if entry != shift_log_relative]

    if len(commits) > int(config["max_fixes_per_cycle"]):
        violations.append(
            f"Cycle created {len(commits)} commits, exceeding max_fixes_per_cycle={config['max_fixes_per_cycle']}."
        )
    if len(non_log_files) > int(config["max_files_per_cycle"]):
        violations.append(
            f"Cycle touched {len(non_log_files)} files, exceeding max_files_per_cycle={config['max_files_per_cycle']}."
        )

    if state["log_only_mode"] and non_log_files:
        violations.append("Log-only mode is active, but code files were modified.")

    for command in forbidden_cycle_commands(agent_output):
        violations.append(f"Agent ran forbidden repo-wide command during cycle: `{command}`")
    for command in forbidden_reported_commands(cycle_result):
        message = f"Agent reported forbidden repo-wide command during cycle: `{command}`"
        if message not in violations:
            violations.append(message)

    if cycle_result is None and config["agent"] == "codex":
        violations.append("Agent cycle did not produce a structured JSON result.")
    if cycle_result is not None:
        expected_commits = expected_cycle_commits(cycle_result)
        if expected_commits is not None and len(commits) != expected_commits:
            violations.append(
                f"Cycle created {len(commits)} commits but structured output implies {expected_commits}."
            )
        for fix in cycle_result.get("fixes", []):
            if len(set(fix.get("files", []))) > int(config["max_files_per_fix"]):
                violations.append(
                    f"Fix `{fix.get('title', 'unknown')}` exceeded max_files_per_fix={config['max_files_per_fix']}."
                )
        new_low = sum(1 for fix in cycle_result.get("fixes", []) if fix.get("impact") == "low")
        if state["counters"]["low_impact_fixes"] + new_low > int(config["max_low_impact_fixes_per_shift"]):
            violations.append("Low-impact fix cap for the shift would be exceeded.")

        category_counts = dict(state["category_counts"])
        total_fixes = state["counters"]["fixes"]
        for fix in cycle_result.get("fixes", []):
            category = fix.get("category")
            if category is not None:
                category_counts[category] = category_counts.get(category, 0) + 1
            total_fixes += 1
        if total_fixes >= 4:
            for category, count in category_counts.items():
                if count / total_fixes > 0.5:
                    violations.append(
                        f"Category dominance exceeded 50% after this cycle: {category} would own {count}/{total_fixes} fixes."
                    )

    recent_paths = state["recent_cycle_paths"]
    cycle_path = top_path(non_log_files)
    if (
        cycle_path != "(none)"
        and len(recent_paths) >= 2
        and recent_paths[-1] == cycle_path
        and recent_paths[-2] == cycle_path
    ):
        violations.append(f"Top-level path `{cycle_path}` would be touched for a third consecutive cycle.")

    cleanup_safe_artifacts(worktree_dir)
    status_output = git(worktree_dir, "status", "--porcelain", check=False)
    if status_output.strip():
        violations.append("Worktree is dirty after the cycle. The runner requires a clean state.")

    verification: CycleVerification = {
        "verify_command": verify_command,
        "verify_status": "skipped",
        "verify_exit_code": None,
        "dominant_path": cycle_path,
        "commits": commits,
        "files_touched": non_log_files,
        "violations": violations,
    }

    if verify_command and not state["log_only_mode"]:
        print_status(f"Running verification: {verify_command}")
        exit_code, _ = run_shell_string(verify_command, cwd=worktree_dir, runner_log=runner_log)
        verification["verify_exit_code"] = exit_code
        verification["verify_status"] = "passed" if exit_code == 0 else "failed"
        if exit_code != 0:
            violations.append(f"Verification command failed: `{verify_command}`")

    return (not violations), verification
