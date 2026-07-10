# AI Usage Disclosure

This file records all AI tool assistance used in this project. It is updated continuously
as work progresses.

Reviewers should treat any AI-assisted output as having been validated before acceptance.
Sections marked "validated" below were run, tested, and reviewed by the author before commit.

---

## Disclosure Format

Each session entry includes:

- **Date**: date of the session
- **Tool**: AI tool and model version
- **Assisted work**: which file, function, or analysis section
- **Nature**: generated / reviewed / debugged / refactored
- **Validation**: how the output was checked
- **Modifications**: what was changed from the AI output
- **Rejected suggestions**: any AI suggestion not used, with reason

---

## Session Log

### 2026-07-10 - Project infrastructure

- **Tool**: Gemini 2.5 Pro (Antigravity IDE)
- **Assisted work**:
  - `pyproject.toml`: dependency list, ruff configuration, pytest settings
  - `AGENTS.md`: coding contract, scope discipline, analytics rules
  - `.agents/` skills directory: 9 skill files with per-module contracts
  - `src/airbnb_intelligence/config.py`: full implementation
  - `src/airbnb_intelligence/utils.py`: path constants and column name constants
  - `src/airbnb_intelligence/cli.py`: argument parser and subcommand declarations
  - `tests/test_config.py`: 21 parametrised test cases
  - `docs/`: architecture, assumptions, decision log, lineage, data dictionary
  - `sql/schema.sql`: star schema DDL
  - `sql/business_queries.sql`: 7 business queries
  - `.gitignore`, `Makefile`, `conftest.py`, `.gitattributes`
- **Nature**: generated with specific prompts; reviewed line-by-line
- **Validation**: `pytest tests/ -q` -> 21 passed; `ruff check src/ tests/` -> all checks passed
- **Modifications**:
  - Removed verbose module-level docstrings from all stub modules
  - Replaced "phase contract" with "pipeline step contract" in AGENTS.md
  - Moved column name constants from AGENTS.md into `utils.py` where they are actually used
  - Removed `tmp_path_factory` fixture override from conftest.py (redundant)
  - Simplified `_write_city_yaml` in test_config.py to remove unused parameter docstring
- **Rejected suggestions**:
  - AI proposed adding a `BaseValidator` abstract class: rejected (no concrete second validator exists)
  - AI proposed a `retry` decorator utility: rejected (no network calls yet, adds speculative complexity)

### 2026-07-11 - Amsterdam URL configuration and docs population

- **Tool**: Gemini 2.5 Pro (Antigravity IDE)
- **Assisted work**:
  - `configs/cities.yml`: populated with Amsterdam snapshot URLs from screenshot
  - `docs/assumptions.md`, `docs/decision_log.md`, `docs/lineage.md`,
    `docs/data_dictionary.md`, `docs/architecture.md`: full content
- **Nature**: generated based on project-specific context
- **Validation**: URLs match the file names visible in the Inside Airbnb screenshot;
  snapshot date 2026-06-15 confirmed from screenshot header
- **Modifications**: None beyond formatting alignment
- **Rejected suggestions**: none in this session

### 2026-07-11 - Commit readiness verification

- **Tool**: OpenAI Codex (GPT-5)
- **Assisted work**:
  - verified `dev` branch alignment with `main`
  - inspected staged Amsterdam configuration and documentation changes
  - cleaned non-ASCII punctuation in new documentation files before commit
  - ran required pre-commit lint and test commands
- **Nature**: reviewed, validated, and prepared for git commit
- **Validation**: `python -m ruff check src/ tests/ conftest.py` -> all checks passed;
  `python -m pytest tests/ -v --basetemp=.pytest_tmp` -> 21 passed; official Inside
  Airbnb data page parsed for the seven Amsterdam 2026-06-15 download URLs
- **Modifications**: Replaced arrows, em dashes, and dash glyphs in new docs
  with ASCII equivalents.
- **Rejected suggestions**: none in this session

### 2026-07-11 - Phase 0 verification and Phase 1 discovery

- **Tool**: OpenAI Codex (GPT-5)
- **Assisted work**:
  - verified Phase 0 gates against the current repository state
  - tightened configuration validation for duplicate YAML keys
  - removed optional dependencies that belong to later roadmap phases
  - generated `docs/data_dictionary.md` from the live Amsterdam source files and official
    Inside Airbnb dictionary sheets
  - added Phase 1 ambiguity assumptions for price currency, host response coverage, review
    score coverage, and anonymized coordinates
- **Nature**: reviewed, generated, validated, and refactored
- **Validation**: official Inside Airbnb download, assumptions, and data dictionary pages were
  consulted; live configured Amsterdam files were inspected without committing raw data;
  data dictionary coverage check confirmed all 127 configured source columns were documented;
  `python -m ruff check src/ tests/ conftest.py` -> all checks passed;
  `python -m pytest tests/ -v --basetemp=.pytest_tmp` -> 22 passed; clean temporary venv
  install with `pip install -e ".[dev]"` succeeded and its pytest run passed with 22 tests
- **Modifications**: Redacted free-text, name, URL, image, permit, and review-comment samples
  from the committed data dictionary.
- **Rejected suggestions**: no optional dashboard, geospatial package, ingestion command, or
  downstream transform code was added because those belong to later phases.
