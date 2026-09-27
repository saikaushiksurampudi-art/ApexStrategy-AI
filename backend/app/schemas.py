"""Pydantic request/response models.

Analytics responses are intentionally loose (``Dict[str, Any]``): the shapes are
assembled by the analytics service and consumed by charts, and pinning every
nested field here would double the maintenance cost without adding safety. The
schemas that matter -- anything a client *sends* -- are strict.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=120)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: Optional[str]
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    session_id: Optional[str] = Field(default=None, max_length=64)
    race_id: Optional[int] = None

    @field_validator("question")
    @classmethod
    def _strip(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question must not be empty")
        return cleaned


class Citation(BaseModel):
    source: str
    detail: str


class ChatResponse(BaseModel):
    session_id: str
    message_id: Optional[int]
    question: str
    answer: str
    intent: str
    citations: List[Citation]
    entities: Dict[str, Any]
    notes: List[str]
    grounded: bool
    context: Dict[str, Any]
    generator: Optional[str]
    model_id: Optional[str] = None
    latency_ms: Optional[int] = None
    fallback_reason: Optional[str] = None


class InsightRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=60)
    payload: Dict[str, Any]


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------
class ScenarioRequest(BaseModel):
    race_id: int
    driver_id: int
    grid: int = Field(ge=1, le=24, description="Hypothetical starting position")


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
class FeedbackCreate(BaseModel):
    surface: str = Field(
        description="Which part of the product the feedback is about",
        pattern="^(chat|prediction|insight|scenario|comparison|circuit)$",
    )
    rating: str = Field(pattern="^(helpful|unhelpful)$")
    reference_id: Optional[str] = Field(default=None, max_length=80)
    reason: Optional[str] = Field(default=None, max_length=80)
    comment: Optional[str] = Field(default=None, max_length=2000)
    context: Optional[Dict[str, Any]] = None


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    surface: str
    rating: str
    reason: Optional[str]
    comment: Optional[str]
    created_at: datetime


class FeedbackStats(BaseModel):
    total: int
    helpful: int
    unhelpful: int
    helpful_rate: Optional[float]
    by_surface: Dict[str, Dict[str, int]]
    top_reasons: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Saved comparisons
# ---------------------------------------------------------------------------
class SavedComparisonCreate(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    kind: str = Field(pattern="^(driver|constructor)$")
    payload: Dict[str, Any]


class SavedComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    kind: str
    payload: Dict[str, Any]
    created_at: datetime


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class HealthOut(BaseModel):
    status: str
    version: str
    environment: str
    database: Dict[str, Any]
    model: Dict[str, Any]
    ai: Dict[str, Any]
