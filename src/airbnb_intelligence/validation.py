from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Final

import pandas as pd
from rapidfuzz import fuzz

from airbnb_intelligence.ingestion import read_manifest
from airbnb_intelligence.utils import REPORTS_DIR, TABLES_DIR, ensure_dirs

FUZZY_NAME_THRESHOLD: Final[int] = 90
COORDINATE_PRECISION: Final[int] = 5
VALID_REVIEW_SCORE_MAX: Final[int] = 5
VALIDATION_CHUNK_ROWS: Final[int] = 100_000


@dataclass(frozen=True)
class ValidationIssue:
    rule_id: str
    file_key: str
    column: str
    finding_type: str
    row_index: int | None
    source_id: str | None
    description: str


def validate_city(
    city_key: str,
    snapshot_date: str,
    *,
    staged_root: Path = Path("data/staged"),
    reports_root: Path = REPORTS_DIR,
) -> dict[str, Any]:
    manifest_path = staged_root / city_key / snapshot_date / "manifest.json"
    manifest = read_manifest(manifest_path)
    if not manifest:
        raise FileNotFoundError(f"Manifest not found or empty: {manifest_path}")

    paths = {file_key: Path(str(entry["local_staged_path"])) for file_key, entry in manifest.items()}
    listings = pd.read_csv(paths["listings_detailed"], low_memory=False)
    _assert_columns(
        listings,
        [
            "id",
            "host_id",
            "name",
            "price",
            "latitude",
            "longitude",
            "availability_365",
            "minimum_nights",
            "last_review",
            "review_scores_rating",
            "number_of_reviews",
            "reviews_per_month",
        ],
        "listings_detailed",
    )

    result = validate_frames(
        listings,
        paths["calendar"],
        paths["reviews_summary"],
        snapshot_date=snapshot_date,
    )
    write_validation_outputs(result, reports_root)
    return result


def validate_frames(
    listings: pd.DataFrame,
    calendar_path: Path | None,
    reviews_summary_path: Path | None,
    *,
    snapshot_date: str,
) -> dict[str, Any]:
    issues: list[ValidationIssue] = []
    issues.extend(validate_listing_identifiers(listings))
    issues.extend(validate_price(listings))
    issues.extend(validate_numeric_range(listings, "latitude", -90, 90, "VLD-03"))
    issues.extend(validate_numeric_range(listings, "longitude", -180, 180, "VLD-04"))
    issues.extend(validate_numeric_range(listings, "availability_365", 0, 365, "VLD-05"))
    issues.extend(validate_numeric_range(listings, "minimum_nights", 0, None, "VLD-06"))
    issues.extend(validate_last_review(listings, snapshot_date))
    issues.extend(validate_review_scores(listings))
    issues.extend(find_fuzzy_candidates(listings))
    issues.extend(find_outliers(listings))

    listing_ids = set(pd.to_numeric(listings["id"], errors="coerce").dropna().astype("int64"))
    if calendar_path is not None:
        issues.extend(validate_join_coverage(calendar_path, listing_ids, "calendar", "VLD-09"))
    if reviews_summary_path is not None:
        issues.extend(
            validate_join_coverage(reviews_summary_path, listing_ids, "reviews_summary", "VLD-10")
        )

    return {
        "summary": summarize_issues(issues),
        "issues": [asdict(issue) for issue in issues],
        "coordinate_precision": COORDINATE_PRECISION,
        "fuzzy_name_threshold": FUZZY_NAME_THRESHOLD,
    }


def validate_listing_identifiers(listings: pd.DataFrame) -> list[ValidationIssue]:
    _assert_columns(listings, ["id"], "listings_detailed")
    issues: list[ValidationIssue] = []
    ids = pd.to_numeric(listings["id"], errors="coerce")
    missing = listings["id"].isna()
    invalid = ids.notna() & (ids <= 0)
    duplicate = listings["id"].notna() & listings["id"].duplicated(keep=False)
    issues.extend(row_issues(listings, missing, "VLD-01", "id", "missing", "Listing id is missing."))
    issues.extend(row_issues(listings, invalid, "VLD-01", "id", "invalid", "Listing id must be positive."))
    issues.extend(
        row_issues(listings, duplicate, "VLD-01", "id", "duplicate", "Listing id appears more than once.")
    )
    return issues


def validate_price(listings: pd.DataFrame) -> list[ValidationIssue]:
    _assert_columns(listings, ["price"], "listings_detailed")
    parsed = parse_price(listings["price"])
    missing = listings["price"].isna()
    invalid = listings["price"].notna() & (parsed.isna() | (parsed <= 0))
    return [
        *row_issues(listings, missing, "VLD-02", "price", "missing", "Listing price is missing."),
        *row_issues(listings, invalid, "VLD-02", "price", "invalid", "Listing price must parse to a positive value."),
    ]


def validate_numeric_range(
    listings: pd.DataFrame,
    column: str,
    minimum: float | None,
    maximum: float | None,
    rule_id: str,
) -> list[ValidationIssue]:
    _assert_columns(listings, [column], "listings_detailed")
    values = pd.to_numeric(listings[column], errors="coerce")
    missing = listings[column].isna()
    invalid = listings[column].notna() & values.isna()
    if minimum is not None:
        invalid = invalid | (values < minimum)
    if maximum is not None:
        invalid = invalid | (values > maximum)
    return [
        *row_issues(listings, missing, rule_id, column, "missing", f"{column} is missing."),
        *row_issues(listings, invalid, rule_id, column, "invalid", f"{column} is outside the valid range."),
    ]


def validate_last_review(listings: pd.DataFrame, snapshot_date: str) -> list[ValidationIssue]:
    _assert_columns(listings, ["last_review"], "listings_detailed")
    dates = pd.to_datetime(listings["last_review"], errors="coerce")
    source = listings["last_review"]
    snapshot = pd.Timestamp(snapshot_date)
    invalid = source.notna() & (dates.isna() | (dates > snapshot))
    return row_issues(
        listings,
        invalid,
        "VLD-07",
        "last_review",
        "invalid",
        "Last review must parse as a date and not be after the snapshot date.",
    )


def validate_review_scores(listings: pd.DataFrame) -> list[ValidationIssue]:
    _assert_columns(listings, ["review_scores_rating"], "listings_detailed")
    values = pd.to_numeric(listings["review_scores_rating"], errors="coerce")
    source = listings["review_scores_rating"]
    invalid = source.notna() & (values.isna() | (values < 0) | (values > VALID_REVIEW_SCORE_MAX))
    return row_issues(
        listings,
        invalid,
        "VLD-08",
        "review_scores_rating",
        "invalid",
        "Review score must be between 0 and 5 for this snapshot schema.",
    )


def validate_join_coverage(
    path: Path,
    listing_ids: set[int],
    file_key: str,
    rule_id: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for chunk in pd.read_csv(path, usecols=["listing_id"], chunksize=VALIDATION_CHUNK_ROWS):
        values = pd.to_numeric(chunk["listing_id"], errors="coerce")
        missing = chunk["listing_id"].isna()
        invalid = values.notna() & ~values.astype("int64").isin(listing_ids)
        issues.extend(
            row_issues(chunk, missing, rule_id, "listing_id", "missing", "Join listing_id is missing.", file_key)
        )
        issues.extend(
            row_issues(
                chunk,
                invalid,
                rule_id,
                "listing_id",
                "invalid",
                "Join listing_id does not exist in detailed listings.",
                file_key,
            )
        )
    return issues


def find_fuzzy_candidates(listings: pd.DataFrame) -> list[ValidationIssue]:
    _assert_columns(listings, ["id", "host_id", "name", "latitude", "longitude"], "listings_detailed")
    frame = listings[["id", "host_id", "name", "latitude", "longitude"]].dropna().copy()
    frame["name_norm"] = frame["name"].map(normalise_name)
    frame["lat_block"] = pd.to_numeric(frame["latitude"], errors="coerce").round(3)
    frame["lon_block"] = pd.to_numeric(frame["longitude"], errors="coerce").round(3)
    issues: list[ValidationIssue] = []

    for _block, group in frame.groupby(["host_id", "lat_block", "lon_block"], dropna=True):
        if len(group) < 2:
            continue
        for left, right in combinations(group.itertuples(index=True), 2):
            score = fuzz.ratio(left.name_norm, right.name_norm)
            if score >= FUZZY_NAME_THRESHOLD:
                issues.append(
                    ValidationIssue(
                        "DUP-02",
                        "listings_detailed",
                        "name",
                        "unusual",
                        int(left.Index),
                        str(left.id),
                        f"Potential duplicate candidate with listing {right.id}; name similarity {score}.",
                    )
                )
    return issues


def find_outliers(listings: pd.DataFrame) -> list[ValidationIssue]:
    fields = {
        "price": parse_price(listings["price"]),
        "availability_365": pd.to_numeric(listings["availability_365"], errors="coerce"),
        "minimum_nights": pd.to_numeric(listings["minimum_nights"], errors="coerce"),
        "number_of_reviews": pd.to_numeric(listings["number_of_reviews"], errors="coerce"),
        "reviews_per_month": pd.to_numeric(listings["reviews_per_month"], errors="coerce"),
    }
    issues: list[ValidationIssue] = []
    for column, values in fields.items():
        clean = values.dropna()
        if len(clean) < 10:
            continue
        q1 = clean.quantile(0.25)
        q3 = clean.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 3 * iqr
        upper = q3 + 3 * iqr
        mask = values.notna() & ((values < lower) | (values > upper))
        if column == "price":
            p99 = clean.quantile(0.99)
            mask = mask | (values > p99)
        issues.extend(
            row_issues(
                listings,
                mask,
                "OUT-01",
                column,
                "unusual",
                f"{column} is statistically extreme by IQR rule.",
            )
        )
    return issues


def standardise_coordinates(listings: pd.DataFrame) -> pd.DataFrame:
    _assert_columns(listings, ["latitude", "longitude"], "listings_detailed")
    result = listings.copy()
    result["latitude_raw"] = result["latitude"]
    result["longitude_raw"] = result["longitude"]
    result["latitude"] = pd.to_numeric(result["latitude"], errors="coerce").round(COORDINATE_PRECISION)
    result["longitude"] = pd.to_numeric(result["longitude"], errors="coerce").round(COORDINATE_PRECISION)
    return result


def row_issues(
    frame: pd.DataFrame,
    mask: pd.Series,
    rule_id: str,
    column: str,
    finding_type: str,
    description: str,
    file_key: str = "listings_detailed",
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for index in frame.index[mask.fillna(False)]:
        source_id = frame.at[index, "id"] if "id" in frame.columns else frame.at[index, column]
        issues.append(
            ValidationIssue(
                rule_id,
                file_key,
                column,
                finding_type,
                int(index),
                None if pd.isna(source_id) else str(source_id),
                description,
            )
        )
    return issues


def summarize_issues(issues: list[ValidationIssue]) -> dict[str, Any]:
    by_type: dict[str, int] = defaultdict(int)
    by_rule: dict[str, int] = defaultdict(int)
    for issue in issues:
        by_type[issue.finding_type] += 1
        by_rule[issue.rule_id] += 1
    return {
        "issue_count": len(issues),
        "by_finding_type": dict(sorted(by_type.items())),
        "by_rule": dict(sorted(by_rule.items())),
    }


def write_validation_outputs(result: dict[str, Any], reports_root: Path) -> None:
    ensure_dirs(reports_root, TABLES_DIR)
    (reports_root / "validation_report.json").write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame(result["issues"]).to_csv(TABLES_DIR / "data_quality_issues.csv", index=False)


def parse_price(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(r"[$,%]", "", regex=True).str.replace(",", "", regex=False),
        errors="coerce",
    )


def normalise_name(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(value).lower())).strip()


def _assert_columns(df_head: pd.DataFrame, required: list[str], file_key: str) -> None:
    missing = set(required) - set(df_head.columns)
    if missing:
        raise ValueError(f"File '{file_key}' is missing expected columns: {sorted(missing)}.")
