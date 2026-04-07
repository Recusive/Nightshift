"""Live formatter for daemon stream-json output.

Reads JSONL from stdin, prints human-readable status lines.
Raw JSON still goes to the log file via tee; this script filters
what the operator sees in the terminal.

Two modes:
  --raw       Show abbreviated JSONL (tool names + message snippets)
  --pretty    Show structured human-readable output (default)

Handles both Claude and Codex stream formats.
"""
from __future__ import annotations

import json
import sys
import time

MODE = "pretty"
if "--raw" in sys.argv:
    MODE = "raw"

# Track state for structured output
_last_tool = ""
_consecutive_reads = 0
_session_start = time.time()


def _elapsed() -> str:
    mins = int(time.time() - _session_start) // 60
    secs = int(time.time() - _session_start) % 60
    return f"{mins:02d}:{secs:02d}"


def _short_path(path: str) -> str:
    """Shorten a file path for display."""
    if not path:
        return ""
    # Remove common prefixes
    for prefix in ["/Users/", "/home/", "/tmp/"]:
        if path.startswith(prefix):
            parts = path.split("/")
            # Keep last 3 parts
            return "/".join(parts[-3:]) if len(parts) > 3 else path
    return path


def _truncate(text: str, limit: int = 100) -> str:
    text = text.replace("\n", " ").strip()
    return text[:limit] + "..." if len(text) > limit else text


def _format_tool_pretty(name: str, inp: dict) -> str | None:
    """Format a tool call as a human-readable action."""
    global _last_tool, _consecutive_reads

    if name == "Read":
        path = _short_path(inp.get("file_path", ""))
        _consecutive_reads += 1
        if _consecutive_reads > 3 and _last_tool == "Read":
            # Collapse consecutive reads
            return None
        _last_tool = "Read"
        return f"  [{_elapsed()}] reading {path}"

    if _last_tool == "Read" and _consecutive_reads > 3:
        # Flush collapsed reads
        print(f"  [{_elapsed()}] ... read {_consecutive_reads} files total", flush=True)
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

    # Default
    return f"  [{_elapsed()}] {name}: {_truncate(str(inp), 70)}"


def _format_text_pretty(text: str) -> str | None:
    """Format agent text output as structured status."""
    if len(text) < 15:
        return None

    # Highlight key markers
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

    # Show first meaningful line
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


# --- Raw mode formatters (original behavior) ---

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
                return f"  FILE  {c.get('kind', '')} {c.get('path', '').split('/')[-1]}"
    return None


def main() -> None:
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
