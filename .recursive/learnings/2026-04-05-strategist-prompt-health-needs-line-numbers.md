# Learning: Strategist prompt-health reviews need line-numbered prompt reads
**Date**: 2026-04-05
**Session**: 0047
**Type**: pattern

## What happened
Task `#0050` needed the strategist to recommend prompt edits with evidence. The report only became actionable once the prompt explicitly told the strategist to read the control files with `nl -ba` and cite prompt file lines alongside session evidence.

## The lesson
If an agent is auditing prompt quality, require line-numbered reads of the prompt files in the prompt itself. Otherwise the output drifts into vague commentary instead of concrete add/remove/reword edits that can become tasks.

## Evidence
- `docs/prompt/strategist.md`
- `docs/strategy/2026-04-05.md`
