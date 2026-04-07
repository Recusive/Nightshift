# Learning: extract_json raw_decode does not reliably find deeply nested JSON in arbitrary text
**Date**: 2026-04-03
**Session**: 0012
**Type**: gotcha

## What Happened
A test expected `extract_json` to find valid JSON embedded between arbitrary text like `"I've analyzed the repo. {...} That's my plan."`. The `raw_decode` approach failed because deeply nested JSON (with multiple levels of arrays and objects) inside arbitrary text confuses the decoder -- it either fails to find the right closing brace or matches a partial object.

## Lesson
`extract_json` reliably handles three cases: (1) pure JSON text, (2) markdown-fenced JSON, (3) JSON with leading text. It does NOT reliably handle JSON sandwiched between arbitrary text with trailing content. For agent output parsing, this is fine -- agents typically return JSON in fences or with a preamble before the JSON.

## How to Apply
When writing tests for JSON extraction, test the realistic cases (fenced, leading text, pure JSON). Do not test arbitrary embedding unless you fix raw_decode to track brace nesting depth.
