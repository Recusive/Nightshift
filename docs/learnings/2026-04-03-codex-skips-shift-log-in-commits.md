# Learning: Codex does not include shift log in fix commits
**Date**: 2026-04-03
**Session**: 0007
**Type**: gotcha

## What happened
Ran a 2-cycle test shift against Phractal with codex. Both cycles were rejected because codex committed the fix files but not the shift log update. The SKILL.md says "One commit per accepted fix. Each fix commit must include the shift log update." Codex does not follow this instruction reliably.

## The lesson
The shift-log-in-commit rule is one of the hardest instructions for agents to follow because it requires them to (1) update the shift log, (2) stage it alongside the fix files, and (3) commit both together. Most agents commit the fix first, then update the log separately. Either the prompt needs to be much more explicit about this sequence, or the verification should tolerate a separate shift-log commit within the same cycle.

## Evidence
- Phractal test shift: both cycles rejected with "Commit does not include the shift log update"
- State file: `failed_verifications: 2`, `halt_reason: "Failed verification threshold reached"`
- Agent DID update the shift log and DID make real fixes -- just committed them separately
