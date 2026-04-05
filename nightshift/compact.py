"""Handoff compaction -- merges numbered handoff files into weekly summaries."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import TypedDict

from nightshift.constants import HANDOFF_COMPACTION_THRESHOLD
from nightshift.types import CompactionResult

# Matches numbered handoff files like 0001.md, 0026.md.
_NUMBERED_RE = re.compile(r"^\d{4}\.md$")

# Section header regex (## Something).
_SECTION_RE = re.compile(r"^##\s+(.+)$")

# Extract date from **Date**: YYYY-MM-DD line.
_DATE_RE = re.compile(r"\*\*Date\*\*:\s*(\d{4}-\d{2}-\d{2})")

# Extract version from **Version**: ... line.
_VERSION_RE = re.compile(r"\*\*Version\*\*:\s*(.+)")

# Extract session number from # Handoff #NNNN.
_SESSION_RE = re.compile(r"^#\s+Handoff\s+#(\d+)")


class _ParsedHandoff(TypedDict):
    """Internal schema extracted from numbered handoff files."""

    session: str
    date: str
    version: str
    built: str
    decisions: str
    known_issues: str
    state: str


def _numbered_handoff_files(handoffs_dir: Path) -> list[Path]:
    """Return numbered handoff files sorted by name."""
    files: list[Path] = []
    if not handoffs_dir.is_dir():
        return files
    for entry in handoffs_dir.iterdir():
        if entry.is_file() and _NUMBERED_RE.match(entry.name):
            files.append(entry)
    files.sort(key=lambda p: p.name)
    return files


def _parse_handoff(path: Path) -> _ParsedHandoff:
    """Extract key fields from a handoff file.

    Returns a dict with keys: session, date, version, built, decisions,
    known_issues, state.  Missing sections default to empty string.
    """
    text = path.read_text(encoding="utf-8")
    result: _ParsedHandoff = {
        "session": "",
        "date": "",
        "version": "",
        "built": "",
        "decisions": "",
        "known_issues": "",
        "state": "",
    }

    # Extract header fields
    m = _SESSION_RE.search(text)
    if m:
        result["session"] = m.group(1)

    m = _DATE_RE.search(text)
    if m:
        result["date"] = m.group(1)

    m = _VERSION_RE.search(text)
    if m:
        result["version"] = m.group(1).strip()

    # Extract sections by splitting on ## headers
    section_map: dict[str, str] = {}
    current_section = ""
    current_lines: list[str] = []
    for line in text.splitlines():
        header_match = _SECTION_RE.match(line)
        if header_match:
            if current_section:
                section_map[current_section] = "\n".join(current_lines).strip()
            current_section = header_match.group(1).strip()
            current_lines = []
        elif current_section:
            current_lines.append(line)
    if current_section:
        section_map[current_section] = "\n".join(current_lines).strip()

    # Map sections to result keys
    for key in section_map:
        lower = key.lower()
        if "built" in lower:
            result["built"] = section_map[key]
        elif "decision" in lower:
            result["decisions"] = section_map[key]
        elif "known" in lower or "issue" in lower:
            result["known_issues"] = section_map[key]
        elif "state" in lower or "current" in lower:
            result["state"] = section_map[key]

    return result


def _summarize_built(built_text: str) -> str:
    """Extract a one-line summary from the 'What I Built' section.

    Takes the first bullet point (the main feature line) and truncates to
    a reasonable length.  Falls back to the first 120 chars if no bullet.
    """
    for line in built_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            summary = stripped[2:].strip()
            # Remove leading ** bold markers
            summary = re.sub(r"^\*\*(.+?)\*\*", r"\1", summary)
            if len(summary) > 120:
                summary = summary[:117] + "..."
            return summary
    # Fallback: first non-empty line
    for line in built_text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return "(no details)"


def _iso_week_string(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYY-WNN format.

    Falls back to 'unknown' if the date can't be parsed.
    """
    parts = date_str.split("-")
    if len(parts) != 3:
        return "unknown"
    try:
        d = dt.date(int(parts[0]), int(parts[1]), int(parts[2]))
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    except (ValueError, IndexError):
        return "unknown"


def _unique_weekly_path(weekly_dir: Path, week_str: str) -> Path:
    """Return a path for the weekly file, adding a suffix if one already exists."""
    base = weekly_dir / f"week-{week_str}.md"
    if not base.exists():
        return base
    # Add letter suffixes: b, c, d, ...
    for suffix_ord in range(ord("b"), ord("z") + 1):
        candidate = weekly_dir / f"week-{week_str}{chr(suffix_ord)}.md"
        if not candidate.exists():
            return candidate
    # Extreme fallback
    return weekly_dir / f"week-{week_str}z2.md"


def _build_weekly_summary(
    parsed: list[_ParsedHandoff],
    first_session: str,
    last_session: str,
) -> str:
    """Generate a weekly summary from parsed handoff data."""
    dates = [p["date"] for p in parsed if p["date"]]
    first_date = dates[0] if dates else "unknown"
    last_date = dates[-1] if dates else "unknown"

    # Version range
    versions = [p["version"] for p in parsed if p["version"]]
    first_version = versions[0] if versions else "unknown"
    last_version = versions[-1] if versions else "unknown"
    version_str = first_version if first_version == last_version else f"{first_version} -> {last_version}"

    # Progress: extract from first and last state sections
    first_state = parsed[0]["state"] if parsed[0]["state"] else ""
    last_state = parsed[-1]["state"] if parsed[-1]["state"] else ""

    # Collect "What Was Built" lines
    built_lines: list[str] = []
    for p in parsed:
        session = p["session"] or "?"
        summary = _summarize_built(p["built"]) if p["built"] else "(no changes)"
        built_lines.append(f"- Session {session}: {summary}")

    # Collect decisions still active (from the last handoff)
    last_decisions = parsed[-1]["decisions"]
    decisions_section = ""
    if last_decisions:
        decisions_section = last_decisions

    # Collect bugs still open (from the last handoff)
    last_issues = parsed[-1]["known_issues"]
    issues_section = ""
    if last_issues:
        issues_section = last_issues

    lines: list[str] = []
    week_str = _iso_week_string(first_date)
    lines.append(f"# Week {week_str} Summary")
    lines.append(f"**Sessions**: {first_session}-{last_session}")
    if first_date == last_date:
        lines.append(f"**Dates**: {first_date}")
    else:
        lines.append(f"**Dates**: {first_date} to {last_date}")
    lines.append(f"**Version**: {version_str}")
    lines.append("")
    lines.append("## Progress")
    if first_state and last_state:
        # Try to extract percentages from both
        lines.append("Start of batch:")
        for sline in first_state.splitlines():
            stripped = sline.strip()
            if stripped.startswith("- ") and ":" in stripped:
                lines.append(f"  {stripped}")
        lines.append("End of batch:")
        for sline in last_state.splitlines():
            stripped = sline.strip()
            if stripped.startswith("- ") and ":" in stripped:
                lines.append(f"  {stripped}")
    elif last_state:
        for sline in last_state.splitlines():
            stripped = sline.strip()
            if stripped.startswith("- ") and ":" in stripped:
                lines.append(stripped)
    else:
        lines.append("- (no state data)")
    lines.append("")
    lines.append("## What Was Built")
    lines.extend(built_lines)
    lines.append("")

    if decisions_section:
        lines.append("## Decisions Still Active")
        lines.append(decisions_section)
        lines.append("")

    if issues_section:
        lines.append("## Bugs Still Open")
        lines.append(issues_section)
        lines.append("")

    return "\n".join(lines) + "\n"


def compact_handoffs(
    handoffs_dir: str,
    threshold: int = HANDOFF_COMPACTION_THRESHOLD,
) -> CompactionResult:
    """Compact numbered handoff files into a weekly summary when threshold is reached.

    Scans *handoffs_dir* for files matching ``NNNN.md``.  If the count is
    at least *threshold*, reads them all, generates a weekly summary in
    ``handoffs_dir/weekly/``, and deletes the originals.

    Returns a :class:`CompactionResult` with paths of compacted files,
    the weekly file written, and any errors.
    """
    errors: list[str] = []
    hdir = Path(handoffs_dir)
    files = _numbered_handoff_files(hdir)

    if len(files) < threshold:
        return {"compacted": [], "weekly_file": "", "errors": []}

    # Parse all files
    parsed: list[_ParsedHandoff] = []
    for f in files:
        try:
            parsed.append(_parse_handoff(f))
        except OSError as exc:
            errors.append(f"Failed to read {f.name}: {exc}")

    if not parsed:
        return {"compacted": [], "weekly_file": "", "errors": errors}

    # Determine session range from filenames
    first_session = files[0].stem
    last_session = files[-1].stem

    # Determine week from the first file's date
    first_date = parsed[0]["date"]
    week_str = _iso_week_string(first_date) if first_date else "unknown"

    # Write weekly summary
    weekly_dir = hdir / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    weekly_path = _unique_weekly_path(weekly_dir, week_str)

    summary = _build_weekly_summary(parsed, first_session, last_session)
    try:
        weekly_path.write_text(summary, encoding="utf-8")
    except OSError as exc:
        errors.append(f"Failed to write weekly summary: {exc}")
        return {"compacted": [], "weekly_file": "", "errors": errors}

    # Delete originals
    compacted: list[str] = []
    for f in files:
        try:
            f.unlink()
            compacted.append(f.name)
        except OSError as exc:
            errors.append(f"Failed to delete {f.name}: {exc}")

    return {
        "compacted": compacted,
        "weekly_file": str(weekly_path),
        "errors": errors,
    }
