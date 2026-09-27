"""Orchestration for the AI Race Analyst.

    question -> grounding.build_context -> Bedrock (or narrator) -> answer

The context pack travels with the answer all the way to the UI, so a user can
always open "what this was based on" and see the same rows a chart would show.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatMessage
from app.services import bedrock, grounding, narrator

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 8

SUGGESTED_QUESTIONS = [
    "Compare Verstappen and Norris over the last two seasons",
    "Which drivers have historically performed well at Monza?",
    "Why might a one-stop strategy be risky at Bahrain?",
    "How has Leclerc's qualifying pace compared with his race results?",
    "What are the podium probabilities for the next race?",
    "Who leads the championship and by how much?",
]


def _load_history(db: Session, session_id: str) -> List[Dict[str, str]]:
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_HISTORY_TURNS)
    ).all()
    return [{"role": row.role, "content": row.content} for row in reversed(rows)]


def ask(
    db: Session,
    question: str,
    session_id: Optional[str] = None,
    race_id: Optional[int] = None,
    user_id: Optional[int] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Answer a natural-language question about the stored F1 data."""
    question = (question or "").strip()
    if not question:
        raise ValueError("Question must not be empty")

    session_id = session_id or uuid.uuid4().hex
    started = time.monotonic()

    context = grounding.build_context(db, question, race_id=race_id)
    context_dict = context.to_dict()

    history = _load_history(db, session_id) if persist else []

    answer: str
    metadata: Dict[str, Any]
    if bedrock.is_enabled():
        try:
            answer, metadata = bedrock.generate(question, context_dict, history)
        except bedrock.BedrockUnavailable as exc:
            logger.warning("Bedrock unavailable, using narrator: %s", exc)
            answer = narrator.generate(question, context_dict)
            metadata = {"generator": "template", "fallback_reason": str(exc)}
    else:
        answer = narrator.generate(question, context_dict)
        metadata = {"generator": "template"}

    latency_ms = int((time.monotonic() - started) * 1000)
    metadata["latency_ms"] = metadata.get("latency_ms") or latency_ms

    message_id: Optional[int] = None
    if persist:
        db.add(
            ChatMessage(
                session_id=session_id,
                user_id=user_id,
                role="user",
                content=question,
                intent=context.intent,
            )
        )
        assistant_row = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            content=answer,
            citations=context.citations,
            intent=context.intent,
            generator=metadata.get("generator"),
            latency_ms=latency_ms,
        )
        db.add(assistant_row)
        db.commit()
        db.refresh(assistant_row)
        message_id = assistant_row.id

    return {
        "session_id": session_id,
        "message_id": message_id,
        "question": question,
        "answer": answer,
        "intent": context.intent,
        "citations": context.citations,
        "entities": context.entities,
        "notes": context.notes,
        "grounded": context.has_data,
        "context": context_dict["facts"],
        "generator": metadata.get("generator"),
        "model_id": metadata.get("model_id"),
        "latency_ms": latency_ms,
        "fallback_reason": metadata.get("fallback_reason"),
    }


def transcript(db: Session, session_id: str) -> List[Dict[str, Any]]:
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    ).all()
    return [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "citations": row.citations or [],
            "intent": row.intent,
            "generator": row.generator,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def summarize_insight(
    db: Session, topic: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Narrate a chart or table the user is already looking at.

    The caller passes the exact data the UI rendered, so the summary describes
    that view rather than a fresh query.
    """
    context = {
        "intent": f"insight:{topic}",
        "entities": {},
        "facts": payload,
        "citations": [{"source": topic, "detail": "data currently shown in the UI"}],
        "notes": [
            "This summary describes only the data on screen.",
        ],
    }
    question = f"Summarise the key patterns in this {topic.replace('_', ' ')} view."

    if bedrock.is_enabled():
        try:
            answer, metadata = bedrock.generate(question, context)
            return {
                "summary": answer,
                "generator": metadata.get("generator"),
                "citations": context["citations"],
            }
        except bedrock.BedrockUnavailable as exc:
            logger.warning("Bedrock unavailable for insight summary: %s", exc)

    return {
        "summary": narrator.generate(question, context),
        "generator": "template",
        "citations": context["citations"],
    }
