"""Circuit history, strategy profile and search."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Circuit
from app.services import analytics

router = APIRouter(prefix="/circuits", tags=["circuits"])


@router.get("")
def list_circuits(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    circuits = db.scalars(select(Circuit).order_by(Circuit.name)).all()
    return [
        {
            "id": c.id,
            "ref": c.ref,
            "name": c.name,
            "locality": c.locality,
            "country": c.country,
            "circuit_type": c.circuit_type,
            "tyre_degradation": c.tyre_degradation,
            "overtaking_difficulty": c.overtaking_difficulty,
        }
        for c in circuits
    ]


@router.get("/{identifier}")
def circuit_detail(
    identifier: str,
    seasons: Optional[List[int]] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    circuit = analytics.resolve_circuit(db, identifier)
    if circuit is None:
        raise HTTPException(status_code=404, detail=f"Circuit '{identifier}' not found")

    history = analytics.circuit_history(db, circuit, seasons)
    history["pit_strategy"] = analytics.circuit_pit_strategy(db, circuit)
    return history
