#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_DIR="${1:-${RECURSIVE_TASK_DIR:-$REPO_DIR/.recursive/tasks}}"

python3 - "$TASK_DIR" <<'PY'
from __future__ import annotations

from datetime import date
from pathlib import Path
import re
import sys

VALID_STATUSES = {"pending", "in-progress", "done", "blocked"}
VALID_PRIORITIES = {"urgent", "normal", "low"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_valid_date(value: str) -> bool:
    if not DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def parse_frontmatter(path: Path) -> tuple[dict[str, str] | None, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None, ["frontmatter: missing opening --- delimiter"]

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        return None, ["frontmatter: missing closing --- delimiter"]

    values: dict[str, str] = {}
    errors: list[str] = []
    for lineno, line in enumerate(lines[1:end_index], start=2):
        if not line.strip():
            continue
        if ":" not in line:
            errors.append(f"frontmatter line {lineno}: missing ':'")
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if not key or key.startswith("#"):
            errors.append(f"frontmatter line {lineno}: invalid field {key!r}")
            continue
        values[key] = value.strip()

    return values, errors


def validate_task(path: Path) -> list[str]:
    frontmatter, errors = parse_frontmatter(path)
    if frontmatter is None:
        return errors

    issues = list(errors)
    for field in ("status", "priority", "target", "created"):
        if not frontmatter.get(field):
            issues.append(f"{field}: missing")

    status = frontmatter.get("status", "")
    if status and status not in VALID_STATUSES:
        issues.append(
            "status: invalid value "
            f"{status!r} (expected one of: pending, in-progress, done, blocked)"
        )

    priority = frontmatter.get("priority", "")
    if priority and priority not in VALID_PRIORITIES:
        issues.append(
            "priority: invalid value "
            f"{priority!r} (expected one of: urgent, normal, low)"
        )

    created = frontmatter.get("created", "")
    if created and not is_valid_date(created):
        issues.append(f"created: invalid date {created!r} (expected YYYY-MM-DD)")

    if status == "blocked" and not frontmatter.get("blocked_reason"):
        issues.append("blocked_reason: required when status is 'blocked'")

    if status == "done":
        completed = frontmatter.get("completed", "")
        if not completed:
            issues.append("completed: required when status is 'done'")
        elif not is_valid_date(completed):
            issues.append(f"completed: invalid date {completed!r} (expected YYYY-MM-DD)")

    return issues


task_dir = Path(sys.argv[1])
if not task_dir.is_dir():
    print(f"Task directory not found: {task_dir}", file=sys.stderr)
    raise SystemExit(1)

violations: list[tuple[Path, str]] = []
for path in sorted(task_dir.glob("[0-9][0-9][0-9][0-9].md")):
    for issue in validate_task(path):
        violations.append((path, issue))

if violations:
    print("TASK FRONTMATTER INVALID")
    print("========================")
    for path, issue in violations:
        print(f"{path}: {issue}")
    raise SystemExit(1)

print(f"All {len(list(task_dir.glob('[0-9][0-9][0-9][0-9].md')))} task files valid.")
PY
