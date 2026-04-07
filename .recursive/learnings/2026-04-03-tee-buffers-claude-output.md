# Learning: claude -p --verbose buffers output through tee
**Date**: 2026-04-03
**Session**: 0003-daemon
**Type**: gotcha

## What happened
The daemon piped `claude -p --verbose 2>&1 | tee log.log`. The log file stayed at 0 bytes for the entire session. Only the final summary (35 lines) appeared after the session ended. All tool calls, messages, and errors were invisible.

## The lesson
Use `--output-format stream-json` with `--verbose`. This produces newline-delimited JSON events that flush line-by-line through tee. Each event contains tool calls, messages, and results. Parse with `json.loads()` per line.

## Evidence
- Session 1 log: 1331 bytes (only final summary)
- Session 3 log (after fix): 260KB, 39+ events, full tool call history
- Fix: PR #11
