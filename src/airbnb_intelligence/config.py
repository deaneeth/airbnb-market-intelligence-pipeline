from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml

REQUIRED_FILE_KEYS: Final[tuple[str, ...]] = (
    "listings_detailed",
    "listings_summary",
    "calendar",
    "reviews_detailed",
    "reviews_summary",
    "neighbourhoods",
    "neighbourhoods_geojson",
)

_SNAPSHOT_DATE_RE: re.Pattern[str] = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ALLOWED_URL_SCHEMES: frozenset[str] = frozenset({"http", "https"})


@dataclass(frozen=True)
class CityConfig:
    key: str
    name: str
    country: str
    snapshot_date: str
    files: dict[str, str]


class ConfigValidationError(ValueError):
    """Raised when the cities configuration fails validation."""


def load_config(config_path: str | Path = "configs/cities.yml") -> dict[str, CityConfig]:
    """
    Load and validate the cities configuration file.

    Raises ConfigValidationError on invalid content, FileNotFoundError if missing.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict) or "cities" not in raw:
        raise ConfigValidationError(
            f"Configuration file must contain a top-level 'cities' mapping: {path}"
        )

    cities_raw = raw["cities"]
    if not isinstance(cities_raw, dict) or not cities_raw:
        raise ConfigValidationError("'cities' must be a non-empty mapping of city keys.")

    return {key: _validate_city(key, entry) for key, entry in cities_raw.items()}


def _validate_city(key: str, entry: object) -> CityConfig:
    if not isinstance(entry, dict):
        raise ConfigValidationError(
            f"City '{key}': entry must be a mapping, got {type(entry)}"
        )

    for field in ("name", "country", "snapshot_date", "files"):
        if field not in entry:
            raise ConfigValidationError(
                f"City '{key}': missing required field '{field}'"
            )

    snapshot_date: str = entry["snapshot_date"]
    if not snapshot_date or not _SNAPSHOT_DATE_RE.match(snapshot_date):
        raise ConfigValidationError(
            f"City '{key}': snapshot_date must be YYYY-MM-DD, got '{snapshot_date}'"
        )

    files: object = entry["files"]
    if not isinstance(files, dict):
        raise ConfigValidationError(
            f"City '{key}': 'files' must be a mapping of key to URL"
        )

    _validate_file_urls(key, files)

    return CityConfig(
        key=key,
        name=str(entry["name"]),
        country=str(entry["country"]),
        snapshot_date=snapshot_date,
        files=dict(files),
    )


def _validate_file_urls(city_key: str, files: dict[str, object]) -> None:
    for required_key in REQUIRED_FILE_KEYS:
        if required_key not in files:
            raise ConfigValidationError(
                f"City '{city_key}': missing required file key '{required_key}'"
            )

    seen_urls: set[str] = set()
    for file_key, url in files.items():
        if not isinstance(url, str) or not url.strip():
            raise ConfigValidationError(
                f"City '{city_key}', file '{file_key}': URL must be a non-empty string"
            )

        scheme = url.split("://")[0].lower() if "://" in url else ""
        if scheme not in _ALLOWED_URL_SCHEMES:
            raise ConfigValidationError(
                f"City '{city_key}', file '{file_key}': URL must use http or https, got '{scheme}'"
            )

        if url in seen_urls:
            raise ConfigValidationError(
                f"City '{city_key}': duplicate URL for file key '{file_key}'"
            )
        seen_urls.add(url)
