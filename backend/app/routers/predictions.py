"""Podium probabilities, model transparency and scenario simulation."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Race
from app.schemas import ScenarioRequest
from app.services import analytics
from app.services.prediction import model_status, predict_race, scenario

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/model")
def model_info() -> Dict[str, Any]:
    """Model version, training window and how it scored against baselines.

    Exposed deliberately: users are being shown probabilities, so they should
    be able to check how well the thing producing them actually performs.
    """
    return model_status()


@router.get("/next")
def next_race_predictions(
    persist: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    race = analytics.next_race(db)
    if race is None:
        raise HTTPException(status_code=404, detail="No races in the database")
    return predict_race(db, race, persist=persist)


@router.get("/race/{race_id}")
def race_predictions(
    race_id: int,
    persist: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    race = db.get(Race, race_id)
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return predict_race(db, race, persist=persist)


@router.post("/scenario")
def run_scenario(
    payload: ScenarioRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Re-score a race with one driver moved to a different grid slot."""
    race = db.get(Race, payload.race_id)
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")

    result = scenario(db, race, payload.driver_id, payload.grid)
    if not result.get("available"):
        raise HTTPException(
            status_code=400,
            detail=result.get("message", "Scenario could not be simulated"),
        )
    return result
