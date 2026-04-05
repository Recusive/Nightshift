# Learning: Per-file cap fires before total cap in cascaded truncation

**Date**: 2026-04-04
**Session**: 0024
**Type**: gotcha

## What happened
Tests for total-cap truncation failed because the test created files larger than the per-file limit (10 KB), expecting them to consume the total budget (30 KB). But per-file truncation runs first, capping each file at 10 KB. So 3 files at 30 KB each all got cut to 10 KB, totaling exactly 30 KB -- the total cap was never hit.

## The lesson
When testing cascaded size limits (per-file then total), use file sizes that are under the per-file cap but together exceed the total cap. The per-file limit always fires first, so any file larger than `MAX_INSTRUCTION_FILE_BYTES` is already reduced before the total budget is checked.

To trigger total-cap truncation: write 3 files at `MAX_INSTRUCTION_FILE_BYTES - 40` bytes each (under per-file, but 3x nearly fills the 30 KB total), then a 4th file that exceeds the remaining ~120 bytes.
