# Learning: Plan agent invocation is simpler than cycle agent invocation
**Date**: 2026-04-04
**Session**: 0017
**Type**: pattern

The cycle agent (in `cycle.py:command_for_agent`) needs `schema_path` and `message_path` because cycles produce structured JSON via output schemas and message files. The plan agent only needs to produce text that contains JSON -- `parse_plan()` handles extraction via `extract_json()`.

This means plan agent commands are simpler: just the agent CLI, the prompt, and max turns. No schema flags, no message file paths. The same pattern will likely apply to other "prompt in, text out" agent invocations (e.g., if we add `nightshift profile --agent` or `nightshift summarize --agent`).

When adding new agent-invoking commands, check whether you need structured output (schema+message path) or just text parsing (simpler command). Most non-cycle operations only need text parsing.
