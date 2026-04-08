# Nightshift Vision

You are reading this because you are an AI agent about to work on the Nightshift codebase. This document tells you what Nightshift is, where it's going, and how your work fits into the bigger picture. Read it completely before doing anything.

## What Nightshift Is Right Now

Nightshift is an autonomous overnight codebase improvement agent. A human runs it before bed on any repo. It creates an isolated git worktree, spawns headless agent cycles (Codex or Claude), and each cycle finds small production-readiness issues — security holes, missing error handling, test gaps, accessibility problems — fixes them, and commits. A Python orchestrator (`nightshift/`) enforces hard limits: max files per fix, blocked paths, category balance, clean worktree after every cycle. If a cycle violates policy, it gets reverted. The human wakes up to a shift log and a clean branch they can review and merge.

This is Loop 1. It works. It has been tested end-to-end. It found real bugs in its own codebase on its first run.

## Where Nightshift Is Going

Nightshift evolves into a **fully autonomous engineering system** with two operational modes.

---

## Loop 1 — The Hardening Loop

### What it does today

You point it at a repo. It runs for hours. It finds small issues and fixes them. Think of it as a senior engineer doing a code review and fixing everything they find, one commit at a time, all night long.

### Example of what a good hardening shift looks like

Imagine you run Nightshift on a Next.js SaaS app:

- **Cycle 1**: Reads the codebase. Finds that the API route `/api/users` doesn't validate the `id` parameter — a SQL injection vector. Fixes it by adding Zod validation. Commits: `nightshift: [security] add input validation to /api/users`. Updates shift log.
- **Cycle 2**: Finds that the `ErrorBoundary` component catches errors but doesn't report them anywhere — users see a blank screen and no one knows. Adds a `reportError()` call that sends to the existing Sentry setup it found in `lib/monitoring.ts`. Commits. Updates shift log.
- **Cycle 3**: Notices that `useAuth()` hook has no test file at all. The hook handles login, logout, token refresh. Writes a test suite covering the happy path and three edge cases (expired token, network failure, concurrent refresh). Commits. Updates shift log.
- **Cycle 4**: Finds 14 instances of `<button>` without `type="button"` across the component library. Fixes 3 representative ones and logs the pattern for the day team to sweep. This is low-impact, so the runner's low-impact cap prevents it from spending the whole night on this.
- **Final cycle**: Rewrites the Summary section, adds Recommendations ("the auth module has zero test coverage — prioritize this"), makes sure commit hashes are correct, final commit.

The human wakes up, reads `docs/Nightshift/2026-04-03.md`, sees 4 fixes and 2 logged issues, reviews the branch, merges.

### What it needs to get better at

These are known weaknesses. If you are working on Loop 1, these are the problems to solve:

1. **Category tunnel vision**: The agent tends to find one category (usually a11y or code quality) and hammer it all night. The runner has a category dominance check (>50% rejection) and a low-impact cap, but the agent should be smarter about exploring different areas proactively.

2. **Cycle-to-cycle amnesia**: Each cycle reads the shift log to see what was done. But it still sometimes rediscovers the same issue. The state file tracks categories and file paths, but the agent doesn't always use that information effectively in its exploration strategy.

3. **Test writing avoidance**: Despite tests being priority #3 in the SKILL.md, agents rarely write tests in practice. They prefer quick one-file fixes over the harder work of understanding a module well enough to test it. This needs structural incentives, not just prompt nudging.

4. **Backend blindness**: In full-stack repos, the agent gravitates toward React components because they're self-contained and easy to reason about. Backend code (API routes, database queries, middleware) gets underexplored. The path bias detection helps but doesn't fully solve this.

5. **Shallow fixes**: Some fixes are technically correct but don't matter. Adding `type="button"` to a button in an admin panel that 3 people use is not the same priority as fixing an unvalidated API endpoint. The agent needs better judgment about impact, not just category.

6. **No diff scoring**: Currently, if a cycle produces commits and passes verification, it's accepted. There's no evaluation of whether the changes are actually valuable. A post-cycle diff scorer that rates the quality/impact of changes before accepting would prevent low-value churn.

---

## Loop 2 — The Feature Builder Loop

### What it does (not built yet)

You give it a feature request in plain English. It builds the entire feature autonomously — plan, code, tests, integration — and only comes back to you when it's production-ready. Not an MVP. Not a v1. The actual finished feature, tested end-to-end, ready to merge and deploy.

### Example of what a feature build looks like

You say: "Build me an auth system with email/password login, Google OAuth, session management, and role-based access control."

Here's what the Feature Builder does:

**Phase 1 — Understanding (5-10 minutes)**
- Reads the entire target repo: stack, conventions, existing auth (if any), database schema, API patterns, frontend routing
- Reads CLAUDE.md / AGENTS.md for repo-specific rules
- Identifies what already exists that it can build on (e.g., "there's already a `prisma/schema.prisma` with a User model but no auth fields")
- Identifies constraints ("this repo uses Next.js App Router, not Pages Router — auth middleware goes in `middleware.ts`, not `_app.tsx`")

**Phase 2 — Planning (10-15 minutes)**
- Creates a comprehensive plan document with:
  - Architecture decisions (where auth state lives, session strategy, token format)
  - Task breakdown with dependencies (what can be parallelized, what's sequential)
  - File-by-file changes (new files, modified files, with expected content summaries)
  - Test plan (unit tests, integration tests, E2E tests)
  - Rollback strategy (what to do if something doesn't work)
- The plan is written to a file so subsequent cycles can read it

**Phase 3 — Building (the bulk of the time)**
- The orchestrator decomposes the plan into independent work streams
- Sub-agents are spawned for parallel work:
  - **Sub-agent A**: Database schema changes — adds auth fields to User, creates Session and Role tables, runs migration
  - **Sub-agent B**: Backend auth logic — signup, login, logout, token refresh, password hashing, OAuth flow
  - **Sub-agent C**: Frontend auth UI — login page, signup page, forgot password, OAuth buttons, protected route wrapper
  - **Sub-agent D**: Middleware and RBAC — session validation middleware, role checking, route protection
- Each sub-agent:
  - Writes its code following repo conventions
  - Writes tests for its piece
  - Runs those tests
  - Reports back: "done, all tests pass" or "blocked on X"

**Phase 4 — Integration (critical)**
- The orchestrator merges all sub-agent work
- Runs the full test suite (not just individual pieces)
- Runs E2E tests: "can a user sign up, log in, access a protected page, get rejected from an admin page?"
- If integration tests fail, it diagnoses the issue, fixes it, and retests
- This loops until everything passes

**Phase 5 — Verification and Handoff**
- All tests pass
- The orchestrator reviews the full diff one more time for:
  - Security: no hardcoded secrets, no exposed tokens, proper CSRF protection
  - Consistency: naming conventions match the repo, no orphaned imports
  - Completeness: every route is protected that should be, every error state has a UI
- Writes a feature summary document: what was built, how it works, how to test it manually
- Creates a PR or branch ready for human review
- **Only now** does it surface to the user: "Auth system is ready. Here's the branch, here's the summary, here's how to test it."

### What makes this hard

These are the real engineering challenges. If you are designing Loop 2, you need to solve these:

1. **Sub-agent coordination**: Parallel agents will produce conflicting changes. Agent A adds a `userId` column, Agent B adds a `user_id` column. The orchestrator needs a merge/conflict resolution strategy that goes beyond `git merge`.

2. **Shared state during build**: Sub-agents need to agree on interfaces before they build. Agent B needs to know the database schema Agent A is creating. This requires either a shared specification document or a sequential dependency chain.

3. **E2E testing is hard**: Running actual E2E tests (Playwright, Cypress) requires a running application. The orchestrator needs to start the dev server, wait for it, run tests, and tear down. This is infrastructure the hardening loop doesn't need.

4. **"Production-ready" is subjective**: The system needs a concrete definition of done. Suggested criteria:
   - All unit tests pass
   - All integration tests pass
   - All E2E tests pass
   - No TypeScript/linting errors
   - No security vulnerabilities (secret exposure, injection, XSS)
   - No accessibility violations in new UI
   - Error states handled (loading, error, empty, offline)
   - Responsive if it's frontend
   - Database migrations are reversible

5. **Knowing when to ask**: Most features have ambiguous requirements. "Build me an auth system" — what kind of sessions? JWTs or server-side? How long do they last? Is there "remember me"? The system needs to either make sensible defaults and document them, or ask the human before building. The bar: only ask if the decision would be expensive to change later.

6. **Cost control**: Spawning many sub-agents running for hours gets expensive. The orchestrator needs budget awareness — if it's spent 4 hours and only completed 30% of the plan, something is wrong.

---

## The Meta-Prompt

### What it is

A single prompt that you (an AI agent) receive at the start of a session in this repo. It tells you:

1. Read the vision docs (you're reading one now)
2. Read the current state of the codebase (what's built, what's not)
3. Read any feedback from previous runs (in `.recursive/operators/feedback/`)
4. Figure out the highest-impact next feature to build toward the vision
5. Propose it to the human, get confirmation
6. Build it, test it, push it

### How the self-improving loop works

```
Session 1: Human pastes prompt → Agent reads vision + code → "I think we should build
           the diff scorer for Loop 1" → Human: "go" → Agent builds it, tests it, pushes

Session 2: Human pastes same prompt → Agent reads vision + code → sees diff scorer exists
           → "Next highest impact: cycle-to-cycle state passing" → builds, tests, pushes

Session 3: Human pastes same prompt → Agent reads vision + code → "I think we should
           start scaffolding Loop 2's orchestrator" → builds the skeleton, tests, pushes

Session 10: Human pastes same prompt → Loop 2 is functional → Agent focuses on
            making it smarter, handling edge cases, improving test coverage

Session 50: Both loops are production-grade. Agent suggests polish, documentation,
            performance optimization, multi-repo support.
```

Each session builds on the last. The prompt doesn't change — the codebase does, and the agent adapts.

### What makes this work

- **Vision docs are the north star**: The agent always knows where it's going
- **Code is the source of truth**: The agent reads what exists, not what was planned
- **Feedback loop is explicit**: After testing, the human writes what worked and what didn't into `.recursive/operators/feedback/`. The agent reads this next session.
- **Priority is emergent**: The agent picks what to build based on impact toward the vision, not a hardcoded roadmap. If the human says "the diff scorer was useless, rip it out" — the agent adjusts.

---

## Architecture: How Both Loops Share Infrastructure

Both loops use the same core infrastructure. This is critical — we are NOT building two separate systems.

```
Shared Infrastructure:
├── nightshift/shell.py          — subprocess execution (both loops shell out to agents)
├── nightshift/config.py         — repo detection, verify commands (both loops need this)
├── nightshift/eval_targets.py   — repo-specific evaluation defaults for known real-repo targets
├── nightshift/state.py          — state tracking (both loops persist progress to disk)
├── nightshift/worktree.py       — git worktree isolation (both loops work in worktrees)
├── nightshift/cycle.py          — verification, blocked paths (both loops enforce policy)
├── nightshift.schema.json       — structured output (both loops need machine-readable results)

Loop 1 Specific:
├── nightshift/cli.py            — the current run/test/summarize commands
├── nightshift/SKILL.md          — the hardening prompt
├── cycle prompt (in cycle.py)   — per-cycle instructions for the hardening agent

Loop 2 Specific (to be built):
├── nightshift/planner.py        — reads repo, creates feature plan
├── nightshift/decomposer.py     — breaks plan into parallel sub-agent tasks
├── nightshift/subagent.py       — spawns and manages sub-agents
├── nightshift/integrator.py     — merges sub-agent work, runs E2E tests
├── nightshift/feature_cli.py    — the `python3 -m nightshift build "auth system"` command
├── feature.schema.json          — structured output for feature build cycles
```

### What this means for you

If you are building toward Loop 2, you should:
- Reuse everything in the shared infrastructure
- Extend `nightshift/cli.py` with new subcommands, don't create a separate entry point
- Follow the same patterns: worktree isolation, machine-readable state, runner-enforced limits
- The difference is the PROMPT (what the agent is told to do) and the ORCHESTRATION (how sub-agents coordinate), not the infrastructure

---

## Non-Goals

Things Nightshift will NOT do:

- **Deploy anything**: Nightshift creates branches and PRs. Deployment is the human's job.
- **Modify CI/CD**: Build configs, GitHub Actions, deployment scripts are always blocked.
- **Make architecture decisions**: Database schema changes, routing rewrites, state management migrations — these need human sign-off.
- **Touch credentials**: Never reads, writes, or modifies `.env`, secrets, API keys.
- **Force push**: All work is on isolated branches. Never force pushes. Never touches main directly.

---

## Success Criteria

How we know Nightshift has achieved the vision:

**Loop 1 is done when:**
- You can run it on any repo (JS, Python, Rust, Go) and wake up to a useful shift log
- At least 70% of fixes are merged without changes
- It finds issues a human reviewer would also flag
- It doesn't waste time on trivial fixes when high-impact issues exist

**Loop 2 is done when:**
- You can say "build me a feature" and get back a working, tested, production-ready implementation
- Sub-agents successfully parallelize without producing conflicts
- E2E tests actually run and catch real integration bugs
- The human review is "looks good, merge" more than 50% of the time

**The meta-prompt is done when:**
- Each session produces a meaningful improvement to Nightshift itself
- The agent consistently picks the right next thing to build
- The human's only job is: paste prompt, confirm feature, test result, write feedback
