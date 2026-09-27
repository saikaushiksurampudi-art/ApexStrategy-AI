"""Driver profiles, comparisons and qualifying trends."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Driver, Race, RaceResult
from app.services import analytics

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("")
def list_drivers(
    season: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """All drivers, or only those who raced in a given season."""
    if season:
        driver_ids = select(RaceResult.driver_id).join(
            Race, RaceResult.race_id == Race.id
        ).where(Race.season == season).distinct()
        drivers = db.scalars(
            select(Driver).where(Driver.id.in_(driver_ids)).order_by(Driver.family_name)
        ).all()
    else:
        drivers = db.scalars(select(Driver).order_by(Driver.family_name)).all()

    return [
        {
            "id": driver.id,
            "ref": driver.ref,
            "name": analytics.driver_label(driver),
            "code": driver.code,
            "number": driver.permanent_number,
            "nationality": driver.nationality,
            **analytics.driver_portrait(driver),
        }
        for driver in drivers
    ]


@router.get("/compare")
def compare(
    a: str = Query(description="Driver ref, code or surname"),
    b: str = Query(description="Driver ref, code or surname"),
    seasons: Optional[List[int]] = Query(default=None),
    circuit_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    driver_a = analytics.resolve_driver(db, a)
    driver_b = analytics.resolve_driver(db, b)
    if driver_a is None:
        raise HTTPException(status_code=404, detail=f"Driver '{a}' not found")
    if driver_b is None:
        raise HTTPException(status_code=404, detail=f"Driver '{b}' not found")
    if driver_a.id == driver_b.id:
        raise HTTPException(status_code=400, detail="Pick two different drivers")

    return analytics.head_to_head(db, driver_a, driver_b, seasons, circuit_id)


@router.get("/{identifier}")
def driver_profile(
    identifier: str,
    seasons: Optional[List[int]] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    driver = analytics.resolve_driver(db, identifier)
    if driver is None:
        raise HTTPException(status_code=404, detail=f"Driver '{identifier}' not found")

    summary = analytics.driver_summary(db, driver, seasons)
    bounds = analytics.season_bounds(db)
    target_season = (seasons or [bounds["last_season"]])[-1]

    return {
        "summary": summary.to_dict(),
        "season": target_season,
        "progression": analytics.driver_season_progression(db, driver, target_season),
        "qualifying": analytics.driver_qualifying_trend(db, driver, seasons)[-24:],
    }


@router.get("/{identifier}/circuits")
def driver_circuit_breakdown(
    identifier: str, db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """How a driver has gone at every circuit they have raced at."""
    driver = analytics.resolve_driver(db, identifier)
    if driver is None:
        raise HTTPException(status_code=404, detail=f"Driver '{identifier}' not found")

    from app.models import Circuit

    circuits = db.scalars(
        select(Circuit)
        .join(Race, Race.circuit_id == Circuit.id)
        .join(RaceResult, RaceResult.race_id == Race.id)
        .where(RaceResult.driver_id == driver.id)
        .distinct()
    ).all()

    breakdown = []
    for circuit in circuits:
        summary = analytics.driver_summary(db, driver, circuit_id=circuit.id)
        if summary.races == 0:
            continue
        breakdown.append(
            {
                "circuit_id": circuit.id,
                "circuit": circuit.name,
                "country": circuit.country,
                "starts": summary.races,
                "wins": summary.wins,
                "podiums": summary.podiums,
                "avg_finish": summary.avg_finish,
                "avg_grid": summary.avg_grid,
                "podium_rate": summary.podium_rate,
                "points": summary.total_points,
            }
        )
    breakdown.sort(key=lambda entry: (entry["avg_finish"] or 99))
    return breakdown
