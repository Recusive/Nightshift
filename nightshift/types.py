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
    category_balancing_cycle: int
    claude_model: str
    claude_effort: str
    codex_model: str
    codex_thinking: str
    notification_webhook: str | None
    readiness_checks: list[str]


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


class RepoShiftResult(TypedDict):
    """Per-repo outcome from a multi-repo shift."""

    repo_dir: str
    exit_code: int
    cycles_run: int
    fixes: int
    issues_logged: int
    halt_reason: str


class FrameworkInfo(TypedDict):
    """A detected framework in the target repo."""

    name: str
    version: str


class RepoProfile(TypedDict):
    """Comprehensive profile of a target repository for Loop 2 sub-agents."""

    languages: dict[str, int]
    primary_language: str
    frameworks: list[FrameworkInfo]
    package_manager: str | None
    test_runner: str | None
    instruction_files: list[str]
    top_level_dirs: list[str]
    has_monorepo_markers: bool
    total_files: int


# --- Loop 2: Feature Planner types -------------------------------------------


class PlanTask(TypedDict):
    """A single task in a feature plan's task breakdown."""

    id: int
    title: str
    description: str
    depends_on: list[int]
    parallel: bool
    acceptance_criteria: list[str]
    estimated_files: int


class ArchitectureDoc(TypedDict):
    """Architecture decisions for a feature."""

    overview: str
    tech_choices: list[str]
    data_model_changes: list[str]
    api_changes: list[str]
    frontend_changes: list[str]
    integration_points: list[str]


class TestPlan(TypedDict):
    """Test strategy for a feature."""

    unit_tests: list[str]
    integration_tests: list[str]
    e2e_tests: list[str]
    edge_cases: list[str]


class FeaturePlan(TypedDict):
    """Complete plan for a feature build -- output of the planner module."""

    feature: str
    architecture: ArchitectureDoc
    tasks: list[PlanTask]
    test_plan: TestPlan


# --- Loop 2: Task Decomposer types ------------------------------------------


class WorkOrder(TypedDict):
    """A single sub-agent work order -- everything an agent needs to execute one task."""

    task_id: int
    wave: int
    title: str
    prompt: str
    acceptance_criteria: list[str]
    estimated_files: int
    depends_on: list[int]
    schema_path: str


class DecomposerResult(TypedDict):
    """Output of decompose_plan() -- work orders grouped by execution wave."""

    feature: str
    total_waves: int
    total_tasks: int
    waves: list[list[WorkOrder]]


# --- Loop 2: Sub-agent spawner types -----------------------------------------


class TaskCompletion(TypedDict):
    """Parsed result from a sub-agent executing a work order."""

    task_id: int
    status: str  # "done" | "blocked"
    files_created: list[str]
    files_modified: list[str]
    tests_written: list[str]
    tests_passed: bool
    notes: str


class WaveResult(TypedDict):
    """Outcome of spawning all sub-agents for one execution wave."""

    wave: int
    completed: list[TaskCompletion]
    failed: list[TaskCompletion]
    total_tasks: int


# --- Loop 2: Integrator types ------------------------------------------------


class FixAttempt(TypedDict):
    """Record of one attempt to fix a failing test after wave integration."""

    task_id: int
    test_output: str
    fix_agent_notes: str
    tests_passed: bool


class IntegrationResult(TypedDict):
    """Outcome of integrating one wave's sub-agent work into the repo."""

    wave: int
    status: str  # "passed" | "failed" | "no_test_runner"
    tests_run: bool
    test_exit_code: int
    test_output: str
    files_staged: list[str]
    fix_attempts: list[FixAttempt]
    failure_diagnosis: str


# --- Loop 2: Coordination types ---------------------------------------------


class FileOverlap(TypedDict):
    """A file reference mentioned by multiple tasks within a wave."""

    file_pattern: str
    task_ids: list[int]


class FileConflict(TypedDict):
    """A file touched by multiple completed tasks in a wave."""

    file_path: str
    task_ids: list[int]


class ConflictReport(TypedDict):
    """Post-wave file conflict analysis result."""

    conflicts: list[FileConflict]
    has_conflicts: bool


# --- Loop 2: Feature build orchestration ------------------------------------


class FinalVerificationResult(TypedDict):
    """Outcome of the final production-readiness verification step."""

    status: str  # "passed" | "failed"
    tests_run: bool
    lint_run: bool
    test_command: str | None
    lint_command: str | None
    test_exit_code: int
    lint_exit_code: int
    test_output: str
    lint_output: str


class FeatureWaveState(TypedDict):
    """Persisted state for one execution wave in a feature build."""

    wave: int
    task_ids: list[int]
    status: str  # "pending" | "running" | "passed" | "failed"
    wave_result: WaveResult | None
    integration_result: IntegrationResult | None


class FeatureSummary(TypedDict):
    """Structured summary of a completed feature build."""

    files_created: list[str]
    files_modified: list[str]
    tests_added: list[str]
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    patterns_detected: list[str]
    description: str


class ReadinessCheck(TypedDict):
    """Result of a single production-readiness check."""

    name: str
    passed: bool
    details: str


class ReadinessReport(TypedDict):
    """Aggregate production-readiness report for a feature build."""

    checks: list[ReadinessCheck]
    verdict: str  # "ready" | "not_ready"
    passed_count: int
    failed_count: int


class E2EResult(TypedDict):
    """Result of running end-to-end tests after all waves complete."""

    status: str  # "passed" | "failed" | "skipped"
    test_command: str | None
    test_exit_code: int
    test_output: str
    smoke_test_command: str | None
    smoke_test_exit_code: int
    smoke_test_output: str


class FeatureState(TypedDict):
    """Persisted state for the Loop 2 feature build orchestrator."""

    version: int
    feature_description: str
    agent: str
    status: str  # "awaiting_confirmation" | "building" | "failed" | "completed"
    scope_warning: str
    current_wave: int
    profile: RepoProfile
    plan: FeaturePlan
    waves: list[FeatureWaveState]
    e2e_result: E2EResult | None
    final_verification: FinalVerificationResult | None
    readiness: ReadinessReport | None
    summary: FeatureSummary | None


# --- Cost tracking types ----------------------------------------------------


class SessionCost(TypedDict):
    """Token usage and estimated cost for a single daemon session."""

    session_id: str
    agent: str
    model: str
    input_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    output_tokens: int
    total_cost_usd: float


class CostLedger(TypedDict):
    """Cumulative cost tracking across daemon sessions."""

    total_cost_usd: float
    sessions: list[SessionCost]


# --- Cleanup types ----------------------------------------------------------


class LogRotationResult(TypedDict):
    """Outcome of rotating old session logs."""

    deleted: list[str]
    kept: int
    errors: list[str]


class BranchPruneResult(TypedDict):
    """Outcome of pruning orphan remote branches."""

    pruned: list[str]
    skipped: list[str]
    errors: list[str]


# --- Handoff compaction types -----------------------------------------------


class CompactionResult(TypedDict):
    """Outcome of compacting numbered handoff files into a weekly summary."""

    compacted: list[str]
    weekly_file: str
    errors: list[str]
