from __future__ import annotations

import gzip
import json
from pathlib import Path
from urllib.error import HTTPError

import pandas as pd
import pytest

from airbnb_intelligence.config import REQUIRED_FILE_KEYS
from airbnb_intelligence.ingestion import IngestionError, count_rows, run_ingestion, sha256_file


def _write_config(tmp_path: Path, snapshot_date: str = "2026-06-15") -> Path:
    files = {
        key: f"https://example.test/{snapshot_date}/{key}.csv.gz" for key in REQUIRED_FILE_KEYS
    }
    files["neighbourhoods_geojson"] = (
        f"https://example.test/{snapshot_date}/neighbourhoods.geojson"
    )
    path = tmp_path / f"cities-{snapshot_date}.yml"
    lines = [
        "cities:",
        "  amsterdam:",
        "    name: Amsterdam",
        "    country: Netherlands",
        f'    snapshot_date: "{snapshot_date}"',
        "    files:",
    ]
    lines.extend(f'      {key}: "{url}"' for key, url in files.items())
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _download_fixture(url: str, destination: Path) -> None:
    if url.endswith(".geojson"):
        destination.write_text(
            '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{}}]}',
            encoding="utf-8",
        )
        return
    with gzip.open(destination, "wt", encoding="utf-8", newline="") as handle:
        handle.write("id,value\n1,a\n2,b\n")


def _manifest(staged_root: Path, snapshot_date: str = "2026-06-15") -> dict:
    path = staged_root / "amsterdam" / snapshot_date / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_checksum_stability(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    raw_root = tmp_path / "raw"
    staged_root = tmp_path / "staged"

    run_ingestion(
        config_path, raw_root=raw_root, staged_root=staged_root, download_fn=_download_fixture
    )
    raw_path = raw_root / "amsterdam" / "2026-06-15" / "listings_detailed.csv.gz"
    first_hash = sha256_file(raw_path)

    run_ingestion(
        config_path, raw_root=raw_root, staged_root=staged_root, download_fn=_download_fixture
    )

    assert sha256_file(raw_path) == first_hash


def test_existing_matching_file_is_skipped(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    raw_root = tmp_path / "raw"
    staged_root = tmp_path / "staged"
    calls: list[str] = []

    def download(url: str, destination: Path) -> None:
        calls.append(url)
        _download_fixture(url, destination)

    run_ingestion(config_path, raw_root=raw_root, staged_root=staged_root, download_fn=download)
    first_count = len(calls)
    run_ingestion(config_path, raw_root=raw_root, staged_root=staged_root, download_fn=download)

    statuses = {entry["status"] for entry in _manifest(staged_root)["files"]}
    assert len(calls) == first_count
    assert statuses == {"skipped"}


def test_failed_download_records_failed_status(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    raw_root = tmp_path / "raw"
    staged_root = tmp_path / "staged"

    def fail(url: str, destination: Path) -> None:
        raise HTTPError(url, 404, "not found", hdrs=None, fp=None)

    with pytest.raises(IngestionError):
        run_ingestion(
            config_path,
            raw_root=raw_root,
            staged_root=staged_root,
            download_fn=fail,
            backoff_seconds=0,
        )

    assert _manifest(staged_root)["files"][0]["status"] == "failed"
    metadata = pd.read_parquet(staged_root / "amsterdam" / "pipeline_runs.parquet")
    assert metadata.iloc[-1]["status"] == "failed"


def test_transient_failure_is_retried(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    attempts = {"count": 0}

    def download(url: str, destination: Path) -> None:
        if url.endswith("listings_detailed.csv.gz") and attempts["count"] == 0:
            attempts["count"] += 1
            raise HTTPError(url, 503, "temporarily unavailable", hdrs=None, fp=None)
        _download_fixture(url, destination)

    run_ingestion(
        config_path,
        raw_root=tmp_path / "raw",
        staged_root=tmp_path / "staged",
        download_fn=download,
        backoff_seconds=0,
    )

    assert attempts["count"] == 1


def test_metadata_records_success_status(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    staged_root = tmp_path / "staged"

    run_ingestion(
        config_path,
        raw_root=tmp_path / "raw",
        staged_root=staged_root,
        download_fn=_download_fixture,
    )

    metadata = pd.read_parquet(staged_root / "amsterdam" / "pipeline_runs.parquet")
    record = metadata.iloc[-1]
    row_counts = json.loads(record["row_counts"])
    assert record["status"] == "success"
    assert record["processing_status"] == "completed"
    assert record["validation_status"] == "not_started"
    assert row_counts["listings_detailed"] == 2
    assert (staged_root / "amsterdam" / "2026-06-15" / "listings_detailed.csv").exists()
    assert (staged_root / "amsterdam" / "2026-06-15" / "listings_summary.csv").exists()


def test_new_snapshot_uses_separate_directories(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    staged_root = tmp_path / "staged"

    run_ingestion(
        _write_config(tmp_path, "2026-06-15"),
        raw_root=raw_root,
        staged_root=staged_root,
        download_fn=_download_fixture,
    )
    run_ingestion(
        _write_config(tmp_path, "2026-09-15"),
        raw_root=raw_root,
        staged_root=staged_root,
        download_fn=_download_fixture,
    )

    assert (raw_root / "amsterdam" / "2026-06-15").is_dir()
    assert (raw_root / "amsterdam" / "2026-09-15").is_dir()
    assert (staged_root / "amsterdam" / "2026-06-15" / "manifest.json").exists()
    assert (staged_root / "amsterdam" / "2026-09-15" / "manifest.json").exists()


def test_changed_file_creates_versioned_raw_file(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    raw_root = tmp_path / "raw"
    staged_root = tmp_path / "staged"
    revision = {"value": "a"}

    def download(url: str, destination: Path) -> None:
        if url.endswith(".geojson"):
            _download_fixture(url, destination)
            return
        with gzip.open(destination, "wt", encoding="utf-8", newline="") as handle:
            handle.write(f"id,value\n1,{revision['value']}\n")

    run_ingestion(config_path, raw_root=raw_root, staged_root=staged_root, download_fn=download)
    revision["value"] = "b"
    (raw_root / "amsterdam" / "2026-06-15" / "listings_detailed.csv.gz").write_bytes(b"changed")

    run_ingestion(config_path, raw_root=raw_root, staged_root=staged_root, download_fn=download)

    raw_files = sorted((raw_root / "amsterdam" / "2026-06-15").glob("listings_detailed.*.csv.gz"))
    assert len(raw_files) == 1


def test_count_rows_handles_quoted_newlines(tmp_path: Path) -> None:
    csv_path = tmp_path / "quoted.csv"
    csv_path.write_text('id,description\n1,"line one\nline two"\n2,"plain"\n', encoding="utf-8")

    assert count_rows(csv_path) == 2
