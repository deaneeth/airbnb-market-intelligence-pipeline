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
  - `id` renamed to `listing_id` and `host_id` typed as integer identifiers
  - Source `price` preserved as `price_raw` and parsed into numeric `price`
  - `price_log` and `is_price_usable` derived without imputing missing prices
  - `room_type` normalised while preserving `room_type_raw`
  - `neighbourhood_cleansed` and `city` stripped and Unicode-normalised while preserving raw fields
  - `host_since` and `last_review` parsed with explicit `%Y-%m-%d` format
  - Latitude and longitude rounded to 5 decimal places; originals kept as raw columns
  - `minimum_nights > 365` flagged as `is_long_stay`; rows retained
- **Filters and exclusions**: Rows with invalid or duplicate listing IDs, missing host IDs,
  non-empty unparseable prices, non-positive prices, missing coordinates, or out-of-range
  coordinates go to `listings_quarantine.parquet` with reason code. The Amsterdam run produced
  0 quarantined rows.
- **Output grain**: one row per valid listing in the snapshot
- **Primary key**: `listing_id`
- **Foreign keys**: `host_id` references the source host account identifier
- **Consumed by**: later database loading, analysis notebooks, figures, and models

### listings_quarantine.parquet

- **Source files**: `listings_detailed` (staged CSV)
- **Key transformations**: one quarantine row is written for each exclusion reason, carrying
  source file, source row index, listing identifier if available, reason code, raw failing value,
  and snapshot date
- **Filters and exclusions**: n/a (this IS the exclusion output)
- **Output grain**: one row per excluded source-row reason
- **Primary key**: (`source_row_index`, `reason`)
- **Foreign keys**: none
- **Consumed by**: data quality report, `docs/assumptions.md` quarantine count entry

### listings_analysis_view.parquet

- **Source files**: `listings_master.parquet`
- **Key transformations**:
  - Preserves every canonical listing row
  - Adds `is_price_outlier_iqr` using a 3 IQR rule on usable positive prices
  - Does not winsorise or overwrite canonical prices
- **Filters and exclusions**: none
- **Output grain**: one row per valid listing in the snapshot
- **Primary key**: `listing_id`
- **Foreign keys**: `listing_id` references `listings_master.parquet`
- **Consumed by**: later robust price analyses that need explicit outlier flags

### calendar_agg.parquet

- **Source files**: `calendar` (staged CSV, large file - processed via DuckDB scan)
- **Key transformations**:
  - Aggregated by `listing_id` and calendar month (`YYYY-MM`)
  - `availability_rate`: share of days marked available by the host
  - `occupancy_proxy`: 1 - availability_rate
  - Minimum and maximum nights summarised from source calendar rows
- **Filters and exclusions**: rows with null `listing_id` excluded by the DuckDB query
- **Output grain**: one row per (listing_id, calendar month)
- **Primary key**: (`listing_id`, `month`)
- **Foreign keys**: `listing_id` references `listings_master.parquet`
- **Consumed by**: enrichment step (join to listings_master), later database loading and availability analysis

### listings_master.parquet (enriched)

- **Source files**: `listings_master.parquet` (cleaned) + `calendar_agg.parquet`
- **Key transformations**:
  - `host_tenure_years`: Haversine of (snapshot_date - host_since) / 365.25; null when host_since is null
  - `portfolio_size`: count of listings per host_id in the snapshot
  - `host_segment`: "casual" (1 listing) or "professional" (2+ listings); see PROFESSIONAL_HOST_THRESHOLD
  - `distance_to_centre_km`: Haversine distance from Dam Square (52.37310, 4.89319); see docs/assumptions.md
  - `availability_rate`, `occupancy_proxy`: mean across all calendar months per listing (left join from calendar_agg)
  - `revenue_proxy`: listing_price * occupancy_proxy * total_calendar_days_observed; null when price or calendar is absent
  - `neighbourhood_listing_count`, `neighbourhood_median_price`: broadcast from neighbourhoods with >= 15 listings
- **Filters and exclusions**: no rows removed; listings without calendar data receive null availability/occupancy/revenue fields
- **Output grain**: one row per valid listing in the snapshot
- **Primary key**: `listing_id`
- **Foreign keys**: `host_id` (source host identifier), `neighbourhood_cleansed` (neighbourhood key)
- **Consumed by**: DuckDB star schema load, analysis notebooks, EDA figures, statistical tests, ML experiment


---

## DuckDB Tables

All DuckDB tables live in `db/airbnb.duckdb`. The load is fully idempotent (drop and recreate on
every run). Schema DDL is in `sql/schema.sql`. Business query SQL is in `sql/business_queries.sql`.

### dim_neighbourhood

- **Source**: `listings_master.parquet` (`neighbourhood_cleansed`, `neighbourhood_listing_count`,
  `neighbourhood_median_price`)
- **Key transformations**: deduplicate; assign surrogate `neighbourhood_id` via `ROW_NUMBER()`
- **Filters**: `neighbourhood_cleansed` must be non-null and not `'Unknown'`
- **Output grain**: one row per unique neighbourhood
- **Primary key**: `neighbourhood_id` (surrogate integer)
- **Consumed by**: `dim_listing` (FK), `fact_listing_snapshot` (FK), Q1, Q2, Q5 business queries

### dim_host

- **Source**: `listings_master.parquet` (`host_id`, `host_since`, `host_tenure_years`,
  `portfolio_size`, `host_segment`)
- **Key transformations**: `DISTINCT ON (host_id)` to deduplicate multi-listing hosts
- **Filters**: `host_id` must be non-null
- **Output grain**: one row per host
- **Primary key**: `host_id`
- **Consumed by**: `dim_listing` (FK), `fact_listing_snapshot` (FK), Q4 host segment query

### dim_listing

- **Source**: `listings_master.parquet` joined to `dim_neighbourhood` on `neighbourhood_cleansed`
- **Key transformations**: resolves `neighbourhood_id` surrogate key; casts `room_type` to VARCHAR
- **Filters**: `listing_id` must be non-null; listings without a matching neighbourhood are excluded
- **Output grain**: one row per listing
- **Primary key**: `listing_id`
- **Foreign keys**: `host_id` → `dim_host`, `neighbourhood_id` → `dim_neighbourhood`
- **Consumed by**: `fact_listing_snapshot` (FK), `fact_calendar` (FK), Q1, Q5, Q6, Q7 queries

### dim_date

- **Source**: date spine generated by `generate_date_spine()` from the min/max month in `calendar_agg.parquet`
- **Key transformations**: `pd.date_range` expanded to one row per day; `date_id` = YYYYMMDD integer
- **Output grain**: one row per calendar date covering the full calendar window (395 days)
- **Primary key**: `date_id` (YYYYMMDD integer)
- **Consumed by**: available for future day-level calendar queries; not yet joined by current business queries

### fact_listing_snapshot

- **Source**: `listings_master.parquet` joined to `dim_neighbourhood` on `neighbourhood_cleansed`
- **Key transformations**: resolves `neighbourhood_id` surrogate; casts `snapshot_date` to DATE
- **Filters**: `listing_id` must be non-null; listings without a matching neighbourhood are excluded
- **Output grain**: one row per listing in the snapshot (same grain as `listings_master.parquet`)
- **Primary key**: `listing_id`
- **Foreign keys**: `listing_id` → `dim_listing`, `host_id` → `dim_host`,
  `neighbourhood_id` → `dim_neighbourhood`
- **Key measures**: `price`, `availability_365`, `number_of_reviews`,
  `review_frequency` (demand proxy), `availability_rate`, `occupancy_proxy` (host-set availability
  proxy), `revenue_proxy` (not observed revenue)
- **Consumed by**: Q1 (price by neighbourhood), Q2 (supply concentration), Q4 (host segment),
  Q5 (top/bottom neighbourhoods), Q6 (distance vs price), Q7 (listing summary)

### fact_calendar

- **Source**: `calendar_agg.parquet` inner-joined to `dim_listing` on `listing_id`
- **Key transformations**: none; loaded as-is from the monthly aggregate Parquet
- **Filters**: listings not present in `dim_listing` are excluded (inner join); 1,572 calendar
  rows excluded from the 136,369 source rows due to listings that were excluded from `dim_listing`
  (no matching neighbourhood)
- **Output grain**: one row per (listing_id, calendar month)
- **Primary key**: (`listing_id`, `month`)
- **Foreign keys**: `listing_id` → `dim_listing`
- **Key measures**: `days_observed`, `days_available`, `availability_rate`, `occupancy_proxy`
- **Consumed by**: Q3 (monthly availability and occupancy proxy trend)

### Business Query Outputs (reports/tables/)

| File | Query | Rows | Description |
|---|---|---|---|
| `Q1_*.csv` | Q1 | 46 | Median price by neighbourhood and room type (≥10 listings) |
| `Q2_*.csv` | Q2 | 22 | Listing supply and host concentration per neighbourhood |
| `Q3_*.csv` | Q3 | 13 | Monthly availability rate and occupancy proxy |
| `Q4_*.csv` | Q4 | 2 | Casual vs professional host comparison |
| `Q5_*.csv` | Q5 | 20 | Top 10 and bottom 10 neighbourhoods by supply |
| `Q6_*.csv` | Q6 | 12 | Distance to city centre vs median price (km buckets) |
| `Q7_*.csv` | Q7 | 6,377 | Listing-level review and price summary |

### EDA Figure Outputs (reports/figures/eda_*.png)

- **Source files**: `listings_master.parquet`, `calendar_agg.parquet`,
  `listings_detailed.csv`, `reviews_summary.csv`, and `neighbourhoods_geojson.geojson`
- **Key transformations**:
  - Price, host segment, availability, geography, review-score, and review-frequency summaries
    generated by `reporting.py`
  - Review score, property type, amenities, response rate, and superhost fields joined from staged
    detailed listings by `listing_id`
  - Review volume trend aggregated by review month from `reviews_summary.csv`
- **Filters and exclusions**: price charts use rows with positive non-null `price`; neighbourhood
  comparisons require at least 15 price-usable listings; unavailable host-tenure and response-rate
  analyses are recorded in `reports/eda_coverage.md`
- **Output grain**: one static PNG per EDA business question
- **Primary key**: n/a
- **Foreign keys**: figure source rows reference `listing_id` where listing-level data is used
- **Consumed by**: final report exploratory analysis section

### EDA Table and Interpretation Outputs (reports/tables/eda_*.csv, reports/eda_coverage.md, reports/eda_interpretations.md)

- **Source files**: `listings_master.parquet`, `calendar_agg.parquet`,
  `listings_detailed.csv`, and `reviews_summary.csv`
- **Key transformations**:
  - Summary tables produced by `write_summary_tables`
  - Coverage table records completed and unavailable requested analyses with reasons
  - Amenities parsed from source list strings using Python literal parsing
  - Plain-English chart interpretations drafted from generated tables and figures
- **Filters and exclusions**: no source rows deleted; table-specific thresholds are documented in
  `docs/assumptions.md`
- **Output grain**: one summary row per analytical grouping, one coverage row per requested
  analysis, or one interpretation section per selected figure
- **Primary key**: varies by table; coverage table key is `analysis`
- **Foreign keys**: listing-level summaries reference `listing_id` in the source data
- **Consumed by**: final report captions, business interpretations, and limitations section
