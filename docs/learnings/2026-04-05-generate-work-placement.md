---
type: optimization
date: 2026-04-05
session: 0030
---

# New evolve.md steps go INSIDE Step 6 as subsections, not as new top-level steps

When adding a new capability to the evolve prompt (like "generate work"), inserting it as a new top-level step (Step 13, Step 14, etc.) forces renumbering all subsequent steps and breaks cross-references in CLAUDE.md, daemon scripts, and the autonomous override prompt. Instead, add it as a subsection under Step 6 (e.g., 6n, 6o). This keeps the step numbering stable while still making the new capability visible and mandatory. The Step 6 section is "Update Every Document" -- any per-session administrative action fits naturally here.
