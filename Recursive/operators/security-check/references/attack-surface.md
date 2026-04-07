# Attack Surface Checklist

## Prompt Control
- Self-modification gaps — can the agent rewrite its own instructions?
- Prompt injection via task titles, handoff text, or eval reports?
- Pentest data block treated as instructions instead of data?

## Shell & Path Handling
- Shell quoting bugs (unquoted variables in test expressions, paths with spaces)
- Path traversal in file operations
- Symlink attacks in worktree or temp directories

## Cleanup & Recovery
- Stale worktrees, temp files, or lock files accumulating?
- Daemon recovery after crash — does it actually come back clean?
- Git state corruption after failed operations?

## Verification Paths
- False-green: can tests pass while behavior is broken?
- Can the agent claim success without actually verifying?
- Dry-run vs real-run divergence?

## Documentation
- Stale docs that would cause the builder to do the wrong thing?
- Path references pointing to files that don't exist?
- Contradictory instructions across different prompt files?

## Task & State Integrity
- Task queue poisoning (malformed frontmatter, ID collisions)?
- Session index manipulation affecting role selection?
- Cost tracking or handoff workflows that can drift?
- Eval or autonomy reports that could be fabricated to game role selection?

## Daemon Behavior
- Brittle daemon recovery or PR recovery?
- Can the autonomous loop corrupt itself?
- Can it silently skip work or claim success when it should fail?
- Race conditions between daemon and manual operations?
