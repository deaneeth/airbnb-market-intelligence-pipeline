from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from datetime import date

import duckdb
import pandas as pd

from airbnb_intelligence.config import load_config
from airbnb_intelligence.utils import (
    DB_PATH,
    SQL_DIR,
    TABLES_DIR,
    city_processed_dir,
    ensure_dirs,
    get_logger,
)

logger = get_logger(__name__)

MIN_LISTING_ROWS: Final[int] = 100
MIN_CALENDAR_ROWS: Final[int] = 1_000


@dataclass(frozen=True)
class DatabaseResult:
    city_key: str
    table_counts: dict[str, int]
    query_row_counts: dict[str, int]


def generate_date_spine(start_date: date, end_date: date) -> pd.DataFrame:
    """Return a dim_date DataFrame covering start_date to end_date inclusive."""
    dates = pd.date_range(start_date, end_date, freq="D")
    return pd.DataFrame(
        {
            "date_id": dates.strftime("%Y%m%d").astype(int),
            "date": dates.date,
            "year": dates.year,
            "month": dates.month,
            "month_name": dates.strftime("%B"),
            "day_of_week": dates.dayofweek,
            "is_weekend": dates.dayofweek >= 5,
        }
    )


def build_database(
    city_key: str,
    config_path: str | Path = "configs/cities.yml",
    db_path: Path = DB_PATH,
) -> DatabaseResult:
    """Load the star schema from enriched Parquet files and run business queries.

    Idempotent: safe to call multiple times with the same inputs. The schema
    uses CREATE OR REPLACE so all tables are rebuilt from scratch each run.
    """
    load_config(config_path)
    processed_dir = city_processed_dir(city_key)
    listings_path = processed_dir / "listings_master.parquet"
    calendar_path = processed_dir / "calendar_agg.parquet"

    if not listings_path.exists():
        raise FileNotFoundError(f"listings_master.parquet not found at {listings_path}")
    if not calendar_path.exists():
        raise FileNotFoundError(f"calendar_agg.parquet not found at {calendar_path}")

    schema_sql = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    ensure_dirs(db_path.parent, TABLES_DIR)

    with duckdb.connect(str(db_path)) as conn:
        conn.execute(schema_sql)
        logger.info("Schema created (idempotent)")

        _load_dimensions(conn, listings_path)
        _load_fact_listing_snapshot(conn, listings_path)
        _load_fact_calendar(conn, calendar_path)

        counts = _verify_counts(conn)
        query_counts = _run_business_queries(conn)

    logger.info("Database build complete: %s", counts)
    return DatabaseResult(city_key=city_key, table_counts=counts, query_row_counts=query_counts)


def run_database(
    config_path: str | Path = "configs/cities.yml",
    city_key: str | None = None,
) -> list[DatabaseResult]:
    cities = load_config(config_path)
    selected = [cities[city_key]] if city_key else list(cities.values())
    return [build_database(city.key, config_path) for city in selected]


def _load_dimensions(
    conn: duckdb.DuckDBPyConnection,
    listings_path: Path,
) -> None:
    p = _posix(listings_path)

    conn.execute(f"""
        INSERT INTO dim_neighbourhood
        SELECT
            ROW_NUMBER() OVER (ORDER BY neighbourhood_cleansed) AS neighbourhood_id,
            neighbourhood_cleansed                              AS neighbourhood,
            neighbourhood_listing_count                         AS listing_count,
            neighbourhood_median_price                          AS median_price
        FROM (
            SELECT DISTINCT
                neighbourhood_cleansed,
                neighbourhood_listing_count,
                neighbourhood_median_price
            FROM read_parquet('{p}')
            WHERE neighbourhood_cleansed IS NOT NULL
              AND neighbourhood_cleansed != 'Unknown'
        )
    """)
    logger.info("dim_neighbourhood loaded")

    conn.execute(f"""
        INSERT INTO dim_host
        SELECT DISTINCT ON (host_id)
            host_id,
            host_since::DATE,
            host_tenure_years,
            portfolio_size,
            host_segment::VARCHAR
        FROM read_parquet('{p}')
        WHERE host_id IS NOT NULL
    """)
    logger.info("dim_host loaded")

    conn.execute(f"""
        INSERT INTO dim_listing
        SELECT
            fls.listing_id,
            fls.host_id,
            dn.neighbourhood_id,
            fls.room_type::VARCHAR,
            fls.minimum_nights,
            fls.latitude,
            fls.longitude,
            fls.distance_to_centre_km
        FROM read_parquet('{p}') fls
        JOIN dim_neighbourhood dn
          ON fls.neighbourhood_cleansed = dn.neighbourhood
        WHERE fls.listing_id IS NOT NULL
    """)
    logger.info("dim_listing loaded")

    cal_path = listings_path.parent / "calendar_agg.parquet"
    date_bounds = conn.execute(f"""
        SELECT
            MIN(TRY_STRPTIME(month, '%Y-%m'))::DATE               AS min_date,
            (MAX(TRY_STRPTIME(month || '-01', '%Y-%m-%d'))
             + INTERVAL '1 month' - INTERVAL '1 day')::DATE       AS max_date
        FROM read_parquet('{_posix(cal_path)}')
    """).fetchone()

    if date_bounds and date_bounds[0] and date_bounds[1]:
        date_spine = generate_date_spine(date_bounds[0], date_bounds[1])
        conn.register("date_spine", date_spine)
        conn.execute("INSERT INTO dim_date SELECT * FROM date_spine")
        conn.unregister("date_spine")
        logger.info("dim_date loaded: %d rows", len(date_spine))
    else:
        logger.warning("Could not determine calendar date range; dim_date will be empty")


def _load_fact_listing_snapshot(
    conn: duckdb.DuckDBPyConnection,
    listings_path: Path,
) -> None:
    p = _posix(listings_path)
    conn.execute(f"""
        INSERT INTO fact_listing_snapshot
        SELECT
            fls.listing_id,
            fls.host_id,
            dn.neighbourhood_id,
            fls.snapshot_date::DATE,
            fls.price,
            fls.price_raw::VARCHAR,
            fls.availability_365,
            fls.number_of_reviews,
            fls.review_frequency,
            fls.availability_rate,
            fls.occupancy_proxy,
            fls.revenue_proxy
        FROM read_parquet('{p}') fls
        JOIN dim_neighbourhood dn
          ON fls.neighbourhood_cleansed = dn.neighbourhood
        WHERE fls.listing_id IS NOT NULL
    """)
    logger.info("fact_listing_snapshot loaded")


def _load_fact_calendar(
    conn: duckdb.DuckDBPyConnection,
    calendar_path: Path,
) -> None:
    p = _posix(calendar_path)
    conn.execute(f"""
        INSERT INTO fact_calendar
        SELECT
            cal.listing_id,
            cal.month,
            cal.days_observed,
            cal.days_available,
            cal.availability_rate,
            cal.occupancy_proxy,
            cal.snapshot_date::DATE
        FROM read_parquet('{p}') cal
        JOIN dim_listing dl ON cal.listing_id = dl.listing_id
    """)
    logger.info("fact_calendar loaded")


def _verify_counts(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    tables = [
        ("dim_neighbourhood", 1),
        ("dim_host", 1),
        ("dim_listing", 1),
        ("fact_listing_snapshot", MIN_LISTING_ROWS),
        ("fact_calendar", MIN_CALENDAR_ROWS),
    ]
    counts: dict[str, int] = {}
    for table, minimum in tables:
        (count,) = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        counts[table] = int(count)
        if count < minimum:
            raise RuntimeError(
                f"Table '{table}' has {count} rows; expected at least {minimum}."
            )
        logger.info("%s: %d rows", table, count)
    return counts


def _run_business_queries(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    sql_text = (SQL_DIR / "business_queries.sql").read_text(encoding="utf-8")
    queries = _split_queries(sql_text)
    row_counts: dict[str, int] = {}

    for name, sql in queries.items():
        result = conn.execute(sql).df()
        row_counts[name] = len(result)
        output_path = TABLES_DIR / f"{name}.csv"
        result.to_csv(output_path, index=False)
        logger.info("%s: %d rows -> %s", name, len(result), output_path)
        if len(result) == 0:
            logger.warning("Query '%s' returned zero rows", name)

    return row_counts


def _split_queries(sql_text: str) -> dict[str, str]:
    """Split business_queries.sql into named query blocks by -- Q<N>: header."""
    pattern = re.compile(r"--\s*──\s*(Q\d+):\s*(.+?)─+", re.MULTILINE)
    parts = pattern.split(sql_text)
    queries: dict[str, str] = {}
    i = 1
    while i + 2 < len(parts):
        q_num = parts[i].strip()
        q_desc = parts[i + 1].strip().replace(" ", "_").lower()[:40]
        q_sql = parts[i + 2].strip()
        if q_sql:
            key = f"{q_num}_{q_desc}"
            queries[key] = q_sql
        i += 3
    return queries


def _posix(path: Path) -> str:
    return path.as_posix().replace("'", "''")
