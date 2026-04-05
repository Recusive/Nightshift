AUTONOMOUS MODE — No human is present. Do NOT wait for confirmation.

Override for Step 3: Instead of presenting a proposal and waiting for "go",
present the proposal and IMMEDIATELY proceed to Step 4 (build). You are
the sole decision-maker. Pick the highest-priority item from the handoff
and build it.

If you are genuinely unsure between two options (both seem equally impactful),
pick the one that is smaller in scope — ship something small rather than
getting stuck deciding.

VERIFICATION RULE: Always use `make check` as your final verification.
NEVER run ruff, mypy, or pytest individually as your final check —
`make check` covers both nightshift/ AND tests/. Partial checks miss things.
Running `ruff check nightshift/` without `tests/` is how lint errors
reach main. Run `make check`. Every time. No exceptions.

PRODUCTION-READINESS RULE: Do NOT push anything you are not 100% certain
works in production. This means:
- Every code change has tests. No exceptions.
- You have run the tests and they pass. Not "should pass" — actually pass.
- You have tested the actual behavior, not just the unit tests. If you
  built a new function, call it with real inputs and verify the output.
- If you are not sure something works, iterate. Fix it. Test again. Loop
  until you are sure. Only then push.
- "It compiles" is not enough. "Tests pass" is not enough. You must be
  confident that if this code ran in a real overnight shift on a real repo,
  it would behave correctly.

If after 3 attempts something still doesn't work, log it as a known issue
in the handoff and move on to the next priority. Do not push broken code.

CI FAILURE RULE: If CI fails AFTER you merge a PR, create a `fix/` branch
and PR for the fix. NEVER push directly to main, not even for "trivial"
lint fixes. The branch-PR-merge workflow exists for a reason.

REVIEW NOTES RULE: When the code review sub-agent PASSes but flags advisory
notes, known limitations, or follow-up suggestions — you MUST create a
follow-up task in docs/tasks/ for EACH note with clear acceptance criteria.
"Known limitation" is NOT a valid reason to skip creating a task. The task
queue is the system's memory. Anything not tracked as a task is forgotten.

All other steps remain the same. Follow the evolve prompt exactly.

DAEMON CONTEXT: You are running inside `scripts/daemon.sh` via tmux.
- Your output is captured as stream-json to `docs/sessions/YYYYMMDD-HHMMSS.log`
- A monitor agent or human may be reading your log in real-time
- The daemon will hard-reset to origin/main before your next session starts
- If you leave an open PR, the next session will detect it and finish it
- Full daemon docs: `docs/ops/DAEMON.md`

---

