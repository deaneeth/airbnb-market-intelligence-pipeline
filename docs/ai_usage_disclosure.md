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
- **Author direction and decisions**: decisions, scope limits, rejected suggestions, and manual
  acceptance made by the developer
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
  - Replaced ambiguous milestone wording with "pipeline step contract" in AGENTS.md
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
- **Author direction and decisions**: The developer required a clean `dev` workflow, detailed
  commit evidence, exact source verification, and no unverified production-readiness claims.
- **Validation**: `python -m ruff check src/ tests/ conftest.py` -> all checks passed;
  `python -m pytest tests/ -v --basetemp=.pytest_tmp` -> 21 passed; official Inside
  Airbnb data page parsed for the seven Amsterdam 2026-06-15 download URLs
- **Modifications**: Replaced arrows, em dashes, and dash glyphs in new docs
  with ASCII equivalents.
- **Rejected suggestions**: none in this session

### 2026-07-11 - Foundation verification and dataset discovery

- **Tool**: OpenAI Codex (GPT-5)
- **Assisted work**:
  - verified foundation gates against the current repository state
  - tightened configuration validation for duplicate YAML keys
  - removed optional dependencies that belong to later work
  - generated `docs/data_dictionary.md` from the live Amsterdam source files and official
    Inside Airbnb dictionary sheets
  - added dataset-discovery ambiguity assumptions for price currency, host response coverage, review
    score coverage, and anonymized coordinates
- **Nature**: reviewed, generated, validated, and refactored
- **Author direction and decisions**: The developer selected Amsterdam as the primary city,
  required source-backed facts, rejected broad optional work, and required neutral public wording
  in branch names, PR text, and repository documents.
- **Validation**: official Inside Airbnb download, assumptions, and data dictionary pages were
  consulted; live configured Amsterdam files were inspected without committing raw data;
  data dictionary coverage check confirmed all 127 configured source columns were documented;
  `python -m ruff check src/ tests/ conftest.py` -> all checks passed;
  `python -m pytest tests/ -v --basetemp=.pytest_tmp` -> 22 passed; clean temporary venv
  install with `pip install -e ".[dev]"` succeeded and its pytest run passed with 22 tests
- **Modifications**: Redacted free-text, name, URL, image, permit, and review-comment samples
  from the committed data dictionary.
- **Rejected suggestions**: no optional dashboard, geospatial package, ingestion command, or
  downstream transform code was added because those belong to later work.

### 2026-07-11 - Ingestion manifest implementation

- **Tool**: OpenAI Codex (GPT-5)
- **Assisted work**:
  - `src/airbnb_intelligence/ingestion.py`: download, extraction, manifest, retry, checksum,
    and run metadata implementation
  - `src/airbnb_intelligence/cli.py`: wired the `download` command to ingestion
  - `tests/test_ingestion.py`: fixture-based ingestion tests with no real network calls
  - `docs/decision_log.md` and `docs/lineage.md`: ingestion provenance documentation
- **Nature**: generated, reviewed, and refactored
- **Author direction and decisions**: The developer required a fresh branch from `dev`, no commit
  by the assistant, minimal readable code, no PR until manual review, and a strict scope limited
  to ingestion and manifest work. The developer also rejected unnecessary comments, over-broad
  helpers, and public wording that could make the repository look process-generated.
- **Validation**: focused ingestion tests and ruff were run during implementation; the real
  Amsterdam download command succeeded, a second run skipped all seven files, and the generated
  manifest recorded seven unique staged paths.
- **Modifications**: Kept implementation limited to ingestion and did not add orchestration,
  transformation, validation, or analysis code.
- **Rejected suggestions**: no shell download tools, framework orchestration, or full-file
  pandas reads for large source files were added.

### 2026-07-11 - Data quality profiling and validation

- **Tool**: OpenAI Codex (GPT-5)
- **Assisted work**:
  - `src/airbnb_intelligence/profiling.py`: chunked staged-file profiling and Markdown report output
  - `src/airbnb_intelligence/validation.py`: explicit domain rules, duplicate candidates,
    outlier reporting, coordinate standardisation helper, and validation outputs
  - `src/airbnb_intelligence/cli.py`: wired `profile` and `validate` commands
  - `tests/test_validation.py`: fixture-based rule tests
  - `docs/assumptions.md`, `docs/decision_log.md`, and `docs/lineage.md`: quality-method documentation
- **Nature**: generated, reviewed, and refactored
- **Author direction and decisions**: The developer required a fresh branch from `dev`, no commit
  by the assistant, simple reviewable code, no broad abstractions, no public process wording, and
  explicit credit for developer decisions and rejected over-broad suggestions.
- **Validation**: `python -m ruff check src/ tests/ conftest.py` passed twice;
  `python -m pytest tests/ -v --basetemp=.pytest_tmp` passed twice with 48 tests; real
  `profile` and `validate` commands generated the quality report, profile JSON, validation
  JSON, and issue table from the staged Amsterdam files.
- **Modifications**: Kept validation as report-only evidence collection; no staged source rows
  are edited, deleted, or quarantined here.
- **Rejected suggestions**: no all-pairs fuzzy matching, no framework profiler, no full-load
  large-file profiling path, and no cleaning transformations were added.

### 2026-07-11 - Cleaning and standardisation

- **Tool**: OpenAI Codex (GPT-5)
- **Assisted work**:
  - `src/airbnb_intelligence/cleaning.py`: deterministic price, date, category, coordinate,
    quarantine, listing output, analysis-view, and calendar aggregation functions
  - `src/airbnb_intelligence/cli.py`: wired `transform` to the implemented cleaning step
  - `tests/test_cleaning.py`: fixture-based tests for parsing, normalisation, missing values,
    invalid coordinates, and quarantine reasons
  - `docs/assumptions.md`, `docs/decision_log.md`, and `docs/lineage.md`: cleaning-method
    documentation and output lineage
- **Nature**: generated, reviewed, debugged, and validated
- **Author direction and decisions**: The developer required a new branch from `dev`, no commit
  by the assistant, minimal readable code, neutral public wording, actual-schema inspection before
  implementation, and repeated verification. The developer also directed that AI attribution stay
  balanced by recording manual scope control, rejected broad suggestions, and practical acceptance
  decisions instead of presenting the work as passively accepted AI output.
- **Validation**: focused cleaning tests passed; broad ruff and pytest checks passed before and
  after the real transform; `transform` generated typed Parquet outputs from the staged Amsterdam
  files; generated counts were inspected from Parquet.
- **Modifications**: Calendar aggregation was limited to source columns actually present in the
  staged calendar file; missing listing prices were preserved as nulls instead of being imputed
  or blanket-quarantined.
- **Rejected suggestions**: no invented calendar price or revenue fields, no winsorised canonical
  prices, no orchestration framework, no full calendar pandas load, and no broad enrichment logic
  were added.

### 2026-07-11 - DuckDB star schema and business queries

- **Tool**: Claude Sonnet 4.6 (Antigravity IDE)
- **Assisted work**:
  - `sql/schema.sql`: rewritten to match actual enriched master columns
  - `sql/business_queries.sql`: seven named business queries adapted to available data
  - `src/airbnb_intelligence/database.py`: full implementation including dimension and fact
    table loading, date spine generation, row count verification, query execution, CSV export
  - `src/airbnb_intelligence/cli.py`: wired the `load` subcommand
  - `tests/test_pipeline_smoke.py`: 16 smoke tests covering schema idempotency, fixture loads,
    no duplicate fact rows, verify_counts behaviour, query execution, date spine, and query parsing
  - `docs/assumptions.md`, `docs/decision_log.md`, `docs/lineage.md`: database documentation
- **Nature**: generated, reviewed, debugged, and verified on real data
- **Author direction and decisions**: The developer specified that the schema must match the actual
  enriched master rather than a speculative design. The developer caught that the original schema
  contained fields (`bedrooms`, `host_is_superhost`, review sub-scores) that do not exist in the
  cleaned master and instructed AI to rewrite rather than add NULL placeholders. The decision to
  replace the weekday/weekend query (Q6) with distance-to-centre analysis — because the calendar
  is month-grain, not day-grain — was the developer's judgment call. The developer also reviewed
  and confirmed the business query set before any data was exported.
- **Validation**: `ruff check` clean (twice). `pytest tests/` 87 tests passed (twice).
  Real `load` command run twice on Amsterdam: identical counts both runs (idempotency confirmed).
  All 7 business queries executed and exported to `reports/tables/`.
- **Modifications**: Fixed `CREATE OR REPLACE TABLE` DependencyException by adding explicit
  ordered `DROP TABLE IF EXISTS` in reverse dependency order. Fixed two smoke tests after the
  schema idempotency fix: idempotency test was reading schema at module load before the fix was
  applied; verify_counts test needed dim_listing populated before it could reach fact_listing_snapshot.
- **Rejected suggestions**: no NULL placeholder columns for missing data, no speculative fields
  added without a concrete source column, no pandas full-calendar load.


### 2026-07-11 - Listing enrichment and derived fields

- **Tool**: Claude Sonnet 4.6 (Antigravity IDE)
- **Assisted work**:
  - `src/airbnb_intelligence/enrichment.py`: host tenure, portfolio size, host segment, distance
    to city centre (Haversine), calendar left-join, availability_rate, occupancy_proxy, revenue_proxy,
    and neighbourhood aggregate columns
  - `src/airbnb_intelligence/cli.py`: wired the `enrich` subcommand
  - `tests/test_enrichment.py`: 16 fixture-based tests for all public functions
  - `docs/assumptions.md`, `docs/decision_log.md`, `docs/lineage.md`: enrichment documentation
- **Nature**: generated, reviewed, and debugged
- **Author direction and decisions**: The developer set the analytical scope for this step,
  required the enrichment to match the existing schema rather than inventing new columns,
  directed that `host_since` nulls be handled transparently rather than imputed, and required
  all proxy measures to carry exact caveat wording. The developer also caught that `bedrooms`
  was not in the cleaned master and decided to defer `price_per_bedroom` rather than re-run
  cleaning. The professional host threshold (2+ listings) and the minimum neighbourhood size
  (15 listings) were both validated and approved by the developer before implementation.
  Dam Square coordinates were confirmed as the appropriate city-centre reference.
- **Validation**: `python -m ruff check src/ tests/ conftest.py` passed (all checks); first
  full test run caught a Haversine bug (`asin(a)` instead of `asin(sqrt(a))`) which was
  fixed before accepting the code. Final run: 74 tests passed. Real `enrich` command ran on
  the Amsterdam dataset: 10,369 rows in, 10,369 rows out, 33 columns in enriched master.
- **Modifications**: Fixed the Haversine sqrt bug. Changed `pd.NA` to `float("nan")` for
  float64 Series initialization (Python 3.14 compatibility). Moved `Path` import to
  TYPE_CHECKING block after ruff TC003 error. Removed unused COL_HOST_SEGMENT import from tests.
- **Rejected suggestions**: no `geopy` dependency added, no bedrooms field added without schema
  change, no winsorisation of revenue proxy, no null-filling of host_tenure_years.

