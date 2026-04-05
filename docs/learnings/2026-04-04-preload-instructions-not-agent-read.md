# Learning: Pre-load instruction files in the runner, not the agent
**Date**: 2026-04-04
**Session**: 0018
**Type**: pattern

When running against external repos, having the agent read instruction files directly means the agent sees the raw content with no guardrails. The fix is to pre-load the files in the runner (Python code you control) and inject them into the prompt wrapped in an untrusted context block. This way the agent never reads the raw files — it only sees the sanitized version.

The key insight: `build_prompt()` should remain a pure text-construction function. The caller (cli.py) reads the files and passes the content as a string parameter. This separation makes testing easy — you can pass any string (including adversarial content) without needing filesystem fixtures in every test.
