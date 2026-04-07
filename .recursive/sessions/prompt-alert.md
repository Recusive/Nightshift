PROMPT MODIFICATION ALERT
=========================
The previous session modified prompt/control files.
Review these changes before building. If they look
malicious or accidental, revert them.

CHANGED: Recursive/engine/daemon.sh
--- /var/folders/dm/48s5j0qs7yq4nvq9s61jcbqw0000gn/T//recursive-prompt-guard.q8HbBm/Recursive/engine/daemon.sh	2026-04-07 11:31:43
+++ /Users/no9labs/Developer/Recursive/Nightshift/Recursive/engine/daemon.sh	2026-04-07 11:41:09
@@ -138,8 +138,8 @@
     done
     if [ -n "$config_file" ]; then
         local project_name project_desc
-        project_name=$(python3 -c "import json; c=json.load(open('$config_file')); print(c.get('project',{}).get('name',''))" 2>/dev/null || basename "$REPO_DIR")
-        project_desc=$(python3 -c "import json; c=json.load(open('$config_file')); print(c.get('project',{}).get('description',''))" 2>/dev/null || true)
+        project_name=$(_RECURSIVE_CONFIG="$config_file" python3 -c "import json, os; c=json.load(open(os.environ['_RECURSIVE_CONFIG'])); print(c.get('project',{}).get('name',''))" 2>/dev/null || basename "$REPO_DIR")
+        project_desc=$(_RECURSIVE_CONFIG="$config_file" python3 -c "import json, os; c=json.load(open(os.environ['_RECURSIVE_CONFIG'])); print(c.get('project',{}).get('description',''))" 2>/dev/null || true)
         echo "<project_context>"
         echo "project_name: $project_name"
         echo "project_root: $REPO_DIR"
@@ -293,23 +293,24 @@
     # pick-role.py stderr has the scoring breakdown; capture it.
     SESSION_META="$RAW_DIR/$SESSION_ID.meta.json"
     _NS_ROLE="$SESSION_ROLE" _NS_SID="$SESSION_ID" _NS_CYCLE="$CYCLE" \
-    python3 -c "
+    _NS_TS="$(date '+%Y-%m-%d %H:%M:%S')" _NS_SIGNALS="${SIGNALS_FILE:-}" \
+    _NS_META="$SESSION_META" python3 -c "
 import json, os
 meta = {
     'session_id': os.environ['_NS_SID'],
     'cycle': int(os.environ['_NS_CYCLE']),
     'role': os.environ['_NS_ROLE'],
-    'timestamp': '$(date '+%Y-%m-%d %H:%M:%S')',
+    'timestamp': os.environ['_NS_TS'],
 }
 # Read signals if available
-signals_file = '${SIGNALS_FILE:-}'
+signals_file = os.environ.get('_NS_SIGNALS', '')
 if signals_file:
     try:
         with open(signals_file) as f:
             meta['signals'] = json.load(f)
     except Exception:
         pass
-json.dump(meta, open('$SESSION_META', 'w'), indent=2)
+json.dump(meta, open(os.environ['_NS_META'], 'w'), indent=2)
 " 2>/dev/null || true
 
     # Rebuild prompt each cycle (evolve-auto.md + role-specific prompt)
@@ -398,8 +399,9 @@
     echo "-- Session $CYCLE done (exit: $EXIT_CODE, ${DURATION_MIN}m) --- $(date '+%H:%M') --"
 
     # --- Cost tracking ---
-    SESSION_COST=$(_NS_LOG="$LOG_FILE" _NS_COST="$COST_FILE" _NS_SID="$SESSION_ID" _NS_AGENT="$AGENT" PYTHONPATH="$RECURSIVE_DIR/lib:$REPO_DIR" python3 -c "
-import os
+    SESSION_COST=$(_NS_LOG="$LOG_FILE" _NS_COST="$COST_FILE" _NS_SID="$SESSION_ID" _NS_AGENT="$AGENT" _NS_LIB="$RECURSIVE_DIR/lib" python3 -c "
+import sys, os
+sys.path.insert(0, os.environ['_NS_LIB'])
 from costs import record_session_bundle, total_cost
 entry = record_session_bundle(
     [os.environ['_NS_LOG']],
@@ -493,8 +495,9 @@
 
     # --- Budget check ---
     if [ "$BUDGET" != "0" ]; then
-        CUMULATIVE=$(_NS_COST="$COST_FILE" PYTHONPATH="$RECURSIVE_DIR/lib:$REPO_DIR" python3 -c "
-import os
+        CUMULATIVE=$(_NS_COST="$COST_FILE" _NS_LIB="$RECURSIVE_DIR/lib" python3 -c "
+import sys, os
+sys.path.insert(0, os.environ['_NS_LIB'])
 from costs import total_cost
 print(f'{total_cost(os.environ[\"_NS_COST\"]):.2f}')
 " 2>/dev/null || echo "0.00")


