#!/usr/bin/env python3
"""Download driver portraits from Wikimedia Commons into the database.

    python -m scripts.fetch_portraits            # only drivers without one
    python -m scripts.fetch_portraits --refresh  # re-fetch every driver
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from app.ingest.portraits import sync_driver_portraits  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch driver portraits")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch all drivers")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    init_db()
    with SessionLocal() as db:
        stats = sync_driver_portraits(db, only_missing=not args.refresh)

    print(
        f"\nchecked {stats['checked']} drivers -> "
        f"{stats['updated']} with portraits, {stats['missing']} without"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
