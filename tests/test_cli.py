from __future__ import annotations

from types import SimpleNamespace

from airbnb_intelligence import cli


def _city(key: str) -> SimpleNamespace:
    return SimpleNamespace(key=key, snapshot_date="2026-06-15")


def test_profile_without_city_runs_all_configured_cities(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "load_config", lambda _: {"amsterdam": _city("amsterdam")})
    monkeypatch.setattr(cli, "profile_city", lambda key, snapshot: calls.append((key, snapshot)))
    monkeypatch.setattr("sys.argv", ["airbnb-pipeline", "profile"])

    cli.main()

    assert calls == [("amsterdam", "2026-06-15")]


def test_run_command_executes_dependency_order(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli, "load_config", lambda _: {"amsterdam": _city("amsterdam")})
    monkeypatch.setattr(cli, "run_ingestion", lambda *_args, **_kwargs: calls.append("download"))
    monkeypatch.setattr(cli, "profile_city", lambda *_args: calls.append("profile"))
    monkeypatch.setattr(cli, "validate_city", lambda *_args: calls.append("validate"))
    monkeypatch.setattr(cli, "run_cleaning", lambda *_args, **_kwargs: calls.append("transform"))
    monkeypatch.setattr(cli, "run_enrichment", lambda *_args, **_kwargs: calls.append("enrich"))
    monkeypatch.setattr(cli, "run_database", lambda *_args, **_kwargs: calls.append("load"))
    monkeypatch.setattr(cli, "run_eda", lambda *_args, **_kwargs: calls.append("eda"))
    monkeypatch.setattr(
        cli, "run_statistics", lambda *_args, **_kwargs: calls.append("statistics")
    )
    monkeypatch.setattr(cli, "run_ml_experiment", lambda *_args, **_kwargs: calls.append("ml"))
    monkeypatch.setattr("sys.argv", ["airbnb-pipeline", "--city", "amsterdam", "run"])

    cli.main()

    assert calls == [
        "download",
        "profile",
        "validate",
        "transform",
        "enrich",
        "load",
        "eda",
        "statistics",
        "ml",
    ]
