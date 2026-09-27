#!/usr/bin/env python3
"""Train the podium/points model and print its evaluation against baselines.

Examples
--------
    python -m scripts.train_model
    python -m scripts.train_model --train-seasons 2021 2022 2023 --test-seasons 2024
    python -m scripts.train_model --upload-s3
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.ml.train import run_training  # noqa: E402
from app.services.storage import upload_model_artifact  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the ApexStrategy podium model")
    parser.add_argument("--train-seasons", type=int, nargs="+", default=None)
    parser.add_argument("--test-seasons", type=int, nargs="+", default=None)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument(
        "--upload-s3", action="store_true",
        help="Also upload the artifact to the configured S3 bucket",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    init_db()
    with SessionLocal() as db:
        outcome = run_training(
            db,
            train_seasons=args.train_seasons,
            test_seasons=args.test_seasons,
            output_path=args.output,
        )

    print()
    print(outcome["summary"])
    print(f"\nArtifact : {outcome['model_path']}")
    print(f"Report   : {outcome['report_path']}")

    if args.upload_s3:
        if not settings.s3_bucket:
            print("\nS3_BUCKET is not configured -- skipping upload.")
        else:
            key = upload_model_artifact(outcome["model_path"], outcome["version"])
            print(f"Uploaded : s3://{settings.s3_bucket}/{key}" if key else "Upload failed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
