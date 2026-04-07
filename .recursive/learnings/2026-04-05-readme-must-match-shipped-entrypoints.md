# Learning: README must match shipped entry points
**Date**: 2026-04-05
**Session**: 0054
**Type**: process

## What happened
The README still documented bare `nightshift run` / `nightshift build`
commands, but the repo does not install a global `nightshift` console script.
The real entry points are `python3 -m nightshift ...` in a repo checkout and
the wrapper scripts installed by `scripts/install.sh`.

## The lesson
For repo-local tools, document the invocation surfaces that actually ship. If
there is no console script, say so explicitly and point users to the module
entry point or wrapper scripts. Treat README commands as contracts that need
validation, not as marketing shorthand.

## Evidence
`README.md`, `pyproject.toml`, `scripts/install.sh`, `nightshift/cli.py`
