from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).parent.parent.parent.resolve()

DATA_RAW: Final[Path] = PROJECT_ROOT / "data" / "raw"
DATA_STAGED: Final[Path] = PROJECT_ROOT / "data" / "staged"
DATA_PROCESSED: Final[Path] = PROJECT_ROOT / "data" / "processed"
DATA_SAMPLE: Final[Path] = PROJECT_ROOT / "data" / "sample"
DB_DIR: Final[Path] = PROJECT_ROOT / "db"
REPORTS_DIR: Final[Path] = PROJECT_ROOT / "reports"
FIGURES_DIR: Final[Path] = REPORTS_DIR / "figures"
TABLES_DIR: Final[Path] = REPORTS_DIR / "tables"
SQL_DIR: Final[Path] = PROJECT_ROOT / "sql"

DB_PATH: Final[Path] = DB_DIR / "airbnb.duckdb"

# Column name constants - use these everywhere instead of string literals.
COL_LISTING_ID: Final[str] = "listing_id"
COL_HOST_ID: Final[str] = "host_id"
COL_PRICE: Final[str] = "price"
COL_PRICE_RAW: Final[str] = "price_raw"
COL_PRICE_LOG: Final[str] = "price_log"
COL_ROOM_TYPE: Final[str] = "room_type"
COL_NEIGHBOURHOOD: Final[str] = "neighbourhood_cleansed"
COL_AVAILABILITY_RATE: Final[str] = "availability_rate"
COL_OCCUPANCY_PROXY: Final[str] = "occupancy_proxy"
COL_REVENUE_PROXY: Final[str] = "revenue_proxy"
COL_REVIEW_FREQUENCY: Final[str] = "review_frequency"
COL_HOST_SEGMENT: Final[str] = "host_segment"
COL_SNAPSHOT_DATE: Final[str] = "snapshot_date"


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger. Root configuration is set in cli.py."""
    return logging.getLogger(name)


def city_raw_dir(city_key: str, snapshot_date: str) -> Path:
    return DATA_RAW / city_key / snapshot_date


def city_staged_dir(city_key: str, snapshot_date: str) -> Path:
    return DATA_STAGED / city_key / snapshot_date


def city_processed_dir(city_key: str) -> Path:
    return DATA_PROCESSED / city_key


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
