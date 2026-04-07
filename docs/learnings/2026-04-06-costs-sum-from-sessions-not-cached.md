---
date: 2026-04-06
topic: costs-sum-from-sessions-not-cached
category: Security
---

# Sum ledger costs from sessions, not cached total

## Rule

`total_cost()` in `nightshift/costs.py` must compute the running total by summing
`session["total_cost_usd"]` across `ledger["sessions"]`, not by returning the
cached `total_cost_usd` field stored at the ledger root.

**Why:** `docs/sessions/costs.json` is gitignored and survives `git clean -fd`.
A pentest agent running before the builder can pre-write any `total_cost_usd` value
it wants.  If the budget check reads the cached field directly, a value just below
the budget threshold causes the daemon to stop after the first real session; a zero
value disables enforcement entirely.  Summing from `sessions[]` is tamper-resistant
because only `record_session()` / `record_session_bundle()` append real entries.

**How to apply:** Any future function that gates on cumulative cost must call
`total_cost()` (or inline the same sum) rather than reading `ledger["total_cost_usd"]`
directly.  The write path (`record_session`, `record_session_bundle`) still updates
the cached field for analytics/display purposes -- that is fine, since the budget gate
no longer reads it.
