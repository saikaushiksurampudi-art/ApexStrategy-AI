"""SQLAlchemy ORM models for ApexStrategy AI.

Schema groups
-------------
Reference data  : Circuit, Constructor, Driver
Race weekend    : Race, QualifyingResult, RaceResult, PitStop, RaceLapSummary
Championship    : DriverStanding, ConstructorStanding
Product data    : User, Prediction, Feedback, SavedComparison, ChatMessage
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
class Circuit(Base):
    __tablename__ = "circuits"

    id: Mapped[int] = mapped_column(primary_key=True)
    ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    locality: Mapped[Optional[str]] = mapped_column(String(120))
    country: Mapped[Optional[str]] = mapped_column(String(120))
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lng: Mapped[Optional[float]] = mapped_column(Float)
    url: Mapped[Optional[str]] = mapped_column(String(400))

    # Editorial metadata used by the strategy/tyre explanations.
    circuit_type: Mapped[Optional[str]] = mapped_column(String(40))  # street/permanent/hybrid
    overtaking_difficulty: Mapped[Optional[str]] = mapped_column(String(20))  # low/medium/high
    tyre_degradation: Mapped[Optional[str]] = mapped_column(String(20))
    pit_loss_seconds: Mapped[Optional[float]] = mapped_column(Float)
    drs_zones: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    races: Mapped[List[Race]] = relationship(back_populates="circuit")


class Constructor(Base):
    __tablename__ = "constructors"

    id: Mapped[int] = mapped_column(primary_key=True)
    ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    nationality: Mapped[Optional[str]] = mapped_column(String(80))
    url: Mapped[Optional[str]] = mapped_column(String(400))
    color: Mapped[Optional[str]] = mapped_column(String(16))  # hex, for charts

    results: Mapped[List[RaceResult]] = relationship(back_populates="constructor")


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    code: Mapped[Optional[str]] = mapped_column(String(8))
    permanent_number: Mapped[Optional[int]] = mapped_column(Integer)
    given_name: Mapped[str] = mapped_column(String(80))
    family_name: Mapped[str] = mapped_column(String(80))
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(Date)
    nationality: Mapped[Optional[str]] = mapped_column(String(80))
    url: Mapped[Optional[str]] = mapped_column(String(400))

    # Portrait sourced from Wikimedia Commons. Licence and author are stored
    # alongside the URL because these images are freely licensed but nearly all
    # require attribution, which the UI renders next to the photo.
    image_url: Mapped[Optional[str]] = mapped_column(String(600))
    image_author: Mapped[Optional[str]] = mapped_column(String(300))
    image_license: Mapped[Optional[str]] = mapped_column(String(120))
    image_license_url: Mapped[Optional[str]] = mapped_column(String(400))

    results: Mapped[List[RaceResult]] = relationship(back_populates="driver")

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}"


# ---------------------------------------------------------------------------
# Race weekend
# ---------------------------------------------------------------------------
class Race(Base):
    __tablename__ = "races"
    __table_args__ = (
        UniqueConstraint("season", "round", name="uq_race_season_round"),
        Index("ix_race_season_round", "season", "round"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    round: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(160))
    date: Mapped[Optional[datetime]] = mapped_column(Date, index=True)
    time: Mapped[Optional[str]] = mapped_column(String(16))
    url: Mapped[Optional[str]] = mapped_column(String(400))
    circuit_id: Mapped[int] = mapped_column(ForeignKey("circuits.id"), index=True)

    # Populated when results exist; lets the UI distinguish past from upcoming.
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    weather: Mapped[Optional[str]] = mapped_column(String(40))  # dry/mixed/wet/unknown
    total_laps: Mapped[Optional[int]] = mapped_column(Integer)

    circuit: Mapped[Circuit] = relationship(back_populates="races")
    results: Mapped[List[RaceResult]] = relationship(
        back_populates="race", cascade="all, delete-orphan"
    )
    qualifying: Mapped[List[QualifyingResult]] = relationship(
        back_populates="race", cascade="all, delete-orphan"
    )
    pit_stops: Mapped[List[PitStop]] = relationship(
        back_populates="race", cascade="all, delete-orphan"
    )


class QualifyingResult(Base):
    __tablename__ = "qualifying_results"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id", name="uq_quali_race_driver"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    constructor_id: Mapped[int] = mapped_column(ForeignKey("constructors.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    q1_ms: Mapped[Optional[int]] = mapped_column(Integer)
    q2_ms: Mapped[Optional[int]] = mapped_column(Integer)
    q3_ms: Mapped[Optional[int]] = mapped_column(Integer)
    best_ms: Mapped[Optional[int]] = mapped_column(Integer)

    race: Mapped[Race] = relationship(back_populates="qualifying")
    driver: Mapped[Driver] = relationship()
    constructor: Mapped[Constructor] = relationship()


class RaceResult(Base):
    __tablename__ = "race_results"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id", name="uq_result_race_driver"),
        Index("ix_result_driver_race", "driver_id", "race_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    constructor_id: Mapped[int] = mapped_column(ForeignKey("constructors.id"), index=True)

    position: Mapped[Optional[int]] = mapped_column(Integer)          # None = DNF/DSQ
    position_text: Mapped[Optional[str]] = mapped_column(String(8))   # "R", "D", "1"...
    grid: Mapped[Optional[int]] = mapped_column(Integer)
    laps: Mapped[Optional[int]] = mapped_column(Integer)
    points: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[Optional[str]] = mapped_column(String(80))
    finished: Mapped[bool] = mapped_column(Boolean, default=False)
    time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    fastest_lap_rank: Mapped[Optional[int]] = mapped_column(Integer)
    fastest_lap_ms: Mapped[Optional[int]] = mapped_column(Integer)

    race: Mapped[Race] = relationship(back_populates="results")
    driver: Mapped[Driver] = relationship(back_populates="results")
    constructor: Mapped[Constructor] = relationship(back_populates="results")


class PitStop(Base):
    __tablename__ = "pit_stops"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id", "stop", name="uq_pit_race_driver_stop"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    stop: Mapped[int] = mapped_column(Integer)
    lap: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    race: Mapped[Race] = relationship(back_populates="pit_stops")
    driver: Mapped[Driver] = relationship()


class RaceLapSummary(Base):
    """Per-driver lap-time aggregates, computed at ingest.

    Storing every lap for every race is a lot of rows for little MVP value, so
    the pipeline reduces them to the pace statistics the analytics layer uses.
    """

    __tablename__ = "race_lap_summaries"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id", name="uq_lapsum_race_driver"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    laps_recorded: Mapped[int] = mapped_column(Integer, default=0)
    mean_ms: Mapped[Optional[int]] = mapped_column(Integer)
    median_ms: Mapped[Optional[int]] = mapped_column(Integer)
    best_ms: Mapped[Optional[int]] = mapped_column(Integer)
    std_ms: Mapped[Optional[int]] = mapped_column(Integer)
    # Mean of the middle 80% of laps -- a rough "clean air race pace" proxy.
    trimmed_mean_ms: Mapped[Optional[int]] = mapped_column(Integer)


# ---------------------------------------------------------------------------
# Championship standings
# ---------------------------------------------------------------------------
class DriverStanding(Base):
    __tablename__ = "driver_standings"
    __table_args__ = (
        UniqueConstraint("season", "round", "driver_id", name="uq_dstanding"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    round: Mapped[int] = mapped_column(Integer)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    constructor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("constructors.id"))
    position: Mapped[Optional[int]] = mapped_column(Integer)
    points: Mapped[float] = mapped_column(Float, default=0.0)
    wins: Mapped[int] = mapped_column(Integer, default=0)

    driver: Mapped[Driver] = relationship()
    constructor: Mapped[Optional[Constructor]] = relationship()


class ConstructorStanding(Base):
    __tablename__ = "constructor_standings"
    __table_args__ = (
        UniqueConstraint("season", "round", "constructor_id", name="uq_cstanding"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    round: Mapped[int] = mapped_column(Integer)
    constructor_id: Mapped[int] = mapped_column(ForeignKey("constructors.id"), index=True)
    position: Mapped[Optional[int]] = mapped_column(Integer)
    points: Mapped[float] = mapped_column(Float, default=0.0)
    wins: Mapped[int] = mapped_column(Integer, default=0)

    constructor: Mapped[Constructor] = relationship()


# ---------------------------------------------------------------------------
# Product data
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    feedback: Mapped[List[Feedback]] = relationship(back_populates="user")


class Prediction(Base):
    """A stored model output for one driver at one race.

    ``model_version`` and ``features`` are persisted so that any explanation
    shown to a user can be traced back to the exact inputs that produced it.
    """

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "race_id", "driver_id", "model_version", name="uq_prediction_race_driver_ver"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    constructor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("constructors.id"))

    podium_probability: Mapped[float] = mapped_column(Float)
    points_probability: Mapped[float] = mapped_column(Float)
    win_probability: Mapped[Optional[float]] = mapped_column(Float)
    expected_position: Mapped[Optional[float]] = mapped_column(Float)

    model_version: Mapped[str] = mapped_column(String(64), default="v0")
    features: Mapped[Optional[dict]] = mapped_column(JSON)
    top_factors: Mapped[Optional[list]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    race: Mapped[Race] = relationship()
    driver: Mapped[Driver] = relationship()
    constructor: Mapped[Optional[Constructor]] = relationship()


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    surface: Mapped[str] = mapped_column(String(40))  # chat | prediction | insight | scenario
    reference_id: Mapped[Optional[str]] = mapped_column(String(80))
    rating: Mapped[str] = mapped_column(String(16))  # helpful | unhelpful
    reason: Mapped[Optional[str]] = mapped_column(String(80))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    context: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped[Optional[User]] = relationship(back_populates="feedback")


class SavedComparison(Base):
    __tablename__ = "saved_comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(40))  # driver | constructor
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ChatMessage(Base):
    """Transcript of the AI Race Analyst, including what grounded each answer."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[Optional[list]] = mapped_column(JSON)
    intent: Mapped[Optional[str]] = mapped_column(String(40))
    generator: Mapped[Optional[str]] = mapped_column(String(32))  # bedrock | template
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
