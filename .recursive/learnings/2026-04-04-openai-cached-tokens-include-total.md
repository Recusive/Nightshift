# Learning: OpenAI input_tokens includes cached; Claude separates them

**Date**: 2026-04-04
**Session**: 0026
**Type**: gotcha

## What happened
Adding Codex cost tracking required understanding a subtle difference in token reporting between Claude and OpenAI:

- **Claude** reports `input_tokens` (non-cached), `cache_creation_input_tokens`, and `cache_read_input_tokens` as separate, non-overlapping counts.
- **OpenAI** reports `input_tokens` (total, including cached) and `cached_input_tokens` (subset). Non-cached = `input_tokens - cached_input_tokens`.

If you naively map OpenAI's `input_tokens` to Claude's `input_tokens`, you double-count cached tokens and overestimate cost.

## The fix
Subtract `cached_input_tokens` from `input_tokens` when parsing Codex logs, so the stored `input_tokens` always means "non-cached, charged at full rate" regardless of provider. Guard with `max(0, ...)` for malformed data.
