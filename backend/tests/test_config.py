"""Configuration parsing.

These cover the .env formats documented in ``.env.example``. A regression here
breaks start-up for anyone following the README, so the documented forms are
pinned by tests rather than trusted.
"""

from __future__ import annotations

import pytest

from app.config import Settings


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2021,2022,2023", [2021, 2022, 2023]),        # the documented form
        ("2021, 2022, 2023", [2021, 2022, 2023]),      # tolerant of spaces
        ("[2021, 2022]", [2021, 2022]),                # JSON also accepted
        ("2024", [2024]),                              # single value
        ("", []),
    ],
)
def test_ingest_seasons_accepts_comma_separated_values(raw, expected, monkeypatch):
    monkeypatch.setenv("INGEST_SEASONS", raw)
    settings = Settings(_env_file=None)
    assert settings.ingest_seasons == expected
    assert all(isinstance(season, int) for season in settings.ingest_seasons)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            "http://localhost:5173,http://127.0.0.1:5173",
            ["http://localhost:5173", "http://127.0.0.1:5173"],
        ),
        ('["http://a.test"]', ["http://a.test"]),
        ("", []),
    ],
)
def test_cors_origins_accepts_comma_separated_values(raw, expected, monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", raw)
    settings = Settings(_env_file=None)
    assert settings.cors_origins == expected


def test_defaults_work_without_any_env_file():
    """A fresh clone with no .env must still boot."""
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("sqlite")
    assert settings.enable_bedrock is False
    assert settings.ingest_seasons


def test_env_example_parses(monkeypatch, tmp_path):
    """Load the shipped .env.example verbatim -- it is the documented setup."""
    from pathlib import Path

    example = Path(__file__).resolve().parents[2] / ".env.example"
    assert example.exists(), "env.example must ship with the project"

    # Strip comments the way a user's copied file would still contain them.
    target = tmp_path / ".env"
    target.write_text(example.read_text())

    settings = Settings(_env_file=str(target))
    assert settings.ingest_seasons == [2021, 2022, 2023, 2024, 2025]
    assert settings.cors_origins
    assert settings.environment == "development"


def test_model_path_is_composed_from_dir_and_file():
    settings = Settings(_env_file=None, model_dir="./artifacts/", model_file="m.joblib")
    assert settings.model_path == "./artifacts/m.joblib"


def test_is_production_flag():
    assert Settings(_env_file=None, environment="production").is_production is True
    assert Settings(_env_file=None, environment="development").is_production is False
