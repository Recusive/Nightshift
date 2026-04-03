#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import textwrap
from typing import Any


DATA_VERSION = 1
SCRIPT_DIR = Path(__file__).resolve().parent
CATEGORY_ORDER = [
    "Security",
    "Error Handling",
    "Tests",
    "A11y",
    "Code Quality",
    "Performance",
    "Polish",
]

DEFAULT_CONFIG: dict[str, Any] = {
    "agent": "codex",
    "hours": 8,
    "cycle_minutes": 30,
    "verify_command": None,
    "blocked_paths": [
        ".github/",
        "deploy/",
        "deployment/",
        "dist/",
        "infra/",
        "k8s/",
        "ops/",
        "terraform/",
        "vendor/",
    ],
    "blocked_globs": [
        "*.lock",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "bun.lockb",
        "Cargo.lock",
    ],
    "max_fixes_per_cycle": 3,
    "max_files_per_fix": 5,
    "max_files_per_cycle": 12,
    "max_low_impact_fixes_per_shift": 4,
    "stop_after_failed_verifications": 2,
    "stop_after_empty_cycles": 2,
}

SAFE_ARTIFACT_DIRS = [
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
]

SAFE_ARTIFACT_GLOBS = [
    "*.pyc",
    "*.pyo",
]

SHIFT_LOG_TEMPLATE = """# Nightshift — {today}

**Branch**: `{branch}`
**Base**: `{base_branch}`
**Started**: {started}

## Summary
The shift has started. Reconnaissance is underway and this summary will be rewritten as the overnight run accumulates real fixes and logged issues.

## Stats
- Fixes committed: 0
- Issues logged: 0
- Tests added: 0
- Files touched: 0
- Low-impact fixes: 0

---

## Fixes

<!-- Add entries as you work. Number sequentially and include the cycle number. -->

### 1. Example title (cycle 1)
- **Category**: Error Handling
- **Impact**: medium
- **Files**: `path/to/file.ts`
- **Commit**: `abcdef1`
- **Verification**: `npm test`
- **What I found**: Describe the concrete problem.
- **Why it matters**: Explain the production impact.
- **What I did**: Describe the exact change.

---

## Logged Issues

<!-- Add entries that need human review or larger architectural work. -->

### 1. Example logged issue
- **Severity**: medium
- **Category**: Code Quality
- **Files**: `path/to/file.ts`
- **What I found**: Describe the issue.
- **Production impact**: Explain why it matters.
- **Suggested fix**: Describe the likely next step.
- **Why not fixed tonight**: State the reason.

---

## Recommendations

- Add patterns and systemic follow-up items here as the shift progresses.
"""


class NightshiftError(RuntimeError):
    pass


def now_local() -> dt.datetime:
    return dt.datetime.now().astimezone()


def print_status(message: str) -> None:
    print(message, flush=True)


def run_command(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path | None = None,
    env: dict[str, str] | None = None,
    timeout_seconds: int | None = None,
) -> tuple[int, str]:
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: list[str] = []
    log_handle = None
    process_start = dt.datetime.now().timestamp()
    try:
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_handle = log_path.open("a", encoding="utf-8")
        assert process.stdout is not None
        while True:
            try:
                line = process.stdout.readline()
            except Exception:
                line = ""
            if line:
                sys.stdout.write(line)
                lines.append(line)
                if log_handle is not None:
                    log_handle.write(line)
                    log_handle.flush()
            elif process.poll() is not None:
                break
            if timeout_seconds is not None:
                try:
                    process.wait(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    pass
                runtime = 0.0
                if process.pid:
                    runtime = (dt.datetime.now().timestamp() - process_start)
                if runtime > timeout_seconds:
                    timeout_message = (
                        f"\n[nightshift] Agent cycle hit timeout after {timeout_seconds} seconds. "
                        "Terminating the agent process.\n"
                    )
                    sys.stdout.write(timeout_message)
                    lines.append(timeout_message)
                    if log_handle is not None:
                        log_handle.write(timeout_message)
                        log_handle.flush()
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    break
        process.wait()
    finally:
        if log_handle is not None:
            log_handle.close()
    return process.returncode, "".join(lines)


def run_capture(cmd: list[str], *, cwd: Path, check: bool = True) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise NightshiftError(
            f"Command failed ({result.returncode}): {' '.join(shlex.quote(part) for part in cmd)}\n"
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


def git(cwd: Path, *args: str, check: bool = True) -> str:
    return run_capture(["git", *args], cwd=cwd, check=check)


def command_exists(name: str) -> bool:
    return subprocess.run(
        ["bash", "-lc", f"command -v {shlex.quote(name)} >/dev/null"],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def merge_config(repo_dir: Path) -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    path = repo_dir / ".nightshift.json"
    if path.exists():
        loaded = load_json(path)
        if not isinstance(loaded, dict):
            raise NightshiftError(".nightshift.json must contain a JSON object")
        config.update(loaded)
    return config


def infer_package_manager(repo_dir: Path) -> str | None:
    if (repo_dir / "bun.lockb").exists():
        return "bun"
    if (repo_dir / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (repo_dir / "yarn.lock").exists():
        return "yarn"
    if (repo_dir / "package-lock.json").exists():
        return "npm"
    if (repo_dir / "package.json").exists():
        return "npm"
    return None


def infer_install_command(repo_dir: Path) -> list[str] | None:
    if not (repo_dir / "package.json").exists():
        return None
    package_manager = infer_package_manager(repo_dir)
    if package_manager == "bun":
        return ["bun", "install", "--frozen-lockfile"]
    if package_manager == "pnpm":
        return ["pnpm", "install", "--frozen-lockfile"]
    if package_manager == "yarn":
        return ["yarn", "install", "--frozen-lockfile"]
    return ["npm", "install"]


def infer_verify_command(repo_dir: Path, config: dict[str, Any]) -> str | None:
    if config.get("verify_command"):
        return str(config["verify_command"])
    package_json = repo_dir / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
        package_manager = infer_package_manager(repo_dir) or "npm"
        if "test:ci" in scripts:
            return f"{package_manager} run test:ci"
        if "test" in scripts:
            return f"{package_manager} test"
    if (repo_dir / "Cargo.toml").exists():
        return "cargo test"
    if (repo_dir / "go.mod").exists():
        return "go test ./..."
    if (repo_dir / "pyproject.toml").exists() or (repo_dir / "pytest.ini").exists():
        return "python3 -m pytest"
    return None


def ensure_worktree(repo_dir: Path, worktree_dir: Path, branch: str) -> None:
    # Clean up stale registrations left behind by interrupted or manually removed worktrees.
    git(repo_dir, "worktree", "prune", check=False)
    if worktree_dir.exists():
        print_status(f"Resuming existing worktree at: {worktree_dir}")
        return
    print_status(f"Creating worktree at: {worktree_dir}")
    branch_exists = bool(git(repo_dir, "branch", "--list", branch))
    try:
        if branch_exists:
            git(repo_dir, "worktree", "add", str(worktree_dir), branch)
        else:
            git(repo_dir, "worktree", "add", str(worktree_dir), "-b", branch)
    except NightshiftError as error:
        if "already registered worktree" not in str(error):
            raise
        git(repo_dir, "worktree", "prune", check=False)
        if branch_exists:
            git(repo_dir, "worktree", "add", "-f", str(worktree_dir), branch)
        else:
            git(repo_dir, "worktree", "add", "-f", str(worktree_dir), "-b", branch)


def ensure_shift_log(shift_log_path: Path, *, today: str, branch: str, base_branch: str) -> None:
    if shift_log_path.exists():
        return
    shift_log_path.parent.mkdir(parents=True, exist_ok=True)
    shift_log_path.write_text(
        SHIFT_LOG_TEMPLATE.format(
            today=today,
            branch=branch,
            base_branch=base_branch,
            started=now_local().strftime("%H:%M"),
        ),
        encoding="utf-8",
    )


def ensure_shift_log_committed(worktree_dir: Path, shift_log_relative: str) -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", shift_log_relative],
        cwd=str(worktree_dir),
        text=True,
        capture_output=True,
        check=False,
    ).returncode == 0
    if tracked:
        return
    status = git(worktree_dir, "status", "--porcelain", check=False)
    if shift_log_relative not in status:
        return
    git(worktree_dir, "add", shift_log_relative)
    git(
        worktree_dir,
        "commit",
        "-m",
        "nightshift: [meta] initialize shift log\n\nWhat: add the initial overnight shift scaffold\nFix: create the shift log before cycle work begins",
    )


def read_state(state_path: Path, *, today: str, branch: str, agent: str, verify_command: str | None) -> dict[str, Any]:
    if state_path.exists():
        payload = load_json(state_path)
        if payload.get("version") != DATA_VERSION:
            raise NightshiftError(f"Unsupported state version in {state_path}")
        return payload
    return {
        "version": DATA_VERSION,
        "date": today,
        "branch": branch,
        "agent": agent,
        "verify_command": verify_command,
        "baseline": {
            "status": "pending",
            "command": verify_command,
            "message": "",
        },
        "counters": {
            "fixes": 0,
            "issues_logged": 0,
            "files_touched": 0,
            "low_impact_fixes": 0,
            "failed_verifications": 0,
            "empty_cycles": 0,
            "agent_failures": 0,
        },
        "category_counts": {},
        "recent_cycle_paths": [],
        "cycles": [],
        "halt_reason": None,
        "log_only_mode": False,
    }


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


def blocked_file(path: str, config: dict[str, Any]) -> str | None:
    normalized = path.strip()
    if not normalized:
        return None
    for prefix in config.get("blocked_paths", []):
        if normalized.startswith(prefix):
            return f"blocked path prefix `{prefix}`"
    for pattern in config.get("blocked_globs", []):
        if fnmatch.fnmatch(normalized, pattern):
            return f"blocked glob `{pattern}`"
    return None


def cleanup_safe_artifacts(worktree_dir: Path) -> None:
    for directory_name in SAFE_ARTIFACT_DIRS:
        for path in worktree_dir.rglob(directory_name):
            if path.is_dir():
                subprocess.run(["rm", "-rf", str(path)], check=False)
    for pattern in SAFE_ARTIFACT_GLOBS:
        for path in worktree_dir.rglob(pattern):
            if path.is_file():
                path.unlink(missing_ok=True)


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
    config: dict[str, Any],
    state: dict[str, Any],
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
    log_only = state.get("log_only_mode", False)
    return textwrap.dedent(
        f"""
        You are Nightshift running inside an isolated git worktree. Do not create a worktree, do not switch branches, and do not touch the user's original checkout.

        Read these first:
        1. The repo's AGENTS.md / CLAUDE.md / equivalent instructions.
        2. The existing shift log at `{shift_log_relative}`.

        Cycle context:
        - Cycle: {cycle}
        - Final cycle: {"yes" if is_final else "no"}
        - Agent policy: {config["agent"]}
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


def discover_base_branch(repo_dir: Path) -> str:
    try:
        origin_head = git(repo_dir, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
        return origin_head.rsplit("/", 1)[-1]
    except NightshiftError:
        return git(repo_dir, "branch", "--show-current")


def install_dependencies_if_needed(worktree_dir: Path, runner_log: Path) -> None:
    install_cmd = infer_install_command(worktree_dir)
    if not install_cmd:
        return
    marker = worktree_dir / "node_modules"
    if marker.exists():
        return
    print_status("Installing dependencies in worktree...")
    exit_code, _ = run_command(install_cmd, cwd=worktree_dir, log_path=runner_log)
    if exit_code != 0:
        raise NightshiftError("Dependency install failed in worktree")


def run_shell_string(command: str, *, cwd: Path, runner_log: Path) -> tuple[int, str]:
    return run_command(["bash", "-lc", command], cwd=cwd, log_path=runner_log)


def evaluate_baseline(
    *,
    worktree_dir: Path,
    runner_log: Path,
    state: dict[str, Any],
) -> None:
    if state["baseline"]["status"] != "pending":
        return
    verify_command = state.get("verify_command")
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


def git_changed_files_for_commit(worktree_dir: Path, commit: str) -> list[str]:
    output = git(worktree_dir, "show", "--pretty=format:", "--name-only", commit)
    return [line.strip() for line in output.splitlines() if line.strip()]


def git_name_status_for_commit(worktree_dir: Path, commit: str) -> list[str]:
    output = git(worktree_dir, "show", "--pretty=format:", "--name-status", commit)
    return [line.strip() for line in output.splitlines() if line.strip()]


def revert_cycle(worktree_dir: Path, pre_head: str) -> None:
    subprocess.run(["git", "reset", "--hard", pre_head], cwd=str(worktree_dir), check=False)
    subprocess.run(["git", "clean", "-fd"], cwd=str(worktree_dir), check=False)


def parse_cycle_result(
    *,
    agent: str,
    message_path: Path,
    raw_output: str,
) -> dict[str, Any] | None:
    if agent == "codex" and message_path.exists():
        parsed = extract_json(message_path.read_text(encoding="utf-8"))
        if parsed is not None:
            return parsed
    return extract_json(raw_output)


def verify_cycle(
    *,
    worktree_dir: Path,
    shift_log_relative: str,
    pre_head: str,
    cycle_result: dict[str, Any] | None,
    config: dict[str, Any],
    state: dict[str, Any],
    runner_log: Path,
) -> tuple[bool, dict[str, Any]]:
    verify_command = state.get("verify_command")
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
                violations.append(f"File deletion is not allowed: {line.split('\t', 1)[1]}")
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

    if state.get("log_only_mode") and non_log_files:
        violations.append("Log-only mode is active, but code files were modified.")

    if cycle_result is None and config["agent"] == "codex":
        violations.append("Codex cycle did not produce a structured JSON result.")
    if cycle_result is not None:
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
            category_counts[category] = category_counts.get(category, 0) + 1
            total_fixes += 1
        if total_fixes >= 4:
            for category, count in category_counts.items():
                if count / total_fixes > 0.5:
                    violations.append(
                        f"Category dominance exceeded 50% after this cycle: {category} would own {count}/{total_fixes} fixes."
                    )

    recent_paths = state.get("recent_cycle_paths", [])
    cycle_path = top_path(non_log_files)
    if cycle_path != "(none)" and len(recent_paths) >= 2 and recent_paths[-1] == cycle_path and recent_paths[-2] == cycle_path:
        violations.append(f"Top-level path `{cycle_path}` would be touched for a third consecutive cycle.")

    cleanup_safe_artifacts(worktree_dir)
    status_output = git(worktree_dir, "status", "--porcelain", check=False)
    if status_output.strip():
        violations.append("Worktree is dirty after the cycle. The runner requires a clean state.")

    verification = {
        "verify_command": verify_command,
        "verify_status": "skipped",
        "verify_exit_code": None,
        "dominant_path": cycle_path,
        "commits": commits,
        "files_touched": non_log_files,
        "violations": violations,
    }

    if verify_command and not state.get("log_only_mode"):
        print_status(f"Running verification: {verify_command}")
        exit_code, _ = run_shell_string(verify_command, cwd=worktree_dir, runner_log=runner_log)
        verification["verify_exit_code"] = exit_code
        verification["verify_status"] = "passed" if exit_code == 0 else "failed"
        if exit_code != 0:
            violations.append(f"Verification command failed: `{verify_command}`")

    return (not violations), verification


def append_cycle_state(
    *,
    state: dict[str, Any],
    cycle_number: int,
    cycle_result: dict[str, Any] | None,
    verification: dict[str, Any],
) -> None:
    fixes = cycle_result.get("fixes", []) if cycle_result else []
    logged_issues = cycle_result.get("logged_issues", []) if cycle_result else []
    low_impact = sum(1 for fix in fixes if fix.get("impact") == "low")
    inferred_fix_count = len(fixes)
    if not fixes and not logged_issues and verification["commits"] and not state.get("log_only_mode"):
        inferred_fix_count = len(verification["commits"])

    for fix in fixes:
        category = fix.get("category")
        state["category_counts"][category] = state["category_counts"].get(category, 0) + 1

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

    state["cycles"].append(
        {
            "cycle": cycle_number,
            "status": cycle_result.get("status", "unknown") if cycle_result else "unknown",
            "fixes": fixes,
            "logged_issues": logged_issues,
            "verification": verification,
        }
    )


def sync_shift_log(worktree_dir: Path, repo_dir: Path, shift_log_relative: str) -> None:
    source = worktree_dir / shift_log_relative
    if not source.exists():
        return
    target = repo_dir / shift_log_relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def run_nightshift(args: argparse.Namespace, *, test_mode: bool) -> int:
    repo_dir = Path(args.repo_dir or os.getcwd()).resolve()
    config = merge_config(repo_dir)
    if args.agent:
        config["agent"] = args.agent
    if getattr(args, "hours", None) is not None:
        config["hours"] = args.hours
    if getattr(args, "cycle_minutes", None) is not None:
        config["cycle_minutes"] = args.cycle_minutes
    today = args.date or now_local().strftime("%Y-%m-%d")
    docs_dir = repo_dir / "docs" / "Nightshift"
    worktree_dir = docs_dir / f"worktree-{today}"
    branch = f"nightshift/{today}"
    shift_log_relative = f"docs/Nightshift/{today}.md"
    state_path = docs_dir / f"{today}.state.json"
    runner_log = docs_dir / f"{today}.runner.log"
    base_branch = discover_base_branch(repo_dir)
    verify_command = infer_verify_command(repo_dir, config)

    if not command_exists(config["agent"]):
        raise NightshiftError(f"`{config['agent']}` is not installed or not on PATH.")

    state = read_state(
        state_path,
        today=today,
        branch=branch,
        agent=config["agent"],
        verify_command=verify_command,
    )
    state["verify_command"] = verify_command

    if test_mode:
        total_cycles = args.cycles
        end_time = None
        cycle_minutes = args.cycle_minutes or 8
    else:
        total_cycles = None
        end_time = now_local().timestamp() + int(config["hours"]) * 3600
        cycle_minutes = int(config["cycle_minutes"])

    blocked_summary = "\n".join(
        f"- `{entry}`" for entry in [*config["blocked_paths"], *config["blocked_globs"]]
    )
    dry_run_cycle = len(state["cycles"]) + 1
    dry_run_final = total_cycles is not None and dry_run_cycle == total_cycles
    prompt = build_prompt(
        cycle=dry_run_cycle,
        is_final=dry_run_final,
        config=config,
        state=state,
        shift_log_relative=shift_log_relative,
        blocked_summary=blocked_summary,
        hot_files=recent_hot_files(repo_dir),
        prior_path_bias=state.get("recent_cycle_paths", []),
        test_mode=test_mode,
    )
    if args.dry_run:
        print(prompt)
        return 0

    docs_dir.mkdir(parents=True, exist_ok=True)
    ensure_worktree(repo_dir, worktree_dir, branch)
    ensure_shift_log(worktree_dir / shift_log_relative, today=today, branch=branch, base_branch=base_branch)
    ensure_shift_log_committed(worktree_dir, shift_log_relative)
    sync_shift_log(worktree_dir, repo_dir, shift_log_relative)
    install_dependencies_if_needed(worktree_dir, runner_log)
    evaluate_baseline(worktree_dir=worktree_dir, runner_log=runner_log, state=state)
    write_json(state_path, state)

    schema_path = (SCRIPT_DIR / "nightshift.schema.json").resolve()
    if not schema_path.exists():
        raise NightshiftError(f"Missing bundled schema file at {schema_path}")
    print_status("")
    print_status("╔══════════════════════════════════════════════════╗")
    print_status("║         NIGHTSHIFT STARTING                      ║")
    print_status(f"║  Agent:      {config['agent']:<36}║")
    print_status(f"║  Worktree:   {str(worktree_dir)[:36]:<36}║")
    print_status(f"║  Branch:     {branch[:36]:<36}║")
    print_status("╚══════════════════════════════════════════════════╝")
    print_status("")

    cycle_number = len(state["cycles"])
    while True:
        if total_cycles is not None and cycle_number >= total_cycles:
            break
        if end_time is not None and now_local().timestamp() >= end_time:
            break
        if state.get("halt_reason"):
            break

        cycle_number += 1
        pre_head = git(worktree_dir, "rev-parse", "HEAD")
        remaining_minutes = None
        if end_time is not None:
            remaining_minutes = int(max(0, end_time - now_local().timestamp()) // 60)
        is_final = False
        if total_cycles is not None:
            is_final = cycle_number == total_cycles
        elif remaining_minutes is not None:
            is_final = remaining_minutes < cycle_minutes + 10

        print_status(f"── Cycle {cycle_number} ─── {now_local().strftime('%H:%M')} ──")

        prompt = build_prompt(
            cycle=cycle_number,
            is_final=is_final,
            config=config,
            state=state,
            shift_log_relative=shift_log_relative,
            blocked_summary=blocked_summary,
            hot_files=recent_hot_files(repo_dir),
            prior_path_bias=state.get("recent_cycle_paths", []),
            test_mode=test_mode,
        )

        message_path = docs_dir / f"{today}.cycle-{cycle_number}.json"
        if message_path.exists():
            message_path.unlink()
        cmd = command_for_agent(
            agent=config["agent"],
            prompt=prompt,
            cwd=worktree_dir,
            schema_path=schema_path,
            message_path=message_path,
        )
        print_status(" ".join(shlex.quote(part) for part in cmd))
        exit_code, raw_output = run_command(
            cmd,
            cwd=worktree_dir,
            log_path=runner_log,
            timeout_seconds=max(60, cycle_minutes * 60 + 30),
        )

        if exit_code != 0:
            state["counters"]["agent_failures"] += 1
            state["cycles"].append(
                {
                    "cycle": cycle_number,
                    "status": "agent_failed",
                    "exit_code": exit_code,
                }
            )
            if state["counters"]["agent_failures"] >= 2:
                state["halt_reason"] = "Agent command failed twice in a row."
            write_json(state_path, state)
            continue

        state["counters"]["agent_failures"] = 0
        cycle_result = parse_cycle_result(
            agent=config["agent"],
            message_path=message_path,
            raw_output=raw_output,
        )
        valid, verification = verify_cycle(
            worktree_dir=worktree_dir,
            shift_log_relative=shift_log_relative,
            pre_head=pre_head,
            cycle_result=cycle_result,
            config=config,
            state=state,
            runner_log=runner_log,
        )

        if not valid:
            state["counters"]["failed_verifications"] += 1
            revert_cycle(worktree_dir, pre_head)
            state["cycles"].append(
                {
                    "cycle": cycle_number,
                    "status": "rejected",
                    "cycle_result": cycle_result,
                    "verification": verification,
                }
            )
            if state["counters"]["failed_verifications"] >= int(config["stop_after_failed_verifications"]):
                state["halt_reason"] = "Failed verification threshold reached."
            write_json(state_path, state)
            continue

        state["counters"]["failed_verifications"] = 0
        append_cycle_state(
            state=state,
            cycle_number=cycle_number,
            cycle_result=cycle_result,
            verification=verification,
        )
        sync_shift_log(worktree_dir, repo_dir, shift_log_relative)
        write_json(state_path, state)

        if state["counters"]["empty_cycles"] >= int(config["stop_after_empty_cycles"]):
            state["halt_reason"] = "Empty cycle threshold reached."
            write_json(state_path, state)
            break

    print_status("")
    print_status("╔══════════════════════════════════════════════════╗")
    print_status("║         NIGHTSHIFT COMPLETE                      ║")
    print_status(f"║  Cycles run: {len(state['cycles']):<36}║")
    if state.get("halt_reason"):
        print_status(f"║  Halted:     {state['halt_reason'][:36]:<36}║")
    print_status("╚══════════════════════════════════════════════════╝")
    print_status("")
    print_status(f"Shift log:   {repo_dir / shift_log_relative}")
    print_status(f"State file:  {state_path}")
    print_status(f"Runner log:  {runner_log}")
    print_status(f"Branch:      {branch}")
    unresolved_failure = bool(state.get("halt_reason")) or state["counters"]["agent_failures"] > 0 or state["counters"]["failed_verifications"] > 0
    return 1 if unresolved_failure else 0


def summarize(args: argparse.Namespace) -> int:
    repo_dir = Path(args.repo_dir or os.getcwd()).resolve()
    date = args.date or now_local().strftime("%Y-%m-%d")
    state_path = repo_dir / "docs" / "Nightshift" / f"{date}.state.json"
    if not state_path.exists():
        raise NightshiftError(f"No state file found at {state_path}")
    state = load_json(state_path)
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


def verify_cycle_cli(args: argparse.Namespace) -> int:
    repo_dir = Path(args.repo_dir or os.getcwd()).resolve()
    date = args.date or now_local().strftime("%Y-%m-%d")
    config = merge_config(repo_dir)
    if args.agent:
        config["agent"] = args.agent
    state = read_state(
        repo_dir / "docs" / "Nightshift" / f"{date}.state.json",
        today=date,
        branch=f"nightshift/{date}",
        agent=config["agent"],
        verify_command=infer_verify_command(repo_dir, config),
    )
    result = extract_json(Path(args.result_file).read_text(encoding="utf-8")) if args.result_file else None
    valid, verification = verify_cycle(
        worktree_dir=Path(args.worktree_dir).resolve(),
        shift_log_relative=f"docs/Nightshift/{date}.md",
        pre_head=args.pre_head,
        cycle_result=result,
        config=config,
        state=state,
        runner_log=repo_dir / "docs" / "Nightshift" / f"{date}.runner.log",
    )
    payload = {"valid": valid, "verification": verification}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if valid else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nightshift orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo-dir", help="Repository root to run from")
    common.add_argument("--agent", choices=["codex", "claude"], help="Override configured agent")
    common.add_argument("--date", help="Shift date in YYYY-MM-DD format")

    run_parser = subparsers.add_parser("run", parents=[common], help="Run a full overnight shift")
    run_parser.add_argument("hours", nargs="?", type=int, help="Override shift duration in hours")
    run_parser.add_argument("cycle_minutes", nargs="?", type=int, help="Override cycle minutes")
    run_parser.add_argument("--dry-run", action="store_true", help="Print the cycle prompt and exit")
    run_parser.set_defaults(func=lambda args: run_nightshift(args, test_mode=False))

    test_parser = subparsers.add_parser("test", parents=[common], help="Run a short validation shift")
    test_parser.add_argument("--cycles", type=int, default=4, help="Number of short cycles to run")
    test_parser.add_argument("--cycle-minutes", type=int, default=8, help="Guidance value inserted into prompts")
    test_parser.add_argument("--dry-run", action="store_true", help="Print the cycle prompt and exit")
    test_parser.set_defaults(func=lambda args: run_nightshift(args, test_mode=True))

    summarize_parser = subparsers.add_parser("summarize", parents=[common], help="Print shift state JSON")
    summarize_parser.set_defaults(func=summarize)

    verify_parser = subparsers.add_parser("verify-cycle", parents=[common], help="Verify a cycle against current policy")
    verify_parser.add_argument("--worktree-dir", required=True, help="Worktree to verify")
    verify_parser.add_argument("--pre-head", required=True, help="Commit hash before the cycle")
    verify_parser.add_argument("--result-file", help="Structured result JSON from the agent")
    verify_parser.set_defaults(func=verify_cycle_cli)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except NightshiftError as error:
        print(f"nightshift: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
