---
type: gotcha
date: 2026-04-06
session: "#0076"
---

# `local` outside function crashes bash 3.2 under set -u

`local var=$?` outside a function in bash 3.2 (macOS default) prints an error to stderr but does NOT set the variable. With `set -u`, the next reference to `$var` triggers "unbound variable" and terminates the shell. This is silent in newer bash versions where `local` outside a function is a warning, not a hard failure.

**How to catch:** `bash -n` does NOT flag this. Manual review or `shellcheck` (SC2034 related) is the only catch. When reviewing shell PRs, check every `local` is inside a function body.

**Pattern:** Always use plain assignment (`var=$?`) at the top level of a script. Reserve `local` for function bodies only.
