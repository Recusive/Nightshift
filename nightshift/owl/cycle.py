"""Per-cycle logic: prompt building, agent dispatch, verification, evaluation."""

from __future__ import annotations

import fnmatch
import json
import re
import textwrap
from pathlib import Path
from typing import Any

from nightshift.core.constants import (
    BACKEND_DIR_NAMES,
    BACKEND_EXTENSIONS,
    CATEGORY_ORDER,
    CLASSIFY_SKIP_DIRS,
    FORBIDDEN_CYCLE_COMMANDS,
    FRONTEND_DIR_NAMES,
    FRONTEND_EXTENSIONS,
    HIGH_SIGNAL_PATH_CANDIDATES,
    INSTRUCTION_FILE_NAMES,
    MAX_INSTRUCTION_FILE_BYTES,
    MAX_INSTRUCTION_TOTAL_BYTES,
    UNTRUSTED_INSTRUCTIONS_PREAMBLE,
    UNTRUSTED_INSTRUCTIONS_SUFFIX,
    VALID_CATEGORIES,
    print_status,
)
from nightshift.core.errors import NightshiftError
from nightshift.core.shell import git, run_shell_string
from nightshift.core.state import top_path
from nightshift.core.types import (
    CycleResult,
    CycleVerification,
    NightshiftConfig,
    ShiftState,
)
from nightshift.infra.worktree import (
    canonical_repo_relative_path,
    cleanup_safe_artifacts,
    git_changed_files_for_commit,
    git_name_status_for_commit,
)

# Allowlist for category strings supplied by agent output.  Only strings that
# appear in CATEGORY_ORDER are accepted; unknown strings are silently ignored.
# Defined once in constants.py; imported here to avoid duplication.
_VALID_CATEGORIES = VALID_CATEGORIES


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


def _truncate_utf8_bytes(text: str, limit_bytes: int) -> str:
    if limit_bytes <= 0:
        return ""
    return text.encode("utf-8")[:limit_bytes].decode("utf-8", errors="ignore").rstrip()


def _instruction_section(name: str, body: str) -> str:
    return f"--- {name} ---\n{body}\n--- end {name} ---"


def _sanitize_instruction_content(name: str, content: str) -> str:
    sanitized = content.replace(f"--- end {name} ---", f"[--- end {name} ---]")
    return sanitized.replace(
        UNTRUSTED_INSTRUCTIONS_SUFFIX,
        f"[{UNTRUSTED_INSTRUCTIONS_SUFFIX}]",
    )


def _fit_instruction_to_total_budget(*, name: str, content: str, remaining_bytes: int) -> tuple[str, int]:
    warning_body = (
        f"[WARNING: {name} truncated -- total instruction size cap ({MAX_INSTRUCTION_TOTAL_BYTES:,} bytes) reached]"
    )
    warning = f"\n\n{warning_body}"
    warning_bytes = len(warning.encode("utf-8"))
    if remaining_bytes >= warning_bytes:
        prefix = _truncate_utf8_bytes(content, remaining_bytes - warning_bytes)
        body = f"{prefix}{warning}" if prefix else warning_body
        return body, len(body.encode("utf-8"))
    short_warning = "[TRUNCATED]"
    short_warning_bytes = len(short_warning.encode("utf-8"))
    if remaining_bytes >= short_warning_bytes:
        return short_warning, short_warning_bytes
    return "", 0


def read_repo_instructions(repo_dir: Path) -> str:
    """Read instruction files from a target repo and return their combined content.

    Scans for known instruction file names (CLAUDE.md, AGENTS.md, etc.)
    and returns the content of all that exist, labeled by filename.
    Symlinks are rejected with a warning to prevent path-traversal attacks.
    Files exceeding MAX_INSTRUCTION_FILE_BYTES are truncated with a warning.
    Total combined content is capped at MAX_INSTRUCTION_TOTAL_BYTES.
    Returns an empty string if no instruction files are found.
    """
    sections: list[str] = []
    total_bytes = 0
    for name in INSTRUCTION_FILE_NAMES:
        file_path = repo_dir / name
        if file_path.is_symlink():
            sections.append(_instruction_section(name, f"[WARNING: {name} is a symlink -- skipped for security]"))
            continue
        if file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError:
                sections.append(_instruction_section(name, f"[WARNING: {name} is not valid UTF-8 -- skipped]"))
                continue
            except OSError:
                continue
            if not content:
                continue
            content = _sanitize_instruction_content(name, content)
            content_bytes = len(content.encode("utf-8"))
            if content_bytes > MAX_INSTRUCTION_FILE_BYTES:
                content = _truncate_utf8_bytes(content, MAX_INSTRUCTION_FILE_BYTES)
                content += (
                    f"\n\n[WARNING: {name} truncated from {content_bytes:,} bytes"
                    f" to {MAX_INSTRUCTION_FILE_BYTES:,} bytes]"
                )
                content_bytes = len(content.encode("utf-8"))
            remaining = MAX_INSTRUCTION_TOTAL_BYTES - total_bytes
            if remaining <= 0:
                sections.append(
                    _instruction_section(
                        name,
                        f"[WARNING: {name} skipped -- total instruction size cap ({MAX_INSTRUCTION_TOTAL_BYTES:,} bytes) reached]",
                    )
                )
                continue
            if content_bytes > remaining:
                content, content_bytes = _fit_instruction_to_total_budget(
                    name=name,
                    content=content,
                    remaining_bytes=remaining,
                )
                if not content:
                    continue
            total_bytes += content_bytes
            sections.append(_instruction_section(name, content))
    return "\n\n".join(sections)


def wrap_repo_instructions(raw_instructions: str) -> str:
    """Wrap raw instruction file content in an untrusted context block.

    Returns an empty string if the input is empty.
    """
    if not raw_instructions.strip():
        return ""
    return f"{UNTRUSTED_INSTRUCTIONS_PREAMBLE}\n{raw_instructions}\n\n{UNTRUSTED_INSTRUCTIONS_SUFFIX}"


def command_for_agent(
    *,
    agent: str,
    prompt: str,
    cwd: Path,
    schema_path: Path,
    message_path: Path,
    config: NightshiftConfig,
) -> list[str]:
    if agent == "codex":
        return [
            "codex",
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--json",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(message_path),
            "--model",
            config["codex_model"],
            "-c",
            f'reasoning_effort="{config["codex_thinking"]}"',
            prompt,
        ]
    if agent == "claude":
        return [
            "claude",
            "-p",
            prompt,
            "--max-turns",
            "50",
            "--model",
            config["claude_model"],
            "--effort",
            config["claude_effort"],
            "--verbose",
        ]
    raise NightshiftError(f"Unsupported agent: {agent}")


def build_test_escalation(
    *,
    cycle: int,
    config: NightshiftConfig,
    state: ShiftState,
) -> str:
    """Return a test-writing escalation message if the agent has not written tests.

    Returns an empty string when tests have been written or the cycle threshold
    has not been reached.
    """
    threshold = int(config.get("test_incentive_cycle", 3))
    if cycle < threshold:
        return ""
    if state["counters"]["tests_written"] > 0:
        return ""
    return (
        "You have not written any tests in this shift so far. "
        "Your next fix MUST include a test file. "
        "Writing tests is priority #3 (after Security and Error Handling). "
        "If you cannot find a security or error-handling issue, write a test."
    )


def build_category_balancing(
    *,
    cycle: int,
    config: NightshiftConfig,
    state: ShiftState,
) -> str:
    """Return a category-balancing directive if fix categories are lopsided.

    Steers the agent toward the highest-priority unexplored category
    from CATEGORY_ORDER. Returns an empty string when balancing is not
    needed or the cycle threshold has not been reached.
    """
    threshold = config["category_balancing_cycle"]
    if cycle < threshold:
        return ""

    category_counts = state["category_counts"]
    total_fixes = state["counters"]["fixes"]

    # Need at least 2 fixes before we can detect imbalance
    if total_fixes < 2:
        return ""

    # Find categories from CATEGORY_ORDER with zero fixes
    explored = set(category_counts.keys())
    unexplored = [cat for cat in CATEGORY_ORDER if cat not in explored]

    if not unexplored:
        return ""

    target = unexplored[0]
    parts = [
        f"Category imbalance detected: {len(unexplored)} of {len(CATEGORY_ORDER)} categories have no fixes yet.",
        f"Focus this cycle on {target} issues.",
    ]
    others = unexplored[1:3]
    if others:
        parts.append(f"Also underrepresented: {', '.join(others)}.")

    return " ".join(parts)


def _classify_dir(dir_path: Path) -> str:
    """Classify a single directory as 'frontend', 'backend', or 'unknown'.

    Uses the directory name first. If ambiguous, samples file extensions
    one level deep to break the tie.
    """
    name = dir_path.name.lower()
    if name in FRONTEND_DIR_NAMES:
        return "frontend"
    if name in BACKEND_DIR_NAMES:
        return "backend"
    # Ambiguous name (e.g. "src", "app") -- sample extensions
    frontend_count = 0
    backend_count = 0
    try:
        for child in dir_path.iterdir():
            if not child.is_file():
                continue
            ext = child.suffix.lower()
            if ext in FRONTEND_EXTENSIONS:
                frontend_count += 1
            elif ext in BACKEND_EXTENSIONS:
                backend_count += 1
    except OSError:
        return "unknown"
    if frontend_count == 0 and backend_count == 0:
        return "unknown"
    if frontend_count > backend_count:
        return "frontend"
    if backend_count > frontend_count:
        return "backend"
    return "unknown"


def classify_repo_dirs(repo_dir: Path) -> tuple[list[str], list[str]]:
    """Classify top-level directories as frontend or backend.

    Returns (frontend_dirs, backend_dirs). Directories that cannot be
    classified are excluded from both lists. Hidden directories and
    common non-code directories are skipped.
    """
    frontend: list[str] = []
    backend: list[str] = []
    try:
        entries = sorted(repo_dir.iterdir())
    except OSError:
        return ([], [])
    for entry in entries:
        if not entry.is_dir():
            continue
        name = entry.name
        if name.startswith(".") or name in CLASSIFY_SKIP_DIRS:
            continue
        classification = _classify_dir(entry)
        if classification == "frontend":
            frontend.append(name)
        elif classification == "backend":
            backend.append(name)
    return (frontend, backend)


def build_backend_escalation(
    *,
    cycle: int,
    config: NightshiftConfig,
    state: ShiftState,
    repo_dir: Path,
) -> str:
    """Return a backend-exploration directive if recent cycles are frontend-heavy.

    Returns an empty string when:
    - The cycle threshold has not been reached
    - Backend dirs have already been visited
    - The repo has no identifiable backend directories
    - Recent cycles are not all frontend-classified
    """
    threshold = int(config.get("backend_forcing_cycle", 3))
    if cycle < threshold:
        return ""
    recent = state["recent_cycle_paths"]
    if len(recent) < threshold:
        return ""
    frontend_dirs, backend_dirs = classify_repo_dirs(repo_dir)
    if not backend_dirs:
        return ""
    frontend_set = set(frontend_dirs)
    backend_set = set(backend_dirs)
    # Check recent paths, filtering out "(none)" from empty/log-only cycles
    real_paths = [p for p in recent if p != "(none)"]
    if len(real_paths) < threshold:
        return ""
    window = real_paths[-threshold:]
    all_frontend = all(p in frontend_set for p in window)
    any_backend = any(p in backend_set for p in window)
    if any_backend or not all_frontend:
        return ""
    dirs_list = ", ".join(f"`{d}`" for d in backend_dirs[:5])
    return (
        f"The last {threshold} cycles all targeted frontend code. "
        f"The backend has not been explored. "
        f"Focus this cycle on backend directories: {dirs_list}."
    )


def build_state_summary(state: ShiftState) -> str:
    """Build a human-readable summary of prior cycles for injection into the prompt.

    Returns an empty string when no cycles have run yet (cycle 1).
    """
    cycles = state["cycles"]
    if not cycles:
        return ""

    # Gather category fix counts from state-level aggregation
    category_counts = state["category_counts"]

    # Gather all top-level paths touched across cycles
    paths_touched: set[str] = set()
    for cycle_entry in cycles:
        verification = cycle_entry.get("verification")
        if verification:
            for file_path in verification["files_touched"]:
                if file_path:
                    paths_touched.add(file_path.split("/", 1)[0])

    lines: list[str] = []

    # What was fixed, by category
    if category_counts:
        fix_parts = [f"{count} {cat}" for cat, count in sorted(category_counts.items())]
        lines.append(f"Previous cycles fixed: {', '.join(fix_parts)}.")

    # Which categories remain unexplored
    explored = set(category_counts.keys())
    unexplored = [cat for cat in CATEGORY_ORDER if cat not in explored]
    if unexplored:
        lines.append(f"Categories not yet explored: {', '.join(unexplored)}.")

    # Which paths have been visited
    if paths_touched:
        sorted_paths = ", ".join(f"`{p}`" for p in sorted(paths_touched))
        lines.append(f"Paths already visited: {sorted_paths}. Explore different areas of the codebase.")

    # Running totals
    total_fixes = state["counters"]["fixes"]
    total_logged = state["counters"]["issues_logged"]
    if total_fixes or total_logged:
        lines.append(f"Running totals: {total_fixes} fix(es) committed, {total_logged} issue(s) logged.")

    return "\n".join(lines)


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
    focus_hints: list[str],
    test_mode: bool,
    backend_escalation: str = "",
    category_balancing: str = "",
    repo_instructions: str = "",
) -> str:
    hot_files_lines = "\n".join(f"- `{entry}`" for entry in hot_files[:10]) or "- None"
    prior_paths = "\n".join(f"- `{entry}`" for entry in prior_path_bias[-2:]) or "- None"
    focus_lines = "\n".join(f"- `{entry}`" for entry in focus_hints[:5]) or "- None"
    blocked_lines = textwrap.indent(blocked_summary, "        ")
    hot_lines = textwrap.indent(hot_files_lines, "        ")
    prior_lines = textwrap.indent(prior_paths, "        ")
    focus_block = textwrap.indent(focus_lines, "        ")
    log_only = state["log_only_mode"]
    state_summary = build_state_summary(state)
    state_block = ""
    if state_summary:
        indented = textwrap.indent(state_summary, "        ")
        state_block = f"\n        Prior cycle intelligence:\n{indented}\n"
    test_escalation = build_test_escalation(cycle=cycle, config=config, state=state)
    test_block = ""
    if test_escalation:
        indented_test = textwrap.indent(test_escalation, "        ")
        test_block = f"\n        Test writing directive:\n{indented_test}\n"
    backend_block = ""
    if backend_escalation:
        indented_backend = textwrap.indent(backend_escalation, "        ")
        backend_block = f"\n        Backend exploration directive:\n{indented_backend}\n"
    category_block = ""
    if category_balancing:
        indented_category = textwrap.indent(category_balancing, "        ")
        category_block = f"\n        Category balancing directive:\n{indented_category}\n"
    instructions_block = ""
    if repo_instructions:
        wrapped = wrap_repo_instructions(repo_instructions)
        indented_instructions = textwrap.indent(wrapped, "        ")
        instructions_block = f"\n{indented_instructions}\n"
    return textwrap.dedent(
        f"""
        You are Nightshift running inside an isolated git worktree. Do not create a worktree, do not switch branches, and do not touch the user's original checkout.

        Read the existing shift log at `{shift_log_relative}` before starting.
{instructions_block}

        Cycle context:
        - Cycle: {cycle}
        - Final cycle: {"yes" if is_final else "no"}
        - Agent: {config["agent"]}
        - Log-only mode: {"yes" if log_only else "no"}
{state_block}{test_block}{backend_block}{category_block}
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
        - Do not read or write files outside this isolated worktree, except for commands that operate on the current git metadata inside the worktree itself.
        - If a fix would exceed the limits, log the issue instead of editing.
        - If baseline verification is failing, do not make code changes; update the shift log with logged issues only.
        - One commit per accepted fix. Stage the shift log alongside your fix files so both ship in the same commit: `git add <fix-files> {shift_log_relative} && git commit`. If co-committing is not possible, make a separate shift-log-only commit immediately after.
        - At least one commit in this cycle must include the shift log. The runner rejects cycles with no shift log commit.
        - If you only add logged issues to the shift log, commit that shift-log update so the worktree ends clean.
        - Update the shift log immediately after every fix or logged issue.
        - Every fix entry must include `Impact` and `Verification`.
        - Do not run the repo's full verification or lint commands yourself. The Nightshift runner already executed baseline verification and will run final verification after your cycle.
        - If you need extra confidence, only run narrow, file-scoped checks that do not require background IPC servers or long-lived watchers.
        - Avoid repo-wide package-manager commands like `npm test`, `npm run lint`, `npm run build`, `pnpm test`, `pnpm lint`, `pnpm build`, `yarn test`, or `bun test` inside the cycle unless they are clearly file-scoped and sandbox-safe. Many JavaScript toolchains spawn IPC servers or duplicate the runner's own final verification.
        - Do not add dependencies, do not delete files, and do not edit CI/deploy/generated artifacts.
        - Do not access personal memory systems, home-directory notes, sibling repositories, or any path outside the target repo. If more context seems necessary, log the gap instead of leaving the worktree boundary.
        - Do not invoke Nightshift recursively. Never run `nightshift.py`, `run.sh`, `test.sh`, `codex exec`, or `claude -p` from inside this cycle.

        Category mix guidance:
        - Prefer breadth across Security, Error Handling, Tests, A11y, Code Quality, Performance, and Polish.
        - If you find repetitive low-value cleanup, fix a small representative sample and log the broader pattern.
        - Prefer high-signal, low-blast-radius helpers before broad UI sweeps when these areas exist:
{focus_block}

        {"This is a short validation run. Finish quickly. Prefer exactly one small fix or one logged issue. Prefer a 1-2 file fix in auth/session/http/parser/api helper code before choosing log-only. If nothing clearly safe is found within a few minutes, log one issue and stop." if test_mode else ""}

        {"Final cycle instructions: wrap up the Summary and Recommendations sections, make sure commit hashes are correct, and leave full verification to the Nightshift runner." if is_final else "Do not rewrite the final Summary yet unless there is less than one cycle left."}

        End your work with a single JSON object and nothing else. Required JSON structure:
        {{
          "cycle": <integer>,
          "status": "<completed|log_only|no_changes|failed>",
          "fixes": [
            {{
              "title": "<short description>",
              "category": "<Security|Error Handling|Tests|A11y|Code Quality|Performance|Polish>",
              "impact": "<high|medium|low>",
              "files": ["<file path>"],
              "commit": "<git commit hash>"
            }}
          ],
          "logged_issues": [
            {{
              "title": "<short description>",
              "category": "<Security|Error Handling|Tests|A11y|Code Quality|Performance|Polish>",
              "severity": "<critical|high|medium|low>",
              "files": ["<file path>"],
              "reason": "<why not fixed>"
            }}
          ],
          "categories": ["<category1>", "<category2>"],
          "files_touched": ["<file path>"],
          "tests_run": [],
          "notes": "<optional notes>"
        }}
        Each committed fix MUST appear as a structured object in "fixes" with all required fields (title, category, impact, files, commit). Do not use "fixes_committed" or "fixes_applied" count fields -- use the structured "fixes" array instead.
        """
    ).strip()


def high_signal_focus_paths(repo_dir: Path, hot_files: list[str]) -> list[str]:
    hot_prefixes = {entry for entry in hot_files if entry}
    existing = [c for c in HIGH_SIGNAL_PATH_CANDIDATES if (repo_dir / c).exists()]
    filtered = [c for c in existing if not any(_paths_overlap(c, hot) for hot in hot_prefixes)]
    candidates = filtered[:5] if filtered else existing[:5]
    return candidates


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


def _paths_overlap(path_a: str, path_b: str) -> bool:
    return path_a == path_b or path_a.startswith(f"{path_b}/") or path_b.startswith(f"{path_a}/")


def _matches_blocked_path_prefix(path: str, prefix: str) -> bool:
    normalized_prefix = prefix.strip().strip("/")
    if not normalized_prefix:
        return False
    return path == normalized_prefix or path.startswith(f"{normalized_prefix}/")


def _coerce_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    return None


def blocked_file(path: str, config: NightshiftConfig) -> str | None:
    normalized = path.strip()
    if not normalized:
        return None
    for prefix in config["blocked_paths"]:
        if _matches_blocked_path_prefix(normalized, prefix):
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
    if not isinstance(categories, list):
        categories = data.get("categories_covered")
    result["categories"] = categories if isinstance(categories, list) else []
    touched = data.get("files_touched")
    result["files_touched"] = touched if isinstance(touched, list) else []
    tests_run = data.get("tests_run")
    result["tests_run"] = tests_run if isinstance(tests_run, list) else []
    notes_parts: list[str] = []
    if "notes" in data and isinstance(data["notes"], str) and data["notes"].strip():
        notes_parts.append(data["notes"].strip())
    summary = data.get("summary")
    if isinstance(summary, str) and summary.strip() and summary.strip() not in notes_parts:
        notes_parts.append(summary.strip())
    if not result["fixes"]:
        fix_count = _coerce_nonnegative_int(data.get("fixes_applied"))
        if fix_count is None:
            fix_count = _coerce_nonnegative_int(data.get("fixes_committed"))
        if fix_count:
            notes_parts.append(f"Agent reported {fix_count} fix(es) in summary form.")
            result["fixes_count_only"] = fix_count
    if not result["logged_issues"]:
        issue_count = _coerce_nonnegative_int(data.get("issues_logged"))
        if issue_count:
            notes_parts.append(f"Agent reported {issue_count} logged issue(s) in summary form.")
    if notes_parts:
        result["notes"] = " ".join(notes_parts)
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
    """Extract the inner command from common shell wrappers.

    Handles patterns like:
    - /bin/zsh -lc 'npm run lint'
    - bash -c "npm test"
    - sh -c 'npm run build'
    - raw commands without a wrapper
    """
    shell_match = re.search(
        r"(?:/(?:usr/)?(?:bin/)?)?"
        r"(?:bash|sh|zsh|dash)\s+"
        r"(?:-\w+\s+)*"
        r"['\"](?P<body>.+?)['\"]$",
        command,
    )
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
        reported = _reported_forbidden_command(entry)
        if reported is not None and reported not in seen:
            seen.append(reported)
    return seen


def _reported_forbidden_command(entry: str) -> str | None:
    normalized = _extract_shell_command(entry).strip()
    for command in FORBIDDEN_CYCLE_COMMANDS:
        if normalized == command or normalized.startswith(f"{command} ("):
            return command
    return None


def expected_cycle_commits(cycle_result: CycleResult | None) -> tuple[int, int] | None:
    """Return (min_commits, max_commits) expected for the cycle.

    Agents may commit fixes and shift-log updates together or separately.
    The minimum assumes co-committed shift-log updates; the maximum adds
    one extra commit for a separate shift-log-only commit.

    When the agent returned a count-only payload (fixes_committed/fixes_applied)
    instead of a structured fixes[] list, fixes_count_only is used as fallback.
    """
    if cycle_result is None:
        return None
    fixes = cycle_result.get("fixes", [])
    fix_count = len(fixes) if fixes else cycle_result.get("fixes_count_only", 0)
    logged_issues = cycle_result.get("logged_issues", [])
    base = fix_count + (1 if logged_issues else 0)
    return (base, base + 1)


def expected_fix_commits(cycle_result: CycleResult | None) -> int | None:
    """Return the exact number of commits that should touch non-log files.

    When the agent returned a count-only payload (fixes_committed/fixes_applied)
    instead of a structured fixes[] list, fixes_count_only is used as fallback.
    """
    if cycle_result is None:
        return None
    fixes = cycle_result.get("fixes", [])
    if fixes:
        return len(fixes)
    return cycle_result.get("fixes_count_only", 0)


def allowed_total_cycle_commits(cycle_result: CycleResult | None) -> tuple[int, int] | None:
    """Return a bounded total-commit range for a cycle.

    Each fix needs one non-log commit. Agents may either co-commit the shift log
    or follow a fix with a separate shift-log-only commit, and the final wrap-up
    may add one extra shift-log-only summary commit.

    When the agent returned a count-only payload (fixes_committed/fixes_applied)
    instead of a structured fixes[] list, fixes_count_only is used as fallback.
    """
    if cycle_result is None:
        return None
    fixes = cycle_result.get("fixes", [])
    fix_count = len(fixes) if fixes else cycle_result.get("fixes_count_only", 0)
    logged_issues = cycle_result.get("logged_issues", [])
    min_commits = fix_count if fix_count else (1 if logged_issues else 0)
    max_commits = (fix_count * 2) + (1 if logged_issues and not fix_count else 0) + 1
    return (min_commits, max_commits)


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
    canonical_shift_log = canonical_repo_relative_path(worktree_dir, shift_log_relative)
    union_files: list[str] = []
    violations: list[str] = []
    shift_log_seen = False
    fix_commits = 0
    for commit in commits:
        commit_files = git_changed_files_for_commit(worktree_dir, commit)
        canonical_commit_files = [canonical_repo_relative_path(worktree_dir, file_path) for file_path in commit_files]
        name_status = git_name_status_for_commit(worktree_dir, commit)
        if canonical_shift_log in canonical_commit_files:
            shift_log_seen = True
        has_non_log_files = any(file_path != canonical_shift_log for file_path in canonical_commit_files)
        if has_non_log_files:
            fix_commits += 1
        for line in name_status:
            if line.startswith("D\t"):
                deleted_file = line.split("\t", 1)[1]
                violations.append(f"File deletion is not allowed: {deleted_file}")
        for file_path in commit_files:
            reason = blocked_file(file_path, config)
            if reason:
                violations.append(f"Blocked file touched: {file_path} ({reason})")
        union_files.extend(canonical_commit_files)
    if commits and not shift_log_seen:
        violations.append("No commit in this cycle includes the shift log update.")
    unique_files = sorted(set(union_files))
    non_log_files = [entry for entry in unique_files if entry != canonical_shift_log]

    if fix_commits > int(config["max_fixes_per_cycle"]):
        violations.append(
            f"Cycle created {fix_commits} fix commits, exceeding max_fixes_per_cycle={config['max_fixes_per_cycle']}."
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
        expected_non_log_commits = expected_fix_commits(cycle_result)
        if expected_non_log_commits is not None and fix_commits != expected_non_log_commits:
            violations.append(
                "Cycle created "
                f"{fix_commits} commit(s) touching non-log files but structured output implies "
                f"{expected_non_log_commits}."
            )
        total_commit_range = allowed_total_cycle_commits(cycle_result)
        if total_commit_range is not None:
            min_total_commits, max_total_commits = total_commit_range
            if len(commits) < min_total_commits or len(commits) > max_total_commits:
                violations.append(
                    f"Cycle created {len(commits)} total commits but allowed range is "
                    f"{min_total_commits}-{max_total_commits}."
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
            if category is not None and category in _VALID_CATEGORIES:
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
