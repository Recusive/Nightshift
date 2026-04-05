#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_DIR="${1:-${NIGHTSHIFT_TASK_DIR:-$REPO_DIR/docs/tasks}}"

python3 - "$TASK_DIR" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

ACTIVE_STATUSES = {"pending", "blocked", "in-progress"}
KNOWN_STATUSES = ACTIVE_STATUSES | {"done"}
PRIORITY_ORDER = {"urgent": 0, "normal": 1, "low": 2}
FIELD_RE = re.compile(r"^\s*#*\s*([A-Za-z_]+):\s*(.*?)\s*$")
TITLE_RE = re.compile(r"^\s*#+\s+(.*?)\s*$")


def find_title(lines: list[str]) -> str:
    for line in lines:
        match = TITLE_RE.match(line)
        if match:
            title = match.group(1).strip()
            if title and not FIELD_RE.match(title):
                return title
    return ""


def parse_frontmatter(lines: list[str]) -> tuple[bool, dict[str, str], list[str]]:
    if not lines or lines[0].strip() != "---":
        return False, {}, lines

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        return False, {}, lines[1:]

    values: dict[str, str] = {}
    valid = True
    for line in lines[1:end_index]:
        if not line.strip():
            continue
        if ":" not in line:
            valid = False
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()

    return valid, values, lines[end_index + 1 :]


def salvage_fields(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        match = FIELD_RE.match(line)
        if match and match.group(1) not in values:
            values[match.group(1)] = match.group(2)
    return values


def parse_task(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    has_valid_frontmatter, frontmatter, body_lines = parse_frontmatter(lines)
    salvaged = salvage_fields(lines)

    title = find_title(body_lines) or find_title(lines)
    status = frontmatter.get("status") or salvaged.get("status", "")
    priority = frontmatter.get("priority") or salvaged.get("priority", "")
    target = frontmatter.get("target") or salvaged.get("target", "?")
    environment = frontmatter.get("environment") or salvaged.get("environment") or "internal"

    valid = (
        has_valid_frontmatter
        and status in KNOWN_STATUSES
        and priority in PRIORITY_ORDER
        and bool(title)
    )
    reasons: list[str] = []
    if not has_valid_frontmatter:
        reasons.append("frontmatter")
    if status not in KNOWN_STATUSES:
        reasons.append("status")
    if priority not in PRIORITY_ORDER:
        reasons.append("priority")
    if not title:
        reasons.append("title")

    return {
        "id": path.stem,
        "status": status or "?",
        "priority": priority or "?",
        "target": target,
        "environment": environment,
        "title": title or "(missing title)",
        "valid": valid,
        "reason": ", ".join(dict.fromkeys(reasons)) or "unknown",
    }


def render_header(title: str) -> None:
    print(title)
    print("=" * len(title))


def render_rows(rows: list[dict[str, object]], invalid: bool = False) -> None:
    print("  ID    Status         Priority  Target    Env         Title")
    for row in rows:
        label = "invalid" if invalid else str(row["status"])
        suffix = f" ({row['reason']})" if invalid else ""
        print(
            "  "
            f"{row['id']:>4}  "
            f"[{label:<11}]  "
            f"{row['priority']:<8}  "
            f"{row['target']:<8}  "
            f"{row['environment']:<10}  "
            f"{row['title']}{suffix}"
        )


task_dir = Path(sys.argv[1])
if not task_dir.is_dir():
    print(f"Task directory not found: {task_dir}", file=sys.stderr)
    raise SystemExit(1)

rows = [parse_task(path) for path in sorted(task_dir.glob("[0-9][0-9][0-9][0-9].md"))]
active = [
    row
    for row in rows
    if bool(row["valid"]) and str(row["status"]) in ACTIVE_STATUSES
]
active.sort(key=lambda row: (PRIORITY_ORDER[str(row["priority"])], int(str(row["id"]))))
invalid = [row for row in rows if not bool(row["valid"])]
invalid.sort(key=lambda row: int(str(row["id"])))

render_header("TASK QUEUE")
if active:
    render_rows(active)
else:
    print("  No pending, blocked, or in-progress tasks.")

if invalid:
    print()
    render_header("INVALID TASK FILES")
    render_rows(invalid, invalid=True)
PY
