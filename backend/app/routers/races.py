"""Race, season and dashboard endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Race
from app.services import analytics

router = APIRouter(prefix="/races", tags=["races"])


@router.get("")
def list_races(
    season: Optional[int] = Query(default=None),
    completed_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    query = select(Race)
    if season:
        query = query.where(Race.season == season)
    if completed_only:
        query = query.where(Race.is_completed.is_(True))

    races = db.scalars(query.order_by(Race.season.desc(), Race.round.asc())).all()
    return [
        {
            "id": race.id,
            "season": race.season,
            "round": race.round,
            "name": race.name,
            "date": race.date.isoformat() if race.date else None,
            "is_completed": race.is_completed,
            "weather": race.weather,
            "circuit": {
                "id": race.circuit.id,
                "ref": race.circuit.ref,
                "name": race.circuit.name,
                "country": race.circuit.country,
                "locality": race.circuit.locality,
            },
        }
        for race in races
    ]


@router.get("/next")
def upcoming_race(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """The next race without results, or the most recent one if the season ended."""
    race = analytics.next_race(db)
    if race is None:
        raise HTTPException(status_code=404, detail="No races in the database")
    detail = analytics.race_detail(db, race)
    detail["pit_strategy"] = analytics.circuit_pit_strategy(db, race.circuit)
    detail["circuit_history"] = analytics.circuit_history(db, race.circuit)
    return detail


@router.get("/{race_id}")
def race_detail(race_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    race = db.get(Race, race_id)
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")
    detail = analytics.race_detail(db, race)
    detail["pit_strategy"] = analytics.circuit_pit_strategy(db, race.circuit)
    return detail


@router.get("/{race_id}/circuit-history")
def race_circuit_history(
    race_id: int,
    seasons: Optional[List[int]] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    race = db.get(Race, race_id)
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")
    return analytics.circuit_history(db, race.circuit, seasons)
