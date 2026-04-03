# Harden the Daemon — One-Time Task Prompt

Paste this into a Claude Code session to fix the daemon's safety gaps.

---

Read these first:
1. `docs/handoffs/LATEST.md`
2. `CLAUDE.md` (especially Code Structure rules)
3. `scripts/daemon.sh` + `docs/prompt/evolve-auto.md`

## What to fix in `scripts/daemon.sh`:

1. **Max-sessions flag**: `./scripts/daemon.sh claude 60 10` = stop after 10 sessions. Default: unlimited.
2. **Dirty state cleanup**: At the top of each cycle, before `git checkout main`, run `git reset --hard origin/main && git clean -fd` to guarantee a clean slate even if the previous session crashed.
3. **Circuit breaker**: Track consecutive failures. After 3 in a row, stop the daemon and log "Circuit breaker tripped" to the session log. Reset the counter on any successful session.
4. **Session index**: After each session, append a one-line summary to `docs/sessions/index.md`: timestamp, session ID, exit code, duration, one-line description (extracted from the log or "failed").

## What to fix in `docs/prompt/evolve.md`:

5. **Post-merge CI check**: After Step 8 (merge), add: "Wait for CI on main. Run `gh run list --branch main --limit 1` and check status. If it fails, immediately revert with `bash scripts/rollback.sh`."

## Follow the workflow:
- Branch, build, test, `make check`, `bash scripts/validate-docs.sh`, pre-push checklist, PR, sub-agent review, merge with `--merge --delete-branch --admin`.
