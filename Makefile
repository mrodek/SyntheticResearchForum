.PHONY: install install-dev test test-unit test-integration lint fmt check clean

PYTHON := py -3.11
PIP    := $(PYTHON) -m pip

# ── Setup ─────────────────────────────────────────────────────────────────────

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

# ── Tests ─────────────────────────────────────────────────────────────────────

test: test-unit

test-unit:
	$(PYTHON) -m pytest tests/unit -v --tb=short

test-integration:
	$(PYTHON) -m pytest tests/integration -v --tb=short --timeout=60

test-all:
	$(PYTHON) -m pytest tests/ -v --tb=short

# ── Linting / formatting ───────────────────────────────────────────────────────

lint:
	$(PYTHON) -m ruff check src/ tests/

fmt:
	$(PYTHON) -m ruff format src/ tests/

check: lint test-unit

# ── CI validation ─────────────────────────────────────────────────────────────

validate-prompts:
	$(PYTHON) scripts/validate_prompts.py

# ── Cleanup ────────────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
