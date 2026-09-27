"""AI Race Analyst endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user_optional
from app.models import User
from app.schemas import ChatRequest, ChatResponse, InsightRequest
from app.services import analyst

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/suggestions")
def suggestions() -> Dict[str, List[str]]:
    return {"questions": analyst.SUGGESTED_QUESTIONS}


@router.post("", response_model=ChatResponse)
def ask(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
) -> ChatResponse:
    try:
        result = analyst.ask(
            db,
            question=payload.question,
            session_id=payload.session_id,
            race_id=payload.race_id,
            user_id=user.id if user else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChatResponse(**result)


@router.get("/sessions/{session_id}")
def transcript(session_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    messages = analyst.transcript(db, session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="No messages for that session")
    return {"session_id": session_id, "messages": messages}


@router.post("/insight")
def insight(payload: InsightRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Narrate a chart or table the user is currently looking at."""
    return analyst.summarize_insight(db, payload.topic, payload.payload)
