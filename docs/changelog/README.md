# Changelog

Each version gets its own file. This is the index.

## For Contributors

This changelog is **maintained by the agent**, not by humans. When the agent finishes a session, it:

1. Adds entries to the current version file (or creates a new one if cutting a release)
2. Updates the version table below
3. Commits alongside the code changes

If you're a human contributor and your PR gets merged, the next agent session will document it in the changelog. You don't need to write changelog entries yourself.

### Version format

```
v{major}.{minor}.{patch}  —  {codename}

major: breaking changes to the runner, config format, or CLI
minor: new features, new modules, significant improvements
patch: bug fixes, small improvements, docs
```

Beta period (`0.x.x`): breaking changes can happen in any release.

### Entry tags

`[feat]` `[fix]` `[refactor]` `[test]` `[docs]` `[meta]` `[remove]`

### Sections per version file

```
## Added       — new features, files, capabilities
## Changed     — modifications to existing behavior
## Fixed       — bug fixes
## Removed     — deleted features, files, deprecated code
## Internal    — refactors, tests, CI, docs that don't affect users
```

## Versions

| Version | Date | Codename | Status | Highlights |
|---------|------|----------|--------|------------|
| [v0.0.1](v0.0.1.md) | 2026-04-03 | Initial Beta | Released | SKILL.md, bash runners, Claude Code only |
| [v0.0.2](v0.0.2.md) | 2026-04-03 | Control Plane | Released | Python orchestrator, pluggable agents, 123 tests, guard rails |
| [v0.0.3](v0.0.3.md) | 2026-04-03 | Intelligence | Released | Diff scorer, state injection, test incentives, backend forcing, Phractal validation |
| [v0.0.4](v0.0.4.md) | 2026-04-03 | Agent Quality | Released | Category balancing, shift-log tolerance, PR #13 hardening, focus path improvements |
| [v0.0.5](v0.0.5.md) | 2026-04-03 | Multi-Repo | Released | Multi-repo support, Loop 1 complete at 100% |
