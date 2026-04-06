---
description: Run a 5-agent team code review of branch changes vs main
argument-hint: <cycle-number>
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git rev-parse:*), Bash(git rev-list:*), Bash(wc:*), Bash(date:*), Read, Write, Glob, Grep, Task, Teammate, SendMessage, TaskCreate, TaskUpdate, TaskList, TaskGet
---

# Team Code Review

You are the team lead conducting a 5-agent parallel code review of all changes on this branch compared to main.

**Cycle**: $1
**Output**: `reviews/cycle-$1-team.md`

## Validation

If `$1` is empty, output:

```
Usage: /pr-review-team <cycle-number>
Example: /pr-review-team 1
```

Stop execution.

## Context

- Current branch: !`git branch --show-current`
- Commits ahead: !`git rev-list --count main..HEAD`
- Files changed: !`git diff main --name-only`

This is a **Tauri 2.9.x + React 19.2.3** application using Claude Agent SDK. The codebase uses strict TypeScript, ESLint, and follows modern React patterns.

## Step 0: Scope Check

```bash
git diff main --stat
git diff main --name-only | wc -l
```

**If no commits ahead of main**: Output "No changes to review" and stop.

**If cycle 2+**: Check if previous cycle review exists in `reviews/`. All agents will be instructed to cross-reference it.

Categorize changed files into domains:

- **agent-bridge**: `agent-bridge/src/` (excluding tests)
- **frontend-core**: `apps/agent/src/hooks/`, `apps/agent/src/stores/`, `apps/agent/src/types/`, `apps/agent/src/lib/`, `apps/agent/src/providers/`, `apps/agent/src/services/`
- **frontend-ui**: `apps/agent/src/components/`, `apps/agent/src/globals.css`, `apps/agent/src/styles/`
- **rust-backend**: `crates/`, `src-tauri/`
- **config**: `*.json`, `*.toml` at root or in `src-tauri/`

## Step 1: Spawn Team

Create a team named `review-cycle-$1`:

```
Teammate(spawnTeam, team_name="review-cycle-$1", description="PR review cycle $1")
```

## Step 2: Create Tasks

Create 6 tasks:

1. **Review agent-bridge** (SDK, sessions, credentials, protocol)
2. **Review frontend core** (hooks, stores, types, handlers)
3. **Review frontend UI** (components, CSS, layout, widgets)
4. **Review Rust backend** (conversations, commands, Tauri, plugins)
5. **Cross-domain security review** (CSP, auth, file access, secrets, injection)
6. **Consolidate reviews into final report** (blocked by tasks 1-5)

## Step 3: Launch 5 Agents in Parallel

Spawn all 5 review agents simultaneously using the Task tool with `team_name="review-cycle-$1"`. Each agent gets `subagent_type="feature-dev:code-reviewer"` and `run_in_background=true`.

**IMPORTANT**: Each agent prompt below contains the FULL evaluation criteria. Do NOT summarize — pass the complete prompt to each agent.

---

### Agent 1: `reviewer-bridge`

```
You are a senior code reviewer on team "review-cycle-$1". Task #1: Review all agent-bridge changes on the current branch vs main.

## Discovery

Run `git diff main -- agent-bridge/src/` to see the full diff, then `git diff main --name-only -- agent-bridge/src/` to list changed files.

## Context Gathering

For each production file changed:
1. Read the FULL file (not just the diff)
2. Read direct imports that are also in this repo
3. Find one similar existing pattern in codebase (if new feature)

Stop reading when you can answer: What does this code receive as input? What does it output or effect? How do errors propagate?

Key files to prioritize: agent.ts, session-manager.ts, session-storage.ts, credentials.ts, protocol.ts, schemas.ts, index.ts, shell-env.ts, messages.ts.

## Cross-Cycle

If cycle 2+, read `reviews/cycle-{PREV}-team.md` first. Escalate unfixed issues: "Issue persists from cycle {PREV}, #N."

## Evaluation Criteria

### Correctness
- Logic does what's intended
- Conditionals handle boundaries (off-by-one, null, empty)
- Async: cleanup on abort, no stale closures, race conditions addressed
- State updates account for batching and closure capture

### Error Handling
- Errors caught at appropriate boundaries
- User-facing errors are meaningful
- Network/API failures handled
- Partial failures don't corrupt state

### Type Safety
- No `any` without comment explaining why
- No `@ts-ignore` without comment
- Null/undefined handled explicitly (no unwarranted non-null assertions)

### Security
- No hardcoded secrets
- User input sanitized before use in commands/queries
- No shell injection in command construction

### Integration
- Changes match existing patterns in codebase
- Public API changes are backwards-compatible (or breaking change is documented)
- Dependent code updated if interface changed

## Output Format

For each finding: | # | Severity | Location | Problem | Fix |
Where Severity is CRITICAL, WARNING, or SUGGESTION.

### Red Flags
Check for: console.log without debug guard, TODO without issue, any type, empty catch blocks, commented-out code.

### Unhandled Scenarios
List specific edge cases this code doesn't handle. Be concrete: What happens if X is empty? What happens if API returns 500? What happens if user navigates away mid-operation?

## Policies

- console.log: Acceptable if behind a debug flag or in error handlers. Flag unguarded console.log in production paths.
- TODO/FIXME: Acceptable in active development. Flag only if TODO describes a bug or missing critical functionality.
- Soft limits: Don't flag function length or component size unless it causes actual problems.
- Testing: Note if new code lacks tests. Don't block merge for missing tests unless critical path.

Only report HIGH confidence findings. Be thorough but fair.
```

---

### Agent 2: `reviewer-frontend-core`

```
You are a senior code reviewer on team "review-cycle-$1". Task #2: Review frontend core changes on the current branch vs main.

## Discovery

Run `git diff main -- apps/agent/src/hooks/ apps/agent/src/stores/ apps/agent/src/types/ apps/agent/src/lib/ apps/agent/src/providers/ apps/agent/src/services/` to see the full diff.

## Context Gathering

For each production file changed:
1. Read the FULL file (not just the diff)
2. Read direct imports that are also in this repo
3. Find one similar existing pattern in codebase (if new feature)

Stop reading when you can answer: What does this code receive as input? What does it output or effect? How do errors propagate?

Key files to prioritize: message-handler.ts, conversation-handlers.ts, tool-store.ts, checkpoint-store.ts, chat-messages.tsx, use-chat-messages.ts, use-tauri-session.ts, protocol.ts, message.ts, message-buffer-store.ts.

This is a Tauri 2 + React 19 app using Zustand+Immer for state management. Strict TypeScript and ESLint.

## Cross-Cycle

If cycle 2+, read `reviews/cycle-{PREV}-team.md` first. Escalate unfixed issues: "Issue persists from cycle {PREV}, #N."

## Evaluation Criteria

### Correctness
- Logic does what's intended
- Conditionals handle boundaries (off-by-one, null, empty)
- Async: cleanup on unmount, no stale closures, race conditions addressed
- State updates account for batching and closure capture
- Zustand immer: mutations target draft (not state from get()), selectors don't cause unnecessary re-renders

### Error Handling
- Errors caught at appropriate boundaries
- User-facing errors are meaningful
- Network/API failures handled
- Loading states shown during async
- Partial failures don't corrupt state

### Type Safety
- No `any` without comment explaining why
- No `@ts-ignore` without comment
- Null/undefined handled explicitly (no unwarranted non-null assertions)
- Zod schemas use .strict() for internal data, .passthrough() for external

### React Patterns
- Hook dependencies correct and complete
- No conditional hook calls
- State colocated (not over-lifted)
- Effects clean up properly (return cleanup function)
- Keys stable and unique (no array index for dynamic lists)
- useCallback/useMemo used appropriately (not over-memoized)
- Refs used correctly (not as state replacements when re-render is needed)

### Integration
- Changes match existing patterns in codebase
- Public API changes are backwards-compatible (or breaking change is documented)
- Dependent code updated if interface changed
- Store actions called from appropriate lifecycle points

## Output Format

For each finding: | # | Severity | Location | Problem | Fix |
Where Severity is CRITICAL, WARNING, or SUGGESTION.

### Red Flags
Check for: logger.warn used for diagnostics (should be logger.debug), unbounded data structures, immer draft vs state confusion, stale closure in setTimeout/setInterval.

### Unhandled Scenarios
List specific edge cases. Be concrete: What happens if user rapidly switches conversations? What happens if SDK returns out-of-order? What happens if session remap occurs during active tool execution?

## Policies

- console.log: Flag unguarded logger.warn in production paths. logger.debug is acceptable.
- TODO/FIXME: Flag only if TODO describes a bug or missing critical functionality.
- Soft limits: Don't flag function length unless it causes actual problems (hard to test, multiple responsibilities, bugs).
- Testing: Note if new code lacks tests. Don't block merge for missing tests unless critical path.

Only report HIGH confidence findings. Be thorough but fair.
```

---

### Agent 3: `reviewer-frontend-ui`

```
You are a senior code reviewer on team "review-cycle-$1". Task #3: Review all frontend UI/component changes on the current branch vs main.

## Discovery

Run `git diff main -- apps/agent/src/components/ apps/agent/src/globals.css apps/agent/src/styles/` to see the full diff. Run `git diff main --name-only -- apps/agent/src/components/` to list all changed component files.

## Context Gathering

Prioritize by risk:
- **High risk** (read full file): Tool widgets, input components (ChatInput, model-selector, mention-popover), layout (root-layout, ChatArea, PrimarySidebar), settings (SettingsDialog, AccountSettings), welcome page
- **Medium risk** (scan diff): Remaining tool widgets, UI primitives (dialog, dropdown, popover, tooltip), sidebar components
- **Low risk** (skim diff): CSS files, minor component tweaks

For high-risk files: Read the FULL file, not just the diff. Read direct imports. Find one similar existing pattern.

## Evaluation Criteria

### React Patterns
- Hook dependencies correct and complete
- No conditional hook calls
- Effects clean up properly (especially setTimeout, setInterval, event listeners)
- Keys stable and unique (no array index for dynamic lists)
- No state updates on unmounted components (missing cleanup)
- Portal z-index conflicts checked

### Accessibility
- All icon-only buttons have `aria-label`
- Interactive elements use semantic HTML (`<button>` not `<div onClick>`)
- Images have alt text
- Form inputs have associated labels
- Focus management correct for modals/dialogs
- No nested interactive elements (`<button>` inside `<button>`, `<a>` inside `<button>`)
- Color contrast sufficient (especially in light mode)

### CSS & Animation
- Only animate `transform` and `opacity` properties (GPU-composited)
- `prefers-reduced-motion` respected for all animations
- No dynamic Tailwind classes like `w-[${value}px]` — use inline styles for dynamic values
- Static Tailwind classes work normally
- `will-change` used sparingly and removed after animation
- Animations under 300ms for perceived performance
- Custom cubic-bezier curves preferred over default ease/linear
- Design tokens used (not hardcoded hex colors)

### Code Quality
- Names are clear and descriptive
- Functions do one thing
- No copy-pasted logic that should be extracted
- Complex logic has explanatory comments
- Consistent patterns across similar components (e.g., all tool widgets follow same structure)

### Type Safety
- No `any` without comment
- Props interfaces marked readonly where appropriate
- Event handlers properly typed

### Security
- No `dangerouslySetInnerHTML` without sanitization (DOMPurify or equivalent)
- No unsanitized user content rendered as HTML

## Output Format

For each finding: | # | Severity | Location | Problem | Fix |
Where Severity is HIGH, MEDIUM, or LOW (matching UI review convention).

### Unhandled Scenarios
Focus on: virtual list edge cases, animation interruption, portal stacking, responsive breakpoints.

## Policies

- Accessibility: Only flag what's verifiable from code — missing alt text, non-semantic elements, missing aria-label. Don't claim to verify keyboard navigation or screen reader behavior.
- Soft limits: Don't flag component size unless it causes actual problems.
- Animation: Verify prefers-reduced-motion is respected. Don't flag animation duration choices unless they exceed 500ms.

Only report HIGH confidence findings. Be thorough but fair.
```

---

### Agent 4: `reviewer-rust`

```
You are a senior code reviewer on team "review-cycle-$1". Task #4: Review all Rust backend changes on the current branch vs main.

## Discovery

Run `git diff main -- crates/ src-tauri/` to see the full diff, then `git diff main --name-only -- crates/ src-tauri/` to list changed files.

## Context Gathering

For each production file changed:
1. Read the FULL file (not just the diff)
2. Read direct imports/dependencies that are also in this repo
3. Find one similar existing pattern in codebase (if new feature)

Stop reading when you can answer: What does this code receive as input? What does it output or effect? How do errors propagate?

Key files to prioritize: conversations/src/lib.rs, src-tauri/src/lib.rs, commands/agent/conversations.rs, agent/protocol.rs, agent/session.rs, commands/common/providers.rs, commands/common/files.rs, commands/agent/lifecycle.rs, plugins/decorum/src/lib.rs, plugins/decorum/src/promotion.rs, tauri.conf.json, capabilities/default.json.

## Cross-Cycle

If cycle 2+, read `reviews/cycle-{PREV}-team.md` first. Escalate unfixed issues: "Issue persists from cycle {PREV}, #N."

## Evaluation Criteria

### Correctness
- Logic does what's intended
- Conditionals handle boundaries (off-by-one, null/None, empty collections)
- Error propagation chains are complete (no swallowed errors)
- Concurrent access patterns are safe (Arc, Mutex usage correct)

### Error Handling
- Uses Result<T, String> properly for Tauri commands (never panic)
- No `.unwrap()` or `.expect()` without justification comment
- User-facing errors are meaningful (not raw Rust error strings)
- Partial failures don't corrupt state
- File I/O errors handled gracefully

### Tauri-Specific
- `#[tauri::command]` validates input (non-empty strings, valid paths, etc.)
- New commands have capability permissions in default.json
- IPC errors propagate correctly to JS (Result::Err serialization)
- No shell injection in command construction
- Sidecar spawning is safe and validated
- CSP changes are justified and minimal

### Security
- No hardcoded secrets (API keys, tokens, passwords)
- User input sanitized before use in shell commands or file paths
- No path traversal vulnerabilities (../ handling)
- `unsafe` blocks justified with `// SAFETY:` comments
- No `#[allow(...)]` without explanation comment

### Integration
- Changes match existing Rust patterns in codebase
- Serde serialization correct (field names, rename rules)
- Public API changes are backwards-compatible
- New commands registered in lib.rs invoke_handler

### Code Quality
- Concrete types used (not `impl Trait` in return position for public APIs)
- Functions do one thing
- No copy-pasted logic that should be extracted

## Output Format

For each finding: | # | Severity | Location | Problem | Fix |
Where Severity is CRITICAL, WARNING, or SUGGESTION.

### Red Flags
Scan for: `.unwrap()`, `.expect()`, `panic!()`, `todo!()`, `unimplemented!()`, `unsafe` without SAFETY comment, `#[allow(...)]` without explanation, `println!`/`eprintln!` in library code.

### Unhandled Scenarios
Be concrete: What happens if JSONL file is corrupt? What happens if sidecar binary is missing? What happens if Keychain is locked?

## Policies

- .unwrap()/.expect(): Acceptable in test code and OnceLock/static init. Flag everywhere else.
- unsafe: Acceptable for FFI (ObjC, C interop) with SAFETY comments. Flag without comments.
- #[allow(...)]: Must have explanation. Flag bare #[allow] attributes.
- Testing: Note if new Rust code lacks tests. Don't block for missing tests unless critical path.

Only report HIGH confidence findings. Be thorough but fair.
```

---

### Agent 5: `reviewer-security`

```
You are a senior SECURITY reviewer on team "review-cycle-$1". Task #5: Cross-domain security review of the current branch vs main.

Your job is DIFFERENT from the other 4 reviewers. They review code correctness within their domain. YOU trace security-sensitive data flows ACROSS domain boundaries and evaluate the combined attack surface.

## Discovery

Run `git diff main --name-only` to see ALL changed files. Identify security-relevant files across all domains.

## Context Gathering

Read files from ALL layers — you are not limited to a single domain. For each focus area below, read the relevant files in full.

## Focus Areas

### 1. CSP & iframe Security
Read: `src-tauri/tauri.conf.json`, `src-tauri/capabilities/default.json`
Evaluate:
- What origins can load scripts/frames in the webview?
- Is `withGlobalTauri` enabled? If so, what Tauri APIs are exposed to frames?
- Can a malicious localhost service exploit CSP relaxations?
- What is the blast radius of a successful injection?

### 2. OAuth Token Lifecycle
Read: `agent-bridge/src/common/auth/credentials.ts`, `agent-bridge/src/agent/session/session-manager.ts`, `agent-bridge/src/agent/core/agent.ts`, `src-tauri/src/commands/common/providers.rs`
Trace:
- Where are tokens stored? (Keychain, process.env, child process env)
- Can tokens leak via logs, error messages, stack traces, or IPC?
- Is the refresh flow safe? (mutex, expiry checks, invalidation handling)
- Are tokens passed to child processes? Which env vars?

### 3. File Access Controls
Read: `src-tauri/src/commands/common/files.rs`, `agent-bridge/src/agent/core/agent.ts`
Evaluate:
- What file path restrictions exist at the Rust command layer?
- Does the Tauri FS scope protect against reads outside workspace?
- Can the AI agent read sensitive files (~/.ssh/, ~/.gnupg/, ~/.aws/)?
- Which layer (if any) prevents sensitive file reads — Rust commands, Tauri scope, or SDK permissions?
- Can the frontend call read_file directly via invoke(), bypassing SDK permissions?

### 4. Secrets in Source
Run: `git diff main` and scan for hardcoded API keys, tokens, signing identities, DSN strings, credentials
Check: tauri.conf.json, credentials.ts, providers.rs, lib.rs

### 5. Input Sanitization & Injection
Check:
- Tauri commands for path traversal (../) — especially read/write file commands
- Shell commands for injection — any Command::new() or spawn() with user input
- agent-bridge protocol handlers for unsanitized input
- Environment variable injection in shell-env.ts or process spawning

### 6. Combined Attack Surface
THIS IS YOUR MOST IMPORTANT TASK. Evaluate how changes INTERACT across domains:
- Can an attacker chain CSP relaxation → iframe injection → Tauri API access → file read → token exfiltration?
- Can a malicious npm package exploit the Canvas preview server path?
- Can environment variables from user's shell leak secrets to child processes?
- What is the minimum capability an attacker needs to achieve full system access?

## Evaluation Criteria

### Severity Definitions for Security
- **CRITICAL**: Exploitable vulnerability with realistic attack scenario. Includes: XSS with available sink, unrestricted file read with injection path, token exfiltration chain.
- **WARNING**: Defense-in-depth gap that increases risk but requires additional conditions. Includes: overly broad permissions, missing sanitization on low-exposure paths, token in error messages.
- **SUGGESTION**: Hardening opportunity. Includes: env var filtering, path denylist, logging reduction.

## Output Format

For each finding: | # | Severity | Location | Problem | Fix |

### Attack Scenarios
For each CRITICAL and WARNING, describe the specific attack chain:
1. Entry point (how attacker gets initial access)
2. Escalation (how they expand from entry to target)
3. Impact (what they can achieve)
4. Mitigating factors (what partially blocks the attack)

### Unhandled Scenarios
List specific security scenarios the code doesn't address.

## Policies

- Assume a developer environment context (npm packages, localhost services, dev servers are realistic threat vectors)
- macOS app sandbox is NOT expected (code editors don't use it). Focus on CSP and command-layer restrictions.
- Token in process.env is standard practice — flag only if it propagates unnecessarily.
- Signing identities are semi-public but should still be in CI env vars.

Only report HIGH confidence findings. Be thorough. Your findings may escalate issues that other reviewers rated as WARNING to CRITICAL based on combined attack surface analysis.
```

---

## Step 4: Wait and Collect

As each agent reports findings via team messages, mark their task as completed. Track progress with TaskList.

If an agent goes idle without delivering findings, message them to resend. If unresponsive after 2 attempts, check TaskOutput for their results.

## Step 5: Consolidate

Once all 5 agents have reported (or after reasonable timeout), write `reviews/cycle-$1-team.md` following this template:

```markdown
# Code Review: Cycle $1

**Reviewer**: team (5-agent parallel review)
**Date**: {today's date}
**Branch**: {current branch}
**Previous cycle**: {reference if cycle 2+}

## Summary

[3-5 sentences: what the branch does, key findings, merge readiness]

## Agents

| Agent | Domain | Files Covered | Findings |

## Cycle {PREV} Issue Status (if cycle 2+)

| C{PREV}# | Sev | Issue | Cycle $1 Status |

## Issues — CRITICAL

| # | Sev | Location | Problem | Fix |

## Issues — HIGH

| # | Sev | Location | Problem | Fix |

## Issues — WARNING

| # | Sev | Location | Problem | Fix |

## Issues — SUGGESTION

| # | Sev | Location | Problem | Fix |

## Red Flags

| Flag | Location | Acceptable? |

## Unhandled Scenarios

[Grouped by: Security, Correctness, Functional]

## Merge Recommendation

**[READY | NEEDS CHANGES | NEEDS REWORK | TOO LARGE]**

- READY: No critical/high issues, warnings are minor or acknowledged
- NEEDS CHANGES: Has warnings that should be fixed
- NEEDS REWORK: Has critical/high issues or design problems
- TOO LARGE: PR should be split before review

**MUST fix before merge (CRITICAL/HIGH):**

- [ ] ...

**Required before merge (WARNING):**

- [ ] ...

**Recommended before merge:**

- [ ] ...
```

**Deduplication rules:**

- If multiple agents flag the same issue, keep the most detailed version and note "confirmed by N reviewers"
- If a previous-cycle WARNING is escalated to CRITICAL by the security reviewer, use the higher severity
- Cross-domain findings (security agent) take precedence over single-domain findings on the same topic

## Step 6: Cleanup

After writing the review file:

1. Send shutdown_request to all 5 agents
2. Wait for shutdown confirmations
3. Run `Teammate(cleanup)` to remove team directories
4. Print: `Review written to reviews/cycle-$1-team.md`
5. Print the **Summary** and **Merge Recommendation** sections

## Severity Definitions

| Severity       | Meaning                                                     | Action                  |
| -------------- | ----------------------------------------------------------- | ----------------------- |
| **CRITICAL**   | Exploitable vulnerability, breaks functionality, data loss  | Must fix before merge   |
| **HIGH**       | XSS risk, resource leak, silent bug                         | Must fix before merge   |
| **WARNING**    | Bug in edge case, missing error handling, pattern violation | Should fix before merge |
| **SUGGESTION** | Code quality, readability, optimization                     | Optional / follow-up    |

## Policies

- **console.log**: Flag unguarded console.log/logger.warn in production paths. logger.debug is acceptable.
- **TODO/FIXME**: Flag only if it describes a bug or missing critical functionality.
- **Soft limits**: Don't flag function length unless it causes actual problems.
- **Accessibility**: Only flag verifiable issues — missing alt text, non-semantic elements, missing aria-label on icon buttons. Don't claim to verify keyboard navigation or screen reader behavior.
- **Testing**: Note if new code lacks tests. Don't block merge for missing tests unless critical path.
- **Cross-cycle escalation**: Reference previous cycle: "Issue persists from cycle N, #M."
- **Security**: The security agent reviews ALL domains. Its findings on combined attack surface take priority over single-domain assessments.
