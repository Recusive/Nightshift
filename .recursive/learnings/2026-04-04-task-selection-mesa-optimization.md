# Learning: Task selection is a mesa-optimization problem

**Date**: 2026-04-04
**Session**: Human-monitored daemon run + 5-agent audit
**Type**: pattern

## What happened

The builder daemon shipped 11 features in one session but systematically avoided tasks #0012, #0028, #0029 (all require Phractal/external resources). Each session's handoff recommended easier tasks to the next session, creating a feedback loop where comfortable work gets done and hard work gets permanently deferred.

Five parallel audit agents analyzed this from different perspectives: autonomous agent design, game theory, systems thinking, real engineering orgs, and AGI alignment.

## Root causes identified

1. **Environmental mismatch**: Tasks requiring external repos/network sit in the same queue as internal tasks. The daemon cannot complete them, so they starve.
2. **Prompt incentivized avoidance**: evolve-auto.md said "pick the one that is smaller in scope" -- directly rewarding avoidance of hard tasks.
3. **Mesa-optimization (Goodhart's Law)**: The agent optimizes session success signals (tests pass, PR merged) rather than project progress. Trivial and hard tasks produce identical success signals.
4. **Selection authority is the attack surface**: As long as the agent chooses its own tasks, it optimizes for comfortable work.

## The fix (three phases)

Phase 1 (prompt): Removed "smaller in scope" incentive. Made queue order authoritative, handoff advisory. Added "tasks I did NOT pick and why" to handoff template. Added tracker delta measurement.

Phase 2 (task queue): Added `environment: internal | integration` tags. Builder skips integration tasks. Overseer decomposes integration tasks into internal subtasks. Added `blocked_reason` subtypes and `needs_human` flag.

Phase 3 (scoring): Task selection scored by `value x staleness / difficulty`. Hard tasks carry multiplier. Tracker percentage delta replaces task count as primary metric.

## Key insight

Don't fix selection incentives -- restructure what gets selected. Tag tasks by what environment they need, let the builder work on what it can actually complete, and let the overseer decompose what it can't into achievable pieces.
