.DEFAULT_GOAL := help

PYTHON := python
PYTEST  := pytest
RUFF    := ruff

.PHONY: help install lint format test clean run-download run-profile run-validate run-transform run-load run-analyse run-all

help:
	@echo "Available targets:"
	@echo "  install          Install the package and dev dependencies in editable mode"
	@echo "  lint             Run ruff linting checks"
	@echo "  format           Run ruff formatter"
	@echo "  test             Run the full test suite"
	@echo "  clean            Remove generated caches and build artifacts"
	@echo "  run-download     Download raw city data"
	@echo "  run-profile      Profile and validate staged data"
	@echo "  run-validate     Run domain validation rules"
	@echo "  run-transform    Clean and enrich listings"
	@echo "  run-load         Load processed data into DuckDB"
	@echo "  run-analyse      Run EDA, statistics, and ML"
	@echo "  run-all          Run the complete pipeline end to end"

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(RUFF) check src/ tests/

format:
	$(RUFF) format src/ tests/

test:
	$(PYTEST) tests/ -v --basetemp=.pytest_tmp

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name ".ruff_cache"  -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true

run-download:
	airbnb-pipeline download

run-profile:
	airbnb-pipeline profile

run-validate:
	airbnb-pipeline validate

run-transform:
	airbnb-pipeline transform

run-load:
	airbnb-pipeline load

run-analyse:
	airbnb-pipeline analyse

run-all:
	airbnb-pipeline run
