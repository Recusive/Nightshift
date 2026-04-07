.PHONY: test check dry-run lint typecheck validate clean release daemon tasks

# Run the full test suite
test:
	python3 -m pytest nightshift/tests/ Recursive/tests/ -v

# Run the full CI check locally (lint + typecheck + test + integration + artifacts)
check:
	bash nightshift/scripts/check.sh

# Preview the cycle prompt without spawning agents
dry-run:
	python3 -m nightshift run --dry-run --agent codex

# Show the active task queue
tasks:
	bash Recursive/scripts/list-tasks.sh

# Run a quick validation shift (2 cycles, ~10 min)
quick-test:
	python3 -m nightshift test --agent claude --cycles 2 --cycle-minutes 5

# Syntax-check all shell scripts
validate-sh:
	bash -n nightshift/scripts/run.sh && bash -n nightshift/scripts/test.sh && bash -n nightshift/scripts/install.sh

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
	gh release create v$(VERSION) --title "v$(VERSION) -- $(CODENAME)" --notes-file .recursive/changelog/v$(VERSION).md
	@echo "Released v$(VERSION) -- $(CODENAME)"

# Run the Recursive daemon (auto-picks operator each cycle)
daemon:
	bash Recursive/engine/daemon.sh

# Remove runtime artifacts
clean:
	rm -rf Runtime/Nightshift/worktree-*/ Runtime/Nightshift/*.runner.log Runtime/Nightshift/*.state.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
