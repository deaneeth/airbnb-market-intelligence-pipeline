from __future__ import annotations

from pathlib import Path

import pytest

from airbnb_intelligence.config import (
    REQUIRED_FILE_KEYS,
    ConfigValidationError,
    load_config,
)


def _make_city_files(scheme: str = "https", duplicate_url: bool = False) -> dict:
    base = f"{scheme}://data.insideairbnb.com/netherlands/nh/amsterdam/2024-03-15"
    return {
        key: f"{base}/file.csv.gz" if duplicate_url else f"{base}/{key}.csv.gz"
        for key in REQUIRED_FILE_KEYS
    }


def _write_city_yaml(
    tmp_path: Path,
    *,
    snapshot_date: str = "2024-03-15",
    scheme: str = "https",
    duplicate_url: bool = False,
    extra_cities: dict | None = None,
    omit_top_field: str | None = None,
    omit_file_key: str | None = None,
) -> Path:
    import yaml

    files = _make_city_files(scheme=scheme, duplicate_url=duplicate_url)
    if omit_file_key is not None:
        del files[omit_file_key]

    amsterdam: dict = {
        "name": "Amsterdam",
        "country": "Netherlands",
        "snapshot_date": snapshot_date,
        "files": files,
    }
    if omit_top_field is not None:
        del amsterdam[omit_top_field]

    data: dict = {"cities": {"amsterdam": amsterdam}}
    if extra_cities:
        data["cities"].update(extra_cities)

    cfg = tmp_path / "cities.yml"
    cfg.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return cfg


def test_valid_config_loads(tmp_path: Path) -> None:
    configs = load_config(_write_city_yaml(tmp_path))
    assert "amsterdam" in configs
    assert configs["amsterdam"].name == "Amsterdam"
    assert configs["amsterdam"].snapshot_date == "2024-03-15"
    assert set(configs["amsterdam"].files.keys()) >= set(REQUIRED_FILE_KEYS)


def test_second_city_requires_no_code_changes(tmp_path: Path) -> None:
    base = "https://data.insideairbnb.com/ireland/leinster/dublin/2024-03-15"
    extra = {
        "dublin": {
            "name": "Dublin",
            "country": "Ireland",
            "snapshot_date": "2024-03-15",
            "files": {k: f"{base}/{k}.csv.gz" for k in REQUIRED_FILE_KEYS},
        }
    }
    configs = load_config(_write_city_yaml(tmp_path, extra_cities=extra))
    assert "amsterdam" in configs
    assert "dublin" in configs


@pytest.mark.parametrize("missing_field", ["name", "country", "snapshot_date", "files"])
def test_missing_top_level_field_raises(tmp_path: Path, missing_field: str) -> None:
    with pytest.raises(ConfigValidationError, match=missing_field):
        load_config(_write_city_yaml(tmp_path, omit_top_field=missing_field))


@pytest.mark.parametrize("missing_key", REQUIRED_FILE_KEYS)
def test_missing_required_file_key_raises(tmp_path: Path, missing_key: str) -> None:
    with pytest.raises(ConfigValidationError, match=missing_key):
        load_config(_write_city_yaml(tmp_path, omit_file_key=missing_key))


@pytest.mark.parametrize("bad_date", ["20240315", "2024/03/15", "march-2024", "", "2024-3-5"])
def test_invalid_snapshot_date_raises(tmp_path: Path, bad_date: str) -> None:
    with pytest.raises(ConfigValidationError, match="snapshot_date"):
        load_config(_write_city_yaml(tmp_path, snapshot_date=bad_date))


def test_non_https_url_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigValidationError, match="http"):
        load_config(_write_city_yaml(tmp_path, scheme="ftp"))


def test_duplicate_url_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigValidationError, match="duplicate"):
        load_config(_write_city_yaml(tmp_path, duplicate_url=True))


def test_missing_config_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.yml")
