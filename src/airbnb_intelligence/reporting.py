from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from airbnb_intelligence.config import load_config
from airbnb_intelligence.enrichment import MIN_NEIGHBOURHOOD_LISTINGS
from airbnb_intelligence.utils import (
    COL_AVAILABILITY_RATE,
    COL_HOST_SEGMENT,
    COL_LISTING_ID,
    COL_NEIGHBOURHOOD,
    COL_OCCUPANCY_PROXY,
    COL_PRICE,
    COL_PRICE_LOG,
    COL_REVIEW_FREQUENCY,
    COL_ROOM_TYPE,
    FIGURES_DIR,
    REPORTS_DIR,
    TABLES_DIR,
    city_processed_dir,
    city_staged_dir,
    ensure_dirs,
)

if TYPE_CHECKING:
    from pathlib import Path

FIGURE_STYLE: Final[dict[str, object]] = {
    "figure.figsize": (10, 6),
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.35,
    "font.size": 10,
}
plt.rcParams.update(FIGURE_STYLE)

ROOM_TYPE_COLOURS: Final[dict[str, str]] = {
    "entire home/apt": "#2E86AB",
    "private room": "#F18F01",
    "shared room": "#6A994E",
    "hotel room": "#A23B72",
}

REVIEW_SCORE_COLUMNS: Final[list[str]] = [
    "review_scores_rating",
    "review_scores_accuracy",
    "review_scores_cleanliness",
    "review_scores_checkin",
    "review_scores_communication",
    "review_scores_location",
    "review_scores_value",
]

SUPPLEMENTAL_COLUMNS: Final[list[str]] = [
    "id",
    "property_type",
    "host_response_rate",
    "host_is_superhost",
    "amenities",
    *REVIEW_SCORE_COLUMNS,
]

EDA_CAVEATS: Final[dict[str, str]] = {
    COL_OCCUPANCY_PROXY: "Derived from host-set availability; not equivalent to confirmed booked nights.",
    COL_REVIEW_FREQUENCY: "Reviews per month as reported by Inside Airbnb; used as a demand signal proxy only.",
}


@dataclass(frozen=True)
class EDAResult:
    city_key: str
    figure_paths: list[Path]
    table_paths: list[Path]
    coverage_path: Path


def run_eda(
    config_path: str | Path = "configs/cities.yml", city_key: str | None = None
) -> list[EDAResult]:
    cities = load_config(config_path)
    selected = [cities[city_key]] if city_key else list(cities.values())
    return [build_eda_outputs(city.key, config_path) for city in selected]


def build_eda_outputs(city_key: str, config_path: str | Path = "configs/cities.yml") -> EDAResult:
    city = load_config(config_path)[city_key]
    ensure_dirs(FIGURES_DIR, TABLES_DIR)
    listings = load_eda_listings(city.key, city.snapshot_date)
    calendar = pd.read_parquet(city_processed_dir(city.key) / "calendar_agg.parquet")

    figure_paths = [
        plot_price_distribution(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_price_by_room_type(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_price_by_property_type(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_price_by_neighbourhood(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_host_portfolio_concentration(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_host_portfolio_ccdf(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_review_score_distribution(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_review_score_subdimensions(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_monthly_availability(calendar, city.name, city.snapshot_date, FIGURES_DIR),
        plot_listing_supply_map(listings, city.key, city.snapshot_date, FIGURES_DIR),
        plot_property_type_geography(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_price_vs_distance(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_host_segment_performance(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_superhost_performance(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_review_frequency_relationships(listings, city.name, city.snapshot_date, FIGURES_DIR),
        plot_review_volume_trend(city.key, city.snapshot_date, FIGURES_DIR),
        plot_monthly_minimum_nights(calendar, city.name, city.snapshot_date, FIGURES_DIR),
    ]

    table_paths = write_summary_tables(
        listings, calendar, city.key, city.snapshot_date, TABLES_DIR
    )
    coverage_path = write_coverage_report(listings, city.key, city.snapshot_date, REPORTS_DIR)
    return EDAResult(city.key, figure_paths, table_paths, coverage_path)


def load_eda_listings(city_key: str, snapshot_date: str) -> pd.DataFrame:
    master = pd.read_parquet(city_processed_dir(city_key) / "listings_master.parquet")
    staged_path = city_staged_dir(city_key, snapshot_date) / "listings_detailed.csv"
    supplemental = pd.read_csv(staged_path, usecols=SUPPLEMENTAL_COLUMNS)
    supplemental = supplemental.rename(columns={"id": COL_LISTING_ID})
    listings = master.merge(supplemental, on=COL_LISTING_ID, how="left")
    listings["property_type"] = listings["property_type"].fillna("Unknown")
    listings["host_is_superhost"] = listings["host_is_superhost"].map(_normalise_tf)
    return listings


def write_summary_tables(
    listings: pd.DataFrame,
    calendar: pd.DataFrame,
    city_key: str,
    snapshot_date: str,
    output_dir: Path,
) -> list[Path]:
    paths: list[Path] = []
    paths.append(_write_csv(room_type_summary(listings), output_dir / "eda_room_type_summary.csv"))
    paths.append(
        _write_csv(property_type_summary(listings), output_dir / "eda_property_type_summary.csv")
    )
    paths.append(
        _write_csv(
            neighbourhood_summary(listings),
            output_dir / "eda_neighbourhood_summary.csv",
        )
    )
    paths.append(
        _write_csv(host_segment_summary(listings), output_dir / "eda_host_segment_summary.csv")
    )
    paths.append(
        _write_csv(host_portfolio_summary(listings), output_dir / "eda_host_portfolio_summary.csv")
    )
    paths.append(_write_csv(superhost_summary(listings), output_dir / "eda_superhost_summary.csv"))
    paths.append(
        _write_csv(review_score_summary(listings), output_dir / "eda_review_score_summary.csv")
    )
    paths.append(_write_csv(room_property_mix(listings), output_dir / "eda_room_property_mix.csv"))
    paths.append(
        _write_csv(
            neighbourhood_review_score_summary(listings),
            output_dir / "eda_neighbourhood_review_scores.csv",
        )
    )
    paths.append(
        _write_csv(
            high_review_low_score_profile(listings),
            output_dir / "eda_high_review_low_score_profile.csv",
        )
    )
    paths.append(
        _write_csv(
            monthly_availability_summary(calendar), output_dir / "eda_monthly_availability.csv"
        )
    )
    paths.append(
        _write_csv(
            monthly_minimum_nights_summary(calendar),
            output_dir / "eda_monthly_minimum_nights.csv",
        )
    )
    paths.append(_write_csv(top_amenities(listings), output_dir / "eda_top_amenities.csv"))
    paths.append(
        _write_csv(coverage_table(listings, snapshot_date), output_dir / "eda_coverage.csv")
    )
    return paths


def room_type_summary(listings: pd.DataFrame) -> pd.DataFrame:
    usable = _usable_price_rows(listings)
    return (
        usable.groupby(COL_ROOM_TYPE, observed=True)
        .agg(
            listing_count=(COL_LISTING_ID, "count"),
            median_price=(COL_PRICE, "median"),
            price_q1=(COL_PRICE, lambda s: s.quantile(0.25)),
            price_q3=(COL_PRICE, lambda s: s.quantile(0.75)),
            mean_review_score=("review_scores_rating", "mean"),
        )
        .round(2)
        .reset_index()
        .sort_values("listing_count", ascending=False)
    )


def property_type_summary(listings: pd.DataFrame) -> pd.DataFrame:
    usable = _usable_price_rows(listings)
    return (
        usable.groupby("property_type")
        .agg(
            listing_count=(COL_LISTING_ID, "count"),
            median_price=(COL_PRICE, "median"),
            mean_review_score=("review_scores_rating", "mean"),
        )
        .query("listing_count >= @MIN_NEIGHBOURHOOD_LISTINGS")
        .round(2)
        .reset_index()
        .sort_values(["median_price", "listing_count"], ascending=[False, False])
    )


def neighbourhood_summary(listings: pd.DataFrame) -> pd.DataFrame:
    usable = _usable_price_rows(listings)
    return (
        usable.groupby(COL_NEIGHBOURHOOD)
        .agg(
            listing_count=(COL_LISTING_ID, "count"),
            median_price=(COL_PRICE, "median"),
            mean_price=(COL_PRICE, "mean"),
            mean_review_score=("review_scores_rating", "mean"),
            mean_availability_rate=(COL_AVAILABILITY_RATE, "mean"),
        )
        .query("listing_count >= @MIN_NEIGHBOURHOOD_LISTINGS")
        .round(2)
        .reset_index()
        .sort_values("median_price", ascending=False)
    )


def host_segment_summary(listings: pd.DataFrame) -> pd.DataFrame:
    return (
        listings.groupby(COL_HOST_SEGMENT, observed=True)
        .agg(
            listing_count=(COL_LISTING_ID, "count"),
            host_count=("host_id", "nunique"),
            median_price=(COL_PRICE, "median"),
            mean_availability_rate=(COL_AVAILABILITY_RATE, "mean"),
            mean_occupancy_proxy=(COL_OCCUPANCY_PROXY, "mean"),
        )
        .round(3)
        .reset_index()
    )


def host_portfolio_summary(listings: pd.DataFrame) -> pd.DataFrame:
    hosts = listings.groupby("host_id").agg(listing_count=(COL_LISTING_ID, "count")).reset_index()
    return pd.DataFrame(
        {
            "metric": [
                "hosts",
                "listings",
                "single_listing_hosts",
                "hosts_with_2_plus_listings",
                "top_10_host_listing_share",
            ],
            "value": [
                len(hosts),
                int(hosts["listing_count"].sum()),
                int((hosts["listing_count"] == 1).sum()),
                int((hosts["listing_count"] >= 2).sum()),
                round(
                    hosts.nlargest(10, "listing_count")["listing_count"].sum() / len(listings), 4
                ),
            ],
        }
    )


def superhost_summary(listings: pd.DataFrame) -> pd.DataFrame:
    return (
        listings.dropna(subset=["host_is_superhost"])
        .groupby("host_is_superhost")
        .agg(
            listing_count=(COL_LISTING_ID, "count"),
            median_price=(COL_PRICE, "median"),
            mean_availability_rate=(COL_AVAILABILITY_RATE, "mean"),
            mean_review_score=("review_scores_rating", "mean"),
        )
        .round(3)
        .reset_index()
    )


def room_property_mix(listings: pd.DataFrame) -> pd.DataFrame:
    return (
        listings.groupby([COL_ROOM_TYPE, "property_type"], observed=True)
        .agg(
            listing_count=(COL_LISTING_ID, "count"),
            median_latitude=("latitude", "median"),
            median_longitude=("longitude", "median"),
        )
        .query("listing_count >= @MIN_NEIGHBOURHOOD_LISTINGS")
        .round(5)
        .reset_index()
        .sort_values("listing_count", ascending=False)
    )


def review_score_summary(listings: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in REVIEW_SCORE_COLUMNS:
        scores = listings[column].dropna()
        rows.append(
            {
                "score_column": column,
                "listing_count": len(scores),
                "mean": round(float(scores.mean()), 2) if not scores.empty else np.nan,
                "median": round(float(scores.median()), 2) if not scores.empty else np.nan,
                "share_at_4_9_or_above": round(float((scores >= 4.9).mean()), 4)
                if not scores.empty
                else np.nan,
                "share_at_5": round(float((scores == 5.0).mean()), 4)
                if not scores.empty
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def neighbourhood_review_score_summary(listings: pd.DataFrame) -> pd.DataFrame:
    return (
        listings.dropna(subset=["review_scores_rating"])
        .groupby(COL_NEIGHBOURHOOD)
        .agg(
            listing_count=(COL_LISTING_ID, "count"),
            mean_review_score=("review_scores_rating", "mean"),
            median_review_score=("review_scores_rating", "median"),
        )
        .query("listing_count >= @MIN_NEIGHBOURHOOD_LISTINGS")
        .round(2)
        .reset_index()
        .sort_values("mean_review_score", ascending=False)
    )


def high_review_low_score_profile(listings: pd.DataFrame) -> pd.DataFrame:
    scored = listings.dropna(subset=["review_scores_rating", "number_of_reviews"]).copy()
    if scored.empty:
        return pd.DataFrame()
    review_threshold = scored["number_of_reviews"].quantile(0.75)
    score_threshold = scored["review_scores_rating"].quantile(0.25)
    subset = scored[
        (scored["number_of_reviews"] >= review_threshold)
        & (scored["review_scores_rating"] <= score_threshold)
    ]
    return (
        subset.groupby([COL_ROOM_TYPE, COL_NEIGHBOURHOOD], observed=True)
        .agg(
            listing_count=(COL_LISTING_ID, "count"),
            median_price=(COL_PRICE, "median"),
            median_review_score=("review_scores_rating", "median"),
            median_review_count=("number_of_reviews", "median"),
        )
        .round(2)
        .reset_index()
        .sort_values("listing_count", ascending=False)
        .head(20)
    )


def monthly_availability_summary(calendar: pd.DataFrame) -> pd.DataFrame:
    return (
        calendar.groupby("month")
        .agg(
            listing_month_rows=(COL_LISTING_ID, "count"),
            mean_availability_rate=(COL_AVAILABILITY_RATE, "mean"),
            mean_occupancy_proxy=(COL_OCCUPANCY_PROXY, "mean"),
        )
        .round(4)
        .reset_index()
    )


def monthly_minimum_nights_summary(calendar: pd.DataFrame) -> pd.DataFrame:
    return (
        calendar.groupby("month")
        .agg(
            listing_month_rows=(COL_LISTING_ID, "count"),
            median_minimum_nights=("min_minimum_nights", "median"),
            p75_minimum_nights=("min_minimum_nights", lambda s: s.quantile(0.75)),
        )
        .round(2)
        .reset_index()
    )


def top_amenities(listings: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for raw in listings["amenities"].dropna():
        try:
            amenities = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            continue
        for amenity in amenities:
            label = str(amenity).strip()
            if label:
                counts[label] = counts.get(label, 0) + 1
    rows = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]
    return pd.DataFrame(rows, columns=["amenity", "listing_count"])


def coverage_table(listings: pd.DataFrame, snapshot_date: str) -> pd.DataFrame:
    host_tenure_available = int(listings["host_tenure_years"].notna().sum())
    host_response_available = int(listings["host_response_rate"].notna().sum())
    return pd.DataFrame(
        [
            (
                "price distribution and log-price distribution",
                "completed",
                "price and price_log are available",
            ),
            (
                "price by room type and property type",
                "completed",
                "room_type and property_type are available",
            ),
            (
                "price by neighbourhood with minimum sample threshold",
                "completed",
                f"N >= {MIN_NEIGHBOURHOOD_LISTINGS}",
            ),
            (
                "listing and host portfolio concentration",
                "completed",
                "host_id and portfolio_size are available",
            ),
            (
                "review-score distribution and subdimensions",
                "completed",
                "review score fields are available in staged detailed listings",
            ),
            (
                "availability by month",
                "completed",
                "calendar_agg.parquet provides month-level availability",
            ),
            (
                "neighbourhood listing density and price map",
                "completed",
                "GeoJSON and listing coordinates are available",
            ),
            ("neighbourhood review-score table", "completed", "review score fields are available"),
            (
                "geographic mix of room types and property types",
                "completed",
                "room type and top property type geography figures generated",
            ),
            (
                "price versus approximate distance to centre",
                "completed",
                "distance_to_centre_km is available",
            ),
            (
                "host tenure versus price",
                "unavailable",
                f"host_tenure_years populated rows: {host_tenure_available}",
            ),
            (
                "newer-versus-established host comparison",
                "unavailable",
                f"host_since is fully null for snapshot {snapshot_date}",
            ),
            (
                "host segment versus price and availability",
                "completed",
                "host_segment and availability_rate are available",
            ),
            (
                "host response rate versus listing performance",
                "unavailable",
                f"host_response_rate populated rows: {host_response_available}",
            ),
            (
                "superhost status versus listing performance",
                "completed",
                "host_is_superhost is available in staged detailed listings",
            ),
            (
                "review frequency versus price and review score",
                "completed",
                "review_frequency is available as a demand signal proxy only",
            ),
            (
                "high-review, low-score listing profile",
                "completed",
                "profile table generated from review count and score quartiles",
            ),
            (
                "review volume trend over available dates",
                "completed",
                "reviews_summary.csv provides review dates",
            ),
            (
                "minimum-night policy by month",
                "completed",
                "calendar_agg.parquet provides monthly minimum-night summaries",
            ),
            ("event-level analysis", "unavailable", "no external event data was introduced"),
        ],
        columns=["analysis", "status", "reason"],
    )


def write_coverage_report(
    listings: pd.DataFrame,
    city_key: str,
    snapshot_date: str,
    output_dir: Path,
) -> Path:
    coverage = coverage_table(listings, snapshot_date)
    path = output_dir / "eda_coverage.md"
    lines = [
        "# EDA Coverage",
        "",
        f"City: {city_key}",
        f"Snapshot date: {snapshot_date}",
        "",
        "| Analysis | Status | Reason |",
        "|---|---|---|",
    ]
    lines.extend(
        f"| {row.analysis} | {row.status} | {row.reason} |"
        for row in coverage.itertuples(index=False)
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def plot_price_distribution(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    usable = _usable_price_rows(listings)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].hist(usable[COL_PRICE], bins=40, color="#2E86AB", edgecolor="white")
    axes[0].set_title("Raw nightly price")
    axes[0].set_xlabel("nightly price")
    axes[0].set_ylabel("listing count")
    axes[1].hist(usable[COL_PRICE_LOG], bins=40, color="#F18F01", edgecolor="white")
    axes[1].set_title("Log nightly price")
    axes[1].set_xlabel("log(nightly price)")
    axes[1].set_ylabel("listing count")
    fig.suptitle(f"{city} - price distribution - snapshot {snapshot_date} - N={len(usable):,}")
    _add_note(fig, "Log scale is shown because raw price is right-skewed.")
    return _save_figure(fig, output_dir / "eda_price_distribution.png")


def plot_price_by_room_type(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    usable = _usable_price_rows(listings)
    groups = [
        group[COL_PRICE_LOG].dropna() for _, group in usable.groupby(COL_ROOM_TYPE, observed=True)
    ]
    labels = [
        f"{room}\nN={len(group):,}" for room, group in usable.groupby(COL_ROOM_TYPE, observed=True)
    ]
    fig, ax = plt.subplots()
    ax.boxplot(groups, labels=labels, showfliers=False)
    ax.set_title(f"{city} - log price by room type - snapshot {snapshot_date}")
    ax.set_ylabel("log(nightly price)")
    _add_note(fig, "Prices shown on log scale; raw price is right-skewed.")
    return _save_figure(fig, output_dir / "eda_price_by_room_type.png")


def plot_price_by_property_type(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    summary = property_type_summary(listings).head(15).sort_values("median_price")
    fig, ax = plt.subplots()
    ax.barh(summary["property_type"], summary["median_price"], color="#2E86AB")
    for idx, row in enumerate(summary.itertuples(index=False)):
        ax.text(row.median_price, idx, f"  N={row.listing_count}", va="center")
    ax.set_title(f"{city} - median price by property type - snapshot {snapshot_date}")
    ax.set_xlabel("median nightly price")
    return _save_figure(fig, output_dir / "eda_price_by_property_type.png")


def plot_price_by_neighbourhood(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    summary = neighbourhood_summary(listings).head(15).sort_values("median_price")
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(summary[COL_NEIGHBOURHOOD], summary["median_price"], color="#6A994E")
    for idx, row in enumerate(summary.itertuples(index=False)):
        ax.text(row.median_price, idx, f"  N={row.listing_count}", va="center")
    ax.set_title(f"{city} - median price by neighbourhood - snapshot {snapshot_date}")
    ax.set_xlabel("median nightly price")
    _add_note(
        fig,
        f"Only neighbourhoods with at least {MIN_NEIGHBOURHOOD_LISTINGS} price-usable listings.",
    )
    return _save_figure(fig, output_dir / "eda_price_by_neighbourhood.png")


def plot_host_portfolio_concentration(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    hosts = listings.groupby("host_id").agg(listing_count=(COL_LISTING_ID, "count")).reset_index()
    hosts = hosts.sort_values("listing_count", ascending=False).reset_index(drop=True)
    hosts["cumulative_listing_share"] = (
        hosts["listing_count"].cumsum() / hosts["listing_count"].sum()
    )
    fig, ax = plt.subplots()
    ax.plot(np.arange(1, len(hosts) + 1), hosts["cumulative_listing_share"], color="#A23B72")
    ax.set_title(f"{city} - host portfolio concentration - snapshot {snapshot_date}")
    ax.set_xlabel("hosts ranked by listing count")
    ax.set_ylabel("cumulative listing share")
    return _save_figure(fig, output_dir / "eda_host_portfolio_concentration.png")


def plot_host_portfolio_ccdf(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    counts = listings.groupby("host_id")[COL_LISTING_ID].count()
    values = np.sort(counts.unique())
    shares = [(counts >= value).mean() for value in values]
    fig, ax = plt.subplots()
    ax.loglog(values, shares, marker="o", linestyle="-", color="#2E86AB")
    ax.set_title(f"{city} - listing count per host CCDF - snapshot {snapshot_date}")
    ax.set_xlabel("listings per host, log scale")
    ax.set_ylabel("share of hosts at or above count, log scale")
    _add_note(fig, "Log-log view assesses concentration shape; it does not prove a power law.")
    return _save_figure(fig, output_dir / "eda_host_portfolio_ccdf.png")


def plot_review_score_distribution(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    fig, ax = plt.subplots()
    for segment, group in listings.dropna(subset=["review_scores_rating"]).groupby(
        COL_HOST_SEGMENT, observed=True
    ):
        ax.hist(
            group["review_scores_rating"],
            bins=np.linspace(3.5, 5.0, 31),
            alpha=0.55,
            label=str(segment),
        )
    ax.set_title(f"{city} - review score distribution - snapshot {snapshot_date}")
    ax.set_xlabel("review score rating, 1-5 scale")
    ax.set_ylabel("listing count")
    ax.legend(title="host segment")
    _add_note(
        fig, "Ceiling concentration is a distribution pattern, not proof of rating inflation."
    )
    return _save_figure(fig, output_dir / "eda_review_score_distribution.png")


def plot_review_score_subdimensions(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    summary = review_score_summary(listings)
    fig, ax = plt.subplots(figsize=(11, 5))
    labels = summary["score_column"].str.replace("review_scores_", "", regex=False)
    ax.bar(labels, summary["median"], color="#F18F01")
    ax.set_ylim(4.0, 5.05)
    ax.set_title(f"{city} - review score subdimensions - snapshot {snapshot_date}")
    ax.set_ylabel("median score, 1-5 scale")
    ax.tick_params(axis="x", rotation=30)
    _add_note(
        fig, "High scores near 5 show concentration only; they do not prove inflated ratings."
    )
    return _save_figure(fig, output_dir / "eda_review_score_subdimensions.png")


def plot_monthly_availability(
    calendar: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    summary = monthly_availability_summary(calendar)
    fig, ax = plt.subplots()
    x = pd.to_datetime(summary["month"], format="%Y-%m")
    ax.plot(x, summary["mean_availability_rate"], marker="o", label=COL_AVAILABILITY_RATE)
    ax.plot(x, summary["mean_occupancy_proxy"], marker="o", label=COL_OCCUPANCY_PROXY)
    ax.set_title(f"{city} - monthly availability - snapshot {snapshot_date}")
    ax.set_xlabel("calendar month")
    ax.set_ylabel("mean rate")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    _add_note(fig, EDA_CAVEATS[COL_OCCUPANCY_PROXY])
    return _save_figure(fig, output_dir / "eda_monthly_availability.png")


def plot_listing_supply_map(
    listings: pd.DataFrame, city_key: str, snapshot_date: str, output_dir: Path
) -> Path:
    fig, ax = plt.subplots(figsize=(8, 8))
    _draw_geojson_boundaries(ax, city_key, snapshot_date)
    for room_type, group in listings.groupby(COL_ROOM_TYPE, observed=True):
        ax.scatter(
            group["longitude"],
            group["latitude"],
            s=5,
            alpha=0.45,
            label=str(room_type),
            color=ROOM_TYPE_COLOURS.get(str(room_type), "#666666"),
        )
    ax.set_title(f"Amsterdam - listing geography by room type - snapshot {snapshot_date}")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.legend(markerscale=3)
    ax.text(0.03, 0.97, "N", transform=ax.transAxes, ha="center", va="top", weight="bold")
    return _save_figure(fig, output_dir / "eda_listing_supply_map.png")


def plot_property_type_geography(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    top_types = listings["property_type"].value_counts().head(6).index
    data = listings[listings["property_type"].isin(top_types)]
    fig, ax = plt.subplots(figsize=(8, 8))
    for property_type, group in data.groupby("property_type"):
        ax.scatter(
            group["longitude"], group["latitude"], s=5, alpha=0.35, label=str(property_type)
        )
    ax.set_title(f"{city} - top property-type geography - snapshot {snapshot_date}")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.legend(markerscale=3, fontsize=8)
    return _save_figure(fig, output_dir / "eda_property_type_geography.png")


def plot_price_vs_distance(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    usable = _usable_price_rows(listings).dropna(subset=["distance_to_centre_km", COL_PRICE_LOG])
    fig, ax = plt.subplots()
    for room_type, group in usable.groupby(COL_ROOM_TYPE, observed=True):
        ax.scatter(
            group["distance_to_centre_km"],
            group[COL_PRICE_LOG],
            s=8,
            alpha=0.35,
            label=str(room_type),
            color=ROOM_TYPE_COLOURS.get(str(room_type), "#666666"),
        )
        smooth = _rolling_trend(group, "distance_to_centre_km", COL_PRICE_LOG)
        ax.plot(smooth["x"], smooth["y"], color=ROOM_TYPE_COLOURS.get(str(room_type), "#666666"))
    ax.set_title(f"{city} - log price versus distance to centre - snapshot {snapshot_date}")
    ax.set_xlabel("approximate distance to centre, km")
    ax.set_ylabel("log(nightly price)")
    ax.legend()
    return _save_figure(fig, output_dir / "eda_price_vs_distance.png")


def plot_host_segment_performance(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    summary = host_segment_summary(listings)
    fig, ax = plt.subplots()
    x = np.arange(len(summary))
    width = 0.35
    ax.bar(x - width / 2, summary["median_price"], width, label="median price", color="#2E86AB")
    ax2 = ax.twinx()
    ax2.bar(
        x + width / 2,
        summary["mean_availability_rate"],
        width,
        label=COL_AVAILABILITY_RATE,
        color="#F18F01",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(summary[COL_HOST_SEGMENT].astype(str))
    ax.set_title(f"{city} - host segment price and availability - snapshot {snapshot_date}")
    ax.set_ylabel("median nightly price")
    ax2.set_ylabel("mean availability_rate")
    _add_note(fig, EDA_CAVEATS[COL_OCCUPANCY_PROXY])
    return _save_figure(fig, output_dir / "eda_host_segment_performance.png")


def plot_superhost_performance(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    summary = superhost_summary(listings)
    fig, ax = plt.subplots()
    labels = summary["host_is_superhost"].map({"true": "superhost", "false": "not superhost"})
    x = np.arange(len(summary))
    width = 0.35
    ax.bar(x - width / 2, summary["median_price"], width, color="#2E86AB", label="median price")
    ax2 = ax.twinx()
    ax2.bar(
        x + width / 2,
        summary["mean_review_score"],
        width,
        color="#6A994E",
        label="mean review score",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title(f"{city} - superhost price and score profile - snapshot {snapshot_date}")
    ax.set_ylabel("median nightly price")
    ax2.set_ylabel("mean review score, 1-5 scale")
    _add_note(fig, "Descriptive comparison only; no causal claim is made.")
    return _save_figure(fig, output_dir / "eda_superhost_performance.png")


def plot_review_frequency_relationships(
    listings: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    data = listings.dropna(subset=[COL_REVIEW_FREQUENCY, COL_PRICE_LOG, "review_scores_rating"])
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].scatter(
        data[COL_REVIEW_FREQUENCY], data[COL_PRICE_LOG], s=8, alpha=0.35, color="#2E86AB"
    )
    axes[0].set_xlabel("review_frequency")
    axes[0].set_ylabel("log(nightly price)")
    axes[1].scatter(
        data[COL_REVIEW_FREQUENCY], data["review_scores_rating"], s=8, alpha=0.35, color="#6A994E"
    )
    axes[1].set_xlabel("review_frequency")
    axes[1].set_ylabel("review score rating, 1-5 scale")
    fig.suptitle(f"{city} - review frequency relationships - snapshot {snapshot_date}")
    _add_note(fig, EDA_CAVEATS[COL_REVIEW_FREQUENCY])
    return _save_figure(fig, output_dir / "eda_review_frequency_relationships.png")


def plot_review_volume_trend(city_key: str, snapshot_date: str, output_dir: Path) -> Path:
    path = city_staged_dir(city_key, snapshot_date) / "reviews_summary.csv"
    reviews = pd.read_csv(path, usecols=["date"])
    reviews["month"] = (
        pd.to_datetime(reviews["date"], format="%Y-%m-%d", errors="coerce")
        .dt.to_period("M")
        .dt.to_timestamp()
    )
    summary = (
        reviews.dropna(subset=["month"]).groupby("month").size().reset_index(name="review_count")
    )
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(summary["month"], summary["review_count"], color="#A23B72")
    ax.set_title(f"Amsterdam - review volume trend - snapshot {snapshot_date}")
    ax.set_xlabel("review month")
    ax.set_ylabel("review count")
    ax.tick_params(axis="x", rotation=45)
    return _save_figure(fig, output_dir / "eda_review_volume_trend.png")


def plot_monthly_minimum_nights(
    calendar: pd.DataFrame, city: str, snapshot_date: str, output_dir: Path
) -> Path:
    summary = monthly_minimum_nights_summary(calendar)
    fig, ax = plt.subplots()
    x = pd.to_datetime(summary["month"], format="%Y-%m")
    ax.plot(x, summary["median_minimum_nights"], marker="o", label="median")
    ax.plot(x, summary["p75_minimum_nights"], marker="o", label="75th percentile")
    ax.set_title(f"{city} - monthly minimum-night policy - snapshot {snapshot_date}")
    ax.set_xlabel("calendar month")
    ax.set_ylabel("minimum nights")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    return _save_figure(fig, output_dir / "eda_monthly_minimum_nights.png")


def _usable_price_rows(listings: pd.DataFrame) -> pd.DataFrame:
    return listings[listings[COL_PRICE].notna() & (listings[COL_PRICE] > 0)].copy()


def _write_csv(df: pd.DataFrame, path: Path) -> Path:
    df.to_csv(path, index=False)
    return path


def _save_figure(fig: plt.Figure, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _add_note(fig: plt.Figure, text: str) -> None:
    fig.text(0.01, 0.01, text, ha="left", va="bottom", fontsize=8)


def _normalise_tf(raw: object) -> str | None:
    if pd.isna(raw):
        return None
    value = str(raw).strip().lower()
    if value == "t":
        return "true"
    if value == "f":
        return "false"
    return None


def _rolling_trend(group: pd.DataFrame, x_col: str, y_col: str) -> pd.DataFrame:
    ordered = group[[x_col, y_col]].dropna().sort_values(x_col)
    if len(ordered) < 20:
        return pd.DataFrame({"x": ordered[x_col], "y": ordered[y_col]})
    window = max(20, len(ordered) // 12)
    return pd.DataFrame(
        {
            "x": ordered[x_col],
            "y": ordered[y_col].rolling(window=window, center=True, min_periods=10).median(),
        }
    ).dropna()


def _draw_geojson_boundaries(ax: plt.Axes, city_key: str, snapshot_date: str) -> None:
    path = city_staged_dir(city_key, snapshot_date) / "neighbourhoods_geojson.geojson"
    if not path.exists():
        return
    geojson = json.loads(path.read_text(encoding="utf-8"))
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "Polygon":
            _draw_polygon(ax, geometry.get("coordinates", []))
        elif geometry.get("type") == "MultiPolygon":
            for polygon in geometry.get("coordinates", []):
                _draw_polygon(ax, polygon)


def _draw_polygon(ax: plt.Axes, polygon: list[object]) -> None:
    for ring in polygon:
        points = np.asarray(ring)
        if points.ndim == 2 and points.shape[1] >= 2:
            ax.plot(points[:, 0], points[:, 1], color="#333333", linewidth=0.4, alpha=0.5)
