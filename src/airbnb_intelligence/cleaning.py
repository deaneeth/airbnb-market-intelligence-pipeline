from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Final

import duckdb
import pandas as pd

from airbnb_intelligence.config import load_config
from airbnb_intelligence.utils import (
    COL_HOST_ID,
    COL_LISTING_ID,
    COL_NEIGHBOURHOOD,
    COL_PRICE,
    COL_PRICE_LOG,
    COL_PRICE_RAW,
    COL_REVIEW_FREQUENCY,
    COL_ROOM_TYPE,
    COL_SNAPSHOT_DATE,
    city_processed_dir,
    city_staged_dir,
    ensure_dirs,
)

if TYPE_CHECKING:
    from pathlib import Path

DATE_FORMAT: Final[str] = "%Y-%m-%d"
COORDINATE_PRECISION: Final[int] = 5
LONG_STAY_MINIMUM_NIGHTS: Final[int] = 365
PRICE_OUTLIER_IQR_MULTIPLIER: Final[float] = 3.0

LISTING_COLUMNS: Final[list[str]] = [
    "id",
    "host_id",
    "price",
    "room_type",
    "neighbourhood_cleansed",
    "latitude",
    "longitude",
    "minimum_nights",
    "availability_365",
    "number_of_reviews",
    "reviews_per_month",
    "host_since",
    "last_review",
]

QUARANTINE_COLUMNS: Final[list[str]] = [
    "source_file",
    "source_row_index",
    COL_LISTING_ID,
    "reason",
    "raw_value",
    COL_SNAPSHOT_DATE,
]


@dataclass(frozen=True)
class CleaningResult:
    city_key: str
    snapshot_date: str
    listings_master_path: Path
    listings_quarantine_path: Path
    listings_analysis_view_path: Path
    calendar_agg_path: Path
    listings_rows: int
    quarantine_rows: int
    calendar_agg_rows: int


def parse_price(raw: object) -> float | None:
    if raw is None or pd.isna(raw):
        return None

    value = str(raw).strip()
    if not value:
        return None

    cleaned = (
        value.replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace("¥", "")
        .replace(",", "")
        .strip()
    )
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_date(raw: object, fmt: str = DATE_FORMAT) -> date | None:
    if raw is None or pd.isna(raw):
        return None

    value = str(raw).strip()
    if not value:
        return None

    try:
        return datetime.strptime(value, fmt).date()
    except ValueError:
        return None


def normalise_boolean(raw: object) -> bool | None:
    if raw is None or pd.isna(raw):
        return None

    value = str(raw).strip().lower()
    if value == "t":
        return True
    if value == "f":
        return False
    return None


def normalise_category(raw: object) -> str | None:
    if raw is None or pd.isna(raw):
        return None

    value = " ".join(str(raw).strip().split())
    if not value:
        return None
    return unicodedata.normalize("NFC", value).lower()


def normalise_place_text(raw: object) -> str:
    if raw is None or pd.isna(raw):
        return "Unknown"

    value = " ".join(str(raw).strip().split())
    if not value:
        return "Unknown"
    return unicodedata.normalize("NFC", value)


def clean_listings_frame(
    listings: pd.DataFrame,
    *,
    city_name: str,
    snapshot_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = listings.copy()
    frame["source_row_index"] = frame.index.astype("int64")
    frame[COL_LISTING_ID] = pd.to_numeric(frame["id"], errors="coerce").astype("Int64")
    frame[COL_HOST_ID] = pd.to_numeric(frame["host_id"], errors="coerce").astype("Int64")
    frame[COL_PRICE_RAW] = frame["price"].astype("string")
    frame[COL_PRICE] = frame["price"].map(parse_price)
    frame["room_type_raw"] = frame["room_type"].astype("string")
    frame[COL_ROOM_TYPE] = frame["room_type"].map(normalise_category).astype("category")
    frame["neighbourhood_raw"] = frame["neighbourhood_cleansed"].astype("string")
    frame[COL_NEIGHBOURHOOD] = frame["neighbourhood_cleansed"].map(normalise_place_text)
    frame["city_raw"] = city_name
    frame["city"] = normalise_place_text(city_name)
    frame["latitude_raw"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude_raw"] = pd.to_numeric(frame["longitude"], errors="coerce")
    frame["latitude"] = frame["latitude_raw"].round(COORDINATE_PRECISION)
    frame["longitude"] = frame["longitude_raw"].round(COORDINATE_PRECISION)
    frame["minimum_nights"] = pd.to_numeric(frame["minimum_nights"], errors="coerce").astype(
        "Int64"
    )
    frame["is_long_stay"] = frame["minimum_nights"] > LONG_STAY_MINIMUM_NIGHTS
    frame["availability_365"] = pd.to_numeric(frame["availability_365"], errors="coerce").astype(
        "Int64"
    )
    frame["number_of_reviews"] = pd.to_numeric(frame["number_of_reviews"], errors="coerce").astype(
        "Int64"
    )
    frame[COL_REVIEW_FREQUENCY] = pd.to_numeric(frame["reviews_per_month"], errors="coerce")
    frame["host_since"] = frame["host_since"].map(parse_date)
    frame["last_review"] = frame["last_review"].map(parse_date)
    frame[COL_SNAPSHOT_DATE] = parse_date(snapshot_date)
    frame[COL_PRICE_LOG] = frame[COL_PRICE].map(_log_price)
    frame["is_price_usable"] = frame[COL_PRICE].map(lambda value: value is not None and value > 0)

    quarantine = _build_quarantine(frame, snapshot_date)
    bad_rows = set(quarantine["source_row_index"].tolist()) if not quarantine.empty else set()
    master = frame.loc[~frame["source_row_index"].isin(bad_rows), _master_columns()].copy()
    master = _apply_master_dtypes(master)
    return master.reset_index(drop=True), quarantine.reset_index(drop=True)


def write_listing_analysis_view(master: pd.DataFrame, path: Path) -> int:
    analysis = master.copy()
    usable = analysis[analysis["is_price_usable"]][COL_PRICE]
    lower, upper = _iqr_bounds(usable)
    analysis["is_price_outlier_iqr"] = analysis[COL_PRICE].map(
        lambda value: bool(
            value is not None and not pd.isna(value) and (value < lower or value > upper)
        )
    )
    analysis.to_parquet(path, index=False)
    return len(analysis)


def aggregate_calendar(staged_dir: Path, processed_dir: Path, snapshot_date: str) -> int:
    calendar_path = staged_dir / "calendar.csv"
    output_path = processed_dir / "calendar_agg.parquet"
    calendar_sql = f"""
    -- PROXY NOTE: occupancy_proxy is derived from host-set availability;
    -- it is not equivalent to confirmed booked nights.
    COPY (
        SELECT
            CAST(listing_id AS BIGINT) AS listing_id,
            strftime(CAST(date AS DATE), '%Y-%m') AS month,
            COUNT(*) AS days_observed,
            SUM(CASE WHEN available = 't' THEN 1 ELSE 0 END) AS days_available,
            ROUND(
                SUM(CASE WHEN available = 't' THEN 1 ELSE 0 END)::DOUBLE / COUNT(*),
                4
            ) AS availability_rate,
            ROUND(
                1 - SUM(CASE WHEN available = 't' THEN 1 ELSE 0 END)::DOUBLE / COUNT(*),
                4
            ) AS occupancy_proxy,
            MIN(TRY_CAST(minimum_nights AS INTEGER)) AS min_minimum_nights,
            MAX(TRY_CAST(maximum_nights AS INTEGER)) AS max_maximum_nights,
            CAST('{snapshot_date}' AS DATE) AS snapshot_date
        FROM read_csv_auto('{_duckdb_path(calendar_path)}', header = true)
        WHERE listing_id IS NOT NULL
        GROUP BY listing_id, month
    ) TO '{_duckdb_path(output_path)}' (FORMAT PARQUET)
    """
    with duckdb.connect() as conn:
        conn.execute(calendar_sql)
        count = conn.execute(
            f"SELECT COUNT(*) FROM read_parquet('{_duckdb_path(output_path)}')"
        ).fetchone()[0]
    return int(count)


def clean_city(city_key: str, config_path: str | Path = "configs/cities.yml") -> CleaningResult:
    city = load_config(config_path)[city_key]
    staged_dir = city_staged_dir(city.key, city.snapshot_date)
    processed_dir = city_processed_dir(city.key)
    ensure_dirs(processed_dir)

    listings = pd.read_csv(staged_dir / "listings_detailed.csv", usecols=LISTING_COLUMNS)
    master, quarantine = clean_listings_frame(
        listings,
        city_name=city.name,
        snapshot_date=city.snapshot_date,
    )

    master_path = processed_dir / "listings_master.parquet"
    quarantine_path = processed_dir / "listings_quarantine.parquet"
    analysis_path = processed_dir / "listings_analysis_view.parquet"
    calendar_path = processed_dir / "calendar_agg.parquet"

    master.to_parquet(master_path, index=False)
    quarantine.to_parquet(quarantine_path, index=False)
    write_listing_analysis_view(master, analysis_path)
    calendar_rows = aggregate_calendar(staged_dir, processed_dir, city.snapshot_date)

    return CleaningResult(
        city_key=city.key,
        snapshot_date=city.snapshot_date,
        listings_master_path=master_path,
        listings_quarantine_path=quarantine_path,
        listings_analysis_view_path=analysis_path,
        calendar_agg_path=calendar_path,
        listings_rows=len(master),
        quarantine_rows=len(quarantine),
        calendar_agg_rows=calendar_rows,
    )


def run_cleaning(
    config_path: str | Path = "configs/cities.yml", city_key: str | None = None
) -> list[CleaningResult]:
    cities = load_config(config_path)
    selected = [cities[city_key]] if city_key else list(cities.values())
    return [clean_city(city.key, config_path) for city in selected]


def _build_quarantine(frame: pd.DataFrame, snapshot_date: str) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    duplicate_ids = frame[frame[COL_LISTING_ID].duplicated(keep=False)][COL_LISTING_ID].dropna()
    duplicate_id_values = set(duplicate_ids.astype("int64").tolist())

    for row in frame.itertuples(index=False):
        _append_issue(
            records, row, snapshot_date, "listing_id_missing", row.id, pd.isna(row.listing_id)
        )
        _append_issue(
            records,
            row,
            snapshot_date,
            "listing_id_duplicate",
            row.id,
            row.listing_id in duplicate_id_values,
        )
        _append_issue(
            records, row, snapshot_date, "host_id_missing", row.host_id, pd.isna(row.host_id)
        )
        _append_issue(
            records,
            row,
            snapshot_date,
            "price_parse_failed",
            row.price_raw,
            _has_non_empty_value(row.price_raw) and pd.isna(row.price),
        )
        _append_issue(
            records,
            row,
            snapshot_date,
            "non_positive_price",
            row.price_raw,
            row.price is not None and row.price <= 0,
        )
        _append_issue(
            records,
            row,
            snapshot_date,
            "latitude_missing",
            row.latitude_raw,
            pd.isna(row.latitude_raw),
        )
        _append_issue(
            records,
            row,
            snapshot_date,
            "latitude_out_of_range",
            row.latitude_raw,
            not pd.isna(row.latitude_raw) and not (-90 <= row.latitude_raw <= 90),
        )
        _append_issue(
            records,
            row,
            snapshot_date,
            "longitude_missing",
            row.longitude_raw,
            pd.isna(row.longitude_raw),
        )
        _append_issue(
            records,
            row,
            snapshot_date,
            "longitude_out_of_range",
            row.longitude_raw,
            not pd.isna(row.longitude_raw) and not (-180 <= row.longitude_raw <= 180),
        )

    return pd.DataFrame.from_records(records, columns=QUARANTINE_COLUMNS)


def _append_issue(
    records: list[dict[str, Any]],
    row: Any,
    snapshot_date: str,
    reason: str,
    raw_value: object,
    condition: bool,
) -> None:
    if not condition:
        return

    records.append(
        {
            "source_file": "listings_detailed",
            "source_row_index": int(row.source_row_index),
            COL_LISTING_ID: None if pd.isna(row.listing_id) else int(row.listing_id),
            "reason": reason,
            "raw_value": None if pd.isna(raw_value) else str(raw_value),
            COL_SNAPSHOT_DATE: parse_date(snapshot_date),
        }
    )


def _master_columns() -> list[str]:
    return [
        COL_LISTING_ID,
        COL_HOST_ID,
        COL_PRICE_RAW,
        COL_PRICE,
        COL_PRICE_LOG,
        "is_price_usable",
        "room_type_raw",
        COL_ROOM_TYPE,
        "neighbourhood_raw",
        COL_NEIGHBOURHOOD,
        "city_raw",
        "city",
        "latitude",
        "latitude_raw",
        "longitude",
        "longitude_raw",
        "minimum_nights",
        "is_long_stay",
        "availability_365",
        "number_of_reviews",
        COL_REVIEW_FREQUENCY,
        "host_since",
        "last_review",
        COL_SNAPSHOT_DATE,
    ]


def _apply_master_dtypes(master: pd.DataFrame) -> pd.DataFrame:
    typed = master.copy()
    typed[COL_LISTING_ID] = typed[COL_LISTING_ID].astype("int64")
    typed[COL_HOST_ID] = typed[COL_HOST_ID].astype("int64")
    typed["minimum_nights"] = typed["minimum_nights"].astype("Int32")
    typed["availability_365"] = typed["availability_365"].astype("Int32")
    typed["number_of_reviews"] = typed["number_of_reviews"].astype("Int32")
    typed[COL_ROOM_TYPE] = typed[COL_ROOM_TYPE].astype("category")
    return typed


def _log_price(value: float | None) -> float | None:
    if value is None or value <= 0:
        return None
    return math.log(value)


def _iqr_bounds(values: pd.Series) -> tuple[float, float]:
    if values.empty:
        return float("-inf"), float("inf")

    q1 = float(values.quantile(0.25))
    q3 = float(values.quantile(0.75))
    iqr = q3 - q1
    return q1 - PRICE_OUTLIER_IQR_MULTIPLIER * iqr, q3 + PRICE_OUTLIER_IQR_MULTIPLIER * iqr


def _has_non_empty_value(value: object) -> bool:
    return value is not None and not pd.isna(value) and bool(str(value).strip())


def _duckdb_path(path: Path) -> str:
    return path.as_posix().replace("'", "''")
