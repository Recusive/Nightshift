"""Configuration loading, agent resolution, and environment detection."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from nightshift.core.constants import DEFAULT_CONFIG, SUPPORTED_AGENTS, print_status
from nightshift.core.errors import NightshiftError
from nightshift.core.shell import validate_verify_command
from nightshift.core.state import load_json
from nightshift.core.types import NightshiftConfig
from nightshift.settings.eval_targets import infer_target_verify_command


def _require_int(raw: dict[str, Any], key: str) -> int:
    val = raw.get(key)
    if not isinstance(val, int):
        raise NightshiftError(f".nightshift.json: '{key}' must be an integer, got {type(val).__name__}")
    return val


def _require_str(raw: dict[str, Any], key: str) -> str:
    val = raw.get(key)
    if not isinstance(val, str):
        raise NightshiftError(f".nightshift.json: '{key}' must be a string, got {type(val).__name__}")
    return val


def _require_str_list(raw: dict[str, Any], key: str) -> list[str]:
    val = raw.get(key)
    if not isinstance(val, list) or not all(isinstance(item, str) for item in val):
        raise NightshiftError(f".nightshift.json: '{key}' must be a list of strings")
    return val


def _build_config(raw: dict[str, Any]) -> NightshiftConfig:
    agent = raw.get("agent")
    if agent is not None and not isinstance(agent, str):
        raise NightshiftError(f".nightshift.json: 'agent' must be a string or null, got {type(agent).__name__}")
    verify_command = raw.get("verify_command")
    if verify_command is not None and not isinstance(verify_command, str):
        raise NightshiftError(
            f".nightshift.json: 'verify_command' must be a string or null, got {type(verify_command).__name__}"
        )
    if isinstance(verify_command, str):
        validate_verify_command(verify_command)
    notification_webhook = raw.get("notification_webhook")
    if notification_webhook is not None and not isinstance(notification_webhook, str):
        raise NightshiftError(
            f".nightshift.json: 'notification_webhook' must be a string or null, got {type(notification_webhook).__name__}"
        )
    return NightshiftConfig(
        agent=agent,
        hours=_require_int(raw, "hours"),
        cycle_minutes=_require_int(raw, "cycle_minutes"),
        verify_command=verify_command,
        blocked_paths=_require_str_list(raw, "blocked_paths"),
        blocked_globs=_require_str_list(raw, "blocked_globs"),
        max_fixes_per_cycle=_require_int(raw, "max_fixes_per_cycle"),
        max_files_per_fix=_require_int(raw, "max_files_per_fix"),
        max_files_per_cycle=_require_int(raw, "max_files_per_cycle"),
        max_low_impact_fixes_per_shift=_require_int(raw, "max_low_impact_fixes_per_shift"),
        stop_after_failed_verifications=_require_int(raw, "stop_after_failed_verifications"),
        stop_after_empty_cycles=_require_int(raw, "stop_after_empty_cycles"),
        score_threshold=_require_int(raw, "score_threshold"),
        test_incentive_cycle=_require_int(raw, "test_incentive_cycle"),
        backend_forcing_cycle=_require_int(raw, "backend_forcing_cycle"),
        category_balancing_cycle=_require_int(raw, "category_balancing_cycle"),
        claude_model=_require_str(raw, "claude_model"),
        claude_effort=_require_str(raw, "claude_effort"),
        codex_model=_require_str(raw, "codex_model"),
        codex_thinking=_require_str(raw, "codex_thinking"),
        notification_webhook=notification_webhook,
        readiness_checks=_require_str_list(raw, "readiness_checks"),
        eval_frequency=_require_int(raw, "eval_frequency"),
        eval_target_repo=_require_str(raw, "eval_target_repo"),
    )


_LIST_FIELDS: set[str] = {"blocked_paths", "blocked_globs"}


def merge_config(repo_dir: Path) -> NightshiftConfig:
    """Merge .nightshift.json with defaults.

    List fields (blocked_paths, blocked_globs) are unioned so user entries
    extend the defaults rather than replacing them.  Scalar fields are
    overwritten normally.
    """
    raw: dict[str, Any] = json.loads(json.dumps(DEFAULT_CONFIG))
    # Environment variable overrides (between defaults and config file).
    # Config file values win over env vars; env vars win over defaults.
    _ENV_OVERRIDES: dict[str, str] = {
        "claude_model": "NIGHTSHIFT_CLAUDE_MODEL",
        "codex_model": "NIGHTSHIFT_CODEX_MODEL",
        "codex_thinking": "NIGHTSHIFT_CODEX_THINKING",
    }
    for config_key, env_var in _ENV_OVERRIDES.items():
        env_val = os.environ.get(env_var)
        if env_val is not None:
            raw[config_key] = env_val
    path = repo_dir / ".nightshift.json"
    if path.exists():
        loaded = load_json(path)
        if not isinstance(loaded, dict):
            raise NightshiftError(".nightshift.json must contain a JSON object")
        for key, value in loaded.items():
            if key in _LIST_FIELDS and isinstance(value, list):
                existing = raw.get(key, [])
                seen: set[str] = set(existing)
                merged = list(existing)
                for item in value:
                    if item not in seen:
                        merged.append(item)
                        seen.add(item)
                raw[key] = merged
            else:
                raw[key] = value
    return _build_config(raw)


def prompt_for_agent() -> str:
    """Ask the user which agent to use. Only called when stdin is a TTY."""
    print_status("")
    print_status("Which agent should run this shift?")
    for i, name in enumerate(SUPPORTED_AGENTS, 1):
        print_status(f"  {i}) {name}")
    print_status("")
    while True:
        try:
            choice = input("Enter 1 or 2: ").strip()
        except (EOFError, KeyboardInterrupt) as exc:
            raise NightshiftError("No agent selected.") from exc
        if choice in ("1", "2"):
            selected = SUPPORTED_AGENTS[int(choice) - 1]
            print_status(f"  -> {selected}")
            return selected
        print_status("  Invalid choice. Enter 1 or 2.")


def resolve_agent(config: NightshiftConfig, cli_agent: str | None) -> str:
    """Determine which agent to use: CLI flag > config file > interactive prompt."""
    if cli_agent:
        return cli_agent
    if config["agent"]:
        return str(config["agent"])
    if sys.stdin.isatty():
        return prompt_for_agent()
    raise NightshiftError(
        'No agent configured. Pass --agent codex or --agent claude, or set "agent" in .nightshift.json.'
    )


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
    if (repo_dir / "package-lock.json").exists():
        return ["npm", "ci"]
    return ["npm", "install", "--package-lock=false"]


def _validated_inferred_command(command: str) -> str:
    """Assert that an inferred verify command passes validation (belt-and-suspenders).

    Inferred commands are produced by nightshift from hardcoded patterns and
    are expected to always be safe.  If the assertion fires, it indicates a bug
    in the inference logic rather than untrusted user input.
    """
    validate_verify_command(command)
    return command


def infer_verify_command(repo_dir: Path, config: NightshiftConfig) -> str | None:
    if config["verify_command"]:
        # Already validated at config-load time; return as-is.
        return str(config["verify_command"])
    target_command = infer_target_verify_command(repo_dir)
    if target_command:
        return _validated_inferred_command(target_command)
    package_json = repo_dir / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
        package_manager = infer_package_manager(repo_dir) or "npm"
        if "test:ci" in scripts:
            return _validated_inferred_command(f"{package_manager} run test:ci")
        if "test" in scripts:
            return _validated_inferred_command(f"{package_manager} test")
    if (repo_dir / "Cargo.toml").exists():
        return _validated_inferred_command("cargo test")
    if (repo_dir / "go.mod").exists():
        return _validated_inferred_command("go test ./...")
    if (repo_dir / "pyproject.toml").exists() or (repo_dir / "pytest.ini").exists():
        return _validated_inferred_command("python3 -m pytest")
    return None


def infer_lint_command(repo_dir: Path) -> str | None:
    package_json = repo_dir / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
        package_manager = infer_package_manager(repo_dir) or "npm"
        if "lint:ci" in scripts:
            return f"{package_manager} run lint:ci"
        if "lint" in scripts:
            return f"{package_manager} run lint"

    pyproject = repo_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
        except OSError:
            content = ""
        if "[tool.ruff" in content:
            return "python3 -m ruff check ."

    for config_name in ("ruff.toml", ".ruff.toml"):
        if (repo_dir / config_name).exists():
            return "python3 -m ruff check ."

    if (repo_dir / "Cargo.toml").exists():
        return "cargo clippy -- -D warnings"

    return None
