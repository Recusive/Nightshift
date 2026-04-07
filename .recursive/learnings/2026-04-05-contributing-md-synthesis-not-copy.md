---
type: optimization
date: 2026-04-05
session: 0034
---

# CONTRIBUTING.md must synthesize, not copy

When writing a contributor guide for a repo with existing CLAUDE.md, the temptation is to copy-paste conventions. This produces a bloated document that duplicates maintenance burden and drifts out of sync.

Instead: read CLAUDE.md, the review agent config, CI workflows, and task guide. Identify what an EXTERNAL agent needs (quality gates, PR format, what not to touch) vs what the INTERNAL agent already has in its prompt context. Write only the external view. Reference CLAUDE.md for details.

Key insight: the resident daemon's review agent (.claude/agents/code-reviewer.md) defines the actual quality gates. The CONTRIBUTING.md should mirror those gates as a checklist, not redefine them. If the review agent config changes, CONTRIBUTING.md just says "the review daemon checks these" without duplicating the full list.
