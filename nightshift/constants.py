"""Module-level constants and tiny utilities used across the package."""

from __future__ import annotations

import datetime as dt
import re

from nightshift.types import NightshiftConfig

DATA_VERSION = 1

SUPPORTED_AGENTS = ["codex", "claude"]

CATEGORY_ORDER = [
    "Security",
    "Error Handling",
    "Tests",
    "A11y",
    "Code Quality",
    "Performance",
    "Polish",
]

DEFAULT_CONFIG: NightshiftConfig = {
    "agent": None,
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
    "score_threshold": 3,
    "test_incentive_cycle": 3,
    "backend_forcing_cycle": 3,
    "category_balancing_cycle": 3,
}

# --- Diff scoring data -------------------------------------------------------

SECURITY_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"(sql.?inject|xss|csrf|auth|sanitiz|escap|vulnerab)", re.IGNORECASE), 8),
    (re.compile(r"(password|secret|token|credential|api.?key)", re.IGNORECASE), 7),
]

ERROR_HANDLING_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"(try|catch|except|raise|throw|Error|Exception)", re.IGNORECASE), 5),
    (re.compile(r"(error.?handl|fallback|retry|timeout)", re.IGNORECASE), 5),
]

CATEGORY_SCORES: dict[str, int] = {
    "Security": 8,
    "Error Handling": 6,
    "Tests": 6,
    "A11y": 5,
    "Code Quality": 3,
    "Performance": 5,
    "Polish": 2,
}

FORBIDDEN_CYCLE_COMMANDS = [
    "npm test",
    "npm run test",
    "npm run lint",
    "npm run build",
    "pnpm test",
    "pnpm run test",
    "pnpm run lint",
    "pnpm run build",
    "yarn test",
    "yarn lint",
    "yarn build",
    "bun test",
    "bun run test",
    "bun run lint",
    "bun run build",
]

HIGH_SIGNAL_PATH_CANDIDATES = [
    # JS/TS
    "src/lib/auth",
    "src/lib/http.ts",
    "src/app/api",
    "src/lib/db/queries",
    "src/lib/analytics",
    "src/lib/contracts",
    "lib/auth",
    "lib/http.ts",
    "app/api",
    # Python
    "app/models",
    "app/auth",
    "app/api",
    "src/auth",
    "src/api",
    # Go
    "internal/auth",
    "internal/api",
    "pkg/api",
    "cmd",
    # Rust
    "src/main.rs",
    "src/lib.rs",
    "src/api",
    # Generic
    "server",
    "api",
    "backend",
    "src/server",
    "src/api",
]

# --- Backend exploration forcing data ----------------------------------------

FRONTEND_DIR_NAMES: set[str] = {
    "components",
    "pages",
    "views",
    "styles",
    "css",
    "scss",
    "public",
    "static",
    "assets",
    "templates",
    "layouts",
    "hooks",
    "contexts",
    "providers",
    "theme",
    "client",
    "frontend",
    "web",
    "ui",
}

BACKEND_DIR_NAMES: set[str] = {
    "server",
    "api",
    "backend",
    "routes",
    "controllers",
    "models",
    "middleware",
    "services",
    "handlers",
    "db",
    "database",
    "migrations",
    "resolvers",
    "graphql",
    "lib",
    "pkg",
    "internal",
    "cmd",
}

FRONTEND_EXTENSIONS: set[str] = {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".less"}
BACKEND_EXTENSIONS: set[str] = {".py", ".go", ".rs", ".java", ".rb", ".php", ".ex", ".exs"}

CLASSIFY_SKIP_DIRS: set[str] = {
    "node_modules",
    ".git",
    "__pycache__",
    "dist",
    "build",
    "out",
    "target",
    "coverage",
    ".svn",
}

# --- Safe artifacts ----------------------------------------------------------

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

SHIFT_LOG_TEMPLATE = """# Nightshift -- {today}

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

<!-- Number sequentially. Include cycle number, category, impact, files, commit hash, and verification command. -->

---

## Logged Issues

<!-- Issues too large to fix autonomously. Include severity, category, files, and suggested approach. -->

---

## Recommendations

<!-- Patterns noticed, areas needing deeper work. Updated as the shift progresses. -->
"""


# --- Repo profiling data -----------------------------------------------------

LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".rb": "Ruby",
    ".php": "PHP",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".vue": "Vue",
    ".svelte": "Svelte",
}

FRAMEWORK_MARKERS: dict[str, list[str]] = {
    "Next.js": ["next.config.js", "next.config.mjs", "next.config.ts"],
    "Nuxt": ["nuxt.config.js", "nuxt.config.ts"],
    "SvelteKit": ["svelte.config.js", "svelte.config.ts"],
    "Django": ["manage.py", "django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Rails": ["Gemfile", "config/routes.rb"],
    "Express": ["express"],
    "Nest.js": ["nest-cli.json"],
    "Spring Boot": ["pom.xml", "build.gradle"],
    "Laravel": ["artisan", "composer.json"],
    "Phoenix": ["mix.exs"],
    "Remix": ["remix.config.js", "remix.config.ts"],
    "Astro": ["astro.config.mjs", "astro.config.ts"],
}

# Framework names that are detected by scanning package.json dependencies
# rather than by marker files. Maps framework name -> package name.
FRAMEWORK_PACKAGES: dict[str, str] = {
    "React": "react",
    "Vue": "vue",
    "Angular": "@angular/core",
    "Svelte": "svelte",
    "Express": "express",
    "Nest.js": "@nestjs/core",
    "FastAPI": "fastapi",
    "Flask": "flask",
    "Django": "django",
}

INSTRUCTION_FILE_NAMES: list[str] = [
    "CLAUDE.md",
    "AGENTS.md",
    ".cursorrules",
    ".github/copilot-instructions.md",
    "CONTRIBUTING.md",
    "GEMINI.md",
    ".clinerules",
    "CONVENTIONS.md",
]

MONOREPO_MARKERS: list[str] = [
    "lerna.json",
    "pnpm-workspace.yaml",
    "turbo.json",
    "nx.json",
    "rush.json",
]

# --- Feature planner data ----------------------------------------------------

# Maximum tasks before suggesting the feature be broken into phases.
PLAN_MAX_TASKS = 10

# Maximum estimated files across all tasks before suggesting phasing.
PLAN_MAX_TOTAL_FILES = 50

# Recommended max files per individual task (guidance for the agent prompt).
PLAN_MAX_FILES_PER_TASK = 5

PLAN_PROMPT_TEMPLATE = """You are a senior software architect planning a feature for an existing codebase.

## Repository Profile

- **Primary language**: {primary_language}
- **Frameworks**: {frameworks}
- **Package manager**: {package_manager}
- **Test runner**: {test_runner}
- **Instruction files**: {instruction_files}
- **Top-level directories**: {top_level_dirs}
- **Monorepo**: {is_monorepo}
- **Total files**: {total_files}

## Feature Request

{feature_description}

## Your Task

Produce a feature plan as a JSON object with this exact structure:

```json
{{
  "feature": "<one-line feature name>",
  "architecture": {{
    "overview": "<2-3 sentence summary of the approach>",
    "tech_choices": ["<choice 1 with reasoning>", "..."],
    "data_model_changes": ["<change 1>", "..."],
    "api_changes": ["<endpoint or route change>", "..."],
    "frontend_changes": ["<component or page change>", "..."],
    "integration_points": ["<where this touches existing code>", "..."]
  }},
  "tasks": [
    {{
      "id": 1,
      "title": "<short task title>",
      "description": "<what this task builds>",
      "depends_on": [],
      "parallel": true,
      "acceptance_criteria": ["<testable criterion>", "..."],
      "estimated_files": 3
    }}
  ],
  "test_plan": {{
    "unit_tests": ["<what to unit test>", "..."],
    "integration_tests": ["<what to integration test>", "..."],
    "e2e_tests": ["<what to e2e test>", "..."],
    "edge_cases": ["<edge case to handle>", "..."]
  }}
}}
```

## Rules

1. Use the repo's existing stack. Do not introduce new frameworks unless the feature absolutely requires it.
2. Follow existing conventions (file naming, directory structure, test patterns).
3. Every task must have at least one acceptance criterion that is testable.
4. Mark tasks as `parallel: true` if they have no dependencies on each other.
5. Task `depends_on` references other task IDs that must complete first.
6. Keep tasks small -- each should touch {max_files_hint} files or fewer.
7. If the feature would need more than {max_tasks} tasks, suggest breaking it into phases and plan only phase 1.
8. Use empty arrays (not null) for sections that don't apply (e.g., no frontend changes for a backend-only feature).
9. Return ONLY the JSON object. No markdown fences, no commentary.
"""

# --- Task decomposer data ----------------------------------------------------

# JSON schema path for sub-agent task completion output.
TASK_SCHEMA_PATH = "schemas/task.schema.json"

# Maximum retries for a single sub-agent work order before marking it failed.
DECOMPOSER_MAX_RETRIES = 3

WORK_ORDER_PROMPT_TEMPLATE = """You are a software engineer executing a specific task as part of a larger feature build.

## Repository Profile

- **Primary language**: {primary_language}
- **Frameworks**: {frameworks}
- **Package manager**: {package_manager}
- **Test runner**: {test_runner}
- **Instruction files**: {instruction_files}

## Feature Context

You are building: **{feature_name}**

Architecture overview: {architecture_overview}

## Your Task

**Task {task_id}: {task_title}**

{task_description}

### Acceptance Criteria

{acceptance_criteria}

### Dependencies

{dependency_context}

### Constraints

1. Only modify files relevant to this task.
2. Follow the repo's existing conventions (naming, imports, file structure).
3. Write tests for every piece of logic you add.
4. Run the test runner ({test_runner}) and ensure your tests pass.
5. Keep changes under {estimated_files} files if possible.
6. Do NOT modify files that other parallel tasks are working on.

## Output

When done, return a JSON object matching the task completion schema:

```json
{{
  "task_id": {task_id},
  "status": "done",
  "files_created": ["<path>", "..."],
  "files_modified": ["<path>", "..."],
  "tests_written": ["<test description>", "..."],
  "tests_passed": true,
  "notes": "<any important context for the orchestrator>"
}}
```

If you are blocked and cannot complete the task, return:

```json
{{
  "task_id": {task_id},
  "status": "blocked",
  "files_created": [],
  "files_modified": [],
  "tests_written": [],
  "tests_passed": false,
  "notes": "<explain what is blocking you>"
}}
```

Return ONLY the JSON object. No markdown fences, no commentary.
"""

# --- Sub-agent spawner data --------------------------------------------------

# Default timeout per sub-agent invocation in seconds (10 minutes).
SUBAGENT_DEFAULT_TIMEOUT = 600

# Maximum turns for claude sub-agents.
SUBAGENT_MAX_TURNS = 50

PROFILER_SKIP_DIRS: set[str] = {
    "node_modules",
    ".git",
    "__pycache__",
    "dist",
    "build",
    "out",
    "target",
    "coverage",
    ".svn",
    ".next",
    ".nuxt",
    "vendor",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}


def now_local() -> dt.datetime:
    return dt.datetime.now().astimezone()


def print_status(message: str) -> None:
    print(message, flush=True)
