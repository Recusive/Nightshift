# Sub-Agent Review Tiers

Determine review depth from `gh pr diff --stat`:

## DOCS-ONLY (.md only, no .py/.sh/.json/.toml)
1 agent: code-reviewer (fast path — reports PASS immediately)

## SMALL (<100 lines changed, <3 files)
1 agent: code-reviewer

## MEDIUM (100-300 lines, OR new module, OR new dependency)
3 agents in parallel: code-reviewer + safety-reviewer + docs-reviewer

## COMPLEX (>300 lines, OR 5+ files, OR touches scripts/ or prompts/)
4-5 agents in parallel: code-reviewer + safety-reviewer + docs-reviewer + architecture-reviewer + meta-reviewer (only if PR touches engine scripts or prompt files)

Each agent reads its definition from the agents/ directory, then reads the diff with `gh pr diff <number>`. Reports PASS or FAIL with specific file:line references. Spawn all agents in parallel. ALL must PASS to merge.
