from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor
from sklearn.metrics import r2_score

from airbnb_intelligence.ml import (
    FEATURE_COLUMNS,
    RESULT_COLUMNS,
    build_features,
    evaluate_predictions,
    preprocessor,
    split_features,
    validate_no_leakage,
)


def test_feature_build_excludes_leakage_columns() -> None:
    X, _, _, _ = build_features(_sample_frame())

    assert set(X.columns) == set(FEATURE_COLUMNS)
    with pytest.raises(ValueError, match="Forbidden leakage"):
        validate_no_leakage(["price", "room_type"])
    with pytest.raises(ValueError, match="Forbidden leakage"):
        validate_no_leakage(["availability_rate", "room_type"])


def test_train_test_split_has_no_listing_overlap() -> None:
    X, y, ids, metadata = build_features(_sample_frame())
    _, _, y_train, y_test, ids_train, ids_test, _, _ = split_features(X, y, ids, metadata)

    assert set(ids_train).isdisjoint(set(ids_test))
    assert set(y_train.index).isdisjoint(set(y_test.index))


def test_median_baseline_r2_is_not_positive() -> None:
    _, y, _, _ = build_features(_sample_frame())
    train = y.iloc[:30]
    test = y.iloc[30:]
    baseline = DummyRegressor(strategy="median").fit(np.zeros((len(train), 1)), train)
    prediction = baseline.predict(np.zeros((len(test), 1)))

    assert r2_score(test, prediction) <= 0


def test_numeric_imputer_uses_training_data_only() -> None:
    X, _, _, _ = build_features(_sample_frame())
    X_train = X.iloc[:30].copy()
    X_test = X.iloc[30:].copy()
    X_test.loc[:, "bedrooms"] = 99.0

    fitted_train = preprocessor().fit(X_train)
    stats_train = fitted_train.named_transformers_["num"].named_steps["imputer"].statistics_.copy()
    fitted_combined = preprocessor().fit(pd.concat([X_train, X_test], ignore_index=True))
    stats_combined = fitted_combined.named_transformers_["num"].named_steps["imputer"].statistics_

    assert not np.array_equal(stats_train, stats_combined)


def test_result_schema_columns() -> None:
    empty = pd.DataFrame(columns=RESULT_COLUMNS)

    assert list(empty.columns) == RESULT_COLUMNS


def test_evaluate_predictions_returns_required_metrics() -> None:
    y_true = pd.Series(np.log([100.0, 120.0, 180.0]))
    y_pred = np.log([90.0, 130.0, 170.0])

    metrics = evaluate_predictions(y_true, y_pred)

    assert {
        "mae_log",
        "rmse_log",
        "r2_log",
        "mae_original",
        "rmse_original",
        "mape_original",
    } <= set(metrics)


def _sample_frame() -> pd.DataFrame:
    rows = []
    for i in range(50):
        price = 80 + i * 4
        rows.append(
            {
                "listing_id": i + 1,
                "price": float(price),
                "price_log": float(np.log(price)),
                "room_type": "entire home/apt" if i % 2 == 0 else "private room",
                "property_type": "Entire rental unit" if i % 3 else "Private room in rental unit",
                "bedrooms": np.nan if i in {3, 8} else 1.0 + (i % 3),
                "bathrooms": np.nan if i in {4, 9} else 1.0 + (i % 2),
                "accommodates": 2 + (i % 5),
                "minimum_nights": 1 + (i % 7),
                "distance_to_centre_km": 0.5 + (i % 10) / 2,
                "availability_rate": 0.1 + (i % 8) / 10,
                "host_is_superhost": "true" if i % 4 == 0 else "false",
                "neighbourhood_cleansed": f"N{i % 5}",
                "amenities": '["Wifi", "Kitchen", "Washer"]' if i % 2 == 0 else '["Heating"]',
            }
        )
    return pd.DataFrame(rows)
