"""Constructor profiles and comparisons."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Constructor
from app.services import analytics

router = APIRouter(prefix="/constructors", tags=["constructors"])


@router.get("")
def list_constructors(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    constructors = db.scalars(select(Constructor).order_by(Constructor.name)).all()
    return [
        {
            "id": c.id,
            "ref": c.ref,
            "name": c.name,
            "nationality": c.nationality,
            "color": c.color,
        }
        for c in constructors
    ]


@router.get("/compare")
def compare(
    a: str = Query(description="Constructor ref or name"),
    b: str = Query(description="Constructor ref or name"),
    seasons: Optional[List[int]] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    first = analytics.resolve_constructor(db, a)
    second = analytics.resolve_constructor(db, b)
    if first is None:
        raise HTTPException(status_code=404, detail=f"Constructor '{a}' not found")
    if second is None:
        raise HTTPException(status_code=404, detail=f"Constructor '{b}' not found")
    if first.id == second.id:
        raise HTTPException(status_code=400, detail="Pick two different teams")

    return {
        "constructor_a": analytics.constructor_summary(db, first, seasons),
        "constructor_b": analytics.constructor_summary(db, second, seasons),
        "seasons": seasons,
    }


@router.get("/{identifier}")
def constructor_profile(
    identifier: str,
    seasons: Optional[List[int]] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    constructor = analytics.resolve_constructor(db, identifier)
    if constructor is None:
        raise HTTPException(
            status_code=404, detail=f"Constructor '{identifier}' not found"
        )
    return analytics.constructor_summary(db, constructor, seasons)
