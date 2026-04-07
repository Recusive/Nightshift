# Learnings verification is process, not code

**Date**: 2026-04-05
**Type**: optimization
**Session**: #0033

## The learning

Enforcing that agents read learnings requires changes in three coordinated places: the status report template (where it's first produced), the handoff requirements (where it's persisted), and the pre-push checklist (where it's verified). Changing only one creates a gap -- the agent can claim to have read learnings without auditable evidence.

Process enforcement through prompt engineering requires closing all the loops: production point, persistence point, and verification point. Missing any one makes the enforcement toothless.
