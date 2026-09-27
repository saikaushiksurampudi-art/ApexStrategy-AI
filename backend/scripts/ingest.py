#!/usr/bin/env python3
"""CLI entry point for loading historical F1 data.

Examples
--------
    python -m scripts.ingest --seasons 2023 2024 2025
    python -m scripts.ingest --seasons 2025 --lap-rounds 18 19 20
    python -m scripts.ingest --seasons 2024 --no-pitstops --no-cache
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.ingest.ergast import ErgastClient  # noqa: E402
from app.ingest.pipeline import ingest_season  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest historical F1 data")
    parser.add_argument(
        "--seasons", type=int, nargs="+", default=settings.ingest_seasons,
        help="Seasons to ingest (default: INGEST_SEASONS from config)",
    )
    parser.add_argument("--no-pitstops", action="store_true", help="Skip pit-stop data")
    parser.add_argument(
        "--lap-rounds", type=int, nargs="*", default=None,
        help="Rounds of the LAST listed season to summarise lap times for",
    )
    parser.add_argument("--no-cache", action="store_true", help="Bypass the HTTP cache")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("ingest")

    init_db()
    totals: dict = {}
    with ErgastClient(use_cache=not args.no_cache) as client, SessionLocal() as db:
        for index, season in enumerate(args.seasons):
            is_last = index == len(args.seasons) - 1
            log.info("=== ingesting %s ===", season)
            stats = ingest_season(
                db,
                client,
                season,
                with_pitstops=not args.no_pitstops,
                lap_rounds=args.lap_rounds if is_last else None,
            )
            totals[season] = stats
            log.info("%s -> %s", season, stats)

    print("\nIngestion summary")
    print("-" * 52)
    for season, stats in totals.items():
        parts = ", ".join(f"{k}={v}" for k, v in stats.items())
        print(f"  {season}: {parts}")
    print(f"\nDatabase: {settings.database_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
