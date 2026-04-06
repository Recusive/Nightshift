---
description: Generate a marketing-quality changelog for a release version
argument-hint: <version> [pr-number]
allowed-tools: Bash(gh:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git status:*), Read, Write, Edit, Glob, Grep
---

# Changelog Generator

Generate a changelog for Orbit release `$1`, written for the marketing site. If a PR number `$2` is provided, pull its metadata from GitHub.

## Validation

If `$1` is empty, output:

```
Usage: /changelog <version> [pr-number]
Examples:
  /changelog v0.0.7
  /changelog v0.0.7 74
```

Stop execution.

## Step 0: Resolve Version

The version is `$1`. Determine whether it's a version or a PR number:

- **Pure integer** (e.g., `73`, `104`) → This is a PR number, not a version. Infer the version from the current branch name and use `$1` as the PR number.
- **Contains dots** (e.g., `0.0.7`, `v0.0.7`) → This is a version. Prepend `v` if missing.
- **Starts with `v`** (e.g., `v0.0.7`) → This is a version. Use as-is.

To get the branch name for fallback:

```bash
git branch --show-current
```

---

## Step 1: Gather Context

Collect all raw material. Run these commands:

```bash
git branch --show-current
git log main..HEAD --oneline
git diff main --stat
git diff main --name-only
git status --short
```

If a PR number is available (either `$2`, or `$1` if it was a bare number):

```bash
gh pr view <pr-number> --json title,body,commits,files
```

Check if a changelog already exists by reading `docs/changelog-<version>.md`. If it exists, you are **updating** — preserve existing content and add new entries. Do not rewrite what's already there.

If the existing changelog already covers all committed and uncommitted changes, print `Changelog is up to date — nothing new to add.` and stop.

Read `docs/changelog-v0.0.6.md` as the **tone and structure reference**. Match its style exactly.

---

## Step 2: Categorize Changes

Group everything into user-facing categories. Use your judgment — not every commit deserves a section.

| Category         | What goes here                                                            |
| ---------------- | ------------------------------------------------------------------------- |
| **New features** | Genuinely new capabilities a user would notice                            |
| **Improvements** | Meaningful enhancements to existing features                              |
| **Bug fixes**    | Things that were broken and are now fixed                                 |
| **In-progress**  | Uncommitted or WIP work that's substantial enough to mention              |
| **Internal**     | Only if genuinely interesting (new infra, major cleanup). Skip if boring. |

**Discard:**

- Routine refactors that don't change behavior
- File renames, import reordering, lint fixes
- Test additions (unless they represent a new testing capability)
- Documentation changes (unless they're user-facing docs)

---

## Step 3: Write the Changelog

Create or update `docs/changelog-<version>.md`.

### Format

```markdown
# Orbit <version>

_<Month Year>_

---

## <Category Name>

### <Feature or improvement name>

<1-2 paragraphs describing what the user gets. Not what files changed.>

---

## Bug Fixes

- **<Short name>** — <What was broken, now fixed.>

---

## <Feature Name> _(in progress)_

<One paragraph. What it will do. Note it ships in a later release.>

---

## Internal

- <One-liner only>
```

### Writing Rules

These are non-negotiable:

1. **Lead with what users get.** "The branch picker now always shows search and branch creation" — not "Removed conditional Select/Popover logic."

2. **No internal naming.** Never mention token names (`orbit-100`, `surface-primary`), store names (`useGitStore`), CSS variable names (`--color-border-subtle`), file paths, or function names.

3. **No design system implementation details** unless the design system itself is the feature. "Consistent colors across light and dark themes" is fine. "Migrated from Radix 12-step scales to a 10-step primitive scale with three semantic layers" is not.

4. **Don't elevate routine cleanup.** Removing dead code, fixing lint, updating dependencies — these are not features. If they're significant enough (e.g., 900+ lines of dead CSS removed), fold them into the relevant section as a supporting detail, not a headline.

5. **Bug fixes are one-liners.** State what broke and that it's fixed. Don't explain the implementation.

6. **In-progress features get one paragraph.** What it will do, what's built so far at a high level, and that it ships later.

7. **Internal section uses one-liners.** If there's nothing interesting, omit the section entirely.

8. **Don't sound impressed by your own work.** No "comprehensive", "robust", "elegant", "powerful". Just say what it does.

9. **Match the reference.** Read `docs/changelog-v0.0.6.md` before writing. Your output should feel like the same person wrote both.

---

## Step 4: Output

After writing the file:

1. Print: `Changelog written to docs/changelog-<version>.md`
2. Print the full changelog content
3. If updating an existing file, note what was added
