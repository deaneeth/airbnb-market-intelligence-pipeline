from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from airbnb_intelligence.statistics import (
    REQUIRED_RESULT_COLUMNS,
    apply_bh_correction,
    cohens_d,
    correlation_matrix,
    eta_squared,
    fit_price_model,
    model_limitations_table,
    model_vif_table,
    price_ci_table,
    rank_biserial_r,
    residual_summary,
    run_hypothesis_tests,
    strongest_price_correlations,
)


def test_apply_bh_correction_known_values() -> None:
    adjusted = apply_bh_correction([0.01, 0.04, 0.03])

    assert adjusted == pytest.approx([0.03, 0.04, 0.04])


def test_effect_size_helpers_known_values() -> None:
    assert cohens_d(pd.Series([1.0, 2.0, 3.0]), pd.Series([2.0, 3.0, 4.0])) == pytest.approx(-1.0)
    assert rank_biserial_r(9.0, 3, 3) == pytest.approx(1.0)
    assert eta_squared(12.0, 30, 3) == pytest.approx(10.0 / 27.0)


def test_hypothesis_results_have_required_schema() -> None:
    results = run_hypothesis_tests(_sample_listings())

    assert list(results.columns) == REQUIRED_RESULT_COLUMNS
    assert set(results["hypothesis_id"]) == {"H1", "H2", "H3", "H4", "H5", "H6", "H7"}
    assert results.loc[results["hypothesis_id"] == "H4", "status"].item() == "unavailable"
    assert results.loc[results["hypothesis_id"] != "H4", "effect_size"].ne("").all()


def test_spearman_known_answer_fixture() -> None:
    results = run_hypothesis_tests(_sample_listings())
    h6 = results.loc[results["hypothesis_id"] == "H6"].iloc[0]

    assert h6["test_statistic_name"] == "rho"
    assert float(h6["test_statistic"]) < 0


def test_price_ci_table_uses_minimum_group_size() -> None:
    listings = _sample_listings()
    ci = price_ci_table(listings, "room_type")

    assert set(ci["group"]) == {"entire home/apt", "private room"}
    assert ci["ci_lower"].notna().all()
    assert ci["ci_upper"].notna().all()


def test_fit_price_model_returns_coefficient_table() -> None:
    model = fit_price_model(_sample_listings())

    assert "Intercept" in set(model["term"])
    assert model["n_obs"].iloc[0] == len(_sample_listings())
    assert math.isfinite(model["r_squared"].iloc[0])
    assert model["interpretation_note"].str.contains("not causal").all()


def test_price_model_diagnostics_tables_are_populated() -> None:
    listings = _sample_listings()

    assert "bedrooms" in correlation_matrix(listings).columns
    assert strongest_price_correlations(listings)["absolute_correlation"].is_monotonic_decreasing
    assert model_vif_table(listings)["vif"].notna().all()
    assert model_limitations_table(listings)["topic"].notna().all()
    assert residual_summary(listings, "room_type")["row_count"].sum() == len(listings)


def _sample_listings() -> pd.DataFrame:
    rows = []
    neighbourhoods = ["Centre", "West", "East"]
    property_types = [
        "Entire rental unit",
        "Entire condo",
        "Private room in rental unit",
        "House",
    ]
    for i in range(120):
        is_entire = i % 2 == 0
        price = 90 + (80 if is_entire else 0) + ((i % 17) * 4) + ((i % 5) * 9)
        rows.append(
            {
                "listing_id": i + 1,
                "price": float(price),
                "price_log": float(np.log(price)),
                "room_type": "entire home/apt" if is_entire else "private room",
                "property_type": property_types[(i // 2) % len(property_types)],
                "bedrooms": 1.0 + ((i // 3) % 4),
                "host_is_superhost": "true" if i % 3 == 0 else "false",
                "host_segment": "professional" if i % 4 == 0 else "casual",
                "neighbourhood_cleansed": neighbourhoods[i % len(neighbourhoods)],
                "minimum_nights": 1 + (i % 7),
                "availability_rate": 1.2 - (price / 300) + ((i % 7) / 100),
                "review_frequency": 0.2 + (i / 30),
                "review_scores_rating": 4.2 + (i % 10) / 20,
                "distance_to_centre_km": 0.5 + (i % 12) / 3,
            }
        )
    return pd.DataFrame(rows)
