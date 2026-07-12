from __future__ import annotations

import gzip
import json
import shutil
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

from airbnb_intelligence.config import CityConfig, load_config
from airbnb_intelligence.utils import DATA_RAW, DATA_STAGED, get_logger

DownloadFn = Callable[[str, Path], None]

CHUNK_SIZE: Final[int] = 1024 * 1024
TRANSIENT_HTTP_STATUSES: Final[frozenset[int]] = frozenset({500, 502, 503, 504})
LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class ManifestEntry:
    city_key: str
    snapshot_date: str
    file_key: str
    source_url: str
    file_type: str
    local_raw_path: str
    local_staged_path: str
    download_timestamp_utc: str
    file_size_bytes: int
    sha256: str
    status: str
    row_count: int
    prior_snapshot_date: str | None = None
    prior_sha256: str | None = None


class IngestionError(RuntimeError):
    """Raised when a required source file cannot be ingested."""


def run_ingestion(
    config_path: str | Path = "configs/cities.yml",
    *,
    city_key: str | None = None,
    raw_root: Path = DATA_RAW,
    staged_root: Path = DATA_STAGED,
    download_fn: DownloadFn | None = None,
    retry_count: int = 3,
    backoff_seconds: float = 1.0,
) -> list[dict[str, object]]:
    configs = load_config(config_path)
    selected = [configs[city_key]] if city_key else list(configs.values())
    metadata: list[dict[str, object]] = []

    for city in selected:
        started = utc_now()
        run_id = str(uuid.uuid4())
        try:
            entries = ingest_city(
                city,
                raw_root=raw_root,
                staged_root=staged_root,
                download_fn=download_fn,
                retry_count=retry_count,
                backoff_seconds=backoff_seconds,
            )
            metadata.append(
                write_run_metadata(
                    city,
                    staged_root,
                    run_id,
                    "success",
                    started,
                    utc_now(),
                    {entry.file_key: entry.row_count for entry in entries},
                    None,
                )
            )
        except Exception as exc:
            metadata.append(
                write_run_metadata(
                    city,
                    staged_root,
                    run_id,
                    "failed",
                    started,
                    utc_now(),
                    {},
                    str(exc),
                )
            )
            raise

    return metadata


def ingest_city(
    city: CityConfig,
    *,
    raw_root: Path = DATA_RAW,
    staged_root: Path = DATA_STAGED,
    download_fn: DownloadFn | None = None,
    retry_count: int = 3,
    backoff_seconds: float = 1.0,
) -> list[ManifestEntry]:
    raw_dir = city_raw_dir_from_root(raw_root, city)
    staged_dir = city_staged_dir_from_root(staged_root, city)
    raw_dir.mkdir(parents=True, exist_ok=True)
    staged_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = staged_dir / "manifest.json"
    previous_manifest = read_manifest(manifest_path)
    entries: list[ManifestEntry] = []

    for file_key, source_url in city.files.items():
        raw_path = raw_dir / source_filename(source_url)
        staged_path = staged_dir / staged_filename(file_key, raw_path.name)
        prior = previous_manifest.get(file_key)

        if prior:
            prior_raw_path = Path(str(prior["local_raw_path"]))
            if prior_raw_path.exists():
                raw_path = prior_raw_path
                staged_path = staged_dir / staged_filename(file_key, raw_path.name)

        if raw_path.exists() and prior and sha256_file(raw_path) == prior["sha256"]:
            extract_or_copy(raw_path, staged_path)
            entry = manifest_entry(city, file_key, source_url, raw_path, staged_path, "skipped")
            LOGGER.info("Skipped %s for %s %s", file_key, city.key, city.snapshot_date)
        else:
            target_raw_path = raw_dir / source_filename(source_url)
            temp_path = target_raw_path.with_name(f"{target_raw_path.name}.download")
            try:
                download_with_retries(
                    source_url,
                    temp_path,
                    download_fn=download_fn,
                    retry_count=retry_count,
                    backoff_seconds=backoff_seconds,
                )
                raw_path = finalize_download(target_raw_path, temp_path, prior)
                staged_path = staged_dir / staged_filename(file_key, raw_path.name)
                extract_or_copy(raw_path, staged_path)
                entry = manifest_entry(
                    city,
                    file_key,
                    source_url,
                    raw_path,
                    staged_path,
                    "downloaded",
                    prior_version=find_prior_version(staged_root, city, file_key, raw_path),
                )
                LOGGER.info("Downloaded %s for %s %s", file_key, city.key, city.snapshot_date)
            except Exception as exc:
                failed = failed_entry(city, file_key, source_url, raw_path, staged_path, exc)
                write_manifest(manifest_path, [*entries, failed])
                LOGGER.error(
                    "Failed %s for %s %s: %s", file_key, city.key, city.snapshot_date, exc
                )
                raise IngestionError(
                    f"Failed to ingest {file_key} from {source_url}: {exc}"
                ) from exc

        entries.append(entry)

    write_manifest(manifest_path, entries)
    return entries


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {entry["file_key"]: entry for entry in raw["files"]}


def write_manifest(path: Path, entries: list[ManifestEntry]) -> None:
    payload = {
        "generated_at_utc": utc_now(),
        "files": [asdict(entry) for entry in entries],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def download_with_retries(
    source_url: str,
    destination: Path,
    *,
    download_fn: DownloadFn | None,
    retry_count: int,
    backoff_seconds: float,
) -> None:
    for attempt in range(1, retry_count + 1):
        try:
            (download_fn or stream_download)(source_url, destination)
            return
        except HTTPError as exc:
            if exc.code not in TRANSIENT_HTTP_STATUSES or attempt == retry_count:
                destination.unlink(missing_ok=True)
                raise
        except (TimeoutError, URLError):
            if attempt == retry_count:
                destination.unlink(missing_ok=True)
                raise
        time.sleep(backoff_seconds * (2 ** (attempt - 1)))


def stream_download(source_url: str, destination: Path) -> None:
    request = Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output, length=CHUNK_SIZE)


def finalize_download(
    target_raw_path: Path,
    temp_path: Path,
    prior: dict[str, object] | None,
) -> Path:
    new_sha = sha256_file(temp_path)
    if prior and target_raw_path.exists() and new_sha != prior["sha256"]:
        versioned_path = versioned_raw_path(target_raw_path, new_sha)
        shutil.move(str(temp_path), versioned_path)
        return versioned_path
    shutil.move(str(temp_path), target_raw_path)
    return target_raw_path


def versioned_raw_path(raw_path: Path, sha256: str) -> Path:
    name = raw_path.name
    if name.endswith(".csv.gz"):
        return raw_path.with_name(f"{name[:-7]}.{sha256[:12]}.csv.gz")
    if raw_path.suffix:
        return raw_path.with_name(f"{raw_path.stem}.{sha256[:12]}{raw_path.suffix}")
    return raw_path.with_name(f"{name}.{sha256[:12]}")


def extract_or_copy(raw_path: Path, staged_path: Path) -> None:
    if raw_path.suffix == ".gz":
        with gzip.open(raw_path, "rb") as source, staged_path.open("wb") as target:
            shutil.copyfileobj(source, target, length=CHUNK_SIZE)
    else:
        shutil.copy2(raw_path, staged_path)


def manifest_entry(
    city: CityConfig,
    file_key: str,
    source_url: str,
    raw_path: Path,
    staged_path: Path,
    status: str,
    prior_version: dict[str, str] | None = None,
) -> ManifestEntry:
    return ManifestEntry(
        city_key=city.key,
        snapshot_date=city.snapshot_date,
        file_key=file_key,
        source_url=source_url,
        file_type=file_type(raw_path),
        local_raw_path=relative_path(raw_path),
        local_staged_path=relative_path(staged_path),
        download_timestamp_utc=utc_now(),
        file_size_bytes=raw_path.stat().st_size,
        sha256=sha256_file(raw_path),
        status=status,
        row_count=count_rows(staged_path),
        prior_snapshot_date=prior_version["snapshot_date"] if prior_version else None,
        prior_sha256=prior_version["sha256"] if prior_version else None,
    )


def failed_entry(
    city: CityConfig,
    file_key: str,
    source_url: str,
    raw_path: Path,
    staged_path: Path,
    exc: Exception,
) -> ManifestEntry:
    return ManifestEntry(
        city_key=city.key,
        snapshot_date=city.snapshot_date,
        file_key=file_key,
        source_url=source_url,
        file_type=file_type(raw_path),
        local_raw_path=relative_path(raw_path),
        local_staged_path=relative_path(staged_path),
        download_timestamp_utc=utc_now(),
        file_size_bytes=raw_path.stat().st_size if raw_path.exists() else 0,
        sha256=sha256_file(raw_path) if raw_path.exists() else "",
        status="failed",
        row_count=0,
        prior_snapshot_date=None,
        prior_sha256=None,
    )


def write_run_metadata(
    city: CityConfig,
    staged_root: Path,
    run_id: str,
    status: str,
    started_at_utc: str,
    finished_at_utc: str,
    row_counts: dict[str, int],
    error_message: str | None,
) -> dict[str, object]:
    metadata_path = staged_root / city.key / "pipeline_runs.parquet"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, object] = {
        "run_id": run_id,
        "city_key": city.key,
        "snapshot_date": city.snapshot_date,
        "step": "ingestion",
        "status": status,
        "processing_status": "completed" if status == "success" else "failed",
        "validation_status": "not_started",
        "started_at_utc": started_at_utc,
        "finished_at_utc": finished_at_utc,
        "row_counts": json.dumps(row_counts, sort_keys=True),
        "output_paths": json.dumps(
            {
                "manifest": relative_path(
                    city_staged_dir_from_root(staged_root, city) / "manifest.json"
                )
            },
            sort_keys=True,
        ),
        "error_message": error_message,
    }
    frame = pd.DataFrame([record])
    if metadata_path.exists():
        frame = pd.concat([pd.read_parquet(metadata_path), frame], ignore_index=True)
    frame.to_parquet(metadata_path, index=False)
    return record


def count_rows(path: Path) -> int:
    if path.suffix.lower() == ".geojson":
        data = json.loads(path.read_text(encoding="utf-8"))
        return len(data.get("features", []))
    return int(sum(len(chunk) for chunk in pd.read_csv(path, chunksize=100_000)))


def source_filename(source_url: str) -> str:
    name = Path(source_url.split("?", 1)[0]).name
    if not name:
        raise IngestionError(f"Source URL has no filename: {source_url}")
    return name


def staged_filename(file_key: str, raw_name: str) -> str:
    if raw_name.endswith(".csv.gz") or raw_name.endswith(".csv"):
        return f"{file_key}.csv"
    if raw_name.endswith(".geojson"):
        return f"{file_key}.geojson"
    return f"{file_key}{Path(raw_name).suffix}"


def file_type(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".csv.gz"):
        return "csv.gz"
    return path.suffix.lower().lstrip(".")


def find_prior_version(
    staged_root: Path,
    city: CityConfig,
    file_key: str,
    raw_path: Path,
) -> dict[str, str] | None:
    current_sha = sha256_file(raw_path)
    city_dir = staged_root / city.key
    if not city_dir.exists():
        return None
    for manifest_path in sorted(city_dir.glob("*/manifest.json")):
        if manifest_path.parent.name == city.snapshot_date:
            continue
        for entry in read_manifest(manifest_path).values():
            if entry["file_key"] == file_key and entry["sha256"] == current_sha:
                return {"snapshot_date": str(entry["snapshot_date"]), "sha256": current_sha}
    return None


def city_raw_dir_from_root(root: Path, city: CityConfig) -> Path:
    return root / city.key / city.snapshot_date


def city_staged_dir_from_root(root: Path, city: CityConfig) -> Path:
    return root / city.key / city.snapshot_date


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
