.PHONY: setup hooks fmt check test test-all tasks calibrate smoke pilot report demo audit clean

UV ?= uv

setup:
	@command -v $(UV) >/dev/null 2>&1 || { echo "uv not found; see README"; exit 1; }
	$(UV) sync --extra dev
	@echo "setup complete. Activate with: source .venv/bin/activate"

hooks:
	@mkdir -p .git/hooks
	@printf '#!/bin/sh\npython scripts/check_no_secrets.py\n' > .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "pre-commit hook installed"

fmt:
	$(UV) run ruff format src tests scripts
	$(UV) run ruff check --fix src tests scripts

check:
	$(UV) run ruff format --check src tests scripts
	$(UV) run ruff check src tests scripts
	$(UV) run python scripts/check_no_secrets.py $(shell git ls-files '*.py' '*.toml' '*.yaml' '*.yml' '*.md' 2>/dev/null)
	$(UV) run pytest -q -m "not slow and not data and not live"

test:
	$(UV) run pytest -q -m "not slow and not data and not live"

test-all:
	$(UV) run pytest -q

tasks:
	$(UV) run gg tasks build

calibrate:
	$(UV) run gg calibrate

smoke:
	$(UV) run gg run configs/experiments/smoke.yaml

pilot:
	$(UV) run gg run configs/experiments/pilot.yaml

report:
	$(UV) run gg report --latest

demo:
	$(UV) run gg demo

audit:
	-$(UV) run pip-audit || true

clean:
	rm -rf .pytest_cache .ruff_cache **/__pycache__ data/built results/runs
