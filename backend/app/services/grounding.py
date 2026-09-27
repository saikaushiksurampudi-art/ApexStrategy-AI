"""Retrieval layer for the AI Race Analyst.

The assistant is never allowed to answer from its own memory of Formula 1. This
module is the gate: it reads the user's question, works out which entities and
which intent it refers to, pulls the matching rows out of the database, and
returns a *context pack* -- the facts, plus a citation for every one of them.

If the context pack comes back empty, the generator is instructed to say it has
no data rather than to improvise. That single rule is what keeps the product's
promise of evidence-based answers.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Circuit, Constructor, Driver, Race
from app.services import analytics
from app.services.prediction import get_model, predict_race

logger = logging.getLogger(__name__)

MAX_SEASONS_IN_CONTEXT = 5

INTENT_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "tyre_strategy": (
        "tyre", "tire", "stop", "stint", "undercut", "overcut", "pit",
        "strategy", "degradation", "compound",
    ),
    "prediction": (
        "predict", "prediction", "chance", "chances", "odds", "probability",
        "likely", "favourite", "favorite", "will win", "expect",
    ),
    "qualifying": ("qualifying", "quali", "pole", "q3", "grid", "one lap"),
    "standings": ("standings", "championship", "title", "leader", "points table"),
    "circuit": ("circuit", "track", "at ", "grand prix", "gp", "here"),
    "comparison": ("compare", "versus", " vs ", "against", "better than", "head to head"),
}


@dataclass
class ContextPack:
    """Facts the model may use, and nothing else."""

    intent: str
    question: str
    entities: Dict[str, Any] = field(default_factory=dict)
    facts: Dict[str, Any] = field(default_factory=dict)
    citations: List[Dict[str, str]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return bool(self.facts)

    def cite(self, source: str, detail: str) -> None:
        entry = {"source": source, "detail": detail}
        if entry not in self.citations:
            self.citations.append(entry)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "entities": self.entities,
            "facts": self.facts,
            "citations": self.citations,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------
def _extract_seasons(question: str) -> List[int]:
    years = [int(y) for y in re.findall(r"\b(19[5-9]\d|20[0-4]\d)\b", question)]
    return sorted(set(years))


def _candidate_terms(question: str) -> List[str]:
    """Capitalised words and quoted phrases are the likely entity mentions."""
    quoted = re.findall(r'"([^"]+)"', question)
    # Two-word proper nouns first ("Max Verstappen", "Red Bull"), then singles.
    pairs = re.findall(r"\b([A-Z][a-zA-Z]+)\s+([A-Z][a-zA-Z]+)\b", question)
    singles = re.findall(r"\b([A-Z][a-zA-Z]{2,})\b", question)
    terms = quoted + [f"{a} {b}" for a, b in pairs] + singles
    # Also try lowercase surnames -- people type "verstappen vs leclerc".
    terms += re.findall(r"\b([a-z]{4,})\b", question)
    seen, ordered = set(), []
    for term in terms:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(term)
    return ordered


STOPWORDS = {
    "what", "which", "who", "when", "where", "why", "how", "does", "did", "will",
    "compare", "comparison", "versus", "against", "between", "about", "this",
    "that", "than", "with", "from", "have", "has", "been", "their", "there",
    "they", "them", "were", "was", "the", "and", "for", "are", "race", "races",
    "season", "seasons", "driver", "drivers", "team", "teams", "constructor",
    "circuit", "track", "lap", "laps", "best", "better", "good", "well",
    "performance", "strategy", "tyre", "tire", "tires", "tyres", "stop",
    "stops", "pit", "grand", "prix", "formula", "chance", "chances", "odds",
    "probability", "podium", "points", "win", "wins", "won", "explain", "tell",
    "show", "give", "should", "could", "would", "risky", "risk", "here",
    "historically", "history", "performed", "perform", "might", "work",
    "upcoming", "weekend", "qualifying", "quali", "standings", "championship",
}


def extract_entities(db: Session, question: str) -> Dict[str, Any]:
    """Resolve drivers, constructors and circuits mentioned in the question."""
    drivers: List[Driver] = []
    constructors: List[Constructor] = []
    circuits: List[Circuit] = []
    seen_drivers, seen_constructors, seen_circuits = set(), set(), set()

    for term in _candidate_terms(question):
        if term.lower() in STOPWORDS or len(term) < 3:
            continue

        driver = analytics.resolve_driver(db, term)
        if driver and driver.id not in seen_drivers:
            seen_drivers.add(driver.id)
            drivers.append(driver)
            continue

        constructor = analytics.resolve_constructor(db, term)
        if constructor and constructor.id not in seen_constructors:
            seen_constructors.add(constructor.id)
            constructors.append(constructor)
            continue

        circuit = analytics.resolve_circuit(db, term)
        if circuit and circuit.id not in seen_circuits:
            seen_circuits.add(circuit.id)
            circuits.append(circuit)

    return {
        "drivers": drivers[:3],
        "constructors": constructors[:3],
        "circuits": circuits[:2],
        "seasons": _extract_seasons(question),
    }


def classify_intent(question: str, entities: Dict[str, Any]) -> str:
    """Pick the most specific intent the question matches."""
    lowered = f" {question.lower()} "
    scores: Dict[str, int] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in lowered)
        if hits:
            scores[intent] = hits

    if len(entities.get("drivers", [])) >= 2:
        scores["comparison"] = scores.get("comparison", 0) + 3
    if entities.get("circuits"):
        scores["circuit"] = scores.get("circuit", 0) + 1

    # Prediction and tyre questions are the most specific, so they win ties.
    for priority in ("prediction", "tyre_strategy", "comparison"):
        if scores.get(priority):
            return priority
    if not scores:
        return "driver_profile" if entities.get("drivers") else "general"
    return max(scores, key=scores.get)


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------
def build_context(
    db: Session,
    question: str,
    race_id: Optional[int] = None,
) -> ContextPack:
    """Assemble the facts an answer to ``question`` is allowed to use."""
    entities = extract_entities(db, question)
    intent = classify_intent(question, entities)

    pack = ContextPack(
        intent=intent,
        question=question,
        entities={
            "drivers": [
                {"id": d.id, "ref": d.ref, "name": analytics.driver_label(d)}
                for d in entities["drivers"]
            ],
            "constructors": [
                {"id": c.id, "ref": c.ref, "name": c.name}
                for c in entities["constructors"]
            ],
            "circuits": [
                {"id": c.id, "ref": c.ref, "name": c.name}
                for c in entities["circuits"]
            ],
            "seasons": entities["seasons"],
        },
    )

    seasons = entities["seasons"] or None
    bounds = analytics.season_bounds(db)
    if bounds["first_season"] is None:
        pack.notes.append(
            "The database contains no race data yet -- run the ingest script first."
        )
    else:
        pack.notes.append(
            f"The database covers seasons {bounds['first_season']}-{bounds['last_season']}."
        )
    if seasons and bounds["first_season"] is not None:
        available = set(range(bounds["first_season"] or 0, (bounds["last_season"] or 0) + 1))
        missing = [s for s in seasons if s not in available]
        if missing:
            pack.notes.append(
                f"No data is held for season(s) {missing}; they cannot be discussed."
            )
            seasons = [s for s in seasons if s in available] or None

    target_race = _resolve_race(db, race_id, entities)

    handlers = {
        "comparison": _ground_comparison,
        "prediction": _ground_prediction,
        "tyre_strategy": _ground_tyre_strategy,
        "circuit": _ground_circuit,
        "qualifying": _ground_qualifying,
        "standings": _ground_standings,
        "driver_profile": _ground_driver_profile,
        "general": _ground_general,
    }
    handler = handlers.get(intent, _ground_general)
    handler(db, pack, entities, seasons, target_race)

    # A question about specific drivers should always carry their records, even
    # when the primary intent was something else.
    if entities["drivers"] and "drivers" not in pack.facts:
        _attach_driver_summaries(db, pack, entities["drivers"], seasons)

    if not pack.has_data:
        pack.notes.append(
            "No matching records were found for this question in the database."
        )

    return pack


def _resolve_race(
    db: Session, race_id: Optional[int], entities: Dict[str, Any]
) -> Optional[Race]:
    if race_id:
        race = db.get(Race, race_id)
        if race:
            return race
    if entities["circuits"]:
        circuit = entities["circuits"][0]
        query = select(Race).where(Race.circuit_id == circuit.id)
        if entities["seasons"]:
            query = query.where(Race.season.in_(entities["seasons"]))
        race = db.scalars(
            query.order_by(Race.season.desc(), Race.round.desc()).limit(1)
        ).first()
        if race:
            return race
    return analytics.next_race(db)


def _attach_driver_summaries(
    db: Session,
    pack: ContextPack,
    drivers: List[Driver],
    seasons: Optional[List[int]],
    circuit_id: Optional[int] = None,
) -> None:
    summaries = []
    for driver in drivers:
        summary = analytics.driver_summary(db, driver, seasons, circuit_id)
        if summary.races == 0:
            continue
        summaries.append(summary.to_dict())
        scope = f"seasons {summary.seasons}" if summary.seasons else "all seasons"
        pack.cite(
            "race_results",
            f"{summary.name}: {summary.races} races across {scope}",
        )
    if summaries:
        pack.facts["drivers"] = summaries


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------
def _ground_comparison(db, pack, entities, seasons, race) -> None:
    drivers = entities["drivers"]
    circuit = entities["circuits"][0] if entities["circuits"] else None

    if len(drivers) >= 2:
        comparison = analytics.head_to_head(
            db, drivers[0], drivers[1], seasons, circuit.id if circuit else None
        )
        if comparison["shared_races"] == 0:
            pack.notes.append(
                f"{analytics.driver_label(drivers[0])} and "
                f"{analytics.driver_label(drivers[1])} have no races in common "
                "in the selected scope."
            )
            return
        pack.facts["head_to_head"] = comparison
        pack.cite(
            "race_results",
            f"{comparison['shared_races']} shared races between "
            f"{comparison['driver_a']['name']} and {comparison['driver_b']['name']}"
            + (f" at {circuit.name}" if circuit else ""),
        )
        pack.cite(
            "qualifying_results",
            f"qualifying head-to-head over "
            f"{comparison['qualifying_head_to_head']['counted']} sessions",
        )
        return

    if len(entities["constructors"]) >= 2:
        pack.facts["constructors"] = [
            analytics.constructor_summary(db, c, seasons)
            for c in entities["constructors"][:2]
        ]
        pack.cite("race_results", "constructor race entries and points")
        return

    _ground_driver_profile(db, pack, entities, seasons, race)


def _ground_driver_profile(db, pack, entities, seasons, race) -> None:
    drivers = entities["drivers"]
    circuit = entities["circuits"][0] if entities["circuits"] else None
    if not drivers:
        _ground_general(db, pack, entities, seasons, race)
        return

    _attach_driver_summaries(db, pack, drivers, seasons, circuit.id if circuit else None)

    bounds = analytics.season_bounds(db)
    latest = bounds["last_season"]
    progression = analytics.driver_season_progression(db, drivers[0], latest)
    if progression:
        pack.facts["season_progression"] = {
            "season": latest,
            "driver": analytics.driver_label(drivers[0]),
            "races": progression,
        }
        pack.cite("race_results", f"{latest} season race-by-race results")


def _ground_circuit(db, pack, entities, seasons, race) -> None:
    circuit = entities["circuits"][0] if entities["circuits"] else (
        race.circuit if race else None
    )
    if circuit is None:
        _ground_general(db, pack, entities, seasons, race)
        return

    history = analytics.circuit_history(db, circuit, seasons)
    if not history["top_drivers"]:
        pack.notes.append(f"No results are held for {circuit.name}.")
        return

    pack.facts["circuit_history"] = history
    pack.cite(
        "race_results",
        f"{circuit.name}: {history['races_counted']} races in seasons "
        f"{history['seasons_covered']}",
    )
    if history["circuit"]["notes"]:
        pack.cite("circuit_metadata", f"editorial track notes for {circuit.name}")

    if entities["drivers"]:
        _attach_driver_summaries(db, pack, entities["drivers"], seasons, circuit.id)


def _ground_tyre_strategy(db, pack, entities, seasons, race) -> None:
    circuit = entities["circuits"][0] if entities["circuits"] else (
        race.circuit if race else None
    )
    if circuit is None:
        _ground_general(db, pack, entities, seasons, race)
        return

    strategy = analytics.circuit_pit_strategy(db, circuit)
    history = analytics.circuit_history(db, circuit, seasons)

    pack.facts["pit_strategy"] = strategy
    pack.facts["circuit_profile"] = history["circuit"]
    pack.facts["grid_analysis"] = history["grid_analysis"]

    if strategy["sample_size"]:
        pack.cite(
            "pit_stops",
            f"{circuit.name}: stop counts from {strategy['sample_size']} driver-races",
        )
    pack.cite(
        "circuit_metadata",
        f"{circuit.name} track character "
        f"(degradation: {circuit.tyre_degradation}, "
        f"overtaking: {circuit.overtaking_difficulty})",
    )
    if history["grid_analysis"]:
        pack.cite(
            "race_results",
            f"{circuit.name}: conversion rates by starting-position bucket",
        )


def _ground_prediction(db, pack, entities, seasons, race) -> None:
    if race is None:
        pack.notes.append("No race could be identified for a prediction.")
        return

    if get_model() is None:
        pack.notes.append(
            "No trained model is loaded, so no probabilities can be quoted."
        )
        _ground_circuit(db, pack, entities, seasons, race)
        return

    outcome = predict_race(db, race, explain=True)
    if not outcome.get("available"):
        pack.notes.append(outcome.get("message", "Predictions are unavailable."))
        return

    wanted = {d.id for d in entities["drivers"]}
    predictions = outcome["predictions"]
    focus = [p for p in predictions if p["driver_id"] in wanted] if wanted else []

    pack.facts["prediction"] = {
        "race": outcome["race"],
        "season": outcome["season"],
        "round": outcome["round"],
        "circuit": outcome["circuit"],
        "model_version": outcome["model_version"],
        "grid_source": outcome["grid_source"],
        "is_completed": outcome["is_completed"],
        "disclaimer": outcome["disclaimer"],
        "focus_drivers": focus,
        "top_contenders": predictions[:6],
    }
    pack.cite(
        "predictions",
        f"model {outcome['model_version']} probabilities for {outcome['race']} "
        f"(grid source: {outcome['grid_source']})",
    )

    status = None
    try:
        from app.services.prediction import model_status

        status = model_status().get("evaluation")
    except Exception:  # pragma: no cover
        status = None
    if status:
        pack.facts["model_evaluation"] = status
        pack.cite("model_evaluation", "held-out season scores versus baselines")

    _ground_circuit(db, pack, entities, seasons, race)


def _ground_qualifying(db, pack, entities, seasons, race) -> None:
    if entities["drivers"]:
        trends = {}
        for driver in entities["drivers"][:2]:
            trend = analytics.driver_qualifying_trend(db, driver, seasons)
            if trend:
                trends[analytics.driver_label(driver)] = trend[-15:]
                pack.cite(
                    "qualifying_results",
                    f"{analytics.driver_label(driver)}: {len(trend)} qualifying sessions",
                )
        if trends:
            pack.facts["qualifying_trends"] = trends
        _attach_driver_summaries(db, pack, entities["drivers"], seasons)
        return

    if race is not None:
        detail = analytics.race_detail(db, race)
        if detail["qualifying"]:
            pack.facts["qualifying_session"] = {
                "race": detail["race"]["name"],
                "season": detail["race"]["season"],
                "results": detail["qualifying"],
            }
            pack.cite(
                "qualifying_results",
                f"{detail['race']['name']} {detail['race']['season']} qualifying",
            )


def _ground_standings(db, pack, entities, seasons, race) -> None:
    bounds = analytics.season_bounds(db)
    season = (seasons or [bounds["last_season"]])[-1]
    standings = analytics.season_standings(db, season)
    if not standings["drivers"]:
        pack.notes.append(f"No standings are held for {season}.")
        return
    pack.facts["standings"] = standings
    pack.cite(
        "driver_standings",
        f"{season} championship standings through round {standings['through_round']}",
    )


def _ground_general(db, pack, entities, seasons, race) -> None:
    """Fallback: describe the current state of the season and the next race."""
    bounds = analytics.season_bounds(db)
    season = (seasons or [bounds["last_season"]])[-1]
    standings = analytics.season_standings(db, season)
    if standings["drivers"]:
        pack.facts["standings"] = {
            "season": season,
            "through_round": standings["through_round"],
            "drivers": standings["drivers"][:10],
            "constructors": standings["constructors"],
        }
        pack.cite("driver_standings", f"{season} championship standings")

    if race is not None:
        detail = analytics.race_detail(db, race)
        pack.facts["race"] = detail["race"]
        if detail["results"]:
            pack.facts["race"]["podium"] = detail["results"][:3]
        pack.cite(
            "races",
            f"{detail['race']['name']} ({detail['race']['season']}) at "
            f"{detail['race']['circuit']['name']}",
        )
