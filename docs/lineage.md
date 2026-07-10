# Data Lineage

One entry per Parquet output and per DuckDB table. Updated whenever a new output is created.

---

## Format

```
### <output_name>

- **Source files**: which staged or upstream files feed into this
- **Key transformations**: bullet list of each transformation step
- **Filters and exclusions**: rows excluded and where they go
- **Output grain**: one row per what?
- **Primary key**: column(s) that uniquely identify a row
- **Foreign keys**: references to other outputs
- **Consumed by**: SQL, notebooks, figures, or models that use this output
```

---

## Parquet Outputs

### pipeline_runs.parquet

- **Source files**: ingestion run metadata produced by `run_ingestion`
- **Key transformations**:
  - One metadata row appended per ingestion run
  - Row counts stored as a JSON object keyed by configured file key
  - Output paths stored as a JSON object so later steps can find the manifest
- **Filters and exclusions**: none
- **Output grain**: one row per ingestion run
- **Primary key**: `run_id`
- **Foreign keys**: none
- **Consumed by**: reproducibility checks, report provenance summary

### manifest.json

- **Source files**: configured Inside Airbnb URLs in `configs/cities.yml`
- **Key transformations**:
  - Raw source bytes downloaded to `data/raw/<city>/<snapshot>/`
  - Gzip files extracted to `data/staged/<city>/<snapshot>/`
  - SHA-256, byte size, row count, status, and source URL recorded per configured file
  - Changed raw files within a snapshot receive a checksum-suffixed filename
- **Filters and exclusions**: failed downloads are recorded with `status = "failed"` and stop the run
- **Output grain**: one file entry per configured source file
- **Primary key**: (`city_key`, `snapshot_date`, `file_key`)
- **Foreign keys**: none
- **Consumed by**: later profiling, validation, transformation, and report provenance summary

### profile.json

- **Source files**: staged files listed in `manifest.json`
- **Key transformations**:
  - CSV files profiled in chunks
  - GeoJSON feature properties converted to a tabular profile input
  - Sensitive categorical examples redacted from committed code paths
  - Row counts, column counts, null rates, distinct counts, numeric summaries, and top categories recorded
- **Filters and exclusions**: none
- **Output grain**: one profile section per staged source file
- **Primary key**: `file_key`
- **Foreign keys**: `file_key` references manifest entries
- **Consumed by**: `reports/data_quality_report.md`, report quality summary

### validation_report.json and data_quality_issues.csv

- **Source files**: staged listings, calendar, and review summary files listed in `manifest.json`
- **Key transformations**:
  - Domain rules classify findings as missing, invalid, duplicate, or unusual
  - Join coverage checks compare calendar and review summary `listing_id` values to detailed listings
  - Fuzzy duplicate candidates are blocked by host and rounded coordinates
  - Outliers are reported separately without deleting staged rows
- **Filters and exclusions**: none
- **Output grain**: one issue row per validation finding
- **Primary key**: no single source key; issue rows carry `rule_id`, `file_key`, `row_index`, and `source_id`
- **Foreign keys**: source identifiers reference staged source rows
- **Consumed by**: manual data quality review, later cleaning decisions, report quality summary

### listings_master.parquet

- **Source files**: `listings_detailed` (staged CSV)
- **Key transformations**:
  - Price string parsed to float; currency symbol and thousands separator stripped
  - Boolean flags (`host_is_superhost`, `host_identity_verified`) normalised from `t`/`f`
  - `host_since` and `last_review` parsed to date with explicit format string
  - Latitude and longitude rounded to 5 decimal places; originals kept as `_raw` columns
  - `minimum_nights > 365` flagged as `is_long_stay`; rows retained
  - Host tenure, portfolio size, host segment, review frequency, price per bedroom,
    and distance to city centre added as derived columns
  - Neighbourhood aggregates (listing count, median price) broadcast to each row
  - `availability_rate` and `occupancy_proxy` joined from `calendar_agg.parquet`
- **Filters and exclusions**: Rows with unparseable price or out-of-range coordinates
  go to `listings_quarantine.parquet` with reason code. No rows silently dropped.
- **Output grain**: one row per listing in the snapshot
- **Primary key**: `listing_id`
- **Foreign keys**: none (self-contained; host dimension derived in database.py)
- **Consumed by**: `database.py` (all dimension and fact tables), notebooks 02 and 03,
  EDA figures, OLS model, ML experiment

### listings_quarantine.parquet

- **Source files**: `listings_detailed` (staged CSV)
- **Key transformations**: none; preserves original field values alongside reason code
- **Filters and exclusions**: n/a (this IS the exclusion output)
- **Output grain**: one row per excluded source row
- **Primary key**: `source_row_index` (0-based position in the staged file)
- **Foreign keys**: none
- **Consumed by**: data quality report, `docs/assumptions.md` quarantine count entry

### calendar_agg.parquet

- **Source files**: `calendar` (staged CSV, large file - processed via DuckDB scan)
- **Key transformations**:
  - Aggregated by `listing_id` and calendar month (`YYYY-MM`)
  - `availability_rate`: share of days marked available by the host
  - `occupancy_proxy`: 1 - availability_rate
  - `median_calendar_price`: median nightly price from calendar rows
  - `revenue_proxy`: median_calendar_price * occupancy_proxy * days_observed
- **Filters and exclusions**: rows with null `listing_id` excluded; count logged
- **Output grain**: one row per (listing_id, calendar month)
- **Primary key**: (`listing_id`, `month`)
- **Foreign keys**: `listing_id` references `listings_master.parquet`
- **Consumed by**: `enrichment.py` (joined to listings_master), `database.py` (fact_calendar)

---

## DuckDB Tables

### dim_neighbourhood

- **Source**: `listings_master.parquet`
- **Output grain**: one row per unique `neighbourhood_cleansed` value
- **Primary key**: `neighbourhood_id` (surrogate, row number)
- **Consumed by**: `dim_listing`, `fact_listing_snapshot`

### dim_host

- **Source**: `listings_master.parquet`
- **Output grain**: one row per `host_id` (most recent record wins on duplicate host_id)
- **Primary key**: `host_id`
- **Consumed by**: `fact_listing_snapshot`

### dim_listing

- **Source**: `listings_master.parquet`
- **Output grain**: one row per `listing_id`
- **Primary key**: `listing_id`
- **Foreign keys**: `neighbourhood_id` -> `dim_neighbourhood`, `host_id` -> `dim_host`
- **Consumed by**: `fact_listing_snapshot`, `fact_calendar`

### dim_date

- **Source**: date spine generated from `calendar_agg.parquet` date range
- **Output grain**: one row per calendar date
- **Primary key**: `date_id` (integer YYYYMMDD)
- **Consumed by**: `fact_calendar`

### fact_listing_snapshot

- **Source**: `listings_master.parquet`
- **Output grain**: one row per listing in the snapshot
- **Primary key**: `listing_id`
- **Foreign keys**: `listing_id` -> `dim_listing`, `host_id` -> `dim_host`,
  `neighbourhood_id` -> `dim_neighbourhood`
- **Consumed by**: business SQL queries, notebooks

### fact_calendar

- **Source**: `calendar_agg.parquet`
- **Output grain**: one row per (listing_id, calendar month)
- **Primary key**: (`listing_id`, `month`)
- **Foreign keys**: `listing_id` -> `dim_listing`
- **Consumed by**: monthly trend queries, revenue proxy analysis
