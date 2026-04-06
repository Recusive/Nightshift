---
date: 2026-04-06
type: security
topic: Every agent-invoking script must be in PROMPT_GUARD_FILES
---

# PROMPT_GUARD_FILES must cover all agent-invoking scripts

Any script that directly invokes an agent OR controls daemon restart behavior
must be in `PROMPT_GUARD_FILES` in `scripts/lib-agent.sh`.

Gaps discovered in PR #158: `watchdog.sh` (restart rate-limiter + daemon.sh
caller), `daemon-strategist.sh`, `daemon-review.sh`, `daemon-overseer.sh`
(legacy single-role entry points that source lib-agent.sh) were all absent
from the guard list despite being live, callable scripts.

**Rule**: After adding any new script to `scripts/` that:
- Calls `run_agent`, `claude`, `codex`, or any model invocation
- Sources `lib-agent.sh`
- Controls how often `daemon.sh` runs

...immediately add it to `PROMPT_GUARD_FILES`. The `PROMPT_GUARD_DIRS` array
includes `"scripts"` which catches NEW files post-cycle, but it does NOT
protect existing files that were already on disk before the guard snapshot.

`PROMPT_GUARD_FILES` is the only protection for existing files.

**Checklist** when adding a new `scripts/*.sh`:
1. Does it invoke an agent? → Add to PROMPT_GUARD_FILES
2. Does it source lib-agent.sh? → Add to PROMPT_GUARD_FILES
3. Does it call daemon.sh or control the restart loop? → Add to PROMPT_GUARD_FILES
