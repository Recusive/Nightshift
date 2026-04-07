---
name: sed POSIX space-before-slash bypass
description: POSIX character class needed to match any space before slash in XML closing tags
type: feedback
---

`</ *tag *>` in sed means: literal `<`, then `/`, then zero-or-more spaces, then `tag`.
It does NOT match `< /tag>` (a space BEFORE the slash).

To match any whitespace before AND after the slash use POSIX character classes:

```bash
sed 's|<[[:space:]]*/[[:space:]]*tag[[:space:]]*>|...|g'
```

This covers `</tag>`, `</ tag>`, `< /tag>`, `< / tag >` etc.

**Why:** The pentest found that `< /pentest_data>` (space before slash) escaped the
`</ *pentest_data *>` sanitization in daemon.sh, breaking the XML data boundary in
the builder prompt and allowing content after the tag to land as uninhibited instructions.
Same gap existed in `prompt_alert`. POSIX `[[:space:]]*` is supported by both GNU and BSD sed.

**How to apply:** Any time you write a sed pattern to strip or replace an XML-like
closing tag that originated from agent output, use `[[:space:]]*/[[:space:]]*` not `/ *`.
