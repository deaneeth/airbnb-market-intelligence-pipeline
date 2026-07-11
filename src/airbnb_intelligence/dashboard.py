from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import pandas as pd

from airbnb_intelligence.utils import (
    COL_AVAILABILITY_RATE,
    COL_HOST_SEGMENT,
    COL_LISTING_ID,
    COL_NEIGHBOURHOOD,
    COL_PRICE,
    COL_ROOM_TYPE,
    city_processed_dir,
)

PROPERTY_TYPE: Final[str] = "property_type"
REQUIRED_LISTING_COLUMNS: Final[set[str]] = {
    COL_LISTING_ID,
    COL_PRICE,
    COL_ROOM_TYPE,
    COL_NEIGHBOURHOOD,
    COL_AVAILABILITY_RATE,
    COL_HOST_SEGMENT,
}
REQUIRED_CALENDAR_COLUMNS: Final[set[str]] = {
    COL_LISTING_ID,
    "month",
    COL_AVAILABILITY_RATE,
}


@dataclass(frozen=True)
class DashboardData:
    listings: pd.DataFrame
    calendar: pd.DataFrame


def load_dashboard_data(city_key: str = "amsterdam") -> DashboardData:
    processed_dir = city_processed_dir(city_key)
    listings = pd.read_parquet(processed_dir / "listings_master.parquet")
    calendar = pd.read_parquet(processed_dir / "calendar_agg.parquet")
    validate_dashboard_data(listings, calendar)
    return DashboardData(listings=listings, calendar=calendar)


def validate_dashboard_data(listings: pd.DataFrame, calendar: pd.DataFrame) -> None:
    missing_listing = REQUIRED_LISTING_COLUMNS - set(listings.columns)
    missing_calendar = REQUIRED_CALENDAR_COLUMNS - set(calendar.columns)
    if missing_listing or missing_calendar:
        raise ValueError(
            "Dashboard inputs are missing required columns: "
            f"listings={sorted(missing_listing)}, calendar={sorted(missing_calendar)}"
        )


def filter_values(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame.columns:
        return []
    values = frame[column].dropna().astype(str).sort_values().unique()
    return list(values)


def filter_listings(
    listings: pd.DataFrame,
    neighbourhoods: list[str] | None = None,
    room_types: list[str] | None = None,
    property_types: list[str] | None = None,
) -> pd.DataFrame:
    filtered = listings.copy()
    if neighbourhoods:
        filtered = filtered[filtered[COL_NEIGHBOURHOOD].isin(neighbourhoods)]
    if room_types:
        filtered = filtered[filtered[COL_ROOM_TYPE].isin(room_types)]
    if property_types:
        if PROPERTY_TYPE not in filtered.columns:
            raise ValueError("property_type is not available in the processed dashboard input")
        filtered = filtered[filtered[PROPERTY_TYPE].isin(property_types)]
    return filtered


def kpi_summary(listings: pd.DataFrame) -> dict[str, float]:
    priced = listings[listings[COL_PRICE].notna() & (listings[COL_PRICE] > 0)]
    professional_share = 0.0
    availability_rate = 0.0
    if not listings.empty:
        professional_share = float((listings[COL_HOST_SEGMENT] == "professional").mean() * 100)
        availability = listings[COL_AVAILABILITY_RATE].dropna()
        availability_rate = float(availability.mean() * 100) if not availability.empty else 0.0
    return {
        "listing_count": float(len(listings)),
        "median_price": float(priced[COL_PRICE].median()) if not priced.empty else 0.0,
        "availability_rate": availability_rate,
        "professional_host_share": professional_share,
    }


def price_histogram(listings: pd.DataFrame, bins: int = 30) -> pd.DataFrame:
    priced = listings[listings[COL_PRICE].notna() & (listings[COL_PRICE] > 0)][COL_PRICE]
    if priced.empty:
        return pd.DataFrame(columns=["price_bin", "listing_count"])
    counts = pd.cut(priced, bins=bins).value_counts(sort=False)
    histogram = counts.reset_index()
    histogram.columns = ["price_bin", "listing_count"]
    histogram["price_bin"] = histogram["price_bin"].astype(str)
    return histogram


def supply_table(listings: pd.DataFrame) -> pd.DataFrame:
    if listings.empty:
        return pd.DataFrame(columns=[COL_NEIGHBOURHOOD, "listing_count", "median_price"])
    priced = listings[listings[COL_PRICE].notna() & (listings[COL_PRICE] > 0)]
    return (
        priced.groupby(COL_NEIGHBOURHOOD)
        .agg(listing_count=(COL_LISTING_ID, "count"), median_price=(COL_PRICE, "median"))
        .round(2)
        .reset_index()
        .sort_values(["listing_count", "median_price"], ascending=[False, False])
    )


def room_type_price_table(listings: pd.DataFrame) -> pd.DataFrame:
    priced = listings[listings[COL_PRICE].notna() & (listings[COL_PRICE] > 0)]
    if priced.empty:
        return pd.DataFrame(columns=[COL_ROOM_TYPE, "listing_count", "median_price"])
    return (
        priced.groupby(COL_ROOM_TYPE)
        .agg(listing_count=(COL_LISTING_ID, "count"), median_price=(COL_PRICE, "median"))
        .round(2)
        .reset_index()
        .sort_values("listing_count", ascending=False)
    )


def monthly_availability(calendar: pd.DataFrame, listing_ids: pd.Series) -> pd.DataFrame:
    filtered = calendar[calendar[COL_LISTING_ID].isin(listing_ids)]
    if filtered.empty:
        return pd.DataFrame(columns=["month", "availability_rate"])
    trend = (
        filtered.groupby("month")
        .agg(availability_rate=(COL_AVAILABILITY_RATE, "mean"))
        .reset_index()
        .sort_values("month")
    )
    trend[COL_AVAILABILITY_RATE] = (trend[COL_AVAILABILITY_RATE] * 100).round(2)
    return trend
