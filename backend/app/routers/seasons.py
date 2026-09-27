"""Season standings and championship progression."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import analytics

router = APIRouter(prefix="/seasons", tags=["seasons"])


@router.get("/{season}/standings")
def standings(season: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    result = analytics.season_standings(db, season)
    if not result["drivers"]:
        raise HTTPException(
            status_code=404, detail=f"No standings held for season {season}"
        )
    return result


@router.get("/{season}/constructor-progression")
def constructor_progression(
    season: int, db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    series = analytics.constructor_season_points(db, season)
    if not series:
        raise HTTPException(
            status_code=404, detail=f"No results held for season {season}"
        )
    return series
