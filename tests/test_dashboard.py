from __future__ import annotations

import pandas as pd
import pytest

from airbnb_intelligence.dashboard import (
    PROPERTY_TYPE,
    filter_listings,
    filter_values,
    kpi_summary,
    monthly_availability,
    price_histogram,
    room_type_price_table,
    supply_table,
    validate_dashboard_data,
)


def _listings() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "listing_id": [1, 2, 3],
            "price": [100.0, 200.0, None],
            "room_type": ["entire home/apt", "private room", "private room"],
            "neighbourhood_cleansed": ["Centrum", "West", "West"],
            "availability_rate": [0.2, 0.6, 0.8],
            "host_segment": ["casual", "professional", "professional"],
            PROPERTY_TYPE: ["Apartment", "House", "Apartment"],
        }
    )


def _calendar() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "listing_id": [1, 1, 2, 3],
            "month": ["2026-07", "2026-08", "2026-07", "2026-07"],
            "availability_rate": [0.2, 0.4, 0.6, 0.8],
        }
    )


def test_validate_dashboard_data_accepts_required_columns() -> None:
    validate_dashboard_data(_listings(), _calendar())


def test_validate_dashboard_data_rejects_missing_required_columns() -> None:
    listings = _listings().drop(columns=["price"])

    with pytest.raises(ValueError, match="price"):
        validate_dashboard_data(listings, _calendar())


def test_filter_values_returns_sorted_values_and_empty_for_missing_column() -> None:
    assert filter_values(_listings(), "room_type") == ["entire home/apt", "private room"]
    assert filter_values(_listings(), "missing") == []


def test_filter_listings_applies_all_available_filters() -> None:
    filtered = filter_listings(
        _listings(),
        neighbourhoods=["West"],
        room_types=["private room"],
        property_types=["House"],
    )

    assert filtered["listing_id"].tolist() == [2]


def test_filter_listings_rejects_property_filter_when_column_is_absent() -> None:
    listings = _listings().drop(columns=[PROPERTY_TYPE])

    with pytest.raises(ValueError, match="property_type"):
        filter_listings(listings, property_types=["Apartment"])


def test_empty_filter_selection_returns_all_rows() -> None:
    assert len(filter_listings(_listings(), [], [], [])) == 3


def test_kpi_summary_handles_filtered_rows() -> None:
    summary = kpi_summary(_listings())

    assert summary["listing_count"] == 3
    assert summary["median_price"] == 150.0
    assert summary["availability_rate"] == pytest.approx(53.3333, rel=1e-3)
    assert summary["professional_host_share"] == pytest.approx(66.6666, rel=1e-3)


def test_price_histogram_returns_counts() -> None:
    histogram = price_histogram(_listings(), bins=2)

    assert histogram["listing_count"].sum() == 2


def test_supply_and_room_type_tables_ignore_missing_prices() -> None:
    supply = supply_table(_listings())
    room_type = room_type_price_table(_listings())

    assert supply["listing_count"].sum() == 2
    assert room_type["listing_count"].sum() == 2


def test_monthly_availability_uses_filtered_listing_ids() -> None:
    trend = monthly_availability(_calendar(), pd.Series([1]))

    assert trend["month"].tolist() == ["2026-07", "2026-08"]
    assert trend["availability_rate"].tolist() == [20.0, 40.0]
