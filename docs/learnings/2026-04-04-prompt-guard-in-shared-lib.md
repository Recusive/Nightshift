---
type: pattern
date: 2026-04-04
---

# Put daemon cross-cutting concerns in lib-agent.sh

When adding logic that all 4 daemon scripts need (daemon.sh, daemon-review.sh, daemon-overseer.sh, daemon-strategist.sh), put it as functions in `lib-agent.sh` rather than duplicating across scripts. All daemons already `source lib-agent.sh`.

The pattern: define functions in lib-agent.sh, then each daemon calls them with ~5-8 lines of integration code. This keeps the daemons lean and the shared logic testable in one place.

Example: prompt guard uses `save_prompt_snapshots()`, `check_prompt_integrity()`, `cleanup_prompt_snapshots()` in lib-agent.sh. Each daemon adds the same before/after pattern around `run_agent`.
