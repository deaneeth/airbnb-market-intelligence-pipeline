# Decision Log

This file records significant engineering and analytical decisions: the options considered,
the choice made, the rationale, and the trade-offs accepted.

---

## Format

```
### [YYYY-MM-DD] Decision title

- **Context**: what problem prompted this decision
- **Options considered**: numbered list of alternatives evaluated
- **Decision**: what was chosen
- **Rationale**: why this option was selected
- **Trade-offs accepted**: what was given up or deferred
```

---

## Entries

### [2026-07-11] DuckDB for analytical queries

- **Context**: The calendar file (~50M rows) and detailed reviews cannot be loaded into
  pandas on an 8 GB machine without hitting memory limits.
- **Options considered**:
  1. pandas with chunked processing
  2. DuckDB with SQL queries against Parquet files
  3. SQLite
- **Decision**: DuckDB for all aggregations on large files; pandas for row-level cleaning
  on the smaller listings and reviews summary files.
- **Rationale**: DuckDB can scan Parquet directly with a SQL interface, avoids loading full
  files into memory, and is a zero-dependency local binary. chunked pandas is verbose and
  harder to audit.
- **Trade-offs accepted**: Team members need to know basic SQL. DuckDB's API differs slightly
  from standard SQLite; this is documented in the skills guide.

### [2026-07-11] Parquet as the intermediate file format

- **Context**: Each pipeline step needs to hand off data to the next without holding it in
  memory across the session boundary.
- **Options considered**:
  1. CSV (simple, universal, slow and untyped)
  2. Parquet (columnar, typed, compressed)
  3. Feather / Arrow IPC (fast but less portable)
- **Decision**: Parquet with PyArrow as the serialisation backend.
- **Rationale**: Parquet preserves column types across reads, compresses well, and is natively
  readable by DuckDB without any conversion step. PyArrow is already a pandas dependency.
- **Trade-offs accepted**: Parquet files are not human-readable. The profiling report and
  manifest JSON provide the human-readable audit trail instead.

### [2026-07-11] pip plus venv for dependency management

- **Context**: The project needs a reproducible Python environment that reviewers can install
  on any machine.
- **Options considered**:
  1. pip + venv with pyproject.toml (PEP 517/518)
  2. uv (faster resolver, newer tool)
  3. conda
- **Decision**: pip + venv with `pyproject.toml` declaring all dependencies.
- **Rationale**: pip + venv is universally available without additional installation.
  pyproject.toml is the current packaging standard. uv is faster but adds a bootstrap step
  that not all reviewers will have installed.
- **Trade-offs accepted**: Dependency resolution is slower than uv. Exact versions are not
  locked; a `requirements.lock` can be generated with `pip freeze` if needed.

### [2026-07-11] No slowly-changing dimension for listings

- **Context**: The pipeline processes a single snapshot. Deciding whether to build SCD logic
  for multi-snapshot tracking was a design choice.
- **Options considered**:
  1. Build SCD Type 2 (track historical changes with valid_from / valid_to)
  2. Single-snapshot design with snapshot_date as a partitioning column
- **Decision**: Single-snapshot design. `snapshot_date` is a column on every fact table row.
  A second snapshot would add a new partition, not update existing rows.
- **Rationale**: A single snapshot is provided. Building SCD infrastructure for a hypothetical
  second snapshot adds complexity with no demonstrated current need.
- **Trade-offs accepted**: A second snapshot would require a migration to add SCD logic.
  This is documented in the architecture as a known production-scale consideration.

### [2026-07-11] Custom validation rules instead of Great Expectations

- **Context**: Domain validation rules are needed to check column types, ranges, and
  referential integrity between files.
- **Options considered**:
  1. Great Expectations (full framework, extensive output)
  2. Custom validation functions in validation.py
- **Decision**: Custom validation functions with a structured result dict per rule.
- **Rationale**: Great Expectations adds a significant dependency surface and requires a
  configuration layer that is heavier than what a single-snapshot academic pipeline needs.
  Custom functions are easier to test, read, and explain in an interview.
- **Trade-offs accepted**: Less automatic documentation than Great Expectations provides.
  Compensated by explicit rule IDs and the profiling report.

### [2026-07-11] Defer optional geospatial and dashboard dependencies

- **Context**: The current foundation requires core dependencies only. GeoPandas, Folium, and
  Streamlit are useful later, but that work has not started.
- **Options considered**:
  1. Keep optional dependency groups for future geospatial and dashboard work
  2. Remove them until the relevant implementation work starts
- **Decision**: Remove the optional dependency groups for now.
- **Rationale**: The current gate is easier to install and audit when it contains only packages
  required by the current foundation and dataset discovery work.
- **Trade-offs accepted**: Later geospatial or dashboard work must re-add the packages with
  their own validation and documentation.

### [2026-07-11] Versioned raw files for changed source bytes

- **Context**: The same city snapshot can be re-run, and a source file may change after a
  previous manifest was written. Overwriting the old raw file would destroy provenance.
- **Options considered**:
  1. Overwrite the raw file and keep only the latest checksum
  2. Keep the original raw file and write changed bytes to a checksum-suffixed filename
- **Decision**: Keep the original file and write changed bytes to a versioned raw filename.
- **Rationale**: The manifest can trace exactly which source bytes produced each staged file,
  and reruns remain auditable.
- **Trade-offs accepted**: A changed source can create multiple raw files for the same file key
  within one snapshot directory. The manifest identifies the active version.

### [2026-07-11] Incremental production refresh strategy

- **Context**: The local project stores full snapshot outputs, but a production system would
  need smaller refresh work when only some listings or listing-date records change.
- **Options considered**:
  1. Rebuild all downstream tables after every changed source file
  2. Upsert changed listing records and rebuild only affected listing-date partitions
- **Decision**: Keep full local snapshot storage now, and document the production strategy as
  listing-level upserts plus listing-date partition rebuilds keyed by `snapshot_date` and source
  checksum.
- **Rationale**: Full local snapshots are simpler and safer for this assessment-scale project.
  The production strategy shows how the design would scale without adding unnecessary code now.
- **Trade-offs accepted**: The current implementation does not include production upsert SQL or
  partition orchestration.

### [2026-07-11] Chunked profiling for staged CSV files

- **Context**: The calendar and detailed review files are large enough that loading every file
  fully into pandas for profiling would be wasteful on an 8 GB development machine.
- **Options considered**:
  1. Load each staged CSV fully into pandas
  2. Profile staged CSV files in chunks and aggregate deterministic summary statistics
- **Decision**: Profile CSV files in chunks, with redaction for sensitive categorical examples.
- **Rationale**: Chunking keeps memory bounded and still produces the required row counts,
  null rates, inferred types, distinct estimates, numeric summaries, and top categorical values.
- **Trade-offs accepted**: Distinct counts are approximate when a column has more than 100,000
  observed values in the profiler's bounded tracking set.

### [2026-07-11] Validation reports issues without deleting rows

- **Context**: Dataset quality checks must distinguish missing, invalid, duplicate, and unusual
  records without changing the source files.
- **Options considered**:
  1. Quarantine or edit records during validation
  2. Produce a structured issue table and leave row treatment to later cleaning decisions
- **Decision**: Validation writes structured reports and leaves every staged row untouched.
- **Rationale**: Validation is evidence collection. Row exclusion belongs in cleaning, where
  every exclusion can be recorded with a reason.
- **Trade-offs accepted**: Later cleaning code must explicitly consume or reinterpret these
  findings instead of assuming validation already removed bad rows.

### [2026-07-11] Deterministic listing cleaning outputs

- **Context**: Staged detailed listings need typed Parquet outputs while preserving raw values
  and making every excluded source row auditable.
- **Options considered**:
  1. Drop missing prices and keep only price-complete listings in the canonical table
  2. Preserve missing prices as null and quarantine only invalid source values
  3. Impute missing prices with a sentinel or neighbourhood median
- **Decision**: Preserve missing prices as null, quarantine invalid IDs, duplicate IDs,
  non-empty unparseable prices, non-positive prices, and invalid coordinates.
- **Rationale**: This keeps the canonical output useful for non-price analysis without hiding
  data quality issues or inventing prices.
- **Trade-offs accepted**: Price-complete analysis must filter `is_price_usable = true` rather
  than assuming every listing has a valid price.

### [2026-07-11] Calendar aggregation from available source columns only

- **Context**: Monthly calendar aggregation is useful for later joins, but the staged Amsterdam
  calendar file does not include price.
- **Options considered**:
  1. Aggregate only columns present in the calendar file
  2. Join listing-level price into the calendar aggregation
  3. Skip calendar aggregation until later analysis
- **Decision**: Aggregate listing-month availability, `occupancy_proxy`, and minimum/maximum
  nights from the calendar file only.
- **Rationale**: The output remains traceable to actual source columns and avoids creating a
  revenue estimate from mixed-grain inputs.
- **Trade-offs accepted**: Revenue proxy work is deferred until a documented method can combine
  price and availability without implying observed earnings.

### [2026-07-11] Haversine distance implementation without external geo library

- **Context**: Distance to city centre must be computed for each listing. Options include a pure
  Python formula, `geopy`, or `scipy.spatial`.
- **Options considered**:
  1. Pure Python Haversine using `math` (standard library only)
  2. `geopy.distance.geodesic` for higher accuracy
  3. `scipy.spatial.distance` (no native geodesic)
- **Decision**: Pure Python Haversine using the `math` standard library.
- **Rationale**: `geopy` is not a declared dependency. Adding it for one field is not justified
  when the Haversine formula delivers sufficient accuracy for neighbourhood-scale analysis on
  anonymized coordinates.
- **Trade-offs accepted**: Haversine ignores Earth's ellipsoidal shape; error is under 0.5% for
  the distances involved in Amsterdam. Acceptable given that coordinates are already approximate.

### [2026-07-11] Revenue proxy computed at enrichment step from listing price and calendar

- **Context**: The cleaned calendar file has no price column. Revenue proxy requires combining
  calendar availability with listing price.
- **Options considered**:
  1. Compute revenue proxy in cleaning by joining listing price into calendar before aggregation
  2. Compute revenue proxy in enrichment by joining calendar aggregates onto the master listing table
  3. Leave revenue proxy to the statistical analysis step
- **Decision**: Compute `revenue_proxy` at the enrichment step by joining the calendar aggregate
  onto the listing master and applying `price * occupancy_proxy * total_days_observed`.
- **Rationale**: Enrichment is the correct step for cross-file joins. The listing master already
  has the price field; computing the proxy here keeps the formula in one documented location
  and avoids pushing join logic into cleaning or analysis.
- **Trade-offs accepted**: Revenue proxy is only non-null for listings with both a valid calendar
  and a non-null listing price (6,377 of 10,369 listings). Null values are left as null, not zero.

### [2026-07-11] Star schema adapted to actual data rather than speculative design

- **Context**: The original `schema.sql` included fields (`bedrooms`, `bathrooms`, `accommodates`,
  `property_type`, `host_is_superhost`, `host_response_rate`, review sub-scores) that were designed
  before the cleaning step was implemented. After running cleaning, these fields were confirmed to
  be absent from `listings_master.parquet`.
- **Options considered**:
  1. Keep the original schema, add NULL placeholders for missing fields
  2. Re-run the cleaning step to bring in additional columns
  3. Rewrite the schema to match the actual available columns
- **Decision**: Rewrite the schema to match what exists.
- **Rationale**: NULL placeholders mislead consumers about column reliability. Re-running cleaning
  would invalidate the existing quarantine outputs and require re-validation. The analytical goals
  for this step are achievable with the fields that do exist.
- **Trade-offs accepted**: Q4 (superhost comparison) was replaced with host segment comparison.
  Q6 (weekday/weekend) was replaced with distance-to-centre price analysis.

### [2026-07-11] Drop-and-recreate idempotency for single-snapshot database; SCD deferred

- **Context**: The database serves a single snapshot. Idempotency must be guaranteed but history
  management is not required.
- **Options considered**:
  1. `CREATE OR REPLACE TABLE` (DuckDB syntax) — fails when foreign keys reference the table
  2. `DROP TABLE IF EXISTS ... CASCADE` in reverse dependency order, then `CREATE TABLE`
  3. `MERGE`/`UPSERT` with SCD Type 2 effective dates
- **Decision**: Explicit `DROP TABLE IF EXISTS` in reverse dependency order at the top of
  `schema.sql`, followed by `CREATE TABLE`.
- **Rationale**: `CREATE OR REPLACE` raises a `DependencyException` when tables have foreign key
  referents. Explicit ordered drops avoid the error without cascading drops, which would hide
  dependency bugs. SCD Type 2 adds significant complexity for a goal that currently needs only a
  single-snapshot database.
- **Trade-offs accepted**: Each load is a complete rebuild from Parquet. No history across
  snapshots. SCD is documented as a production enhancement to implement when multiple snapshots
  are available.

### [2026-07-11] Static EDA outputs from tested reporting functions

- **Context**: Exploratory analysis needs reproducible figures and summary tables that can be
  quoted in the report without duplicating logic in notebooks.
- **Options considered**:
  1. Put EDA code directly in notebooks
  2. Generate static figures and CSV tables from `reporting.py`
  3. Build an interactive dashboard
- **Decision**: Generate deterministic PNG figures, CSV summary tables, and a coverage note from
  tested functions in `reporting.py`.
- **Rationale**: Static artifacts are easy to review, version, and cite. They avoid notebook-only
  logic while staying within the local Python stack.
- **Trade-offs accepted**: The output is not interactive. Manual visual review is still required
  before final report writing.

### [2026-07-11] Supplemental EDA fields loaded from staged detailed listings

- **Context**: `listings_master.parquet` contains the canonical analytical fields but does not
  include property type, review score subdimensions, amenities, or superhost flags.
- **Options considered**:
  1. Re-run cleaning to add every EDA field to the canonical table
  2. Load selected supplemental columns from staged detailed listings during EDA
  3. Omit those analyses
- **Decision**: Load only the selected supplemental columns needed for EDA and join them by
  `listing_id`.
- **Rationale**: This keeps canonical cleaning stable and avoids broad schema churn while still
  using source-backed fields for figures and tables.
- **Trade-offs accepted**: These supplemental fields are available to EDA outputs but are not yet
  part of the canonical Parquet contract.

### [2026-07-11] Statistical outputs from source-backed fields only

- **Context**: Planned hypothesis tests require price, host, review, neighbourhood, availability,
  and calendar fields, but the current calendar output has no price column.
- **Options considered**:
  1. Run only the tests fully supported by the current processed tables
  2. Join listing quote price onto calendar rows to approximate weekday/weekend price
  3. Add placeholder columns for missing calendar price
- **Decision**: Run the supported tests, record the weekday/weekend calendar-price question as
  unavailable, and keep its limitation in the output table.
- **Rationale**: This preserves the analysis plan while avoiding a false listing-day price claim.
  The implemented results include p-value adjustment, effect sizes, confidence intervals, and
  plain-English interpretations for completed tests.
- **Trade-offs accepted**: One planned question remains unanswered until a source with day-level
  calendar prices is available.

### [2026-07-11] Transparent OLS model over automatic feature selection

- **Context**: The explanatory price model needs to be inspectable in a technical review and must
  avoid implying causal effects from a single observational snapshot.
- **Options considered**:
  1. A deliberately limited statsmodels OLS formula with grouped categorical variables
  2. Automatic feature selection across all available listing columns
  3. A predictive model optimised for accuracy
- **Decision**: Use one explicit OLS formula with HC3 robust standard errors, VIF diagnostics,
  residual diagnostics, and a limitations table.
- **Rationale**: The explicit formula is easier to explain and audit. Grouping sparse
  neighbourhood and property categories keeps coefficients more stable without hiding the
  complete-case row filter.
- **Trade-offs accepted**: The model is not optimised for prediction and may omit useful fields
  such as amenities or exact property size.

### [2026-07-11] Focused predictive benchmark instead of broad model search

- **Context**: The nightly-price prediction experiment needs to compare practical model families
  without turning the assignment into an open-ended modelling contest.
- **Options considered**:
  1. Compare one median baseline, one regularised linear model, one bagged tree model, and one
     gradient-boosting model with fixed modest settings
  2. Run a broad hyperparameter search over many algorithms
  3. Build a feature-heavy model from all available listing columns
- **Decision**: Use the four requested model families with a small leakage-reviewed feature set,
  training-fold cross-validation, final test metrics, error slices, and permutation importance.
- **Rationale**: This gives an honest benchmark against a simple baseline while keeping the code
  explainable and reproducible on the local machine.
- **Trade-offs accepted**: The experiment may not find the absolute best predictive model, and it
  is not evidence of production readiness.

### [2026-07-12] Strict exclusion of calendar-derived predictive features

- **Context**: `availability_rate` is useful analytically but is derived from the future calendar
  window relative to the listing snapshot.
- **Options considered**:
  1. Keep `availability_rate` as a feature with a caveat
  2. Remove it from predictive features and make the leakage check reject it
- **Decision**: Remove `availability_rate` from predictive features and add it to
  `FORBIDDEN_FEATURES`.
- **Rationale**: The stricter rule prevents future-calendar leakage and avoids relying on caveats
  for a feature that should not be available in the stated prediction task.
- **Trade-offs accepted**: Predictive performance is slightly lower, but the experiment is more
  defensible.

### [2026-07-12] Optional dashboard reads processed Parquet only

- **Context**: A lightweight interactive dashboard is useful for reviewing market summaries, but
  it should not alter the core pipeline or reach back into source files.
- **Options considered**:
  1. Build a Streamlit dashboard directly on processed Parquet outputs
  2. Read staged detailed listings to add property-type filtering
  3. Add a custom frontend or API server
- **Decision**: Build a small Streamlit dashboard that reads only `listings_master.parquet` and
  `calendar_agg.parquet`.
- **Rationale**: This keeps the add-on isolated, reproducible, and easy to remove if the reviewer
  wants only the batch pipeline.
- **Trade-offs accepted**: The property-type filter is unavailable until `property_type` becomes
  part of a generated processed output.
