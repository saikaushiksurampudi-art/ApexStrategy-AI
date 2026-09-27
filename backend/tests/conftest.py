"""Test fixtures: an in-memory database seeded with a small, known F1 dataset.

The fixture data is deliberately hand-built rather than loaded from the real
API: tests need results they can reason about precisely, and a fixed dataset
makes assertions about averages and head-to-head counts verifiable by hand.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ENABLE_BEDROCK", "false")

from app.database import Base, get_db  # noqa: E402
from app.models import (  # noqa: E402
    Circuit,
    Constructor,
    ConstructorStanding,
    Driver,
    DriverStanding,
    PitStop,
    QualifyingResult,
    Race,
    RaceResult,
)


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        _seed(session)
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    from fastapi.testclient import TestClient

    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixture dataset
# ---------------------------------------------------------------------------
#  Two circuits, four drivers, two teams, three seasons of two races each.
#  Driver A ("apex") is consistently fast; driver B ("bolt") is his team mate;
#  "cruz" and "dash" drive for the slower team.
DRIVERS = [
    ("apex", "APX", "Ada", "Apex"),
    ("bolt", "BLT", "Ben", "Bolt"),
    ("cruz", "CRZ", "Cam", "Cruz"),
    ("dash", "DSH", "Dee", "Dash"),
]

# (season, round, circuit_ref, [(driver_ref, grid, position, points, finished, status)])
RACES = [
    (2023, 1, "alpha", [
        ("apex", 1, 1, 25.0, True, "Finished"),
        ("bolt", 2, 2, 18.0, True, "Finished"),
        ("cruz", 3, 3, 15.0, True, "Finished"),
        ("dash", 4, 4, 12.0, True, "Finished"),
    ]),
    (2023, 2, "beta", [
        ("apex", 2, 2, 18.0, True, "Finished"),
        ("bolt", 1, 1, 25.0, True, "Finished"),
        ("cruz", 4, None, 0.0, False, "Engine"),
        ("dash", 3, 3, 15.0, True, "Finished"),
    ]),
    (2024, 1, "alpha", [
        ("apex", 1, 1, 25.0, True, "Finished"),
        ("bolt", 3, 3, 15.0, True, "Finished"),
        ("cruz", 2, 2, 18.0, True, "Finished"),
        ("dash", 4, None, 0.0, False, "Collision"),
    ]),
    (2024, 2, "beta", [
        ("apex", 1, None, 0.0, False, "Gearbox"),
        ("bolt", 2, 1, 25.0, True, "Finished"),
        ("cruz", 3, 2, 18.0, True, "Finished"),
        ("dash", 4, 3, 15.0, True, "Finished"),
    ]),
    (2025, 1, "alpha", [
        ("apex", 1, 1, 25.0, True, "Finished"),
        ("bolt", 2, 2, 18.0, True, "Finished"),
        ("cruz", 3, 4, 12.0, True, "Finished"),
        ("dash", 4, 3, 15.0, True, "Finished"),
    ]),
    (2025, 2, "beta", [
        ("apex", 2, 1, 25.0, True, "Finished"),
        ("bolt", 1, 2, 18.0, True, "Finished"),
        ("cruz", 4, 3, 15.0, True, "Finished"),
        ("dash", 3, 4, 12.0, True, "Finished"),
    ]),
]

TEAM_OF = {"apex": "swift", "bolt": "swift", "cruz": "steady", "dash": "steady"}


def _seed(db) -> None:
    circuits = {}
    for ref, name, deg, overtaking in (
        ("alpha", "Alpha Circuit", "high", "low"),
        ("beta", "Beta Circuit", "low", "medium"),
    ):
        circuit = Circuit(
            ref=ref,
            name=name,
            locality="Testville",
            country="Testland",
            circuit_type="permanent",
            tyre_degradation=deg,
            overtaking_difficulty=overtaking,
            pit_loss_seconds=21.0,
            drs_zones=2,
            notes=f"{name} notes.",
        )
        db.add(circuit)
        circuits[ref] = circuit

    constructors = {}
    for ref, name, color in (("swift", "Swift Racing", "#3987e5"), ("steady", "Steady GP", "#d95926")):
        constructor = Constructor(ref=ref, name=name, nationality="Testland", color=color)
        db.add(constructor)
        constructors[ref] = constructor

    drivers = {}
    for ref, code, given, family in DRIVERS:
        driver = Driver(
            ref=ref,
            code=code,
            given_name=given,
            family_name=family,
            nationality="Testland",
            date_of_birth=date(1995, 1, 1),
        )
        db.add(driver)
        drivers[ref] = driver

    db.flush()

    for season, rnd, circuit_ref, entries in RACES:
        race = Race(
            season=season,
            round=rnd,
            name=f"{circuits[circuit_ref].name} Grand Prix",
            date=date(season, 3 + rnd, 10),
            circuit_id=circuits[circuit_ref].id,
            is_completed=True,
            weather="dry",
            total_laps=55,
        )
        db.add(race)
        db.flush()

        for order, (driver_ref, grid, position, points, finished, status) in enumerate(entries):
            driver = drivers[driver_ref]
            constructor = constructors[TEAM_OF[driver_ref]]
            db.add(
                RaceResult(
                    race_id=race.id,
                    driver_id=driver.id,
                    constructor_id=constructor.id,
                    position=position,
                    position_text=str(position) if position else "R",
                    grid=grid,
                    laps=55 if finished else 20,
                    points=points,
                    status=status,
                    finished=finished,
                    fastest_lap_ms=90000 + order * 200,
                )
            )
            db.add(
                QualifyingResult(
                    race_id=race.id,
                    driver_id=driver.id,
                    constructor_id=constructor.id,
                    position=grid,
                    q1_ms=91000 + grid * 100,
                    q2_ms=90500 + grid * 100,
                    q3_ms=90000 + grid * 100,
                    best_ms=90000 + grid * 100,
                )
            )
            # Two stops at Alpha (high degradation), one at Beta.
            stops = 2 if circuit_ref == "alpha" else 1
            for stop in range(1, stops + 1):
                db.add(
                    PitStop(
                        race_id=race.id,
                        driver_id=driver.id,
                        stop=stop,
                        lap=18 * stop,
                        duration_ms=23000 + stop * 100,
                    )
                )

    # Final standings for the last season.
    totals = {ref: 0.0 for ref in drivers}
    for season, _, _, entries in RACES:
        if season != 2025:
            continue
        for driver_ref, _, _, points, _, _ in entries:
            totals[driver_ref] += points

    for position, (driver_ref, points) in enumerate(
        sorted(totals.items(), key=lambda kv: -kv[1]), start=1
    ):
        db.add(
            DriverStanding(
                season=2025,
                round=2,
                driver_id=drivers[driver_ref].id,
                constructor_id=constructors[TEAM_OF[driver_ref]].id,
                position=position,
                points=points,
                wins=1 if position == 1 else 0,
            )
        )

    db.add(
        ConstructorStanding(
            season=2025, round=2, constructor_id=constructors["swift"].id,
            position=1, points=86.0, wins=2,
        )
    )
    db.add(
        ConstructorStanding(
            season=2025, round=2, constructor_id=constructors["steady"].id,
            position=2, points=54.0, wins=0,
        )
    )
    db.commit()
