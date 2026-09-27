"""Health and metadata endpoints.

``/health`` is what AWS App Runner polls, so it must stay cheap and must not
fail when optional components (model artifact, Bedrock) are absent.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import __version__
from app.config import settings
from app.database import get_db
from app.models import Circuit, Driver, Race, RaceResult
from app.schemas import HealthOut
from app.services import bedrock
from app.services.prediction import model_status

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    database: dict = {"connected": False}
    try:
        db.execute(text("SELECT 1"))
        database = {
            "connected": True,
            "engine": settings.database_url.split("://", 1)[0],
            "races": db.scalar(select(func.count(Race.id))) or 0,
            "completed_races": db.scalar(
                select(func.count(Race.id)).where(Race.is_completed.is_(True))
            ) or 0,
            "results": db.scalar(select(func.count(RaceResult.id))) or 0,
            "drivers": db.scalar(select(func.count(Driver.id))) or 0,
            "circuits": db.scalar(select(func.count(Circuit.id))) or 0,
            "seasons": [
                season
                for (season,) in db.execute(
                    select(Race.season).distinct().order_by(Race.season)
                ).all()
            ],
        }
    except Exception as exc:  # pragma: no cover - depends on environment
        database = {"connected": False, "error": str(exc)}

    return HealthOut(
        status="ok" if database.get("connected") else "degraded",
        version=__version__,
        environment=settings.environment,
        database=database,
        model=model_status(),
        ai=bedrock.health(),
    )


@router.get("/meta")
def meta(db: Session = Depends(get_db)) -> dict:
    """Reference data the frontend needs on first load."""
    from app.services import analytics

    bounds = analytics.season_bounds(db)
    upcoming = analytics.next_race(db)
    latest = analytics.latest_completed_race(db)

    def _race(race) -> dict | None:
        if race is None:
            return None
        return {
            "id": race.id,
            "season": race.season,
            "round": race.round,
            "name": race.name,
            "date": race.date.isoformat() if race.date else None,
            "circuit": race.circuit.name,
            "circuit_id": race.circuit.id,
            "is_completed": race.is_completed,
        }

    return {
        "app_name": settings.app_name,
        "version": __version__,
        "seasons": [
            season
            for (season,) in db.execute(
                select(Race.season).distinct().order_by(Race.season.desc())
            ).all()
        ],
        "first_season": bounds["first_season"],
        "last_season": bounds["last_season"],
        "next_race": _race(upcoming),
        "latest_race": _race(latest),
        "ai_generator": "bedrock" if bedrock.is_enabled() else "template",
    }
