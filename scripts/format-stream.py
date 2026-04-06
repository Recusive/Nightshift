"""Live formatter for daemon stream-json output.

Reads JSONL from stdin, prints human-readable status lines.
Raw JSON still goes to the log file via tee; this script filters
what the operator sees in the terminal.

Handles both Claude and Codex stream formats.
"""
from __future__ import annotations

import json
import sys


def _truncate(text: str, limit: int = 120) -> str:
    text = text.replace("\n", " ").strip()
    return text[:limit] + "..." if len(text) > limit else text


def format_claude(event: dict) -> str | None:
    """Format a Claude stream-json event."""
    if event.get("type") != "assistant":
        return None
    for block in event.get("message", {}).get("content", []):
        if block.get("type") == "tool_use":
            name = block.get("name", "")
            inp = str(block.get("input", {}))
            desc = block.get("input", {}).get("description", "")
            if desc:
                return f"  TOOL  {name}: {_truncate(desc, 80)}"
            return f"  TOOL  {name}: {_truncate(inp, 80)}"
        if block.get("type") == "text":
            text = block.get("text", "")
            if len(text) < 15:
                continue
            # Highlight key markers
            for marker in [
                "SYSTEM SIGNALS", "ROLE DECISION", "EXECUTING ROLE",
                "SESSION STATUS", "PROPOSAL", "PRE-PUSH CHECKLIST",
                "SESSION COMPLETE", "GENERATED TASKS",
            ]:
                if marker in text:
                    return f"  >>>   {marker}"
            return f"  MSG   {_truncate(text)}"
    return None


def format_codex(event: dict) -> str | None:
    """Format a Codex stream-json event."""
    etype = event.get("type", "")

    if etype == "item.completed":
        item = event.get("item", {})
        itype = item.get("type", "")

        if itype == "command_execution":
            cmd = item.get("command", "")
            exit_code = item.get("exit_code")
            status = "ok" if exit_code == 0 else f"exit {exit_code}"
            # Shorten the command for display
            if cmd.startswith("/bin/zsh -lc "):
                cmd = cmd[14:].strip("'\"")
            return f"  CMD   [{status}] {_truncate(cmd, 90)}"

        if itype == "agent_message":
            text = item.get("text", "")
            if len(text) < 15:
                return None
            for marker in [
                "SYSTEM SIGNALS", "ROLE DECISION", "EXECUTING ROLE",
                "SESSION STATUS", "PROPOSAL", "PRE-PUSH CHECKLIST",
                "SESSION COMPLETE", "Session Complete", "GENERATED TASKS",
            ]:
                if marker in text:
                    return f"  >>>   {marker}"
            return f"  MSG   {_truncate(text)}"

        if itype == "file_change":
            changes = item.get("changes", [])
            for c in changes:
                path = c.get("path", "")
                kind = c.get("kind", "")
                short = path.split("/")[-1] if "/" in path else path
                return f"  FILE  {kind} {short}"

    if etype == "turn.completed":
        usage = event.get("usage", {})
        out = usage.get("output_tokens", 0)
        return f"  ---   Turn complete ({out} output tokens)"

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
                # Non-JSON line (stderr, errors) — show to operator
                if len(line) > 10 and not line.startswith("{"):
                    print(f"  ERR   {_truncate(line)}", flush=True)
                continue

            # Try Claude format first, then Codex
            result = format_claude(event)
            if result is None:
                result = format_codex(event)
            if result is not None:
                print(result, flush=True)
        except Exception:
            # Never crash the pipeline — log and continue
            continue


if __name__ == "__main__":
    main()
