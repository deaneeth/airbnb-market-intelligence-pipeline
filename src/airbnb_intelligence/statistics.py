from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import matplotlib
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.nonparametric.smoothers_lowess import lowess
from statsmodels.stats.outliers_influence import variance_inflation_factor

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from airbnb_intelligence.config import load_config
from airbnb_intelligence.enrichment import MIN_NEIGHBOURHOOD_LISTINGS
from airbnb_intelligence.utils import (
    COL_AVAILABILITY_RATE,
    COL_HOST_SEGMENT,
    COL_LISTING_ID,
    COL_NEIGHBOURHOOD,
    COL_PRICE,
    COL_PRICE_LOG,
    COL_ROOM_TYPE,
    FIGURES_DIR,
    TABLES_DIR,
    city_processed_dir,
    city_staged_dir,
    ensure_dirs,
)

if TYPE_CHECKING:
    from pathlib import Path


ALPHA: Final[float] = 0.05
BOOTSTRAP_REPS: Final[int] = 500
RANDOM_SEED: Final[int] = 42
REVIEW_SCORE_COL: Final[str] = "review_scores_rating"
SUPERHOST_COL: Final[str] = "host_is_superhost"
PROPERTY_TYPE_COL: Final[str] = "property_type"
BEDROOMS_COL: Final[str] = "bedrooms"
MINIMUM_NIGHTS_COL: Final[str] = "minimum_nights"
NEIGHBOURHOOD_GROUP_COL: Final[str] = "neighbourhood_group"
PROPERTY_TYPE_GROUP_COL: Final[str] = "property_type_group"
FITTED_COL: Final[str] = "fitted_log_price"
RESIDUAL_COL: Final[str] = "residual_log_price"
PRICE_DECILE_COL: Final[str] = "price_decile"
MODEL_MIN_GROUP_SIZE: Final[int] = MIN_NEIGHBOURHOOD_LISTINGS
LOWESS_FRACTION: Final[float] = 0.35
REQUIRED_RESULT_COLUMNS: Final[list[str]] = [
    "hypothesis_id",
    "business_question",
    "null_hypothesis",
    "alternative_hypothesis",
    "status",
    "unit_of_analysis",
    "sample_size",
    "exclusion_rules",
    "selected_test",
    "test_rationale",
    "assumption_diagnostics",
    "test_statistic",
    "test_statistic_name",
    "raw_p_value",
    "bh_adjusted_p_value",
    "bonferroni_adjusted_p_value",
    "confidence_interval_95",
    "effect_size",
    "effect_size_name",
    "plain_english_interpretation",
    "limitation_or_sensitivity",
]


@dataclass(frozen=True)
class StatisticsResult:
    city_key: str
    table_paths: list[Path]


def run_statistics(
    config_path: str | Path = "configs/cities.yml", city_key: str | None = None
) -> list[StatisticsResult]:
    cities = load_config(config_path)
    selected = [cities[city_key]] if city_key else list(cities.values())
    return [build_statistical_outputs(city.key, city.snapshot_date) for city in selected]


def build_statistical_outputs(city_key: str, snapshot_date: str) -> StatisticsResult:
    ensure_dirs(TABLES_DIR, FIGURES_DIR)
    listings = load_statistics_listings(city_key, snapshot_date)
    results = run_hypothesis_tests(listings)
    results_path = TABLES_DIR / "hypothesis_tests.csv"
    results.to_csv(results_path, index=False)

    room_ci_path = TABLES_DIR / "price_ci_by_room_type.csv"
    neighbourhood_ci_path = TABLES_DIR / "price_ci_by_neighbourhood.csv"
    ols_path = TABLES_DIR / "ols_price_model.csv"
    vif_path = TABLES_DIR / "ols_price_model_vif.csv"
    limitations_path = TABLES_DIR / "ols_price_model_limitations.csv"
    correlation_path = TABLES_DIR / "price_model_correlations.csv"
    strongest_path = TABLES_DIR / "price_model_strongest_correlations.csv"
    room_residual_path = TABLES_DIR / "ols_residuals_by_room_type.csv"
    neighbourhood_residual_path = TABLES_DIR / "ols_residuals_by_neighbourhood.csv"
    decile_residual_path = TABLES_DIR / "ols_residuals_by_price_decile.csv"

    price_ci_table(listings, COL_ROOM_TYPE).to_csv(room_ci_path, index=False)
    price_ci_table(listings, COL_NEIGHBOURHOOD).to_csv(neighbourhood_ci_path, index=False)
    write_price_model_diagnostics(
        listings,
        snapshot_date,
        ols_path,
        vif_path,
        limitations_path,
        correlation_path,
        strongest_path,
        room_residual_path,
        neighbourhood_residual_path,
        decile_residual_path,
    )

    return StatisticsResult(
        city_key=city_key,
        table_paths=[
            results_path,
            room_ci_path,
            neighbourhood_ci_path,
            ols_path,
            vif_path,
            limitations_path,
            correlation_path,
            strongest_path,
            room_residual_path,
            neighbourhood_residual_path,
            decile_residual_path,
        ],
    )


def load_statistics_listings(city_key: str, snapshot_date: str) -> pd.DataFrame:
    master = pd.read_parquet(city_processed_dir(city_key) / "listings_master.parquet")
    staged = city_staged_dir(city_key, snapshot_date) / "listings_detailed.csv"
    supplemental = pd.read_csv(
        staged,
        usecols=["id", SUPERHOST_COL, REVIEW_SCORE_COL, PROPERTY_TYPE_COL, BEDROOMS_COL],
    ).rename(columns={"id": COL_LISTING_ID})
    supplemental[SUPERHOST_COL] = supplemental[SUPERHOST_COL].map(_normalise_tf)
    return master.merge(supplemental, on=COL_LISTING_ID, how="left")


def run_hypothesis_tests(listings: pd.DataFrame) -> pd.DataFrame:
    rows = [
        _room_type_price_test(listings),
        _superhost_price_test(listings),
        _host_segment_price_test(listings),
        _weekday_weekend_unavailable(),
        _neighbourhood_price_test(listings),
        _availability_price_test(listings),
        _review_score_price_test(listings),
    ]
    _add_p_value_adjustments(rows)
    return pd.DataFrame(rows, columns=REQUIRED_RESULT_COLUMNS)


def apply_bh_correction(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    ranked = sorted((p, i) for i, p in enumerate(p_values))
    adjusted = [1.0] * len(p_values)
    running_min = 1.0
    total = len(p_values)
    for rank, (p_value, original_index) in reversed(list(enumerate(ranked, start=1))):
        running_min = min(running_min, p_value * total / rank)
        adjusted[original_index] = min(running_min, 1.0)
    return adjusted


def cohens_d(group_a: pd.Series, group_b: pd.Series) -> float:
    a = pd.to_numeric(group_a, errors="coerce").dropna()
    b = pd.to_numeric(group_b, errors="coerce").dropna()
    if len(a) < 2 or len(b) < 2:
        return math.nan
    pooled_var = ((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (
        len(a) + len(b) - 2
    )
    if pooled_var <= 0:
        return 0.0
    return float((a.mean() - b.mean()) / math.sqrt(pooled_var))


def rank_biserial_r(u_statistic: float, n_a: int, n_b: int) -> float:
    if n_a == 0 or n_b == 0:
        return math.nan
    return float((2 * u_statistic) / (n_a * n_b) - 1)


def eta_squared(kw_statistic: float, n_total: int, group_count: int) -> float:
    if n_total <= group_count:
        return math.nan
    return float(max(0.0, (kw_statistic - group_count + 1) / (n_total - group_count)))


def fit_price_model(listings: pd.DataFrame) -> pd.DataFrame:
    model_df = prepare_price_model_frame(listings)
    model = _fit_price_model(model_df)
    conf = model.conf_int(alpha=ALPHA)
    return pd.DataFrame(
        {
            "term": model.params.index,
            "marginal_association": model.params.values,
            "std_error_hc3": model.bse.values,
            "test_statistic": model.tvalues.values,
            "p_value": model.pvalues.values,
            "ci_lower": conf[0].values,
            "ci_upper": conf[1].values,
            "n_obs": int(model.nobs),
            "r_squared": model.rsquared,
            "adjusted_r_squared": model.rsquared_adj,
            "model_formula": _price_model_formula(),
            "interpretation_note": "Marginal associations in an observational cross-sectional model; not causal.",
        }
    ).round(6)


def prepare_price_model_frame(listings: pd.DataFrame) -> pd.DataFrame:
    required = _price_model_required_columns()
    missing = [column for column in required if column not in listings.columns]
    if missing:
        raise ValueError(f"Price model input is missing columns: {missing}")
    model_df = listings[required].copy()
    for column in [
        COL_PRICE_LOG,
        COL_PRICE,
        BEDROOMS_COL,
        MINIMUM_NIGHTS_COL,
        REVIEW_SCORE_COL,
        COL_AVAILABILITY_RATE,
        "distance_to_centre_km",
    ]:
        model_df[column] = pd.to_numeric(model_df[column], errors="coerce")
    model_df = model_df.dropna()
    model_df = model_df[(model_df[COL_PRICE] > 0) & (model_df[MINIMUM_NIGHTS_COL] >= 0)]
    model_df[PROPERTY_TYPE_GROUP_COL] = _group_sparse_categories(
        model_df[PROPERTY_TYPE_COL], "other property types"
    )
    model_df[NEIGHBOURHOOD_GROUP_COL] = _group_sparse_categories(
        model_df[COL_NEIGHBOURHOOD], "other neighbourhoods"
    )
    return model_df


def correlation_matrix(listings: pd.DataFrame) -> pd.DataFrame:
    model_df = prepare_price_model_frame(listings)
    numeric_cols = [
        COL_PRICE_LOG,
        COL_PRICE,
        BEDROOMS_COL,
        MINIMUM_NIGHTS_COL,
        REVIEW_SCORE_COL,
        COL_AVAILABILITY_RATE,
        "distance_to_centre_km",
    ]
    return model_df[numeric_cols].corr(method="pearson").round(6)


def strongest_price_correlations(listings: pd.DataFrame) -> pd.DataFrame:
    corr = correlation_matrix(listings)
    rows = []
    for feature, value in corr[COL_PRICE_LOG].drop(labels=[COL_PRICE_LOG, COL_PRICE]).items():
        rows.append(
            {
                "feature": feature,
                "pearson_correlation_with_log_price": value,
                "absolute_correlation": abs(value),
                "interpretation_note": "Correlation is an association and does not establish a causal relationship.",
            }
        )
    return pd.DataFrame(rows).sort_values("absolute_correlation", ascending=False)


def model_vif_table(listings: pd.DataFrame) -> pd.DataFrame:
    model_df = prepare_price_model_frame(listings)
    model = _fit_price_model(model_df)
    exog = model.model.exog
    rows = []
    for index, name in enumerate(model.model.exog_names):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            value = variance_inflation_factor(exog, index)
        rows.append(
            {
                "term": name,
                "vif": round(float(value), 4),
                "warning": _vif_warning(name, value),
            }
        )
    return pd.DataFrame(rows)


def residual_summary(
    listings: pd.DataFrame,
    group_col: str,
) -> pd.DataFrame:
    residuals = price_model_residuals(listings)
    grouped = residuals.groupby(group_col, observed=True)[RESIDUAL_COL]
    return (
        grouped.agg(
            row_count="count",
            mean_residual="mean",
            median_residual="median",
            residual_std="std",
        )
        .reset_index()
        .round(6)
        .sort_values("row_count", ascending=False)
    )


def price_model_residuals(listings: pd.DataFrame) -> pd.DataFrame:
    model_df = prepare_price_model_frame(listings)
    model = _fit_price_model(model_df)
    residuals = model_df[
        [
            COL_LISTING_ID,
            COL_PRICE,
            COL_PRICE_LOG,
            COL_ROOM_TYPE,
            COL_NEIGHBOURHOOD,
        ]
    ].copy()
    residuals[FITTED_COL] = model.fittedvalues
    residuals[RESIDUAL_COL] = model.resid
    residuals[PRICE_DECILE_COL] = pd.qcut(
        residuals[COL_PRICE],
        q=10,
        labels=[f"D{i}" for i in range(1, 11)],
        duplicates="drop",
    )
    return residuals


def model_limitations_table(listings: pd.DataFrame) -> pd.DataFrame:
    model_df = prepare_price_model_frame(listings)
    return pd.DataFrame(
        [
            {
                "topic": "Complete-case filtering",
                "detail": f"Model uses {len(model_df)} rows from {len(listings)} listings after required fields are non-null.",
                "consequence": "Rows with missing bedrooms, review score, superhost flag, price, or model features are excluded.",
            },
            {
                "topic": "Observational design",
                "detail": "The model is cross-sectional for one Amsterdam snapshot.",
                "consequence": "Coefficients are marginal associations, not causal effects.",
            },
            {
                "topic": "Availability field",
                "detail": "availability_rate is host-set availability.",
                "consequence": "It is not confirmed booked nights and may be jointly determined with listing strategy.",
            },
            {
                "topic": "Neighbourhood categories",
                "detail": f"Neighbourhood fixed effects are kept when they have at least {MODEL_MIN_GROUP_SIZE} model rows.",
                "consequence": "Sparse neighbourhoods are grouped to avoid unstable category estimates.",
            },
            {
                "topic": "Omitted attributes",
                "detail": "Amenities, exact property size, event demand, and regulation context are not in the model.",
                "consequence": "Estimated associations can reflect unobserved listing and location differences.",
            },
        ]
    )


def write_price_model_diagnostics(
    listings: pd.DataFrame,
    snapshot_date: str,
    ols_path: Path,
    vif_path: Path,
    limitations_path: Path,
    correlation_path: Path,
    strongest_path: Path,
    room_residual_path: Path,
    neighbourhood_residual_path: Path,
    decile_residual_path: Path,
) -> None:
    fit_price_model(listings).to_csv(ols_path, index=False)
    model_vif_table(listings).to_csv(vif_path, index=False)
    model_limitations_table(listings).to_csv(limitations_path, index=False)
    correlation_matrix(listings).to_csv(correlation_path)
    strongest = strongest_price_correlations(listings)
    strongest.to_csv(strongest_path, index=False)
    residual_summary(listings, COL_ROOM_TYPE).to_csv(room_residual_path, index=False)
    residual_summary(listings, COL_NEIGHBOURHOOD).to_csv(neighbourhood_residual_path, index=False)
    residual_summary(listings, PRICE_DECILE_COL).to_csv(decile_residual_path, index=False)
    residuals = price_model_residuals(listings)
    _plot_residuals_vs_fitted(residuals, snapshot_date)
    plotted = 0
    for feature in strongest["feature"].head(3):
        if _has_enough_unique_values(listings, feature):
            _plot_lowess_relationship(listings, feature, snapshot_date)
            plotted += 1
    for feature in strongest["feature"].iloc[3:]:
        if plotted >= 3:
            break
        if _has_enough_unique_values(listings, feature):
            _plot_lowess_relationship(listings, feature, snapshot_date)
            plotted += 1


def _fit_price_model(model_df: pd.DataFrame) -> object:
    formula = (
        f"{COL_PRICE_LOG} ~ C({COL_ROOM_TYPE}) + C({PROPERTY_TYPE_GROUP_COL}) + "
        f"C({SUPERHOST_COL}) + C({NEIGHBOURHOOD_GROUP_COL}) + {BEDROOMS_COL} + "
        f"{MINIMUM_NIGHTS_COL} + {REVIEW_SCORE_COL} + {COL_AVAILABILITY_RATE} + "
        "distance_to_centre_km"
    )
    return smf.ols(formula=formula, data=model_df).fit(cov_type="HC3")


def _price_model_formula() -> str:
    return (
        f"{COL_PRICE_LOG} ~ C({COL_ROOM_TYPE}) + C({PROPERTY_TYPE_GROUP_COL}) + "
        f"C({SUPERHOST_COL}) + C({NEIGHBOURHOOD_GROUP_COL}) + {BEDROOMS_COL} + "
        f"{MINIMUM_NIGHTS_COL} + {REVIEW_SCORE_COL} + {COL_AVAILABILITY_RATE} + "
        "distance_to_centre_km"
    )


def _price_model_required_columns() -> list[str]:
    return [
        COL_LISTING_ID,
        COL_PRICE,
        COL_PRICE_LOG,
        COL_ROOM_TYPE,
        PROPERTY_TYPE_COL,
        BEDROOMS_COL,
        MINIMUM_NIGHTS_COL,
        REVIEW_SCORE_COL,
        SUPERHOST_COL,
        COL_AVAILABILITY_RATE,
        "distance_to_centre_km",
        COL_NEIGHBOURHOOD,
    ]


def _group_sparse_categories(values: pd.Series, other_label: str) -> pd.Series:
    counts = values.value_counts()
    keep = counts[counts >= MODEL_MIN_GROUP_SIZE].index
    return values.where(values.isin(keep), other_label)


def _vif_warning(name: str, value: float) -> str:
    if name == "Intercept":
        return "Intercept is not assessed as a predictor."
    if value > 10:
        return "VIF > 10"
    return ""


def _has_enough_unique_values(listings: pd.DataFrame, feature: str) -> bool:
    values = pd.to_numeric(listings[feature], errors="coerce").dropna()
    return values.nunique() >= 20


def _plot_residuals_vs_fitted(residuals: pd.DataFrame, snapshot_date: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(residuals[FITTED_COL], residuals[RESIDUAL_COL], s=8, alpha=0.25)
    ax.axhline(0, color="black", linewidth=1)
    ax.set_title(f"Residuals versus fitted log price - Amsterdam {snapshot_date}")
    ax.set_xlabel("Fitted log nightly price")
    ax.set_ylabel("Residual log nightly price")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "price_model_residuals_vs_fitted.png", dpi=160)
    plt.close(fig)


def _plot_lowess_relationship(listings: pd.DataFrame, feature: str, snapshot_date: str) -> None:
    model_df = prepare_price_model_frame(listings)
    plot_df = model_df[[feature, COL_PRICE_LOG]].dropna().sort_values(feature)
    if len(plot_df) > 5000:
        plot_df = plot_df.sample(5000, random_state=RANDOM_SEED).sort_values(feature)
    smooth_input = plot_df.groupby(feature, as_index=False)[COL_PRICE_LOG].mean()
    if len(smooth_input) < 5:
        return
    smoothed = lowess(
        smooth_input[COL_PRICE_LOG],
        smooth_input[feature],
        frac=LOWESS_FRACTION,
        return_sorted=True,
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(plot_df[feature], plot_df[COL_PRICE_LOG], s=8, alpha=0.18)
    ax.plot(smoothed[:, 0], smoothed[:, 1], color="#C0392B", linewidth=2, label="LOWESS smoother")
    ax.set_title(f"{feature} and log nightly price - Amsterdam {snapshot_date}")
    ax.set_xlabel(feature)
    ax.set_ylabel("Log nightly price")
    ax.legend()
    fig.tight_layout()
    safe_feature = feature.replace("_", "-")
    fig.savefig(FIGURES_DIR / f"price_model_lowess_{safe_feature}.png", dpi=160)
    plt.close(fig)


def price_ci_table(listings: pd.DataFrame, group_col: str) -> pd.DataFrame:
    usable = listings[[group_col, COL_PRICE]].dropna()
    rows = []
    for group, values in usable.groupby(group_col)[COL_PRICE]:
        if len(values) < MIN_NEIGHBOURHOOD_LISTINGS:
            continue
        ci_low, ci_high = _bootstrap_ci(values, np.median)
        rows.append(
            {
                "group": group,
                "listing_count": len(values),
                "median_price": round(float(values.median()), 2),
                "ci_method": f"bootstrap median, {BOOTSTRAP_REPS} resamples, seed {RANDOM_SEED}",
                "ci_lower": round(ci_low, 2),
                "ci_upper": round(ci_high, 2),
            }
        )
    return pd.DataFrame(rows).sort_values(["median_price", "listing_count"], ascending=False)


def _room_type_price_test(listings: pd.DataFrame) -> dict[str, object]:
    df = listings[[COL_ROOM_TYPE, COL_PRICE_LOG]].dropna()
    entire = df.loc[df[COL_ROOM_TYPE] == "entire home/apt", COL_PRICE_LOG]
    other = df.loc[df[COL_ROOM_TYPE] != "entire home/apt", COL_PRICE_LOG]
    return _welch_result(
        "H1",
        "Are entire homes priced differently from other room types?",
        "Mean log price is equal for entire homes and other room types.",
        "Mean log price differs between entire homes and other room types.",
        entire,
        other,
        "entire home/apt",
        "other room types",
        "listing",
        "Rows require positive listing price and room type.",
    )


def _superhost_price_test(listings: pd.DataFrame) -> dict[str, object]:
    df = listings[[SUPERHOST_COL, COL_PRICE_LOG]].dropna()
    superhost = df.loc[df[SUPERHOST_COL] == "true", COL_PRICE_LOG]
    non_superhost = df.loc[df[SUPERHOST_COL] == "false", COL_PRICE_LOG]
    return _welch_result(
        "H2",
        "Are superhost listings priced differently from non-superhost listings?",
        "Mean log price is equal for superhost and non-superhost listings.",
        "Mean log price differs between superhost and non-superhost listings.",
        superhost,
        non_superhost,
        "superhost",
        "non-superhost",
        "listing",
        "Rows require positive listing price and non-missing superhost flag.",
    )


def _host_segment_price_test(listings: pd.DataFrame) -> dict[str, object]:
    df = listings[[COL_HOST_SEGMENT, COL_PRICE_LOG]].dropna()
    professional = df.loc[df[COL_HOST_SEGMENT] == "professional", COL_PRICE_LOG]
    casual = df.loc[df[COL_HOST_SEGMENT] == "casual", COL_PRICE_LOG]
    return _welch_result(
        "H3",
        "Are professional-host listings priced differently from casual-host listings?",
        "Mean log price is equal for professional-host and casual-host listings.",
        "Mean log price differs between professional-host and casual-host listings.",
        professional,
        casual,
        "professional host",
        "casual host",
        "listing",
        "Rows require positive listing price and host segment.",
    )


def _weekday_weekend_unavailable() -> dict[str, object]:
    return _base_row(
        "H4",
        "Are weekend calendar prices higher than weekday calendar prices?",
        "Listing-level weekend and weekday calendar prices are equal.",
        "Listing-level weekend calendar prices are higher than weekday calendar prices.",
        "unavailable",
        "listing-day",
        0,
        "The staged Amsterdam calendar file has no calendar price column.",
        "Not run",
        "A paired listing-level comparison requires day-level calendar prices for both weekdays and weekends.",
        "Source schema inspected; no price field is available in calendar_agg or the staged calendar CSV.",
        limitation_or_sensitivity="No result is reported because substituting listing price would mix grains and overstate precision.",
    )


def _neighbourhood_price_test(listings: pd.DataFrame) -> dict[str, object]:
    df = listings[[COL_NEIGHBOURHOOD, COL_PRICE_LOG, COL_PRICE]].dropna()
    counts = df[COL_NEIGHBOURHOOD].value_counts()
    df = df[df[COL_NEIGHBOURHOOD].isin(counts[counts >= MIN_NEIGHBOURHOOD_LISTINGS].index)]
    groups = [group[COL_PRICE_LOG] for _, group in df.groupby(COL_NEIGHBOURHOOD)]
    if len(groups) < 2:
        return _base_row(
            "H5",
            "Do listing prices differ across neighbourhoods?",
            "Log price distributions are equal across eligible neighbourhoods.",
            "At least one eligible neighbourhood has a different log price distribution.",
            "unavailable",
            "listing",
            len(df),
            f"Rows require positive price and neighbourhood with N >= {MIN_NEIGHBOURHOOD_LISTINGS}.",
            "Kruskal-Wallis",
            "Omnibus comparison across more than two independent neighbourhood groups.",
            "Fewer than two eligible neighbourhood groups.",
        )
    statistic, p_value = stats.kruskal(*groups)
    spread_ci = _neighbourhood_median_spread_ci(df)
    effect = eta_squared(statistic, len(df), len(groups))
    return _base_row(
        "H5",
        "Do listing prices differ across neighbourhoods?",
        "Log price distributions are equal across eligible neighbourhoods.",
        "At least one eligible neighbourhood has a different log price distribution.",
        "completed",
        "listing",
        len(df),
        f"Rows require positive price and neighbourhood with N >= {MIN_NEIGHBOURHOOD_LISTINGS}.",
        "Kruskal-Wallis",
        "Price is right-skewed and the comparison has many neighbourhood groups.",
        f"{len(groups)} neighbourhoods included; independent listing-level comparison.",
        statistic,
        "H",
        p_value,
        f"bootstrap 95% CI for max-minus-min median price: [{spread_ci[0]:.2f}, {spread_ci[1]:.2f}]",
        effect,
        "epsilon-squared",
        "Eligible neighbourhoods show different listing-price distributions; this is descriptive, not causal.",
        "Omnibus test does not identify which neighbourhood pairs differ.",
    )


def _availability_price_test(listings: pd.DataFrame) -> dict[str, object]:
    return _spearman_result(
        listings,
        "H6",
        "Is host-set availability associated with listing price?",
        "There is no monotonic association between availability rate and log price.",
        "There is a monotonic association between availability rate and log price.",
        COL_AVAILABILITY_RATE,
        "Rows require positive listing price and non-missing availability_rate.",
        "availability_rate",
    )


def _review_score_price_test(listings: pd.DataFrame) -> dict[str, object]:
    return _spearman_result(
        listings,
        "H7",
        "Is review score associated with listing price?",
        "There is no monotonic association between review score and log price.",
        "There is a monotonic association between review score and log price.",
        REVIEW_SCORE_COL,
        "Rows require positive listing price and non-missing review score.",
        "review_scores_rating",
    )


def _welch_result(
    hypothesis_id: str,
    question: str,
    null: str,
    alternative: str,
    group_a: pd.Series,
    group_b: pd.Series,
    group_a_name: str,
    group_b_name: str,
    unit: str,
    exclusions: str,
) -> dict[str, object]:
    group_a = pd.to_numeric(group_a, errors="coerce").dropna()
    group_b = pd.to_numeric(group_b, errors="coerce").dropna()
    if len(group_a) < 2 or len(group_b) < 2:
        return _base_row(
            hypothesis_id,
            question,
            null,
            alternative,
            "unavailable",
            unit,
            len(group_a) + len(group_b),
            exclusions,
            "Welch t-test",
            "Independent two-group comparison on log listing price.",
            f"{group_a_name} N={len(group_a)}, {group_b_name} N={len(group_b)}.",
        )
    statistic, p_value = stats.ttest_ind(group_a, group_b, equal_var=False, nan_policy="omit")
    mann = stats.mannwhitneyu(group_a, group_b, alternative="two-sided")
    ci_low, ci_high = _welch_mean_difference_ci(group_a, group_b)
    effect = cohens_d(group_a, group_b)
    mean_diff = group_a.mean() - group_b.mean()
    direction = "higher" if mean_diff > 0 else "lower"
    return _base_row(
        hypothesis_id,
        question,
        null,
        alternative,
        "completed",
        unit,
        len(group_a) + len(group_b),
        exclusions,
        "Welch t-test on log price",
        "Welch test is used because group variances may differ.",
        _welch_diagnostics(group_a, group_b, group_a_name, group_b_name),
        statistic,
        "t",
        p_value,
        f"log-price mean difference {group_a_name} minus {group_b_name}: [{ci_low:.4f}, {ci_high:.4f}]",
        effect,
        "Cohen's d",
        f"{group_a_name} listings have {direction} mean log price than {group_b_name} listings; this is an association, not a causal effect.",
        f"Mann-Whitney sensitivity p-value: {mann.pvalue:.6g}.",
    )


def _spearman_result(
    listings: pd.DataFrame,
    hypothesis_id: str,
    question: str,
    null: str,
    alternative: str,
    feature_col: str,
    exclusions: str,
    feature_label: str,
) -> dict[str, object]:
    df = listings[[feature_col, COL_PRICE_LOG]].dropna()
    if len(df) < 3:
        return _base_row(
            hypothesis_id,
            question,
            null,
            alternative,
            "unavailable",
            "listing",
            len(df),
            exclusions,
            "Spearman correlation",
            "Monotonic association test.",
            "Fewer than three complete rows.",
        )
    statistic, p_value = stats.spearmanr(df[feature_col], df[COL_PRICE_LOG])
    ci_low, ci_high = _correlation_ci(statistic, len(df))
    direction = "positive" if statistic > 0 else "negative"
    return _base_row(
        hypothesis_id,
        question,
        null,
        alternative,
        "completed",
        "listing",
        len(df),
        exclusions,
        "Spearman correlation",
        "Robust rank-based test for monotonic association.",
        f"Complete-case listing-level rows: {len(df)}.",
        statistic,
        "rho",
        p_value,
        f"Spearman rho 95% CI: [{ci_low:.4f}, {ci_high:.4f}]",
        statistic,
        "Spearman rho",
        f"{feature_label} has a {direction} rank association with log price; this is not causal.",
        "Sensitivity is the rank-based method itself; it does not assume linearity.",
    )


def _base_row(
    hypothesis_id: str,
    question: str,
    null: str,
    alternative: str,
    status: str,
    unit: str,
    sample_size: int,
    exclusions: str,
    selected_test: str,
    rationale: str,
    diagnostics: str,
    statistic: float | None = None,
    statistic_name: str = "",
    p_value: float | None = None,
    confidence_interval: str = "",
    effect_size: float | None = None,
    effect_size_name: str = "",
    interpretation: str = "",
    limitation_or_sensitivity: str = "",
) -> dict[str, object]:
    return {
        "hypothesis_id": hypothesis_id,
        "business_question": question,
        "null_hypothesis": null,
        "alternative_hypothesis": alternative,
        "status": status,
        "unit_of_analysis": unit,
        "sample_size": sample_size,
        "exclusion_rules": exclusions,
        "selected_test": selected_test,
        "test_rationale": rationale,
        "assumption_diagnostics": diagnostics,
        "test_statistic": _round_or_blank(statistic),
        "test_statistic_name": statistic_name,
        "raw_p_value": _round_or_blank(p_value),
        "bh_adjusted_p_value": "",
        "bonferroni_adjusted_p_value": "",
        "confidence_interval_95": confidence_interval,
        "effect_size": _round_or_blank(effect_size),
        "effect_size_name": effect_size_name,
        "plain_english_interpretation": interpretation,
        "limitation_or_sensitivity": limitation_or_sensitivity,
    }


def _add_p_value_adjustments(rows: list[dict[str, object]]) -> None:
    tested = [
        (idx, float(row["raw_p_value"]))
        for idx, row in enumerate(rows)
        if row["raw_p_value"] != "" and not pd.isna(row["raw_p_value"])
    ]
    p_values = [p_value for _, p_value in tested]
    bh_values = apply_bh_correction(p_values)
    bonferroni_values = [min(p_value * len(p_values), 1.0) for p_value in p_values]
    for (idx, _), bh_value, bonferroni_value in zip(
        tested, bh_values, bonferroni_values, strict=True
    ):
        rows[idx]["bh_adjusted_p_value"] = round(bh_value, 8)
        rows[idx]["bonferroni_adjusted_p_value"] = round(bonferroni_value, 8)


def _welch_diagnostics(
    group_a: pd.Series,
    group_b: pd.Series,
    group_a_name: str,
    group_b_name: str,
) -> str:
    sample_a = group_a.sample(min(len(group_a), 5000), random_state=RANDOM_SEED)
    sample_b = group_b.sample(min(len(group_b), 5000), random_state=RANDOM_SEED)
    shapiro_a = stats.shapiro(sample_a).pvalue if len(sample_a) >= 3 else math.nan
    shapiro_b = stats.shapiro(sample_b).pvalue if len(sample_b) >= 3 else math.nan
    levene = stats.levene(group_a, group_b).pvalue
    return (
        f"{group_a_name} N={len(group_a)}, {group_b_name} N={len(group_b)}; "
        f"Shapiro p-values {shapiro_a:.4g}, {shapiro_b:.4g}; Levene p-value {levene:.4g}."
    )


def _welch_mean_difference_ci(group_a: pd.Series, group_b: pd.Series) -> tuple[float, float]:
    var_a = group_a.var(ddof=1)
    var_b = group_b.var(ddof=1)
    se = math.sqrt(var_a / len(group_a) + var_b / len(group_b))
    if se == 0:
        diff = float(group_a.mean() - group_b.mean())
        return diff, diff
    numerator = (var_a / len(group_a) + var_b / len(group_b)) ** 2
    denominator = (var_a / len(group_a)) ** 2 / (len(group_a) - 1) + (
        var_b / len(group_b)
    ) ** 2 / (len(group_b) - 1)
    df = numerator / denominator
    diff = group_a.mean() - group_b.mean()
    margin = stats.t.ppf(1 - ALPHA / 2, df) * se
    return float(diff - margin), float(diff + margin)


def _correlation_ci(rho: float, n: int) -> tuple[float, float]:
    if n <= 3 or abs(rho) >= 1:
        return float(rho), float(rho)
    z_value = np.arctanh(rho)
    margin = stats.norm.ppf(1 - ALPHA / 2) / math.sqrt(n - 3)
    return float(np.tanh(z_value - margin)), float(np.tanh(z_value + margin))


def _neighbourhood_median_spread_ci(df: pd.DataFrame) -> tuple[float, float]:
    rng = np.random.default_rng(RANDOM_SEED)
    spreads = []
    for _ in range(BOOTSTRAP_REPS):
        medians = []
        for _, group in df.groupby(COL_NEIGHBOURHOOD)[COL_PRICE]:
            sample = rng.choice(group.to_numpy(), size=len(group), replace=True)
            medians.append(float(np.median(sample)))
        spreads.append(max(medians) - min(medians))
    return float(np.percentile(spreads, 2.5)), float(np.percentile(spreads, 97.5))


def _bootstrap_ci(values: pd.Series, statistic: object) -> tuple[float, float]:
    rng = np.random.default_rng(RANDOM_SEED)
    array = values.dropna().to_numpy()
    estimates = [
        float(statistic(rng.choice(array, size=len(array), replace=True)))
        for _ in range(BOOTSTRAP_REPS)
    ]
    return float(np.percentile(estimates, 2.5)), float(np.percentile(estimates, 97.5))


def _normalise_tf(value: object) -> str | None:
    if value == "t":
        return "true"
    if value == "f":
        return "false"
    return None


def _round_or_blank(value: float | None) -> float | str:
    if value is None or pd.isna(value):
        return ""
    return round(float(value), 8)
