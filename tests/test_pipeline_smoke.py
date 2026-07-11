from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from airbnb_intelligence.database import (
    _split_queries,
    _verify_counts,
    generate_date_spine,
)
from airbnb_intelligence.utils import SQL_DIR

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SCHEMA_SQL = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
QUERIES_SQL = (SQL_DIR / "business_queries.sql").read_text(encoding="utf-8")


def _make_listings_parquet(tmp_path: Path) -> Path:
    df = pd.DataFrame(
        {
            "listing_id": [1, 2, 3, 4, 5],
            "host_id": [10, 10, 20, 30, 30],
            "price_raw": ["$100.00", "$200.00", "$150.00", "$80.00", "$120.00"],
            "price": [100.0, 200.0, 150.0, 80.0, 120.0],
            "room_type": ["Entire home/apt"] * 3 + ["Private room"] * 2,
            "neighbourhood_cleansed": ["De Wallen"] * 3 + ["Jordaan"] * 2,
            "neighbourhood_listing_count": [3, 3, 3, 2, 2],
            "neighbourhood_median_price": [150.0, 150.0, 150.0, 100.0, 100.0],
            "minimum_nights": [2, 3, 1, 7, 2],
            "latitude": [52.373, 52.374, 52.375, 52.371, 52.372],
            "longitude": [4.893, 4.894, 4.895, 4.891, 4.892],
            "distance_to_centre_km": [0.1, 0.2, 0.3, 0.4, 0.5],
            "host_since": [None, None, None, None, None],
            "host_tenure_years": [None, None, None, None, None],
            "portfolio_size": [2, 2, 1, 2, 2],
            "host_segment": ["professional", "professional", "casual", "professional", "professional"],
            "snapshot_date": ["2024-06-15"] * 5,
            "availability_365": [180, 90, 300, 120, 200],
            "number_of_reviews": [10, 5, 20, 3, 8],
            "review_frequency": [1.0, 0.5, 2.0, 0.3, 0.8],
            "availability_rate": [0.5, 0.3, 0.8, 0.4, 0.6],
            "occupancy_proxy": [0.5, 0.7, 0.2, 0.6, 0.4],
            "revenue_proxy": [5000.0, 7000.0, 2000.0, 3000.0, 4000.0],
        }
    )
    path = tmp_path / "listings_master.parquet"
    df.to_parquet(path, index=False)
    return path


def _make_calendar_parquet(tmp_path: Path) -> Path:
    rows = []
    for lid in [1, 2, 3, 4, 5]:
        for month in ["2024-06", "2024-07", "2024-08"]:
            rows.append(
                {
                    "listing_id": lid,
                    "month": month,
                    "days_observed": 30,
                    "days_available": 15.0,
                    "availability_rate": 0.5,
                    "occupancy_proxy": 0.5,
                    "snapshot_date": "2024-06-15",
                }
            )
    df = pd.DataFrame(rows)
    path = tmp_path / "calendar_agg.parquet"
    df.to_parquet(path, index=False)
    return path


def _load_fixture_db(conn: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    """Load small fixture data into an in-memory connection."""
    listings_path = _make_listings_parquet(tmp_path)
    calendar_path = _make_calendar_parquet(tmp_path)
    p_listings = listings_path.as_posix()
    p_calendar = calendar_path.as_posix()

    conn.execute(SCHEMA_SQL)

    conn.execute(f"""
        INSERT INTO dim_neighbourhood
        SELECT ROW_NUMBER() OVER (ORDER BY neighbourhood_cleansed) AS neighbourhood_id,
               neighbourhood_cleansed AS neighbourhood,
               neighbourhood_listing_count AS listing_count,
               neighbourhood_median_price  AS median_price
        FROM (
            SELECT DISTINCT neighbourhood_cleansed, neighbourhood_listing_count, neighbourhood_median_price
            FROM read_parquet('{p_listings}')
        )
    """)
    conn.execute(f"""
        INSERT INTO dim_host
        SELECT DISTINCT ON (host_id)
            host_id, host_since::DATE, host_tenure_years, portfolio_size, host_segment::VARCHAR
        FROM read_parquet('{p_listings}')
        WHERE host_id IS NOT NULL
    """)
    conn.execute(f"""
        INSERT INTO dim_listing
        SELECT fls.listing_id, fls.host_id, dn.neighbourhood_id,
               fls.room_type::VARCHAR, fls.minimum_nights,
               fls.latitude, fls.longitude, fls.distance_to_centre_km
        FROM read_parquet('{p_listings}') fls
        JOIN dim_neighbourhood dn ON fls.neighbourhood_cleansed = dn.neighbourhood
    """)

    from airbnb_intelligence.database import generate_date_spine
    date_spine = generate_date_spine(date(2024, 6, 1), date(2024, 8, 31))
    conn.register("date_spine", date_spine)
    conn.execute("INSERT INTO dim_date SELECT * FROM date_spine")
    conn.unregister("date_spine")

    conn.execute(f"""
        INSERT INTO fact_listing_snapshot
        SELECT fls.listing_id, fls.host_id, dn.neighbourhood_id,
               fls.snapshot_date::DATE, fls.price, fls.price_raw::VARCHAR,
               fls.availability_365, fls.number_of_reviews, fls.review_frequency,
               fls.availability_rate, fls.occupancy_proxy, fls.revenue_proxy
        FROM read_parquet('{p_listings}') fls
        JOIN dim_neighbourhood dn ON fls.neighbourhood_cleansed = dn.neighbourhood
    """)
    conn.execute(f"""
        INSERT INTO fact_calendar
        SELECT cal.listing_id, cal.month, cal.days_observed, cal.days_available,
               cal.availability_rate, cal.occupancy_proxy, cal.snapshot_date::DATE
        FROM read_parquet('{p_calendar}') cal
        JOIN dim_listing dl ON cal.listing_id = dl.listing_id
    """)


# ---------------------------------------------------------------------------
# Schema idempotency
# ---------------------------------------------------------------------------


def test_schema_creation_is_idempotent() -> None:
    schema = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    with duckdb.connect(":memory:") as conn:
        conn.execute(schema)
        conn.execute(schema)  # second run must not raise


# ---------------------------------------------------------------------------
# Load from fixtures produces correct row counts
# ---------------------------------------------------------------------------


def test_fixture_load_produces_nonzero_counts(tmp_path: Path) -> None:
    with duckdb.connect(":memory:") as conn:
        _load_fixture_db(conn, tmp_path)
        for table in ("dim_neighbourhood", "dim_host", "dim_listing", "fact_listing_snapshot", "fact_calendar"):
            (count,) = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            assert count > 0, f"{table} is empty"


def test_fixture_load_listing_count(tmp_path: Path) -> None:
    with duckdb.connect(":memory:") as conn:
        _load_fixture_db(conn, tmp_path)
        (count,) = conn.execute("SELECT COUNT(*) FROM fact_listing_snapshot").fetchone()
        assert count == 5


def test_fixture_load_calendar_count(tmp_path: Path) -> None:
    with duckdb.connect(":memory:") as conn:
        _load_fixture_db(conn, tmp_path)
        (count,) = conn.execute("SELECT COUNT(*) FROM fact_calendar").fetchone()
        assert count == 15  # 5 listings x 3 months


# ---------------------------------------------------------------------------
# No duplicate fact rows from joins
# ---------------------------------------------------------------------------


def test_no_duplicate_listing_snapshot_rows(tmp_path: Path) -> None:
    with duckdb.connect(":memory:") as conn:
        _load_fixture_db(conn, tmp_path)
        (total,) = conn.execute("SELECT COUNT(*) FROM fact_listing_snapshot").fetchone()
        (distinct,) = conn.execute("SELECT COUNT(DISTINCT listing_id) FROM fact_listing_snapshot").fetchone()
        assert total == distinct


def test_no_duplicate_calendar_rows(tmp_path: Path) -> None:
    with duckdb.connect(":memory:") as conn:
        _load_fixture_db(conn, tmp_path)
        (total,) = conn.execute("SELECT COUNT(*) FROM fact_calendar").fetchone()
        (distinct,) = conn.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT listing_id, month FROM fact_calendar)"
        ).fetchone()
        assert total == distinct


# ---------------------------------------------------------------------------
# Row count verification raises for empty table
# ---------------------------------------------------------------------------


def test_verify_counts_raises_for_empty_fact_table() -> None:
    with duckdb.connect(":memory:") as conn:
        schema = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
        conn.execute(schema)
        conn.execute("INSERT INTO dim_neighbourhood VALUES (1, 'Test', 10, 100.0)")
        conn.execute("INSERT INTO dim_host VALUES (99, NULL, NULL, 1, 'casual')")
        conn.execute(
            "INSERT INTO dim_listing VALUES (1001, 99, 1, 'Entire home/apt', 2, 52.37, 4.89, 0.5)"
        )
        with pytest.raises(RuntimeError, match="fact_listing_snapshot"):
            _verify_counts(conn)


# ---------------------------------------------------------------------------
# Business queries execute on fixture database
# ---------------------------------------------------------------------------


def test_all_business_queries_run_on_fixture(tmp_path: Path) -> None:
    queries = _split_queries(QUERIES_SQL)
    assert len(queries) >= 7, "Expected at least 7 named queries"

    with duckdb.connect(":memory:") as conn:
        _load_fixture_db(conn, tmp_path)
        for name, sql in queries.items():
            result = conn.execute(sql).df()
            assert isinstance(result, pd.DataFrame), f"Query {name} did not return a DataFrame"


# ---------------------------------------------------------------------------
# generate_date_spine
# ---------------------------------------------------------------------------


def test_date_spine_includes_endpoints() -> None:
    spine = generate_date_spine(date(2024, 1, 1), date(2024, 1, 3))
    assert len(spine) == 3
    assert spine["date"].iloc[0] == date(2024, 1, 1)
    assert spine["date"].iloc[-1] == date(2024, 1, 3)


def test_date_spine_is_weekend_flags_saturday_sunday() -> None:
    spine = generate_date_spine(date(2024, 1, 6), date(2024, 1, 7))  # Sat + Sun
    assert all(spine["is_weekend"])


def test_date_spine_weekday_not_weekend() -> None:
    spine = generate_date_spine(date(2024, 1, 1), date(2024, 1, 1))  # Monday
    assert not spine["is_weekend"].iloc[0]


# ---------------------------------------------------------------------------
# _split_queries parses all named blocks
# ---------------------------------------------------------------------------


def test_split_queries_returns_expected_count() -> None:
    queries = _split_queries(QUERIES_SQL)
    assert len(queries) == 7


def test_split_queries_all_have_select() -> None:
    queries = _split_queries(QUERIES_SQL)
    for name, sql in queries.items():
        assert "SELECT" in sql.upper(), f"Query {name} has no SELECT statement"
