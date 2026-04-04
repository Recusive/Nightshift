"""Tests for nightshift.py -- captures current behavior before refactoring.

Every testable function in the monolith is covered here. After the refactor
into a package, these same tests must pass with only import-path changes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nightshift  # noqa: I001


# --- Constants & Module-Level ------------------------------------------------


class TestConstants:
    def test_data_version_is_int(self):
        assert isinstance(nightshift.DATA_VERSION, int)
        assert nightshift.DATA_VERSION == 1

    def test_supported_agents(self):
        assert nightshift.SUPPORTED_AGENTS == ["codex", "claude"]

    def test_category_order_has_seven(self):
        assert len(nightshift.CATEGORY_ORDER) == 7
        assert "Security" in nightshift.CATEGORY_ORDER
        assert "Polish" in nightshift.CATEGORY_ORDER

    def test_default_config_agent_is_none(self):
        assert nightshift.DEFAULT_CONFIG["agent"] is None

    def test_default_config_has_all_keys(self):
        expected = {
            "agent",
            "hours",
            "cycle_minutes",
            "verify_command",
            "blocked_paths",
            "blocked_globs",
            "max_fixes_per_cycle",
            "max_files_per_fix",
            "max_files_per_cycle",
            "max_low_impact_fixes_per_shift",
            "stop_after_failed_verifications",
            "stop_after_empty_cycles",
            "score_threshold",
            "test_incentive_cycle",
            "backend_forcing_cycle",
            "category_balancing_cycle",
        }
        assert set(nightshift.DEFAULT_CONFIG.keys()) == expected

    def test_shift_log_template_has_placeholders(self):
        assert "{today}" in nightshift.SHIFT_LOG_TEMPLATE
        assert "{branch}" in nightshift.SHIFT_LOG_TEMPLATE
        assert "{base_branch}" in nightshift.SHIFT_LOG_TEMPLATE
        assert "{started}" in nightshift.SHIFT_LOG_TEMPLATE

    def test_safe_artifact_dirs(self):
        assert "__pycache__" in nightshift.SAFE_ARTIFACT_DIRS

    def test_safe_artifact_globs(self):
        assert "*.pyc" in nightshift.SAFE_ARTIFACT_GLOBS


# --- Error Class -------------------------------------------------------------


class TestNightshiftError:
    def test_is_runtime_error(self):
        assert issubclass(nightshift.NightshiftError, RuntimeError)

    def test_message_preserved(self):
        err = nightshift.NightshiftError("test message")
        assert str(err) == "test message"


# --- Utility Functions -------------------------------------------------------


class TestNowLocal:
    def test_returns_aware_datetime(self):
        result = nightshift.now_local()
        assert result.tzinfo is not None

    def test_is_recent(self):
        import datetime as dt

        result = nightshift.now_local()
        now = dt.datetime.now().astimezone()
        assert abs((now - result).total_seconds()) < 2


class TestPrintStatus:
    def test_prints_to_stdout(self, capsys):
        nightshift.print_status("hello")
        assert capsys.readouterr().out == "hello\n"


# --- run_command -------------------------------------------------------------


class TestRunCommand:
    def test_captures_output(self, tmp_path: Path) -> None:
        exit_code, output = nightshift.run_command(
            ["python3", "-c", "print('hello')"],
            cwd=tmp_path,
        )
        assert exit_code == 0
        assert "hello" in output

    def test_returns_exit_code(self, tmp_path: Path) -> None:
        exit_code, _ = nightshift.run_command(
            ["python3", "-c", "raise SystemExit(42)"],
            cwd=tmp_path,
        )
        assert exit_code == 42

    def test_writes_to_log_file(self, tmp_path: Path) -> None:
        log = tmp_path / "test.log"
        nightshift.run_command(
            ["python3", "-c", "print('logged')"],
            cwd=tmp_path,
            log_path=log,
        )
        assert "logged" in log.read_text()

    def test_timeout_kills_hung_process(self, tmp_path: Path) -> None:
        exit_code, output = nightshift.run_command(
            ["python3", "-c", "import time; time.sleep(60)"],
            cwd=tmp_path,
            timeout_seconds=2,
        )
        assert "timeout" in output.lower()
        assert exit_code != 0

    def test_timeout_captures_partial_output(self, tmp_path: Path) -> None:
        script = "import sys, time; print('before', flush=True); time.sleep(60)"
        _, output = nightshift.run_command(
            ["python3", "-c", script],
            cwd=tmp_path,
            timeout_seconds=2,
        )
        assert "before" in output
        assert "timeout" in output.lower()

    def test_no_timeout_completes_normally(self, tmp_path: Path) -> None:
        exit_code, output = nightshift.run_command(
            ["python3", "-c", "print('fast')"],
            cwd=tmp_path,
            timeout_seconds=30,
        )
        assert exit_code == 0
        assert "fast" in output
        assert "timeout" not in output.lower()


# --- JSON Utilities ----------------------------------------------------------


class TestLoadJson:
    def test_loads_valid_json(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"key": "value"}')
        assert nightshift.load_json(f) == {"key": "value"}

    def test_raises_on_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json")
        with pytest.raises(json.JSONDecodeError):
            nightshift.load_json(f)


class TestWriteJson:
    def test_writes_json_file(self, tmp_path):
        f = tmp_path / "out.json"
        nightshift.write_json(f, {"a": 1})
        loaded = json.loads(f.read_text())
        assert loaded == {"a": 1}

    def test_creates_parent_dirs(self, tmp_path):
        f = tmp_path / "nested" / "deep" / "out.json"
        nightshift.write_json(f, {"b": 2})
        assert f.exists()
        assert json.loads(f.read_text()) == {"b": 2}

    def test_output_is_sorted_and_indented(self, tmp_path):
        f = tmp_path / "out.json"
        nightshift.write_json(f, {"z": 1, "a": 2})
        text = f.read_text()
        assert text.startswith("{\n")
        assert '"a"' in text
        assert text.index('"a"') < text.index('"z"')

    def test_output_ends_with_newline(self, tmp_path):
        f = tmp_path / "out.json"
        nightshift.write_json(f, {})
        assert f.read_text().endswith("\n")


# --- extract_json ------------------------------------------------------------


class TestExtractJson:
    def test_plain_json(self):
        assert nightshift.extract_json('{"a": 1}') == {"a": 1}

    def test_fenced_json(self):
        text = '```json\n{"a": 1}\n```'
        assert nightshift.extract_json(text) == {"a": 1}

    def test_fenced_without_language(self):
        text = '```\n{"b": 2}\n```'
        assert nightshift.extract_json(text) == {"b": 2}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result: {"c": 3}'
        assert nightshift.extract_json(text) == {"c": 3}

    def test_empty_string(self):
        assert nightshift.extract_json("") is None

    def test_no_json(self):
        assert nightshift.extract_json("no json here") is None

    def test_array_not_returned(self):
        assert nightshift.extract_json("[1, 2, 3]") is None

    def test_nested_json(self):
        text = '{"fixes": [{"title": "a"}], "status": "ok"}'
        result = nightshift.extract_json(text)
        assert result["status"] == "ok"
        assert len(result["fixes"]) == 1

    def test_json_with_trailing_whitespace(self):
        assert nightshift.extract_json('{"x": 1}   \n') == {"x": 1}

    def test_json_preceded_by_garbage(self):
        text = 'some output\nmore output\n{"result": true}'
        assert nightshift.extract_json(text) == {"result": True}


# --- Config ------------------------------------------------------------------


class TestMergeConfig:
    def test_returns_defaults_when_no_config_file(self, tmp_path):
        config = nightshift.merge_config(tmp_path)
        assert config["hours"] == 8
        assert config["agent"] is None
        assert config["max_fixes_per_cycle"] == 3

    def test_overrides_from_file(self, tmp_path):
        (tmp_path / ".nightshift.json").write_text(
            json.dumps(
                {
                    "agent": "claude",
                    "hours": 10,
                }
            )
        )
        config = nightshift.merge_config(tmp_path)
        assert config["agent"] == "claude"
        assert config["hours"] == 10
        assert config["max_fixes_per_cycle"] == 3  # not overridden

    def test_does_not_mutate_default(self, tmp_path):
        (tmp_path / ".nightshift.json").write_text(json.dumps({"hours": 99}))
        nightshift.merge_config(tmp_path)
        assert nightshift.DEFAULT_CONFIG["hours"] == 8

    def test_raises_on_non_object(self, tmp_path):
        (tmp_path / ".nightshift.json").write_text('"not an object"')
        with pytest.raises(nightshift.NightshiftError, match="must contain a JSON object"):
            nightshift.merge_config(tmp_path)

    def test_blocked_paths_extends_defaults(self, tmp_path):
        (tmp_path / ".nightshift.json").write_text(json.dumps({"blocked_paths": ["my/custom/"]}))
        config = nightshift.merge_config(tmp_path)
        defaults = nightshift.DEFAULT_CONFIG["blocked_paths"]
        for dp in defaults:
            assert dp in config["blocked_paths"], f"default '{dp}' was dropped"
        assert "my/custom/" in config["blocked_paths"]

    def test_blocked_globs_extends_defaults(self, tmp_path):
        (tmp_path / ".nightshift.json").write_text(json.dumps({"blocked_globs": ["*.secret"]}))
        config = nightshift.merge_config(tmp_path)
        defaults = nightshift.DEFAULT_CONFIG["blocked_globs"]
        for dg in defaults:
            assert dg in config["blocked_globs"], f"default '{dg}' was dropped"
        assert "*.secret" in config["blocked_globs"]

    def test_list_merge_deduplicates(self, tmp_path):
        (tmp_path / ".nightshift.json").write_text(json.dumps({"blocked_paths": [".github/", "my/path/"]}))
        config = nightshift.merge_config(tmp_path)
        assert config["blocked_paths"].count(".github/") == 1
        assert "my/path/" in config["blocked_paths"]

    def test_scalar_fields_still_override(self, tmp_path):
        (tmp_path / ".nightshift.json").write_text(json.dumps({"hours": 12, "blocked_paths": ["extra/"]}))
        config = nightshift.merge_config(tmp_path)
        assert config["hours"] == 12
        assert "extra/" in config["blocked_paths"]
        assert ".github/" in config["blocked_paths"]

    def test_does_not_mutate_default_lists(self, tmp_path):
        original = list(nightshift.DEFAULT_CONFIG["blocked_paths"])
        (tmp_path / ".nightshift.json").write_text(json.dumps({"blocked_paths": ["injected/"]}))
        nightshift.merge_config(tmp_path)
        assert nightshift.DEFAULT_CONFIG["blocked_paths"] == original


class TestInferPackageManager:
    def test_bun(self, tmp_path):
        (tmp_path / "bun.lockb").touch()
        assert nightshift.infer_package_manager(tmp_path) == "bun"

    def test_pnpm(self, tmp_path):
        (tmp_path / "pnpm-lock.yaml").touch()
        assert nightshift.infer_package_manager(tmp_path) == "pnpm"

    def test_yarn(self, tmp_path):
        (tmp_path / "yarn.lock").touch()
        assert nightshift.infer_package_manager(tmp_path) == "yarn"

    def test_npm_lockfile(self, tmp_path):
        (tmp_path / "package-lock.json").touch()
        assert nightshift.infer_package_manager(tmp_path) == "npm"

    def test_npm_fallback(self, tmp_path):
        (tmp_path / "package.json").touch()
        assert nightshift.infer_package_manager(tmp_path) == "npm"

    def test_none(self, tmp_path):
        assert nightshift.infer_package_manager(tmp_path) is None

    def test_priority_bun_over_npm(self, tmp_path):
        (tmp_path / "bun.lockb").touch()
        (tmp_path / "package-lock.json").touch()
        assert nightshift.infer_package_manager(tmp_path) == "bun"


class TestInferInstallCommand:
    def test_no_package_json(self, tmp_path):
        assert nightshift.infer_install_command(tmp_path) is None

    def test_npm(self, tmp_path):
        (tmp_path / "package.json").touch()
        result = nightshift.infer_install_command(tmp_path)
        assert result == ["npm", "install", "--package-lock=false"]

    def test_npm_with_lockfile_uses_ci(self, tmp_path):
        (tmp_path / "package.json").touch()
        (tmp_path / "package-lock.json").touch()
        result = nightshift.infer_install_command(tmp_path)
        assert result == ["npm", "ci"]

    def test_bun(self, tmp_path):
        (tmp_path / "package.json").touch()
        (tmp_path / "bun.lockb").touch()
        result = nightshift.infer_install_command(tmp_path)
        assert result == ["bun", "install", "--frozen-lockfile"]

    def test_pnpm(self, tmp_path):
        (tmp_path / "package.json").touch()
        (tmp_path / "pnpm-lock.yaml").touch()
        result = nightshift.infer_install_command(tmp_path)
        assert result == ["pnpm", "install", "--frozen-lockfile"]

    def test_yarn(self, tmp_path):
        (tmp_path / "package.json").touch()
        (tmp_path / "yarn.lock").touch()
        result = nightshift.infer_install_command(tmp_path)
        assert result == ["yarn", "install", "--frozen-lockfile"]


class TestInferVerifyCommand:
    def test_explicit_config(self, tmp_path):
        config = {"verify_command": "make test"}
        assert nightshift.infer_verify_command(tmp_path, config) == "make test"

    def test_package_json_test_ci(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test:ci": "jest --ci", "test": "jest"}}))
        result = nightshift.infer_verify_command(tmp_path, {"verify_command": None})
        assert result == "npm run test:ci"

    def test_package_json_test(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "jest"}}))
        result = nightshift.infer_verify_command(tmp_path, {"verify_command": None})
        assert result == "npm test"

    def test_cargo(self, tmp_path):
        (tmp_path / "Cargo.toml").touch()
        result = nightshift.infer_verify_command(tmp_path, {"verify_command": None})
        assert result == "cargo test"

    def test_go(self, tmp_path):
        (tmp_path / "go.mod").touch()
        result = nightshift.infer_verify_command(tmp_path, {"verify_command": None})
        assert result == "go test ./..."

    def test_python(self, tmp_path):
        (tmp_path / "pyproject.toml").touch()
        result = nightshift.infer_verify_command(tmp_path, {"verify_command": None})
        assert result == "python3 -m pytest"

    def test_pytest_ini(self, tmp_path):
        (tmp_path / "pytest.ini").touch()
        result = nightshift.infer_verify_command(tmp_path, {"verify_command": None})
        assert result == "python3 -m pytest"

    def test_none(self, tmp_path):
        result = nightshift.infer_verify_command(tmp_path, {"verify_command": None})
        assert result is None

    def test_bad_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text("not json")
        result = nightshift.infer_verify_command(tmp_path, {"verify_command": None})
        assert result is None

    def test_package_json_uses_detected_manager(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "vitest"}}))
        (tmp_path / "bun.lockb").touch()
        result = nightshift.infer_verify_command(tmp_path, {"verify_command": None})
        assert result == "bun test"


# --- Agent Resolution --------------------------------------------------------


class TestResolveAgent:
    def test_cli_flag_wins(self):
        config = {"agent": "claude"}
        assert nightshift.resolve_agent(config, "codex") == "codex"

    def test_config_used_when_no_cli(self):
        config = {"agent": "claude"}
        assert nightshift.resolve_agent(config, None) == "claude"

    def test_error_when_no_agent_and_no_tty(self):
        config = {"agent": None}
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            with pytest.raises(nightshift.NightshiftError, match="No agent configured"):
                nightshift.resolve_agent(config, None)

    def test_interactive_prompt(self):
        config = {"agent": None}
        with patch("sys.stdin") as mock_stdin, patch("builtins.input", return_value="1"):
            mock_stdin.isatty.return_value = True
            assert nightshift.resolve_agent(config, None) == "codex"

    def test_interactive_prompt_claude(self):
        config = {"agent": None}
        with patch("sys.stdin") as mock_stdin, patch("builtins.input", return_value="2"):
            mock_stdin.isatty.return_value = True
            assert nightshift.resolve_agent(config, None) == "claude"


class TestPromptForAgent:
    def test_choice_1_returns_codex(self):
        with patch("builtins.input", return_value="1"):
            assert nightshift.prompt_for_agent() == "codex"

    def test_choice_2_returns_claude(self):
        with patch("builtins.input", return_value="2"):
            assert nightshift.prompt_for_agent() == "claude"

    def test_eof_raises(self):
        with (
            patch("builtins.input", side_effect=EOFError),
            pytest.raises(nightshift.NightshiftError, match="No agent selected"),
        ):
            nightshift.prompt_for_agent()

    def test_keyboard_interrupt_raises(self):
        with (
            patch("builtins.input", side_effect=KeyboardInterrupt),
            pytest.raises(nightshift.NightshiftError, match="No agent selected"),
        ):
            nightshift.prompt_for_agent()

    def test_retries_on_invalid_input(self):
        with patch("builtins.input", side_effect=["x", "0", "3", "1"]):
            assert nightshift.prompt_for_agent() == "codex"


# --- State Management --------------------------------------------------------


class TestReadState:
    def test_fresh_state(self, tmp_path):
        state_path = tmp_path / "state.json"
        state = nightshift.read_state(
            state_path,
            today="2026-04-03",
            branch="nightshift/2026-04-03",
            agent="codex",
            verify_command="npm test",
        )
        assert state["version"] == 1
        assert state["date"] == "2026-04-03"
        assert state["branch"] == "nightshift/2026-04-03"
        assert state["agent"] == "codex"
        assert state["verify_command"] == "npm test"
        assert state["counters"]["fixes"] == 0
        assert state["counters"]["empty_cycles"] == 0
        assert state["halt_reason"] is None
        assert state["log_only_mode"] is False
        assert state["cycles"] == []

    def test_loads_existing(self, tmp_path):
        state_path = tmp_path / "state.json"
        existing = {
            "version": 1,
            "date": "2026-04-03",
            "branch": "nightshift/2026-04-03",
            "agent": "codex",
            "baseline": {"status": "passed", "command": None, "message": ""},
            "counters": {"fixes": 5},
            "cycles": [],
        }
        state_path.write_text(json.dumps(existing))
        state = nightshift.read_state(
            state_path,
            today="2026-04-03",
            branch="x",
            agent="codex",
            verify_command=None,
        )
        assert state["counters"]["fixes"] == 5

    def test_rejects_wrong_version(self, tmp_path):
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({"version": 999}))
        with pytest.raises(nightshift.NightshiftError, match="Unsupported state version"):
            nightshift.read_state(state_path, today="x", branch="x", agent="x", verify_command=None)


class TestTopPath:
    def test_basic(self):
        assert nightshift.top_path(["src/a.ts", "src/b.ts", "lib/c.ts"]) == "src"

    def test_empty(self):
        assert nightshift.top_path([]) == "(none)"

    def test_single_file(self):
        assert nightshift.top_path(["README.md"]) == "README.md"

    def test_tie_breaks_alphabetically(self):
        result = nightshift.top_path(["b/x.ts", "a/y.ts"])
        assert result == "a"

    def test_ignores_empty_strings(self):
        assert nightshift.top_path(["", "src/a.ts", ""]) == "src"


class TestAppendCycleState:
    def _base_state(self):
        return {
            "counters": {
                "fixes": 0,
                "issues_logged": 0,
                "files_touched": 0,
                "low_impact_fixes": 0,
                "failed_verifications": 0,
                "empty_cycles": 0,
                "agent_failures": 0,
                "tests_written": 0,
            },
            "category_counts": {},
            "recent_cycle_paths": [],
            "cycles": [],
            "log_only_mode": False,
        }

    def test_counts_fixes(self):
        state = self._base_state()
        cycle_result = {
            "fixes": [
                {"title": "a", "category": "Security", "impact": "high", "files": ["x.ts"]},
            ],
            "logged_issues": [],
            "status": "completed",
        }
        verification = {
            "commits": ["abc1234"],
            "files_touched": ["x.ts"],
            "dominant_path": "src",
        }
        nightshift.append_cycle_state(
            state=state,
            cycle_number=1,
            cycle_result=cycle_result,
            verification=verification,
        )
        assert state["counters"]["fixes"] == 1
        assert state["counters"]["files_touched"] == 1
        assert state["category_counts"] == {"Security": 1}
        assert len(state["cycles"]) == 1

    def test_counts_low_impact(self):
        state = self._base_state()
        cycle_result = {
            "fixes": [
                {"title": "a", "category": "Polish", "impact": "low", "files": ["a.ts"]},
                {"title": "b", "category": "A11y", "impact": "low", "files": ["b.ts"]},
            ],
            "logged_issues": [],
            "status": "completed",
        }
        verification = {"commits": ["a", "b"], "files_touched": ["a.ts", "b.ts"], "dominant_path": "src"}
        nightshift.append_cycle_state(
            state=state,
            cycle_number=1,
            cycle_result=cycle_result,
            verification=verification,
        )
        assert state["counters"]["low_impact_fixes"] == 2

    def test_empty_cycle_increments(self):
        state = self._base_state()
        cycle_result = {"fixes": [], "logged_issues": [], "status": "no_changes"}
        verification = {"commits": [], "files_touched": [], "dominant_path": "(none)"}
        nightshift.append_cycle_state(
            state=state,
            cycle_number=1,
            cycle_result=cycle_result,
            verification=verification,
        )
        assert state["counters"]["empty_cycles"] == 1

    def test_non_empty_resets_empty_counter(self):
        state = self._base_state()
        state["counters"]["empty_cycles"] = 3
        cycle_result = {
            "fixes": [{"title": "x", "category": "Security", "impact": "high", "files": ["x"]}],
            "logged_issues": [],
            "status": "completed",
        }
        verification = {"commits": ["abc"], "files_touched": ["x"], "dominant_path": "src"}
        nightshift.append_cycle_state(
            state=state,
            cycle_number=1,
            cycle_result=cycle_result,
            verification=verification,
        )
        assert state["counters"]["empty_cycles"] == 0

    def test_recent_paths_capped_at_four(self):
        state = self._base_state()
        state["recent_cycle_paths"] = ["a", "b", "c", "d"]
        cycle_result = {"fixes": [], "logged_issues": [], "status": "no_changes"}
        verification = {"commits": [], "files_touched": [], "dominant_path": "e"}
        nightshift.append_cycle_state(
            state=state,
            cycle_number=5,
            cycle_result=cycle_result,
            verification=verification,
        )
        assert state["recent_cycle_paths"] == ["b", "c", "d", "e"]

    def test_null_cycle_result(self):
        state = self._base_state()
        verification = {"commits": ["abc"], "files_touched": ["x.ts"], "dominant_path": "src"}
        nightshift.append_cycle_state(
            state=state,
            cycle_number=1,
            cycle_result=None,
            verification=verification,
        )
        # Infers fix count from commits when no structured result
        assert state["counters"]["fixes"] == 1


# --- Blocked File Detection --------------------------------------------------


class TestBlockedFile:
    def _config(self):
        return {
            "blocked_paths": [".github/", "deploy/", "infra/"],
            "blocked_globs": ["*.lock", "package-lock.json"],
        }

    def test_blocked_path(self):
        result = nightshift.blocked_file(".github/workflows/ci.yml", self._config())
        assert result is not None
        assert "blocked path" in result

    def test_blocked_glob(self):
        result = nightshift.blocked_file("yarn.lock", self._config())
        assert result is not None
        assert "blocked glob" in result

    def test_package_lock(self):
        result = nightshift.blocked_file("package-lock.json", self._config())
        assert result is not None

    def test_allowed_file(self):
        assert nightshift.blocked_file("src/index.ts", self._config()) is None

    def test_empty_string(self):
        assert nightshift.blocked_file("", self._config()) is None

    def test_whitespace_only(self):
        assert nightshift.blocked_file("   ", self._config()) is None

    def test_nested_blocked_path(self):
        result = nightshift.blocked_file("deploy/k8s/app.yaml", self._config())
        assert result is not None


# --- Recent Hot Files --------------------------------------------------------


class TestRecentHotFiles:
    def test_returns_list(self, tmp_path):
        # Use the actual repo -- it has git history
        repo = Path(__file__).resolve().parent.parent
        result = nightshift.recent_hot_files(repo)
        assert isinstance(result, list)

    def test_max_twenty(self, tmp_path):
        repo = Path(__file__).resolve().parent.parent
        result = nightshift.recent_hot_files(repo)
        assert len(result) <= 20

    def test_handles_non_git_dir(self, tmp_path):
        result = nightshift.recent_hot_files(tmp_path)
        assert result == []


class TestHighSignalFocusPaths:
    def test_prefers_existing_high_signal_paths(self, tmp_path: Path) -> None:
        (tmp_path / "src" / "lib" / "auth").mkdir(parents=True)
        (tmp_path / "src" / "app" / "api").mkdir(parents=True)
        (tmp_path / "src" / "lib" / "http.ts").write_text("", encoding="utf-8")

        result = nightshift.high_signal_focus_paths(tmp_path, [])
        assert result[:3] == ["src/lib/auth", "src/lib/http.ts", "src/app/api"]

    def test_skips_hot_prefixes_when_possible(self, tmp_path: Path) -> None:
        (tmp_path / "src" / "lib" / "auth").mkdir(parents=True)
        (tmp_path / "src" / "app" / "api").mkdir(parents=True)

        result = nightshift.high_signal_focus_paths(tmp_path, ["src/lib/auth"])
        assert "src/lib/auth" not in result
        assert "src/app/api" in result


# --- Shift Log ---------------------------------------------------------------


class TestEnsureShiftLog:
    def test_creates_file(self, tmp_path):
        log_path = tmp_path / "docs" / "Nightshift" / "2026-04-03.md"
        nightshift.ensure_shift_log(
            log_path,
            today="2026-04-03",
            branch="nightshift/2026-04-03",
            base_branch="main",
        )
        assert log_path.exists()
        content = log_path.read_text()
        assert "2026-04-03" in content
        assert "nightshift/2026-04-03" in content
        assert "main" in content

    def test_idempotent(self, tmp_path):
        log_path = tmp_path / "log.md"
        log_path.write_text("existing content")
        nightshift.ensure_shift_log(log_path, today="x", branch="x", base_branch="x")
        assert log_path.read_text() == "existing content"


class TestSyncShiftLog:
    def test_copies_file(self, tmp_path):
        worktree = tmp_path / "worktree"
        repo = tmp_path / "repo"
        src = worktree / "docs" / "Nightshift" / "log.md"
        src.parent.mkdir(parents=True)
        src.write_text("shift log content")

        nightshift.sync_shift_log(worktree, repo, "docs/Nightshift/log.md")

        target = repo / "docs" / "Nightshift" / "log.md"
        assert target.exists()
        assert target.read_text() == "shift log content"

    def test_no_source_does_nothing(self, tmp_path):
        worktree = tmp_path / "worktree"
        repo = tmp_path / "repo"
        nightshift.sync_shift_log(worktree, repo, "docs/Nightshift/log.md")
        assert not (repo / "docs" / "Nightshift" / "log.md").exists()


class TestValidateWorktree:
    def test_reports_missing_gitdir_from_git_file(self, tmp_path: Path) -> None:
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        missing = tmp_path / "missing-gitdir"
        (worktree / ".git").write_text(f"gitdir: {missing}\n", encoding="utf-8")

        with pytest.raises(nightshift.NightshiftError, match="missing gitdir"):
            nightshift.validate_worktree(worktree)


class TestValidateRepoCheckout:
    def test_accepts_primary_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
        (repo / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True)

        nightshift.validate_repo_checkout(repo)

    def test_accepts_linked_worktree_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        linked = tmp_path / "linked"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
        (repo / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "worktree", "add", str(linked), "-b", "feature/test"], cwd=repo, capture_output=True, check=True
        )

        nightshift.validate_repo_checkout(linked)

    def test_rejects_non_git_dir(self, tmp_path: Path) -> None:
        repo = tmp_path / "not-a-git"
        repo.mkdir()

        with pytest.raises(nightshift.NightshiftError, match="not a valid git checkout"):
            nightshift.validate_repo_checkout(repo)


class TestEnsureWorktree:
    def test_recreates_broken_existing_worktree(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
        (repo / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True)

        worktree = repo / "docs" / "Nightshift" / "worktree-2026-04-03"
        worktree.mkdir(parents=True)
        (worktree / ".git").write_text(f"gitdir: {tmp_path / 'broken-gitdir'}\n", encoding="utf-8")
        (worktree / "broken.txt").write_text("stale\n", encoding="utf-8")

        nightshift.ensure_worktree(repo, worktree, "nightshift/2026-04-03")

        status = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=worktree,
            capture_output=True,
            text=True,
            check=True,
        )
        assert status.stdout.strip() == "true"
        assert not (worktree / "broken.txt").exists()


# --- Command Construction ----------------------------------------------------


class TestCommandForAgent:
    def test_codex_command(self, tmp_path):
        schema = tmp_path / "schema.json"
        message = tmp_path / "msg.json"
        cmd = nightshift.command_for_agent(
            agent="codex",
            prompt="do stuff",
            cwd=tmp_path,
            schema_path=schema,
            message_path=message,
        )
        assert cmd[0] == "codex"
        assert "exec" in cmd
        assert "--json" in cmd
        assert "--output-schema" in cmd
        assert str(schema) in cmd
        assert "do stuff" in cmd

    def test_claude_command(self, tmp_path):
        cmd = nightshift.command_for_agent(
            agent="claude",
            prompt="do stuff",
            cwd=tmp_path,
            schema_path=tmp_path / "s.json",
            message_path=tmp_path / "m.json",
        )
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "do stuff" in cmd
        assert "--max-turns" in cmd
        assert "50" in cmd

    def test_unsupported_agent(self, tmp_path):
        with pytest.raises(nightshift.NightshiftError, match="Unsupported agent"):
            nightshift.command_for_agent(
                agent="gpt",
                prompt="x",
                cwd=tmp_path,
                schema_path=tmp_path / "s",
                message_path=tmp_path / "m",
            )


# --- State Summary -----------------------------------------------------------


class TestBuildStateSummary:
    def _base_state(self):
        return {
            "cycles": [],
            "category_counts": {},
            "counters": {"fixes": 0, "issues_logged": 0},
        }

    def test_empty_cycles_returns_empty_string(self):
        state = self._base_state()
        result = nightshift.build_state_summary(state)
        assert result == ""

    def test_single_cycle_with_security_fix(self):
        state = self._base_state()
        state["category_counts"] = {"Security": 1}
        state["counters"]["fixes"] = 1
        state["cycles"] = [
            {
                "cycle": 1,
                "status": "done",
                "fixes": [{"category": "Security", "files": ["src/api/auth.py"]}],
                "logged_issues": [],
                "verification": {
                    "files_touched": ["src/api/auth.py"],
                    "dominant_path": "src",
                    "commits": ["abc1234"],
                    "violations": [],
                    "verify_command": None,
                    "verify_status": "skipped",
                    "verify_exit_code": None,
                },
            }
        ]
        result = nightshift.build_state_summary(state)
        assert "1 Security" in result
        assert "src" in result

    def test_unexplored_categories_listed(self):
        state = self._base_state()
        state["category_counts"] = {"Security": 1, "Tests": 1}
        state["counters"]["fixes"] = 2
        state["cycles"] = [
            {
                "cycle": 1,
                "status": "done",
                "fixes": [],
                "logged_issues": [],
                "verification": {
                    "files_touched": [],
                    "dominant_path": "(none)",
                    "commits": [],
                    "violations": [],
                    "verify_command": None,
                    "verify_status": "skipped",
                    "verify_exit_code": None,
                },
            }
        ]
        result = nightshift.build_state_summary(state)
        assert "Error Handling" in result
        assert "A11y" in result
        assert "Code Quality" in result
        assert "Performance" in result
        assert "Polish" in result
        # Security and Tests are explored, should NOT be in unexplored
        assert "not yet explored" in result.lower()

    def test_multiple_categories_and_paths(self):
        state = self._base_state()
        state["category_counts"] = {"Security": 2, "Error Handling": 1}
        state["counters"] = {"fixes": 3, "issues_logged": 1}
        state["cycles"] = [
            {
                "cycle": 1,
                "status": "done",
                "fixes": [],
                "logged_issues": [],
                "verification": {
                    "files_touched": ["src/api/auth.py", "lib/utils.js"],
                    "dominant_path": "src",
                    "commits": ["a1"],
                    "violations": [],
                    "verify_command": None,
                    "verify_status": "skipped",
                    "verify_exit_code": None,
                },
            },
            {
                "cycle": 2,
                "status": "done",
                "fixes": [],
                "logged_issues": [],
                "verification": {
                    "files_touched": ["server/routes.py"],
                    "dominant_path": "server",
                    "commits": ["b2"],
                    "violations": [],
                    "verify_command": None,
                    "verify_status": "skipped",
                    "verify_exit_code": None,
                },
            },
        ]
        result = nightshift.build_state_summary(state)
        assert "2 Security" in result
        assert "1 Error Handling" in result
        assert "lib" in result
        assert "server" in result
        assert "src" in result
        assert "3 fix(es) committed" in result
        assert "1 issue(s) logged" in result

    def test_no_running_totals_when_zero(self):
        state = self._base_state()
        state["category_counts"] = {"Polish": 1}
        state["cycles"] = [
            {
                "cycle": 1,
                "status": "done",
                "fixes": [],
                "logged_issues": [],
                "verification": {
                    "files_touched": [],
                    "dominant_path": "(none)",
                    "commits": [],
                    "violations": [],
                    "verify_command": None,
                    "verify_status": "skipped",
                    "verify_exit_code": None,
                },
            }
        ]
        result = nightshift.build_state_summary(state)
        assert "Running totals" not in result

    def test_cycle_without_verification_key(self):
        state = self._base_state()
        state["category_counts"] = {"Security": 1}
        state["counters"]["fixes"] = 1
        state["cycles"] = [
            {
                "cycle": 1,
                "status": "done",
                "fixes": [],
                "logged_issues": [],
            }
        ]
        result = nightshift.build_state_summary(state)
        assert "1 Security" in result
        # No paths section since verification is absent
        assert "Paths already visited" not in result

    def test_all_categories_explored_no_unexplored_line(self):
        state = self._base_state()
        state["category_counts"] = {
            "Security": 1,
            "Error Handling": 1,
            "Tests": 1,
            "A11y": 1,
            "Code Quality": 1,
            "Performance": 1,
            "Polish": 1,
        }
        state["counters"]["fixes"] = 7
        state["cycles"] = [
            {
                "cycle": 1,
                "status": "done",
                "fixes": [],
                "logged_issues": [],
                "verification": {
                    "files_touched": [],
                    "dominant_path": "(none)",
                    "commits": [],
                    "violations": [],
                    "verify_command": None,
                    "verify_status": "skipped",
                    "verify_exit_code": None,
                },
            }
        ]
        result = nightshift.build_state_summary(state)
        assert "not yet explored" not in result.lower()


# --- Prompt Building (with state injection) ----------------------------------


class TestBuildPromptStateInjection:
    """Tests that build_prompt includes state summary when cycles exist."""

    def _base_args(self):
        return dict(
            cycle=2,
            is_final=False,
            config={
                "agent": "codex",
                "max_fixes_per_cycle": 3,
                "max_files_per_fix": 5,
                "max_files_per_cycle": 12,
                "max_low_impact_fixes_per_shift": 4,
            },
            state={
                "counters": {"low_impact_fixes": 0, "fixes": 1, "issues_logged": 0, "tests_written": 0},
                "log_only_mode": False,
                "recent_cycle_paths": ["src"],
                "cycles": [
                    {
                        "cycle": 1,
                        "status": "done",
                        "fixes": [{"category": "Security", "files": ["src/auth.py"]}],
                        "logged_issues": [],
                        "verification": {
                            "files_touched": ["src/auth.py"],
                            "dominant_path": "src",
                            "commits": ["abc1234"],
                            "violations": [],
                            "verify_command": None,
                            "verify_status": "skipped",
                            "verify_exit_code": None,
                        },
                    }
                ],
                "category_counts": {"Security": 1},
            },
            shift_log_relative="docs/Nightshift/2026-04-03.md",
            blocked_summary="- `.github/`",
            hot_files=[],
            prior_path_bias=["src"],
            focus_hints=[],
            test_mode=False,
        )

    def test_prompt_includes_state_summary(self):
        prompt = nightshift.build_prompt(**self._base_args())
        assert "Prior cycle intelligence" in prompt
        assert "1 Security" in prompt

    def test_prompt_includes_unexplored_categories(self):
        prompt = nightshift.build_prompt(**self._base_args())
        assert "Error Handling" in prompt
        assert "Tests" in prompt

    def test_no_state_block_on_first_cycle(self):
        args = self._base_args()
        args["cycle"] = 1
        args["state"]["cycles"] = []
        args["state"]["category_counts"] = {}
        args["state"]["counters"]["fixes"] = 0
        prompt = nightshift.build_prompt(**args)
        assert "Prior cycle intelligence" not in prompt


# --- Prompt Building ---------------------------------------------------------


class TestBuildPrompt:
    def _base_args(self):
        return dict(
            cycle=1,
            is_final=False,
            config={
                "agent": "codex",
                "max_fixes_per_cycle": 3,
                "max_files_per_fix": 5,
                "max_files_per_cycle": 12,
                "max_low_impact_fixes_per_shift": 4,
            },
            state={
                "counters": {"low_impact_fixes": 0, "fixes": 0, "issues_logged": 0, "tests_written": 0},
                "log_only_mode": False,
                "recent_cycle_paths": [],
                "cycles": [],
                "category_counts": {},
            },
            shift_log_relative="docs/Nightshift/2026-04-03.md",
            blocked_summary="- `.github/`\n- `*.lock`",
            hot_files=["src/hot.ts"],
            prior_path_bias=[],
            focus_hints=["src/lib/auth", "src/lib/http.ts"],
            test_mode=False,
        )

    def test_contains_cycle_number(self):
        prompt = nightshift.build_prompt(**self._base_args())
        assert "Cycle: 1" in prompt

    def test_contains_shift_log_path(self):
        prompt = nightshift.build_prompt(**self._base_args())
        assert "docs/Nightshift/2026-04-03.md" in prompt

    def test_contains_limits(self):
        prompt = nightshift.build_prompt(**self._base_args())
        assert "3 fixes" in prompt
        assert "5 files per fix" in prompt
        assert "12 total files" in prompt

    def test_contains_blocked_paths(self):
        prompt = nightshift.build_prompt(**self._base_args())
        assert ".github/" in prompt
        assert "*.lock" in prompt

    def test_contains_hot_files(self):
        prompt = nightshift.build_prompt(**self._base_args())
        assert "src/hot.ts" in prompt

    def test_final_cycle_instructions(self):
        args = self._base_args()
        args["is_final"] = True
        prompt = nightshift.build_prompt(**args)
        assert "Final cycle" in prompt or "wrap up" in prompt.lower()

    def test_test_mode_instructions(self):
        args = self._base_args()
        args["test_mode"] = True
        prompt = nightshift.build_prompt(**args)
        assert "validation run" in prompt.lower() or "finish quickly" in prompt.lower()

    def test_log_only_mode(self):
        args = self._base_args()
        args["state"]["log_only_mode"] = True
        prompt = nightshift.build_prompt(**args)
        assert "Log-only mode: yes" in prompt

    def test_low_impact_remaining_calculated(self):
        args = self._base_args()
        args["state"]["counters"]["low_impact_fixes"] = 2
        prompt = nightshift.build_prompt(**args)
        assert "2" in prompt  # 4 - 2 = 2 remaining

    def test_warns_about_package_manager_test_commands(self):
        prompt = nightshift.build_prompt(**self._base_args())
        assert "Avoid package-manager test commands like `npm test`" in prompt

    def test_includes_high_signal_focus_hints(self):
        prompt = nightshift.build_prompt(**self._base_args())
        assert "Prefer high-signal, low-blast-radius helpers" in prompt
        assert "`src/lib/auth`" in prompt


# --- Parse Cycle Result ------------------------------------------------------


class TestParseCycleResult:
    def test_codex_from_message_file(self, tmp_path):
        msg = tmp_path / "msg.json"
        msg.write_text('{"status": "completed", "fixes": []}')
        result = nightshift.parse_cycle_result(agent="codex", message_path=msg, raw_output="garbage")
        assert result is not None
        assert result["status"] == "completed"
        assert result["fixes"] == []
        assert result["logged_issues"] == []

    def test_codex_fallback_to_output(self, tmp_path):
        msg = tmp_path / "msg.json"  # doesn't exist
        result = nightshift.parse_cycle_result(agent="codex", message_path=msg, raw_output='{"status": "ok"}')
        assert result is not None
        assert result["status"] == "ok"

    def test_claude_from_output(self, tmp_path):
        msg = tmp_path / "msg.json"
        result = nightshift.parse_cycle_result(
            agent="claude", message_path=msg, raw_output='blah blah\n{"status": "completed"}'
        )
        assert result is not None
        assert result["status"] == "completed"

    def test_no_json_anywhere(self, tmp_path):
        result = nightshift.parse_cycle_result(
            agent="claude",
            message_path=tmp_path / "nope.json",
            raw_output="no json here",
        )
        assert result is None

    def test_preserves_schema_fields_used_for_verification(self, tmp_path: Path) -> None:
        msg = tmp_path / "msg.json"
        msg.write_text(
            json.dumps(
                {
                    "cycle": 1,
                    "status": "completed",
                    "fixes": [],
                    "logged_issues": [],
                    "categories": ["Error Handling"],
                    "files_touched": ["src/lib/auth/session.ts"],
                    "tests_run": ["npm run lint"],
                    "notes": "done",
                }
            ),
            encoding="utf-8",
        )

        result = nightshift.parse_cycle_result(agent="codex", message_path=msg, raw_output="")
        assert result is not None
        assert result["cycle"] == 1
        assert result["tests_run"] == ["npm run lint"]
        assert result["notes"] == "done"


class TestForbiddenCycleCommands:
    def test_detects_repo_wide_npm_commands_from_codex_jsonl(self) -> None:
        raw_output = "\n".join(
            [
                json.dumps(
                    {
                        "type": "item.started",
                        "item": {
                            "type": "command_execution",
                            "command": "/bin/zsh -lc 'npm run lint'",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "/bin/zsh -lc 'npm run build'",
                        },
                    }
                ),
            ]
        )

        result = nightshift.forbidden_cycle_commands(raw_output)
        assert result == ["npm run lint", "npm run build"]

    def test_ignores_non_forbidden_and_duplicates(self) -> None:
        raw_output = "\n".join(
            [
                json.dumps(
                    {
                        "type": "item.started",
                        "item": {
                            "type": "command_execution",
                            "command": "/bin/zsh -lc 'npm run lint'",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "/bin/zsh -lc 'npm run lint'",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "item.started",
                        "item": {
                            "type": "command_execution",
                            "command": "/bin/zsh -lc 'npm test -- src/lib/auth/parse-social-url.test.ts'",
                        },
                    }
                ),
            ]
        )

        result = nightshift.forbidden_cycle_commands(raw_output)
        assert result == ["npm run lint"]

    def test_detects_bash_c_wrapper(self) -> None:
        raw_output = json.dumps(
            {
                "type": "item.started",
                "item": {
                    "type": "command_execution",
                    "command": 'bash -c "npm run build"',
                },
            }
        )
        result = nightshift.forbidden_cycle_commands(raw_output)
        assert result == ["npm run build"]

    def test_detects_sh_c_wrapper(self) -> None:
        raw_output = json.dumps(
            {
                "type": "item.started",
                "item": {
                    "type": "command_execution",
                    "command": "sh -c 'npm test'",
                },
            }
        )
        result = nightshift.forbidden_cycle_commands(raw_output)
        assert result == ["npm test"]


class TestForbiddenReportedCommands:
    def test_detects_forbidden_commands_from_structured_tests_run(self) -> None:
        result = nightshift.forbidden_reported_commands(
            {
                "status": "completed",
                "fixes": [],
                "logged_issues": [],
                "tests_run": [
                    "npm run lint",
                    "npm run test (failed in sandbox: tsx IPC pipe EPERM)",
                    "npx eslint src/lib/auth/session.ts",
                ],
            }
        )
        assert result == ["npm run lint", "npm run test"]


class TestExpectedCycleCommits:
    def test_fixes_require_one_commit_each(self) -> None:
        result = nightshift.expected_cycle_commits(
            {"status": "completed", "fixes": [{"title": "a"}, {"title": "b"}], "logged_issues": []}
        )
        assert result == (2, 3)

    def test_logged_issues_batch_into_one_commit(self) -> None:
        result = nightshift.expected_cycle_commits(
            {"status": "log_only", "fixes": [], "logged_issues": [{"title": "a"}, {"title": "b"}]}
        )
        assert result == (1, 2)

    def test_fixes_plus_logged_issues_add_one_extra_commit(self) -> None:
        result = nightshift.expected_cycle_commits(
            {
                "status": "completed",
                "fixes": [{"title": "a"}],
                "logged_issues": [{"title": "issue"}],
            }
        )
        assert result == (2, 3)

    def test_missing_result_returns_none(self) -> None:
        assert nightshift.expected_cycle_commits(None) is None

    def test_no_fixes_no_issues_returns_zero_range(self) -> None:
        result = nightshift.expected_cycle_commits({"status": "completed", "fixes": [], "logged_issues": []})
        assert result == (0, 1)


# --- CLI Parser --------------------------------------------------------------


class TestBuildParser:
    def test_run_subcommand(self):
        parser = nightshift.build_parser()
        args = parser.parse_args(["run", "--agent", "codex", "--dry-run"])
        assert args.command == "run"
        assert args.agent == "codex"
        assert args.dry_run is True

    def test_test_subcommand(self):
        parser = nightshift.build_parser()
        args = parser.parse_args(["test", "--cycles", "2", "--cycle-minutes", "5"])
        assert args.command == "test"
        assert args.cycles == 2
        assert args.cycle_minutes == 5

    def test_summarize_subcommand(self):
        parser = nightshift.build_parser()
        args = parser.parse_args(["summarize", "--date", "2026-04-03"])
        assert args.command == "summarize"
        assert args.date == "2026-04-03"

    def test_verify_cycle_subcommand(self):
        parser = nightshift.build_parser()
        args = parser.parse_args(
            [
                "verify-cycle",
                "--worktree-dir",
                "/tmp/wt",
                "--pre-head",
                "abc123",
            ]
        )
        assert args.command == "verify-cycle"
        assert args.worktree_dir == "/tmp/wt"
        assert args.pre_head == "abc123"

    def test_agent_choices(self):
        parser = nightshift.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["run", "--agent", "gpt"])

    def test_run_positional_hours(self):
        parser = nightshift.build_parser()
        args = parser.parse_args(["run", "10"])
        assert args.hours == 10

    def test_run_positional_hours_and_minutes(self):
        parser = nightshift.build_parser()
        args = parser.parse_args(["run", "6", "45"])
        assert args.hours == 6
        assert args.cycle_minutes == 45


# --- Cleanup Safe Artifacts --------------------------------------------------


class TestCleanupSafeArtifacts:
    def test_removes_pycache(self, tmp_path):
        cache = tmp_path / "src" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "foo.pyc").touch()
        nightshift.cleanup_safe_artifacts(tmp_path)
        assert not cache.exists()

    def test_removes_pyc_files(self, tmp_path):
        pyc = tmp_path / "module.pyc"
        pyc.touch()
        nightshift.cleanup_safe_artifacts(tmp_path)
        assert not pyc.exists()

    def test_leaves_normal_files(self, tmp_path):
        normal = tmp_path / "src" / "app.py"
        normal.parent.mkdir()
        normal.touch()
        nightshift.cleanup_safe_artifacts(tmp_path)
        assert normal.exists()


# --- Diff Scorer -------------------------------------------------------------


class TestDiffLineScore:
    def test_security_pattern_scores_high(self) -> None:
        from nightshift.scoring import _diff_line_score

        diff = "+    sanitize_input(user_data)\n"
        assert _diff_line_score(diff) >= 7

    def test_error_handling_pattern(self) -> None:
        from nightshift.scoring import _diff_line_score

        diff = "+    try:\n+        do_thing()\n+    except ValueError:\n"
        assert _diff_line_score(diff) >= 5

    def test_no_patterns_scores_zero(self) -> None:
        from nightshift.scoring import _diff_line_score

        diff = "+    x = 1\n+    y = 2\n"
        assert _diff_line_score(diff) == 0

    def test_only_added_lines_scanned(self) -> None:
        from nightshift.scoring import _diff_line_score

        diff = "-    sanitize_input(user_data)\n x = 1\n"
        assert _diff_line_score(diff) == 0


class TestHasTestFiles:
    def test_python_test_file(self) -> None:
        from nightshift.scoring import _has_test_files

        assert _has_test_files(["src/main.py", "tests/test_main.py"])

    def test_js_spec_file(self) -> None:
        from nightshift.scoring import _has_test_files

        assert _has_test_files(["src/app.ts", "src/app.spec.ts"])

    def test_no_test_files(self) -> None:
        from nightshift.scoring import _has_test_files

        assert not _has_test_files(["src/main.py", "src/utils.py"])


class TestScoreDiff:
    def test_security_fix_scores_high(self, tmp_path: Path) -> None:
        # Set up a git repo with a security-related commit
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)
        (tmp_path / "dummy.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)
        pre_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout.strip()
        (tmp_path / "auth.py").write_text("sanitize_input(user_data)\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "fix auth"], cwd=tmp_path, capture_output=True, check=True)

        result = nightshift.score_diff(
            worktree_dir=tmp_path,
            pre_head=pre_head,
            cycle_result=nightshift.CycleResult(
                status="done",
                fixes=[{"title": "fix auth", "category": "Security", "impact": "high", "files": ["auth.py"]}],
                logged_issues=[],
            ),
            files_touched=["auth.py"],
        )
        assert result["score"] >= 8

    def test_trivial_fix_scores_low(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)
        (tmp_path / "dummy.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)
        pre_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout.strip()
        (tmp_path / "style.css").write_text("body { color: red; }\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "polish"], cwd=tmp_path, capture_output=True, check=True)

        result = nightshift.score_diff(
            worktree_dir=tmp_path,
            pre_head=pre_head,
            cycle_result=nightshift.CycleResult(
                status="done",
                fixes=[{"title": "color fix", "category": "Polish", "impact": "low", "files": ["style.css"]}],
                logged_issues=[],
            ),
            files_touched=["style.css"],
        )
        assert result["score"] <= 3

    def test_test_bonus_applied(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)
        (tmp_path / "dummy.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)
        pre_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout.strip()
        (tmp_path / "test_auth.py").write_text("def test_login(): pass\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "add test"], cwd=tmp_path, capture_output=True, check=True)

        result = nightshift.score_diff(
            worktree_dir=tmp_path,
            pre_head=pre_head,
            cycle_result=None,
            files_touched=["test_auth.py"],
        )
        assert result["test_bonus"] is True

    def test_no_cycle_result_still_works(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)
        (tmp_path / "dummy.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)
        pre_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout.strip()

        result = nightshift.score_diff(
            worktree_dir=tmp_path,
            pre_head=pre_head,
            cycle_result=None,
            files_touched=[],
        )
        assert isinstance(result["score"], int)
        assert 1 <= result["score"] <= 10


# --- Test File Detection (state._is_test_file via append_cycle_state) --------


class TestTestsWrittenTracking:
    """Tests that append_cycle_state tracks test files in tests_written counter."""

    def _base_state(self):
        return {
            "counters": {
                "fixes": 0,
                "issues_logged": 0,
                "files_touched": 0,
                "low_impact_fixes": 0,
                "failed_verifications": 0,
                "empty_cycles": 0,
                "agent_failures": 0,
                "tests_written": 0,
            },
            "category_counts": {},
            "recent_cycle_paths": [],
            "cycles": [],
            "log_only_mode": False,
        }

    def test_python_test_file_increments_counter(self):
        state = self._base_state()
        cycle_result = {
            "fixes": [{"title": "add test", "category": "Tests", "impact": "medium", "files": ["test_auth.py"]}],
            "logged_issues": [],
            "status": "completed",
        }
        verification = {
            "commits": ["abc1234"],
            "files_touched": ["test_auth.py"],
            "dominant_path": "tests",
        }
        nightshift.append_cycle_state(
            state=state,
            cycle_number=1,
            cycle_result=cycle_result,
            verification=verification,
        )
        assert state["counters"]["tests_written"] == 1

    def test_js_spec_file_increments_counter(self):
        state = self._base_state()
        cycle_result = {
            "fixes": [{"title": "add spec", "category": "Tests", "impact": "medium", "files": ["auth.spec.ts"]}],
            "logged_issues": [],
            "status": "completed",
        }
        verification = {
            "commits": ["abc1234"],
            "files_touched": ["auth.spec.ts"],
            "dominant_path": "tests",
        }
        nightshift.append_cycle_state(
            state=state,
            cycle_number=1,
            cycle_result=cycle_result,
            verification=verification,
        )
        assert state["counters"]["tests_written"] == 1

    def test_non_test_file_does_not_increment(self):
        state = self._base_state()
        cycle_result = {
            "fixes": [{"title": "fix bug", "category": "Security", "impact": "high", "files": ["auth.py"]}],
            "logged_issues": [],
            "status": "completed",
        }
        verification = {
            "commits": ["abc1234"],
            "files_touched": ["auth.py"],
            "dominant_path": "src",
        }
        nightshift.append_cycle_state(
            state=state,
            cycle_number=1,
            cycle_result=cycle_result,
            verification=verification,
        )
        assert state["counters"]["tests_written"] == 0

    def test_multiple_test_files_counted(self):
        state = self._base_state()
        cycle_result = {
            "fixes": [
                {"title": "add tests", "category": "Tests", "impact": "medium", "files": ["test_a.py", "test_b.py"]},
            ],
            "logged_issues": [],
            "status": "completed",
        }
        verification = {
            "commits": ["abc1234"],
            "files_touched": ["test_a.py", "test_b.py"],
            "dominant_path": "tests",
        }
        nightshift.append_cycle_state(
            state=state,
            cycle_number=1,
            cycle_result=cycle_result,
            verification=verification,
        )
        assert state["counters"]["tests_written"] == 2

    def test_accumulates_across_cycles(self):
        state = self._base_state()
        for i in range(1, 3):
            cycle_result = {
                "fixes": [{"title": f"test {i}", "category": "Tests", "impact": "medium", "files": [f"test_{i}.py"]}],
                "logged_issues": [],
                "status": "completed",
            }
            verification = {
                "commits": [f"abc{i}"],
                "files_touched": [f"test_{i}.py"],
                "dominant_path": "tests",
            }
            nightshift.append_cycle_state(
                state=state,
                cycle_number=i,
                cycle_result=cycle_result,
                verification=verification,
            )
        assert state["counters"]["tests_written"] == 2

    def test_tsx_test_file_detected(self):
        state = self._base_state()
        cycle_result = {
            "fixes": [{"title": "add test", "category": "Tests", "impact": "medium", "files": ["Button.test.tsx"]}],
            "logged_issues": [],
            "status": "completed",
        }
        verification = {
            "commits": ["abc1234"],
            "files_touched": ["src/components/Button.test.tsx"],
            "dominant_path": "src",
        }
        nightshift.append_cycle_state(
            state=state,
            cycle_number=1,
            cycle_result=cycle_result,
            verification=verification,
        )
        assert state["counters"]["tests_written"] == 1


# --- Test Writing Escalation -------------------------------------------------


class TestBuildTestEscalation:
    """Tests for build_test_escalation prompt escalation logic."""

    def _base_config(self):
        return {"test_incentive_cycle": 3}

    def _base_state(self, tests_written=0):
        return {
            "counters": {"tests_written": tests_written},
        }

    def test_no_escalation_before_threshold(self):
        result = nightshift.build_test_escalation(
            cycle=2,
            config=self._base_config(),
            state=self._base_state(),
        )
        assert result == ""

    def test_escalation_at_threshold_with_no_tests(self):
        result = nightshift.build_test_escalation(
            cycle=3,
            config=self._base_config(),
            state=self._base_state(),
        )
        assert "MUST include a test file" in result

    def test_escalation_after_threshold_with_no_tests(self):
        result = nightshift.build_test_escalation(
            cycle=5,
            config=self._base_config(),
            state=self._base_state(),
        )
        assert "MUST include a test file" in result

    def test_no_escalation_when_tests_written(self):
        result = nightshift.build_test_escalation(
            cycle=5,
            config=self._base_config(),
            state=self._base_state(tests_written=2),
        )
        assert result == ""

    def test_custom_threshold(self):
        config = {"test_incentive_cycle": 5}
        result = nightshift.build_test_escalation(
            cycle=4,
            config=config,
            state=self._base_state(),
        )
        assert result == ""
        result = nightshift.build_test_escalation(
            cycle=5,
            config=config,
            state=self._base_state(),
        )
        assert "MUST include a test file" in result

    def test_threshold_exactly_at_boundary(self):
        result = nightshift.build_test_escalation(
            cycle=3,
            config=self._base_config(),
            state=self._base_state(tests_written=1),
        )
        assert result == ""


# --- Test Escalation in build_prompt -----------------------------------------


class TestBuildPromptTestEscalation:
    """Tests that build_prompt includes test escalation when appropriate."""

    def _base_args(self, cycle=4, tests_written=0):
        return dict(
            cycle=cycle,
            is_final=False,
            config={
                "agent": "codex",
                "max_fixes_per_cycle": 3,
                "max_files_per_fix": 5,
                "max_files_per_cycle": 12,
                "max_low_impact_fixes_per_shift": 4,
                "test_incentive_cycle": 3,
            },
            state={
                "counters": {"low_impact_fixes": 0, "fixes": 3, "issues_logged": 0, "tests_written": tests_written},
                "log_only_mode": False,
                "recent_cycle_paths": ["src"],
                "cycles": [
                    {
                        "cycle": 1,
                        "status": "done",
                        "fixes": [],
                        "logged_issues": [],
                        "verification": {
                            "files_touched": ["src/auth.py"],
                            "dominant_path": "src",
                            "commits": ["abc1234"],
                            "violations": [],
                            "verify_command": None,
                            "verify_status": "skipped",
                            "verify_exit_code": None,
                        },
                    }
                ],
                "category_counts": {"Security": 1},
            },
            shift_log_relative="docs/Nightshift/2026-04-03.md",
            blocked_summary="- `.github/`",
            hot_files=[],
            prior_path_bias=["src"],
            focus_hints=[],
            test_mode=False,
        )

    def test_escalation_included_after_threshold(self):
        prompt = nightshift.build_prompt(**self._base_args(cycle=4, tests_written=0))
        assert "Test writing directive" in prompt
        assert "MUST include a test file" in prompt

    def test_no_escalation_before_threshold(self):
        prompt = nightshift.build_prompt(**self._base_args(cycle=2, tests_written=0))
        assert "Test writing directive" not in prompt

    def test_no_escalation_when_tests_written(self):
        prompt = nightshift.build_prompt(**self._base_args(cycle=4, tests_written=2))
        assert "Test writing directive" not in prompt


# --- Classify Repo Dirs ------------------------------------------------------


class TestClassifyRepoDirs:
    """Tests for classify_repo_dirs() directory classification."""

    def test_frontend_dir_by_name(self, tmp_path):
        (tmp_path / "components").mkdir()
        (tmp_path / "pages").mkdir()
        frontend, backend = nightshift.classify_repo_dirs(tmp_path)
        assert "components" in frontend
        assert "pages" in frontend
        assert backend == []

    def test_backend_dir_by_name(self, tmp_path):
        (tmp_path / "server").mkdir()
        (tmp_path / "api").mkdir()
        frontend, backend = nightshift.classify_repo_dirs(tmp_path)
        assert frontend == []
        assert "server" in backend
        assert "api" in backend

    def test_mixed_repo(self, tmp_path):
        (tmp_path / "components").mkdir()
        (tmp_path / "server").mkdir()
        (tmp_path / "lib").mkdir()
        frontend, backend = nightshift.classify_repo_dirs(tmp_path)
        assert frontend == ["components"]
        assert "server" in backend
        assert "lib" in backend

    def test_ambiguous_dir_classified_by_extensions(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "App.tsx").write_text("export default App")
        (src / "index.jsx").write_text("render()")
        frontend, backend = nightshift.classify_repo_dirs(tmp_path)
        assert "src" in frontend
        assert backend == []

    def test_ambiguous_dir_backend_extensions(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("if __name__")
        (src / "server.go").write_text("package main")
        frontend, backend = nightshift.classify_repo_dirs(tmp_path)
        assert frontend == []
        assert "src" in backend

    def test_hidden_dirs_skipped(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".config").mkdir()
        (tmp_path / "server").mkdir()
        frontend, backend = nightshift.classify_repo_dirs(tmp_path)
        assert frontend == []
        assert backend == ["server"]

    def test_node_modules_skipped(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "components").mkdir()
        frontend, _backend = nightshift.classify_repo_dirs(tmp_path)
        assert frontend == ["components"]

    def test_empty_repo(self, tmp_path):
        frontend, backend = nightshift.classify_repo_dirs(tmp_path)
        assert frontend == []
        assert backend == []

    def test_unclassifiable_dirs_excluded(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "README.md").write_text("# Docs")
        frontend, backend = nightshift.classify_repo_dirs(tmp_path)
        assert frontend == []
        assert backend == []


# --- Backend Escalation Logic ------------------------------------------------


class TestBuildBackendEscalation:
    """Tests for build_backend_escalation() logic."""

    def _base_config(self, threshold=3):
        return {"backend_forcing_cycle": threshold}

    def _base_state(self, recent_paths=None):
        return {
            "recent_cycle_paths": recent_paths or [],
            "counters": {"fixes": 0, "issues_logged": 0, "tests_written": 0},
            "cycles": [],
            "category_counts": {},
        }

    def test_no_escalation_before_threshold(self, tmp_path):
        (tmp_path / "components").mkdir()
        (tmp_path / "server").mkdir()
        result = nightshift.build_backend_escalation(
            cycle=2,
            config=self._base_config(threshold=3),
            state=self._base_state(recent_paths=["components", "components"]),
            repo_dir=tmp_path,
        )
        assert result == ""

    def test_escalation_after_frontend_only_cycles(self, tmp_path):
        (tmp_path / "components").mkdir()
        (tmp_path / "pages").mkdir()
        (tmp_path / "server").mkdir()
        (tmp_path / "api").mkdir()
        result = nightshift.build_backend_escalation(
            cycle=4,
            config=self._base_config(threshold=3),
            state=self._base_state(recent_paths=["components", "pages", "components"]),
            repo_dir=tmp_path,
        )
        assert "backend" in result.lower()
        assert "`server`" in result or "`api`" in result

    def test_no_escalation_when_backend_visited(self, tmp_path):
        (tmp_path / "components").mkdir()
        (tmp_path / "server").mkdir()
        result = nightshift.build_backend_escalation(
            cycle=4,
            config=self._base_config(threshold=3),
            state=self._base_state(recent_paths=["components", "server", "components"]),
            repo_dir=tmp_path,
        )
        assert result == ""

    def test_no_escalation_when_no_backend_dirs(self, tmp_path):
        (tmp_path / "components").mkdir()
        (tmp_path / "pages").mkdir()
        result = nightshift.build_backend_escalation(
            cycle=4,
            config=self._base_config(threshold=3),
            state=self._base_state(recent_paths=["components", "pages", "components"]),
            repo_dir=tmp_path,
        )
        assert result == ""

    def test_no_escalation_when_not_enough_history(self, tmp_path):
        (tmp_path / "components").mkdir()
        (tmp_path / "server").mkdir()
        result = nightshift.build_backend_escalation(
            cycle=4,
            config=self._base_config(threshold=3),
            state=self._base_state(recent_paths=["components"]),
            repo_dir=tmp_path,
        )
        assert result == ""

    def test_custom_threshold(self, tmp_path):
        (tmp_path / "pages").mkdir()
        (tmp_path / "server").mkdir()
        result = nightshift.build_backend_escalation(
            cycle=2,
            config=self._base_config(threshold=2),
            state=self._base_state(recent_paths=["pages", "pages"]),
            repo_dir=tmp_path,
        )
        assert "backend" in result.lower()

    def test_names_specific_dirs(self, tmp_path):
        (tmp_path / "components").mkdir()
        (tmp_path / "api").mkdir()
        (tmp_path / "models").mkdir()
        result = nightshift.build_backend_escalation(
            cycle=4,
            config=self._base_config(threshold=3),
            state=self._base_state(recent_paths=["components", "components", "components"]),
            repo_dir=tmp_path,
        )
        assert "`api`" in result
        assert "`models`" in result


# --- Backend Escalation in build_prompt --------------------------------------


class TestBuildPromptBackendEscalation:
    """Tests that build_prompt includes backend escalation when provided."""

    def _base_args(self, backend_escalation=""):
        return dict(
            cycle=4,
            is_final=False,
            config={
                "agent": "codex",
                "max_fixes_per_cycle": 3,
                "max_files_per_fix": 5,
                "max_files_per_cycle": 12,
                "max_low_impact_fixes_per_shift": 4,
                "test_incentive_cycle": 3,
            },
            state={
                "counters": {"low_impact_fixes": 0, "fixes": 3, "issues_logged": 0, "tests_written": 0},
                "log_only_mode": False,
                "recent_cycle_paths": ["components"],
                "cycles": [
                    {
                        "cycle": 1,
                        "status": "done",
                        "fixes": [],
                        "logged_issues": [],
                        "verification": {
                            "files_touched": ["components/Button.tsx"],
                            "dominant_path": "components",
                            "commits": ["abc1234"],
                            "violations": [],
                            "verify_command": None,
                            "verify_status": "skipped",
                            "verify_exit_code": None,
                        },
                    }
                ],
                "category_counts": {"Code Quality": 1},
            },
            shift_log_relative="docs/Nightshift/2026-04-03.md",
            blocked_summary="- `.github/`",
            hot_files=[],
            prior_path_bias=["components"],
            focus_hints=[],
            test_mode=False,
            backend_escalation=backend_escalation,
        )

    def test_backend_block_included_when_escalation_provided(self):
        msg = "The last 3 cycles all targeted frontend code. Focus on backend: `server`, `api`."
        prompt = nightshift.build_prompt(**self._base_args(backend_escalation=msg))
        assert "Backend exploration directive" in prompt
        assert "server" in prompt

    def test_no_backend_block_when_empty(self):
        prompt = nightshift.build_prompt(**self._base_args(backend_escalation=""))
        assert "Backend exploration directive" not in prompt

    def test_backend_block_coexists_with_test_escalation(self):
        args = self._base_args(backend_escalation="Focus on backend dirs: `server`.")
        args["state"]["counters"]["tests_written"] = 0
        prompt = nightshift.build_prompt(**args)
        assert "Backend exploration directive" in prompt
        assert "Test writing directive" in prompt


# --- Category Balancing Logic ------------------------------------------------


class TestBuildCategoryBalancing:
    """Tests for build_category_balancing() steering directive."""

    def _base_config(self, threshold=3):
        return {"category_balancing_cycle": threshold}

    def _base_state(self, category_counts=None, fixes=0):
        return {
            "category_counts": category_counts or {},
            "counters": {"fixes": fixes},
        }

    def test_no_balancing_before_threshold(self):
        result = nightshift.build_category_balancing(
            cycle=2,
            config=self._base_config(),
            state=self._base_state(category_counts={"Security": 2}, fixes=2),
        )
        assert result == ""

    def test_no_balancing_with_fewer_than_two_fixes(self):
        result = nightshift.build_category_balancing(
            cycle=4,
            config=self._base_config(),
            state=self._base_state(category_counts={"Security": 1}, fixes=1),
        )
        assert result == ""

    def test_balancing_at_threshold_with_imbalance(self):
        result = nightshift.build_category_balancing(
            cycle=3,
            config=self._base_config(),
            state=self._base_state(category_counts={"Security": 2}, fixes=2),
        )
        assert "Category imbalance" in result
        assert "Error Handling" in result  # highest-priority unexplored

    def test_targets_highest_priority_unexplored(self):
        # Security explored, Error Handling should be next
        result = nightshift.build_category_balancing(
            cycle=4,
            config=self._base_config(),
            state=self._base_state(
                category_counts={"Security": 1, "Tests": 1},
                fixes=2,
            ),
        )
        assert "Focus this cycle on Error Handling" in result

    def test_no_balancing_when_all_categories_explored(self):
        all_cats = dict.fromkeys(nightshift.CATEGORY_ORDER, 1)
        result = nightshift.build_category_balancing(
            cycle=5,
            config=self._base_config(),
            state=self._base_state(category_counts=all_cats, fixes=7),
        )
        assert result == ""

    def test_mentions_additional_underrepresented(self):
        result = nightshift.build_category_balancing(
            cycle=4,
            config=self._base_config(),
            state=self._base_state(category_counts={"Security": 3}, fixes=3),
        )
        assert "Also underrepresented" in result
        assert "Error Handling" in result
        assert "Tests" in result

    def test_custom_threshold(self):
        config = self._base_config(threshold=5)
        result = nightshift.build_category_balancing(
            cycle=4,
            config=config,
            state=self._base_state(category_counts={"Security": 2}, fixes=2),
        )
        assert result == ""
        result = nightshift.build_category_balancing(
            cycle=5,
            config=config,
            state=self._base_state(category_counts={"Security": 2}, fixes=2),
        )
        assert "Category imbalance" in result

    def test_counts_unexplored_correctly(self):
        result = nightshift.build_category_balancing(
            cycle=3,
            config=self._base_config(),
            state=self._base_state(
                category_counts={"Security": 1, "Error Handling": 1, "Tests": 1},
                fixes=3,
            ),
        )
        # 4 unexplored: A11y, Code Quality, Performance, Polish
        assert "4 of 7" in result
        assert "Focus this cycle on A11y" in result


# --- Category Balancing in build_prompt --------------------------------------


class TestBuildPromptCategoryBalancing:
    """Tests that build_prompt includes category balancing when provided."""

    def _base_args(self, category_balancing=""):
        return dict(
            cycle=4,
            is_final=False,
            config={
                "agent": "codex",
                "max_fixes_per_cycle": 3,
                "max_files_per_fix": 5,
                "max_files_per_cycle": 12,
                "max_low_impact_fixes_per_shift": 4,
                "test_incentive_cycle": 3,
            },
            state={
                "counters": {"low_impact_fixes": 0, "fixes": 3, "issues_logged": 0, "tests_written": 0},
                "log_only_mode": False,
                "recent_cycle_paths": ["src"],
                "cycles": [
                    {
                        "cycle": 1,
                        "status": "done",
                        "fixes": [],
                        "logged_issues": [],
                        "verification": {
                            "files_touched": ["src/auth.py"],
                            "dominant_path": "src",
                            "commits": ["abc1234"],
                            "violations": [],
                            "verify_command": None,
                            "verify_status": "skipped",
                            "verify_exit_code": None,
                        },
                    }
                ],
                "category_counts": {"Security": 2},
            },
            shift_log_relative="docs/Nightshift/2026-04-03.md",
            blocked_summary="- `.github/`",
            hot_files=[],
            prior_path_bias=["src"],
            focus_hints=[],
            test_mode=False,
            category_balancing=category_balancing,
        )

    def test_category_block_included_when_balancing_provided(self):
        msg = "Category imbalance detected: 6 of 7 categories have no fixes yet. Focus this cycle on Error Handling issues."
        prompt = nightshift.build_prompt(**self._base_args(category_balancing=msg))
        assert "Category balancing directive" in prompt
        assert "Error Handling" in prompt

    def test_no_category_block_when_empty(self):
        prompt = nightshift.build_prompt(**self._base_args(category_balancing=""))
        assert "Category balancing directive" not in prompt

    def test_category_block_coexists_with_other_escalations(self):
        args = self._base_args(category_balancing="Focus on A11y issues.")
        args["backend_escalation"] = "Focus on backend dirs."
        prompt = nightshift.build_prompt(**args)
        assert "Category balancing directive" in prompt
        assert "Backend exploration directive" in prompt
        assert "Test writing directive" in prompt


# --- Discover Base Branch ----------------------------------------------------


class TestDiscoverBaseBranch:
    def test_returns_string(self):
        repo = Path(__file__).resolve().parent.parent
        result = nightshift.discover_base_branch(repo)
        assert isinstance(result, str)
        # In CI PR checkouts (detached HEAD), result may be empty
        if os.environ.get("CI"):
            return
        assert len(result) > 0

    def test_invalid_repo_raises_clear_error(self, tmp_path: Path) -> None:
        with pytest.raises(nightshift.NightshiftError, match="not a valid git checkout"):
            nightshift.discover_base_branch(tmp_path)


# --- Shift Log Verification Tolerance ----------------------------------------


class TestShiftLogVerificationTolerance:
    """Tests that verify_cycle accepts shift-log updates in separate commits."""

    def _setup_repo(self, tmp_path: Path) -> tuple[Path, str]:
        """Create a git repo with one initial commit and return (worktree, pre_head)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
        shift_log = repo / "docs" / "Nightshift"
        shift_log.mkdir(parents=True)
        (shift_log / "2026-04-03.md").write_text("# Shift log\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True)
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True)
        return repo, result.stdout.strip()

    def _base_config(self) -> dict:
        return {
            "agent": "codex",
            "max_fixes_per_cycle": 3,
            "max_files_per_fix": 5,
            "max_files_per_cycle": 12,
            "max_low_impact_fixes_per_shift": 4,
            "blocked_paths": [".github/"],
            "blocked_globs": ["*.lock"],
        }

    def _base_state(self) -> dict:
        return {
            "verify_command": None,
            "log_only_mode": False,
            "counters": {"low_impact_fixes": 0, "fixes": 0, "issues_logged": 0},
            "recent_cycle_paths": [],
            "category_counts": {},
        }

    def test_separate_shift_log_commit_accepted(self, tmp_path: Path) -> None:
        """Agent commits fix first, then shift log separately -- should pass."""
        repo, pre_head = self._setup_repo(tmp_path)
        shift_log_rel = "docs/Nightshift/2026-04-03.md"
        # Commit 1: fix only (no shift log)
        (repo / "src").mkdir()
        (repo / "src" / "auth.py").write_text("# fixed\n")
        subprocess.run(["git", "add", "src/auth.py"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "fix: auth"], cwd=repo, capture_output=True, check=True)
        # Commit 2: shift log only
        (repo / shift_log_rel).write_text("# Updated shift log\n## Fix 1\n")
        subprocess.run(["git", "add", shift_log_rel], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "docs: update shift log"], cwd=repo, capture_output=True, check=True)

        valid, verification = nightshift.verify_cycle(
            worktree_dir=repo,
            shift_log_relative=shift_log_rel,
            pre_head=pre_head,
            cycle_result={
                "status": "completed",
                "fixes": [{"title": "auth fix", "files": ["src/auth.py"]}],
                "logged_issues": [],
            },
            config=self._base_config(),
            state=self._base_state(),
            runner_log=tmp_path / "runner.log",
        )
        assert valid, f"Expected valid but got violations: {verification['violations']}"

    def test_co_committed_shift_log_still_accepted(self, tmp_path: Path) -> None:
        """Agent commits fix and shift log together -- should still pass."""
        repo, pre_head = self._setup_repo(tmp_path)
        shift_log_rel = "docs/Nightshift/2026-04-03.md"
        (repo / "src").mkdir()
        (repo / "src" / "auth.py").write_text("# fixed\n")
        (repo / shift_log_rel).write_text("# Updated shift log\n")
        subprocess.run(["git", "add", "src/auth.py", shift_log_rel], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "fix: auth + log"], cwd=repo, capture_output=True, check=True)

        valid, verification = nightshift.verify_cycle(
            worktree_dir=repo,
            shift_log_relative=shift_log_rel,
            pre_head=pre_head,
            cycle_result={
                "status": "completed",
                "fixes": [{"title": "auth fix", "files": ["src/auth.py"]}],
                "logged_issues": [],
            },
            config=self._base_config(),
            state=self._base_state(),
            runner_log=tmp_path / "runner.log",
        )
        assert valid, f"Expected valid but got violations: {verification['violations']}"

    def test_no_shift_log_commit_rejected(self, tmp_path: Path) -> None:
        """Agent commits fix but never updates shift log -- should fail."""
        repo, pre_head = self._setup_repo(tmp_path)
        shift_log_rel = "docs/Nightshift/2026-04-03.md"
        (repo / "src").mkdir()
        (repo / "src" / "auth.py").write_text("# fixed\n")
        subprocess.run(["git", "add", "src/auth.py"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "fix: auth"], cwd=repo, capture_output=True, check=True)

        valid, verification = nightshift.verify_cycle(
            worktree_dir=repo,
            shift_log_relative=shift_log_rel,
            pre_head=pre_head,
            cycle_result={
                "status": "completed",
                "fixes": [{"title": "auth fix", "files": ["src/auth.py"]}],
                "logged_issues": [],
            },
            config=self._base_config(),
            state=self._base_state(),
            runner_log=tmp_path / "runner.log",
        )
        assert not valid
        assert any("shift log" in v.lower() for v in verification["violations"])

    def test_shift_log_only_commit_not_counted_as_fix(self, tmp_path: Path) -> None:
        """Shift-log-only commit should not count toward max_fixes_per_cycle."""
        repo, pre_head = self._setup_repo(tmp_path)
        shift_log_rel = "docs/Nightshift/2026-04-03.md"
        config = self._base_config()
        config["max_fixes_per_cycle"] = 1
        # Commit 1: fix
        (repo / "src").mkdir()
        (repo / "src" / "auth.py").write_text("# fixed\n")
        subprocess.run(["git", "add", "src/auth.py"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "fix: auth"], cwd=repo, capture_output=True, check=True)
        # Commit 2: shift log only (should not count as fix)
        (repo / shift_log_rel).write_text("# Updated shift log\n")
        subprocess.run(["git", "add", shift_log_rel], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "docs: shift log"], cwd=repo, capture_output=True, check=True)

        _valid, verification = nightshift.verify_cycle(
            worktree_dir=repo,
            shift_log_relative=shift_log_rel,
            pre_head=pre_head,
            cycle_result={
                "status": "completed",
                "fixes": [{"title": "auth fix", "files": ["src/auth.py"]}],
                "logged_issues": [],
            },
            config=config,
            state=self._base_state(),
            runner_log=tmp_path / "runner.log",
        )
        # 2 commits total but only 1 fix commit -- should be within limit
        assert not any("max_fixes_per_cycle" in v for v in verification["violations"]), (
            f"Shift-log-only commit wrongly counted as fix: {verification['violations']}"
        )


# --- Dry Run Integration ----------------------------------------------------


class TestDryRunIntegration:
    """End-to-end test: the full CLI with --dry-run produces a prompt."""

    def test_run_dry_run_package(self):
        repo = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "nightshift", "run", "--agent", "codex", "--dry-run"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Nightshift" in result.stdout
        assert "Cycle: 1" in result.stdout

    def test_test_dry_run_package(self):
        repo = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "nightshift", "test", "--agent", "claude", "--dry-run"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Nightshift" in result.stdout

    def test_no_agent_errors_package(self):
        repo = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "nightshift", "run", "--dry-run"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "No agent configured" in result.stderr
