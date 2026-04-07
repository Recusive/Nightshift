"""Formatter for daemon stream-json output.

Three modes:
  --pretty    Live terminal: timestamps + one-line summaries (default, stdin)
  --raw       Live terminal: abbreviated JSONL (stdin)
  --report F  Post-session: full structured markdown report from raw JSONL file

The live modes (--pretty, --raw) read from stdin during the session.
The report mode reads a completed raw JSONL file and writes a full
session transcript to stdout.

Handles both Claude and Codex stream formats.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

MODE = "pretty"
REPORT_FILE = ""
if "--raw" in sys.argv:
    MODE = "raw"
elif "--report" in sys.argv:
    MODE = "report"
    idx = sys.argv.index("--report")
    if idx + 1 < len(sys.argv):
        REPORT_FILE = sys.argv[idx + 1]

# Track state for live output
_last_tool = ""
_consecutive_reads = 0
_session_start = time.time()


def _elapsed() -> str:
    mins = int(time.time() - _session_start) // 60
    secs = int(time.time() - _session_start) % 60
    return f"{mins:02d}:{secs:02d}"


def _short_path(path: str) -> str:
    """Shorten absolute paths to repo-relative."""
    if not path:
        return ""
    # Try to find repo-relative path by looking for known root markers
    for marker in (".recursive/", "Recursive/", "nightshift/", ".recursive.json"):
        idx = path.find(marker)
        if idx != -1:
            return path[idx:]
    # Fallback: strip home directory prefix
    for prefix in ["/Users/", "/home/", "/tmp/"]:
        if path.startswith(prefix):
            parts = path.split("/")
            return "/".join(parts[-3:]) if len(parts) > 3 else path
    return path


def _truncate(text: str, limit: int = 100) -> str:
    text = text.replace("\n", " ").strip()
    return text[:limit] + "..." if len(text) > limit else text


# =====================================================================
# REPORT MODE -- full structured session transcript
# =====================================================================


def _parse_events(log_path: str) -> list[dict]:
    """Parse all events from a raw JSONL log file."""
    events: list[dict] = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                pass
    return events


def _extract_session_meta(events: list[dict]) -> dict:
    """Extract session metadata from init event and usage totals."""
    meta: dict = {
        "model": "",
        "session_id": "",
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }
    for ev in events:
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            meta["model"] = ev.get("model", "")
            meta["session_id"] = ev.get("session_id", "")
        if ev.get("type") == "assistant":
            usage = ev.get("message", {}).get("usage", {})
            meta["total_input_tokens"] += usage.get("input_tokens", 0)
            meta["total_output_tokens"] += usage.get("output_tokens", 0)
    return meta


def _collect_agent_content(events: list[dict]) -> list[dict]:
    """Collect all agent text, thinking, and tool calls in order."""
    items: list[dict] = []
    pending_tools: dict[str, dict] = {}  # tool_use_id -> tool call info

    for ev in events:
        if ev.get("type") == "assistant":
            for block in ev.get("message", {}).get("content", []):
                btype = block.get("type", "")
                if btype == "text":
                    text = block.get("text", "").strip()
                    if text:
                        items.append({"kind": "text", "content": text})
                elif btype == "thinking":
                    thinking = block.get("thinking", "").strip()
                    if thinking:
                        items.append({"kind": "thinking", "content": thinking})
                elif btype == "tool_use":
                    tool_id = block.get("id", "")
                    name = block.get("name", "")
                    inp = block.get("input", {})
                    entry = {
                        "kind": "tool",
                        "name": name,
                        "input": inp,
                        "result": "",
                    }
                    items.append(entry)
                    if tool_id:
                        pending_tools[tool_id] = entry

        elif ev.get("type") == "result":
            tool_id = ev.get("tool_use_id", "")
            if tool_id and tool_id in pending_tools:
                result_text = ev.get("result", "")
                if isinstance(result_text, list):
                    parts = []
                    for r in result_text:
                        if isinstance(r, dict) and r.get("type") == "text":
                            parts.append(r.get("text", ""))
                    result_text = "\n".join(parts)
                elif isinstance(result_text, dict):
                    result_text = result_text.get("text", str(result_text))
                pending_tools[tool_id]["result"] = str(result_text)[:3000]

    return items


def _format_tool_for_report(item: dict) -> str:
    """Format a tool call + result for the report."""
    name = item["name"]
    inp = item["input"]
    result = item.get("result", "")

    if name == "Read":
        path = _short_path(inp.get("file_path", ""))
        # Don't dump file contents -- just note what was read
        lines = result.count("\n") + 1 if result else 0
        return f"**Read** `{path}` ({lines} lines)"

    if name == "Write":
        path = _short_path(inp.get("file_path", ""))
        content = inp.get("content", "")
        preview = content[:500] + "..." if len(content) > 500 else content
        return f"**Write** `{path}`\n```\n{preview}\n```"

    if name == "Edit":
        path = _short_path(inp.get("file_path", ""))
        old = inp.get("old_string", "")[:200]
        new = inp.get("new_string", "")[:200]
        return f"**Edit** `{path}`\n```diff\n- {old}\n+ {new}\n```"

    if name == "Bash":
        cmd = inp.get("command", "")
        desc = inp.get("description", "")
        header = f"**Run** {desc}" if desc else f"**Run**"
        result_preview = result[:1000] + "..." if len(result) > 1000 else result
        return f"{header}\n```bash\n$ {cmd}\n```\n```\n{result_preview}\n```"

    if name == "Grep":
        pattern = inp.get("pattern", "")
        path = _short_path(inp.get("path", "."))
        result_preview = result[:800] + "..." if len(result) > 800 else result
        return f"**Search** `{pattern}` in `{path}`\n```\n{result_preview}\n```"

    if name == "Glob":
        pattern = inp.get("pattern", "")
        result_preview = result[:500] + "..." if len(result) > 500 else result
        return f"**Find** `{pattern}`\n```\n{result_preview}\n```"

    if name == "Agent":
        desc = inp.get("description", "")
        return f"**Sub-agent** {desc}"

    # Generic
    inp_str = json.dumps(inp, indent=2)[:300]
    return f"**{name}**\n```\n{inp_str}\n```"


def _is_framework_path(path: str) -> bool:
    """Check if a path is inside Recursive/ (the framework), not .recursive/ (runtime)."""
    # Normalize: find the last occurrence of Recursive/ that isn't .recursive/
    parts = path.split("/")
    for i, part in enumerate(parts):
        if part == "Recursive" and (i == 0 or parts[i - 1] != ".recursive"):
            return True
    return False


def _is_checkpoint_text(text: str) -> str | None:
    """Return checkpoint name if text contains a checkpoint block."""
    markers = [
        "SIGNAL ANALYSIS",
        "TRADEOFF ANALYSIS",
        "PRE-COMMITMENT",
        "PENTEST REPORT",
        "ROLE OVERRIDE",
        "ROLE DECISION",
        "AUTONOMY SCORE",
        "OVERSEER AUDIT",
        "STRATEGY REPORT",
        "FRICTION ANALYSIS",
    ]
    for m in markers:
        if m in text:
            return m
    return None


def generate_report(log_path: str) -> str:
    """Generate a structured markdown report from a raw JSONL session log."""
    events = _parse_events(log_path)
    if not events:
        return "# Empty Session\n\nNo events found in log.\n"

    meta = _extract_session_meta(events)
    items = _collect_agent_content(events)

    # Classify content into sections
    files_read: list[str] = []
    files_written: list[str] = []
    files_edited: list[str] = []
    commands: list[dict] = []
    checkpoints: dict[str, str] = {}
    agent_messages: list[str] = []
    thinking_blocks: list[str] = []

    for item in items:
        if item["kind"] == "text":
            text = item["content"]
            cp = _is_checkpoint_text(text)
            if cp:
                checkpoints[cp] = text
            else:
                agent_messages.append(text)

        elif item["kind"] == "thinking":
            thinking_blocks.append(item["content"])

        elif item["kind"] == "tool":
            name = item["name"]
            inp = item["input"]
            if name == "Read":
                files_read.append(_short_path(inp.get("file_path", "")))
            elif name == "Write":
                path = _short_path(inp.get("file_path", ""))
                files_written.append(path)
            elif name == "Edit":
                path = _short_path(inp.get("file_path", ""))
                files_edited.append(path)
            elif name == "Bash":
                commands.append(item)

    # Build the report
    lines: list[str] = []
    session_name = Path(log_path).stem

    # --- Header ---
    lines.append(f"# Session: {session_name}")
    lines.append("")
    lines.append(f"**Model:** {meta['model']}")
    lines.append(
        f"**Tokens:** {meta['total_input_tokens']:,} in "
        f"/ {meta['total_output_tokens']:,} out"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Checkpoints (signal analysis, tradeoffs, reports) ---
    for cp_name in [
        "SIGNAL ANALYSIS",
        "TRADEOFF ANALYSIS",
        "PRE-COMMITMENT",
        "ROLE DECISION",
        "ROLE OVERRIDE",
        "PENTEST REPORT",
        "AUTONOMY SCORE",
        "OVERSEER AUDIT",
        "STRATEGY REPORT",
        "FRICTION ANALYSIS",
    ]:
        if cp_name in checkpoints:
            lines.append(f"## {cp_name.title()}")
            lines.append("")
            lines.append("```")
            lines.append(checkpoints[cp_name].strip().strip("`").strip())
            lines.append("```")
            lines.append("")

    # --- Context: files read ---
    if files_read:
        # Deduplicate preserving order
        seen: set[str] = set()
        unique_reads: list[str] = []
        for f in files_read:
            if f not in seen:
                seen.add(f)
                unique_reads.append(f)
        lines.append("## Context (files read)")
        lines.append("")
        for f in unique_reads:
            lines.append(f"- `{f}`")
        lines.append("")

    # --- Commands run ---
    if commands:
        lines.append("## Commands & Probes")
        lines.append("")
        for cmd_item in commands:
            inp = cmd_item["input"]
            desc = inp.get("description", "")
            cmd = inp.get("command", "")
            result = cmd_item.get("result", "")
            if desc:
                lines.append(f"### {desc}")
            lines.append("```bash")
            lines.append(f"$ {cmd}")
            lines.append("```")
            if result:
                result_preview = (
                    result[:1500] + "\n... (truncated)"
                    if len(result) > 1500
                    else result
                )
                lines.append("```")
                lines.append(result_preview.strip())
                lines.append("```")
            lines.append("")

    # --- Agent reasoning (text output, not thinking) ---
    # Filter out very short status messages
    substantive = [m for m in agent_messages if len(m) > 50]
    if substantive:
        lines.append("## Agent Communication")
        lines.append("")
        for msg in substantive:
            lines.append(msg)
            lines.append("")

    # --- Actions: files written/edited ---
    if files_written or files_edited:
        lines.append("## Actions")
        lines.append("")
        if files_written:
            lines.append("### Files Created")
            for f in files_written:
                warning = ""
                if _is_framework_path(f):
                    warning = " -- BOUNDARY VIOLATION (framework file)"
                lines.append(f"- `{f}`{warning}")
            lines.append("")
        if files_edited:
            lines.append("### Files Modified")
            for f in files_edited:
                warning = ""
                if _is_framework_path(f):
                    warning = " -- BOUNDARY VIOLATION (framework file)"
                lines.append(f"- `{f}`{warning}")
            lines.append("")

    # --- Key thinking (first and last, not all) ---
    if thinking_blocks:
        lines.append("## Agent Thinking (key excerpts)")
        lines.append("")
        # First thinking block = initial reasoning
        lines.append("### Initial")
        first = thinking_blocks[0]
        if len(first) > 1000:
            first = first[:1000] + "\n... (truncated)"
        lines.append(f"> {first.replace(chr(10), chr(10) + '> ')}")
        lines.append("")
        # Last thinking block = final reasoning
        if len(thinking_blocks) > 1:
            lines.append("### Final")
            last = thinking_blocks[-1]
            if len(last) > 1000:
                last = last[:1000] + "\n... (truncated)"
            lines.append(f"> {last.replace(chr(10), chr(10) + '> ')}")
            lines.append("")

    return "\n".join(lines)


# =====================================================================
# LIVE MODES -- pretty + raw (unchanged, for terminal during session)
# =====================================================================


def _format_tool_pretty(name: str, inp: dict) -> str | None:
    """Format a tool call as a human-readable action."""
    global _last_tool, _consecutive_reads

    if name == "Read":
        path = _short_path(inp.get("file_path", ""))
        _consecutive_reads += 1
        if _consecutive_reads > 3 and _last_tool == "Read":
            return None
        _last_tool = "Read"
        return f"  [{_elapsed()}] reading {path}"

    if _last_tool == "Read" and _consecutive_reads > 3:
        print(
            f"  [{_elapsed()}] ... read {_consecutive_reads} files total",
            flush=True,
        )
    _consecutive_reads = 0
    _last_tool = name

    if name == "Edit":
        path = _short_path(inp.get("file_path", ""))
        return f"  [{_elapsed()}] editing {path}"

    if name == "Write":
        path = _short_path(inp.get("file_path", ""))
        return f"  [{_elapsed()}] writing {path}"

    if name == "Bash":
        desc = inp.get("description", "")
        cmd = inp.get("command", "")
        if desc:
            return f"  [{_elapsed()}] running: {_truncate(desc, 80)}"
        return f"  [{_elapsed()}] $ {_truncate(cmd, 80)}"

    if name == "Grep":
        pattern = inp.get("pattern", "")
        path = _short_path(inp.get("path", ""))
        return f"  [{_elapsed()}] searching '{_truncate(pattern, 40)}' in {path or '.'}"

    if name == "Glob":
        pattern = inp.get("pattern", "")
        return f"  [{_elapsed()}] finding files: {pattern}"

    if name == "Agent":
        desc = inp.get("description", "")
        return f"  [{_elapsed()}] launching sub-agent: {desc}"

    if name == "SendMessage":
        to = inp.get("to", "")
        return f"  [{_elapsed()}] messaging agent: {to}"

    if name in ("TaskCreate", "TaskUpdate", "TaskList", "TaskGet"):
        return f"  [{_elapsed()}] {name.lower().replace('task', 'task ')}"

    if name == "WebSearch":
        query = inp.get("query", "")
        return f"  [{_elapsed()}] searching web: {_truncate(query, 60)}"

    if name == "WebFetch":
        url = inp.get("url", "")
        return f"  [{_elapsed()}] fetching: {_truncate(url, 60)}"

    return f"  [{_elapsed()}] {name}: {_truncate(str(inp), 70)}"


def _format_text_pretty(text: str) -> str | None:
    """Format agent text output as structured status."""
    if len(text) < 15:
        return None

    markers = {
        "SIGNAL ANALYSIS": "analyzing signals",
        "TRADEOFF ANALYSIS": "evaluating tradeoffs",
        "PRE-COMMITMENT": "committing to metric",
        "TASK QUEUE SNAPSHOT": "scanning task queue",
        "ROLE DECISION": "deciding role",
        "ROLE OVERRIDE": "overriding role",
        "SESSION STATUS": "reporting status",
        "PROPOSAL": "proposing work",
        "PRE-PUSH CHECKLIST": "running pre-push checklist",
        "SESSION COMPLETE": "session complete",
        "GENERATED TASKS": "generating tasks",
        "AUTONOMY SCORE": "measuring autonomy",
        "OVERSEER AUDIT": "auditing queue",
        "PENTEST REPORT": "pentest report",
        "FRICTION ANALYSIS": "analyzing friction",
        "Commitment Check": "checking previous commitment",
    }
    for marker, label in markers.items():
        if marker in text:
            return f"  [{_elapsed()}] >>> {label}"

    return f"  [{_elapsed()}] {_truncate(text, 90)}"


def format_claude_pretty(event: dict) -> str | None:
    """Format a Claude event for structured display."""
    if event.get("type") != "assistant":
        return None
    for block in event.get("message", {}).get("content", []):
        if block.get("type") == "tool_use":
            return _format_tool_pretty(block.get("name", ""), block.get("input", {}))
        if block.get("type") == "text":
            return _format_text_pretty(block.get("text", ""))
    return None


def format_codex_pretty(event: dict) -> str | None:
    """Format a Codex event for structured display."""
    etype = event.get("type", "")

    if etype == "item.completed":
        item = event.get("item", {})
        itype = item.get("type", "")

        if itype == "command_execution":
            cmd = item.get("command", "")
            exit_code = item.get("exit_code")
            status = "ok" if exit_code == 0 else f"exit {exit_code}"
            if cmd.startswith("/bin/zsh -lc "):
                cmd = cmd[14:].strip("'\"")
            return f"  [{_elapsed()}] $ {_truncate(cmd, 80)} [{status}]"

        if itype == "agent_message":
            return _format_text_pretty(item.get("text", ""))

        if itype == "file_change":
            changes = item.get("changes", [])
            for c in changes:
                path = c.get("path", "")
                kind = c.get("kind", "")
                short = _short_path(path)
                return f"  [{_elapsed()}] {kind} {short}"

    if etype == "turn.completed":
        usage = event.get("usage", {})
        out = usage.get("output_tokens", 0)
        return f"  [{_elapsed()}] --- turn complete ({out} tokens)"

    return None


# --- Raw mode formatters ---

def format_claude_raw(event: dict) -> str | None:
    if event.get("type") != "assistant":
        return None
    for block in event.get("message", {}).get("content", []):
        if block.get("type") == "tool_use":
            name = block.get("name", "")
            desc = block.get("input", {}).get("description", "")
            inp = str(block.get("input", {}))
            if desc:
                return f"  TOOL  {name}: {_truncate(desc, 80)}"
            return f"  TOOL  {name}: {_truncate(inp, 80)}"
        if block.get("type") == "text":
            text = block.get("text", "")
            if len(text) < 15:
                continue
            return f"  MSG   {_truncate(text)}"
    return None


def format_codex_raw(event: dict) -> str | None:
    etype = event.get("type", "")
    if etype == "item.completed":
        item = event.get("item", {})
        if item.get("type") == "command_execution":
            cmd = item.get("command", "")
            exit_code = item.get("exit_code")
            status = "ok" if exit_code == 0 else f"exit {exit_code}"
            return f"  CMD   [{status}] {_truncate(cmd, 90)}"
        if item.get("type") == "agent_message":
            text = item.get("text", "")
            if len(text) >= 15:
                return f"  MSG   {_truncate(text)}"
        if item.get("type") == "file_change":
            for c in item.get("changes", []):
                return (
                    f"  FILE  {c.get('kind', '')} "
                    f"{c.get('path', '').split('/')[-1]}"
                )
    return None


def main() -> None:
    if MODE == "report":
        if not REPORT_FILE:
            print("Usage: format-stream.py --report <raw-log.log>", file=sys.stderr)
            sys.exit(1)
        print(generate_report(REPORT_FILE))
        return

    for line in sys.stdin:
        try:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                if len(line) > 10 and not line.startswith("{"):
                    print(f"  ERR   {_truncate(line)}", flush=True)
                continue

            if MODE == "pretty":
                result = format_claude_pretty(event)
                if result is None:
                    result = format_codex_pretty(event)
            else:
                result = format_claude_raw(event)
                if result is None:
                    result = format_codex_raw(event)

            if result is not None:
                print(result, flush=True)
        except Exception as exc:
            print(f"  ERR   formatter: {type(exc).__name__}", flush=True)
            continue


if __name__ == "__main__":
    main()
