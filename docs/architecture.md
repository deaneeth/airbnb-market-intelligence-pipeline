# Architecture

## Overview

This pipeline processes publicly available Inside Airbnb snapshot data into a layered
analytical output: profiled and validated Parquet files, a DuckDB star schema, statistical
results, a price prediction experiment, and a final report.

The primary case study is Amsterdam (snapshot 2026-06-15). A second city can be added
by adding one entry to `configs/cities.yml` with no Python code changes required.

---

## Stack

| Layer | Tool | Rationale |
|---|---|---|
| Language | Python 3.11+ | Wide ecosystem, strong typing support |
| Data format | Parquet (via PyArrow) | Columnar, compressed, fast scan |
| Analytics database | DuckDB | Zero-dependency, SQL-native Parquet scans |
| Statistics | SciPy, statsmodels | Established, peer-reviewed implementations |
| ML | scikit-learn | Standard cross-validated experiment framework |
| Visualisation | Matplotlib | Deterministic, no display dependency |
| Config | YAML | Human-readable, version-controlled |
| Packaging | pip + venv | Minimal, reproducible, no build system overhead |

---

## Pipeline Layers

```
configs/cities.yml
        │
        ▼
[1] ingestion.py      -> data/raw/<city>/<date>/<file>
                         data/staged/<city>/<date>/<file>
                         data/staged/<city>/<date>/manifest.json
        │
        ▼
[2] profiling.py      -> reports/data_quality_report.html
[3] validation.py     -> validation findings (in-memory, passed to enrichment)
        │
        ▼
[4] cleaning.py       -> data/processed/<city>/listings_master.parquet
                         data/processed/<city>/listings_quarantine.parquet
                         data/processed/<city>/calendar_agg.parquet
        │
        ▼
[5] enrichment.py     -> data/processed/<city>/listings_master.parquet (enriched in place)
        │
        ▼
[6] database.py       -> db/airbnb.duckdb
        │
        ▼
[7] statistics.py     -> reports/tables/hypothesis_tests.csv
    reporting.py         reports/tables/ols_price_model.csv
                         reports/figures/*.png
        │
        ▼
[8] ml.py             -> reports/tables/ml_experiment_results.csv
                         reports/tables/ml_feature_importance.csv
        │
        ▼
[9] Notebooks         -> narrative view, calls src/ functions, read-only DB access
[10] Report           -> reports/Airbnb_Market_Intelligence_Report.pdf
```

---

## Key Design Decisions

- **No cloud infrastructure.** All processing runs locally on a single machine with 8 GB RAM.
- **Parquet as the intermediate format.** Each pipeline step reads from and writes to Parquet,
  making every step independently restartable.
- **DuckDB for analytics.** SQL queries run directly against Parquet files without loading them
  into pandas, avoiding out-of-memory errors on the calendar file.
- **Configuration-driven city support.** Adding a city requires only a `configs/cities.yml`
  entry. No Python code changes are needed for the download or schema layers.
- **Quarantine instead of drop.** Rows excluded during cleaning are preserved in a quarantine
  table with the source row index and a machine-readable reason string.

See `docs/decision_log.md` for the full rationale behind each choice.
