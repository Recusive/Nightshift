# Prompt contracts need tests

**Date**: 2026-04-05
**Type**: process
**Session**: #0053 (Step 0 evaluation targeting fix)

## What happened

The evaluator code already passed `--repo-dir`, but the authoritative Step 0
prompt in `docs/prompt/evolve.md` still told sessions to run `nightshift test`
without that flag. That let evaluation behavior drift from the control doc in a
way that is easy to miss during normal code review.

## Rule

If a prompt/control file carries an operational contract such as an exact
command, required flag, or filesystem path, add a regression test for the
literal contract in the doc and a code-side test for the helper that executes
it.

## Apply next time

When a red-team or prompt-integrity alert points at a control doc, do not stop
at patching the prose. Add a test that will fail the next time the contract and
the implementation drift apart.
