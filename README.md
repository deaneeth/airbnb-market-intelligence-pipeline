# Airbnb Market Intelligence Pipeline

A reproducible, configuration-driven data engineering and analytics pipeline built on
publicly available Inside Airbnb snapshot data. The primary analytical case is Amsterdam.

---

## Project Status

> **Work in progress.** See `docs/` for current assumptions, decision log, and lineage.

---

## Prerequisites

| Tool | Minimum Version |
|---|---|
| Python | 3.11 |
| Git | any recent |
| (Optional) Docker Desktop | any recent |

No cloud account, no paid API key, and no distributed system is required.

---

## Setup

```bash
# Clone the repository
git clone https://github.com/<your-handle>/airbnb-market-intelligence-pipeline.git
cd airbnb-market-intelligence-pipeline

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows PowerShell

# Install the package and development tools
pip install -e ".[dev]"

# Confirm the CLI is available
airbnb-pipeline --help
```

---

## Data Download

Raw data is **not** committed to this repository. Download it yourself with:

```bash
airbnb-pipeline download
```

This reads `configs/cities.yml`, downloads the configured snapshot files to `data/raw/`,
and writes a manifest to `data/staged/` with SHA-256 checksums and provenance metadata.
Re-running the command is safe: existing files whose checksums match the manifest are skipped.

---

## Execution Order

Run each step in order. Do not skip ahead.

```bash
airbnb-pipeline download    # fetch raw files, write manifest
airbnb-pipeline profile     # profiling and data-quality report
airbnb-pipeline validate    # domain validation rules
airbnb-pipeline transform   # clean, standardise, enrich, write Parquet
airbnb-pipeline load        # build DuckDB star schema from Parquet
airbnb-pipeline analyse     # EDA figures, statistics, and ML experiment
```

Or run the complete pipeline in one command:

```bash
airbnb-pipeline run
```

---

## Key Outputs

| Path | Description |
|---|---|
| `data/staged/<city>/<snapshot>/manifest.json` | Ingestion manifest with SHA-256 and provenance |
| `data/processed/<city>/listings_master.parquet` | Enriched listing master table |
| `db/airbnb.duckdb` | Analytical DuckDB database with star schema |
| `reports/data_quality_report.html` | Profiling and validation summary |
| `reports/figures/` | Publication-quality EDA figures |
| `reports/tables/` | Summary statistics and hypothesis results |
| `reports/Airbnb_Market_Intelligence_Report.pdf` | Final professional report |

---

## Running Tests

```bash
make test
```

All tests use small local fixtures and do not require a network connection or downloaded data.

---

## Linting and Formatting

```bash
make lint     # ruff check
make format   # ruff format
```

---

## Configuration

City configuration lives in `configs/cities.yml`. To add a second city, add a new entry to
that file. No Python code changes are required.

---

## Documentation

| File | Contents |
|---|---|
| `docs/architecture.md` | End-to-end pipeline architecture and layer diagram |
| `docs/data_dictionary.md` | Schema documentation for every source file |
| `docs/assumptions.md` | All assumptions about ambiguous fields and data quality |
| `docs/decision_log.md` | Engineering and analytical decisions with rationale |
| `docs/lineage.md` | Data lineage from source file to report |
| `docs/ai_usage_disclosure.md` | Complete disclosure of AI tool use |

---

## Limitations

- Analysis is based on a single Inside Airbnb snapshot. Results represent conditions at the
  snapshot date, not current market conditions.
- Availability rate from the calendar file is an observational proxy and is not equivalent to
  booked occupancy.
- Revenue estimates derived from calendar availability are proxies with documented limitations.
- The dataset reflects scraping artefacts and does not represent verified booking or revenue data.

---

## Reviewer Quick Start

1. Read `docs/architecture.md` for the system overview.
2. Open `reports/Airbnb_Market_Intelligence_Report.pdf` for the full analysis.
3. Run `make test` to verify the pipeline functions on your machine.
4. Run `airbnb-pipeline download` followed by `airbnb-pipeline run` to reproduce all outputs.
