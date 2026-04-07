---
type: gotcha
date: 2026-04-06
session: fix/codex-extractor-0169
---

# Codex stream-json uses item.completed, not type:result

## Problem

Any inline Python that parses stream-json logs with `if event.get("type") == "result"` silently
produces empty output when the log was written by Codex. Codex emits:

```json
{"type": "item.completed", "item": {"type": "agent_message", "text": "..."}}
```

Claude emits:

```json
{"type": "result", "result": "..."}
```

This caused three extractors to silently fail for the entire Codex daemon:
- `extract_result_summary` (pentest report injected as empty)
- FEATURE extractor (always "-" in session index)
- PR_URL extractor (always "-" in session index)

The session index looked complete, but all Codex sessions had no pentest intelligence and
monitoring was blind to what was built.

## Fix pattern

Accumulate the last `agent_message` from `item.completed` events as a fallback. Prefer the
Claude `result` payload if present:

```python
result_text = ""
codex_last = ""
for event in events:
    if event.get("type") == "result":
        payload = event.get("result", "")
        if isinstance(payload, str) and payload.strip():
            result_text = payload.strip()
    elif event.get("type") == "item.completed":
        item = event.get("item", {})
        if item.get("type") == "agent_message":
            text = item.get("text", "")
            if isinstance(text, str) and text.strip():
                codex_last = text.strip()
text = result_text or codex_last
```

## Key rule

Whenever you write a stream-json parser, handle both `type:result` (Claude) and
`item.completed/agent_message` (Codex). Check `scripts/format-stream.py` for the full
Codex event schema before writing a new parser.
