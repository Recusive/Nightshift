"""Handoff compaction — merge old numbered handoffs into weekly summaries.

Standalone — no dependency on target project code.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

COMPACTION_THRESHOLD = 7  # Compact when this many numbered handoffs exist


def compact_handoffs(
    handoffs_dir: str | Path,
) -> dict[str, Any]:
    """Compact numbered handoff files into weekly summaries.

    Moves content from 0001.md, 0002.md, etc. into
    weekly/week-YYYY-WNN.md when COMPACTION_THRESHOLD+ files exist.

    Preserves LATEST.md and README.md. Deletes compacted files.

    Returns dict with 'compacted' (list), 'weekly_file' (str), 'errors' (list).
    """
    result: dict[str, Any] = {"compacted": [], "weekly_file": "", "errors": []}
    hdir = Path(handoffs_dir)
    if not hdir.is_dir():
        return result

    # Find numbered handoff files (0001.md, 0002.md, etc.)
    numbered = sorted(
        f
        for f in hdir.glob("[0-9]*.md")
        if f.stem.isdigit()
    )

    if len(numbered) < COMPACTION_THRESHOLD:
        return result

    # Keep the newest 2, compact the rest
    to_compact = numbered[:-2]
    if not to_compact:
        return result

    # Determine week identifier from the oldest file
    now = datetime.now()
    week_id = now.strftime("%Y-W%V")

    weekly_dir = hdir / "weekly"
    weekly_dir.mkdir(exist_ok=True)
    weekly_file = weekly_dir / f"week-{week_id}.md"

    # Build compacted content
    sections = [f"# Weekly Summary — {week_id}\n"]
    for f in to_compact:
        try:
            content = f.read_text(encoding="utf-8").strip()
            sections.append(f"\n---\n\n## From {f.name}\n\n{content}\n")
        except OSError as e:
            result["errors"].append(f"Read {f.name}: {e}")
            continue

    # Write weekly summary
    try:
        weekly_file.write_text("\n".join(sections), encoding="utf-8")
        result["weekly_file"] = str(weekly_file)
    except OSError as e:
        result["errors"].append(f"Write {weekly_file.name}: {e}")
        return result

    # Delete compacted files
    for f in to_compact:
        try:
            f.unlink()
            result["compacted"].append(f.name)
        except OSError as e:
            result["errors"].append(f"Delete {f.name}: {e}")

    return result
