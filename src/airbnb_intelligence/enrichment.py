from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path


import pandas as pd

from airbnb_intelligence.config import load_config
from airbnb_intelligence.utils import (
    COL_AVAILABILITY_RATE,
    COL_HOST_ID,
    COL_HOST_SEGMENT,
    COL_LISTING_ID,
    COL_NEIGHBOURHOOD,
    COL_OCCUPANCY_PROXY,
    COL_PRICE,
    COL_REVENUE_PROXY,
    COL_REVIEW_FREQUENCY,
    COL_SNAPSHOT_DATE,
    city_processed_dir,
    get_logger,
)

logger = get_logger(__name__)

# Hosts with 2 or more listings in the snapshot are classified as professional.
# See docs/assumptions.md for the rationale and alternative considered.
PROFESSIONAL_HOST_THRESHOLD: Final[int] = 2

# Neighbourhoods with fewer than this number of listings receive null aggregate
# columns in the master table. Retained in the table; excluded from comparisons.
# See docs/assumptions.md.
MIN_NEIGHBOURHOOD_LISTINGS: Final[int] = 15

# Dam Square, Amsterdam. Used as the city-centre reference point.
# Source and rationale documented in docs/assumptions.md.
AMSTERDAM_CENTRE_LAT: Final[float] = 52.37310
AMSTERDAM_CENTRE_LON: Final[float] = 4.89319


@dataclass(frozen=True)
class EnrichmentResult:
    city_key: str
    listings_rows: int
    null_availability_rate_rows: int


def compute_host_tenure(
    host_since: pd.Series,
    snapshot_date: date,
) -> pd.Series:
    """Return host tenure in decimal years at the snapshot date.

    Null when host_since is null. Uses 365.25 days per year.
    Does not use the system clock; snapshot_date comes from config.
    """
    snapshot_ts = pd.Timestamp(snapshot_date)
    days = (snapshot_ts - pd.to_datetime(host_since)).dt.days
    return (days / 365.25).where(host_since.notna())


def compute_portfolio_size(df: pd.DataFrame) -> pd.Series:
    """Return the number of listings each host has in this snapshot."""
    counts = df.groupby(COL_HOST_ID)[COL_LISTING_ID].transform("count")
    return counts.astype("int32")


def classify_host_segment(portfolio_size: pd.Series) -> pd.Series:
    """Classify hosts as 'casual' (1 listing) or 'professional' (2+ listings).

    Threshold: PROFESSIONAL_HOST_THRESHOLD. Documented in docs/assumptions.md.
    """
    labels = ["professional" if n >= PROFESSIONAL_HOST_THRESHOLD else "casual" for n in portfolio_size]
    return pd.Series(
        pd.Categorical(labels, categories=["casual", "professional"]),
        index=portfolio_size.index,
        dtype="category",
    )


def compute_distance_to_centre(
    latitude: pd.Series,
    longitude: pd.Series,
    centre_lat: float,
    centre_lon: float,
) -> pd.Series:
    """Return Haversine distance in kilometres from the city-centre reference point.

    Uses the standard Haversine formula with Earth radius 6371 km.
    Reference coordinates sourced from city config / AMSTERDAM_CENTRE_LAT/LON.
    """
    r = 6371.0
    lat1 = math.radians(centre_lat)
    lon1 = math.radians(centre_lon)
    lat2_rad = latitude.map(math.radians)
    lon2_rad = longitude.map(math.radians)
    dlat = lat2_rad - lat1
    dlon = lon2_rad - lon1
    a = (dlat / 2).map(math.sin) ** 2 + math.cos(lat1) * lat2_rad.map(math.cos) * (dlon / 2).map(math.sin) ** 2
    c = 2 * a.map(math.sqrt).map(math.asin)
    return (r * c).round(3)


def compute_calendar_aggregates(calendar_agg: pd.DataFrame) -> pd.DataFrame:
    """Collapse calendar_agg to one summary row per listing.

    Returns listing_id, mean availability_rate, mean occupancy_proxy,
    and total_days_observed across all months in the calendar window.

    Proxy notes
    -----------
    occupancy_proxy: Derived from host-set availability; not equivalent to confirmed booked nights.
    """
    grouped = calendar_agg.groupby(COL_LISTING_ID, sort=False)
    return pd.DataFrame(
        {
            COL_LISTING_ID: grouped[COL_LISTING_ID].first(),
            COL_AVAILABILITY_RATE: grouped[COL_AVAILABILITY_RATE].mean().round(4),
            COL_OCCUPANCY_PROXY: grouped[COL_OCCUPANCY_PROXY].mean().round(4),
            "total_days_observed": grouped["days_observed"].sum(),
        }
    ).reset_index(drop=True)


def compute_neighbourhood_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    """Return per-neighbourhood: listing_count and median_price.

    Excludes neighbourhoods below MIN_NEIGHBOURHOOD_LISTINGS from the result
    so the master table receives null for those neighbourhoods.
    """
    counts = df.groupby(COL_NEIGHBOURHOOD)[COL_LISTING_ID].transform("count")
    eligible = df[counts >= MIN_NEIGHBOURHOOD_LISTINGS]
    return (
        eligible.groupby(COL_NEIGHBOURHOOD)
        .agg(
            neighbourhood_listing_count=(COL_LISTING_ID, "count"),
            neighbourhood_median_price=(COL_PRICE, "median"),
        )
        .reset_index()
    )


def enrich_city(
    city_key: str,
    config_path: str | Path = "configs/cities.yml",
) -> EnrichmentResult:
    """Add enrichment columns to listings_master.parquet for city_key.

    Joins calendar_agg on listing_id (left join) so listings without calendar
    data are retained with null availability_rate, occupancy_proxy, and revenue_proxy.

    Row count is verified before writing. Raises if count changes.

    Proxy notes
    -----------
    occupancy_proxy: Derived from host-set availability; not equivalent to confirmed booked nights.
    revenue_proxy:   Estimated from availability proxy and calendar price; not observed revenue.
    """
    cities = load_config(config_path)
    city = cities[city_key]
    processed_dir = city_processed_dir(city_key)
    master_path = processed_dir / "listings_master.parquet"
    calendar_path = processed_dir / "calendar_agg.parquet"

    master = pd.read_parquet(master_path)
    pre_count = len(master)
    logger.info("listings_master loaded: %d rows, %d columns", pre_count, master.shape[1])

    required = {COL_LISTING_ID, COL_HOST_ID, COL_SNAPSHOT_DATE, "host_since", "latitude", "longitude", COL_PRICE}
    missing = required - set(master.columns)
    if missing:
        raise ValueError(f"listings_master is missing required columns: {missing}")

    snapshot_date = _resolve_snapshot_date(master[COL_SNAPSHOT_DATE].iloc[0])

    master["host_tenure_years"] = compute_host_tenure(master["host_since"], snapshot_date)
    master["portfolio_size"] = compute_portfolio_size(master)
    master[COL_HOST_SEGMENT] = classify_host_segment(master["portfolio_size"])
    master["distance_to_centre_km"] = compute_distance_to_centre(
        master["latitude"],
        master["longitude"],
        AMSTERDAM_CENTRE_LAT,
        AMSTERDAM_CENTRE_LON,
    )

    assert COL_REVIEW_FREQUENCY in master.columns, (
        f"{COL_REVIEW_FREQUENCY} must be present in listings_master from the cleaning step"
    )

    calendar_agg = pd.read_parquet(calendar_path)
    cal_summary = compute_calendar_aggregates(calendar_agg)

    master = master.merge(cal_summary, on=COL_LISTING_ID, how="left")

    # revenue_proxy = listing price x occupancy_proxy x total calendar days observed.
    # Caveat: estimated from availability proxy and listing quote price; not observed revenue.
    has_cal = master[COL_AVAILABILITY_RATE].notna() & master[COL_PRICE].notna()
    master[COL_REVENUE_PROXY] = float("nan")
    master.loc[has_cal, COL_REVENUE_PROXY] = (
        master.loc[has_cal, COL_PRICE]
        * master.loc[has_cal, COL_OCCUPANCY_PROXY]
        * master.loc[has_cal, "total_days_observed"]
    ).round(2)
    master = master.drop(columns=["total_days_observed"])

    neigh_agg = compute_neighbourhood_aggregates(master)
    master = master.merge(neigh_agg, on=COL_NEIGHBOURHOOD, how="left")

    post_count = len(master)
    if post_count != pre_count:
        raise RuntimeError(
            f"Row count changed during enrichment: {pre_count} -> {post_count}. Aborting write."
        )

    null_avail = int(master[COL_AVAILABILITY_RATE].isna().sum())
    logger.info("Enriched master: %d rows, %d columns", post_count, master.shape[1])
    logger.info("Listings with null availability_rate (no calendar data): %d", null_avail)

    master.to_parquet(master_path, index=False)
    logger.info("Wrote enriched listings_master to %s", master_path)

    return EnrichmentResult(
        city_key=city.key,
        listings_rows=post_count,
        null_availability_rate_rows=null_avail,
    )


def run_enrichment(
    config_path: str | Path = "configs/cities.yml",
    city_key: str | None = None,
) -> list[EnrichmentResult]:
    cities = load_config(config_path)
    selected = [cities[city_key]] if city_key else list(cities.values())
    return [enrich_city(city.key, config_path) for city in selected]


def _resolve_snapshot_date(raw: object) -> date:
    """Convert the snapshot_date value from the parquet column to a date object."""
    if isinstance(raw, date):
        return raw
    if isinstance(raw, pd.Timestamp):
        return raw.date()
    return datetime.strptime(str(raw), "%Y-%m-%d").date()
