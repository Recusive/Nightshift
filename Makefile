.PHONY: test check dry-run lint typecheck validate clean

# Run the full test suite
test:
	python3 -m pytest tests/ -v

# Run the full CI check locally (lint + typecheck + test + integration + artifacts)
check:
	bash scripts/check.sh

# Preview the cycle prompt without spawning agents
dry-run:
	python3 -m nightshift run --dry-run --agent codex

# Run a quick validation shift (2 cycles, ~10 min)
quick-test:
	python3 -m nightshift test --agent claude --cycles 2 --cycle-minutes 5

# Syntax-check all shell scripts
validate-sh:
	bash -n scripts/run.sh && bash -n scripts/test.sh && bash -n scripts/install.sh

# Remove runtime artifacts
clean:
	rm -rf docs/Nightshift/worktree-*/ docs/Nightshift/*.runner.log docs/Nightshift/*.state.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
