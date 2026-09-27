"""Transform Ergast/Jolpica payloads into ApexStrategy's relational schema.

Every step is idempotent: re-running the pipeline updates existing rows rather
than duplicating them, so a partial run can simply be repeated.
"""

from __future__ import annotations

import logging
import statistics
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.circuit_meta import meta_for
from app.ingest.ergast import ErgastClient
from app.models import (
    Circuit,
    Constructor,
    ConstructorStanding,
    Driver,
    DriverStanding,
    PitStop,
    QualifyingResult,
    Race,
    RaceLapSummary,
    RaceResult,
)

logger = logging.getLogger(__name__)

# Team colours, used so charts stay recognisable to F1 viewers.
TEAM_COLORS = {
    "red_bull": "#3671C6",
    "ferrari": "#E8002D",
    "mercedes": "#27F4D2",
    "mclaren": "#FF8000",
    "aston_martin": "#229971",
    "alpine": "#0093CC",
    "williams": "#64C4FF",
    "rb": "#6692FF",
    "alphatauri": "#5E8FAA",
    "sauber": "#52E252",
    "alfa": "#C92D4B",
    "haas": "#B6BABD",
    "racing_point": "#F596C8",
    "alpha_tauri": "#5E8FAA",
}

# Races known to have run in wet or mixed conditions. Ergast carries no weather
# field; this curated list keeps the "weather category" feature honest about
# being editorial rather than measured.
WET_OR_MIXED: Dict[str, str] = {
    "2021-8": "wet",     # Belgian GP (abandoned behind the safety car)
    "2021-11": "mixed",  # Hungarian GP
    "2021-15": "wet",    # Russian GP
    "2021-18": "wet",    # Turkish GP
    "2022-4": "mixed",   # Imola
    "2022-17": "mixed",  # Singapore
    "2022-18": "mixed",  # Suzuka
    "2023-3": "mixed",   # Australia
    "2023-12": "mixed",  # Zandvoort
    "2023-19": "mixed",  # Brazil sprint weekend
    "2024-11": "mixed",  # Spain -- damp practice
    "2024-14": "mixed",  # Zandvoort
    "2024-21": "wet",    # Brazil
    "2025-4": "mixed",   # Bahrain test conditions placeholder
}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
def parse_lap_time_ms(value: Optional[str]) -> Optional[int]:
    """Convert ``"1:23.456"`` / ``"23.456"`` / ``"1:02:34.567"`` to milliseconds."""
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parts = text.split(":")
        seconds = float(parts[-1])
        minutes = int(parts[-2]) if len(parts) > 1 else 0
        hours = int(parts[-3]) if len(parts) > 2 else 0
        return int(round((hours * 3600 + minutes * 60 + seconds) * 1000))
    except (ValueError, IndexError):
        logger.debug("Unparseable time %r", value)
        return None


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def status_is_finish(status: str, position_text: str) -> bool:
    """True when the driver was classified at the flag (including lapped)."""
    if position_text in {"R", "D", "E", "W", "F", "N"}:
        return False
    return status == "Finished" or status.startswith("+")


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------
def upsert_circuit(db: Session, payload: Dict[str, Any]) -> Circuit:
    ref = payload["circuitId"]
    circuit = db.scalar(select(Circuit).where(Circuit.ref == ref))
    if circuit is None:
        circuit = Circuit(ref=ref)
        db.add(circuit)
    location = payload.get("Location", {})
    circuit.name = payload.get("circuitName", ref)
    circuit.locality = location.get("locality")
    circuit.country = location.get("country")
    circuit.lat = _to_float(location.get("lat"), None) if location.get("lat") else None
    circuit.lng = _to_float(location.get("long"), None) if location.get("long") else None
    circuit.url = payload.get("url")
    for key, value in meta_for(ref).items():
        setattr(circuit, key, value)
    db.flush()
    return circuit


def upsert_driver(db: Session, payload: Dict[str, Any]) -> Driver:
    ref = payload["driverId"]
    driver = db.scalar(select(Driver).where(Driver.ref == ref))
    if driver is None:
        driver = Driver(ref=ref)
        db.add(driver)
    driver.code = payload.get("code")
    driver.permanent_number = _to_int(payload.get("permanentNumber"))
    driver.given_name = payload.get("givenName", ref)
    driver.family_name = payload.get("familyName", "")
    driver.date_of_birth = _parse_date(payload.get("dateOfBirth"))
    driver.nationality = payload.get("nationality")
    driver.url = payload.get("url")
    db.flush()
    return driver


def upsert_constructor(db: Session, payload: Dict[str, Any]) -> Constructor:
    ref = payload["constructorId"]
    constructor = db.scalar(select(Constructor).where(Constructor.ref == ref))
    if constructor is None:
        constructor = Constructor(ref=ref)
        db.add(constructor)
    constructor.name = payload.get("name", ref)
    constructor.nationality = payload.get("nationality")
    constructor.url = payload.get("url")
    constructor.color = TEAM_COLORS.get(ref, "#9AA0A6")
    db.flush()
    return constructor


def upsert_race(db: Session, payload: Dict[str, Any]) -> Race:
    season = int(payload["season"])
    rnd = int(payload["round"])
    # Resolve the circuit first: it flushes, and a half-built Race row would
    # violate the NOT NULL constraint on races.circuit_id.
    circuit = upsert_circuit(db, payload["Circuit"])
    race = db.scalar(select(Race).where(Race.season == season, Race.round == rnd))
    if race is None:
        race = Race(season=season, round=rnd, circuit_id=circuit.id)
        db.add(race)
    race.circuit_id = circuit.id
    race.name = payload.get("raceName", f"Round {rnd}")
    race.date = _parse_date(payload.get("date"))
    race.time = payload.get("time")
    race.url = payload.get("url")
    race.weather = WET_OR_MIXED.get(f"{season}-{rnd}", race.weather or "dry")
    db.flush()
    return race


# ---------------------------------------------------------------------------
# Season-level ingestion
# ---------------------------------------------------------------------------
def ingest_schedule(db: Session, client: ErgastClient, season: int) -> int:
    races = client.season_races(season)
    for payload in races:
        upsert_race(db, payload)
    db.commit()
    logger.info("season %s: %s races in schedule", season, len(races))
    return len(races)


def ingest_results(db: Session, client: ErgastClient, season: int) -> int:
    count = 0
    for race_payload in client.season_results(season):
        race = upsert_race(db, race_payload)
        entries = race_payload.get("Results", [])
        if entries:
            race.is_completed = True
            race.total_laps = max(
                (_to_int(e.get("laps")) or 0 for e in entries), default=None
            )
        existing = {
            r.driver_id: r
            for r in db.scalars(select(RaceResult).where(RaceResult.race_id == race.id))
        }
        for entry in entries:
            driver = upsert_driver(db, entry["Driver"])
            constructor = upsert_constructor(db, entry["Constructor"])
            row = existing.get(driver.id)
            if row is None:
                row = RaceResult(race_id=race.id, driver_id=driver.id)
                db.add(row)
            row.constructor_id = constructor.id
            row.position = _to_int(entry.get("position"))
            row.position_text = entry.get("positionText")
            row.grid = _to_int(entry.get("grid"))
            row.laps = _to_int(entry.get("laps"))
            row.points = _to_float(entry.get("points"))
            row.status = entry.get("status")
            row.finished = status_is_finish(
                entry.get("status", ""), entry.get("positionText", "")
            )
            row.time_ms = _to_int((entry.get("Time") or {}).get("millis"))
            fastest = entry.get("FastestLap") or {}
            row.fastest_lap_rank = _to_int(fastest.get("rank"))
            row.fastest_lap_ms = parse_lap_time_ms((fastest.get("Time") or {}).get("time"))
            count += 1
        db.commit()
    logger.info("season %s: %s race results", season, count)
    return count


def ingest_qualifying(db: Session, client: ErgastClient, season: int) -> int:
    count = 0
    for race_payload in client.season_qualifying(season):
        race = upsert_race(db, race_payload)
        existing = {
            q.driver_id: q
            for q in db.scalars(
                select(QualifyingResult).where(QualifyingResult.race_id == race.id)
            )
        }
        for entry in race_payload.get("QualifyingResults", []):
            driver = upsert_driver(db, entry["Driver"])
            constructor = upsert_constructor(db, entry["Constructor"])
            row = existing.get(driver.id)
            if row is None:
                row = QualifyingResult(race_id=race.id, driver_id=driver.id)
                db.add(row)
            row.constructor_id = constructor.id
            row.position = _to_int(entry.get("position")) or 99
            row.q1_ms = parse_lap_time_ms(entry.get("Q1"))
            row.q2_ms = parse_lap_time_ms(entry.get("Q2"))
            row.q3_ms = parse_lap_time_ms(entry.get("Q3"))
            row.best_ms = min(
                [t for t in (row.q1_ms, row.q2_ms, row.q3_ms) if t], default=None
            )
            count += 1
        db.commit()
    logger.info("season %s: %s qualifying results", season, count)
    return count


def ingest_pitstops(db: Session, client: ErgastClient, season: int) -> int:
    races = db.scalars(
        select(Race).where(Race.season == season, Race.is_completed.is_(True))
    ).all()
    count = 0
    for race in races:
        already = db.scalar(
            select(PitStop.id).where(PitStop.race_id == race.id).limit(1)
        )
        if already:
            continue
        try:
            stops = client.race_pitstops(season, race.round)
        except RuntimeError as exc:
            logger.warning("pit stops unavailable for %s R%s: %s", season, race.round, exc)
            continue
        driver_cache: Dict[str, int] = {}
        for stop in stops:
            ref = stop["driverId"]
            if ref not in driver_cache:
                driver = db.scalar(select(Driver).where(Driver.ref == ref))
                if driver is None:
                    continue
                driver_cache[ref] = driver.id
            db.add(
                PitStop(
                    race_id=race.id,
                    driver_id=driver_cache[ref],
                    stop=_to_int(stop.get("stop")) or 0,
                    lap=_to_int(stop.get("lap")) or 0,
                    duration_ms=parse_lap_time_ms(stop.get("duration")),
                )
            )
            count += 1
        db.commit()
    logger.info("season %s: %s pit stops", season, count)
    return count


def ingest_lap_summaries(
    db: Session, client: ErgastClient, season: int, rounds: Optional[Iterable[int]] = None
) -> int:
    """Fetch lap times for selected rounds and reduce them to pace statistics.

    Lap data is by far the heaviest endpoint, so callers normally pass an
    explicit list of rounds (for example the most recent few races).
    """
    query = select(Race).where(Race.season == season, Race.is_completed.is_(True))
    if rounds is not None:
        query = query.where(Race.round.in_(list(rounds)))
    count = 0
    for race in db.scalars(query).all():
        already = db.scalar(
            select(RaceLapSummary.id).where(RaceLapSummary.race_id == race.id).limit(1)
        )
        if already:
            continue
        try:
            laps = client.race_laps(season, race.round)
        except RuntimeError as exc:
            logger.warning("laps unavailable for %s R%s: %s", season, race.round, exc)
            continue

        per_driver: Dict[str, List[int]] = {}
        for lap in laps:
            for timing in lap.get("Timings", []):
                ms = parse_lap_time_ms(timing.get("time"))
                if ms:
                    per_driver.setdefault(timing["driverId"], []).append(ms)

        for ref, times in per_driver.items():
            driver = db.scalar(select(Driver).where(Driver.ref == ref))
            if driver is None or not times:
                continue
            ordered = sorted(times)
            trim = max(1, int(len(ordered) * 0.1))
            middle = ordered[trim:-trim] or ordered
            db.add(
                RaceLapSummary(
                    race_id=race.id,
                    driver_id=driver.id,
                    laps_recorded=len(times),
                    mean_ms=int(statistics.fmean(times)),
                    median_ms=int(statistics.median(times)),
                    best_ms=ordered[0],
                    std_ms=int(statistics.pstdev(times)) if len(times) > 1 else 0,
                    trimmed_mean_ms=int(statistics.fmean(middle)),
                )
            )
            count += 1
        db.commit()
    logger.info("season %s: %s lap summaries", season, count)
    return count


def ingest_standings(db: Session, client: ErgastClient, season: int) -> int:
    """Ingest end-of-season standings as reported by the API.

    Standings are taken from the source rather than recomputed from race points
    so that sprint points and post-race penalties are reflected correctly.
    """
    rounds = db.scalars(
        select(Race.round)
        .where(Race.season == season, Race.is_completed.is_(True))
        .order_by(Race.round.desc())
        .limit(1)
    ).first()
    if rounds is None:
        return 0

    count = 0
    for entry in client.driver_standings(season):
        driver = upsert_driver(db, entry["Driver"])
        constructors = entry.get("Constructors", [])
        constructor = upsert_constructor(db, constructors[0]) if constructors else None
        row = db.scalar(
            select(DriverStanding).where(
                DriverStanding.season == season,
                DriverStanding.round == rounds,
                DriverStanding.driver_id == driver.id,
            )
        )
        if row is None:
            row = DriverStanding(season=season, round=rounds, driver_id=driver.id)
            db.add(row)
        row.constructor_id = constructor.id if constructor else None
        row.position = _to_int(entry.get("position"))
        row.points = _to_float(entry.get("points"))
        row.wins = _to_int(entry.get("wins")) or 0
        count += 1

    for entry in client.constructor_standings(season):
        constructor = upsert_constructor(db, entry["Constructor"])
        row = db.scalar(
            select(ConstructorStanding).where(
                ConstructorStanding.season == season,
                ConstructorStanding.round == rounds,
                ConstructorStanding.constructor_id == constructor.id,
            )
        )
        if row is None:
            row = ConstructorStanding(
                season=season, round=rounds, constructor_id=constructor.id
            )
            db.add(row)
        row.position = _to_int(entry.get("position"))
        row.points = _to_float(entry.get("points"))
        row.wins = _to_int(entry.get("wins")) or 0
        count += 1

    db.commit()
    logger.info("season %s: %s standings rows", season, count)
    return count


def ingest_season(
    db: Session,
    client: ErgastClient,
    season: int,
    with_pitstops: bool = True,
    lap_rounds: Optional[Iterable[int]] = None,
) -> Dict[str, int]:
    stats = {
        "schedule": ingest_schedule(db, client, season),
        "results": ingest_results(db, client, season),
        "qualifying": ingest_qualifying(db, client, season),
    }
    stats["standings"] = ingest_standings(db, client, season)
    if with_pitstops:
        stats["pit_stops"] = ingest_pitstops(db, client, season)
    if lap_rounds:
        stats["lap_summaries"] = ingest_lap_summaries(db, client, season, lap_rounds)
    return stats
