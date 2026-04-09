"""CLI entry points: run, test, summarize, verify-cycle, module-map."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from collections.abc import Sequence
from pathlib import Path

from nightshift.core.constants import now_local, print_status
from nightshift.core.errors import NightshiftError
from nightshift.core.shell import command_exists, git, run_command
from nightshift.core.state import append_cycle_state, load_json, read_state, write_json
from nightshift.core.types import CycleResult, CycleVerification
from nightshift.infra.module_map import generate_module_map, render_module_map, write_module_map
from nightshift.infra.multi import run_multi_shift
from nightshift.infra.worktree import (
    discover_base_branch,
    ensure_shift_log,
    ensure_shift_log_committed,
    ensure_worktree,
    install_dependencies_if_needed,
    resolve_runtime_dir,
    resolve_shift_log_relative_dir,
    revert_cycle,
    sync_shift_log,
)
from nightshift.owl.cycle import (
    _as_cycle_result,
    build_backend_escalation,
    build_category_balancing,
    build_prompt,
    command_for_agent,
    evaluate_baseline,
    extract_json,
    high_signal_focus_paths,
    parse_cycle_result,
    read_repo_instructions,
    recent_hot_files,
    verify_cycle,
)
from nightshift.owl.eval_runner import format_eval_table, run_eval_dry_run, run_eval_full
from nightshift.owl.scoring import score_diff
from nightshift.raven.feature import build_feature
from nightshift.raven.planner import build_plan_prompt, format_plan, parse_plan, run_plan_agent, scope_check
from nightshift.raven.profiler import profile_repo
from nightshift.settings.config import infer_verify_command, merge_config, resolve_agent

SCRIPT_DIR = Path(__file__).resolve().parent


def _write_rejected_cycle_artifact(
    *,
    runtime_dir: Path,
    today: str,
    cycle_number: int,
    cycle_result: CycleResult | None,
    verification: CycleVerification,
) -> None:
    artifact_path = runtime_dir / f"{today}.md"
    if artifact_path.exists():
        lines = artifact_path.read_text(encoding="utf-8").rstrip().splitlines()
        if lines:
            lines.append("")
    else:
        lines = [
            f"# Nightshift -- {today}",
            "",
            "## Summary",
            "This validation run produced rejected findings. The work below was reverted after cycle verification rejected the cycle, so none of it shipped.",
            "",
            "## Rejected Findings",
            "",
        ]

    notes = ""
    fixes: Sequence[object] = ()
    logged_issues: Sequence[object] = ()
    if isinstance(cycle_result, dict):
        raw_notes = cycle_result.get("notes")
        notes = raw_notes.strip() if isinstance(raw_notes, str) else ""
        raw_fixes = cycle_result.get("fixes")
        fixes = raw_fixes if isinstance(raw_fixes, list) else []
        raw_logged = cycle_result.get("logged_issues")
        logged_issues = raw_logged if isinstance(raw_logged, list) else []

    files_touched_raw = verification.get("files_touched")
    files_touched = files_touched_raw if isinstance(files_touched_raw, list) else []
    violations_raw = verification.get("violations")
    violations = violations_raw if isinstance(violations_raw, list) else []
    verify_command = verification.get("verify_command")
    verify_status = verification.get("verify_status")
    verify_exit_code = verification.get("verify_exit_code")

    verify_line = f"- Verification: `{verify_command}` -> {verify_status}"
    if isinstance(verify_exit_code, int):
        verify_line += f" (exit {verify_exit_code})"

    if files_touched:
        files_line = ", ".join(f"`{entry}`" for entry in files_touched if isinstance(entry, str))
    else:
        files_line = "(none)"

    lines.extend(
        [
            f"### Cycle {cycle_number}",
            "",
            "- Result: rejected and reverted",
            verify_line,
            f"- Files touched before revert: {files_line}",
        ]
    )
    if notes:
        lines.append(f"- Agent summary: {notes}")

    if fixes:
        lines.extend(["", "Rejected fixes:"])
        for index, fix in enumerate(fixes, start=1):
            if not isinstance(fix, dict):
                continue
            title = str(fix.get("title", "Untitled fix"))
            category = fix.get("category")
            impact = fix.get("impact")
            files = fix.get("files")
            file_list = (
                ", ".join(f"`{entry}`" for entry in files if isinstance(entry, str)) if isinstance(files, list) else ""
            )
            suffix_parts = [part for part in (category, impact) if isinstance(part, str) and part]
            suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
            line = f"{index}. {title}{suffix}"
            if file_list:
                line += f" -- {file_list}"
            lines.append(line)
    elif not notes:
        lines.extend(["", "Rejected fixes:", "1. No structured fix details were preserved in the cycle result."])

    if logged_issues:
        lines.extend(["", "Rejected logged issues:"])
        for index, issue in enumerate(logged_issues, start=1):
            if not isinstance(issue, dict):
                continue
            title = str(issue.get("title", "Untitled issue"))
            category = issue.get("category")
            severity = issue.get("severity")
            reason = issue.get("reason")
            suffix_parts = [part for part in (category, severity) if isinstance(part, str) and part]
            suffix = f" ({', '.join(suffix_parts)})" if suffix_parts else ""
            line = f"{index}. {title}{suffix}"
            if isinstance(reason, str) and reason:
                line += f" -- {reason}"
            lines.append(line)

    if violations:
        lines.extend(["", "Rejected because:"])
        for violation in violations:
            if isinstance(violation, str):
                lines.append(f"- {violation}")

    artifact_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_nightshift(args: argparse.Namespace, *, test_mode: bool) -> int:
    repo_dir = Path(args.repo_dir or os.getcwd()).resolve()
    config = merge_config(repo_dir)
    agent = resolve_agent(config, args.agent)
    config["agent"] = agent
    if getattr(args, "hours", None) is not None:
        config["hours"] = args.hours
    if getattr(args, "cycle_minutes", None) is not None:
        config["cycle_minutes"] = args.cycle_minutes
    today = args.date or now_local().strftime("%Y-%m-%d")
    runtime_dir = resolve_runtime_dir(repo_dir, test_mode=test_mode)
    shift_log_dir = resolve_shift_log_relative_dir(repo_dir)
    worktree_dir = runtime_dir / f"worktree-{today}"
    branch = f"nightshift/{today}"
    shift_log_relative = f"{shift_log_dir}/{today}.md"
    state_path = runtime_dir / f"{today}.state.json"
    runner_log = runtime_dir / f"{today}.runner.log"
    base_branch = discover_base_branch(repo_dir)
    verify_command = infer_verify_command(repo_dir, config)

    state = read_state(
        state_path,
        today=today,
        branch=branch,
        agent=agent,
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

    blocked_summary = "\n".join(f"- `{entry}`" for entry in [*config["blocked_paths"], *config["blocked_globs"]])
    target_repo_instructions = read_repo_instructions(repo_dir)
    dry_run_cycle = len(state["cycles"]) + 1
    dry_run_final = total_cycles is not None and dry_run_cycle == total_cycles
    dry_run_hot_files = recent_hot_files(repo_dir)
    backend_esc = build_backend_escalation(
        cycle=dry_run_cycle,
        config=config,
        state=state,
        repo_dir=repo_dir,
    )
    category_esc = build_category_balancing(
        cycle=dry_run_cycle,
        config=config,
        state=state,
    )
    prompt = build_prompt(
        cycle=dry_run_cycle,
        is_final=dry_run_final,
        config=config,
        state=state,
        shift_log_relative=shift_log_relative,
        blocked_summary=blocked_summary,
        hot_files=dry_run_hot_files,
        prior_path_bias=state["recent_cycle_paths"],
        focus_hints=high_signal_focus_paths(repo_dir, dry_run_hot_files),
        test_mode=test_mode,
        backend_escalation=backend_esc,
        category_balancing=category_esc,
        repo_instructions=target_repo_instructions,
    )
    if args.dry_run:
        print(prompt)
        return 0

    if not command_exists(agent):
        raise NightshiftError(f"`{agent}` is not installed or not on PATH.")

    runtime_dir.mkdir(parents=True, exist_ok=True)
    ensure_worktree(repo_dir, worktree_dir, branch)
    ensure_shift_log(worktree_dir / shift_log_relative, today=today, branch=branch, base_branch=base_branch)
    ensure_shift_log_committed(worktree_dir, shift_log_relative)
    if not test_mode:
        sync_shift_log(worktree_dir, repo_dir, shift_log_relative)
    install_dependencies_if_needed(worktree_dir, runner_log)
    evaluate_baseline(worktree_dir=worktree_dir, runner_log=runner_log, state=state)
    write_json(state_path, state)

    schema_path = (SCRIPT_DIR / "schemas" / "nightshift.schema.json").resolve()
    if not schema_path.exists():
        schema_path = (SCRIPT_DIR / ".." / "nightshift.schema.json").resolve()
    if not schema_path.exists():
        raise NightshiftError(f"Missing bundled schema file at {schema_path}")
    print_status("")
    print_status("+--------------------------------------------------+")
    print_status("|         NIGHTSHIFT STARTING                      |")
    print_status(f"|  Agent:      {agent:<36}|")
    print_status(f"|  Worktree:   {str(worktree_dir)[:36]:<36}|")
    print_status(f"|  Branch:     {branch[:36]:<36}|")
    print_status("+--------------------------------------------------+")
    print_status("")

    cycle_number = len(state["cycles"])
    while True:
        if total_cycles is not None and cycle_number >= total_cycles:
            break
        if end_time is not None and now_local().timestamp() >= end_time:
            break
        if state["halt_reason"]:
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

        print_status(f"-- Cycle {cycle_number} --- {now_local().strftime('%H:%M')} --")

        cycle_hot_files = recent_hot_files(repo_dir)
        backend_esc = build_backend_escalation(
            cycle=cycle_number,
            config=config,
            state=state,
            repo_dir=repo_dir,
        )
        category_esc = build_category_balancing(
            cycle=cycle_number,
            config=config,
            state=state,
        )
        prompt = build_prompt(
            cycle=cycle_number,
            is_final=is_final,
            config=config,
            state=state,
            shift_log_relative=shift_log_relative,
            blocked_summary=blocked_summary,
            hot_files=cycle_hot_files,
            prior_path_bias=state["recent_cycle_paths"],
            focus_hints=high_signal_focus_paths(repo_dir, cycle_hot_files),
            test_mode=test_mode,
            backend_escalation=backend_esc,
            category_balancing=category_esc,
            repo_instructions=target_repo_instructions,
        )

        message_path = runtime_dir / f"{today}.cycle-{cycle_number}.json"
        if message_path.exists():
            message_path.unlink()
        cmd = command_for_agent(
            agent=agent,
            prompt=prompt,
            cwd=worktree_dir,
            schema_path=schema_path,
            message_path=message_path,
            config=config,
        )
        print_status(" ".join(shlex.quote(part) for part in cmd))
        timeout_seconds = max(300, cycle_minutes * 60 + (240 if test_mode else 180))
        exit_code, raw_output = run_command(
            cmd,
            cwd=worktree_dir,
            log_path=runner_log,
            timeout_seconds=timeout_seconds,
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
            agent=agent,
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
            agent_output=raw_output,
        )

        if not valid:
            state["counters"]["failed_verifications"] += 1
            if test_mode:
                _write_rejected_cycle_artifact(
                    runtime_dir=runtime_dir,
                    today=today,
                    cycle_number=cycle_number,
                    cycle_result=cycle_result,
                    verification=verification,
                )
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

        # Score the diff before accepting.
        diff_score = score_diff(
            worktree_dir=worktree_dir,
            pre_head=pre_head,
            cycle_result=cycle_result,
            files_touched=verification["files_touched"],
        )
        threshold = int(config["score_threshold"])
        print_status(f"Diff score: {diff_score['score']}/10 ({diff_score['reason']})")
        if diff_score["score"] < threshold and verification["files_touched"]:
            print_status(
                f"Score {diff_score['score']} is below threshold {threshold}. "
                "Reverting cycle -- agent should try harder."
            )
            revert_cycle(worktree_dir, pre_head)
            state["cycles"].append(
                {
                    "cycle": cycle_number,
                    "status": "low-score",
                    "cycle_result": cycle_result,
                    "verification": verification,
                }
            )
            write_json(state_path, state)
            continue

        state["counters"]["failed_verifications"] = 0
        append_cycle_state(
            state=state,
            cycle_number=cycle_number,
            cycle_result=cycle_result,
            verification=verification,
        )
        if not test_mode:
            sync_shift_log(worktree_dir, repo_dir, shift_log_relative)
        write_json(state_path, state)

        if state["counters"]["empty_cycles"] >= int(config["stop_after_empty_cycles"]):
            state["halt_reason"] = "Empty cycle threshold reached."
            write_json(state_path, state)
            break

    print_status("")
    print_status("+--------------------------------------------------+")
    print_status("|         NIGHTSHIFT COMPLETE                      |")
    print_status(f"|  Cycles run: {len(state['cycles']):<36}|")
    halt_reason = state["halt_reason"]
    if halt_reason:
        print_status(f"|  Halted:     {halt_reason[:36]:<36}|")
    print_status("+--------------------------------------------------+")
    print_status("")
    shift_log_path = (worktree_dir / shift_log_relative) if test_mode else (repo_dir / shift_log_relative)
    print_status(f"Shift log:   {shift_log_path}")
    print_status(f"State file:  {state_path}")
    print_status(f"Runner log:  {runner_log}")
    print_status(f"Branch:      {branch}")
    unresolved_failure = (
        bool(state["halt_reason"])
        or state["counters"]["agent_failures"] > 0
        or state["counters"]["failed_verifications"] > 0
    )
    return 1 if unresolved_failure else 0


def summarize(args: argparse.Namespace) -> int:
    repo_dir = Path(args.repo_dir or os.getcwd()).resolve()
    date = args.date or now_local().strftime("%Y-%m-%d")
    state_path = resolve_runtime_dir(repo_dir, test_mode=False) / f"{date}.state.json"
    if not state_path.exists():
        test_state_path = resolve_runtime_dir(repo_dir, test_mode=True) / f"{date}.state.json"
        if test_state_path.exists():
            state_path = test_state_path
    if not state_path.exists():
        raise NightshiftError(f"No state file found at {state_path}")
    state = load_json(state_path)
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


def verify_cycle_cli(args: argparse.Namespace) -> int:
    repo_dir = Path(args.repo_dir or os.getcwd()).resolve()
    date = args.date or now_local().strftime("%Y-%m-%d")
    config = merge_config(repo_dir)
    agent_name = resolve_agent(config, args.agent)
    config["agent"] = agent_name
    runtime_dir = resolve_runtime_dir(repo_dir, test_mode=False)
    shift_log_dir = resolve_shift_log_relative_dir(repo_dir)
    state = read_state(
        runtime_dir / f"{date}.state.json",
        today=date,
        branch=f"nightshift/{date}",
        agent=agent_name,
        verify_command=infer_verify_command(repo_dir, config),
    )
    raw_result = extract_json(Path(args.result_file).read_text(encoding="utf-8")) if args.result_file else None
    cycle_result = _as_cycle_result(raw_result) if raw_result is not None else None
    valid, verification = verify_cycle(
        worktree_dir=Path(args.worktree_dir).resolve(),
        shift_log_relative=f"{shift_log_dir}/{date}.md",
        pre_head=args.pre_head,
        cycle_result=cycle_result,
        config=config,
        state=state,
        runner_log=runtime_dir / f"{date}.runner.log",
    )
    payload = {"valid": valid, "verification": verification}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if valid else 1


def plan_feature(args: argparse.Namespace) -> int:
    """Plan a feature: generate a planning prompt or parse a plan result."""
    repo_dir = Path(args.repo_dir or os.getcwd()).resolve()
    profile = profile_repo(repo_dir)
    feature_description: str = args.feature
    prompt = build_plan_prompt(profile, feature_description)

    if args.dry_run:
        print(prompt)
        return 0

    # If --result-file is provided, parse a plan from agent output
    if args.result_file:
        result_path = Path(args.result_file)
        if not result_path.exists():
            raise NightshiftError(f"Result file not found: {result_path}")
        raw_output = result_path.read_text(encoding="utf-8")
        plan = parse_plan(raw_output)
        if plan is None:
            raise NightshiftError("Could not parse a valid feature plan from the result file.")
        warning = scope_check(plan)
        if warning:
            print_status(f"WARNING: {warning}")
            print_status("")
        print(format_plan(plan))
        return 0

    # If --agent is provided, invoke the agent to generate the plan
    if args.agent:
        config = merge_config(repo_dir)
        plan = run_plan_agent(repo_dir, feature_description, args.agent, profile, config)
        warning = scope_check(plan)
        if warning:
            print_status(f"WARNING: {warning}")
            print_status("")
        print(format_plan(plan))
        return 0

    # Default: print the prompt for manual use with an agent
    print(prompt)
    return 0


def build_feature_cli(args: argparse.Namespace) -> int:
    """Run or inspect the Loop 2 feature builder."""
    repo_dir = Path(args.repo_dir or os.getcwd()).resolve()

    if args.status:
        if args.feature:
            raise NightshiftError("Do not pass a feature description with --status.")
        return build_feature(
            repo_dir=repo_dir,
            feature_description=None,
            agent=None,
            yes=False,
            resume=False,
            status_only=True,
        )

    if args.resume and args.feature:
        raise NightshiftError("Do not pass a feature description with --resume.")
    if not args.resume and not args.feature:
        raise NightshiftError("Feature description is required unless using --resume or --status.")

    resolved_agent: str | None = None
    if args.agent is not None:
        resolved_agent = args.agent
    elif not args.resume:
        config = merge_config(repo_dir)
        resolved_agent = resolve_agent(config, None)

    return build_feature(
        repo_dir=repo_dir,
        feature_description=args.feature,
        agent=resolved_agent,
        yes=args.yes,
        resume=args.resume,
        status_only=False,
    )


def module_map_cli(args: argparse.Namespace) -> int:
    """Render or write the persistent architecture module map."""
    repo_dir = Path(args.repo_dir or os.getcwd()).resolve()
    snapshot = generate_module_map(repo_dir)
    if args.write:
        path = write_module_map(repo_dir, snapshot=snapshot)
        print(path)
    else:
        print(render_module_map(snapshot))
    return 0


def eval_cli(args: argparse.Namespace) -> int:
    """Run the evaluation pipeline and print a dimension scorecard."""
    repo_dir = Path(args.repo_dir or os.getcwd()).resolve()
    write_report: bool = getattr(args, "write", False)

    if args.dry_run:
        result = run_eval_dry_run(repo_dir, write_report=write_report)
    else:
        agent = getattr(args, "agent", None) or "claude"
        result = run_eval_full(repo_dir, agent=agent, write_report=write_report)

    print(format_eval_table(result))
    return 0


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

    verify_parser = subparsers.add_parser(
        "verify-cycle", parents=[common], help="Verify a cycle against current policy"
    )
    verify_parser.add_argument("--worktree-dir", required=True, help="Worktree to verify")
    verify_parser.add_argument("--pre-head", required=True, help="Commit hash before the cycle")
    verify_parser.add_argument("--result-file", help="Structured result JSON from the agent")
    verify_parser.set_defaults(func=verify_cycle_cli)

    plan_parser = subparsers.add_parser("plan", parents=[common], help="Plan a feature build")
    plan_parser.add_argument("feature", help="Natural language feature description")
    plan_parser.add_argument("--dry-run", action="store_true", help="Print the planning prompt and exit")
    plan_parser.add_argument("--result-file", help="Parse a plan from agent output file")
    plan_parser.set_defaults(func=plan_feature)

    build_parser_cmd = subparsers.add_parser("build", parents=[common], help="Build a feature end-to-end")
    build_parser_cmd.add_argument("feature", nargs="?", help="Natural language feature description")
    build_parser_cmd.add_argument("--resume", action="store_true", help="Resume the current feature build")
    build_parser_cmd.add_argument("--status", action="store_true", help="Show current feature build status")
    build_parser_cmd.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    build_parser_cmd.set_defaults(func=build_feature_cli)

    module_map_parser = subparsers.add_parser(
        "module-map",
        parents=[common],
        help="Render the persistent module map for .recursive/architecture/MODULE_MAP.md",
    )
    module_map_parser.add_argument("--write", action="store_true", help="Write the module map file instead of printing")
    module_map_parser.set_defaults(func=module_map_cli)

    eval_parser = subparsers.add_parser(
        "eval",
        parents=[common],
        help="Run the evaluation pipeline and print a dimension scorecard",
    )
    eval_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Score synthetic artifacts without cloning or running a shift",
    )
    eval_parser.add_argument(
        "--write",
        action="store_true",
        help="Write the evaluation report to .recursive/evaluations/",
    )
    eval_parser.set_defaults(func=eval_cli)

    multi_parser = subparsers.add_parser("multi", parents=[common], help="Run shifts on multiple repos")
    multi_parser.add_argument("repos", nargs="+", help="Repository paths to process")
    multi_parser.add_argument("--test", action="store_true", help="Use test mode (short cycles)")
    multi_parser.add_argument("--cycles", type=int, default=4, help="Cycles per repo in test mode")
    multi_parser.add_argument("--cycle-minutes", type=int, default=8, help="Cycle duration in test mode")
    multi_parser.add_argument("hours", nargs="?", type=int, help="Override shift duration in hours")
    multi_parser.add_argument("--dry-run", action="store_true", help="Print first prompt for each repo and exit")
    multi_parser.set_defaults(
        func=lambda a: run_multi_shift(
            a,
            runner=lambda repo_args: run_nightshift(repo_args, test_mode=a.test),
        )
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result: int = args.func(args)
        return result
    except NightshiftError as error:
        print(f"nightshift: {error}", file=sys.stderr)
        return 1
