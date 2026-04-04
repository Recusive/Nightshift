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


def now_local() -> dt.datetime:
    return dt.datetime.now().astimezone()


def print_status(message: str) -> None:
    print(message, flush=True)
