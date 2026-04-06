---
title: Broad fallback regex is an injection vector in scored-file readers
date: 2026-04-06
category: security
type: gotcha
---

# Broad fallback regex is an injection vector in scored-file readers

When a scoring function has a strict primary regex (markdown table format)
and a loose fallback regex (`Total.*?(\d+)\s*/\s*100`), the fallback is the
attack surface.  The fallback fires whenever the primary misses, so a
fabricated single-line file `Total: 99/100` passes the fallback silently
and returns a valid score.

**The correct pattern:**

1. Add a *content validity* check BEFORE score extraction:
   - At least one reliable metadata marker (`**Date**:`)
   - At least N structural rows proving the content is a real report
     (N >= 3 dimension rows with `X/10` scores)
2. Reject the file entirely (`return None`) if the validity check fails.
3. Remove the fallback regex; one strict regex on validated content is enough.

This pattern applies to any daemon that gates behavior on a file score:
eval files, autonomy files, or any future scored artifact.  The validity
check is cheap and eliminates the entire class of single-line injection.
