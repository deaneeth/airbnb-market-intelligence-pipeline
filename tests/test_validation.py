from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from airbnb_intelligence.validation import (
    _assert_columns,
    find_fuzzy_candidates,
    find_outliers,
    standardise_coordinates,
    validate_frames,
)


def clean_listings() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2],
            "host_id": [10, 20],
            "name": ["Canal apartment", "Garden room"],
            "price": ["$100.00", "$80.00"],
            "latitude": [52.37, 52.36],
            "longitude": [4.89, 4.88],
            "availability_365": [120, 90],
            "minimum_nights": [2, 1],
            "last_review": ["2026-06-01", "2026-05-01"],
            "review_scores_rating": [4.8, 4.6],
            "number_of_reviews": [20, 10],
            "reviews_per_month": [1.5, 0.8],
        }
    )


def write_join_files(tmp_path: Path, ids: list[int]) -> tuple[Path, Path]:
    calendar = tmp_path / "calendar.csv"
    reviews = tmp_path / "reviews_summary.csv"
    rows = "\n".join(f"{listing_id},2026-06-16" for listing_id in ids)
    calendar.write_text(f"listing_id,date\n{rows}\n", encoding="utf-8")
    reviews.write_text(f"listing_id,date\n{rows}\n", encoding="utf-8")
    return calendar, reviews


def issue_types(result: dict) -> set[str]:
    return {issue["finding_type"] for issue in result["issues"]}


def test_clean_dataset_has_zero_issues(tmp_path: Path) -> None:
    calendar, reviews = write_join_files(tmp_path, [1, 2])
    result = validate_frames(clean_listings(), calendar, reviews, snapshot_date="2026-06-15")
    assert result["summary"]["issue_count"] == 0


@pytest.mark.parametrize(
    ("column", "value", "finding_type"),
    [
        ("id", None, "missing"),
        ("id", -1, "invalid"),
        ("price", None, "missing"),
        ("price", "$0.00", "invalid"),
        ("latitude", 91, "invalid"),
        ("longitude", 181, "invalid"),
        ("availability_365", -1, "invalid"),
        ("minimum_nights", -1, "invalid"),
        ("last_review", "2026-07-01", "invalid"),
        ("review_scores_rating", 6, "invalid"),
    ],
)
def test_validation_rules_catch_specific_violations(
    tmp_path: Path,
    column: str,
    value: object,
    finding_type: str,
) -> None:
    listings = clean_listings()
    listings.loc[0, column] = value
    calendar, reviews = write_join_files(tmp_path, [1, 2])

    result = validate_frames(listings, calendar, reviews, snapshot_date="2026-06-15")

    assert finding_type in issue_types(result)


def test_duplicate_listing_id_is_reported(tmp_path: Path) -> None:
    listings = clean_listings()
    listings.loc[1, "id"] = 1
    calendar, reviews = write_join_files(tmp_path, [1])

    result = validate_frames(listings, calendar, reviews, snapshot_date="2026-06-15")

    assert any(issue["finding_type"] == "duplicate" for issue in result["issues"])


def test_join_coverage_reports_unknown_listing_id(tmp_path: Path) -> None:
    calendar, reviews = write_join_files(tmp_path, [1, 999])

    result = validate_frames(clean_listings(), calendar, reviews, snapshot_date="2026-06-15")

    assert any(issue["rule_id"] in {"VLD-09", "VLD-10"} for issue in result["issues"])


def test_fuzzy_duplicate_flags_candidate_within_block() -> None:
    listings = clean_listings()
    listings.loc[1, ["host_id", "name", "latitude", "longitude"]] = [
        10,
        "Canal apartment!",
        52.3701,
        4.8901,
    ]

    issues = find_fuzzy_candidates(listings)

    assert len(issues) == 1
    assert issues[0].finding_type == "unusual"


def test_fuzzy_duplicate_ignores_dissimilar_names() -> None:
    listings = clean_listings()
    listings.loc[1, ["host_id", "latitude", "longitude"]] = [10, 52.3701, 4.8901]

    assert find_fuzzy_candidates(listings) == []


def test_outlier_report_keeps_rows() -> None:
    listings = pd.concat([clean_listings()] * 10, ignore_index=True)
    listings.loc[len(listings)] = listings.loc[0]
    listings.loc[len(listings) - 1, "price"] = "$10000.00"

    issues = find_outliers(listings)

    assert len(listings) == 21
    assert any(issue.finding_type == "unusual" for issue in issues)


def test_coordinate_standardisation_preserves_raw_values() -> None:
    listings = clean_listings()
    listings.loc[0, "latitude"] = 52.1234567
    listings.loc[0, "longitude"] = 4.9876543

    result = standardise_coordinates(listings)

    assert result.loc[0, "latitude"] == 52.12346
    assert result.loc[0, "longitude"] == 4.98765
    assert result.loc[0, "latitude_raw"] == 52.1234567
    assert result.loc[0, "longitude_raw"] == 4.9876543


def test_column_assertion_raises_on_missing_column() -> None:
    with pytest.raises(ValueError, match="missing expected columns"):
        _assert_columns(pd.DataFrame({"id": [1]}), ["price"], "listings_detailed")
