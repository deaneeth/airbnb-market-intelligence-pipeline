from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Final

import pandas as pd

from airbnb_intelligence.ingestion import read_manifest
from airbnb_intelligence.utils import REPORTS_DIR, TABLES_DIR, ensure_dirs

PROFILE_CHUNK_ROWS: Final[int] = 50_000
SENSITIVE_COLUMNS: Final[tuple[str, ...]] = (
    "name",
    "url",
    "description",
    "comments",
    "license",
    "about",
    "picture",
)


def profile_city(
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

    profiles = {
        file_key: profile_file(file_key, Path(str(entry["local_staged_path"])))
        for file_key, entry in manifest.items()
    }
    payload = {
        "city_key": city_key,
        "snapshot_date": snapshot_date,
        "files": profiles,
    }
    write_profile_outputs(payload, reports_root)
    return payload


def profile_file(file_key: str, path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".geojson":
        return profile_geojson(file_key, path)
    return profile_csv(file_key, path)


def profile_csv(file_key: str, path: Path, *, chunk_rows: int = PROFILE_CHUNK_ROWS) -> dict[str, Any]:
    reader = pd.read_csv(path, chunksize=chunk_rows, low_memory=False)
    row_count = 0
    column_names: list[str] = []
    inferred_types: dict[str, str] = {}
    numeric_values: dict[str, list[float]] = {}
    top_values: dict[str, Counter[str]] = {}
    distinct_values: dict[str, set[str]] = {}
    null_count: dict[str, int] = {}

    for chunk in reader:
        if not column_names:
            column_names = list(chunk.columns)
            null_count = dict.fromkeys(column_names, 0)
            top_values = {column: Counter() for column in column_names}
            distinct_values = {column: set() for column in column_names}
            numeric_values = {column: [] for column in column_names}
            inferred_types = {column: str(chunk[column].dtype) for column in column_names}

        row_count += len(chunk)
        for column in column_names:
            series = chunk[column]
            null_count[column] += int(series.isna().sum())
            non_null = series.dropna()
            if non_null.empty:
                continue

            numeric = pd.to_numeric(
                non_null.astype(str).str.replace(r"[$,%]", "", regex=True).str.replace(",", ""),
                errors="coerce",
            ).dropna()
            if len(numeric) >= max(1, int(len(non_null) * 0.8)):
                numeric_values[column].extend(float(value) for value in numeric.tolist())
            elif not is_sensitive(column):
                top_values[column].update(non_null.astype(str).head(1000))

            if len(distinct_values[column]) <= 100_000:
                distinct_values[column].update(non_null.astype(str).head(100_000))

    return build_profile(
        file_key,
        row_count,
        column_names,
        inferred_types,
        null_count,
        distinct_values,
        numeric_values,
        top_values,
    )


def profile_geojson(file_key: str, path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features", [])
    property_names = sorted({key for feature in features for key in feature.get("properties", {})})
    rows = []
    for feature in features:
        row = {key: feature.get("properties", {}).get(key) for key in property_names}
        row["geometry_type"] = feature.get("geometry", {}).get("type")
        rows.append(row)
    frame = pd.DataFrame(rows)
    temp_path = path.with_suffix(".profile.tmp.csv")
    frame.to_csv(temp_path, index=False)
    try:
        return profile_csv(file_key, temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


def build_profile(
    file_key: str,
    row_count: int,
    column_names: list[str],
    inferred_types: dict[str, str],
    null_count: dict[str, int],
    distinct_values: dict[str, set[str]],
    numeric_values: dict[str, list[float]],
    top_values: dict[str, Counter[str]],
) -> dict[str, Any]:
    distinct_count = {column: len(values) for column, values in distinct_values.items()}
    return {
        "file_key": file_key,
        "row_count": row_count,
        "column_count": len(column_names),
        "column_names": column_names,
        "inferred_types": inferred_types,
        "null_count": null_count,
        "null_pct": {
            column: round(null_count[column] / row_count * 100, 4) if row_count else 0
            for column in column_names
        },
        "distinct_count": distinct_count,
        "uniqueness_ratio": {
            column: round(distinct_count[column] / row_count, 6) if row_count else 0
            for column in column_names
        },
        "numeric_summary": {
            column: numeric_summary(values)
            for column, values in numeric_values.items()
            if values
        },
        "top_categoricals": {
            column: dict(counter.most_common(5))
            for column, counter in top_values.items()
            if counter
        },
    }


def numeric_summary(values: list[float]) -> dict[str, float]:
    series = pd.Series(values)
    quantiles = series.quantile([0.25, 0.5, 0.75, 0.99])
    return {
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
        "median": float(quantiles.loc[0.5]),
        "p25": float(quantiles.loc[0.25]),
        "p75": float(quantiles.loc[0.75]),
        "p99": float(quantiles.loc[0.99]),
    }


def write_profile_outputs(payload: dict[str, Any], reports_root: Path) -> None:
    profile_dir = reports_root / "profiles" / payload["city_key"] / payload["snapshot_date"]
    ensure_dirs(profile_dir, TABLES_DIR)
    (profile_dir / "profile.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (reports_root / "data_quality_report.md").write_text(render_markdown_report(payload), encoding="utf-8")


def render_markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Data Quality Report",
        "",
        f"City: `{payload['city_key']}`",
        f"Snapshot date: `{payload['snapshot_date']}`",
        "",
        "## File Summary",
        "",
        "| File | Rows | Columns | Highest Null Column | Highest Null % |",
        "|---|---:|---:|---|---:|",
    ]
    for file_key, profile in payload["files"].items():
        null_pct = profile["null_pct"]
        worst_column = max(null_pct, key=null_pct.get) if null_pct else "n/a"
        lines.append(
            f"| `{file_key}` | {profile['row_count']} | {profile['column_count']} | "
            f"`{worst_column}` | {null_pct.get(worst_column, 0):.2f} |"
        )
    lines.extend(["", "## Highest-Risk Findings", ""])
    for file_key, profile in payload["files"].items():
        risks = sorted(profile["null_pct"].items(), key=lambda item: item[1], reverse=True)[:3]
        lines.append(f"### `{file_key}`")
        for column, pct in risks:
            lines.append(f"- `{column}` has {pct:.2f}% null values.")
        lines.append("")
    return "\n".join(lines)


def is_sensitive(column: str) -> bool:
    lowered = column.lower()
    return any(token in lowered for token in SENSITIVE_COLUMNS)
