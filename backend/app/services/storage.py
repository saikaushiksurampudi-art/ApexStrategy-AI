"""Amazon S3 helpers for datasets, model artifacts and exported reports.

Every function degrades gracefully: if the bucket is unset or the call fails,
it logs and returns None so that local development needs no AWS account.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def _client():
    try:
        import boto3

        return boto3.client("s3", region_name=settings.aws_region)
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("S3 client unavailable: %s", exc)
        return None


def upload_model_artifact(local_path: str, version: str) -> Optional[str]:
    """Upload a trained model, returning the S3 key on success."""
    if not settings.s3_bucket:
        return None
    client = _client()
    if client is None:
        return None
    key = f"{settings.s3_model_prefix}{version}/{Path(local_path).name}"
    try:
        client.upload_file(local_path, settings.s3_bucket, key)
        logger.info("uploaded model to s3://%s/%s", settings.s3_bucket, key)
        return key
    except Exception as exc:  # pragma: no cover
        logger.error("model upload failed: %s", exc)
        return None


def download_model_artifact(key: str, local_path: str) -> bool:
    if not settings.s3_bucket:
        return False
    client = _client()
    if client is None:
        return False
    try:
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        client.download_file(settings.s3_bucket, key, local_path)
        return True
    except Exception as exc:  # pragma: no cover
        logger.error("model download failed: %s", exc)
        return False


def upload_dataset(local_path: str, name: Optional[str] = None) -> Optional[str]:
    if not settings.s3_bucket:
        return None
    client = _client()
    if client is None:
        return None
    key = f"{settings.s3_dataset_prefix}{name or Path(local_path).name}"
    try:
        client.upload_file(local_path, settings.s3_bucket, key)
        return key
    except Exception as exc:  # pragma: no cover
        logger.error("dataset upload failed: %s", exc)
        return None
