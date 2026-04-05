.PHONY: test check dry-run lint typecheck validate clean release daemon tasks

# Run the full test suite
test:
	python3 -m pytest tests/ -v

# Run the full CI check locally (lint + typecheck + test + integration + artifacts)
check:
	bash scripts/check.sh

# Preview the cycle prompt without spawning agents
dry-run:
	python3 -m nightshift run --dry-run --agent codex

# Show the active task queue
tasks:
	bash scripts/list-tasks.sh

# Run a quick validation shift (2 cycles, ~10 min)
quick-test:
	python3 -m nightshift test --agent claude --cycles 2 --cycle-minutes 5

# Syntax-check all shell scripts
validate-sh:
	bash -n scripts/run.sh && bash -n scripts/test.sh && bash -n scripts/install.sh

# Cut a release: make release VERSION=0.0.3 CODENAME="Intelligence"
release:
ifndef VERSION
	$(error VERSION is required. Usage: make release VERSION=0.0.3 CODENAME="Intelligence")
endif
ifndef CODENAME
	$(error CODENAME is required. Usage: make release VERSION=0.0.3 CODENAME="Intelligence")
endif
	@echo "Verifying before release..."
	$(MAKE) check
	@echo "Tagging v$(VERSION)..."
	git tag v$(VERSION)
	git push origin main && git push origin v$(VERSION)
	gh release create v$(VERSION) --title "v$(VERSION) -- $(CODENAME)" --notes-file docs/changelog/v$(VERSION).md
	@echo "Released v$(VERSION) -- $(CODENAME)"

# Run the feature-building daemon (loops forever, Ctrl+C to stop)
daemon:
	bash scripts/daemon.sh

# Run the code quality review daemon (loops forever, Ctrl+C to stop)
review:
	bash scripts/daemon-review.sh

# Run the strategist (single run -- reviews the system, produces a report)
strategist:
	bash scripts/daemon-strategist.sh

# Run the overseer (loops -- audits task queue, fixes priorities, cleans duplicates)
overseer:
	bash scripts/daemon-overseer.sh

# Remove runtime artifacts
clean:
	rm -rf docs/Nightshift/worktree-*/ docs/Nightshift/*.runner.log docs/Nightshift/*.state.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
