"""Cost tracking for daemon sessions -- parse token usage from logs and maintain a ledger."""

from __future__ import annotations

import json
import os
from pathlib import Path

from nightshift.constants import COST_LEDGER_FILENAME, MODEL_PRICING
from nightshift.types import CostLedger, SessionCost


def parse_session_tokens(log_path: str) -> SessionCost:
    """Parse a stream-json session log and sum token usage across all messages.

    Extracts usage data from Claude's ``message.usage`` fields. For unknown
    log formats the returned counts are all zero.
    """
    input_tokens = 0
    cache_creation_tokens = 0
    cache_read_tokens = 0
    output_tokens = 0
    model = ""

    path = Path(log_path)
    if not path.exists():
        return _empty_cost("", "", "")

    with path.open() as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                continue

            if event.get("type") != "assistant":
                continue

            msg = event.get("message")
            if not isinstance(msg, dict):
                continue

            # Capture model from the first assistant message that has one.
            if not model:
                msg_model = msg.get("model", "")
                if isinstance(msg_model, str) and msg_model:
                    model = msg_model

            usage = msg.get("usage")
            if not isinstance(usage, dict):
                continue

            input_tokens += _int(usage.get("input_tokens"))
            cache_creation_tokens += _int(usage.get("cache_creation_input_tokens"))
            cache_read_tokens += _int(usage.get("cache_read_input_tokens"))
            output_tokens += _int(usage.get("output_tokens"))

    return _empty_cost("", "", model, input_tokens, cache_creation_tokens, cache_read_tokens, output_tokens)


def calculate_cost(
    model: str,
    input_tokens: int,
    cache_creation_tokens: int,
    cache_read_tokens: int,
    output_tokens: int,
) -> float:
    """Calculate estimated USD cost for the given token counts.

    Uses :data:`MODEL_PRICING` for known models.  Returns ``0.0`` for
    unrecognised models (tokens are still tracked).
    """
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return 0.0

    per_m = 1_000_000.0
    cost = (
        input_tokens * pricing["input"] / per_m
        + cache_creation_tokens * pricing["cache_creation"] / per_m
        + cache_read_tokens * pricing["cache_read"] / per_m
        + output_tokens * pricing["output"] / per_m
    )
    return round(cost, 6)


def read_ledger(ledger_path: str) -> CostLedger:
    """Read the cost ledger from disk.  Returns an empty ledger if the file is missing."""
    path = Path(ledger_path)
    if not path.exists():
        return {"total_cost_usd": 0.0, "sessions": []}

    try:
        with path.open() as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, ValueError, OSError):
        return {"total_cost_usd": 0.0, "sessions": []}

    if not isinstance(data, dict):
        return {"total_cost_usd": 0.0, "sessions": []}

    return {
        "total_cost_usd": float(data.get("total_cost_usd", 0.0)),
        "sessions": list(data.get("sessions", [])),
    }


def write_ledger(ledger_path: str, ledger: CostLedger) -> None:
    """Write the cost ledger to disk, creating parent directories if needed."""
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        json.dump(ledger, fh, indent=2)
        fh.write("\n")


def record_session(
    log_path: str,
    ledger_path: str,
    session_id: str,
    agent: str,
) -> SessionCost:
    """Parse a session log, calculate cost, append to the ledger, and return the cost entry."""
    tokens = parse_session_tokens(log_path)
    cost_usd = calculate_cost(
        tokens["model"],
        tokens["input_tokens"],
        tokens["cache_creation_tokens"],
        tokens["cache_read_tokens"],
        tokens["output_tokens"],
    )

    entry: SessionCost = {
        "session_id": session_id,
        "agent": agent,
        "model": tokens["model"],
        "input_tokens": tokens["input_tokens"],
        "cache_creation_tokens": tokens["cache_creation_tokens"],
        "cache_read_tokens": tokens["cache_read_tokens"],
        "output_tokens": tokens["output_tokens"],
        "total_cost_usd": cost_usd,
    }

    ledger = read_ledger(ledger_path)
    ledger["sessions"].append(entry)
    ledger["total_cost_usd"] = round(ledger["total_cost_usd"] + cost_usd, 6)
    write_ledger(ledger_path, ledger)

    return entry


def total_cost(ledger_path: str) -> float:
    """Return the cumulative cost from the ledger file."""
    return read_ledger(ledger_path)["total_cost_usd"]


def format_session_cost(cost: SessionCost) -> str:
    """Format a session cost as a human-readable one-liner."""
    total_tokens = (
        cost["input_tokens"] + cost["cache_creation_tokens"] + cost["cache_read_tokens"] + cost["output_tokens"]
    )
    return (
        f"Tokens: {total_tokens:,} "
        f"(in={cost['input_tokens']:,} "
        f"cache_w={cost['cache_creation_tokens']:,} "
        f"cache_r={cost['cache_read_tokens']:,} "
        f"out={cost['output_tokens']:,}) "
        f"Cost: ${cost['total_cost_usd']:.4f}"
    )


def default_ledger_path(sessions_dir: str) -> str:
    """Return the default ledger path for a sessions directory."""
    return os.path.join(sessions_dir, COST_LEDGER_FILENAME)


# --- Helpers -----------------------------------------------------------------


def _int(value: object) -> int:
    """Safely coerce a value to int, returning 0 for non-numeric values."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _empty_cost(
    session_id: str,
    agent: str,
    model: str,
    input_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
    output_tokens: int = 0,
) -> SessionCost:
    """Build a SessionCost dict."""
    return {
        "session_id": session_id,
        "agent": agent,
        "model": model,
        "input_tokens": input_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "cache_read_tokens": cache_read_tokens,
        "output_tokens": output_tokens,
        "total_cost_usd": 0.0,
    }
