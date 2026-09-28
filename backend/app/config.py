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

# Sentinel default. Booting production with this value would let anyone forge a
# token, so `validate_runtime_security` refuses to start when it is still set.
DEV_JWT_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- General ---------------------------------------------------------
    app_name: str = "ApexStrategy AI"
    environment: str = Field(default="development")
    # Defaults to False: an unset DEBUG must never be the reason a production
    # deployment leaks exception text to clients.
    debug: bool = Field(default=False)
    api_prefix: str = "/api"

    # --- Database --------------------------------------------------------
    # Defaults to a local SQLite file so the project runs with zero setup.
    # In AWS this becomes a postgresql+psycopg2://... RDS URL.
    database_url: str = Field(default="sqlite:///./apexstrategy.db")

    # Optional: pull the DB credentials from Secrets Manager at boot.
    db_secret_arn: Optional[str] = Field(default=None)

    # --- Auth ------------------------------------------------------------
    jwt_secret: str = Field(default=DEV_JWT_SECRET)
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

    # --- Rate limiting ----------------------------------------------------
    # In-process, per-instance limits. Distributed limiting belongs at the edge
    # (AWS WAF); this is the last line of defence on a single container.
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_per_minute: int = Field(default=240)
    rate_limit_auth_per_minute: int = Field(default=10)

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

    def validate_runtime_security(self) -> None:
        """Fail fast on configuration that is unsafe to run in production.

        These are refusals rather than warnings on purpose: a service that
        silently boots with a publicly-known signing key is worse than one that
        does not boot at all, because nothing surfaces the problem until it is
        exploited.
        """
        if not self.is_production:
            # Still worth flagging in development, just not fatal.
            if self.jwt_secret == DEV_JWT_SECRET:
                logger.warning(
                    "Using the default development JWT secret. Set JWT_SECRET "
                    "before deploying."
                )
            return

        problems = []
        if self.jwt_secret == DEV_JWT_SECRET:
            problems.append(
                "JWT_SECRET is still the public development default. Generate one "
                "with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        if len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be at least 32 characters in production.")
        if self.debug:
            problems.append(
                "DEBUG must be false in production; it returns exception text to clients."
            )
        if "*" in self.cors_origins:
            problems.append(
                "CORS_ORIGINS cannot be '*' while credentials are allowed -- any "
                "site could then make authenticated requests on a user's behalf."
            )
        if self.database_url.startswith("sqlite"):
            logger.warning(
                "Running production on SQLite. Use PostgreSQL (RDS) for a real deployment."
            )

        if problems:
            raise RuntimeError(
                "Refusing to start with an insecure configuration:\n  - "
                + "\n  - ".join(problems)
            )

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
