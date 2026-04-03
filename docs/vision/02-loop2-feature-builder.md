# Loop 2 — Feature Builder Loop Deep Dive

## What This Is

Loop 2 is a system where a human says "build me X" and gets back a production-ready implementation. The human doesn't write code, doesn't write tests, doesn't manage tasks. They describe what they want, confirm the plan, and wait for the result.

This does not exist yet. This document describes what needs to be built.

## How It Works — Step by Step

### Step 0: The Human Says What They Want

Input: a natural language feature request.

```
"Build me an auth system with email/password, Google OAuth, session management, 
and role-based access control."
```

Or simpler:

```
"Add a dark mode toggle to the settings page."
```

Or complex:

```
"Build a real-time collaborative editor using CRDTs. Multiple users should be 
able to edit the same document simultaneously with conflict resolution. Include 
presence indicators showing who's editing where."
```

The system handles all of these. The scope determines how many sub-agents get spawned and how long it takes.

### Step 1: Repo Understanding

Before planning anything, the system reads the target repo deeply:

- **Stack detection**: What framework? What language? What database? What ORM? What test runner?
- **Convention extraction**: How are files organized? How are components structured? What naming patterns? Import conventions? 
- **Existing infrastructure**: What already exists that's related? Is there a User model? An existing auth setup? Middleware patterns?
- **Instruction files**: CLAUDE.md, AGENTS.md, .cursorrules, whatever the repo uses for AI guidance
- **Test patterns**: How do existing tests work? Jest? Vitest? Pytest? What do test files look like?

This produces a **Repo Profile** document that all sub-agents receive.

### Step 2: Planning

The planner reads the feature request + repo profile and produces:

**Architecture Document:**
- Technology choices (with reasoning based on what the repo already uses)
- Data model changes (new tables, modified schemas)
- API endpoints (routes, methods, payloads, responses)
- Frontend components (new pages, modified components, state management)
- Integration points (where this feature touches existing code)

**Task Breakdown:**
- Numbered tasks with explicit dependencies
- Each task tagged: `parallel` (can run simultaneously) or `sequential` (needs prior task done)
- Each task has acceptance criteria: what tests must pass for it to be "done"
- Estimated file count per task (for budgeting)

**Test Plan:**
- Unit tests for each module
- Integration tests for API endpoints
- E2E tests for user flows
- Edge cases: what happens on network failure? Invalid input? Concurrent access? Session expiry?

**Example task breakdown for the auth feature:**

```
Task 1 [parallel]: Database schema
  - Add auth fields to User model (email, passwordHash, role)
  - Create Session model
  - Create OAuthAccount model  
  - Generate and run migration
  - Acceptance: migration runs clean, rollback works
  
Task 2 [parallel]: Auth utilities
  - Password hashing (bcrypt)
  - JWT or session token generation
  - Token validation middleware
  - Acceptance: unit tests for hash, generate, validate

Task 3 [depends: 1, 2]: API routes
  - POST /api/auth/signup
  - POST /api/auth/login
  - POST /api/auth/logout
  - POST /api/auth/refresh
  - GET /api/auth/me
  - Acceptance: integration tests for all routes, error cases

Task 4 [depends: 1]: OAuth integration
  - Google OAuth callback handler
  - Account linking (OAuth → User)
  - Acceptance: integration test with mocked OAuth provider

Task 5 [depends: 2]: RBAC middleware
  - Role checking middleware
  - Route protection configuration
  - Acceptance: unit tests for role checks, integration test for protected routes

Task 6 [depends: 3, 4, 5]: Frontend auth UI
  - Login page
  - Signup page
  - Forgot password page
  - OAuth buttons
  - Protected route wrapper component
  - Acceptance: renders correctly, forms submit, errors display

Task 7 [depends: all]: E2E tests
  - Full signup → login → access protected → logout flow
  - OAuth flow (mocked)
  - Unauthorized access rejection
  - Role-based page access
  - Acceptance: all E2E tests pass in headless browser
```

### Step 3: Human Confirmation

The plan is shown to the human. They can:
- **Approve**: "looks good, build it"
- **Modify**: "skip OAuth for now, just email/password" or "use server-side sessions, not JWTs"
- **Reject**: "wrong approach, I want X instead"

This is the ONLY time the human is involved until the feature is done.

### Step 4: Sub-Agent Execution

The orchestrator spawns sub-agents for parallel tasks:

```
                    Orchestrator
                   /     |      \
             Agent A  Agent B  Agent C
             (schema) (utils)  (OAuth)
                   \     |      /
                    Merge + Test
                   /     |      \
             Agent D  Agent E  Agent F
             (routes) (RBAC)   (UI)
                   \     |      /
                    Merge + Test
                        |
                    Agent G (E2E)
                        |
                    Final Verify
```

Each sub-agent receives:
- The repo profile
- The full plan (so it knows what other agents are building)
- Its specific task with acceptance criteria
- The repo conventions to follow
- A structured output schema (what to return when done)

Each sub-agent:
1. Creates its files / modifies existing files
2. Writes tests for its piece
3. Runs those tests
4. Returns: `{status: "done", files: [...], tests_passed: true}` or `{status: "blocked", reason: "..."}`

### Step 5: Integration

After each wave of parallel agents completes:
1. Orchestrator merges their work (handles conflicts if any)
2. Runs the FULL test suite (not just the new tests)
3. If tests fail:
   - Diagnoses which agent's work caused the failure
   - Spawns a fix agent with the error context
   - Retests after fix
   - Loops until green
4. If tests pass:
   - Proceeds to the next wave of tasks

### Step 6: Final Verification

After all tasks are complete:
1. Run the full test suite one final time
2. Run E2E tests
3. Run linting / type checking
4. Check for security issues (hardcoded secrets, unvalidated input, XSS vectors)
5. Review the full diff for consistency (naming, imports, conventions)
6. Generate a feature summary document

### Step 7: Handoff

The system creates a branch (or PR) and reports to the human:

```
Feature: Auth System
Branch: feature/auth-system
Status: Ready for review

Files changed: 34
Tests added: 47
E2E scenarios: 6 (all passing)

Summary: Built email/password auth with Google OAuth, server-side sessions, 
and role-based access control. See docs/features/auth-system.md for details.

Manual test suggestions:
1. Sign up with a new email
2. Log in, verify session persists across page reload
3. Try accessing /admin as a regular user (should redirect)
4. Log out, verify session is cleared
```

## Technical Architecture

### New Modules

```
nightshift/
  planner.py       — Reads repo, generates architecture doc + task breakdown
  decomposer.py    — Converts task breakdown into sub-agent work orders
  subagent.py      — Spawns, monitors, collects results from sub-agents
  integrator.py    — Merges sub-agent work, runs tests, handles failures
  feature_cli.py   — CLI: `python3 -m nightshift build "feature description"`
  feature_state.py — Feature build state tracking (separate from shift state)

schemas/
  feature.schema.json    — Structured output for feature planning
  task.schema.json       — Structured output for sub-agent task completion
  
docs/features/           — Generated feature summaries (one per build)
```

### New CLI Commands

```bash
# Plan a feature (generates plan, doesn't build yet)
python3 -m nightshift plan "build auth system"

# Build a feature (plans + builds + tests)
python3 -m nightshift build "build auth system"

# Resume a failed/interrupted build
python3 -m nightshift build --resume

# Check status of an in-progress build
python3 -m nightshift build --status
```

### State Management

Feature builds need richer state than hardening shifts:

```json
{
  "version": 1,
  "feature": "auth system",
  "status": "building",
  "plan": { ... },
  "tasks": [
    {
      "id": 1,
      "title": "Database schema",
      "status": "done",
      "agent_id": "agent-a",
      "files": ["prisma/schema.prisma", "prisma/migrations/..."],
      "tests_passed": true
    },
    {
      "id": 3,
      "title": "API routes",
      "status": "in_progress",
      "agent_id": "agent-d",
      "depends_on": [1, 2]
    }
  ],
  "integration_results": [
    {"wave": 1, "status": "passed", "tests": 47, "failures": 0},
    {"wave": 2, "status": "failed", "tests": 89, "failures": 2, "fix_attempts": 1}
  ],
  "final_verification": null
}
```

## Open Design Questions

These need to be answered before building Loop 2. They are listed here so the meta-prompt agent can tackle them one at a time.

1. **How do sub-agents communicate?** Files on disk? Shared JSON? A message queue? The simplest approach is files — each agent reads/writes to the worktree and the orchestrator checks git status between waves.

2. **How is the plan approved?** Does the human see raw markdown? A structured summary? Should there be a TUI for plan review?

3. **How does conflict resolution work?** If two agents modify the same file, who wins? Options: last-write-wins (bad), orchestrator merges (complex), prevent conflicts by assigning files exclusively to agents (constraining but safe).

4. **How does the system know what "production-ready" means for this specific repo?** Some repos have CI that must pass. Some have specific E2E setups. Some have no tests at all. The system needs to discover or be told the bar.

5. **Budget limits**: How long can a feature build run? How many sub-agent spawns before it gives up? Suggested: configurable in `.nightshift.json` with sane defaults (e.g., max 4 hours, max 20 sub-agent spawns).

6. **What if the feature is too big?** The system should detect when a feature request would require >50 files changed or >10 sub-agent tasks and suggest breaking it into phases. "I'd recommend building this in 3 phases: (1) basic email/password auth, (2) OAuth integration, (3) RBAC. Should I start with phase 1?"
