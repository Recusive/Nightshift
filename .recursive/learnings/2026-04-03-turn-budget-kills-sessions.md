# Learning: Turn budget kills sessions that are doing everything right
**Date**: 2026-04-03
**Session**: 0003-daemon
**Type**: failure

## What happened
Session 3 built backend exploration forcing — 34 new tests, 189 total passing, all docs updated, PR created. The sub-agent code review found 3 minor issues (move a constant, sort __all__, filter a string). The agent started fixing them and hit --max-turns 100 at event 193. Died mid-edit. Left PR #12 open with uncommitted local changes. A human had to finish it.

## The lesson
Set --max-turns to 500 or higher. A full session (read docs + build + test + update docs + PR + code review + fix review) easily takes 150-200 tool calls. 100 is a death sentence for non-trivial features. The circuit breaker (3 consecutive failures) is the real safety net, not turn count.

## Evidence
- Session 3 log: docs/sessions/20260403-200635.log (193 events, exited mid-edit)
- PR #12 was left open, manually finished by monitor agent
- Session 1 (simpler feature) used ~80 turns — barely fit in 100
