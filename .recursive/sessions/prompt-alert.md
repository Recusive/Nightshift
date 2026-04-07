PROMPT MODIFICATION ALERT
=========================
The previous session modified prompt/control files.
Review these changes before building. If they look
malicious or accidental, revert them.

CHANGED: Recursive/prompts/autonomous.md
--- /var/folders/dm/48s5j0qs7yq4nvq9s61jcbqw0000gn/T//recursive-prompt-guard.KeMApg/Recursive/prompts/autonomous.md	2026-04-07 10:56:10
+++ /Users/no9labs/Developer/Recursive/Nightshift/Recursive/prompts/autonomous.md	2026-04-07 11:00:47
@@ -128,6 +128,6 @@
 - A monitor agent or human may be reading your log in real-time
 - The daemon will hard-reset to origin/main before your next session starts
 - If you leave an open PR, the next session will detect it and finish it
-- The engine auto-picks BUILD/REVIEW/OVERSEE/STRATEGIZE/ACHIEVE each cycle
+- The engine auto-picks from 8 operators each cycle: BUILD/REVIEW/OVERSEE/STRATEGIZE/ACHIEVE/SECURITY-CHECK (target) + EVOLVE/AUDIT (framework)
 
 ---

CHANGED: Recursive/prompts/checkpoints.md
--- /var/folders/dm/48s5j0qs7yq4nvq9s61jcbqw0000gn/T//recursive-prompt-guard.KeMApg/Recursive/prompts/checkpoints.md	2026-04-07 10:56:10
+++ /Users/no9labs/Developer/Recursive/Nightshift/Recursive/prompts/checkpoints.md	2026-04-07 11:00:47
@@ -1,8 +1,7 @@
-# Process Verification Checkpoints
+# Process Verification Checkpoint
 
-These checkpoints counteract RLHF biases by making your reasoning visible,
-verifiable, and accountable. Each checkpoint produces a structured block in
-your session output that can be audited by future sessions.
+This checkpoint counteracts action bias by making your reasoning visible
+and verifiable. It applies to ALL operators.
 
 ## Checkpoint 1: Signal Analysis (before deciding anything)
 
@@ -22,61 +21,11 @@
 recent_roles:        [list from signals]
 recent_security:     N of last 5 builds were security-driven
 tracker_movement:    [yes/no — did overall % change recently?]
+friction_entries:    N
 ```
 
 Numbers must be verifiable against actual files. If the block is missing or
 numbers don't match reality, the session is flagged.
 
-## Checkpoint 2: Forced Tradeoff Analysis (before starting work)
-
-State at least 2 options with the cost of NOT doing each. This prevents
-easy-task selection and rationalization — you can't just say "I'll do X
-because it's important." You must say "I'm NOT doing Y, and the cost is Z."
-
-```
-TRADEOFF ANALYSIS
-=================
-Option A: [task/action]
-  Impact: [what improves]
-  Cost of skipping: [what stays broken]
-
-Option B: [task/action]
-  Impact: [what improves]
-  Cost of skipping: [what stays broken]
-
-Decision: Option [X]. [Evidence-based reason, not just "it's important"]
-```
-
-## Checkpoint 3: Pre-Commitment Metric (before building)
-
-Declare a specific, measurable success criterion BEFORE starting work.
-This prevents completion bias — declaring success regardless of quality.
-The next session will check whether your metric actually moved.
-
-```
-PRE-COMMITMENT
-==============
-Metric: [specific measurable outcome]
-Verification: [how to check it]
-Fallback: [what to do if it doesn't work]
-```
-
-## Checkpoint 4: Commitment Check (in the handoff)
-
-The handoff includes what you committed to. The NEXT session reads it and
-verifies: did the metric actually move? This creates a cross-session
-feedback loop — accountability across sessions.
-
-In your handoff:
-```
-## Commitment Check
-Pre-commitment: [what you promised]
-Actual result: [to be verified by next session]
-```
-
-In the next session's Step 0:
-- Read the previous handoff's Commitment Check
-- If MET: note "Previous commitment: MET" in status report
-- If MISSED: note "Previous commitment: MISSED — [reason]"
-- If same commitment missed 3+ times: create investigation task
-- If no Commitment Check exists (first session or non-BUILD): skip, note "N/A"
+NOTE: Checkpoints 2-4 (Forced Tradeoff, Pre-Commitment, Commitment Check)
+apply only to the BUILD operator and are embedded in its SKILL.md.

CHANGED: Recursive/engine/lib-agent.sh
--- /var/folders/dm/48s5j0qs7yq4nvq9s61jcbqw0000gn/T//recursive-prompt-guard.KeMApg/Recursive/engine/lib-agent.sh	2026-04-07 10:56:10
+++ /Users/no9labs/Developer/Recursive/Nightshift/Recursive/engine/lib-agent.sh	2026-04-07 11:00:47
@@ -35,6 +35,8 @@
     "Recursive/operators/strategize/SKILL.md"
     "Recursive/operators/achieve/SKILL.md"
     "Recursive/operators/security-check/SKILL.md"
+    "Recursive/operators/evolve/SKILL.md"
+    "Recursive/operators/audit/SKILL.md"
     # --- Project-level control files ---
     "AGENTS.md"
     "CLAUDE.md"


