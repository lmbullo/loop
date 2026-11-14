PYTHON ?= python3
UNIT := $(PYTHON) -m unittest discover -s tests -t . -v

.PHONY: help check test lint verify sim clean

help:
	@echo "check   compile + 200-line + tui layout audits"
	@echo "test    stdlib unittest suite"
	@echo "lint    ruff E4/E9/F when installed"
	@echo "verify  manifest-driven offline checks"
	@echo "sim     run both offline sims"
	@echo "clean   remove bytecode and test caches (never .logs)"

check:
	$(PYTHON) -m compileall -q harness tui run.py
	$(PYTHON) run.py check lines
	$(PYTHON) run.py check tui

test:
	$(UNIT)

lint:
	@command -v ruff >/dev/null 2>&1 && ruff check . || echo "ruff not installed; skipped"

verify:
	$(PYTHON) scripts/verify.py --skip-server

sim:
	$(PYTHON) run.py sim1 task
	$(PYTHON) run.py sim2 task2

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache
