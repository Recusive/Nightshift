# Release Check Algorithm

Run after post-merge health check passes. Do not wait for a task — releasing is part of the build cycle.

1. List changelog files: `ls .recursive/changelog/v*.md`
2. List existing tags: `git tag --list 'v*'`
3. For each changelog version with NO matching tag (oldest first):
   a. Read the changelog — does it have real entries?
   b. Check: are there pending tasks targeting this version? (`target: vX.X.X` in frontmatter)
   c. If pending tasks target it:
      - ALL remaining are low/normal nice-to-haves? **Retarget them** to next version and release.
      - Any remaining is urgent or core? Skip, note in handoff.
   d. If entries exist AND no blocking tasks: **release it**
      - Update changelog status to "Released" with today's date
      - Run: `make release VERSION=X.X.X CODENAME="[codename]"`
      - Create next version's changelog skeleton if needed
4. Release in order (v0.0.6 before v0.0.7). Multiple releases per session is fine.

**Codename:** Use subtitle from changelog title (e.g., `# v0.0.6 -- Loop 2 Foundation` -> codename "Loop 2 Foundation").
