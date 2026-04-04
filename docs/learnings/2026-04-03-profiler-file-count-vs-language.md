# Learning: Config and non-code files can skew language detection
**Date**: 2026-04-03
**Session**: 0011
**Type**: gotcha

## What Happened
In the Next.js integration test, `next.config.js`, `package.json`, and `package-lock.json` were all counted as JavaScript files, outnumbering the single `.tsx` file. This made the primary language "JavaScript" instead of "TypeScript" even though the project was clearly TypeScript-first.

## Lesson
When testing language detection, make the test data realistic -- a real Next.js project has many more `.tsx` files than config `.js` files. The test needed 3 TypeScript files to outweigh the 1 JavaScript config file. JSON files (`.json`) are not counted as any language, but `.js` config files are.

## How to Apply
When writing integration tests for the profiler, ensure the file distribution matches real-world projects. A single file of the "primary" language is not enough if config files in other languages are present.
