from __future__ import annotations

import argparse
import logging
import sys

from airbnb_intelligence.ingestion import run_ingestion


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
    sub.add_parser("transform", help="Clean, enrich, and write Parquet outputs")
    sub.add_parser("load", help="Build DuckDB star schema from processed Parquet")
    sub.add_parser("analyse", help="Run EDA, statistics, and ML experiment")
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

    raise NotImplementedError(f"'{args.command}' is not yet implemented.")


if __name__ == "__main__":
    try:
        main()
    except NotImplementedError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
