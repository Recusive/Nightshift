# Standalone validator before CI gate

## Context
Task `#0058` added `scripts/validate-tasks.sh` to make task-frontmatter drift
explicit. The first real repo run did not just find the known malformed files
`#0024`, `#0036`, and `#0045`; it also found seven live task files missing the
required `target` field.

## Lesson
When you add validation over long-lived repo metadata, ship the validator as a
standalone command first if historical data is already dirty. Wiring it into
`make check` immediately would turn known backlog debt into a merge blocker
before the repair tasks land.

## Action
Land the detector, create the repair/backfill tasks, and only then promote the
validator into CI once the live repo can pass it honestly.
