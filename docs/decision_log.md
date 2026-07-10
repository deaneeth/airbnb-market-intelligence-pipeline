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
