"""Application configuration.

Settings are read from environment variables (or a local ``.env`` file). In AWS
the sensitive values are expected to arrive from Secrets Manager, injected into
the App Runner task environment -- never committed to source control.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Annotated

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- General ---------------------------------------------------------
    app_name: str = "ApexStrategy AI"
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    api_prefix: str = "/api"

    # --- Database --------------------------------------------------------
    # Defaults to a local SQLite file so the project runs with zero setup.
    # In AWS this becomes a postgresql+psycopg2://... RDS URL.
    database_url: str = Field(default="sqlite:///./apexstrategy.db")

    # Optional: pull the DB credentials from Secrets Manager at boot.
    db_secret_arn: Optional[str] = Field(default=None)

    # --- Auth ------------------------------------------------------------
    jwt_secret: str = Field(default="dev-only-insecure-secret-change-me")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    # --- AWS / Bedrock ---------------------------------------------------
    aws_region: str = Field(default="us-east-1")
    bedrock_model_id: str = Field(default="us.anthropic.claude-sonnet-4-5-20250929-v1:0")
    bedrock_max_tokens: int = 1600
    bedrock_temperature: float = 0.2
    # When false (the default) the app uses a deterministic, template-based
    # explanation writer so the whole product works without AWS credentials.
    enable_bedrock: bool = Field(default=False)

    # --- S3 --------------------------------------------------------------
    s3_bucket: Optional[str] = Field(default=None)
    s3_model_prefix: str = "models/"
    s3_dataset_prefix: str = "datasets/"

    # --- ML --------------------------------------------------------------
    model_dir: str = Field(default="./artifacts")
    model_file: str = "podium_model.joblib"

    # --- Data ingestion --------------------------------------------------
    ergast_base_url: str = "https://api.jolpi.ca/ergast/f1"
    # NoDecode: pydantic-settings would otherwise try to JSON-parse this value
    # straight from the .env file and fail on a plain comma-separated list,
    # before ``_split_list`` below ever gets a chance to handle it.
    ingest_seasons: Annotated[List[int], NoDecode] = Field(
        default_factory=lambda: [2021, 2022, 2023, 2024, 2025]
    )

    # --- CORS ------------------------------------------------------------
    cors_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
        ]
    )

    @field_validator("cors_origins", "ingest_seasons", mode="before")
    @classmethod
    def _split_list(cls, value):
        """Allow `A,B,C` or a JSON array in the environment variable."""
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                return json.loads(value)
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}

    @property
    def model_path(self) -> str:
        return f"{self.model_dir.rstrip('/')}/{self.model_file}"


def _load_db_url_from_secrets(settings: Settings) -> Optional[str]:
    """Resolve an RDS connection string from AWS Secrets Manager.

    Returns None (and logs) on any failure so that a misconfigured secret never
    hard-crashes the container -- the caller falls back to ``database_url``.
    """
    if not settings.db_secret_arn:
        return None
    try:
        import boto3

        client = boto3.client("secretsmanager", region_name=settings.aws_region)
        raw = client.get_secret_value(SecretId=settings.db_secret_arn)["SecretString"]
        secret = json.loads(raw)
        if "database_url" in secret:
            return secret["database_url"]
        return (
            "postgresql+psycopg2://{username}:{password}@{host}:{port}/{dbname}".format(
                username=secret["username"],
                password=secret["password"],
                host=secret["host"],
                port=secret.get("port", 5432),
                dbname=secret.get("dbname", "apexstrategy"),
            )
        )
    except Exception as exc:  # pragma: no cover - depends on AWS environment
        logger.warning("Could not read DB secret %s: %s", settings.db_secret_arn, exc)
        return None


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    resolved = _load_db_url_from_secrets(settings)
    if resolved:
        settings.database_url = resolved
    return settings


settings = get_settings()
