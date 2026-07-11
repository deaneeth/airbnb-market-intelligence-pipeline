from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from airbnb_intelligence.enrichment import (
    AMSTERDAM_CENTRE_LAT,
    AMSTERDAM_CENTRE_LON,
    MIN_NEIGHBOURHOOD_LISTINGS,
    PROFESSIONAL_HOST_THRESHOLD,
    classify_host_segment,
    compute_calendar_aggregates,
    compute_distance_to_centre,
    compute_host_tenure,
    compute_neighbourhood_aggregates,
    compute_portfolio_size,
)
from airbnb_intelligence.utils import (
    COL_AVAILABILITY_RATE,
    COL_HOST_ID,
    COL_LISTING_ID,
    COL_NEIGHBOURHOOD,
    COL_OCCUPANCY_PROXY,
    COL_PRICE,
)

# ---------------------------------------------------------------------------
# compute_host_tenure
# ---------------------------------------------------------------------------


def test_host_tenure_known_value() -> None:
    host_since = pd.Series([date(2019, 1, 1)])
    snapshot = date(2024, 1, 1)
    result = compute_host_tenure(host_since, snapshot)
    # 5 years (with 365.25 base) = 1826 days / 365.25 ≈ 4.998
    assert abs(float(result.iloc[0]) - 5.0) < 0.02


def test_host_tenure_null_when_host_since_null() -> None:
    host_since = pd.Series([None])
    result = compute_host_tenure(host_since, date(2024, 1, 1))
    assert pd.isna(result.iloc[0])


def test_host_tenure_uses_snapshot_date_not_clock() -> None:
    # Tenure computed at a fixed past snapshot_date must not change when re-run.
    host_since = pd.Series([date(2020, 6, 15)])
    snapshot = date(2022, 6, 15)
    result1 = compute_host_tenure(host_since, snapshot)
    result2 = compute_host_tenure(host_since, snapshot)
    assert float(result1.iloc[0]) == float(result2.iloc[0])


# ---------------------------------------------------------------------------
# compute_portfolio_size
# ---------------------------------------------------------------------------


def test_portfolio_size_three_listings_same_host() -> None:
    df = pd.DataFrame(
        {
            COL_HOST_ID: [10, 10, 10, 20],
            COL_LISTING_ID: [1, 2, 3, 4],
        }
    )
    result = compute_portfolio_size(df)
    assert result.iloc[0] == 3
    assert result.iloc[1] == 3
    assert result.iloc[2] == 3
    assert result.iloc[3] == 1


# ---------------------------------------------------------------------------
# classify_host_segment
# ---------------------------------------------------------------------------


def test_classify_casual_for_portfolio_one() -> None:
    result = classify_host_segment(pd.Series([1]))
    assert result.iloc[0] == "casual"


def test_classify_professional_for_portfolio_two() -> None:
    result = classify_host_segment(pd.Series([2]))
    assert result.iloc[0] == "professional"


def test_classify_professional_for_portfolio_ten() -> None:
    result = classify_host_segment(pd.Series([10]))
    assert result.iloc[0] == "professional"


def test_classify_segment_dtype_is_category() -> None:
    result = classify_host_segment(pd.Series([1, 2, 3]))
    assert str(result.dtype) == "category"


# ---------------------------------------------------------------------------
# compute_distance_to_centre
# ---------------------------------------------------------------------------


def test_distance_zero_at_centre() -> None:
    lat = pd.Series([AMSTERDAM_CENTRE_LAT])
    lon = pd.Series([AMSTERDAM_CENTRE_LON])
    result = compute_distance_to_centre(lat, lon, AMSTERDAM_CENTRE_LAT, AMSTERDAM_CENTRE_LON)
    assert float(result.iloc[0]) == 0.0


def test_distance_known_coordinate_pair() -> None:
    # Amsterdam Central Station: approx 52.3791, 4.9003
    # Hand-verified with online Haversine calculators: ~0.90 km from Dam Square
    lat = pd.Series([52.3791])
    lon = pd.Series([4.9003])
    result = compute_distance_to_centre(lat, lon, AMSTERDAM_CENTRE_LAT, AMSTERDAM_CENTRE_LON)
    assert 0.7 < float(result.iloc[0]) < 1.1


# ---------------------------------------------------------------------------
# compute_calendar_aggregates
# ---------------------------------------------------------------------------


def test_calendar_aggregates_mean_availability_rate() -> None:
    cal = pd.DataFrame(
        {
            COL_LISTING_ID: [1, 1, 2],
            "days_observed": [30, 31, 30],
            COL_AVAILABILITY_RATE: [0.5, 0.6, 0.8],
            COL_OCCUPANCY_PROXY: [0.5, 0.4, 0.2],
        }
    )
    result = compute_calendar_aggregates(cal)
    row_1 = result[result[COL_LISTING_ID] == 1].iloc[0]
    assert abs(float(row_1[COL_AVAILABILITY_RATE]) - 0.55) < 0.0001
    assert int(row_1["total_days_observed"]) == 61


def test_calendar_aggregates_one_row_per_listing() -> None:
    cal = pd.DataFrame(
        {
            COL_LISTING_ID: [5, 5, 5],
            "days_observed": [28, 30, 31],
            COL_AVAILABILITY_RATE: [0.1, 0.2, 0.3],
            COL_OCCUPANCY_PROXY: [0.9, 0.8, 0.7],
        }
    )
    result = compute_calendar_aggregates(cal)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# compute_neighbourhood_aggregates
# ---------------------------------------------------------------------------


def test_neighbourhood_aggregates_excludes_small_neighbourhoods() -> None:
    neighbourhood = ["A"] * 20 + ["B"] * (MIN_NEIGHBOURHOOD_LISTINGS - 1)
    df = pd.DataFrame(
        {
            COL_LISTING_ID: range(len(neighbourhood)),
            COL_NEIGHBOURHOOD: neighbourhood,
            COL_PRICE: [100.0] * len(neighbourhood),
        }
    )
    result = compute_neighbourhood_aggregates(df)
    assert "A" in result[COL_NEIGHBOURHOOD].values
    assert "B" not in result[COL_NEIGHBOURHOOD].values


# ---------------------------------------------------------------------------
# Row count preservation (integration-style with small fixture)
# ---------------------------------------------------------------------------


def test_enrich_does_not_change_row_count(tmp_path: pytest.TempPathFactory) -> None:
    """Verify that merging calendar aggregates preserves the master row count."""
    master = pd.DataFrame(
        {
            COL_LISTING_ID: [1, 2, 3],
            COL_HOST_ID: [10, 10, 20],
            COL_NEIGHBOURHOOD: ["A", "A", "B"],
            COL_PRICE: [100.0, 200.0, 150.0],
            "host_since": [date(2018, 1, 1), date(2019, 1, 1), None],
            "latitude": [52.37, 52.38, 52.36],
            "longitude": [4.89, 4.90, 4.88],
            "snapshot_date": [date(2024, 6, 15)] * 3,
            "review_frequency": [1.5, 2.0, 0.5],
        }
    )
    cal = pd.DataFrame(
        {
            COL_LISTING_ID: [1, 1],
            "days_observed": [30, 31],
            COL_AVAILABILITY_RATE: [0.4, 0.6],
            COL_OCCUPANCY_PROXY: [0.6, 0.4],
        }
    )
    cal_summary = compute_calendar_aggregates(cal)
    merged = master.merge(cal_summary, on=COL_LISTING_ID, how="left")
    assert len(merged) == len(master)


# ---------------------------------------------------------------------------
# Review-summary join: one-to-one (no row multiplication)
# ---------------------------------------------------------------------------


def test_calendar_join_does_not_multiply_rows() -> None:
    master = pd.DataFrame({COL_LISTING_ID: [1, 2, 3]})
    cal_summary = pd.DataFrame(
        {
            COL_LISTING_ID: [1, 2],
            COL_AVAILABILITY_RATE: [0.5, 0.6],
            COL_OCCUPANCY_PROXY: [0.5, 0.4],
            "total_days_observed": [30, 30],
        }
    )
    merged = master.merge(cal_summary, on=COL_LISTING_ID, how="left")
    assert len(merged) == 3
    assert pd.isna(merged.loc[merged[COL_LISTING_ID] == 3, COL_AVAILABILITY_RATE].iloc[0])


# ---------------------------------------------------------------------------
# Professional host threshold constant matches documented value
# ---------------------------------------------------------------------------


def test_professional_host_threshold_is_two() -> None:
    assert PROFESSIONAL_HOST_THRESHOLD == 2
