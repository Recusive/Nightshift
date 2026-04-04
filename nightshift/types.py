"""Strict type definitions for all Nightshift data structures."""

from __future__ import annotations

from typing import TypedDict


class NightshiftConfig(TypedDict):
    """Per-repo .nightshift.json merged with defaults. merge_config() guarantees all keys are present."""

    agent: str | None
    hours: int
    cycle_minutes: int
    verify_command: str | None
    blocked_paths: list[str]
    blocked_globs: list[str]
    max_fixes_per_cycle: int
    max_files_per_fix: int
    max_files_per_cycle: int
    max_low_impact_fixes_per_shift: int
    stop_after_failed_verifications: int
    stop_after_empty_cycles: int
    score_threshold: int
    test_incentive_cycle: int
    backend_forcing_cycle: int


class DiffScore(TypedDict):
    """Result from scoring a cycle's diff for production impact."""

    score: int
    reason: str
    category_bonus: bool
    test_bonus: bool


class Counters(TypedDict):
    fixes: int
    issues_logged: int
    files_touched: int
    low_impact_fixes: int
    failed_verifications: int
    empty_cycles: int
    agent_failures: int
    tests_written: int


class Baseline(TypedDict):
    status: str  # "pending" | "passed" | "failed" | "skipped"
    command: str | None
    message: str


class Fix(TypedDict, total=False):
    title: str
    category: str
    impact: str  # "low" | "medium" | "high"
    files: list[str]


class LoggedIssue(TypedDict, total=False):
    title: str
    category: str
    severity: str
    files: list[str]


class CycleResult(TypedDict, total=False):
    """Structured JSON returned by the agent at end of cycle."""

    cycle: int
    status: str
    fixes: list[Fix]
    logged_issues: list[LoggedIssue]
    categories: list[str]
    files_touched: list[str]
    tests_run: list[str]
    notes: str


class CycleVerification(TypedDict):
    verify_command: str | None
    verify_status: str  # "skipped" | "passed" | "failed"
    verify_exit_code: int | None
    dominant_path: str
    commits: list[str]
    files_touched: list[str]
    violations: list[str]


class CycleEntry(TypedDict, total=False):
    """One cycle's record in state['cycles']."""

    cycle: int
    status: str
    fixes: list[Fix]
    logged_issues: list[LoggedIssue]
    verification: CycleVerification
    cycle_result: CycleResult | None
    exit_code: int


class ShiftState(TypedDict):
    version: int
    date: str
    branch: str
    agent: str
    verify_command: str | None
    baseline: Baseline
    counters: Counters
    category_counts: dict[str, int]
    recent_cycle_paths: list[str]
    cycles: list[CycleEntry]
    halt_reason: str | None
    log_only_mode: bool
