"""Cross-entity search for the command bar."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import analytics

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(
    q: str = Query(min_length=2, max_length=60),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return analytics.search_entities(db, q)
