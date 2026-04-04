"""CLI entry points: run, test, summarize, verify-cycle."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

from nightshift.config import infer_verify_command, merge_config, resolve_agent
from nightshift.constants import now_local, print_status
from nightshift.cycle import (
    _as_cycle_result,
    build_backend_escalation,
    build_prompt,
    command_for_agent,
    evaluate_baseline,
    extract_json,
    high_signal_focus_paths,
    parse_cycle_result,
    recent_hot_files,
    verify_cycle,
)
from nightshift.errors import NightshiftError
from nightshift.scoring import score_diff
from nightshift.shell import command_exists, git, run_command
from nightshift.state import append_cycle_state, load_json, read_state, write_json
from nightshift.worktree import (
    discover_base_branch,
    ensure_shift_log,
    ensure_shift_log_committed,
    ensure_worktree,
    install_dependencies_if_needed,
    revert_cycle,
    sync_shift_log,
)

SCRIPT_DIR = Path(__file__).resolve().parent


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
    docs_dir = repo_dir / "docs" / "Nightshift"
    worktree_dir = docs_dir / f"worktree-{today}"
    branch = f"nightshift/{today}"
    shift_log_relative = f"docs/Nightshift/{today}.md"
    state_path = docs_dir / f"{today}.state.json"
    runner_log = docs_dir / f"{today}.runner.log"
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
    dry_run_cycle = len(state["cycles"]) + 1
    dry_run_final = total_cycles is not None and dry_run_cycle == total_cycles
    dry_run_hot_files = recent_hot_files(repo_dir)
    backend_esc = build_backend_escalation(
        cycle=dry_run_cycle,
        config=config,
        state=state,
        repo_dir=repo_dir,
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
    )
    if args.dry_run:
        print(prompt)
        return 0

    if not command_exists(agent):
        raise NightshiftError(f"`{agent}` is not installed or not on PATH.")

    docs_dir.mkdir(parents=True, exist_ok=True)
    ensure_worktree(repo_dir, worktree_dir, branch)
    ensure_shift_log(worktree_dir / shift_log_relative, today=today, branch=branch, base_branch=base_branch)
    ensure_shift_log_committed(worktree_dir, shift_log_relative)
    sync_shift_log(worktree_dir, repo_dir, shift_log_relative)
    install_dependencies_if_needed(worktree_dir, runner_log)
    evaluate_baseline(worktree_dir=worktree_dir, runner_log=runner_log, state=state)
    write_json(state_path, state)

    schema_path = (SCRIPT_DIR / ".." / "nightshift.schema.json").resolve()
    if not schema_path.exists():
        schema_path = (SCRIPT_DIR / "nightshift.schema.json").resolve()
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
        )

        message_path = docs_dir / f"{today}.cycle-{cycle_number}.json"
        if message_path.exists():
            message_path.unlink()
        cmd = command_for_agent(
            agent=agent,
            prompt=prompt,
            cwd=worktree_dir,
            schema_path=schema_path,
            message_path=message_path,
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
    print_status(f"Shift log:   {repo_dir / shift_log_relative}")
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
    agent_name = resolve_agent(config, args.agent)
    config["agent"] = agent_name
    state = read_state(
        repo_dir / "docs" / "Nightshift" / f"{date}.state.json",
        today=date,
        branch=f"nightshift/{date}",
        agent=agent_name,
        verify_command=infer_verify_command(repo_dir, config),
    )
    raw_result = extract_json(Path(args.result_file).read_text(encoding="utf-8")) if args.result_file else None
    cycle_result = _as_cycle_result(raw_result) if raw_result is not None else None
    valid, verification = verify_cycle(
        worktree_dir=Path(args.worktree_dir).resolve(),
        shift_log_relative=f"docs/Nightshift/{date}.md",
        pre_head=args.pre_head,
        cycle_result=cycle_result,
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

    verify_parser = subparsers.add_parser(
        "verify-cycle", parents=[common], help="Verify a cycle against current policy"
    )
    verify_parser.add_argument("--worktree-dir", required=True, help="Worktree to verify")
    verify_parser.add_argument("--pre-head", required=True, help="Commit hash before the cycle")
    verify_parser.add_argument("--result-file", help="Structured result JSON from the agent")
    verify_parser.set_defaults(func=verify_cycle_cli)

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
