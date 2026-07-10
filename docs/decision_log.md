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
