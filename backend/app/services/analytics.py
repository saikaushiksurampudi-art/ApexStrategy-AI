"""Statistical queries over the historical F1 tables.

Everything the dashboard renders and everything the AI layer is allowed to cite
comes from this module. Keeping the two on one code path is what makes
"data-grounded answers" true rather than aspirational: the assistant can only
talk about numbers that a chart could also display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models import (
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

POINTS_POSITION = 10
PODIUM_POSITION = 3


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _ms_to_lap_string(ms: Optional[int]) -> Optional[str]:
    if not ms:
        return None
    minutes, remainder = divmod(ms / 1000.0, 60)
    return f"{int(minutes)}:{remainder:06.3f}"


def driver_label(driver: Driver) -> str:
    return f"{driver.given_name} {driver.family_name}"


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
def resolve_driver(db: Session, identifier: str) -> Optional[Driver]:
    """Find a driver by ref, three-letter code, surname or full name."""
    needle = identifier.strip().lower()
    if not needle:
        return None
    candidates = [
        select(Driver).where(func.lower(Driver.ref) == needle),
        select(Driver).where(func.lower(Driver.code) == needle),
        select(Driver).where(func.lower(Driver.family_name) == needle),
        select(Driver).where(
            func.lower(Driver.given_name + " " + Driver.family_name) == needle
        ),
        select(Driver).where(func.lower(Driver.family_name).like(f"%{needle}%")),
    ]
    for query in candidates:
        found = db.scalars(query).first()
        if found:
            return found
    return None


def resolve_constructor(db: Session, identifier: str) -> Optional[Constructor]:
    needle = identifier.strip().lower()
    if not needle:
        return None
    for query in (
        select(Constructor).where(func.lower(Constructor.ref) == needle),
        select(Constructor).where(func.lower(Constructor.name) == needle),
        select(Constructor).where(func.lower(Constructor.name).like(f"%{needle}%")),
    ):
        found = db.scalars(query).first()
        if found:
            return found
    return None


def resolve_circuit(db: Session, identifier: str) -> Optional[Circuit]:
    needle = identifier.strip().lower()
    if not needle:
        return None
    for query in (
        select(Circuit).where(func.lower(Circuit.ref) == needle),
        select(Circuit).where(func.lower(Circuit.name) == needle),
        select(Circuit).where(func.lower(Circuit.name).like(f"%{needle}%")),
        select(Circuit).where(func.lower(Circuit.locality).like(f"%{needle}%")),
        select(Circuit).where(func.lower(Circuit.country).like(f"%{needle}%")),
    ):
        found = db.scalars(query).first()
        if found:
            return found
    return None


def latest_completed_race(db: Session) -> Optional[Race]:
    return db.scalars(
        select(Race)
        .where(Race.is_completed.is_(True))
        .order_by(Race.season.desc(), Race.round.desc())
        .limit(1)
    ).first()


def next_race(db: Session) -> Optional[Race]:
    """The earliest race with no results, falling back to the latest completed one."""
    upcoming = db.scalars(
        select(Race)
        .where(Race.is_completed.is_(False))
        .order_by(Race.season.asc(), Race.round.asc())
        .limit(1)
    ).first()
    return upcoming or latest_completed_race(db)


def season_bounds(db: Session) -> Dict[str, Optional[int]]:
    row = db.execute(select(func.min(Race.season), func.max(Race.season))).one()
    return {"first_season": row[0], "last_season": row[1]}


# ---------------------------------------------------------------------------
# Driver analytics
# ---------------------------------------------------------------------------
@dataclass
class DriverSummary:
    driver_id: int
    ref: str
    name: str
    code: Optional[str]
    nationality: Optional[str]
    constructor: Optional[str]
    constructor_color: Optional[str]
    races: int
    wins: int
    podiums: int
    points_finishes: int
    total_points: float
    dnfs: int
    avg_finish: Optional[float]
    avg_grid: Optional[float]
    best_finish: Optional[int]
    podium_rate: float
    points_rate: float
    dnf_rate: float
    avg_positions_gained: Optional[float]
    seasons: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def driver_summary(
    db: Session,
    driver: Driver,
    seasons: Optional[Sequence[int]] = None,
    circuit_id: Optional[int] = None,
) -> DriverSummary:
    """Aggregate a driver's record, optionally narrowed to seasons/circuit."""
    query = (
        select(RaceResult, Race)
        .join(Race, RaceResult.race_id == Race.id)
        .where(RaceResult.driver_id == driver.id, Race.is_completed.is_(True))
    )
    if seasons:
        query = query.where(Race.season.in_(list(seasons)))
    if circuit_id:
        query = query.where(Race.circuit_id == circuit_id)

    rows = db.execute(query.order_by(Race.season, Race.round)).all()
    results = [row[0] for row in rows]
    races = [row[1] for row in rows]

    finished_positions = [r.position for r in results if r.position]
    grids = [r.grid for r in results if r.grid and r.grid > 0]
    gained = [
        r.grid - r.position
        for r in results
        if r.position and r.grid and r.grid > 0
    ]

    latest_constructor = results[-1].constructor if results else None
    total = len(results)

    return DriverSummary(
        driver_id=driver.id,
        ref=driver.ref,
        name=driver_label(driver),
        code=driver.code,
        nationality=driver.nationality,
        constructor=latest_constructor.name if latest_constructor else None,
        constructor_color=latest_constructor.color if latest_constructor else None,
        races=total,
        wins=sum(1 for p in finished_positions if p == 1),
        podiums=sum(1 for p in finished_positions if p <= PODIUM_POSITION),
        points_finishes=sum(1 for p in finished_positions if p <= POINTS_POSITION),
        total_points=round(sum(r.points for r in results), 1),
        dnfs=sum(1 for r in results if not r.finished),
        avg_finish=round(sum(finished_positions) / len(finished_positions), 2)
        if finished_positions
        else None,
        avg_grid=round(sum(grids) / len(grids), 2) if grids else None,
        best_finish=min(finished_positions) if finished_positions else None,
        podium_rate=_rate(sum(1 for p in finished_positions if p <= PODIUM_POSITION), total),
        points_rate=_rate(sum(1 for p in finished_positions if p <= POINTS_POSITION), total),
        dnf_rate=_rate(sum(1 for r in results if not r.finished), total),
        avg_positions_gained=round(sum(gained) / len(gained), 2) if gained else None,
        seasons=sorted({race.season for race in races}),
    )


def driver_season_progression(
    db: Session, driver: Driver, season: int
) -> List[Dict[str, Any]]:
    """Race-by-race finishing position and cumulative points for one season."""
    rows = db.execute(
        select(RaceResult, Race)
        .join(Race, RaceResult.race_id == Race.id)
        .where(
            RaceResult.driver_id == driver.id,
            Race.season == season,
            Race.is_completed.is_(True),
        )
        .order_by(Race.round)
    ).all()

    output: List[Dict[str, Any]] = []
    running = 0.0
    for result, race in rows:
        running += result.points
        output.append(
            {
                "round": race.round,
                "race": race.name,
                "date": race.date.isoformat() if race.date else None,
                "grid": result.grid,
                "position": result.position,
                "position_text": result.position_text,
                "points": result.points,
                "cumulative_points": round(running, 1),
                "status": result.status,
                "finished": result.finished,
            }
        )
    return output


def driver_recent_form(
    db: Session, driver_id: int, before_race: Race, window: int = 5
) -> Dict[str, Any]:
    """Form over the ``window`` races immediately preceding ``before_race``.

    Strictly backward-looking: this is the same function the model uses to build
    features, so it must never see the race it is predicting.
    """
    rows = db.execute(
        select(RaceResult, Race)
        .join(Race, RaceResult.race_id == Race.id)
        .where(
            RaceResult.driver_id == driver_id,
            Race.is_completed.is_(True),
            _is_before(before_race),
        )
        .order_by(Race.season.desc(), Race.round.desc())
        .limit(window)
    ).all()

    results = [row[0] for row in rows]
    positions = [r.position for r in results if r.position]
    return {
        "races_counted": len(results),
        "avg_finish": round(sum(positions) / len(positions), 2) if positions else None,
        "avg_points": round(sum(r.points for r in results) / len(results), 2)
        if results
        else None,
        "podiums": sum(1 for p in positions if p <= PODIUM_POSITION),
        "points_finishes": sum(1 for p in positions if p <= POINTS_POSITION),
        "dnfs": sum(1 for r in results if not r.finished),
        "finish_rate": _rate(sum(1 for r in results if r.finished), len(results)),
    }


def _is_before(race: Race):
    """SQL predicate for 'earlier in the calendar than this race'."""
    return and_(
        Race.is_completed.is_(True),
        (Race.season < race.season)
        | and_(Race.season == race.season, Race.round < race.round),
    )


def driver_qualifying_trend(
    db: Session, driver: Driver, seasons: Optional[Sequence[int]] = None
) -> List[Dict[str, Any]]:
    """Qualifying position per race, plus the gap to that session's pole time."""
    pole = (
        select(
            QualifyingResult.race_id.label("race_id"),
            func.min(QualifyingResult.best_ms).label("pole_ms"),
        )
        .group_by(QualifyingResult.race_id)
        .subquery()
    )

    query = (
        select(QualifyingResult, Race, pole.c.pole_ms)
        .join(Race, QualifyingResult.race_id == Race.id)
        .join(pole, pole.c.race_id == QualifyingResult.race_id)
        .where(QualifyingResult.driver_id == driver.id)
    )
    if seasons:
        query = query.where(Race.season.in_(list(seasons)))

    output = []
    for quali, race, pole_ms in db.execute(query.order_by(Race.season, Race.round)).all():
        gap = (quali.best_ms - pole_ms) / 1000.0 if quali.best_ms and pole_ms else None
        output.append(
            {
                "season": race.season,
                "round": race.round,
                "race": race.name,
                "circuit": race.circuit.name,
                "position": quali.position,
                "best_time": _ms_to_lap_string(quali.best_ms),
                "gap_to_pole_s": round(gap, 3) if gap is not None else None,
                "reached_q3": quali.q3_ms is not None,
            }
        )
    return output


def head_to_head(
    db: Session,
    driver_a: Driver,
    driver_b: Driver,
    seasons: Optional[Sequence[int]] = None,
    circuit_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Compare two drivers only across races where both actually took part."""
    def _indexed(driver: Driver):
        query = (
            select(RaceResult, Race)
            .join(Race, RaceResult.race_id == Race.id)
            .where(RaceResult.driver_id == driver.id, Race.is_completed.is_(True))
        )
        if seasons:
            query = query.where(Race.season.in_(list(seasons)))
        if circuit_id:
            query = query.where(Race.circuit_id == circuit_id)
        return {row[1].id: row for row in db.execute(query).all()}

    results_a = _indexed(driver_a)
    results_b = _indexed(driver_b)
    shared = sorted(
        set(results_a) & set(results_b),
        key=lambda rid: (results_a[rid][1].season, results_a[rid][1].round),
    )

    quali_a = {q.race_id: q for q in db.scalars(
        select(QualifyingResult).where(QualifyingResult.driver_id == driver_a.id)
    )}
    quali_b = {q.race_id: q for q in db.scalars(
        select(QualifyingResult).where(QualifyingResult.driver_id == driver_b.id)
    )}

    race_wins_a = race_wins_b = quali_wins_a = quali_wins_b = 0
    timeline: List[Dict[str, Any]] = []

    for race_id in shared:
        result_a, race = results_a[race_id]
        result_b, _ = results_b[race_id]

        # Only count a race head-to-head when both drivers were classified.
        winner = None
        if result_a.position and result_b.position:
            if result_a.position < result_b.position:
                race_wins_a += 1
                winner = driver_a.code or driver_a.family_name
            else:
                race_wins_b += 1
                winner = driver_b.code or driver_b.family_name

        qa, qb = quali_a.get(race_id), quali_b.get(race_id)
        quali_winner = None
        if qa and qb and qa.position and qb.position:
            if qa.position < qb.position:
                quali_wins_a += 1
                quali_winner = driver_a.code or driver_a.family_name
            else:
                quali_wins_b += 1
                quali_winner = driver_b.code or driver_b.family_name

        timeline.append(
            {
                "season": race.season,
                "round": race.round,
                "race": race.name,
                "circuit": race.circuit.name,
                "a_position": result_a.position,
                "a_position_text": result_a.position_text,
                "a_points": result_a.points,
                "a_grid": result_a.grid,
                "b_position": result_b.position,
                "b_position_text": result_b.position_text,
                "b_points": result_b.points,
                "b_grid": result_b.grid,
                "race_winner": winner,
                "quali_winner": quali_winner,
            }
        )

    return {
        "driver_a": driver_summary(db, driver_a, seasons, circuit_id).to_dict(),
        "driver_b": driver_summary(db, driver_b, seasons, circuit_id).to_dict(),
        "shared_races": len(shared),
        "race_head_to_head": {
            "a": race_wins_a,
            "b": race_wins_b,
            "counted": race_wins_a + race_wins_b,
        },
        "qualifying_head_to_head": {
            "a": quali_wins_a,
            "b": quali_wins_b,
            "counted": quali_wins_a + quali_wins_b,
        },
        "timeline": timeline,
    }


# ---------------------------------------------------------------------------
# Constructor analytics
# ---------------------------------------------------------------------------
def constructor_summary(
    db: Session, constructor: Constructor, seasons: Optional[Sequence[int]] = None
) -> Dict[str, Any]:
    query = (
        select(RaceResult, Race)
        .join(Race, RaceResult.race_id == Race.id)
        .where(
            RaceResult.constructor_id == constructor.id, Race.is_completed.is_(True)
        )
    )
    if seasons:
        query = query.where(Race.season.in_(list(seasons)))
    rows = db.execute(query).all()
    results = [row[0] for row in rows]
    positions = [r.position for r in results if r.position]
    entries = len(results)
    race_ids = {row[1].id for row in rows}

    return {
        "constructor_id": constructor.id,
        "ref": constructor.ref,
        "name": constructor.name,
        "nationality": constructor.nationality,
        "color": constructor.color,
        "race_entries": entries,
        "races": len(race_ids),
        "wins": sum(1 for p in positions if p == 1),
        "podiums": sum(1 for p in positions if p <= PODIUM_POSITION),
        "points_finishes": sum(1 for p in positions if p <= POINTS_POSITION),
        "total_points": round(sum(r.points for r in results), 1),
        "dnfs": sum(1 for r in results if not r.finished),
        "reliability_rate": _rate(sum(1 for r in results if r.finished), entries),
        "avg_finish": round(sum(positions) / len(positions), 2) if positions else None,
        "seasons": sorted({row[1].season for row in rows}),
    }


def constructor_season_points(db: Session, season: int) -> List[Dict[str, Any]]:
    """Cumulative constructor points, round by round -- the classic season chart."""
    rows = db.execute(
        select(
            Race.round,
            Race.name,
            Constructor.id,
            Constructor.name,
            Constructor.color,
            func.sum(RaceResult.points),
        )
        .join(RaceResult, RaceResult.race_id == Race.id)
        .join(Constructor, RaceResult.constructor_id == Constructor.id)
        .where(Race.season == season, Race.is_completed.is_(True))
        .group_by(Race.round, Race.name, Constructor.id, Constructor.name, Constructor.color)
        .order_by(Race.round)
    ).all()

    series: Dict[int, Dict[str, Any]] = {}
    running: Dict[int, float] = {}
    for rnd, race_name, cid, cname, color, points in rows:
        running[cid] = running.get(cid, 0.0) + float(points or 0)
        entry = series.setdefault(
            cid, {"constructor_id": cid, "name": cname, "color": color, "points": []}
        )
        entry["points"].append(
            {
                "round": rnd,
                "race": race_name,
                "round_points": round(float(points or 0), 1),
                "cumulative_points": round(running[cid], 1),
            }
        )
    return sorted(
        series.values(),
        key=lambda s: s["points"][-1]["cumulative_points"] if s["points"] else 0,
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Circuit analytics
# ---------------------------------------------------------------------------
def circuit_history(
    db: Session, circuit: Circuit, seasons: Optional[Sequence[int]] = None
) -> Dict[str, Any]:
    """Who goes well here, and does starting position actually matter?"""
    query = (
        select(RaceResult, Race, Driver, Constructor)
        .join(Race, RaceResult.race_id == Race.id)
        .join(Driver, RaceResult.driver_id == Driver.id)
        .join(Constructor, RaceResult.constructor_id == Constructor.id)
        .where(Race.circuit_id == circuit.id, Race.is_completed.is_(True))
    )
    if seasons:
        query = query.where(Race.season.in_(list(seasons)))
    rows = db.execute(query.order_by(Race.season.desc())).all()

    by_driver: Dict[int, Dict[str, Any]] = {}
    grid_buckets: Dict[str, Dict[str, int]] = {}
    winners: List[Dict[str, Any]] = []
    seasons_seen = set()

    for result, race, driver, constructor in rows:
        seasons_seen.add(race.season)
        entry = by_driver.setdefault(
            driver.id,
            {
                "driver_id": driver.id,
                "ref": driver.ref,
                "name": driver_label(driver),
                "code": driver.code,
                "constructor": constructor.name,
                "color": constructor.color,
                "starts": 0,
                "wins": 0,
                "podiums": 0,
                "points_finishes": 0,
                "dnfs": 0,
                "points": 0.0,
                "positions": [],
                "grids": [],
            },
        )
        entry["starts"] += 1
        entry["points"] += result.points
        if not result.finished:
            entry["dnfs"] += 1
        if result.position:
            entry["positions"].append(result.position)
            if result.position == 1:
                entry["wins"] += 1
                winners.append(
                    {
                        "season": race.season,
                        "driver": driver_label(driver),
                        "code": driver.code,
                        "constructor": constructor.name,
                        "color": constructor.color,
                        "grid": result.grid,
                    }
                )
            if result.position <= PODIUM_POSITION:
                entry["podiums"] += 1
            if result.position <= POINTS_POSITION:
                entry["points_finishes"] += 1
        if result.grid and result.grid > 0:
            entry["grids"].append(result.grid)
            bucket = _grid_bucket(result.grid)
            stats = grid_buckets.setdefault(
                bucket, {"starts": 0, "podiums": 0, "points": 0, "wins": 0}
            )
            stats["starts"] += 1
            if result.position:
                if result.position == 1:
                    stats["wins"] += 1
                if result.position <= PODIUM_POSITION:
                    stats["podiums"] += 1
                if result.position <= POINTS_POSITION:
                    stats["points"] += 1

    drivers = []
    for entry in by_driver.values():
        positions, grids = entry.pop("positions"), entry.pop("grids")
        entry["avg_finish"] = round(sum(positions) / len(positions), 2) if positions else None
        entry["best_finish"] = min(positions) if positions else None
        entry["avg_grid"] = round(sum(grids) / len(grids), 2) if grids else None
        entry["points"] = round(entry["points"], 1)
        entry["podium_rate"] = _rate(entry["podiums"], entry["starts"])
        drivers.append(entry)

    drivers.sort(key=lambda d: (-d["podiums"], -d["points"], d["avg_finish"] or 99))

    grid_analysis = [
        {
            "bucket": bucket,
            "starts": stats["starts"],
            "win_rate": _rate(stats["wins"], stats["starts"]),
            "podium_rate": _rate(stats["podiums"], stats["starts"]),
            "points_rate": _rate(stats["points"], stats["starts"]),
        }
        for bucket, stats in sorted(grid_buckets.items(), key=lambda kv: _bucket_order(kv[0]))
    ]

    return {
        "circuit": {
            "id": circuit.id,
            "ref": circuit.ref,
            "name": circuit.name,
            "locality": circuit.locality,
            "country": circuit.country,
            "circuit_type": circuit.circuit_type,
            "overtaking_difficulty": circuit.overtaking_difficulty,
            "tyre_degradation": circuit.tyre_degradation,
            "pit_loss_seconds": circuit.pit_loss_seconds,
            "drs_zones": circuit.drs_zones,
            "notes": circuit.notes,
        },
        "seasons_covered": sorted(seasons_seen),
        "races_counted": len(seasons_seen),
        "top_drivers": drivers[:12],
        "grid_analysis": grid_analysis,
        "winners": sorted(winners, key=lambda w: w["season"], reverse=True),
        "pole_to_win_rate": _pole_to_win_rate(db, circuit, seasons),
    }


def _grid_bucket(grid: int) -> str:
    if grid == 1:
        return "P1 (pole)"
    if grid <= 3:
        return "P2-P3"
    if grid <= 6:
        return "P4-P6"
    if grid <= 10:
        return "P7-P10"
    return "P11+"


def _bucket_order(bucket: str) -> int:
    return ["P1 (pole)", "P2-P3", "P4-P6", "P7-P10", "P11+"].index(bucket)


def _pole_to_win_rate(
    db: Session, circuit: Circuit, seasons: Optional[Sequence[int]] = None
) -> Dict[str, Any]:
    query = (
        select(RaceResult.position)
        .join(Race, RaceResult.race_id == Race.id)
        .where(
            Race.circuit_id == circuit.id,
            Race.is_completed.is_(True),
            RaceResult.grid == 1,
        )
    )
    if seasons:
        query = query.where(Race.season.in_(list(seasons)))
    positions = [p for (p,) in db.execute(query).all()]
    wins = sum(1 for p in positions if p == 1)
    podiums = sum(1 for p in positions if p and p <= PODIUM_POSITION)
    return {
        "poles_counted": len(positions),
        "win_rate": _rate(wins, len(positions)),
        "podium_rate": _rate(podiums, len(positions)),
    }


def circuit_pit_strategy(db: Session, circuit: Circuit) -> Dict[str, Any]:
    """Observed stop counts and pit-lane timings at a circuit.

    This is the evidence behind any tyre-strategy explanation: how many stops
    drivers have actually made here, and how long a stop costs.
    """
    rows = db.execute(
        select(Race.season, Race.name, PitStop.driver_id, func.count(PitStop.id), func.avg(PitStop.lap))
        .join(Race, PitStop.race_id == Race.id)
        .where(Race.circuit_id == circuit.id)
        .group_by(Race.season, Race.name, PitStop.driver_id)
    ).all()

    if not rows:
        return {
            "sample_size": 0,
            "stop_distribution": [],
            "avg_stops": None,
            "median_stop_duration_s": None,
            "note": "No pit-stop data ingested for this circuit yet.",
        }

    distribution: Dict[int, int] = {}
    for _, _, _, stops, _ in rows:
        distribution[stops] = distribution.get(stops, 0) + 1
    total = sum(distribution.values())

    durations = [
        d
        for (d,) in db.execute(
            select(PitStop.duration_ms)
            .join(Race, PitStop.race_id == Race.id)
            .where(Race.circuit_id == circuit.id, PitStop.duration_ms.isnot(None))
        ).all()
        # Stops over 60s are almost always a retirement or a penalty served.
        if d and d < 60_000
    ]
    durations.sort()

    return {
        "sample_size": total,
        "stop_distribution": [
            {
                "stops": stops,
                "driver_races": count,
                "share": _rate(count, total),
            }
            for stops, count in sorted(distribution.items())
        ],
        "avg_stops": round(sum(s * c for s, c in distribution.items()) / total, 2),
        "median_stop_duration_s": round(durations[len(durations) // 2] / 1000, 2)
        if durations
        else None,
        "pit_loss_seconds": circuit.pit_loss_seconds,
    }


# ---------------------------------------------------------------------------
# Standings & season overview
# ---------------------------------------------------------------------------
def season_standings(db: Session, season: int) -> Dict[str, Any]:
    latest_round = db.scalar(
        select(func.max(DriverStanding.round)).where(DriverStanding.season == season)
    )
    drivers, constructors = [], []

    if latest_round is not None:
        driver_rows = db.execute(
            select(DriverStanding, Driver, Constructor)
            .join(Driver, DriverStanding.driver_id == Driver.id)
            .outerjoin(Constructor, DriverStanding.constructor_id == Constructor.id)
            .where(DriverStanding.season == season, DriverStanding.round == latest_round)
            .order_by(DriverStanding.position)
        ).all()
        drivers = [
            {
                "position": standing.position,
                "driver_id": driver.id,
                "ref": driver.ref,
                "name": driver_label(driver),
                "code": driver.code,
                "constructor": constructor.name if constructor else None,
                "color": constructor.color if constructor else None,
                "points": standing.points,
                "wins": standing.wins,
            }
            for standing, driver, constructor in driver_rows
        ]

        constructor_rows = db.execute(
            select(ConstructorStanding, Constructor)
            .join(Constructor, ConstructorStanding.constructor_id == Constructor.id)
            .where(
                ConstructorStanding.season == season,
                ConstructorStanding.round == latest_round,
            )
            .order_by(ConstructorStanding.position)
        ).all()
        constructors = [
            {
                "position": standing.position,
                "constructor_id": constructor.id,
                "ref": constructor.ref,
                "name": constructor.name,
                "color": constructor.color,
                "points": standing.points,
                "wins": standing.wins,
            }
            for standing, constructor in constructor_rows
        ]

    return {
        "season": season,
        "through_round": latest_round,
        "drivers": drivers,
        "constructors": constructors,
    }


def race_detail(db: Session, race: Race) -> Dict[str, Any]:
    results = db.execute(
        select(RaceResult, Driver, Constructor)
        .join(Driver, RaceResult.driver_id == Driver.id)
        .join(Constructor, RaceResult.constructor_id == Constructor.id)
        .where(RaceResult.race_id == race.id)
        .order_by(
            case((RaceResult.position.is_(None), 1), else_=0), RaceResult.position
        )
    ).all()

    qualifying = db.execute(
        select(QualifyingResult, Driver, Constructor)
        .join(Driver, QualifyingResult.driver_id == Driver.id)
        .join(Constructor, QualifyingResult.constructor_id == Constructor.id)
        .where(QualifyingResult.race_id == race.id)
        .order_by(QualifyingResult.position)
    ).all()

    pole_ms = qualifying[0][0].best_ms if qualifying else None

    return {
        "race": {
            "id": race.id,
            "season": race.season,
            "round": race.round,
            "name": race.name,
            "date": race.date.isoformat() if race.date else None,
            "url": race.url,
            "is_completed": race.is_completed,
            "weather": race.weather,
            "total_laps": race.total_laps,
            "circuit": {
                "id": race.circuit.id,
                "ref": race.circuit.ref,
                "name": race.circuit.name,
                "locality": race.circuit.locality,
                "country": race.circuit.country,
                "circuit_type": race.circuit.circuit_type,
                "overtaking_difficulty": race.circuit.overtaking_difficulty,
                "tyre_degradation": race.circuit.tyre_degradation,
                "pit_loss_seconds": race.circuit.pit_loss_seconds,
                "drs_zones": race.circuit.drs_zones,
                "notes": race.circuit.notes,
            },
        },
        "results": [
            {
                "position": result.position,
                "position_text": result.position_text,
                "driver_id": driver.id,
                "ref": driver.ref,
                "driver": driver_label(driver),
                "code": driver.code,
                "constructor": constructor.name,
                "color": constructor.color,
                "grid": result.grid,
                "positions_gained": (result.grid - result.position)
                if result.position and result.grid and result.grid > 0
                else None,
                "laps": result.laps,
                "points": result.points,
                "status": result.status,
                "finished": result.finished,
                "fastest_lap": _ms_to_lap_string(result.fastest_lap_ms),
                "fastest_lap_rank": result.fastest_lap_rank,
            }
            for result, driver, constructor in results
        ],
        "qualifying": [
            {
                "position": quali.position,
                "driver_id": driver.id,
                "ref": driver.ref,
                "driver": driver_label(driver),
                "code": driver.code,
                "constructor": constructor.name,
                "color": constructor.color,
                "q1": _ms_to_lap_string(quali.q1_ms),
                "q2": _ms_to_lap_string(quali.q2_ms),
                "q3": _ms_to_lap_string(quali.q3_ms),
                "best": _ms_to_lap_string(quali.best_ms),
                "gap_to_pole_s": round((quali.best_ms - pole_ms) / 1000.0, 3)
                if quali.best_ms and pole_ms
                else None,
            }
            for quali, driver, constructor in qualifying
        ],
    }


def constructor_form(
    db: Session, constructor_id: int, before_race: Race, window: int = 5
) -> Dict[str, Any]:
    """Average points per car and finish rate over the preceding races."""
    race_ids = [
        r
        for (r,) in db.execute(
            select(Race.id)
            .where(_is_before(before_race))
            .order_by(Race.season.desc(), Race.round.desc())
            .limit(window)
        ).all()
    ]
    if not race_ids:
        return {"races_counted": 0, "avg_points_per_car": None, "finish_rate": None}

    rows = db.scalars(
        select(RaceResult).where(
            RaceResult.constructor_id == constructor_id,
            RaceResult.race_id.in_(race_ids),
        )
    ).all()
    if not rows:
        return {"races_counted": 0, "avg_points_per_car": None, "finish_rate": None}

    return {
        "races_counted": len({r.race_id for r in rows}),
        "avg_points_per_car": round(sum(r.points for r in rows) / len(rows), 2),
        "finish_rate": _rate(sum(1 for r in rows if r.finished), len(rows)),
        "entries": len(rows),
    }


def search_entities(db: Session, query: str, limit: int = 8) -> Dict[str, List[Dict[str, Any]]]:
    needle = f"%{query.strip().lower()}%"
    drivers = db.scalars(
        select(Driver)
        .where(
            func.lower(Driver.given_name + " " + Driver.family_name).like(needle)
            | func.lower(Driver.code).like(needle)
        )
        .limit(limit)
    ).all()
    constructors = db.scalars(
        select(Constructor).where(func.lower(Constructor.name).like(needle)).limit(limit)
    ).all()
    circuits = db.scalars(
        select(Circuit)
        .where(
            func.lower(Circuit.name).like(needle)
            | func.lower(Circuit.locality).like(needle)
            | func.lower(Circuit.country).like(needle)
        )
        .limit(limit)
    ).all()
    return {
        "drivers": [
            {"id": d.id, "ref": d.ref, "name": driver_label(d), "code": d.code}
            for d in drivers
        ],
        "constructors": [
            {"id": c.id, "ref": c.ref, "name": c.name, "color": c.color}
            for c in constructors
        ],
        "circuits": [
            {"id": c.id, "ref": c.ref, "name": c.name, "country": c.country}
            for c in circuits
        ],
    }
