from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from airbnb_intelligence.config import load_config
from airbnb_intelligence.utils import (
    COL_LISTING_ID,
    COL_NEIGHBOURHOOD,
    COL_PRICE,
    COL_PRICE_LOG,
    COL_ROOM_TYPE,
    REPORTS_DIR,
    TABLES_DIR,
    city_processed_dir,
    city_staged_dir,
    ensure_dirs,
)

if TYPE_CHECKING:
    from pathlib import Path


RANDOM_SEED: Final[int] = 42
TEST_SIZE: Final[float] = 0.2
CV_FOLDS: Final[int] = 5
PRICE_MAPE_FLOOR: Final[float] = 1.0
MIN_NEIGHBOURHOOD_ERROR_ROWS: Final[int] = 15
SUPERHOST_COL: Final[str] = "host_is_superhost"
PROPERTY_TYPE_COL: Final[str] = "property_type"
BEDROOMS_COL: Final[str] = "bedrooms"
BATHROOMS_COL: Final[str] = "bathrooms"
ACCOMMODATES_COL: Final[str] = "accommodates"
AMENITIES_COL: Final[str] = "amenities"
MINIMUM_NIGHTS_COL: Final[str] = "minimum_nights"
AMENITY_FLAGS: Final[tuple[str, ...]] = (
    "wifi",
    "kitchen",
    "washer",
    "air conditioning",
    "dedicated workspace",
    "free parking",
)
NUMERIC_FEATURES: Final[list[str]] = [
    BEDROOMS_COL,
    BATHROOMS_COL,
    ACCOMMODATES_COL,
    "minimum_nights_capped",
    "is_long_stay",
    "distance_to_centre_km",
    "amenity_count",
    *[f"amenity_{name.replace(' ', '_')}" for name in AMENITY_FLAGS],
]
CATEGORICAL_FEATURES: Final[list[str]] = [
    COL_ROOM_TYPE,
    PROPERTY_TYPE_COL,
    SUPERHOST_COL,
    COL_NEIGHBOURHOOD,
]
FEATURE_COLUMNS: Final[list[str]] = [*NUMERIC_FEATURES, *CATEGORICAL_FEATURES]
FORBIDDEN_FEATURES: Final[set[str]] = {
    "price_raw",
    COL_PRICE,
    COL_PRICE_LOG,
    "revenue_proxy",
    "occupancy_proxy",
    "availability_rate",
    COL_LISTING_ID,
    "host_id",
    "review_frequency",
}
RESULT_COLUMNS: Final[list[str]] = [
    "model_id",
    "model_name",
    "n_train",
    "n_test",
    "cv_mae_log_mean",
    "cv_mae_log_std",
    "cv_rmse_log_mean",
    "cv_rmse_log_std",
    "mae_log",
    "rmse_log",
    "r2_log",
    "mae_original",
    "rmse_original",
    "mape_original",
    "best_params",
]


@dataclass(frozen=True)
class MLExperimentResult:
    city_key: str
    table_paths: list[Path]
    model_card_path: Path


def run_ml_experiment(
    config_path: str | Path = "configs/cities.yml", city_key: str | None = None
) -> list[MLExperimentResult]:
    cities = load_config(config_path)
    selected = [cities[city_key]] if city_key else list(cities.values())
    return [build_ml_outputs(city.key, city.snapshot_date) for city in selected]


def build_ml_outputs(city_key: str, snapshot_date: str) -> MLExperimentResult:
    ensure_dirs(TABLES_DIR, REPORTS_DIR)
    frame = load_ml_frame(city_key, snapshot_date)
    X, y, ids, metadata = build_features(frame)
    X_train, X_test, y_train, y_test, _ids_train, ids_test, _meta_train, meta_test = (
        split_features(X, y, ids, metadata)
    )

    estimators = build_estimators()
    results: list[dict[str, object]] = []
    prediction_frames: dict[str, pd.DataFrame] = {}
    model_names: dict[str, str] = {}
    best_model_id = ""
    best_mae = float("inf")
    fitted_estimators: dict[str, Pipeline] = {}

    for model_id, model_name, estimator in estimators:
        model_names[model_id] = model_name
        fitted = estimator.fit(X_train, y_train)
        fitted_estimators[model_id] = fitted
        y_pred = fitted.predict(X_test)
        metrics = evaluate_predictions(y_test, y_pred)
        cv_metrics = cross_validate_model(estimator, X_train, y_train)
        results.append(
            {
                "model_id": model_id,
                "model_name": model_name,
                "n_train": len(X_train),
                "n_test": len(X_test),
                **cv_metrics,
                **metrics,
                "best_params": "{}",
            }
        )
        predictions = prediction_table(model_id, ids_test, y_test, y_pred, meta_test)
        prediction_frames[model_id] = predictions
        if metrics["mae_original"] < best_mae:
            best_mae = metrics["mae_original"]
            best_model_id = model_id

    results_path = TABLES_DIR / "ml_experiment_results.csv"
    predictions_path = TABLES_DIR / "ml_test_predictions.csv"
    error_room_path = TABLES_DIR / "ml_error_by_room_type.csv"
    error_neighbourhood_path = TABLES_DIR / "ml_error_by_neighbourhood.csv"
    importance_path = TABLES_DIR / "ml_feature_importance.csv"
    coefficient_path = TABLES_DIR / "ml_ridge_coefficients.csv"
    model_card_path = REPORTS_DIR / "ml_model_card.md"

    result_df = pd.DataFrame(results, columns=RESULT_COLUMNS).round(6)
    result_df.to_csv(results_path, index=False)
    best_predictions = prediction_frames[best_model_id]
    best_predictions.to_csv(predictions_path, index=False)
    error_slice(best_predictions, COL_ROOM_TYPE).to_csv(error_room_path, index=False)
    error_slice(best_predictions, COL_NEIGHBOURHOOD, MIN_NEIGHBOURHOOD_ERROR_ROWS).to_csv(
        error_neighbourhood_path, index=False
    )
    feature_importance_table(
        fitted_estimators[best_model_id], X_test, y_test, best_model_id, model_names[best_model_id]
    ).to_csv(importance_path, index=False)
    ridge_coefficients(fitted_estimators["M1"]).to_csv(coefficient_path, index=False)
    write_model_card(
        model_card_path,
        city_key,
        snapshot_date,
        len(X),
        len(X_train),
        len(X_test),
        best_model_id,
        result_df,
    )

    return MLExperimentResult(
        city_key=city_key,
        table_paths=[
            results_path,
            predictions_path,
            error_room_path,
            error_neighbourhood_path,
            importance_path,
            coefficient_path,
        ],
        model_card_path=model_card_path,
    )


def load_ml_frame(city_key: str, snapshot_date: str) -> pd.DataFrame:
    master = pd.read_parquet(city_processed_dir(city_key) / "listings_master.parquet")
    staged = city_staged_dir(city_key, snapshot_date) / "listings_detailed.csv"
    supplemental = pd.read_csv(
        staged,
        usecols=[
            "id",
            PROPERTY_TYPE_COL,
            BEDROOMS_COL,
            BATHROOMS_COL,
            ACCOMMODATES_COL,
            AMENITIES_COL,
            SUPERHOST_COL,
        ],
    ).rename(columns={"id": COL_LISTING_ID})
    supplemental[SUPERHOST_COL] = supplemental[SUPERHOST_COL].map(_normalise_tf)
    return master.merge(supplemental, on=COL_LISTING_ID, how="left")


def build_features(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.DataFrame]:
    data = frame.copy()
    data = data[data[COL_PRICE].notna() & (data[COL_PRICE] > 0) & data[COL_PRICE_LOG].notna()]
    data["minimum_nights_capped"] = pd.to_numeric(data[MINIMUM_NIGHTS_COL], errors="coerce").clip(
        upper=365
    )
    data["is_long_stay"] = (
        pd.to_numeric(data[MINIMUM_NIGHTS_COL], errors="coerce").fillna(0) > 365
    ).astype(int)
    amenities = data[AMENITIES_COL].apply(parse_amenities)
    data["amenity_count"] = amenities.map(len)
    for name in AMENITY_FLAGS:
        data[f"amenity_{name.replace(' ', '_')}"] = amenities.map(
            lambda values, amenity=name: int(amenity in values)
        )
    for column in NUMERIC_FEATURES:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    for column in CATEGORICAL_FEATURES:
        data[column] = data[column].fillna("unknown").astype(str)
    X = data[FEATURE_COLUMNS].copy()
    validate_no_leakage(X.columns)
    y = data[COL_PRICE_LOG].copy()
    ids = data[COL_LISTING_ID].copy()
    metadata = data[[COL_ROOM_TYPE, COL_NEIGHBOURHOOD, COL_PRICE]].copy()
    return X, y, ids, metadata


def split_features(
    X: pd.DataFrame,
    y: pd.Series,
    ids: pd.Series,
    metadata: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.Series,
    pd.Series,
    pd.Series,
    pd.Series,
    pd.DataFrame,
    pd.DataFrame,
]:
    split = train_test_split(
        X,
        y,
        ids,
        metadata,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
    )
    X_train, X_test, y_train, y_test, ids_train, ids_test, meta_train, meta_test = split
    overlap = set(ids_train).intersection(set(ids_test))
    if overlap:
        raise ValueError("Train/test split leaked listing_id values across sets.")
    return X_train, X_test, y_train, y_test, ids_train, ids_test, meta_train, meta_test


def build_estimators() -> list[tuple[str, str, Pipeline]]:
    return [
        ("M0", "Median price baseline", Pipeline([("model", DummyRegressor(strategy="median"))])),
        (
            "M1",
            "Regularised linear regression",
            Pipeline([("prep", preprocessor()), ("model", Ridge(alpha=1.0))]),
        ),
        (
            "M2",
            "Random forest regressor",
            Pipeline(
                [
                    ("prep", preprocessor()),
                    (
                        "model",
                        RandomForestRegressor(
                            n_estimators=100,
                            max_depth=12,
                            min_samples_leaf=3,
                            random_state=RANDOM_SEED,
                            n_jobs=-1,
                        ),
                    ),
                ]
            ),
        ),
        (
            "M3",
            "Histogram gradient boosting regressor",
            Pipeline(
                [
                    ("prep", preprocessor()),
                    (
                        "model",
                        HistGradientBoostingRegressor(
                            max_iter=150,
                            learning_rate=0.06,
                            max_leaf_nodes=31,
                            random_state=RANDOM_SEED,
                        ),
                    ),
                ]
            ),
        ),
    ]


def preprocessor() -> ColumnTransformer:
    numeric = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "onehot",
                OneHotEncoder(handle_unknown="ignore", min_frequency=15, sparse_output=False),
            ),
        ]
    )
    return ColumnTransformer(
        [
            ("num", numeric, NUMERIC_FEATURES),
            ("cat", categorical, CATEGORICAL_FEATURES),
        ]
    )


def cross_validate_model(
    estimator: Pipeline, X_train: pd.DataFrame, y_train: pd.Series
) -> dict[str, float]:
    cv = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    scores = cross_validate(
        estimator,
        X_train,
        y_train,
        cv=cv,
        scoring={
            "mae": "neg_mean_absolute_error",
            "rmse": "neg_root_mean_squared_error",
        },
        n_jobs=None,
    )
    return {
        "cv_mae_log_mean": float(-scores["test_mae"].mean()),
        "cv_mae_log_std": float(scores["test_mae"].std()),
        "cv_rmse_log_mean": float(-scores["test_rmse"].mean()),
        "cv_rmse_log_std": float(scores["test_rmse"].std()),
    }


def evaluate_predictions(y_true_log: pd.Series, y_pred_log: np.ndarray) -> dict[str, float]:
    y_true_price = np.exp(y_true_log)
    y_pred_price = np.exp(y_pred_log)
    mape_mask = y_true_price >= PRICE_MAPE_FLOOR
    return {
        "mae_log": float(mean_absolute_error(y_true_log, y_pred_log)),
        "rmse_log": float(mean_squared_error(y_true_log, y_pred_log) ** 0.5),
        "r2_log": float(r2_score(y_true_log, y_pred_log)),
        "mae_original": float(mean_absolute_error(y_true_price, y_pred_price)),
        "rmse_original": float(mean_squared_error(y_true_price, y_pred_price) ** 0.5),
        "mape_original": float(
            np.mean(
                np.abs(
                    (y_true_price[mape_mask] - y_pred_price[mape_mask]) / y_true_price[mape_mask]
                )
            )
        ),
    }


def prediction_table(
    model_id: str,
    ids: pd.Series,
    y_true_log: pd.Series,
    y_pred_log: np.ndarray,
    metadata: pd.DataFrame,
) -> pd.DataFrame:
    y_true_price = np.exp(y_true_log)
    y_pred_price = np.exp(y_pred_log)
    return pd.DataFrame(
        {
            "model_id": model_id,
            COL_LISTING_ID: ids.to_numpy(),
            "y_true_log": y_true_log.to_numpy(),
            "y_pred_log": y_pred_log,
            "y_true_price": y_true_price.to_numpy(),
            "y_pred_price": y_pred_price,
            "residual_price": y_true_price.to_numpy() - y_pred_price,
            COL_ROOM_TYPE: metadata[COL_ROOM_TYPE].to_numpy(),
            COL_NEIGHBOURHOOD: metadata[COL_NEIGHBOURHOOD].to_numpy(),
        }
    ).round(6)


def error_slice(predictions: pd.DataFrame, group_col: str, min_rows: int = 1) -> pd.DataFrame:
    rows = []
    for group, values in predictions.groupby(group_col):
        if len(values) < min_rows:
            continue
        rows.append(
            {
                group_col: group,
                "row_count": len(values),
                "mae_original": mean_absolute_error(
                    values["y_true_price"], values["y_pred_price"]
                ),
                "rmse_original": mean_squared_error(values["y_true_price"], values["y_pred_price"])
                ** 0.5,
                "mean_residual_price": values["residual_price"].mean(),
            }
        )
    return pd.DataFrame(rows).round(6).sort_values("mae_original", ascending=False)


def feature_importance_table(
    estimator: Pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    model_id: str,
    model_name: str,
) -> pd.DataFrame:
    result = permutation_importance(
        estimator,
        X_test,
        y_test,
        n_repeats=10,
        random_state=RANDOM_SEED,
        scoring="neg_mean_absolute_error",
    )
    rows = []
    for feature, mean, std in zip(
        X_test.columns, result.importances_mean, result.importances_std, strict=True
    ):
        rows.append(
            {
                "model_id": model_id,
                "model_name": model_name,
                "feature": feature,
                "permutation_importance_mean": mean,
                "permutation_importance_std": std,
                "interpretation_note": "Feature importance is predictive association, not causal evidence.",
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values("permutation_importance_mean", ascending=False)
        .head(15)
        .round(6)
    )


def ridge_coefficients(estimator: Pipeline) -> pd.DataFrame:
    prep = estimator.named_steps["prep"]
    model = estimator.named_steps["model"]
    names = prep.get_feature_names_out()
    return (
        pd.DataFrame(
            {
                "feature": names,
                "coefficient": model.coef_,
                "interpretation_note": "marginal association: cross-sectional coefficient, not causal evidence.",
            }
        )
        .assign(abs_coefficient=lambda df: df["coefficient"].abs())
        .sort_values("abs_coefficient", ascending=False)
        .head(30)
        .drop(columns=["abs_coefficient"])
        .round(6)
    )


def validate_no_leakage(columns: pd.Index | list[str]) -> None:
    leaked = FORBIDDEN_FEATURES.intersection(set(columns))
    if leaked:
        raise ValueError(f"Forbidden leakage features included: {sorted(leaked)}")


def parse_amenities(value: object) -> set[str]:
    if not isinstance(value, str) or not value.strip():
        return set()
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return set()
    if not isinstance(parsed, list):
        return set()
    return {str(item).lower() for item in parsed}


def write_model_card(
    path: Path,
    city_key: str,
    snapshot_date: str,
    n_rows: int,
    n_train: int,
    n_test: int,
    best_model_id: str,
    results: pd.DataFrame,
) -> None:
    best = results.loc[results["model_id"] == best_model_id].iloc[0]
    path.write_text(
        "\n".join(
            [
                "# Nightly Price Prediction Model Card",
                "",
                f"- **City**: {city_key}",
                f"- **Snapshot date**: {snapshot_date}",
                "- **Target**: `price_log`, the natural log of parsed nightly listing price.",
                f"- **Population**: {n_rows} price-usable listing rows before the train/test split.",
                f"- **Split**: reproducible listing-level train/test split with {n_train} train rows and {n_test} test rows.",
                "- **Success metrics**: MAE and RMSE on log and original price scales; MAPE is reported only where true price is at least 1.",
                "- **Leakage policy**: excludes identifiers, raw price, parsed price, log price as features, revenue_proxy, occupancy_proxy, availability_rate, and review_frequency.",
                "- **Features**: room type, property type, bedrooms, bathrooms, accommodates, capped minimum nights, long-stay flag, distance to centre, superhost flag, neighbourhood, amenity count, and six amenity flags.",
                "- **Amenity flags**: wifi, kitchen, washer, air conditioning, dedicated workspace, and free parking.",
                "- **Interactions**: none included; the experiment keeps feature engineering limited and interpretable.",
                f"- **Best test MAE on original price scale**: {best['mae_original']:.2f} from {best['model_name']}.",
                "- **Important caveat**: feature importance is predictive association, not causal evidence.",
                "- **Representation risk**: neighbourhood and room-type imbalance can make error uneven across groups; see the error-slice tables before using results in a report.",
                "- **Production warning**: one Amsterdam snapshot is not enough to claim production readiness or future generalisation.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _normalise_tf(value: object) -> str:
    if value == "t":
        return "true"
    if value == "f":
        return "false"
    return "unknown"
