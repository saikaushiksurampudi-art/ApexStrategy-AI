"""Feedback capture and aggregation.

The feedback loop is a first-class product feature: ratings are what surface
weak prompts, unclear charts and gaps in the dataset. Anonymous feedback is
accepted on purpose -- requiring an account would cut the sample to near zero.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_current_user_optional
from app.models import Feedback, SavedComparison, User
from app.schemas import (
    FeedbackCreate,
    FeedbackOut,
    FeedbackStats,
    SavedComparisonCreate,
    SavedComparisonOut,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def submit(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
) -> FeedbackOut:
    row = Feedback(
        user_id=user.id if user else None,
        surface=payload.surface,
        reference_id=payload.reference_id,
        rating=payload.rating,
        reason=payload.reason,
        comment=payload.comment,
        context=payload.context,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return FeedbackOut.model_validate(row)


@router.get("/stats", response_model=FeedbackStats)
def stats(
    surface: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> FeedbackStats:
    """Aggregate ratings -- the signal for which explanations need work."""
    query = select(Feedback.surface, Feedback.rating, func.count(Feedback.id))
    if surface:
        query = query.where(Feedback.surface == surface)
    rows = db.execute(query.group_by(Feedback.surface, Feedback.rating)).all()

    by_surface: Dict[str, Dict[str, int]] = {}
    helpful = unhelpful = 0
    for surface_name, rating, count in rows:
        bucket = by_surface.setdefault(surface_name, {"helpful": 0, "unhelpful": 0})
        bucket[rating] = bucket.get(rating, 0) + count
        if rating == "helpful":
            helpful += count
        else:
            unhelpful += count

    total = helpful + unhelpful
    reason_rows = db.execute(
        select(Feedback.reason, func.count(Feedback.id))
        .where(Feedback.reason.isnot(None), Feedback.rating == "unhelpful")
        .group_by(Feedback.reason)
        .order_by(func.count(Feedback.id).desc())
        .limit(5)
    ).all()

    return FeedbackStats(
        total=total,
        helpful=helpful,
        unhelpful=unhelpful,
        helpful_rate=round(helpful / total, 4) if total else None,
        by_surface=by_surface,
        top_reasons=[{"reason": reason, "count": count} for reason, count in reason_rows],
    )


@router.get("/recent", response_model=List[FeedbackOut])
def recent(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[FeedbackOut]:
    rows = db.scalars(
        select(Feedback).order_by(Feedback.created_at.desc()).limit(limit)
    ).all()
    return [FeedbackOut.model_validate(row) for row in rows]


# ---------------------------------------------------------------------------
# Saved comparisons (requires an account)
# ---------------------------------------------------------------------------
saved_router = APIRouter(prefix="/saved", tags=["saved"])


@saved_router.post(
    "", response_model=SavedComparisonOut, status_code=status.HTTP_201_CREATED
)
def save_comparison(
    payload: SavedComparisonCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SavedComparisonOut:
    row = SavedComparison(
        user_id=user.id,
        label=payload.label,
        kind=payload.kind,
        payload=payload.payload,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return SavedComparisonOut.model_validate(row)


@saved_router.get("", response_model=List[SavedComparisonOut])
def list_saved(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> List[SavedComparisonOut]:
    rows = db.scalars(
        select(SavedComparison)
        .where(SavedComparison.user_id == user.id)
        .order_by(SavedComparison.created_at.desc())
    ).all()
    return [SavedComparisonOut.model_validate(row) for row in rows]


@saved_router.delete(
    "/{saved_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_saved(
    saved_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    row = db.get(SavedComparison, saved_id)
    # Same 404 whether it is missing or someone else's, so the endpoint does
    # not confirm the existence of other users' saved items.
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Saved comparison not found")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
