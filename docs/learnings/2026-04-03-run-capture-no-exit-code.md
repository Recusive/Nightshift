---
type: gotcha
date: 2026-04-03
module: nightshift/shell.py, nightshift/integrator.py
---

# run_capture() only returns stdout, not exit code

`shell.run_capture()` with `check=False` returns `result.stdout.strip()` but
discards the exit code. When you need both the exit code AND the output (e.g.,
running a test suite where you need to know pass/fail AND see the output), use
`subprocess.run()` directly instead.

This is why `integrator.run_test_suite()` uses `subprocess.run` instead of
`run_capture` -- it needs `(exit_code, output)` as a tuple.
