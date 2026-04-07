"""Session cost tracking for the Recursive daemon.

Parses JSONL agent logs for token usage, computes costs, and maintains
a JSON ledger. No dependency on target project code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Model pricing (input $/1M tokens, output $/1M tokens)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Claude
    "opus": (15.0, 75.0),
    "claude-opus-4-6": (15.0, 75.0),
    "claude-opus-4-5-20250414": (15.0, 75.0),
    "sonnet": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5-20250514": (3.0, 15.0),
    "haiku": (1.0, 5.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    # OpenAI / Codex
    "o3": (2.0, 8.0),
    "o4-mini": (1.10, 4.40),
    "gpt-5.4": (2.0, 8.0),
    "codex-mini": (1.50, 6.0),
}

# Agents and their default models
AGENT_DEFAULT_MODELS: dict[str, str] = {
    "claude": "sonnet",
    "codex": "o3",
}


def _extract_tokens_claude(log_path: Path) -> tuple[int, int]:
    """Extract input/output tokens from a Claude JSONL log."""
    input_tok = output_tok = 0
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            usage = event.get("usage") or event.get("message", {}).get("usage")
            if isinstance(usage, dict):
                input_tok += usage.get("input_tokens", 0)
                output_tok += usage.get("output_tokens", 0)
    except OSError:
        pass
    return input_tok, output_tok


def _extract_tokens_codex(log_path: Path) -> tuple[int, int]:
    """Extract input/output tokens from a Codex JSONL log."""
    input_tok = output_tok = 0
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            usage = event.get("usage")
            if isinstance(usage, dict):
                input_tok += usage.get("input_tokens", 0) + usage.get(
                    "prompt_tokens", 0
                )
                output_tok += usage.get("output_tokens", 0) + usage.get(
                    "completion_tokens", 0
                )
    except OSError:
        pass
    return input_tok, output_tok


def parse_session_tokens(log_path: str | Path) -> tuple[int, int]:
    """Parse a session log and return (input_tokens, output_tokens)."""
    p = Path(log_path)
    # Try Claude format first, then Codex
    inp, out = _extract_tokens_claude(p)
    if inp == 0 and out == 0:
        inp, out = _extract_tokens_codex(p)
    return inp, out


def calculate_cost(
    input_tokens: int, output_tokens: int, model: str = "sonnet"
) -> float:
    """Calculate cost in USD for token counts and model."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING.get("sonnet", (3.0, 15.0)))
    inp_rate, out_rate = pricing
    return (input_tokens * inp_rate + output_tokens * out_rate) / 1_000_000


def format_session_cost(
    log_path: str | Path, model: str = "sonnet"
) -> str:
    """Parse a log and return formatted cost string like '$1.23'."""
    inp, out = parse_session_tokens(log_path)
    cost = calculate_cost(inp, out, model)
    return f"${cost:.2f}"


def _read_ledger(path: Path) -> list[dict[str, Any]]:
    """Read the cost ledger JSON file."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_ledger(path: Path, entries: list[dict[str, Any]]) -> None:
    """Write the cost ledger JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def record_session_bundle(
    log_paths: list[str],
    cost_file: str,
    session_id: str = "",
    agent: str = "claude",
    pentest_agent: str = "",
) -> dict[str, Any]:
    """Record costs for multiple log files (pentest + main session).

    Returns the combined entry dict.
    """
    model = AGENT_DEFAULT_MODELS.get(agent, "sonnet")
    pentest_model = AGENT_DEFAULT_MODELS.get(pentest_agent or agent, model)

    total_inp = total_out = 0
    for i, lp in enumerate(log_paths):
        p = Path(lp)
        if p.exists():
            inp, out = parse_session_tokens(p)
            total_inp += inp
            total_out += out

    # Use pentest model for first log, main model for rest (approximation)
    cost = calculate_cost(total_inp, total_out, model)

    entry: dict[str, Any] = {
        "session": session_id,
        "agent": agent,
        "model": model,
        "input_tokens": total_inp,
        "output_tokens": total_out,
        "cost_usd": round(cost, 4),
    }

    ledger = _read_ledger(Path(cost_file))
    ledger.append(entry)
    _write_ledger(Path(cost_file), ledger)

    return entry


def total_cost(cost_file: str) -> float:
    """Sum all costs from the ledger."""
    entries = _read_ledger(Path(cost_file))
    return sum(e.get("cost_usd", 0.0) for e in entries)
