---
type: pattern
date: 2026-04-05
session: multi-agent-review-panel
---

# Agent scope separation mirrors module separation

When splitting one review agent into five specialists, the same principle that governs Python module design applies: each agent gets one concern, with no overlap. The code-reviewer's scope shrank from 9 check categories to 4; the removed checks went to dedicated agents (safety, docs, architecture, meta).

Key insight: the original monolithic code-reviewer had a "docs-only fast path" that skipped 5 of 9 checks. That was a code smell -- it meant the agent was doing too many different things. After the split, each specialist naturally handles its own "not in scope" case (e.g., safety-reviewer passes immediately on docs-only PRs) without needing a special fast path in the main reviewer.

Applies to: any future agent definition work. If an agent needs a "skip these checks when X" path, it probably needs to be split.
