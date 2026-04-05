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


# --- Multi-Repo Support -------------------------------------------------------


class TestRepoShiftResultType:
    def test_has_required_fields(self):
        result: nightshift.RepoShiftResult = {
            "repo_dir": "/tmp/repo",
            "exit_code": 0,
            "cycles_run": 3,
            "fixes": 2,
            "issues_logged": 1,
            "halt_reason": "",
        }
        assert result["repo_dir"] == "/tmp/repo"
        assert result["exit_code"] == 0
        assert result["cycles_run"] == 3
        assert result["fixes"] == 2
        assert result["issues_logged"] == 1
        assert result["halt_reason"] == ""


class TestValidateRepos:
    def test_valid_repos(self, tmp_path):
        repo1 = tmp_path / "repo1"
        repo1.mkdir()
        (repo1 / ".git").mkdir()
        repo2 = tmp_path / "repo2"
        repo2.mkdir()
        (repo2 / ".git").mkdir()
        nightshift.validate_repos([repo1, repo2])

    def test_rejects_missing_dir(self, tmp_path):
        missing = tmp_path / "nonexistent"
        with pytest.raises(nightshift.NightshiftError, match="does not exist"):
            nightshift.validate_repos([missing])

    def test_rejects_non_git_dir(self, tmp_path):
        not_git = tmp_path / "plain"
        not_git.mkdir()
        with pytest.raises(nightshift.NightshiftError, match="Not a git repository"):
            nightshift.validate_repos([not_git])

    def test_accepts_git_worktree_file(self, tmp_path):
        """A .git file (not dir) is valid -- worktrees use this."""
        repo = tmp_path / "worktree"
        repo.mkdir()
        (repo / ".git").write_text("gitdir: /somewhere/.git/worktrees/wt")
        nightshift.validate_repos([repo])


class TestFormatMultiSummary:
    def test_all_ok(self):
        results: list[nightshift.RepoShiftResult] = [
            {
                "repo_dir": "/tmp/alpha",
                "exit_code": 0,
                "cycles_run": 4,
                "fixes": 3,
                "issues_logged": 1,
                "halt_reason": "",
            },
            {
                "repo_dir": "/tmp/beta",
                "exit_code": 0,
                "cycles_run": 2,
                "fixes": 1,
                "issues_logged": 0,
                "halt_reason": "",
            },
        ]
        summary = nightshift.format_multi_summary(results)
        assert "MULTI-REPO SUMMARY" in summary
        assert "alpha" in summary
        assert "beta" in summary
        assert "OK" in summary
        assert "Total: 6 cycles, 4 fixes, 1 issues" in summary

    def test_mixed_results(self):
        results: list[nightshift.RepoShiftResult] = [
            {
                "repo_dir": "/tmp/good",
                "exit_code": 0,
                "cycles_run": 3,
                "fixes": 2,
                "issues_logged": 0,
                "halt_reason": "",
            },
            {
                "repo_dir": "/tmp/bad",
                "exit_code": 1,
                "cycles_run": 1,
                "fixes": 0,
                "issues_logged": 0,
                "halt_reason": "Agent command failed twice in a row.",
            },
        ]
        summary = nightshift.format_multi_summary(results)
        assert "good" in summary
        assert "OK" in summary
        assert "bad" in summary
        assert "FAIL" in summary

    def test_empty_results(self):
        summary = nightshift.format_multi_summary([])
        assert "MULTI-REPO SUMMARY" in summary
        assert "Total: 0 cycles, 0 fixes, 0 issues" in summary


class TestReadRepoMetrics:
    """Test _read_repo_metrics via the multi module."""

    def test_reads_state_file(self, tmp_path):
        from nightshift.multi import _read_repo_metrics

        docs = tmp_path / "docs" / "Nightshift"
        docs.mkdir(parents=True)
        state = {
            "version": 1,
            "cycles": [{"cycle": 1}, {"cycle": 2}],
            "counters": {"fixes": 3, "issues_logged": 1},
            "halt_reason": None,
        }
        (docs / "2026-04-03.state.json").write_text(json.dumps(state))
        result = _read_repo_metrics(tmp_path, "2026-04-03")
        assert result["cycles_run"] == 2
        assert result["fixes"] == 3
        assert result["issues_logged"] == 1
        assert result["halt_reason"] == ""

    def test_missing_state_file(self, tmp_path):
        from nightshift.multi import _read_repo_metrics

        result = _read_repo_metrics(tmp_path, "2026-04-03")
        assert result["cycles_run"] == 0
        assert result["fixes"] == 0
        assert result["issues_logged"] == 0

    def test_halt_reason_preserved(self, tmp_path):
        from nightshift.multi import _read_repo_metrics

        docs = tmp_path / "docs" / "Nightshift"
        docs.mkdir(parents=True)
        state = {
            "version": 1,
            "cycles": [],
            "counters": {"fixes": 0, "issues_logged": 0},
            "halt_reason": "Agent command failed twice in a row.",
        }
        (docs / "2026-04-03.state.json").write_text(json.dumps(state))
        result = _read_repo_metrics(tmp_path, "2026-04-03")
        assert result["halt_reason"] == "Agent command failed twice in a row."


class TestMultiSubcommandParser:
    def test_multi_subcommand_parses(self):
        parser = nightshift.build_parser()
        args = parser.parse_args(["multi", "/tmp/repo1", "/tmp/repo2", "--agent", "codex", "--test"])
        assert args.command == "multi"
        assert args.repos == ["/tmp/repo1", "/tmp/repo2"]
        assert args.agent == "codex"
        assert args.test is True

    def test_multi_requires_repos(self):
        parser = nightshift.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["multi"])

    def test_multi_dry_run(self):
        parser = nightshift.build_parser()
        args = parser.parse_args(["multi", "/tmp/r1", "--dry-run", "--agent", "codex"])
        assert args.dry_run is True

    def test_multi_defaults(self):
        parser = nightshift.build_parser()
        args = parser.parse_args(["multi", "/tmp/r1"])
        assert args.test is False
        assert args.cycles == 4
        assert args.cycle_minutes == 8


class TestMultiDryRunIntegration:
    """End-to-end: multi subcommand with --dry-run against real repos."""

    def test_multi_dry_run_single_repo(self):
        repo = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "nightshift", "multi", str(repo), "--agent", "codex", "--test", "--dry-run"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Nightshift" in result.stdout

    def test_multi_rejects_nonexistent_repo(self):
        repo = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "nightshift", "multi", "/tmp/nonexistent-repo-xyz", "--agent", "codex", "--test"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "does not exist" in result.stderr


# --- Dry-Run Integration Tests -----------------------------------------------


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


# --- Profiler Types -----------------------------------------------------------


class TestFrameworkInfoType:
    def test_framework_info_fields(self) -> None:
        info = nightshift.FrameworkInfo(name="React", version="^18.0.0")
        assert info["name"] == "React"
        assert info["version"] == "^18.0.0"

    def test_repo_profile_fields(self) -> None:
        profile = nightshift.RepoProfile(
            languages={"Python": 10},
            primary_language="Python",
            frameworks=[],
            package_manager=None,
            test_runner=None,
            instruction_files=[],
            top_level_dirs=["src"],
            has_monorepo_markers=False,
            total_files=10,
        )
        assert profile["primary_language"] == "Python"
        assert profile["total_files"] == 10


# --- Profiler Constants -------------------------------------------------------


class TestProfilerConstants:
    def test_language_extensions_has_major_languages(self) -> None:
        from nightshift.constants import LANGUAGE_EXTENSIONS

        assert ".py" in LANGUAGE_EXTENSIONS
        assert ".js" in LANGUAGE_EXTENSIONS
        assert ".ts" in LANGUAGE_EXTENSIONS
        assert ".go" in LANGUAGE_EXTENSIONS
        assert ".rs" in LANGUAGE_EXTENSIONS

    def test_framework_markers_has_common_frameworks(self) -> None:
        from nightshift.constants import FRAMEWORK_MARKERS

        assert "Next.js" in FRAMEWORK_MARKERS
        assert "Django" in FRAMEWORK_MARKERS
        assert "Rails" in FRAMEWORK_MARKERS

    def test_framework_packages_has_common_packages(self) -> None:
        from nightshift.constants import FRAMEWORK_PACKAGES

        assert "React" in FRAMEWORK_PACKAGES
        assert FRAMEWORK_PACKAGES["React"] == "react"

    def test_instruction_file_names(self) -> None:
        from nightshift.constants import INSTRUCTION_FILE_NAMES

        assert "CLAUDE.md" in INSTRUCTION_FILE_NAMES
        assert "AGENTS.md" in INSTRUCTION_FILE_NAMES

    def test_monorepo_markers(self) -> None:
        from nightshift.constants import MONOREPO_MARKERS

        assert "lerna.json" in MONOREPO_MARKERS
        assert "turbo.json" in MONOREPO_MARKERS

    def test_profiler_skip_dirs(self) -> None:
        from nightshift.constants import PROFILER_SKIP_DIRS

        assert "node_modules" in PROFILER_SKIP_DIRS
        assert ".git" in PROFILER_SKIP_DIRS


# --- Profiler Language Detection ----------------------------------------------


class TestCountLanguages:
    def test_empty_dir(self, tmp_path: Path) -> None:
        from nightshift.profiler import _count_languages

        assert _count_languages(tmp_path) == {}

    def test_counts_python_files(self, tmp_path: Path) -> None:
        from nightshift.profiler import _count_languages

        (tmp_path / "app.py").write_text("x = 1")
        (tmp_path / "utils.py").write_text("y = 2")
        counts = _count_languages(tmp_path)
        assert counts == {"Python": 2}

    def test_counts_multiple_languages(self, tmp_path: Path) -> None:
        from nightshift.profiler import _count_languages

        (tmp_path / "app.py").write_text("x = 1")
        (tmp_path / "index.js").write_text("var x = 1")
        (tmp_path / "main.ts").write_text("const x = 1")
        counts = _count_languages(tmp_path)
        assert counts == {"Python": 1, "JavaScript": 1, "TypeScript": 1}

    def test_skips_node_modules(self, tmp_path: Path) -> None:
        from nightshift.profiler import _count_languages

        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("x")
        (tmp_path / "app.js").write_text("y")
        counts = _count_languages(tmp_path)
        assert counts == {"JavaScript": 1}

    def test_skips_hidden_files(self, tmp_path: Path) -> None:
        from nightshift.profiler import _count_languages

        (tmp_path / ".hidden.py").write_text("x = 1")
        (tmp_path / "visible.py").write_text("y = 2")
        counts = _count_languages(tmp_path)
        assert counts == {"Python": 1}

    def test_tsx_counted_as_typescript(self, tmp_path: Path) -> None:
        from nightshift.profiler import _count_languages

        (tmp_path / "App.tsx").write_text("export default App")
        counts = _count_languages(tmp_path)
        assert counts == {"TypeScript": 1}

    def test_nonexistent_dir(self) -> None:
        from nightshift.profiler import _count_languages

        assert _count_languages(Path("/nonexistent/dir")) == {}


class TestPrimaryLanguage:
    def test_returns_unknown_for_empty(self) -> None:
        from nightshift.profiler import _primary_language

        assert _primary_language({}) == "Unknown"

    def test_returns_highest_count(self) -> None:
        from nightshift.profiler import _primary_language

        assert _primary_language({"Python": 5, "JavaScript": 10}) == "JavaScript"

    def test_single_language(self) -> None:
        from nightshift.profiler import _primary_language

        assert _primary_language({"Go": 3}) == "Go"


# --- Profiler Framework Detection ---------------------------------------------


class TestDetectFrameworksByMarker:
    def test_detects_nextjs(self, tmp_path: Path) -> None:
        from nightshift.profiler import _detect_frameworks_by_marker

        (tmp_path / "next.config.js").write_text("{}")
        found = _detect_frameworks_by_marker(tmp_path)
        assert "Next.js" in found

    def test_detects_django(self, tmp_path: Path) -> None:
        from nightshift.profiler import _detect_frameworks_by_marker

        (tmp_path / "manage.py").write_text("#!/usr/bin/env python")
        found = _detect_frameworks_by_marker(tmp_path)
        assert "Django" in found

    def test_empty_dir_no_frameworks(self, tmp_path: Path) -> None:
        from nightshift.profiler import _detect_frameworks_by_marker

        assert _detect_frameworks_by_marker(tmp_path) == []


class TestDetectFrameworksByPackage:
    def test_detects_react_from_package_json(self, tmp_path: Path) -> None:
        from nightshift.profiler import _detect_frameworks_by_package

        pkg = {"dependencies": {"react": "^18.2.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        found = _detect_frameworks_by_package(tmp_path)
        assert len(found) == 1
        assert found[0]["name"] == "React"
        assert found[0]["version"] == "^18.2.0"

    def test_detects_from_dev_dependencies(self, tmp_path: Path) -> None:
        from nightshift.profiler import _detect_frameworks_by_package

        pkg = {"devDependencies": {"svelte": "^4.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        found = _detect_frameworks_by_package(tmp_path)
        assert len(found) == 1
        assert found[0]["name"] == "Svelte"

    def test_no_package_json(self, tmp_path: Path) -> None:
        from nightshift.profiler import _detect_frameworks_by_package

        assert _detect_frameworks_by_package(tmp_path) == []

    def test_invalid_package_json(self, tmp_path: Path) -> None:
        from nightshift.profiler import _detect_frameworks_by_package

        (tmp_path / "package.json").write_text("not json")
        assert _detect_frameworks_by_package(tmp_path) == []


class TestDetectFrameworks:
    def test_combines_marker_and_package(self, tmp_path: Path) -> None:
        from nightshift.profiler import _detect_frameworks

        (tmp_path / "next.config.js").write_text("{}")
        pkg = {"dependencies": {"react": "^18.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        found = _detect_frameworks(tmp_path)
        names = {fw["name"] for fw in found}
        assert "Next.js" in names
        assert "React" in names

    def test_no_duplicates_when_both_detect(self, tmp_path: Path) -> None:
        from nightshift.profiler import _detect_frameworks

        pkg = {"dependencies": {"express": "^4.18.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        found = _detect_frameworks(tmp_path)
        express_count = sum(1 for fw in found if fw["name"] == "Express")
        assert express_count == 1


# --- Profiler Instruction Files -----------------------------------------------


class TestFindInstructionFiles:
    def test_finds_claude_md(self, tmp_path: Path) -> None:
        from nightshift.profiler import _find_instruction_files

        (tmp_path / "CLAUDE.md").write_text("# Instructions")
        found = _find_instruction_files(tmp_path)
        assert "CLAUDE.md" in found

    def test_finds_multiple(self, tmp_path: Path) -> None:
        from nightshift.profiler import _find_instruction_files

        (tmp_path / "CLAUDE.md").write_text("x")
        (tmp_path / "CONTRIBUTING.md").write_text("y")
        found = _find_instruction_files(tmp_path)
        assert "CLAUDE.md" in found
        assert "CONTRIBUTING.md" in found

    def test_finds_nested_instruction(self, tmp_path: Path) -> None:
        from nightshift.profiler import _find_instruction_files

        gh = tmp_path / ".github"
        gh.mkdir()
        (gh / "copilot-instructions.md").write_text("x")
        found = _find_instruction_files(tmp_path)
        assert ".github/copilot-instructions.md" in found

    def test_empty_dir(self, tmp_path: Path) -> None:
        from nightshift.profiler import _find_instruction_files

        assert _find_instruction_files(tmp_path) == []


# --- Profiler Directory Listing -----------------------------------------------


class TestListTopLevelDirs:
    def test_lists_dirs(self, tmp_path: Path) -> None:
        from nightshift.profiler import _list_top_level_dirs

        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        dirs = _list_top_level_dirs(tmp_path)
        assert "src" in dirs
        assert "tests" in dirs

    def test_skips_hidden(self, tmp_path: Path) -> None:
        from nightshift.profiler import _list_top_level_dirs

        (tmp_path / ".git").mkdir()
        (tmp_path / "src").mkdir()
        dirs = _list_top_level_dirs(tmp_path)
        assert ".git" not in dirs
        assert "src" in dirs

    def test_skips_ignored(self, tmp_path: Path) -> None:
        from nightshift.profiler import _list_top_level_dirs

        (tmp_path / "node_modules").mkdir()
        (tmp_path / "src").mkdir()
        dirs = _list_top_level_dirs(tmp_path)
        assert "node_modules" not in dirs

    def test_sorted(self, tmp_path: Path) -> None:
        from nightshift.profiler import _list_top_level_dirs

        (tmp_path / "z_dir").mkdir()
        (tmp_path / "a_dir").mkdir()
        dirs = _list_top_level_dirs(tmp_path)
        assert dirs == ["a_dir", "z_dir"]


# --- Profiler Monorepo Detection ----------------------------------------------


class TestHasMonorepoMarkers:
    def test_detects_turbo(self, tmp_path: Path) -> None:
        from nightshift.profiler import _has_monorepo_markers

        (tmp_path / "turbo.json").write_text("{}")
        assert _has_monorepo_markers(tmp_path) is True

    def test_detects_lerna(self, tmp_path: Path) -> None:
        from nightshift.profiler import _has_monorepo_markers

        (tmp_path / "lerna.json").write_text("{}")
        assert _has_monorepo_markers(tmp_path) is True

    def test_no_markers(self, tmp_path: Path) -> None:
        from nightshift.profiler import _has_monorepo_markers

        assert _has_monorepo_markers(tmp_path) is False


# --- Profiler File Count ------------------------------------------------------


class TestCountTotalFiles:
    def test_counts_files(self, tmp_path: Path) -> None:
        from nightshift.profiler import _count_total_files

        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.txt").write_text("y")
        assert _count_total_files(tmp_path) == 2

    def test_skips_ignored_dirs(self, tmp_path: Path) -> None:
        from nightshift.profiler import _count_total_files

        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("x")
        (tmp_path / "app.py").write_text("y")
        assert _count_total_files(tmp_path) == 1

    def test_skips_hidden_files(self, tmp_path: Path) -> None:
        from nightshift.profiler import _count_total_files

        (tmp_path / ".env").write_text("SECRET=x")
        (tmp_path / "app.py").write_text("y")
        assert _count_total_files(tmp_path) == 1


# --- Profiler Integration (profile_repo) --------------------------------------


class TestProfileRepo:
    def test_python_project(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "app.py").write_text("x = 1")
        (tmp_path / "src" / "utils.py").write_text("y = 2")
        (tmp_path / "tests" / "test_app.py").write_text("def test(): pass")
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]")
        (tmp_path / "CLAUDE.md").write_text("# Instructions")

        profile = nightshift.profile_repo(tmp_path)

        assert profile["primary_language"] == "Python"
        assert profile["languages"]["Python"] == 3
        assert profile["test_runner"] == "python3 -m pytest"
        assert "CLAUDE.md" in profile["instruction_files"]
        assert "src" in profile["top_level_dirs"]
        assert "tests" in profile["top_level_dirs"]
        assert profile["has_monorepo_markers"] is False
        assert profile["total_files"] >= 3

    def test_nextjs_project(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "page.tsx").write_text("export default function Page() {}")
        (tmp_path / "src" / "layout.tsx").write_text("export default function Layout() {}")
        (tmp_path / "src" / "globals.ts").write_text("export const x = 1")
        (tmp_path / "next.config.js").write_text("module.exports = {}")
        pkg = {
            "dependencies": {"react": "^18.2.0", "next": "^14.0.0"},
            "scripts": {"test": "jest"},
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        (tmp_path / "package-lock.json").write_text("{}")

        profile = nightshift.profile_repo(tmp_path)

        assert profile["primary_language"] == "TypeScript"
        assert profile["package_manager"] == "npm"
        framework_names = {fw["name"] for fw in profile["frameworks"]}
        assert "Next.js" in framework_names
        assert "React" in framework_names
        assert profile["test_runner"] == "npm test"

    def test_monorepo_project(self, tmp_path: Path) -> None:
        (tmp_path / "packages").mkdir()
        (tmp_path / "apps").mkdir()
        (tmp_path / "turbo.json").write_text("{}")
        (tmp_path / "pnpm-workspace.yaml").write_text("packages: ['packages/*']")

        profile = nightshift.profile_repo(tmp_path)

        assert profile["has_monorepo_markers"] is True

    def test_empty_dir(self, tmp_path: Path) -> None:
        profile = nightshift.profile_repo(tmp_path)

        assert profile["primary_language"] == "Unknown"
        assert profile["languages"] == {}
        assert profile["frameworks"] == []
        assert profile["package_manager"] is None
        assert profile["test_runner"] is None
        assert profile["instruction_files"] == []
        assert profile["has_monorepo_markers"] is False
        assert profile["total_files"] == 0

    def test_go_project(self, tmp_path: Path) -> None:
        (tmp_path / "cmd").mkdir()
        (tmp_path / "cmd" / "main.go").write_text("package main")
        (tmp_path / "go.mod").write_text("module example.com/foo")

        profile = nightshift.profile_repo(tmp_path)

        assert profile["primary_language"] == "Go"
        assert profile["test_runner"] == "go test ./..."

    def test_profiles_self(self) -> None:
        """Profile the Nightshift repo itself as a real-world integration test."""
        repo_dir = Path(__file__).resolve().parent.parent
        profile = nightshift.profile_repo(repo_dir)

        assert profile["primary_language"] == "Python"
        assert profile["languages"]["Python"] > 0
        assert "CLAUDE.md" in profile["instruction_files"]
        assert "nightshift" in profile["top_level_dirs"]
        assert profile["total_files"] > 0


# --- Feature Planner ---------------------------------------------------------


def _make_profile(**overrides: object) -> nightshift.RepoProfile:
    """Build a minimal RepoProfile for testing, with overrides."""
    defaults: dict[str, object] = {
        "languages": {"Python": 10},
        "primary_language": "Python",
        "frameworks": [],
        "package_manager": "pip",
        "test_runner": "pytest",
        "instruction_files": ["CLAUDE.md"],
        "top_level_dirs": ["src", "tests"],
        "has_monorepo_markers": False,
        "total_files": 42,
    }
    defaults.update(overrides)
    return nightshift.RepoProfile(**defaults)  # type: ignore[arg-type]


def _make_valid_plan_dict(**overrides: object) -> dict[str, object]:
    """Build a valid plan dict for testing, with overrides."""
    plan: dict[str, object] = {
        "feature": "Add dark mode",
        "architecture": {
            "overview": "Add a dark mode toggle to the settings page.",
            "tech_choices": ["Use CSS variables for theming"],
            "data_model_changes": [],
            "api_changes": [],
            "frontend_changes": ["Add ThemeToggle component"],
            "integration_points": ["Settings page"],
        },
        "tasks": [
            {
                "id": 1,
                "title": "Create theme provider",
                "description": "Set up CSS variables and theme context",
                "depends_on": [],
                "parallel": True,
                "acceptance_criteria": ["Theme toggles between light and dark"],
                "estimated_files": 3,
            },
            {
                "id": 2,
                "title": "Add toggle UI",
                "description": "Add toggle switch to settings page",
                "depends_on": [1],
                "parallel": False,
                "acceptance_criteria": ["Toggle renders and changes theme"],
                "estimated_files": 2,
            },
        ],
        "test_plan": {
            "unit_tests": ["Theme provider returns correct CSS vars"],
            "integration_tests": ["Toggle switches theme for all components"],
            "e2e_tests": ["User can toggle dark mode from settings"],
            "edge_cases": ["System preference detection"],
        },
    }
    plan.update(overrides)
    return plan


class TestBuildPlanPrompt:
    def test_includes_primary_language(self) -> None:
        profile = _make_profile(primary_language="TypeScript")
        prompt = nightshift.build_plan_prompt(profile, "Add auth")
        assert "TypeScript" in prompt

    def test_includes_feature_description(self) -> None:
        profile = _make_profile()
        prompt = nightshift.build_plan_prompt(profile, "Build a REST API")
        assert "Build a REST API" in prompt

    def test_includes_frameworks(self) -> None:
        profile = _make_profile(frameworks=[nightshift.FrameworkInfo(name="Next.js", version="14.0.0")])
        prompt = nightshift.build_plan_prompt(profile, "Add auth")
        assert "Next.js (14.0.0)" in prompt

    def test_includes_framework_without_version(self) -> None:
        profile = _make_profile(frameworks=[nightshift.FrameworkInfo(name="Django", version="")])
        prompt = nightshift.build_plan_prompt(profile, "Add auth")
        assert "Django" in prompt

    def test_no_frameworks_shows_none(self) -> None:
        profile = _make_profile(frameworks=[])
        prompt = nightshift.build_plan_prompt(profile, "Add auth")
        assert "none detected" in prompt

    def test_includes_package_manager(self) -> None:
        profile = _make_profile(package_manager="pnpm")
        prompt = nightshift.build_plan_prompt(profile, "Add auth")
        assert "pnpm" in prompt

    def test_null_package_manager_shows_none(self) -> None:
        profile = _make_profile(package_manager=None)
        prompt = nightshift.build_plan_prompt(profile, "Add auth")
        assert "none detected" in prompt

    def test_includes_test_runner(self) -> None:
        profile = _make_profile(test_runner="jest")
        prompt = nightshift.build_plan_prompt(profile, "Add auth")
        assert "jest" in prompt

    def test_includes_instruction_files(self) -> None:
        profile = _make_profile(instruction_files=["CLAUDE.md", "AGENTS.md"])
        prompt = nightshift.build_plan_prompt(profile, "Add auth")
        assert "CLAUDE.md" in prompt
        assert "AGENTS.md" in prompt

    def test_includes_top_level_dirs(self) -> None:
        profile = _make_profile(top_level_dirs=["src", "tests", "docs"])
        prompt = nightshift.build_plan_prompt(profile, "Add auth")
        assert "src" in prompt
        assert "docs" in prompt

    def test_includes_monorepo_flag(self) -> None:
        profile = _make_profile(has_monorepo_markers=True)
        prompt = nightshift.build_plan_prompt(profile, "Add auth")
        assert "yes" in prompt

    def test_includes_total_files(self) -> None:
        profile = _make_profile(total_files=500)
        prompt = nightshift.build_plan_prompt(profile, "Add auth")
        assert "500" in prompt

    def test_includes_json_structure(self) -> None:
        profile = _make_profile()
        prompt = nightshift.build_plan_prompt(profile, "Add auth")
        assert '"feature"' in prompt
        assert '"architecture"' in prompt
        assert '"tasks"' in prompt
        assert '"test_plan"' in prompt


class TestValidatePlan:
    def test_valid_plan_passes(self) -> None:
        plan = _make_valid_plan_dict()
        valid, errors = nightshift.validate_plan(plan)
        assert valid is True
        assert errors == []

    def test_missing_feature(self) -> None:
        plan = _make_valid_plan_dict()
        del plan["feature"]
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("feature" in e for e in errors)

    def test_empty_feature(self) -> None:
        plan = _make_valid_plan_dict(feature="")
        valid, _errors = nightshift.validate_plan(plan)
        assert valid is False

    def test_missing_architecture(self) -> None:
        plan = _make_valid_plan_dict()
        del plan["architecture"]
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("architecture" in e for e in errors)

    def test_architecture_missing_overview(self) -> None:
        plan = _make_valid_plan_dict()
        arch = dict(plan["architecture"])  # type: ignore[arg-type]
        del arch["overview"]
        plan["architecture"] = arch
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("overview" in e for e in errors)

    def test_architecture_missing_list_field(self) -> None:
        plan = _make_valid_plan_dict()
        arch = dict(plan["architecture"])  # type: ignore[arg-type]
        arch["tech_choices"] = "not a list"
        plan["architecture"] = arch
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("tech_choices" in e for e in errors)

    def test_empty_tasks(self) -> None:
        plan = _make_valid_plan_dict(tasks=[])
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("tasks" in e for e in errors)

    def test_missing_tasks(self) -> None:
        plan = _make_valid_plan_dict()
        del plan["tasks"]
        valid, _errors = nightshift.validate_plan(plan)
        assert valid is False

    def test_task_missing_title(self) -> None:
        plan = _make_valid_plan_dict()
        tasks = list(plan["tasks"])  # type: ignore[arg-type]
        task = dict(tasks[0])
        del task["title"]
        tasks[0] = task
        plan["tasks"] = tasks
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("title" in e for e in errors)

    def test_task_missing_acceptance_criteria(self) -> None:
        plan = _make_valid_plan_dict()
        tasks = list(plan["tasks"])  # type: ignore[arg-type]
        task = dict(tasks[0])
        task["acceptance_criteria"] = []
        tasks[0] = task
        plan["tasks"] = tasks
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("acceptance" in e for e in errors)

    def test_task_invalid_id(self) -> None:
        plan = _make_valid_plan_dict()
        tasks = list(plan["tasks"])  # type: ignore[arg-type]
        task = dict(tasks[0])
        task["id"] = -1
        tasks[0] = task
        plan["tasks"] = tasks
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("positive integer" in e for e in errors)

    def test_duplicate_task_ids(self) -> None:
        plan = _make_valid_plan_dict()
        tasks = list(plan["tasks"])  # type: ignore[arg-type]
        task2 = dict(tasks[1])
        task2["id"] = 1  # duplicate
        task2["depends_on"] = []
        tasks[1] = task2
        plan["tasks"] = tasks
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("duplicate" in e for e in errors)

    def test_task_depends_on_itself(self) -> None:
        plan = _make_valid_plan_dict()
        tasks = list(plan["tasks"])  # type: ignore[arg-type]
        task = dict(tasks[0])
        task["depends_on"] = [1]
        tasks[0] = task
        plan["tasks"] = tasks
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("depends on itself" in e for e in errors)

    def test_task_depends_on_unknown_id(self) -> None:
        plan = _make_valid_plan_dict()
        tasks = list(plan["tasks"])  # type: ignore[arg-type]
        task = dict(tasks[1])
        task["depends_on"] = [99]
        tasks[1] = task
        plan["tasks"] = tasks
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("unknown task 99" in e for e in errors)

    def test_circular_dependency(self) -> None:
        plan = _make_valid_plan_dict()
        plan["tasks"] = [
            {
                "id": 1,
                "title": "Task A",
                "description": "Does A",
                "depends_on": [2],
                "parallel": False,
                "acceptance_criteria": ["A works"],
                "estimated_files": 1,
            },
            {
                "id": 2,
                "title": "Task B",
                "description": "Does B",
                "depends_on": [1],
                "parallel": False,
                "acceptance_criteria": ["B works"],
                "estimated_files": 1,
            },
        ]
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("circular" in e for e in errors)

    def test_missing_test_plan(self) -> None:
        plan = _make_valid_plan_dict()
        del plan["test_plan"]
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("test_plan" in e for e in errors)

    def test_test_plan_missing_field(self) -> None:
        plan = _make_valid_plan_dict()
        tp = dict(plan["test_plan"])  # type: ignore[arg-type]
        del tp["unit_tests"]
        plan["test_plan"] = tp
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("unit_tests" in e for e in errors)

    def test_task_negative_estimated_files(self) -> None:
        plan = _make_valid_plan_dict()
        tasks = list(plan["tasks"])  # type: ignore[arg-type]
        task = dict(tasks[0])
        task["estimated_files"] = -1
        tasks[0] = task
        plan["tasks"] = tasks
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("non-negative" in e for e in errors)

    def test_task_parallel_not_bool(self) -> None:
        plan = _make_valid_plan_dict()
        tasks = list(plan["tasks"])  # type: ignore[arg-type]
        task = dict(tasks[0])
        task["parallel"] = "yes"
        tasks[0] = task
        plan["tasks"] = tasks
        valid, errors = nightshift.validate_plan(plan)
        assert valid is False
        assert any("parallel" in e for e in errors)


class TestParsePlan:
    def test_parses_valid_json(self) -> None:
        plan_dict = _make_valid_plan_dict()
        raw = json.dumps(plan_dict)
        plan = nightshift.parse_plan(raw)
        assert plan is not None
        assert plan["feature"] == "Add dark mode"
        assert len(plan["tasks"]) == 2
        assert plan["tasks"][0]["title"] == "Create theme provider"

    def test_parses_json_in_markdown_fence(self) -> None:
        plan_dict = _make_valid_plan_dict()
        raw = f"Here is the plan:\n```json\n{json.dumps(plan_dict)}\n```\nDone."
        plan = nightshift.parse_plan(raw)
        assert plan is not None
        assert plan["feature"] == "Add dark mode"

    def test_parses_json_with_leading_text(self) -> None:
        plan_dict = _make_valid_plan_dict()
        raw = f"Here is the plan:\n{json.dumps(plan_dict)}"
        plan = nightshift.parse_plan(raw)
        assert plan is not None

    def test_returns_none_for_empty(self) -> None:
        assert nightshift.parse_plan("") is None

    def test_returns_none_for_invalid_json(self) -> None:
        assert nightshift.parse_plan("this is not json") is None

    def test_returns_none_for_invalid_plan(self) -> None:
        raw = json.dumps({"feature": ""})
        assert nightshift.parse_plan(raw) is None

    def test_typed_output(self) -> None:
        plan_dict = _make_valid_plan_dict()
        plan = nightshift.parse_plan(json.dumps(plan_dict))
        assert plan is not None
        assert isinstance(plan["architecture"]["overview"], str)
        assert isinstance(plan["tasks"][0]["depends_on"], list)
        assert isinstance(plan["test_plan"]["unit_tests"], list)


class TestExecutionOrder:
    def test_empty_tasks(self) -> None:
        assert nightshift.execution_order([]) == []

    def test_single_task(self) -> None:
        task = nightshift.PlanTask(
            id=1,
            title="A",
            description="A",
            depends_on=[],
            parallel=True,
            acceptance_criteria=["ok"],
            estimated_files=1,
        )
        waves = nightshift.execution_order([task])
        assert waves == [[1]]

    def test_two_parallel_tasks(self) -> None:
        t1 = nightshift.PlanTask(
            id=1,
            title="A",
            description="A",
            depends_on=[],
            parallel=True,
            acceptance_criteria=["ok"],
            estimated_files=1,
        )
        t2 = nightshift.PlanTask(
            id=2,
            title="B",
            description="B",
            depends_on=[],
            parallel=True,
            acceptance_criteria=["ok"],
            estimated_files=1,
        )
        waves = nightshift.execution_order([t1, t2])
        assert waves == [[1, 2]]

    def test_sequential_tasks(self) -> None:
        t1 = nightshift.PlanTask(
            id=1,
            title="A",
            description="A",
            depends_on=[],
            parallel=True,
            acceptance_criteria=["ok"],
            estimated_files=1,
        )
        t2 = nightshift.PlanTask(
            id=2,
            title="B",
            description="B",
            depends_on=[1],
            parallel=False,
            acceptance_criteria=["ok"],
            estimated_files=1,
        )
        waves = nightshift.execution_order([t1, t2])
        assert waves == [[1], [2]]

    def test_diamond_dependency(self) -> None:
        t1 = nightshift.PlanTask(
            id=1,
            title="A",
            description="A",
            depends_on=[],
            parallel=True,
            acceptance_criteria=["ok"],
            estimated_files=1,
        )
        t2 = nightshift.PlanTask(
            id=2,
            title="B",
            description="B",
            depends_on=[1],
            parallel=True,
            acceptance_criteria=["ok"],
            estimated_files=1,
        )
        t3 = nightshift.PlanTask(
            id=3,
            title="C",
            description="C",
            depends_on=[1],
            parallel=True,
            acceptance_criteria=["ok"],
            estimated_files=1,
        )
        t4 = nightshift.PlanTask(
            id=4,
            title="D",
            description="D",
            depends_on=[2, 3],
            parallel=False,
            acceptance_criteria=["ok"],
            estimated_files=1,
        )
        waves = nightshift.execution_order([t1, t2, t3, t4])
        assert waves == [[1], [2, 3], [4]]

    def test_circular_raises(self) -> None:
        t1 = nightshift.PlanTask(
            id=1,
            title="A",
            description="A",
            depends_on=[2],
            parallel=False,
            acceptance_criteria=["ok"],
            estimated_files=1,
        )
        t2 = nightshift.PlanTask(
            id=2,
            title="B",
            description="B",
            depends_on=[1],
            parallel=False,
            acceptance_criteria=["ok"],
            estimated_files=1,
        )
        with pytest.raises(ValueError, match="circular"):
            nightshift.execution_order([t1, t2])

    def test_complex_graph(self) -> None:
        """Tasks: 1 and 2 parallel, 3 depends on 1, 4 depends on 2, 5 depends on 3+4."""
        tasks = [
            nightshift.PlanTask(
                id=1,
                title="A",
                description="A",
                depends_on=[],
                parallel=True,
                acceptance_criteria=["ok"],
                estimated_files=1,
            ),
            nightshift.PlanTask(
                id=2,
                title="B",
                description="B",
                depends_on=[],
                parallel=True,
                acceptance_criteria=["ok"],
                estimated_files=1,
            ),
            nightshift.PlanTask(
                id=3,
                title="C",
                description="C",
                depends_on=[1],
                parallel=True,
                acceptance_criteria=["ok"],
                estimated_files=1,
            ),
            nightshift.PlanTask(
                id=4,
                title="D",
                description="D",
                depends_on=[2],
                parallel=True,
                acceptance_criteria=["ok"],
                estimated_files=1,
            ),
            nightshift.PlanTask(
                id=5,
                title="E",
                description="E",
                depends_on=[3, 4],
                parallel=False,
                acceptance_criteria=["ok"],
                estimated_files=1,
            ),
        ]
        waves = nightshift.execution_order(tasks)
        assert waves == [[1, 2], [3, 4], [5]]


class TestFormatPlan:
    def test_includes_feature_name(self) -> None:
        plan_dict = _make_valid_plan_dict()
        plan = nightshift.parse_plan(json.dumps(plan_dict))
        assert plan is not None
        md = nightshift.format_plan(plan)
        assert "Add dark mode" in md

    def test_includes_architecture_overview(self) -> None:
        plan_dict = _make_valid_plan_dict()
        plan = nightshift.parse_plan(json.dumps(plan_dict))
        assert plan is not None
        md = nightshift.format_plan(plan)
        assert "dark mode toggle" in md

    def test_includes_wave_numbers(self) -> None:
        plan_dict = _make_valid_plan_dict()
        plan = nightshift.parse_plan(json.dumps(plan_dict))
        assert plan is not None
        md = nightshift.format_plan(plan)
        assert "Wave 1" in md
        assert "Wave 2" in md

    def test_includes_task_details(self) -> None:
        plan_dict = _make_valid_plan_dict()
        plan = nightshift.parse_plan(json.dumps(plan_dict))
        assert plan is not None
        md = nightshift.format_plan(plan)
        assert "Create theme provider" in md
        assert "Add toggle UI" in md
        assert "parallel" in md.lower() or "sequential" in md.lower()

    def test_includes_test_plan(self) -> None:
        plan_dict = _make_valid_plan_dict()
        plan = nightshift.parse_plan(json.dumps(plan_dict))
        assert plan is not None
        md = nightshift.format_plan(plan)
        assert "Test Plan" in md
        assert "Unit Tests" in md

    def test_shows_dependencies(self) -> None:
        plan_dict = _make_valid_plan_dict()
        plan = nightshift.parse_plan(json.dumps(plan_dict))
        assert plan is not None
        md = nightshift.format_plan(plan)
        assert "depends on" in md

    def test_skips_empty_sections(self) -> None:
        plan_dict = _make_valid_plan_dict()
        arch = dict(plan_dict["architecture"])  # type: ignore[arg-type]
        arch["data_model_changes"] = []
        plan_dict["architecture"] = arch
        plan = nightshift.parse_plan(json.dumps(plan_dict))
        assert plan is not None
        md = nightshift.format_plan(plan)
        assert "Data Model Changes" not in md


class TestScopeCheck:
    def test_within_limits(self) -> None:
        plan_dict = _make_valid_plan_dict()
        plan = nightshift.parse_plan(json.dumps(plan_dict))
        assert plan is not None
        assert nightshift.scope_check(plan) is None

    def test_too_many_tasks(self) -> None:
        plan_dict = _make_valid_plan_dict()
        tasks = []
        for i in range(1, 12):
            tasks.append(
                {
                    "id": i,
                    "title": f"Task {i}",
                    "description": f"Does {i}",
                    "depends_on": [],
                    "parallel": True,
                    "acceptance_criteria": [f"Task {i} works"],
                    "estimated_files": 2,
                }
            )
        plan_dict["tasks"] = tasks
        plan = nightshift.parse_plan(json.dumps(plan_dict))
        assert plan is not None
        warning = nightshift.scope_check(plan)
        assert warning is not None
        assert "11 tasks" in warning

    def test_too_many_files(self) -> None:
        plan_dict = _make_valid_plan_dict()
        tasks = list(plan_dict["tasks"])  # type: ignore[arg-type]
        task = dict(tasks[0])
        task["estimated_files"] = 60
        tasks[0] = task
        plan_dict["tasks"] = tasks
        plan = nightshift.parse_plan(json.dumps(plan_dict))
        assert plan is not None
        warning = nightshift.scope_check(plan)
        assert warning is not None
        assert "files" in warning


class TestPlanFeatureCLI:
    def test_dry_run_prints_prompt(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = nightshift.build_parser()
        args = parser.parse_args(["plan", "Add dark mode", "--dry-run"])
        result = args.func(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Feature Request" in captured.out
        assert "Add dark mode" in captured.out

    def test_default_prints_prompt(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = nightshift.build_parser()
        args = parser.parse_args(["plan", "Add auth"])
        result = args.func(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Add auth" in captured.out

    def test_result_file_parses_plan(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        plan_dict = _make_valid_plan_dict()
        result_file = tmp_path / "plan.json"
        result_file.write_text(json.dumps(plan_dict), encoding="utf-8")
        parser = nightshift.build_parser()
        args = parser.parse_args(
            [
                "plan",
                "Add dark mode",
                "--result-file",
                str(result_file),
            ]
        )
        result = args.func(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Add dark mode" in captured.out
        assert "Wave 1" in captured.out

    def test_result_file_not_found(self, tmp_path: Path) -> None:
        parser = nightshift.build_parser()
        args = parser.parse_args(
            [
                "plan",
                "Add auth",
                "--result-file",
                str(tmp_path / "nonexistent.json"),
            ]
        )
        with pytest.raises(nightshift.NightshiftError, match="not found"):
            args.func(args)

    def test_result_file_invalid_plan(self, tmp_path: Path) -> None:
        result_file = tmp_path / "bad.json"
        result_file.write_text('{"not": "a plan"}', encoding="utf-8")
        parser = nightshift.build_parser()
        args = parser.parse_args(
            [
                "plan",
                "Add auth",
                "--result-file",
                str(result_file),
            ]
        )
        with pytest.raises(nightshift.NightshiftError, match="Could not parse"):
            args.func(args)


class TestPlanCommandForAgent:
    def test_claude_command(self) -> None:
        cmd = nightshift.plan_command_for_agent("claude", "Plan something")
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "Plan something" in cmd
        max_turns_idx = cmd.index("--max-turns")
        assert cmd[max_turns_idx + 1] == str(nightshift.PLAN_AGENT_MAX_TURNS)

    def test_codex_command(self) -> None:
        cmd = nightshift.plan_command_for_agent("codex", "Plan something")
        assert cmd[0] == "codex"
        assert "exec" in cmd
        assert "Plan something" in cmd

    def test_unsupported_agent_raises(self) -> None:
        with pytest.raises(nightshift.NightshiftError, match="Unsupported agent"):
            nightshift.plan_command_for_agent("gpt4", "Plan something")


class TestRunPlanAgent:
    def _fake_profile(self) -> nightshift.RepoProfile:
        return nightshift.RepoProfile(
            languages={"Python": 10},
            primary_language="Python",
            frameworks=[],
            package_manager=None,
            test_runner=None,
            instruction_files=[],
            top_level_dirs=["src"],
            has_monorepo_markers=False,
            total_files=10,
        )

    def test_agent_not_installed_raises(self, tmp_path: Path) -> None:
        with (
            patch("nightshift.planner.command_exists", return_value=False),
            pytest.raises(nightshift.NightshiftError, match="not installed"),
        ):
            nightshift.run_plan_agent(tmp_path, "Add auth", "claude", self._fake_profile())

    def test_agent_nonzero_exit_raises(self, tmp_path: Path) -> None:
        with (
            patch("nightshift.planner.command_exists", return_value=True),
            patch("nightshift.planner.run_command", return_value=(1, "error output")),
            pytest.raises(nightshift.NightshiftError, match="exited with code 1"),
        ):
            nightshift.run_plan_agent(tmp_path, "Add auth", "claude", self._fake_profile())

    def test_agent_unparseable_output_raises(self, tmp_path: Path) -> None:
        with (
            patch("nightshift.planner.command_exists", return_value=True),
            patch("nightshift.planner.run_command", return_value=(0, "not valid json")),
            pytest.raises(nightshift.NightshiftError, match="could not be parsed"),
        ):
            nightshift.run_plan_agent(tmp_path, "Add auth", "claude", self._fake_profile())

    def test_agent_success_returns_plan(self, tmp_path: Path) -> None:
        plan_dict = _make_valid_plan_dict()
        raw_output = json.dumps(plan_dict)
        with (
            patch("nightshift.planner.command_exists", return_value=True),
            patch("nightshift.planner.run_command", return_value=(0, raw_output)),
        ):
            plan = nightshift.run_plan_agent(tmp_path, "Add dark mode", "claude", self._fake_profile())
        assert plan["feature"] == "Add dark mode"
        assert len(plan["tasks"]) == 2

    def test_agent_invoked_with_correct_cwd(self, tmp_path: Path) -> None:
        plan_dict = _make_valid_plan_dict()
        raw_output = json.dumps(plan_dict)
        with (
            patch("nightshift.planner.command_exists", return_value=True),
            patch("nightshift.planner.run_command", return_value=(0, raw_output)) as mock_run,
        ):
            nightshift.run_plan_agent(tmp_path, "Add dark mode", "claude", self._fake_profile())
        _, kwargs = mock_run.call_args
        assert kwargs["cwd"] == tmp_path

    def test_agent_invoked_with_timeout(self, tmp_path: Path) -> None:
        plan_dict = _make_valid_plan_dict()
        raw_output = json.dumps(plan_dict)
        with (
            patch("nightshift.planner.command_exists", return_value=True),
            patch("nightshift.planner.run_command", return_value=(0, raw_output)) as mock_run,
        ):
            nightshift.run_plan_agent(tmp_path, "Add dark mode", "claude", self._fake_profile())
        _, kwargs = mock_run.call_args
        assert kwargs["timeout_seconds"] == nightshift.PLAN_AGENT_TIMEOUT


class TestPlanFeatureCLIWithAgent:
    def test_agent_invokes_and_displays_plan(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        plan_dict = _make_valid_plan_dict()
        raw_output = json.dumps(plan_dict)
        with (
            patch("nightshift.planner.command_exists", return_value=True),
            patch("nightshift.planner.run_command", return_value=(0, raw_output)),
        ):
            parser = nightshift.build_parser()
            args = parser.parse_args(["plan", "Add dark mode", "--agent", "claude"])
            result = args.func(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Add dark mode" in captured.out
        assert "Wave 1" in captured.out

    def test_agent_displays_scope_warning(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        plan_dict = _make_valid_plan_dict()
        tasks = list(plan_dict["tasks"])  # type: ignore[arg-type]
        task = dict(tasks[0])  # type: ignore[arg-type]
        task["estimated_files"] = 60
        tasks[0] = task
        plan_dict["tasks"] = tasks
        raw_output = json.dumps(plan_dict)
        with (
            patch("nightshift.planner.command_exists", return_value=True),
            patch("nightshift.planner.run_command", return_value=(0, raw_output)),
        ):
            parser = nightshift.build_parser()
            args = parser.parse_args(["plan", "Add dark mode", "--agent", "claude"])
            result = args.func(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    def test_dry_run_skips_agent(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = nightshift.build_parser()
        args = parser.parse_args(["plan", "Add auth", "--agent", "claude", "--dry-run"])
        result = args.func(args)
        assert result == 0
        captured = capsys.readouterr()
        # dry-run prints the prompt, not a formatted plan
        assert "Feature Request" in captured.out

    def test_result_file_takes_precedence_over_agent(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        plan_dict = _make_valid_plan_dict()
        result_file = tmp_path / "plan.json"
        result_file.write_text(json.dumps(plan_dict), encoding="utf-8")
        parser = nightshift.build_parser()
        args = parser.parse_args(
            [
                "plan",
                "Add dark mode",
                "--agent",
                "claude",
                "--result-file",
                str(result_file),
            ]
        )
        # No mocking needed -- result-file path is checked before agent path
        result = args.func(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Wave 1" in captured.out


# ---------------------------------------------------------------------------
# Task Decomposer
# ---------------------------------------------------------------------------


def _make_feature_plan(**overrides: object) -> nightshift.FeaturePlan:
    """Build a minimal typed FeaturePlan for decomposer tests."""
    defaults: dict[str, object] = {
        "feature": "Add dark mode",
        "architecture": nightshift.ArchitectureDoc(
            overview="Add a dark mode toggle to the settings page.",
            tech_choices=["Use CSS variables for theming"],
            data_model_changes=[],
            api_changes=[],
            frontend_changes=["Add ThemeToggle component"],
            integration_points=["Settings page"],
        ),
        "tasks": [
            nightshift.PlanTask(
                id=1,
                title="Create theme provider",
                description="Set up CSS variables and theme context",
                depends_on=[],
                parallel=True,
                acceptance_criteria=["Theme toggles between light and dark"],
                estimated_files=3,
            ),
            nightshift.PlanTask(
                id=2,
                title="Add toggle UI",
                description="Add toggle switch to settings page",
                depends_on=[1],
                parallel=False,
                acceptance_criteria=["Toggle renders and changes theme"],
                estimated_files=2,
            ),
        ],
        "test_plan": nightshift.TestPlan(
            unit_tests=["Theme provider returns correct CSS vars"],
            integration_tests=["Toggle switches theme for all components"],
            e2e_tests=["User can toggle dark mode from settings"],
            edge_cases=["System preference detection"],
        ),
    }
    defaults.update(overrides)
    return nightshift.FeaturePlan(**defaults)  # type: ignore[arg-type]


class TestBuildWorkOrderPrompt:
    def test_includes_primary_language(self) -> None:
        profile = _make_profile(primary_language="TypeScript")
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "TypeScript" in prompt

    def test_includes_feature_name(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan(feature="Build auth system")
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "Build auth system" in prompt

    def test_includes_task_title(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "Create theme provider" in prompt

    def test_includes_task_description(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "Set up CSS variables and theme context" in prompt

    def test_includes_acceptance_criteria(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "Theme toggles between light and dark" in prompt

    def test_includes_architecture_overview(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "dark mode toggle to the settings page" in prompt

    def test_includes_frameworks(self) -> None:
        profile = _make_profile(frameworks=[nightshift.FrameworkInfo(name="React", version="18.0")])
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "React (18.0)" in prompt

    def test_framework_without_version(self) -> None:
        profile = _make_profile(frameworks=[nightshift.FrameworkInfo(name="Express", version="")])
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "Express" in prompt

    def test_no_frameworks(self) -> None:
        profile = _make_profile(frameworks=[])
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "none detected" in prompt

    def test_includes_test_runner(self) -> None:
        profile = _make_profile(test_runner="jest")
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "jest" in prompt

    def test_no_test_runner(self) -> None:
        profile = _make_profile(test_runner=None)
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "none detected" in prompt

    def test_includes_package_manager(self) -> None:
        profile = _make_profile(package_manager="pnpm")
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "pnpm" in prompt

    def test_no_package_manager(self) -> None:
        profile = _make_profile(package_manager=None)
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "none detected" in prompt

    def test_includes_instruction_files(self) -> None:
        profile = _make_profile(instruction_files=["CLAUDE.md", "AGENTS.md"])
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "CLAUDE.md" in prompt
        assert "AGENTS.md" in prompt

    def test_no_instruction_files(self) -> None:
        profile = _make_profile(instruction_files=[])
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "none" in prompt

    def test_includes_estimated_files(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "3" in prompt

    def test_includes_task_id(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "Task 1" in prompt

    def test_no_deps_shows_no_dependencies(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        task = plan["tasks"][0]  # task 1 has no deps
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "no dependencies" in prompt

    def test_with_deps_shows_dependency_context(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        task = plan["tasks"][1]  # task 2 depends on task 1
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert "depends on" in prompt.lower()
        assert "Create theme provider" in prompt

    def test_includes_json_output_schema(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        assert '"task_id"' in prompt
        assert '"status"' in prompt
        assert '"done"' in prompt
        assert '"blocked"' in prompt

    def test_json_examples_have_single_braces(self) -> None:
        """Verify JSON examples use { } not {{ }} (brace escaping correctness)."""
        profile = _make_profile()
        plan = _make_feature_plan()
        task = plan["tasks"][0]
        prompt = nightshift.build_work_order_prompt(task, plan, profile)
        # The prompt should contain valid JSON examples with single braces
        assert "{\n" in prompt
        assert "}" in prompt
        # Double braces would mean the .format() escaping is wrong
        assert "{{\n" not in prompt

    def test_multiple_acceptance_criteria(self) -> None:
        tasks = [
            nightshift.PlanTask(
                id=1,
                title="Multi-criteria task",
                description="Has many criteria",
                depends_on=[],
                parallel=True,
                acceptance_criteria=["Criterion A", "Criterion B", "Criterion C"],
                estimated_files=2,
            ),
        ]
        plan = _make_feature_plan(tasks=tasks)
        profile = _make_profile()
        prompt = nightshift.build_work_order_prompt(tasks[0], plan, profile)
        assert "1. Criterion A" in prompt
        assert "2. Criterion B" in prompt
        assert "3. Criterion C" in prompt


class TestDecomposePlan:
    def test_basic_two_task_plan(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        assert result["feature"] == "Add dark mode"
        assert result["total_waves"] == 2
        assert result["total_tasks"] == 2
        assert len(result["waves"]) == 2

    def test_wave_1_contains_independent_task(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        wave1 = result["waves"][0]
        assert len(wave1) == 1
        assert wave1[0]["task_id"] == 1

    def test_wave_2_contains_dependent_task(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        wave2 = result["waves"][1]
        assert len(wave2) == 1
        assert wave2[0]["task_id"] == 2

    def test_work_order_has_prompt(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        order = result["waves"][0][0]
        assert len(order["prompt"]) > 100

    def test_work_order_has_schema_path(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        order = result["waves"][0][0]
        assert order["schema_path"] == "schemas/task.schema.json"

    def test_work_order_has_acceptance_criteria(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        order = result["waves"][0][0]
        assert order["acceptance_criteria"] == ["Theme toggles between light and dark"]

    def test_work_order_has_estimated_files(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        order = result["waves"][0][0]
        assert order["estimated_files"] == 3

    def test_work_order_has_wave_number(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        assert result["waves"][0][0]["wave"] == 1
        assert result["waves"][1][0]["wave"] == 2

    def test_work_order_has_depends_on(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        assert result["waves"][0][0]["depends_on"] == []
        assert result["waves"][1][0]["depends_on"] == [1]

    def test_work_order_has_title(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        assert result["waves"][0][0]["title"] == "Create theme provider"
        assert result["waves"][1][0]["title"] == "Add toggle UI"

    def test_parallel_tasks_in_same_wave(self) -> None:
        tasks = [
            nightshift.PlanTask(
                id=1,
                title="Task A",
                description="First parallel task",
                depends_on=[],
                parallel=True,
                acceptance_criteria=["A works"],
                estimated_files=2,
            ),
            nightshift.PlanTask(
                id=2,
                title="Task B",
                description="Second parallel task",
                depends_on=[],
                parallel=True,
                acceptance_criteria=["B works"],
                estimated_files=3,
            ),
            nightshift.PlanTask(
                id=3,
                title="Task C",
                description="Depends on both",
                depends_on=[1, 2],
                parallel=False,
                acceptance_criteria=["C works"],
                estimated_files=1,
            ),
        ]
        plan = _make_feature_plan(tasks=tasks)
        profile = _make_profile()
        result = nightshift.decompose_plan(plan, profile)
        assert result["total_waves"] == 2
        assert len(result["waves"][0]) == 2
        assert len(result["waves"][1]) == 1
        wave1_ids = [o["task_id"] for o in result["waves"][0]]
        assert wave1_ids == [1, 2]

    def test_three_wave_chain(self) -> None:
        tasks = [
            nightshift.PlanTask(
                id=1,
                title="Foundation",
                description="Build foundation",
                depends_on=[],
                parallel=True,
                acceptance_criteria=["Foundation done"],
                estimated_files=2,
            ),
            nightshift.PlanTask(
                id=2,
                title="Middle",
                description="Build on foundation",
                depends_on=[1],
                parallel=False,
                acceptance_criteria=["Middle done"],
                estimated_files=2,
            ),
            nightshift.PlanTask(
                id=3,
                title="Final",
                description="Build on middle",
                depends_on=[2],
                parallel=False,
                acceptance_criteria=["Final done"],
                estimated_files=1,
            ),
        ]
        plan = _make_feature_plan(tasks=tasks)
        profile = _make_profile()
        result = nightshift.decompose_plan(plan, profile)
        assert result["total_waves"] == 3
        assert result["waves"][0][0]["task_id"] == 1
        assert result["waves"][1][0]["task_id"] == 2
        assert result["waves"][2][0]["task_id"] == 3

    def test_single_task_plan(self) -> None:
        tasks = [
            nightshift.PlanTask(
                id=1,
                title="Only task",
                description="The one and only",
                depends_on=[],
                parallel=True,
                acceptance_criteria=["It works"],
                estimated_files=1,
            ),
        ]
        plan = _make_feature_plan(tasks=tasks)
        profile = _make_profile()
        result = nightshift.decompose_plan(plan, profile)
        assert result["total_waves"] == 1
        assert result["total_tasks"] == 1
        assert len(result["waves"]) == 1
        assert len(result["waves"][0]) == 1

    def test_circular_deps_raises(self) -> None:
        tasks = [
            nightshift.PlanTask(
                id=1,
                title="A",
                description="depends on B",
                depends_on=[2],
                parallel=False,
                acceptance_criteria=["A done"],
                estimated_files=1,
            ),
            nightshift.PlanTask(
                id=2,
                title="B",
                description="depends on A",
                depends_on=[1],
                parallel=False,
                acceptance_criteria=["B done"],
                estimated_files=1,
            ),
        ]
        plan = _make_feature_plan(tasks=tasks)
        profile = _make_profile()
        with pytest.raises(ValueError, match="circular"):
            nightshift.decompose_plan(plan, profile)

    def test_empty_tasks_returns_empty_waves(self) -> None:
        plan = _make_feature_plan(tasks=[])
        profile = _make_profile()
        result = nightshift.decompose_plan(plan, profile)
        assert result["total_waves"] == 0
        assert result["total_tasks"] == 0
        assert result["waves"] == []

    def test_prompts_contain_repo_context(self) -> None:
        profile = _make_profile(
            primary_language="Go",
            test_runner="go test",
            package_manager="go mod",
        )
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        prompt = result["waves"][0][0]["prompt"]
        assert "Go" in prompt
        assert "go test" in prompt
        assert "go mod" in prompt

    def test_preserves_acceptance_criteria_order(self) -> None:
        tasks = [
            nightshift.PlanTask(
                id=1,
                title="Ordered",
                description="Has ordered criteria",
                depends_on=[],
                parallel=True,
                acceptance_criteria=["First", "Second", "Third"],
                estimated_files=1,
            ),
        ]
        plan = _make_feature_plan(tasks=tasks)
        profile = _make_profile()
        result = nightshift.decompose_plan(plan, profile)
        assert result["waves"][0][0]["acceptance_criteria"] == ["First", "Second", "Third"]


class TestFormatWorkOrders:
    def test_includes_feature_name(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        output = nightshift.format_work_orders(result)
        assert "Add dark mode" in output

    def test_includes_wave_headers(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        output = nightshift.format_work_orders(result)
        assert "## Wave 1" in output
        assert "## Wave 2" in output

    def test_includes_task_titles(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        output = nightshift.format_work_orders(result)
        assert "Create theme provider" in output
        assert "Add toggle UI" in output

    def test_includes_estimated_files(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        output = nightshift.format_work_orders(result)
        assert "Estimated files: 3" in output
        assert "Estimated files: 2" in output

    def test_includes_schema_path(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        output = nightshift.format_work_orders(result)
        assert "schemas/task.schema.json" in output

    def test_includes_acceptance_criteria(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        output = nightshift.format_work_orders(result)
        assert "Theme toggles between light and dark" in output
        assert "Toggle renders and changes theme" in output

    def test_includes_dependency_info(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        output = nightshift.format_work_orders(result)
        assert "after: 1" in output

    def test_includes_total_counts(self) -> None:
        profile = _make_profile()
        plan = _make_feature_plan()
        result = nightshift.decompose_plan(plan, profile)
        output = nightshift.format_work_orders(result)
        assert "Total waves: 2" in output
        assert "Total tasks: 2" in output

    def test_includes_parallel_count(self) -> None:
        tasks = [
            nightshift.PlanTask(
                id=1,
                title="A",
                description="a",
                depends_on=[],
                parallel=True,
                acceptance_criteria=["done"],
                estimated_files=1,
            ),
            nightshift.PlanTask(
                id=2,
                title="B",
                description="b",
                depends_on=[],
                parallel=True,
                acceptance_criteria=["done"],
                estimated_files=1,
            ),
        ]
        plan = _make_feature_plan(tasks=tasks)
        profile = _make_profile()
        result = nightshift.decompose_plan(plan, profile)
        output = nightshift.format_work_orders(result)
        assert "2 task(s)" in output

    def test_empty_result(self) -> None:
        plan = _make_feature_plan(tasks=[])
        profile = _make_profile()
        result = nightshift.decompose_plan(plan, profile)
        output = nightshift.format_work_orders(result)
        assert "Total waves: 0" in output
        assert "Total tasks: 0" in output


# --- Sub-agent spawner -------------------------------------------------------


def _make_work_order(**overrides: object) -> nightshift.WorkOrder:
    """Build a minimal WorkOrder for testing, with overrides."""
    defaults: dict[str, object] = {
        "task_id": 1,
        "wave": 1,
        "title": "Create theme provider",
        "prompt": "Build a theme provider component.",
        "acceptance_criteria": ["Theme toggles between light and dark"],
        "estimated_files": 3,
        "depends_on": [],
        "schema_path": "schemas/task.schema.json",
    }
    defaults.update(overrides)
    return nightshift.WorkOrder(**defaults)  # type: ignore[arg-type]


def _make_done_json(task_id: int = 1) -> str:
    """Return valid JSON for a done TaskCompletion."""
    import json

    return json.dumps(
        {
            "task_id": task_id,
            "status": "done",
            "files_created": ["src/theme.ts"],
            "files_modified": ["src/app.ts"],
            "tests_written": ["theme provider renders"],
            "tests_passed": True,
            "notes": "All good",
        }
    )


def _make_blocked_json(task_id: int = 1) -> str:
    """Return valid JSON for a blocked TaskCompletion."""
    import json

    return json.dumps(
        {
            "task_id": task_id,
            "status": "blocked",
            "files_created": [],
            "files_modified": [],
            "tests_written": [],
            "tests_passed": False,
            "notes": "Missing dependency",
        }
    )


class TestBuildSubagentCommand:
    def test_codex_command(self) -> None:
        from nightshift.subagent import _build_subagent_command

        cmd = _build_subagent_command(
            agent="codex",
            prompt="Build X",
            cwd=Path("/tmp/repo"),
            message_path=Path("/tmp/logs/task-1.msg.json"),
            schema_path="schemas/task.schema.json",
        )
        assert cmd[0] == "codex"
        assert "exec" in cmd
        assert "--json" in cmd
        assert "--output-schema" in cmd
        assert str(Path("/tmp/repo/schemas/task.schema.json")) in cmd
        assert "Build X" in cmd

    def test_claude_command(self) -> None:
        from nightshift.subagent import _build_subagent_command

        cmd = _build_subagent_command(
            agent="claude",
            prompt="Build X",
            cwd=Path("/tmp/repo"),
            message_path=Path("/tmp/logs/task-1.msg.json"),
            schema_path="schemas/task.schema.json",
        )
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "Build X" in cmd
        assert "--max-turns" in cmd

    def test_claude_uses_configured_max_turns(self) -> None:
        from nightshift.subagent import _build_subagent_command

        cmd = _build_subagent_command(
            agent="claude",
            prompt="Build X",
            cwd=Path("/tmp/repo"),
            message_path=Path("/tmp/logs/task-1.msg.json"),
            schema_path="schemas/task.schema.json",
        )
        turns_idx = cmd.index("--max-turns")
        assert cmd[turns_idx + 1] == str(nightshift.SUBAGENT_MAX_TURNS)

    def test_unsupported_agent_raises(self) -> None:
        from nightshift.subagent import _build_subagent_command

        with pytest.raises(nightshift.NightshiftError, match="Unsupported agent"):
            _build_subagent_command(
                agent="gemini",
                prompt="Build X",
                cwd=Path("/tmp/repo"),
                message_path=Path("/tmp/logs/task-1.msg.json"),
                schema_path="schemas/task.schema.json",
            )

    def test_codex_message_path(self) -> None:
        from nightshift.subagent import _build_subagent_command

        msg = Path("/tmp/logs/task-42.msg.json")
        cmd = _build_subagent_command(
            agent="codex",
            prompt="Build X",
            cwd=Path("/tmp/repo"),
            message_path=msg,
            schema_path="schemas/task.schema.json",
        )
        assert "--output-last-message" in cmd
        assert str(msg) in cmd

    def test_codex_uses_work_order_schema_path(self) -> None:
        from nightshift.subagent import _build_subagent_command

        cmd = _build_subagent_command(
            agent="codex",
            prompt="Build X",
            cwd=Path("/tmp/repo"),
            message_path=Path("/tmp/logs/task-1.msg.json"),
            schema_path="custom/schema.json",
        )
        assert str(Path("/tmp/repo/custom/schema.json")) in cmd


class TestValidateTaskCompletion:
    def test_valid_done(self) -> None:
        from nightshift.subagent import _validate_task_completion

        data = {
            "task_id": 1,
            "status": "done",
            "files_created": [],
            "files_modified": [],
            "tests_written": [],
            "tests_passed": True,
            "notes": "",
        }
        assert _validate_task_completion(data, 1) is True

    def test_valid_blocked(self) -> None:
        from nightshift.subagent import _validate_task_completion

        data = {
            "task_id": 2,
            "status": "blocked",
            "files_created": [],
            "files_modified": [],
            "tests_written": [],
            "tests_passed": False,
            "notes": "stuck",
        }
        assert _validate_task_completion(data, 2) is True

    def test_missing_key(self) -> None:
        from nightshift.subagent import _validate_task_completion

        data = {"task_id": 1, "status": "done"}
        assert _validate_task_completion(data, 1) is False

    def test_wrong_task_id(self) -> None:
        from nightshift.subagent import _validate_task_completion

        data = {
            "task_id": 99,
            "status": "done",
            "files_created": [],
            "files_modified": [],
            "tests_written": [],
            "tests_passed": True,
            "notes": "",
        }
        assert _validate_task_completion(data, 1) is False

    def test_invalid_status(self) -> None:
        from nightshift.subagent import _validate_task_completion

        data = {
            "task_id": 1,
            "status": "partial",
            "files_created": [],
            "files_modified": [],
            "tests_written": [],
            "tests_passed": True,
            "notes": "",
        }
        assert _validate_task_completion(data, 1) is False

    def test_string_instead_of_list(self) -> None:
        from nightshift.subagent import _validate_task_completion

        data = {
            "task_id": 1,
            "status": "done",
            "files_created": "src/foo.ts",
            "files_modified": [],
            "tests_written": [],
            "tests_passed": True,
            "notes": "",
        }
        assert _validate_task_completion(data, 1) is False


class TestParseTaskCompletion:
    def test_parses_valid_done(self) -> None:
        from nightshift.subagent import _parse_task_completion

        result = _parse_task_completion(_make_done_json(1), 1)
        assert result is not None
        assert result["task_id"] == 1
        assert result["status"] == "done"
        assert result["files_created"] == ["src/theme.ts"]
        assert result["tests_passed"] is True

    def test_parses_valid_blocked(self) -> None:
        from nightshift.subagent import _parse_task_completion

        result = _parse_task_completion(_make_blocked_json(2), 2)
        assert result is not None
        assert result["task_id"] == 2
        assert result["status"] == "blocked"
        assert result["notes"] == "Missing dependency"

    def test_returns_none_for_garbage(self) -> None:
        from nightshift.subagent import _parse_task_completion

        assert _parse_task_completion("not json at all", 1) is None

    def test_returns_none_for_empty(self) -> None:
        from nightshift.subagent import _parse_task_completion

        assert _parse_task_completion("", 1) is None

    def test_returns_none_for_wrong_task_id(self) -> None:
        from nightshift.subagent import _parse_task_completion

        result = _parse_task_completion(_make_done_json(99), 1)
        assert result is None

    def test_parses_json_in_fences(self) -> None:
        from nightshift.subagent import _parse_task_completion

        fenced = "```json\n" + _make_done_json(1) + "\n```"
        result = _parse_task_completion(fenced, 1)
        assert result is not None
        assert result["status"] == "done"

    def test_parses_json_with_leading_text(self) -> None:
        from nightshift.subagent import _parse_task_completion

        with_text = "Here is my output:\n" + _make_done_json(1)
        result = _parse_task_completion(with_text, 1)
        assert result is not None
        assert result["status"] == "done"


class TestMakeErrorCompletion:
    def test_creates_blocked_completion(self) -> None:
        from nightshift.subagent import _make_error_completion

        result = _make_error_completion(5, "Agent crashed")
        assert result["task_id"] == 5
        assert result["status"] == "blocked"
        assert result["notes"] == "Agent crashed"
        assert result["files_created"] == []
        assert result["tests_passed"] is False


class TestSpawnTask:
    def test_returns_parsed_completion_on_success(self, tmp_path: Path) -> None:
        done_json = _make_done_json(1)
        order = _make_work_order()
        log_dir = tmp_path / "logs"

        with patch("nightshift.subagent.run_command", return_value=(0, done_json)):
            result = nightshift.spawn_task(
                order,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=log_dir,
            )

        assert result is not None
        assert result["task_id"] == 1
        assert result["status"] == "done"

    def test_returns_none_on_unparseable_output(self, tmp_path: Path) -> None:
        order = _make_work_order()
        log_dir = tmp_path / "logs"

        with patch("nightshift.subagent.run_command", return_value=(0, "garbage output")):
            result = nightshift.spawn_task(
                order,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=log_dir,
            )

        assert result is None

    def test_returns_blocked_on_agent_blocked(self, tmp_path: Path) -> None:
        blocked_json = _make_blocked_json(1)
        order = _make_work_order()
        log_dir = tmp_path / "logs"

        with patch("nightshift.subagent.run_command", return_value=(0, blocked_json)):
            result = nightshift.spawn_task(
                order,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=log_dir,
            )

        assert result is not None
        assert result["status"] == "blocked"

    def test_nonzero_exit_still_parses(self, tmp_path: Path) -> None:
        done_json = _make_done_json(1)
        order = _make_work_order()
        log_dir = tmp_path / "logs"

        with patch("nightshift.subagent.run_command", return_value=(1, done_json)):
            result = nightshift.spawn_task(
                order,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=log_dir,
            )

        assert result is not None
        assert result["status"] == "done"

    def test_creates_log_dir(self, tmp_path: Path) -> None:
        order = _make_work_order()
        log_dir = tmp_path / "deep" / "nested" / "logs"

        with patch("nightshift.subagent.run_command", return_value=(0, _make_done_json(1))):
            nightshift.spawn_task(
                order,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=log_dir,
            )

        assert log_dir.exists()

    def test_uses_custom_timeout(self, tmp_path: Path) -> None:
        order = _make_work_order()
        log_dir = tmp_path / "logs"

        with patch("nightshift.subagent.run_command", return_value=(0, _make_done_json(1))) as mock_run:
            nightshift.spawn_task(
                order,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=log_dir,
                timeout_seconds=120,
            )

        _, kwargs = mock_run.call_args
        assert kwargs["timeout_seconds"] == 120

    def test_uses_default_timeout(self, tmp_path: Path) -> None:
        order = _make_work_order()
        log_dir = tmp_path / "logs"

        with patch("nightshift.subagent.run_command", return_value=(0, _make_done_json(1))) as mock_run:
            nightshift.spawn_task(
                order,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=log_dir,
            )

        _, kwargs = mock_run.call_args
        assert kwargs["timeout_seconds"] == nightshift.SUBAGENT_DEFAULT_TIMEOUT

    def test_codex_reads_message_file(self, tmp_path: Path) -> None:
        order = _make_work_order()
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)
        msg_path = log_dir / "task-1.msg.json"
        msg_path.write_text(_make_done_json(1))

        with patch("nightshift.subagent.run_command", return_value=(0, "garbage")):
            result = nightshift.spawn_task(
                order,
                agent="codex",
                repo_dir=tmp_path,
                log_dir=log_dir,
            )

        assert result is not None
        assert result["status"] == "done"


class TestSpawnWave:
    def test_all_done(self, tmp_path: Path) -> None:
        orders = [
            _make_work_order(task_id=1, title="Task A"),
            _make_work_order(task_id=2, title="Task B"),
        ]
        log_dir = tmp_path / "logs"

        def fake_run(cmd: list[str], **kwargs: object) -> tuple[int, str]:
            # Extract task_id from prompt (all prompts are the same, just return done)
            for i, arg in enumerate(cmd):
                if arg == "-p" and i + 1 < len(cmd):
                    return (0, _make_done_json(1))
            return (0, _make_done_json(1))

        with patch(
            "nightshift.subagent.run_command", side_effect=lambda cmd, **kw: (0, _make_done_json(kw.get("_tid", 1)))
        ):

            def mock_spawn(order: nightshift.WorkOrder, **kw: object) -> nightshift.TaskCompletion | None:
                return nightshift.TaskCompletion(
                    task_id=order["task_id"],
                    status="done",
                    files_created=[],
                    files_modified=[],
                    tests_written=[],
                    tests_passed=True,
                    notes="ok",
                )

            with patch("nightshift.subagent.spawn_task", side_effect=mock_spawn):
                result = nightshift.spawn_wave(
                    orders,
                    agent="claude",
                    repo_dir=tmp_path,
                    log_dir=log_dir,
                )

        assert result["wave"] == 1
        assert result["total_tasks"] == 2
        assert len(result["completed"]) == 2
        assert len(result["failed"]) == 0

    def test_one_blocked(self, tmp_path: Path) -> None:
        orders = [
            _make_work_order(task_id=1, title="Task A"),
            _make_work_order(task_id=2, title="Task B"),
        ]
        log_dir = tmp_path / "logs"

        def mock_spawn(order: nightshift.WorkOrder, **kw: object) -> nightshift.TaskCompletion | None:
            if order["task_id"] == 1:
                return nightshift.TaskCompletion(
                    task_id=1,
                    status="done",
                    files_created=[],
                    files_modified=[],
                    tests_written=[],
                    tests_passed=True,
                    notes="ok",
                )
            return nightshift.TaskCompletion(
                task_id=2,
                status="blocked",
                files_created=[],
                files_modified=[],
                tests_written=[],
                tests_passed=False,
                notes="stuck",
            )

        with patch("nightshift.subagent.spawn_task", side_effect=mock_spawn):
            result = nightshift.spawn_wave(
                orders,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=log_dir,
            )

        assert len(result["completed"]) == 1
        assert len(result["failed"]) == 1
        assert result["failed"][0]["task_id"] == 2

    def test_retries_on_none(self, tmp_path: Path) -> None:
        orders = [_make_work_order(task_id=1)]
        log_dir = tmp_path / "logs"
        call_count = 0

        def mock_spawn(order: nightshift.WorkOrder, **kw: object) -> nightshift.TaskCompletion | None:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return None
            return nightshift.TaskCompletion(
                task_id=1,
                status="done",
                files_created=[],
                files_modified=[],
                tests_written=[],
                tests_passed=True,
                notes="ok",
            )

        with patch("nightshift.subagent.spawn_task", side_effect=mock_spawn):
            result = nightshift.spawn_wave(
                orders,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=log_dir,
                max_retries=3,
            )

        assert call_count == 3
        assert len(result["completed"]) == 1

    def test_exhausts_retries(self, tmp_path: Path) -> None:
        orders = [_make_work_order(task_id=1)]
        log_dir = tmp_path / "logs"

        with patch("nightshift.subagent.spawn_task", return_value=None):
            result = nightshift.spawn_wave(
                orders,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=log_dir,
                max_retries=2,
            )

        assert len(result["completed"]) == 0
        assert len(result["failed"]) == 1
        assert "2 attempt(s)" in result["failed"][0]["notes"]

    def test_does_not_retry_blocked(self, tmp_path: Path) -> None:
        orders = [_make_work_order(task_id=1)]
        log_dir = tmp_path / "logs"
        call_count = 0

        def mock_spawn(order: nightshift.WorkOrder, **kw: object) -> nightshift.TaskCompletion | None:
            nonlocal call_count
            call_count += 1
            return nightshift.TaskCompletion(
                task_id=1,
                status="blocked",
                files_created=[],
                files_modified=[],
                tests_written=[],
                tests_passed=False,
                notes="cannot proceed",
            )

        with patch("nightshift.subagent.spawn_task", side_effect=mock_spawn):
            result = nightshift.spawn_wave(
                orders,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=log_dir,
                max_retries=3,
            )

        assert call_count == 1
        assert len(result["failed"]) == 1

    def test_empty_wave(self, tmp_path: Path) -> None:
        result = nightshift.spawn_wave(
            [],
            agent="claude",
            repo_dir=tmp_path,
            log_dir=tmp_path / "logs",
        )
        assert result["wave"] == 0
        assert result["total_tasks"] == 0
        assert result["completed"] == []
        assert result["failed"] == []

    def test_uses_default_max_retries(self, tmp_path: Path) -> None:
        orders = [_make_work_order(task_id=1)]
        log_dir = tmp_path / "logs"
        call_count = 0

        def mock_spawn(order: nightshift.WorkOrder, **kw: object) -> nightshift.TaskCompletion | None:
            nonlocal call_count
            call_count += 1
            return None

        with patch("nightshift.subagent.spawn_task", side_effect=mock_spawn):
            nightshift.spawn_wave(
                orders,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=log_dir,
            )

        assert call_count == nightshift.DECOMPOSER_MAX_RETRIES

    def test_wave_number_from_first_order(self, tmp_path: Path) -> None:
        orders = [_make_work_order(task_id=5, wave=3)]

        def mock_spawn(order: nightshift.WorkOrder, **kw: object) -> nightshift.TaskCompletion | None:
            return nightshift.TaskCompletion(
                task_id=5,
                status="done",
                files_created=[],
                files_modified=[],
                tests_written=[],
                tests_passed=True,
                notes="ok",
            )

        with patch("nightshift.subagent.spawn_task", side_effect=mock_spawn):
            result = nightshift.spawn_wave(
                orders,
                agent="claude",
                repo_dir=tmp_path,
                log_dir=tmp_path / "logs",
            )

        assert result["wave"] == 3


class TestFormatWaveResult:
    def test_includes_wave_number(self) -> None:
        result = nightshift.WaveResult(wave=2, completed=[], failed=[], total_tasks=0)
        output = nightshift.format_wave_result(result)
        assert "Wave 2" in output

    def test_includes_counts(self) -> None:
        completed = [
            nightshift.TaskCompletion(
                task_id=1,
                status="done",
                files_created=["a.py"],
                files_modified=[],
                tests_written=["test A"],
                tests_passed=True,
                notes="ok",
            )
        ]
        result = nightshift.WaveResult(wave=1, completed=completed, failed=[], total_tasks=1)
        output = nightshift.format_wave_result(result)
        assert "**1** completed" in output
        assert "**0** failed" in output
        assert "**1** total" in output

    def test_includes_completed_details(self) -> None:
        completed = [
            nightshift.TaskCompletion(
                task_id=1,
                status="done",
                files_created=["src/new.ts"],
                files_modified=["src/old.ts"],
                tests_written=["test new component"],
                tests_passed=True,
                notes="Looks good",
            )
        ]
        result = nightshift.WaveResult(wave=1, completed=completed, failed=[], total_tasks=1)
        output = nightshift.format_wave_result(result)
        assert "Task 1" in output
        assert "src/new.ts" in output
        assert "src/old.ts" in output
        assert "Looks good" in output

    def test_includes_failed_details(self) -> None:
        failed = [
            nightshift.TaskCompletion(
                task_id=3,
                status="blocked",
                files_created=[],
                files_modified=[],
                tests_written=[],
                tests_passed=False,
                notes="Cannot find dependency",
            )
        ]
        result = nightshift.WaveResult(wave=1, completed=[], failed=failed, total_tasks=1)
        output = nightshift.format_wave_result(result)
        assert "Task 3" in output
        assert "Cannot find dependency" in output
        assert "## Failed" in output

    def test_empty_result(self) -> None:
        result = nightshift.WaveResult(wave=0, completed=[], failed=[], total_tasks=0)
        output = nightshift.format_wave_result(result)
        assert "**0** completed" in output
        assert "**0** failed" in output


class TestSubagentConstants:
    def test_default_timeout(self) -> None:
        assert nightshift.SUBAGENT_DEFAULT_TIMEOUT == 600

    def test_max_turns(self) -> None:
        assert nightshift.SUBAGENT_MAX_TURNS == 50

    def test_max_turns_is_positive(self) -> None:
        assert nightshift.SUBAGENT_MAX_TURNS > 0

    def test_default_timeout_is_positive(self) -> None:
        assert nightshift.SUBAGENT_DEFAULT_TIMEOUT > 0


# --- Integrator ---------------------------------------------------------------


def _make_wave_result(
    wave: int = 1,
    completed: list[nightshift.TaskCompletion] | None = None,
    failed: list[nightshift.TaskCompletion] | None = None,
) -> nightshift.WaveResult:
    """Build a WaveResult for testing."""
    c = completed or []
    f = failed or []
    return nightshift.WaveResult(
        wave=wave,
        completed=c,
        failed=f,
        total_tasks=len(c) + len(f),
    )


def _make_task_completion(
    task_id: int = 1,
    status: str = "done",
    files_created: list[str] | None = None,
    files_modified: list[str] | None = None,
    tests_written: list[str] | None = None,
    tests_passed: bool = True,
    notes: str = "ok",
) -> nightshift.TaskCompletion:
    """Build a TaskCompletion for testing."""
    return nightshift.TaskCompletion(
        task_id=task_id,
        status=status,
        files_created=files_created or [],
        files_modified=files_modified or [],
        tests_written=tests_written or [],
        tests_passed=tests_passed,
        notes=notes,
    )


class TestCollectWaveFiles:
    def test_empty_wave(self) -> None:
        wr = _make_wave_result()
        assert nightshift.collect_wave_files(wr) == []

    def test_collects_created_and_modified(self) -> None:
        tc = _make_task_completion(
            files_created=["src/a.py"],
            files_modified=["src/b.py"],
        )
        wr = _make_wave_result(completed=[tc])
        result = nightshift.collect_wave_files(wr)
        assert result == ["src/a.py", "src/b.py"]

    def test_deduplicates(self) -> None:
        tc1 = _make_task_completion(task_id=1, files_created=["src/shared.py"])
        tc2 = _make_task_completion(task_id=2, files_modified=["src/shared.py"])
        wr = _make_wave_result(completed=[tc1, tc2])
        result = nightshift.collect_wave_files(wr)
        assert result == ["src/shared.py"]

    def test_sorted_output(self) -> None:
        tc = _make_task_completion(
            files_created=["z.py", "a.py", "m.py"],
        )
        wr = _make_wave_result(completed=[tc])
        result = nightshift.collect_wave_files(wr)
        assert result == ["a.py", "m.py", "z.py"]

    def test_ignores_failed_tasks(self) -> None:
        tc_done = _make_task_completion(task_id=1, files_created=["good.py"])
        tc_fail = _make_task_completion(task_id=2, status="blocked", files_created=["bad.py"])
        wr = _make_wave_result(completed=[tc_done], failed=[tc_fail])
        result = nightshift.collect_wave_files(wr)
        assert result == ["good.py"]

    def test_multiple_tasks_merge(self) -> None:
        tc1 = _make_task_completion(task_id=1, files_created=["a.py"], files_modified=["c.py"])
        tc2 = _make_task_completion(task_id=2, files_created=["b.py"], files_modified=["d.py"])
        wr = _make_wave_result(completed=[tc1, tc2])
        result = nightshift.collect_wave_files(wr)
        assert result == ["a.py", "b.py", "c.py", "d.py"]


class TestStageFiles:
    def test_stages_existing_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("print('a')")
        (tmp_path / "b.py").write_text("print('b')")

        with patch("nightshift.integrator.git") as mock_git:
            result = nightshift.stage_files(tmp_path, ["a.py", "b.py"])

        assert result == ["a.py", "b.py"]
        assert mock_git.call_count == 2

    def test_skips_missing_files(self, tmp_path: Path) -> None:
        (tmp_path / "exists.py").write_text("print('hi')")

        with patch("nightshift.integrator.git") as mock_git:
            result = nightshift.stage_files(tmp_path, ["exists.py", "missing.py"])

        assert result == ["exists.py"]
        assert mock_git.call_count == 1

    def test_empty_file_list(self, tmp_path: Path) -> None:
        with patch("nightshift.integrator.git") as mock_git:
            result = nightshift.stage_files(tmp_path, [])

        assert result == []
        assert mock_git.call_count == 0


class TestRunTestSuite:
    def test_returns_zero_on_success(self, tmp_path: Path) -> None:
        with patch("nightshift.integrator.run_test_command", return_value=(0, "ok")):
            code, output = nightshift.run_test_suite(tmp_path, "echo test")

        assert code == 0
        assert "ok" in output

    def test_returns_nonzero_on_failure(self, tmp_path: Path) -> None:
        with patch("nightshift.integrator.run_test_command", return_value=(1, "FAIL error")):
            code, output = nightshift.run_test_suite(tmp_path, "test")

        assert code == 1
        assert "FAIL" in output

    def test_no_test_command_returns_success(self, tmp_path: Path) -> None:
        code, output = nightshift.run_test_suite(tmp_path, None)
        assert code == 0
        assert output == ""

    def test_timeout_returns_failure(self, tmp_path: Path) -> None:
        with patch("nightshift.integrator.run_test_command", return_value=(1, "Command timed out after 10 seconds")):
            code, output = nightshift.run_test_suite(tmp_path, "test", timeout=10)

        assert code == 1
        assert "timed out" in output


class TestDiagnoseFailure:
    def test_identifies_suspect_by_file_mention(self) -> None:
        tc1 = _make_task_completion(task_id=1, files_created=["src/auth.py"])
        tc2 = _make_task_completion(task_id=2, files_created=["src/utils.py"])
        wr = _make_wave_result(completed=[tc1, tc2])

        test_output = "FAILED tests/test_auth.py::test_login - ImportError: src/auth.py"
        suspect_id, diag = nightshift.diagnose_failure(test_output, wr)

        assert suspect_id == 1
        assert "Task 1" in diag

    def test_identifies_by_basename(self) -> None:
        tc = _make_task_completion(task_id=3, files_created=["deep/nested/handler.py"])
        wr = _make_wave_result(completed=[tc])

        test_output = "Error in handler.py line 42"
        suspect_id, _diag = nightshift.diagnose_failure(test_output, wr)

        assert suspect_id == 3

    def test_returns_none_when_no_match(self) -> None:
        tc = _make_task_completion(task_id=1, files_created=["src/models.py"])
        wr = _make_wave_result(completed=[tc])

        test_output = "FAILED: something completely unrelated"
        suspect_id, diag = nightshift.diagnose_failure(test_output, wr)

        assert suspect_id is None
        assert "Could not match" in diag

    def test_empty_test_output(self) -> None:
        wr = _make_wave_result()
        suspect_id, diag = nightshift.diagnose_failure("", wr)

        assert suspect_id is None
        assert "No test output" in diag

    def test_picks_most_mentioned_task(self) -> None:
        tc1 = _make_task_completion(task_id=1, files_created=["a.py"])
        tc2 = _make_task_completion(task_id=2, files_created=["b.py"])
        wr = _make_wave_result(completed=[tc1, tc2])

        # b.py mentioned 3 times, a.py mentioned 1 time
        test_output = "Error in a.py\nError in b.py\nAlso b.py\nAnd b.py again"
        suspect_id, _ = nightshift.diagnose_failure(test_output, wr)

        assert suspect_id == 2


class TestIntegrateWave:
    def test_passed_when_tests_succeed(self, tmp_path: Path) -> None:
        tc = _make_task_completion(task_id=1, files_created=["src/new.py"])
        wr = _make_wave_result(completed=[tc])
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "new.py").write_text("x = 1")
        log_dir = tmp_path / "logs"

        with (
            patch("nightshift.integrator.git"),
            patch("nightshift.integrator.run_test_command", return_value=(0, "3 passed")),
        ):
            result = nightshift.integrate_wave(
                wr,
                repo_dir=tmp_path,
                test_command="pytest",
                agent="claude",
                log_dir=log_dir,
            )

        assert result["status"] == "passed"
        assert result["tests_run"] is True
        assert result["test_exit_code"] == 0
        assert "src/new.py" in result["files_staged"]
        assert result["fix_attempts"] == []

    def test_no_test_runner(self, tmp_path: Path) -> None:
        tc = _make_task_completion(task_id=1, files_created=["app.js"])
        wr = _make_wave_result(completed=[tc])
        (tmp_path / "app.js").write_text("module.exports = {}")
        log_dir = tmp_path / "logs"

        with patch("nightshift.integrator.git"):
            result = nightshift.integrate_wave(
                wr,
                repo_dir=tmp_path,
                test_command=None,
                agent="claude",
                log_dir=log_dir,
            )

        assert result["status"] == "no_test_runner"
        assert result["tests_run"] is False

    def test_failed_after_exhausting_fix_attempts(self, tmp_path: Path) -> None:
        tc = _make_task_completion(
            task_id=1,
            files_created=["src/broken.py"],
            notes="Something went wrong",
        )
        wr = _make_wave_result(completed=[tc])
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "broken.py").write_text("x = 1")
        log_dir = tmp_path / "logs"

        with (
            patch("nightshift.integrator.git"),
            patch("nightshift.integrator.run_test_command", return_value=(1, "FAIL src/broken.py broken.py")),
            patch("nightshift.integrator.spawn_task", return_value=_make_task_completion()),
        ):
            result = nightshift.integrate_wave(
                wr,
                repo_dir=tmp_path,
                test_command="pytest",
                agent="claude",
                log_dir=log_dir,
                max_fix_attempts=2,
            )

        assert result["status"] == "failed"
        assert result["tests_run"] is True
        assert result["test_exit_code"] == 1
        assert len(result["fix_attempts"]) == 2

    def test_fix_agent_succeeds_on_second_attempt(self, tmp_path: Path) -> None:
        tc = _make_task_completion(
            task_id=1,
            files_created=["src/fixable.py"],
        )
        wr = _make_wave_result(completed=[tc])
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "fixable.py").write_text("x = 1")
        log_dir = tmp_path / "logs"

        # First test run fails, second succeeds (after fix)
        call_count = 0

        def mock_test_run(*args: object, **kwargs: object) -> tuple[int, str]:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return (1, "FAIL fixable.py")
            return (0, "3 passed")

        with (
            patch("nightshift.integrator.git"),
            patch("nightshift.integrator.run_test_command", side_effect=mock_test_run),
            patch("nightshift.integrator.spawn_task", return_value=_make_task_completion()),
        ):
            result = nightshift.integrate_wave(
                wr,
                repo_dir=tmp_path,
                test_command="pytest",
                agent="claude",
                log_dir=log_dir,
                max_fix_attempts=3,
            )

        assert result["status"] == "passed"
        assert len(result["fix_attempts"]) == 2
        assert result["fix_attempts"][-1]["tests_passed"] is True

    def test_stops_fixing_when_diagnosis_fails(self, tmp_path: Path) -> None:
        tc = _make_task_completion(task_id=1, files_created=["src/x.py"])
        wr = _make_wave_result(completed=[tc])
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "x.py").write_text("x = 1")
        log_dir = tmp_path / "logs"

        with (
            patch("nightshift.integrator.git"),
            patch("nightshift.integrator.run_test_command", return_value=(1, "FAIL unrelated_test")),
        ):
            result = nightshift.integrate_wave(
                wr,
                repo_dir=tmp_path,
                test_command="pytest",
                agent="claude",
                log_dir=log_dir,
                max_fix_attempts=3,
            )

        assert result["status"] == "failed"
        # Should only have 1 fix attempt (stopped early because diagnosis failed)
        assert len(result["fix_attempts"]) == 1
        assert "Could not identify" in result["fix_attempts"][0]["fix_agent_notes"]

    def test_empty_wave_still_integrates(self, tmp_path: Path) -> None:
        wr = _make_wave_result()
        log_dir = tmp_path / "logs"

        with (
            patch("nightshift.integrator.git"),
            patch("nightshift.integrator.run_test_command", return_value=(0, "ok")),
        ):
            result = nightshift.integrate_wave(
                wr,
                repo_dir=tmp_path,
                test_command="pytest",
                agent="claude",
                log_dir=log_dir,
            )

        assert result["status"] == "passed"
        assert result["files_staged"] == []

    def test_missing_files_not_staged(self, tmp_path: Path) -> None:
        tc = _make_task_completion(
            task_id=1,
            files_created=["exists.py", "ghost.py"],
        )
        wr = _make_wave_result(completed=[tc])
        (tmp_path / "exists.py").write_text("x = 1")
        log_dir = tmp_path / "logs"

        with (
            patch("nightshift.integrator.git"),
            patch("nightshift.integrator.run_test_command", return_value=(0, "ok")),
        ):
            result = nightshift.integrate_wave(
                wr,
                repo_dir=tmp_path,
                test_command="pytest",
                agent="claude",
                log_dir=log_dir,
            )

        assert "exists.py" in result["files_staged"]
        assert "ghost.py" not in result["files_staged"]

    def test_uses_custom_max_fix_attempts(self, tmp_path: Path) -> None:
        tc = _make_task_completion(task_id=1, files_created=["src/f.py"])
        wr = _make_wave_result(completed=[tc])
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "f.py").write_text("x = 1")
        log_dir = tmp_path / "logs"

        spawn_count = 0

        def counting_spawn(*args: object, **kwargs: object) -> nightshift.TaskCompletion:
            nonlocal spawn_count
            spawn_count += 1
            return _make_task_completion()

        with (
            patch("nightshift.integrator.git"),
            patch("nightshift.integrator.run_test_command", return_value=(1, "FAIL src/f.py f.py")),
            patch("nightshift.integrator.spawn_task", side_effect=counting_spawn),
        ):
            nightshift.integrate_wave(
                wr,
                repo_dir=tmp_path,
                test_command="pytest",
                agent="claude",
                log_dir=log_dir,
                max_fix_attempts=5,
            )

        assert spawn_count == 5


class TestFormatIntegrationResult:
    def test_includes_status(self) -> None:
        result = nightshift.IntegrationResult(
            wave=1,
            status="passed",
            tests_run=True,
            test_exit_code=0,
            test_output="3 passed",
            files_staged=["a.py"],
            fix_attempts=[],
            failure_diagnosis="",
        )
        output = nightshift.format_integration_result(result)
        assert "passed" in output
        assert "Wave 1" in output

    def test_includes_files_staged(self) -> None:
        result = nightshift.IntegrationResult(
            wave=2,
            status="passed",
            tests_run=True,
            test_exit_code=0,
            test_output="ok",
            files_staged=["src/auth.py", "src/utils.py"],
            fix_attempts=[],
            failure_diagnosis="",
        )
        output = nightshift.format_integration_result(result)
        assert "src/auth.py" in output
        assert "src/utils.py" in output

    def test_includes_fix_attempts(self) -> None:
        fa = nightshift.FixAttempt(
            task_id=3,
            test_output="FAIL",
            fix_agent_notes="Fixed import",
            tests_passed=True,
        )
        result = nightshift.IntegrationResult(
            wave=1,
            status="passed",
            tests_run=True,
            test_exit_code=0,
            test_output="ok",
            files_staged=[],
            fix_attempts=[fa],
            failure_diagnosis="Task 3 files mentioned",
        )
        output = nightshift.format_integration_result(result)
        assert "Fix Attempts" in output
        assert "Fixed import" in output
        assert "Task 3 files mentioned" in output

    def test_includes_diagnosis(self) -> None:
        result = nightshift.IntegrationResult(
            wave=1,
            status="failed",
            tests_run=True,
            test_exit_code=1,
            test_output="FAIL",
            files_staged=[],
            fix_attempts=[],
            failure_diagnosis="Could not match test failures",
        )
        output = nightshift.format_integration_result(result)
        assert "Could not match" in output

    def test_empty_result(self) -> None:
        result = nightshift.IntegrationResult(
            wave=0,
            status="no_test_runner",
            tests_run=False,
            test_exit_code=0,
            test_output="",
            files_staged=[],
            fix_attempts=[],
            failure_diagnosis="",
        )
        output = nightshift.format_integration_result(result)
        assert "no_test_runner" in output


class TestIntegratorConstants:
    def test_max_fix_attempts(self) -> None:
        assert nightshift.INTEGRATOR_MAX_FIX_ATTEMPTS == 3

    def test_test_timeout(self) -> None:
        assert nightshift.INTEGRATOR_TEST_TIMEOUT == 300

    def test_max_fix_attempts_is_positive(self) -> None:
        assert nightshift.INTEGRATOR_MAX_FIX_ATTEMPTS > 0

    def test_test_timeout_is_positive(self) -> None:
        assert nightshift.INTEGRATOR_TEST_TIMEOUT > 0


class TestIntegratorTypes:
    def test_fix_attempt_fields(self) -> None:
        fa = nightshift.FixAttempt(
            task_id=1,
            test_output="output",
            fix_agent_notes="notes",
            tests_passed=True,
        )
        assert fa["task_id"] == 1
        assert fa["tests_passed"] is True

    def test_integration_result_fields(self) -> None:
        result = nightshift.IntegrationResult(
            wave=1,
            status="passed",
            tests_run=True,
            test_exit_code=0,
            test_output="ok",
            files_staged=["a.py"],
            fix_attempts=[],
            failure_diagnosis="",
        )
        assert result["wave"] == 1
        assert result["status"] == "passed"
        assert result["files_staged"] == ["a.py"]
