from __future__ import annotations

import pandas as pd

from airbnb_intelligence.reporting import (
    coverage_table,
    high_review_low_score_profile,
    host_portfolio_summary,
    review_score_summary,
    room_property_mix,
    room_type_summary,
    superhost_summary,
    top_amenities,
)


def test_room_type_summary_uses_only_positive_prices() -> None:
    summary = room_type_summary(_eda_fixture())

    entire = summary[summary["room_type"] == "entire home/apt"].iloc[0]
    assert entire["listing_count"] == 2
    assert entire["median_price"] == 150.0


def test_host_portfolio_summary_reports_concentration() -> None:
    summary = host_portfolio_summary(_eda_fixture())
    values = dict(zip(summary["metric"], summary["value"], strict=True))

    assert values["hosts"] == 4
    assert values["listings"] == 5
    assert values["single_listing_hosts"] == 3
    assert values["hosts_with_2_plus_listings"] == 1


def test_review_score_summary_reports_ceiling_share() -> None:
    summary = review_score_summary(_eda_fixture())
    rating = summary[summary["score_column"] == "review_scores_rating"].iloc[0]

    assert rating["listing_count"] == 5
    assert rating["share_at_5"] == 0.2


def test_superhost_summary_groups_available_flags() -> None:
    summary = superhost_summary(_eda_fixture())

    assert set(summary["host_is_superhost"]) == {"true", "false"}


def test_room_property_mix_reports_geographic_centres() -> None:
    mix = room_property_mix(_eda_fixture())

    assert {"median_latitude", "median_longitude"}.issubset(mix.columns)


def test_high_review_low_score_profile_returns_segment_rows() -> None:
    profile = high_review_low_score_profile(_eda_fixture())

    assert not profile.empty
    assert {"room_type", "neighbourhood_cleansed", "listing_count"}.issubset(profile.columns)


def test_top_amenities_parses_list_strings() -> None:
    amenities = top_amenities(_eda_fixture(), limit=2)

    assert amenities.iloc[0]["amenity"] == "Wifi"
    assert amenities.iloc[0]["listing_count"] == 4


def test_coverage_marks_missing_host_tenure_unavailable() -> None:
    coverage = coverage_table(_eda_fixture(), "2026-06-15")
    tenure = coverage[coverage["analysis"] == "host tenure versus price"].iloc[0]

    assert tenure["status"] == "unavailable"


def _eda_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "listing_id": [1, 2, 3, 4, 5],
            "host_id": [10, 10, 20, 30, 40],
            "room_type": pd.Categorical(
                [
                    "entire home/apt",
                    "entire home/apt",
                    "private room",
                    "private room",
                    "private room",
                ]
            ),
            "price": [100.0, 200.0, 80.0, None, 120.0],
            "price_log": [4.60, 5.30, 4.38, None, 4.79],
            "neighbourhood_cleansed": ["A", "A", "B", "B", "B"],
            "review_scores_rating": [5.0, 4.8, 4.2, 4.6, 4.1],
            "review_scores_accuracy": [5.0, 4.7, 4.1, 4.5, 4.0],
            "review_scores_cleanliness": [5.0, 4.7, 4.1, 4.5, 4.0],
            "review_scores_checkin": [5.0, 4.7, 4.1, 4.5, 4.0],
            "review_scores_communication": [5.0, 4.7, 4.1, 4.5, 4.0],
            "review_scores_location": [5.0, 4.7, 4.1, 4.5, 4.0],
            "review_scores_value": [5.0, 4.7, 4.1, 4.5, 4.0],
            "number_of_reviews": [100, 90, 120, 5, 130],
            "availability_rate": [0.2, 0.3, 0.4, 0.5, 0.6],
            "occupancy_proxy": [0.8, 0.7, 0.6, 0.5, 0.4],
            "host_segment": pd.Categorical(
                ["professional", "professional", "casual", "casual", "casual"]
            ),
            "host_tenure_years": [None, None, None, None, None],
            "host_response_rate": [None, None, None, None, None],
            "property_type": [
                "Entire rental unit",
                "Entire rental unit",
                "Private room in rental unit",
                "Private room in rental unit",
                "Private room in rental unit",
            ],
            "latitude": [52.1, 52.2, 52.3, 52.4, 52.5],
            "longitude": [4.1, 4.2, 4.3, 4.4, 4.5],
            "host_is_superhost": ["true", "true", "false", "false", "false"],
            "amenities": [
                '["Wifi", "Kitchen"]',
                '["Wifi"]',
                '["Wifi", "Heating"]',
                '["Kitchen"]',
                '["Wifi"]',
            ],
        }
    )
