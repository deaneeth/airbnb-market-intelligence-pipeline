from __future__ import annotations

import argparse
import logging

from airbnb_intelligence.cleaning import run_cleaning
from airbnb_intelligence.config import load_config
from airbnb_intelligence.database import run_database
from airbnb_intelligence.enrichment import run_enrichment
from airbnb_intelligence.ingestion import run_ingestion
from airbnb_intelligence.ml import run_ml_experiment
from airbnb_intelligence.profiling import profile_city
from airbnb_intelligence.reporting import run_eda
from airbnb_intelligence.statistics import run_statistics
from airbnb_intelligence.validation import validate_city


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="airbnb-pipeline",
        description="Inside Airbnb market intelligence pipeline",
    )
    parser.add_argument("--city", default=None, help="City key (default: all configured cities)")
    parser.add_argument("--config", default="configs/cities.yml", help="Path to cities.yml")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="Download raw city files and write manifest")
    sub.add_parser("profile", help="Profile staged files and generate quality report")
    sub.add_parser("validate", help="Run domain validation rules")
    sub.add_parser("transform", help="Clean staged files and write Parquet outputs")
    sub.add_parser("enrich", help="Add derived fields to the listings master table")
    sub.add_parser("load", help="Build DuckDB star schema from processed Parquet")
    sub.add_parser("analyse", help="Generate analysis figures, tests, and summary tables")
    sub.add_parser("run", help="Execute all steps in dependency order")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if args.command == "download":
        run_ingestion(args.config, city_key=args.city)
        return
    if args.command == "profile":
        for city in _selected_cities(args.config, args.city):
            profile_city(city.key, city.snapshot_date)
        return
    if args.command == "validate":
        for city in _selected_cities(args.config, args.city):
            validate_city(city.key, city.snapshot_date)
        return
    if args.command == "transform":
        run_cleaning(args.config, city_key=args.city)
        return
    if args.command == "enrich":
        run_enrichment(args.config, city_key=args.city)
        return
    if args.command == "load":
        run_database(args.config, city_key=args.city)
        return
    if args.command == "analyse":
        run_eda(args.config, city_key=args.city)
        run_statistics(args.config, city_key=args.city)
        run_ml_experiment(args.config, city_key=args.city)
        return
    if args.command == "run":
        run_ingestion(args.config, city_key=args.city)
        for city in _selected_cities(args.config, args.city):
            profile_city(city.key, city.snapshot_date)
            validate_city(city.key, city.snapshot_date)
        run_cleaning(args.config, city_key=args.city)
        run_enrichment(args.config, city_key=args.city)
        run_database(args.config, city_key=args.city)
        run_eda(args.config, city_key=args.city)
        run_statistics(args.config, city_key=args.city)
        run_ml_experiment(args.config, city_key=args.city)
        return


def _selected_cities(config_path: str, city_key: str | None):
    cities = load_config(config_path)
    return [cities[city_key]] if city_key else list(cities.values())


if __name__ == "__main__":
    main()
